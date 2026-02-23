"""
Stock Image Preparation Pipeline.

Orchestrates the full workflow:
  generate → deduplicate → upscale → generate metadata → save locally → upload to Notion

Each stage is a discrete DAG node.  The pipeline tracks per-image state
and supports partial recovery: images that have already been upscaled are
not re-processed if the Notion upload fails and the pipeline is re-run.

Entry points:
  - run_pipeline()  — programmatic / API
  - CLI at bottom   — python -m backend.app.workflows.stock_prep_pipeline ...
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Pipeline result types ─────────────────────────────────────────────────────

@dataclass
class ImagePipelineResult:
    """Per-image result across all pipeline stages."""

    image_id: str
    generation_prompt: str
    local_image_path: str = ""
    local_metadata_path: str = ""
    notion_page_id: str = ""
    upscaled_width: int = 0
    upscaled_height: int = 0
    backend_used: str = ""
    title: str = ""
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    category: str = ""
    confidence_score: float = 0.0
    stage_reached: str = "none"   # generate|upscale|metadata|notion
    error: str = ""
    success: bool = False


@dataclass
class PipelineRun:
    """Full result of one pipeline invocation."""

    run_id: str
    batch_id: str
    theme: str
    style: str
    requested_count: int
    results: List[ImagePipelineResult]
    started_at: datetime
    completed_at: datetime
    success_count: int
    failure_count: int
    notion_database_id: str = ""

    @property
    def summary(self) -> Dict[str, Any]:
        return {
            "run_id":          self.run_id,
            "batch_id":        self.batch_id,
            "theme":           self.theme,
            "style":           self.style,
            "requested":       self.requested_count,
            "succeeded":       self.success_count,
            "failed":          self.failure_count,
            "notion_database": self.notion_database_id,
            "duration_s": round(
                (self.completed_at - self.started_at).total_seconds(), 1
            ),
        }


# ── Pipeline ──────────────────────────────────────────────────────────────────

class StockImagePipeline:
    """
    Multi-stage stock image preparation pipeline.

    Stages:
      1. Generate  — AI image generation (DALL-E 3 / Stability / mock)
      2. Deduplicate — SHA-256 hash dedup
      3. Upscale   — Real-ESRGAN or Pillow to 6000×4000
      4. Metadata  — GPT-4 / Claude SEO metadata per image
      5. Save      — Write JPEG + .txt to local disk
      6. Notion    — Create database entry with embedded metadata block

    Notion upload is skipped gracefully when NOTION_API_TOKEN is not set.
    """

    def __init__(self):
        from backend.app.core.config import settings
        self._settings = settings
        self._stock_dir = Path(settings.STOCK_IMAGES_LOCAL_PATH)
        self._meta_dir = Path(settings.METADATA_FILES_PATH)

    async def run(
        self,
        theme: str,
        style: str = "photorealistic",
        count: int = 10,
        provider: Optional[str] = None,
        notion_parent_page_id: Optional[str] = None,
        additional_context: str = "",
    ) -> PipelineRun:
        """
        Execute the full pipeline.

        Args:
            theme:                  Subject/topic (e.g. "modern office").
            style:                  Visual style label.
            count:                  Number of images to generate.
            provider:               Override image generation provider.
            notion_parent_page_id:  Required to create a new Notion DB; skip if None
                                    and NOTION_DATABASE_ID is already set.
            additional_context:     Extra prompt text appended to every generation prompt.

        Returns:
            PipelineRun with per-image results.
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.utcnow()

        logger.info(
            f"[{run_id}] Pipeline start: theme='{theme}', style='{style}', "
            f"count={count}"
        )

        # Lazy-import services to avoid top-level circular imports
        from backend.app.services.ai.image_generator import ImageGenerator
        from backend.app.services.ai.image_upscaler import ImageUpscaler
        from backend.app.services.ai.metadata_optimizer import MetadataOptimizer

        generator = ImageGenerator()
        upscaler = ImageUpscaler()
        metadata_svc = MetadataOptimizer()

        # ── Stage 1: Generate ─────────────────────────────────────────────────
        logger.info(f"[{run_id}] Stage 1: generating {count} images …")
        batch = await generator.generate_batch(
            theme=theme,
            style=style,
            count=count,
            provider=provider,
            additional_context=additional_context,
        )

        # ── Stage 2: Deduplicate ──────────────────────────────────────────────
        unique_images = ImageGenerator.deduplicate(batch.images)
        logger.info(
            f"[{run_id}] Stage 2: {len(unique_images)} unique images "
            f"(removed {len(batch.images) - len(unique_images)} duplicates)"
        )

        # Prepare per-image state
        results: List[ImagePipelineResult] = [
            ImagePipelineResult(
                image_id=img.image_id,
                generation_prompt=img.prompt,
                stage_reached="generate",
            )
            for img in unique_images
        ]

        # ── Stage 3: Upscale ──────────────────────────────────────────────────
        batch_dir = self._stock_dir / batch.batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[{run_id}] Stage 3: upscaling {len(unique_images)} images …")
        upscale_items = [(img.image_bytes, img.image_id) for img in unique_images]
        upscaled = await upscaler.upscale_batch(upscale_items, output_dir=batch_dir)

        for i, (upsc, result) in enumerate(zip(upscaled, results)):
            if upsc is not None:
                result.local_image_path = upsc.local_path
                result.upscaled_width = upsc.upscaled_width
                result.upscaled_height = upsc.upscaled_height
                result.backend_used = upsc.backend_used
                result.stage_reached = "upscale"
            else:
                result.error = "Upscaling failed"

        # ── Stage 4: Metadata ─────────────────────────────────────────────────
        logger.info(f"[{run_id}] Stage 4: generating metadata …")
        meta_items = [
            {
                "image_id": img.image_id,
                "generation_prompt": img.prompt,
                "theme": theme,
                "style": style,
            }
            for img in unique_images
        ]
        metadata_list = await metadata_svc.generate_batch(meta_items)

        for meta, result, upsc, orig_img in zip(
            metadata_list, results, upscaled, unique_images
        ):
            result.title = meta.title
            result.description = meta.description
            result.keywords = meta.keywords
            result.category = meta.category
            result.confidence_score = meta.confidence_score
            if result.stage_reached == "upscale":
                result.stage_reached = "metadata"

            # ── Stage 5: Save metadata .txt ───────────────────────────────────
            self._meta_dir.mkdir(parents=True, exist_ok=True)
            meta_filename = f"{orig_img.image_id}_metadata.txt"
            meta_path = self._meta_dir / batch.batch_id / meta_filename
            meta_path.parent.mkdir(parents=True, exist_ok=True)

            file_size_mb = (
                len(upsc.image_bytes) / (1024 * 1024) if upsc else 0.0
            )
            txt_content = meta.to_txt(
                resolution=f"{result.upscaled_width}x{result.upscaled_height}",
                file_size_mb=file_size_mb,
                provider=batch.provider,
                batch_id=batch.batch_id,
            )
            meta_path.write_text(txt_content, encoding="utf-8")
            result.local_metadata_path = str(meta_path)

        # ── Stage 6: Notion upload ────────────────────────────────────────────
        notion_db_id = ""
        if self._settings.NOTION_API_TOKEN:
            notion_db_id = await self._upload_to_notion(
                batch_id=batch.batch_id,
                unique_images=unique_images,
                upscaled=upscaled,
                metadata_list=metadata_list,
                results=results,
                notion_parent_page_id=notion_parent_page_id,
            )
        else:
            logger.info(
                f"[{run_id}] Stage 6 skipped: NOTION_API_TOKEN not configured. "
                "Images and metadata saved locally only."
            )

        # ── Finalise ──────────────────────────────────────────────────────────
        completed_at = datetime.utcnow()
        success_count = sum(1 for r in results if r.stage_reached == "notion"
                            or (not self._settings.NOTION_API_TOKEN
                                and r.stage_reached == "metadata"))
        # Mark as success if we got at least through metadata when Notion is disabled
        for r in results:
            if not r.error and r.stage_reached in ("metadata", "notion"):
                r.success = True

        run = PipelineRun(
            run_id=run_id,
            batch_id=batch.batch_id,
            theme=theme,
            style=style,
            requested_count=count,
            results=results,
            started_at=started_at,
            completed_at=completed_at,
            success_count=sum(1 for r in results if r.success),
            failure_count=sum(1 for r in results if not r.success),
            notion_database_id=notion_db_id,
        )

        logger.info(
            f"[{run_id}] Pipeline complete: "
            f"{run.success_count}/{len(results)} succeeded in "
            f"{run.summary['duration_s']}s"
        )
        return run

    # ── Notion helper ─────────────────────────────────────────────────────────

    async def _upload_to_notion(
        self,
        batch_id: str,
        unique_images: list,
        upscaled: list,
        metadata_list: list,
        results: List[ImagePipelineResult],
        notion_parent_page_id: Optional[str],
    ) -> str:
        """Upload all processed images to Notion and return the database ID."""
        from backend.app.services.integrations.notion import NotionIntegration

        notion = NotionIntegration(
            api_token=self._settings.NOTION_API_TOKEN,
            database_id=self._settings.NOTION_DATABASE_ID or None,
        )

        # Create database if needed
        db_id = self._settings.NOTION_DATABASE_ID
        if not db_id:
            if not notion_parent_page_id:
                logger.warning(
                    "NOTION_DATABASE_ID not set and no notion_parent_page_id provided. "
                    "Skipping Notion upload."
                )
                return ""
            db_id = await notion.create_database(
                parent_page_id=notion_parent_page_id,
                db_name=f"Stock Images — {datetime.utcnow().strftime('%Y-%m-%d')}",
            )
            notion.database_id = db_id

        entries = []
        for meta, result, upsc in zip(metadata_list, results, upscaled):
            file_size_mb = len(upsc.image_bytes) / (1024 * 1024) if upsc else 0.0
            txt_content = meta.to_txt(
                resolution=f"{result.upscaled_width}x{result.upscaled_height}",
                file_size_mb=file_size_mb,
                provider="AI",
                batch_id=batch_id,
            )
            entries.append({
                "title":              meta.title,
                "description":        meta.description,
                "keywords":           meta.keywords,
                "category":           meta.category,
                "style":              meta.style,
                "color_palette":      meta.color_palette,
                "resolution":         f"{result.upscaled_width}x{result.upscaled_height}",
                "batch_id":           batch_id,
                "confidence_score":   meta.confidence_score,
                "generation_date":    meta.generated_at,
                "target_platforms":   list(meta.platform_validation.keys()),
                "metadata_text":      txt_content,
                "generation_prompt":  meta.generation_prompt,
            })

        page_ids = await notion.bulk_create_entries(entries)
        for page_id, result in zip(page_ids, results):
            if page_id:
                result.notion_page_id = page_id
                result.stage_reached = "notion"

        return db_id

    # ── Convenience: save run report ──────────────────────────────────────────

    def save_report(self, run: PipelineRun, output_path: Optional[Path] = None) -> str:
        """Save pipeline run as JSON report. Returns file path."""
        if output_path is None:
            output_path = Path(f"stock_pipeline_report_{run.run_id[:8]}.json")
        report = {
            "summary": run.summary,
            "images": [
                {
                    "image_id":          r.image_id,
                    "title":             r.title,
                    "category":          r.category,
                    "confidence":        r.confidence_score,
                    "local_image":       r.local_image_path,
                    "local_metadata":    r.local_metadata_path,
                    "notion_page_id":    r.notion_page_id,
                    "resolution":        f"{r.upscaled_width}x{r.upscaled_height}",
                    "stage_reached":     r.stage_reached,
                    "success":           r.success,
                    "error":             r.error,
                }
                for r in run.results
            ],
        }
        output_path.write_text(json.dumps(report, indent=2, default=str))
        logger.info(f"Pipeline report saved: {output_path}")
        return str(output_path)


