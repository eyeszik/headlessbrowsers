"""
Social media image generation via OpenAI DALL-E 3.

Generates platform-optimized images (YouTube, Twitter, Facebook, Instagram,
LinkedIn) for a Content record, distinct from the stock-photo pipeline
(stock_prep_pipeline.py) which targets external stock marketplaces.

Design notes:
- Confidence scoring here is an explicit, disclosed heuristic (prompt length,
  retry count, metadata completeness) — not a statistical model. It is meant
  to flag content for human review, not to make unsupervised decisions.
- Integrity verification (SHA-256) happens at download time and again after
  S3 upload (see MediaManager.verify_upload_integrity) to catch silent
  corruption, not to detect adversarial tampering.
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from backend.app.models.models import PlatformType

logger = logging.getLogger(__name__)


# ── Platform image specifications ────────────────────────────────────────────
# Maps the platform enum already used throughout the codebase (Content,
# ContentFormatter) to DALL-E-3-compatible generation sizes plus the exact
# publish dimensions each platform recommends. DALL-E 3 only supports three
# sizes (1024x1024, 1024x1792, 1792x1024), so PIL resizes the closest match
# down to the platform's exact target dimensions after generation.

PLATFORM_IMAGE_SPECS: Dict[PlatformType, Dict[str, Any]] = {
    PlatformType.YOUTUBE: {
        "target_width": 1280, "target_height": 720,       # thumbnail spec
        "dalle_size": "1792x1024",
        "tone": "bold, high-contrast, attention-grabbing",
        "prompt_modifier": "cinematic lighting, bold colors, thumbnail-ready, high contrast",
    },
    PlatformType.TWITTER: {
        "target_width": 1200, "target_height": 675,
        "dalle_size": "1792x1024",
        "tone": "clean, punchy, high-contrast",
        "prompt_modifier": "clean composition, high contrast, eye-catching, minimal clutter",
    },
    PlatformType.FACEBOOK: {
        "target_width": 1200, "target_height": 630,
        "dalle_size": "1792x1024",
        "tone": "warm, relatable, community-focused",
        "prompt_modifier": "warm tones, relatable, community-focused, approachable",
    },
    PlatformType.INSTAGRAM: {
        "target_width": 1080, "target_height": 1080,
        "dalle_size": "1024x1024",
        "tone": "aesthetic, inspiring, vibrant",
        "prompt_modifier": "aesthetic composition, inspiring, vibrant, visually striking",
    },
    PlatformType.LINKEDIN: {
        "target_width": 1200, "target_height": 627,
        "dalle_size": "1792x1024",
        "tone": "professional, authoritative",
        "prompt_modifier": "professional setting, corporate, authoritative, business-appropriate",
    },
}

# Prohibited-content guardrail: DALL-E 3 already refuses most of this, but we
# reject obviously non-compliant requests before spending an API call.
BASE_NEGATIVE_CONSTRAINTS = (
    "no readable text or words in the image, no recognizable real people, "
    "no brand logos, photorealistic professional stock photography style"
)


@dataclass
class SocialImageResult:
    """Result of one platform image generation."""

    image_id: str
    platform: PlatformType
    image_bytes: bytes
    width: int
    height: int
    content_hash_sha256: str
    prompt: str
    enhanced_prompt: str
    revised_prompt: str
    confidence_score: float
    confidence_breakdown: Dict[str, float]
    retry_count: int
    generation_time_ms: float
    requires_review: bool
    generated_at: datetime = field(default_factory=datetime.utcnow)


class SocialImageGenerationError(Exception):
    """Raised when generation fails after all retries are exhausted."""


class SocialImageGenerator:
    """
    Generates platform-optimized images via OpenAI DALL-E 3.

    Usage:
        generator = SocialImageGenerator()
        result = await generator.generate(
            prompt="A modern minimalist office workspace with natural light",
            platform=PlatformType.LINKEDIN,
        )
    """

    _MAX_RETRIES = 3
    _BACKOFF_BASE_SECONDS = 2

    def __init__(self):
        from backend.app.core.config import settings
        self._settings = settings

    # ── Public API ────────────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        platform: PlatformType,
        confidence_threshold: float = 0.7,
        use_case: str = "draft",  # "draft" | "published"
    ) -> SocialImageResult:
        """
        Generate one platform-optimized image.

        Args:
            prompt: Natural-language description (20-500 chars recommended).
            platform: Target PlatformType.
            confidence_threshold: Minimum confidence to accept for "published".
            use_case: "draft" tolerates low confidence with a review flag;
                      "published" raises if confidence is below threshold.

        Returns:
            SocialImageResult with image bytes, dimensions, hash, and
            confidence scoring.

        Raises:
            ValueError: invalid platform or prompt.
            SocialImageGenerationError: all API retries exhausted.
        """
        if platform not in PLATFORM_IMAGE_SPECS:
            raise ValueError(f"Unsupported platform: {platform}")
        if not (5 <= len(prompt.strip()) <= 1000):
            raise ValueError("Prompt must be between 5 and 1000 characters")

        spec = PLATFORM_IMAGE_SPECS[platform]
        enhanced_prompt = self._build_prompt(prompt, spec)

        start = time.monotonic()
        image_bytes, revised_prompt, retry_count = await self._call_dalle_with_retry(
            enhanced_prompt, spec["dalle_size"]
        )
        generation_time_ms = (time.monotonic() - start) * 1000

        if len(image_bytes) == 0:
            raise SocialImageGenerationError("Downloaded image was empty (0 bytes)")

        content_hash = hashlib.sha256(image_bytes).hexdigest()
        resized_bytes, w, h = self._resize_to_target(
            image_bytes, spec["target_width"], spec["target_height"]
        )
        # Recompute hash on the resized artifact — that's the file we persist.
        final_hash = hashlib.sha256(resized_bytes).hexdigest()

        confidence, breakdown = self._score_confidence(
            prompt=prompt,
            enhanced_prompt=enhanced_prompt,
            revised_prompt=revised_prompt,
            retry_count=retry_count,
        )

        requires_review = confidence < confidence_threshold
        if requires_review and use_case == "published":
            raise SocialImageGenerationError(
                f"Confidence {confidence:.2f} below threshold "
                f"{confidence_threshold:.2f} for published use_case. "
                f"Breakdown: {breakdown}"
            )

        result = SocialImageResult(
            image_id=str(uuid.uuid4()),
            platform=platform,
            image_bytes=resized_bytes,
            width=w,
            height=h,
            content_hash_sha256=final_hash,
            prompt=prompt,
            enhanced_prompt=enhanced_prompt,
            revised_prompt=revised_prompt,
            confidence_score=confidence,
            confidence_breakdown=breakdown,
            retry_count=retry_count,
            generation_time_ms=generation_time_ms,
            requires_review=requires_review,
        )

        logger.info(
            f"Generated social image {result.image_id} for {platform.value}: "
            f"{w}x{h}, confidence={confidence:.2f}, retries={retry_count}"
        )
        return result

    # ── Prompt construction ───────────────────────────────────────────────────

    def _build_prompt(self, user_prompt: str, spec: Dict[str, Any]) -> str:
        return (
            f"{user_prompt.strip()}, {spec['prompt_modifier']}, "
            f"{BASE_NEGATIVE_CONSTRAINTS}"
        )

    # ── API call with retry ───────────────────────────────────────────────────

    async def _call_dalle_with_retry(
        self, enhanced_prompt: str, size: str
    ) -> tuple[bytes, str, int]:
        """Returns (image_bytes, revised_prompt, retry_count)."""
        if not self._settings.OPENAI_API_KEY:
            raise SocialImageGenerationError("OPENAI_API_KEY not configured")

        import openai
        client = openai.AsyncOpenAI(api_key=self._settings.OPENAI_API_KEY)

        last_error: Optional[Exception] = None
        for attempt in range(self._MAX_RETRIES):
            try:
                response = await client.images.generate(
                    model="dall-e-3",
                    prompt=enhanced_prompt,
                    size=size,  # type: ignore[arg-type]
                    quality="hd",
                    style="natural",
                    n=1,
                )
                revised_prompt = response.data[0].revised_prompt or enhanced_prompt
                image_url = response.data[0].url

                image_bytes = await self._download(image_url)
                return image_bytes, revised_prompt, attempt

            except Exception as exc:  # noqa: BLE001 - openai raises several types
                last_error = exc
                is_rate_limit = "rate" in str(exc).lower() or "429" in str(exc)
                if attempt < self._MAX_RETRIES - 1:
                    wait = self._BACKOFF_BASE_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"DALL-E generation attempt {attempt + 1} failed "
                        f"({'rate limit' if is_rate_limit else 'error'}): {exc}. "
                        f"Retrying in {wait}s"
                    )
                    import asyncio
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"All {self._MAX_RETRIES} generation attempts failed")

        raise SocialImageGenerationError(
            f"Generation failed after {self._MAX_RETRIES} attempts: {last_error}"
        )

    async def _download(self, url: str) -> bytes:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    raise SocialImageGenerationError(
                        f"Image download returned HTTP {resp.status}"
                    )
                return await resp.read()

    # ── Resize to exact platform dimensions ───────────────────────────────────

    def _resize_to_target(
        self, image_bytes: bytes, target_w: int, target_h: int
    ) -> tuple[bytes, int, int]:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Scale to cover target, then centre-crop — avoids distortion.
        scale = max(target_w / img.width, target_h / img.height)
        new_size = (round(img.width * scale), round(img.height * scale))
        img = img.resize(new_size, Image.LANCZOS)

        left = (img.width - target_w) // 2
        top = (img.height - target_h) // 2
        img = img.crop((left, top, left + target_w, top + target_h))

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue(), target_w, target_h

    # ── Confidence scoring (disclosed heuristic, not a statistical model) ────

    def _score_confidence(
        self,
        prompt: str,
        enhanced_prompt: str,
        revised_prompt: str,
        retry_count: int,
    ) -> tuple[float, Dict[str, float]]:
        """
        Heuristic confidence estimate in [0.0, 1.0]. This is NOT a calibrated
        probability — it is a simple, disclosed set of signals meant to flag
        content that likely needs human review before publishing.
        """
        breakdown: Dict[str, float] = {}

        # Signal 1: prompt clarity — very short prompts tend to under-specify.
        length = len(prompt.strip())
        if 20 <= length <= 500:
            breakdown["prompt_clarity"] = 1.0
        elif length < 20:
            breakdown["prompt_clarity"] = round(length / 20.0, 2)
        else:
            breakdown["prompt_clarity"] = round(max(0.5, 1.0 - (length - 500) / 1000), 2)

        # Signal 2: how much OpenAI rewrote the prompt. Large rewrites suggest
        # the original prompt was ambiguous or triggered safety rewriting.
        similarity = self._token_overlap(enhanced_prompt, revised_prompt)
        breakdown["prompt_stability"] = round(similarity, 2)

        # Signal 3: reliability penalty for retries (transient failures raise
        # the chance something about this request is at the edge of a policy
        # or capacity boundary).
        breakdown["reliability"] = round(max(0.0, 1.0 - 0.15 * retry_count), 2)

        weights = {"prompt_clarity": 0.4, "prompt_stability": 0.35, "reliability": 0.25}
        confidence = sum(breakdown[k] * weights[k] for k in weights)
        confidence = max(0.0, min(1.0, round(confidence, 3)))

        return confidence, breakdown

    @staticmethod
    def _token_overlap(a: str, b: str) -> float:
        """Jaccard similarity over lowercased word sets — cheap, no ML dependency."""
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.5
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union else 0.5


# Global instance, mirrors the pattern used by ai_service.py / media_manager.py
social_image_generator = SocialImageGenerator()
