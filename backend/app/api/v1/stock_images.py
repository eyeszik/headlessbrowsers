"""
Stock Images API endpoints.

Routes:
  POST   /stock-images/generate          Trigger a generation batch
  GET    /stock-images/batches           List reports in output directory
  GET    /stock-images/batches/{run_id}  Get a specific run report
  POST   /stock-images/notion/health     Check Notion connectivity
  GET    /stock-images/status            Pipeline configuration status
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    theme: str = Field(..., min_length=3, max_length=500,
                       description="Subject/topic for the images")
    style: str = Field(
        default="photorealistic",
        description="Visual style",
    )
    count: int = Field(default=5, ge=1, le=50,
                       description="Number of images to generate (max 50 per batch)")
    provider: Optional[str] = Field(
        default=None,
        description="Override image provider: openai | stability | mock",
    )
    notion_parent_page_id: Optional[str] = Field(
        default=None,
        description="Notion page ID to create a new database under",
    )
    additional_context: str = Field(
        default="",
        max_length=500,
        description="Extra text appended to every generation prompt",
    )
    run_async: bool = Field(
        default=False,
        description="If true, return immediately and run pipeline in background",
    )

    @field_validator("style")
    @classmethod
    def validate_style(cls, v: str) -> str:
        allowed = {"photorealistic", "artistic", "3d render", "illustration"}
        if v.lower() not in allowed:
            raise ValueError(f"style must be one of {allowed}")
        return v.lower()

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"openai", "stability", "mock"}
        if v.lower() not in allowed:
            raise ValueError(f"provider must be one of {allowed}")
        return v.lower()


class ImageResult(BaseModel):
    image_id: str
    title: str
    category: str
    confidence: float
    local_image: str
    local_metadata: str
    notion_page_id: str
    resolution: str
    stage_reached: str
    success: bool
    error: str


class GenerateResponse(BaseModel):
    success: bool
    run_id: str
    batch_id: str
    theme: str
    style: str
    requested: int
    succeeded: int
    failed: int
    duration_s: float
    notion_database_id: str
    images: List[ImageResult]
    report_path: str


class AsyncGenerateResponse(BaseModel):
    success: bool
    message: str
    run_id: str


class NotionHealthResponse(BaseModel):
    success: bool
    status: str
    user: Optional[str] = None
    database_title: Optional[str] = None
    error: Optional[str] = None


class StatusResponse(BaseModel):
    image_generation: Dict[str, Any]
    upscaling: Dict[str, Any]
    notion: Dict[str, Any]
    metadata: Dict[str, Any]
    storage: Dict[str, Any]


# ── In-memory job tracker (dev only; use Redis/DB for production) ─────────────
_running_jobs: Dict[str, str] = {}   # run_id → status


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateResponse, status_code=200)
async def generate_images(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
) -> GenerateResponse:
    """
    Trigger a stock image generation batch.

    Runs synchronously by default (returns when complete).
    Set run_async=true to return immediately with a run_id and check status later.
    """
    from backend.app.workflows.stock_prep_pipeline import run_pipeline
    import uuid as _uuid

    if request.run_async:
        run_id = str(_uuid.uuid4())
        _running_jobs[run_id] = "queued"

        async def _bg():
            _running_jobs[run_id] = "running"
            try:
                run = await run_pipeline(
                    theme=request.theme,
                    style=request.style,
                    count=request.count,
                    provider=request.provider,
                    notion_parent_page_id=request.notion_parent_page_id,
                    additional_context=request.additional_context,
                )
                _running_jobs[run_id] = f"complete:{run.batch_id}"
            except Exception as exc:
                _running_jobs[run_id] = f"error:{exc}"

        background_tasks.add_task(_bg)
        return AsyncGenerateResponse(   # type: ignore[return-value]
            success=True,
            message="Pipeline started in background. Poll /stock-images/jobs/{run_id}",
            run_id=run_id,
        )

    try:
        run = await run_pipeline(
            theme=request.theme,
            style=request.style,
            count=request.count,
            provider=request.provider,
            notion_parent_page_id=request.notion_parent_page_id,
            additional_context=request.additional_context,
        )
    except Exception as exc:
        logger.exception("Pipeline failed")
        raise HTTPException(status_code=500, detail=str(exc))

    return GenerateResponse(
        success=True,
        run_id=run.run_id,
        batch_id=run.batch_id,
        theme=run.theme,
        style=run.style,
        requested=run.requested_count,
        succeeded=run.success_count,
        failed=run.failure_count,
        duration_s=run.summary["duration_s"],
        notion_database_id=run.notion_database_id,
        report_path=f"stock_pipeline_report_{run.run_id[:8]}.json",
        images=[
            ImageResult(
                image_id=r.image_id,
                title=r.title,
                category=r.category,
                confidence=r.confidence_score,
                local_image=r.local_image_path,
                local_metadata=r.local_metadata_path,
                notion_page_id=r.notion_page_id,
                resolution=f"{r.upscaled_width}x{r.upscaled_height}",
                stage_reached=r.stage_reached,
                success=r.success,
                error=r.error,
            )
            for r in run.results
        ],
    )


@router.get("/batches", response_model=List[Dict[str, Any]])
async def list_batches(
    limit: int = Query(default=20, ge=1, le=100),
) -> List[Dict[str, Any]]:
    """Return metadata from the most recent pipeline run reports."""
    from backend.app.core.config import settings

    reports: List[Dict[str, Any]] = []
    pattern = "stock_pipeline_report_*.json"

    for report_file in sorted(
        Path(".").glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True
    )[:limit]:
        try:
            data = json.loads(report_file.read_text())
            reports.append(data.get("summary", {}))
        except Exception:
            pass
    return reports


@router.get("/batches/{run_id}", response_model=Dict[str, Any])
async def get_batch(run_id: str) -> Dict[str, Any]:
    """Return the full pipeline run report for a given run_id prefix."""
    matches = list(Path(".").glob(f"stock_pipeline_report_{run_id[:8]}*.json"))
    if not matches:
        raise HTTPException(status_code=404, detail=f"No report found for run_id={run_id}")
    return json.loads(matches[0].read_text())


@router.get("/jobs/{run_id}")
async def get_job_status(run_id: str) -> Dict[str, Any]:
    """Check the status of an async pipeline job."""
    status = _running_jobs.get(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Job {run_id} not found")
    return {"run_id": run_id, "status": status}


@router.post("/notion/health", response_model=NotionHealthResponse)
async def notion_health() -> NotionHealthResponse:
    """Verify Notion API token and database connectivity."""
    from backend.app.core.config import settings

    if not settings.NOTION_API_TOKEN:
        return NotionHealthResponse(
            success=False,
            status="not_configured",
            error="NOTION_API_TOKEN not set in environment",
        )

    from backend.app.services.integrations.notion import NotionIntegration
    notion = NotionIntegration(
        api_token=settings.NOTION_API_TOKEN,
        database_id=settings.NOTION_DATABASE_ID,
    )
    result = await notion.health_check()
    return NotionHealthResponse(
        success=result["status"] == "healthy",
        status=result["status"],
        user=result.get("user"),
        database_title=result.get("database_title"),
        error=result.get("error"),
    )


@router.get("/status", response_model=StatusResponse)
async def pipeline_status() -> StatusResponse:
    """Return current pipeline configuration and provider availability."""
    from backend.app.core.config import settings

    return StatusResponse(
        image_generation={
            "provider":      settings.IMAGE_GEN_PROVIDER,
            "openai_ready":  bool(settings.OPENAI_API_KEY),
            "stability_ready": bool(settings.STABILITY_AI_API_KEY),
            "mock_ready":    True,
            "batch_size":    settings.IMAGE_GEN_BATCH_SIZE,
            "image_size":    settings.IMAGE_GEN_SIZE,
        },
        upscaling={
            "backend":       settings.UPSCALER_BACKEND,
            "target_width":  settings.UPSCALE_TARGET_WIDTH,
            "target_height": settings.UPSCALE_TARGET_HEIGHT,
        },
        notion={
            "configured":    bool(settings.NOTION_API_TOKEN),
            "database_id":   settings.NOTION_DATABASE_ID or "not set",
        },
        metadata={
            "provider":        settings.METADATA_AI_PROVIDER,
            "openai_ready":    bool(settings.OPENAI_API_KEY),
            "anthropic_ready": bool(settings.ANTHROPIC_API_KEY),
            "gemini_ready":    bool(settings.GEMINI_API_KEY),
            "keyword_count":   settings.METADATA_KEYWORD_COUNT,
            "target_platforms": settings.TARGET_STOCK_PLATFORMS.split(","),
        },
        storage={
            "images_path":   settings.STOCK_IMAGES_LOCAL_PATH,
            "metadata_path": settings.METADATA_FILES_PATH,
        },
    )
