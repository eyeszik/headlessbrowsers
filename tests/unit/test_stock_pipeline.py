"""
Unit tests for the stock image preparation pipeline.

Runs entirely without external API keys by using:
  - provider="mock" for image generation
  - Pillow upscaler (always available)
  - Heuristic metadata generation (no AI key required)
  - Notion upload skipped (NOTION_API_TOKEN not set)

Run with:
    pytest tests/unit/test_stock_pipeline.py -v
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import os
import sys
import types
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

# ── Path setup ─────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Ensure a minimal .env is loaded so config doesn't raise
os.environ.setdefault("UPSCALER_BACKEND", "pillow")
os.environ.setdefault("UPSCALE_TARGET_WIDTH", "200")   # small for tests
os.environ.setdefault("UPSCALE_TARGET_HEIGHT", "200")
os.environ.setdefault("IMAGE_GEN_PROVIDER", "mock")
os.environ.setdefault("STOCK_IMAGES_LOCAL_PATH", "/tmp/test_stock_images")
os.environ.setdefault("METADATA_FILES_PATH", "/tmp/test_metadata")
os.environ.setdefault("TARGET_STOCK_PLATFORMS", "shutterstock,adobe_stock")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_jpeg_bytes(width: int = 100, height: int = 100) -> bytes:
    """Create a minimal valid JPEG for testing."""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# ImageGenerator tests
# ─────────────────────────────────────────────────────────────────────────────

class TestImageGenerator:
    def test_mock_generate_single(self):
        from backend.app.services.ai.image_generator import ImageGenerator
        gen = ImageGenerator()
        result = gen._generate_mock("test prompt", "batch-001")
        assert result.image_bytes
        assert result.width == 100
        assert result.height == 100
        assert result.provider == "mock"
        assert len(result.sha256_hash) == 64

    def test_prompts_are_varied(self):
        from backend.app.services.ai.image_generator import ImageGenerator
        gen = ImageGenerator()
        prompts = gen._build_prompts("office", "photorealistic", 10, "")
        # All prompts should contain the theme
        assert all("office" in p for p in prompts)
        # Prompts should be unique (different compositions)
        assert len(set(prompts)) == len(prompts)

    def test_deduplicate_removes_exact_duplicates(self):
        from backend.app.services.ai.image_generator import ImageGenerator, GeneratedImage
        dup_bytes = b"same content"
        dup_hash = hashlib.sha256(dup_bytes).hexdigest()
        images = [
            GeneratedImage("id1", "p1", "mock", dup_bytes, 10, 10, dup_hash),
            GeneratedImage("id2", "p2", "mock", dup_bytes, 10, 10, dup_hash),
            GeneratedImage("id3", "p3", "mock", b"different", 10, 10,
                           hashlib.sha256(b"different").hexdigest()),
        ]
        unique = ImageGenerator.deduplicate(images)
        assert len(unique) == 2

    @pytest.mark.asyncio
    async def test_generate_batch_mock(self, tmp_path):
        from backend.app.services.ai.image_generator import ImageGenerator
        gen = ImageGenerator()
        batch = await gen.generate_batch(
            theme="forest landscape",
            style="photorealistic",
            count=3,
            output_dir=tmp_path,
            provider="mock",
        )
        assert batch.success_count == 3
        assert batch.failure_count == 0
        assert len(batch.images) == 3
        # Files should be written to disk
        saved = list(tmp_path.rglob("*.jpg"))
        assert len(saved) == 3


# ─────────────────────────────────────────────────────────────────────────────
# ImageUpscaler tests
# ─────────────────────────────────────────────────────────────────────────────

class TestImageUpscaler:
    @pytest.mark.asyncio
    async def test_upscale_pillow(self, tmp_path):
        from backend.app.services.ai.image_upscaler import ImageUpscaler
        upscaler = ImageUpscaler()
        assert upscaler._backend == "pillow"

        jpeg = _make_jpeg_bytes(100, 100)
        result = await upscaler.upscale(jpeg, "test-img", output_dir=tmp_path)

        assert result.source_image_id == "test-img"
        assert result.original_width == 100
        assert result.original_height == 100
        assert result.upscaled_width == 200   # matches env override
        assert result.upscaled_height == 200
        assert result.backend_used == "pillow"
        assert result.image_bytes  # non-empty output
        assert Path(result.local_path).exists()

    @pytest.mark.asyncio
    async def test_upscale_batch(self, tmp_path):
        from backend.app.services.ai.image_upscaler import ImageUpscaler
        upscaler = ImageUpscaler()
        items = [(_make_jpeg_bytes(), f"img-{i}") for i in range(3)]
        results = await upscaler.upscale_batch(items, output_dir=tmp_path)
        assert len(results) == 3
        assert all(r is not None for r in results)

    @pytest.mark.asyncio
    async def test_upscale_invalid_bytes_returns_none(self, tmp_path):
        from backend.app.services.ai.image_upscaler import ImageUpscaler
        upscaler = ImageUpscaler()
        results = await upscaler.upscale_batch(
            [(b"not an image", "bad-img")], output_dir=tmp_path
        )
        assert results[0] is None


# ─────────────────────────────────────────────────────────────────────────────
# MetadataOptimizer tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMetadataOptimizer:
    @pytest.mark.asyncio
    async def test_heuristic_fallback(self):
        """Should work without any API keys."""
        from backend.app.services.ai.metadata_optimizer import MetadataOptimizer
        optimizer = MetadataOptimizer()
        meta = await optimizer.generate(
            image_id="test-001",
            generation_prompt="diverse team in modern glass office",
            theme="business",
            style="photorealistic",
        )
        assert meta.image_id == "test-001"
        assert len(meta.title) > 0
        assert len(meta.description) > 0
        assert len(meta.keywords) >= 5
        assert meta.confidence_score >= 0.0

    @pytest.mark.asyncio
    async def test_metadata_platform_validation(self):
        from backend.app.services.ai.metadata_optimizer import MetadataOptimizer, ImageMetadata
        meta = ImageMetadata(
            image_id="test",
            title="A" * 70,             # exactly at Shutterstock limit
            description="B" * 200,
            keywords=["k"] * 40,
            category="Business",
            style="Photorealistic",
            color_palette=["Warm"],
            confidence_score=0.8,
            generation_prompt="test",
        )
        assert meta.validate_for_platform("shutterstock") is True
        # Exceed title limit
        meta.title = "A" * 71
        assert meta.validate_for_platform("shutterstock") is False

    @pytest.mark.asyncio
    async def test_batch_metadata_generation(self):
        from backend.app.services.ai.metadata_optimizer import MetadataOptimizer
        optimizer = MetadataOptimizer()
        items = [
            {"image_id": f"img-{i}", "generation_prompt": f"prompt {i}",
             "theme": "nature", "style": "photorealistic"}
            for i in range(3)
        ]
        results = await optimizer.generate_batch(items)
        assert len(results) == 3
        assert all(r.image_id == f"img-{i}" for i, r in enumerate(results))

    def test_metadata_to_txt(self):
        from backend.app.services.ai.metadata_optimizer import ImageMetadata
        meta = ImageMetadata(
            image_id="test",
            title="Test Title",
            description="Test description.",
            keywords=["keyword1", "keyword2"],
            category="Business",
            style="Photorealistic",
            color_palette=["Warm"],
            confidence_score=0.85,
            generation_prompt="original prompt",
            platform_validation={"shutterstock": True, "adobe_stock": True},
        )
        txt = meta.to_txt(
            resolution="6000x4000",
            file_size_mb=9.5,
            provider="openai",
            batch_id="batch-abc123",
        )
        assert "TITLE:" in txt
        assert "Test Title" in txt
        assert "DESCRIPTION:" in txt
        assert "KEYWORDS:" in txt
        assert "keyword1" in txt
        assert "6000x4000" in txt
        assert "300 DPI" in txt
        assert "openai" in txt
        assert "batch-abc123" in txt


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline integration test (mock provider, no external APIs)
# ─────────────────────────────────────────────────────────────────────────────

class TestStockImagePipeline:
    @pytest.mark.asyncio
    async def test_full_pipeline_mock(self, tmp_path):
        """
        Run the complete pipeline with mock provider.
        No API keys required; Notion upload skipped.
        """
        # Patch storage paths to tmp_path
        with patch.dict(os.environ, {
            "STOCK_IMAGES_LOCAL_PATH": str(tmp_path / "images"),
            "METADATA_FILES_PATH":     str(tmp_path / "metadata"),
            "UPSCALE_TARGET_WIDTH":    "200",
            "UPSCALE_TARGET_HEIGHT":   "200",
        }):
            # Reload settings with patched env
            import importlib
            import backend.app.core.config as cfg
            importlib.reload(cfg)

            from backend.app.workflows.stock_prep_pipeline import run_pipeline
            run = await run_pipeline(
                theme="sunset beach",
                style="photorealistic",
                count=2,
                provider="mock",
                save_report=False,
            )

        assert run.requested_count == 2
        assert run.success_count == 2
        assert run.failure_count == 0

        for result in run.results:
            assert result.success
            assert result.stage_reached == "metadata"
            assert Path(result.local_image_path).exists()
            assert Path(result.local_metadata_path).exists()
            assert result.title
            assert result.keywords

    @pytest.mark.asyncio
    async def test_pipeline_saves_report(self, tmp_path):
        from backend.app.workflows.stock_prep_pipeline import StockImagePipeline, PipelineRun
        pipeline = StockImagePipeline()

        # Construct a minimal PipelineRun object
        run = PipelineRun(
            run_id="test-run-id",
            batch_id="test-batch",
            theme="test",
            style="photorealistic",
            requested_count=1,
            results=[],
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            success_count=0,
            failure_count=0,
        )
        report_path = pipeline.save_report(run, output_path=tmp_path / "report.json")
        assert Path(report_path).exists()

        import json
        data = json.loads(Path(report_path).read_text())
        assert "summary" in data
        assert data["summary"]["run_id"] == "test-run-id"


# ─────────────────────────────────────────────────────────────────────────────
# NotionIntegration tests (mocked client)
# ─────────────────────────────────────────────────────────────────────────────

class TestNotionIntegration:
    def test_raises_without_package(self):
        """Should raise RuntimeError when notion-client is not installed."""
        import backend.app.services.integrations.notion as notion_mod
        original = notion_mod.NOTION_AVAILABLE
        try:
            notion_mod.NOTION_AVAILABLE = False
            with pytest.raises(RuntimeError, match="notion-client is required"):
                notion_mod.NotionIntegration(api_token="test")
        finally:
            notion_mod.NOTION_AVAILABLE = original

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """health_check returns 'healthy' when API responds normally."""
        import backend.app.services.integrations.notion as notion_mod
        if not notion_mod.NOTION_AVAILABLE:
            pytest.skip("notion-client not installed")

        notion = notion_mod.NotionIntegration(api_token="fake-token")
        mock_client = AsyncMock()
        mock_client.users.me.return_value = {"name": "Test User"}
        notion.client = mock_client

        result = await notion.health_check()
        assert result["status"] == "healthy"
        assert result["user"] == "Test User"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_on_exception(self):
        import backend.app.services.integrations.notion as notion_mod
        if not notion_mod.NOTION_AVAILABLE:
            pytest.skip("notion-client not installed")

        notion = notion_mod.NotionIntegration(api_token="fake-token")
        mock_client = AsyncMock()
        mock_client.users.me.side_effect = Exception("401 Unauthorized")
        notion.client = mock_client

        result = await notion.health_check()
        assert result["status"] == "unhealthy"
        assert "401" in result["error"]