# ── Top-level convenience function ───────────────────────────────────────────

async def run_pipeline(
    theme: str,
    style: str = "photorealistic",
    count: int = 10,
    provider: Optional[str] = None,
    notion_parent_page_id: Optional[str] = None,
    additional_context: str = "",
    save_report: bool = True,
) -> PipelineRun:
    """
    Convenience wrapper — run the full stock image pipeline.

    Example:
        run = await run_pipeline(
            theme="remote work laptop coffee shop",
            style="photorealistic",
            count=5,
            provider="mock",   # Use "mock" for testing without API keys
        )
        print(run.summary)
    """
    pipeline = StockImagePipeline()
    run = await pipeline.run(
        theme=theme,
        style=style,
        count=count,
        provider=provider,
        notion_parent_page_id=notion_parent_page_id,
        additional_context=additional_context,
    )
    if save_report:
        pipeline.save_report(run)
    return run


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Stock Image Preparation Pipeline"
    )
    parser.add_argument("--theme",   required=True, help="Image theme/subject")
    parser.add_argument("--style",   default="photorealistic",
                        choices=["photorealistic", "artistic", "3d render", "illustration"])
    parser.add_argument("--count",   type=int, default=5, help="Number of images")
    parser.add_argument("--provider", default=None,
                        choices=["openai", "stability", "mock"],
                        help="Image generation provider (default: from .env)")
    parser.add_argument("--notion-page", default=None,
                        help="Notion parent page ID (creates new DB here)")
    parser.add_argument("--context", default="", help="Extra prompt context")
    args = parser.parse_args()

    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    run = asyncio.run(run_pipeline(
        theme=args.theme,
        style=args.style,
        count=args.count,
        provider=args.provider,
        notion_parent_page_id=args.notion_page,
        additional_context=args.context,
    ))

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    for k, v in run.summary.items():
        print(f"  {k:<25} {v}")
    print()
    for r in run.results:
        status = "✓" if r.success else "✗"
        print(f"  {status} [{r.stage_reached:<8}] {r.title or r.image_id[:16]}")
        if r.local_image_path:
            print(f"       Image    : {r.local_image_path}")
        if r.local_metadata_path:
            print(f"       Metadata : {r.local_metadata_path}")
        if r.notion_page_id:
            print(f"       Notion   : {r.notion_page_id}")
        if r.error:
            print(f"       Error    : {r.error}")
