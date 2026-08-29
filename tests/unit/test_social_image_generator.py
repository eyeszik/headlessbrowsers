"""
Unit tests for social_image_generator.py.

The OpenAI DALL-E call and the HTTP download are mocked so these tests run
with no API key and no network access. Only the pure logic (prompt building,
resizing, confidence scoring, retry handling) is exercised directly.
"""
import io
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")

from backend.app.models.models import PlatformType
from backend.app.services.ai.social_image_generator import (
    SocialImageGenerator,
    SocialImageGenerationError,
    PLATFORM_IMAGE_SPECS,
)


def _fake_png_bytes(w=1792, h=1024) -> bytes:
    img = Image.new("RGB", (w, h), color=(120, 140, 160))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestPromptConstruction:
    def test_prompt_includes_platform_modifier(self):
        gen = SocialImageGenerator()
        spec = PLATFORM_IMAGE_SPECS[PlatformType.LINKEDIN]
        prompt = gen._build_prompt("a business meeting", spec)
        assert "a business meeting" in prompt
        assert spec["prompt_modifier"] in prompt

    def test_all_platforms_have_specs(self):
        for platform in PlatformType:
            assert platform in PLATFORM_IMAGE_SPECS
            spec = PLATFORM_IMAGE_SPECS[platform]
            assert spec["target_width"] > 0
            assert spec["target_height"] > 0
            assert spec["dalle_size"] in {"1024x1024", "1792x1024", "1024x1792"}


class TestResize:
    def test_resize_to_exact_target_dimensions(self):
        gen = SocialImageGenerator()
        source = _fake_png_bytes(1792, 1024)
        resized_bytes, w, h = gen._resize_to_target(source, 1200, 630)
        assert w == 1200
        assert h == 630

        img = Image.open(io.BytesIO(resized_bytes))
        assert img.size == (1200, 630)

    def test_resize_square_target(self):
        gen = SocialImageGenerator()
        source = _fake_png_bytes(1024, 1024)
        resized_bytes, w, h = gen._resize_to_target(source, 1080, 1080)
        assert (w, h) == (1080, 1080)


class TestConfidenceScoring:
    def test_short_prompt_scores_lower_clarity(self):
        gen = SocialImageGenerator()
        confidence, breakdown = gen._score_confidence(
            prompt="cat",
            enhanced_prompt="cat, photorealistic",
            revised_prompt="a cat sitting photorealistically",
            retry_count=0,
        )
        assert breakdown["prompt_clarity"] < 1.0

    def test_ideal_length_prompt_scores_high_clarity(self):
        gen = SocialImageGenerator()
        prompt = "A modern minimalist office workspace with natural light and plants"
        confidence, breakdown = gen._score_confidence(
            prompt=prompt,
            enhanced_prompt=prompt + ", professional",
            revised_prompt=prompt + ", professional stock photo",
            retry_count=0,
        )
        assert breakdown["prompt_clarity"] == 1.0

    def test_retries_reduce_reliability_score(self):
        gen = SocialImageGenerator()
        _, breakdown_no_retry = gen._score_confidence(
            prompt="a" * 50, enhanced_prompt="x", revised_prompt="x", retry_count=0
        )
        _, breakdown_with_retry = gen._score_confidence(
            prompt="a" * 50, enhanced_prompt="x", revised_prompt="x", retry_count=2
        )
        assert breakdown_with_retry["reliability"] < breakdown_no_retry["reliability"]

    def test_confidence_always_in_valid_range(self):
        gen = SocialImageGenerator()
        for retry_count in [0, 1, 2, 5, 10]:
            confidence, _ = gen._score_confidence(
                prompt="x", enhanced_prompt="x", revised_prompt="completely different text",
                retry_count=retry_count,
            )
            assert 0.0 <= confidence <= 1.0

    def test_token_overlap_identical_strings(self):
        assert SocialImageGenerator._token_overlap("hello world", "hello world") == 1.0

    def test_token_overlap_disjoint_strings(self):
        overlap = SocialImageGenerator._token_overlap("cat dog", "car boat")
        assert overlap == 0.0

    def test_token_overlap_empty_string_returns_neutral(self):
        assert SocialImageGenerator._token_overlap("", "something") == 0.5


class TestGenerateEndToEndMocked:
    @pytest.mark.asyncio
    async def test_generate_success(self):
        gen = SocialImageGenerator()
        fake_bytes = _fake_png_bytes(1792, 1024)

        mock_response = MagicMock()
        mock_response.data = [MagicMock(revised_prompt="a revised prompt", url="http://fake/image.png")]

        with patch.object(gen, "_call_dalle_with_retry", new=AsyncMock(
            return_value=(fake_bytes, "a revised prompt describing an office", 0)
        )):
            result = await gen.generate(
                prompt="A modern minimalist office workspace with natural light",
                platform=PlatformType.LINKEDIN,
                use_case="draft",
            )

        assert result.platform == PlatformType.LINKEDIN
        assert result.width == PLATFORM_IMAGE_SPECS[PlatformType.LINKEDIN]["target_width"]
        assert result.height == PLATFORM_IMAGE_SPECS[PlatformType.LINKEDIN]["target_height"]
        assert len(result.content_hash_sha256) == 64
        assert 0.0 <= result.confidence_score <= 1.0
        assert result.retry_count == 0

    @pytest.mark.asyncio
    async def test_generate_rejects_invalid_platform(self):
        gen = SocialImageGenerator()
        with pytest.raises(ValueError):
            await gen.generate(prompt="a valid prompt here", platform="not_a_platform")  # type: ignore

    @pytest.mark.asyncio
    async def test_generate_rejects_too_short_prompt(self):
        gen = SocialImageGenerator()
        with pytest.raises(ValueError):
            await gen.generate(prompt="hi", platform=PlatformType.TWITTER)

    @pytest.mark.asyncio
    async def test_generate_raises_on_published_low_confidence(self):
        gen = SocialImageGenerator()
        fake_bytes = _fake_png_bytes(1024, 1024)

        with patch.object(gen, "_call_dalle_with_retry", new=AsyncMock(
            return_value=(fake_bytes, "totally unrelated revised text here", 2)
        )):
            with pytest.raises(SocialImageGenerationError):
                await gen.generate(
                    prompt="a short cat photo",
                    platform=PlatformType.INSTAGRAM,
                    confidence_threshold=0.99,
                    use_case="published",
                )

    @pytest.mark.asyncio
    async def test_generate_flags_review_but_succeeds_for_draft(self):
        gen = SocialImageGenerator()
        fake_bytes = _fake_png_bytes(1024, 1024)

        with patch.object(gen, "_call_dalle_with_retry", new=AsyncMock(
            return_value=(fake_bytes, "totally unrelated revised text here", 2)
        )):
            result = await gen.generate(
                prompt="a reasonably long prompt about a cat",
                platform=PlatformType.INSTAGRAM,
                confidence_threshold=0.99,
                use_case="draft",
            )
            assert result.requires_review is True

    @pytest.mark.asyncio
    async def test_generate_raises_on_empty_download(self):
        gen = SocialImageGenerator()
        with patch.object(gen, "_call_dalle_with_retry", new=AsyncMock(
            return_value=(b"", "revised", 0)
        )):
            with pytest.raises(SocialImageGenerationError):
                await gen.generate(
                    prompt="a reasonably long prompt about a cat",
                    platform=PlatformType.TWITTER,
                )
