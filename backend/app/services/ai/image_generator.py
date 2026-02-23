"""
AI image generation service.

Providers supported:
  - openai     : DALL-E 3 via openai SDK (requires OPENAI_API_KEY)
  - stability  : Stable Diffusion via Stability AI REST API (requires STABILITY_AI_API_KEY)
  - mock       : Returns placeholder bytes — useful for testing without API keys

Each provider returns a GeneratedImage dataclass.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class GeneratedImage:
    """Result of a single image generation request."""

    image_id: str
    prompt: str
    provider: str
    image_bytes: bytes
    width: int
    height: int
    sha256_hash: str
    generated_at: datetime = field(default_factory=datetime.utcnow)
    revised_prompt: str = ""   # DALL-E 3 may return a revised prompt
    local_path: str = ""       # Set after saving to disk


@dataclass
class GenerationBatch:
    """Result of a batch generation run."""

    batch_id: str
    images: List[GeneratedImage]
    provider: str
    theme: str
    style: str
    started_at: datetime
    completed_at: datetime
    success_count: int
    failure_count: int


class ImageGenerator:
    """
    Multi-provider AI image generator.

    Usage:
        generator = ImageGenerator()
        batch = await generator.generate_batch(
            theme="modern office collaboration",
            style="photorealistic",
            count=5,
            output_dir=Path("./data/stock_images"),
        )
    """

    # DALL-E 3 supported sizes
    _DALLE_SIZES = {"1024x1024", "1792x1024", "1024x1792"}
    _DALLE_QUALITY = "hd"       # "standard" or "hd"
    _DALLE_STYLE = "natural"    # "vivid" or "natural"

    # Stability AI v1 REST endpoint
    _STABILITY_URL = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"

    def __init__(self):
        from backend.app.core.config import settings
        self._settings = settings
        self._provider = settings.IMAGE_GEN_PROVIDER
        self._openai_key = settings.OPENAI_API_KEY
        self._stability_key = settings.STABILITY_AI_API_KEY

    # ── Public API ────────────────────────────────────────────────────────────

    async def generate_batch(
        self,
        theme: str,
        style: str = "photorealistic",
        count: int = 10,
        output_dir: Optional[Path] = None,
        provider: Optional[str] = None,
        additional_context: str = "",
    ) -> GenerationBatch:
        """
        Generate a batch of images for a given theme.

        Args:
            theme: Subject/topic for the images (e.g. "modern office").
            style: Visual style (photorealistic, artistic, 3d render, illustration).
            count: Number of images to generate.
            output_dir: Save images here; skip saving if None.
            provider: Override the configured provider for this batch.
            additional_context: Extra descriptive text appended to prompts.

        Returns:
            GenerationBatch with all results.
        """
        provider = provider or self._provider
        batch_id = str(uuid.uuid4())
        started_at = datetime.utcnow()

        prompts = self._build_prompts(theme, style, count, additional_context)

        logger.info(
            f"Starting batch {batch_id}: {count} images, "
            f"theme='{theme}', style='{style}', provider={provider}"
        )

        tasks = [
            self._generate_single(prompt, provider, batch_id)
            for prompt in prompts
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        images: List[GeneratedImage] = []
        failures = 0
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Image generation failed: {result}")
                failures += 1
            else:
                images.append(result)

        # Save to disk if output_dir provided
        if output_dir:
            output_dir = Path(output_dir)
            batch_dir = output_dir / batch_id
            batch_dir.mkdir(parents=True, exist_ok=True)
            for img in images:
                await self._save_image(img, batch_dir)

        completed_at = datetime.utcnow()
        logger.info(
            f"Batch {batch_id} complete: {len(images)} ok, {failures} failed"
        )

        return GenerationBatch(
            batch_id=batch_id,
            images=images,
            provider=provider,
            theme=theme,
            style=style,
            started_at=started_at,
            completed_at=completed_at,
            success_count=len(images),
            failure_count=failures,
        )

    # ── Prompt construction ───────────────────────────────────────────────────

    def _build_prompts(
        self,
        theme: str,
        style: str,
        count: int,
        additional_context: str,
    ) -> List[str]:
        """
        Build varied prompts from a theme to ensure visual diversity.
        Includes composition hints so images are not repetitive.
        """
        style_descriptors = {
            "photorealistic": (
                "ultra-realistic, DSLR photography, natural lighting, "
                "sharp focus, high detail, commercial photography quality"
            ),
            "artistic": (
                "fine art style, painterly, expressive brushwork, "
                "gallery quality, aesthetic composition"
            ),
            "3d render": (
                "3D CGI render, physically based rendering, studio lighting, "
                "8K resolution, product visualization quality"
            ),
            "illustration": (
                "professional digital illustration, clean vector aesthetic, "
                "editorial illustration style"
            ),
        }
        style_desc = style_descriptors.get(style.lower(), style)

        # Composition and angle variations to diversify output
        compositions = [
            "wide establishing shot",
            "close-up detail shot",
            "medium shot, eye level",
            "aerial perspective",
            "low angle, dynamic perspective",
            "symmetrical composition",
            "rule of thirds, off-center subject",
            "negative space, minimalist",
            "busy scene, environmental context",
            "shallow depth of field, bokeh background",
        ]

        prompts: List[str] = []
        for i in range(count):
            comp = compositions[i % len(compositions)]
            base = (
                f"{theme}, {comp}, {style_desc}"
                f"{', ' + additional_context if additional_context else ''}"
                ", commercial stock photography, no watermarks, no text overlays"
            )
            prompts.append(base)

        return prompts

    # ── Provider dispatch ─────────────────────────────────────────────────────

    async def _generate_single(
        self,
        prompt: str,
        provider: str,
        batch_id: str,
    ) -> GeneratedImage:
        if provider == "openai":
            return await self._generate_dalle(prompt, batch_id)
        elif provider == "stability":
            return await self._generate_stability(prompt, batch_id)
        elif provider == "mock":
            return self._generate_mock(prompt, batch_id)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    # ── DALL-E 3 ──────────────────────────────────────────────────────────────

    async def _generate_dalle(self, prompt: str, batch_id: str) -> GeneratedImage:
        """Generate one image using OpenAI DALL-E 3."""
        if not self._openai_key:
            raise RuntimeError("OPENAI_API_KEY not configured")

        import openai
        client = openai.AsyncOpenAI(api_key=self._openai_key)

        size = self._settings.IMAGE_GEN_SIZE
        if size not in self._DALLE_SIZES:
            size = "1024x1024"

        response = await client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,         # type: ignore[arg-type]
            quality=self._DALLE_QUALITY,
            style=self._DALLE_STYLE,
            response_format="b64_json",
            n=1,
        )

        import base64
        b64 = response.data[0].b64_json
        image_bytes = base64.b64decode(b64)
        revised_prompt = response.data[0].revised_prompt or prompt

        w, h = map(int, size.split("x"))
        sha = hashlib.sha256(image_bytes).hexdigest()

        return GeneratedImage(
            image_id=str(uuid.uuid4()),
            prompt=prompt,
            provider="openai",
            image_bytes=image_bytes,
            width=w,
            height=h,
            sha256_hash=sha,
            revised_prompt=revised_prompt,
        )

    # ── Stability AI ──────────────────────────────────────────────────────────

    async def _generate_stability(self, prompt: str, batch_id: str) -> GeneratedImage:
        """Generate one image using Stability AI SDXL REST API."""
        if not self._stability_key:
            raise RuntimeError("STABILITY_AI_API_KEY not configured")

        payload = {
            "text_prompts": [
                {"text": prompt, "weight": 1.0},
                {"text": "watermark, text, logo, blurry, low quality, nsfw", "weight": -1.0},
            ],
            "cfg_scale": 7,
            "height": 1024,
            "width": 1024,
            "samples": 1,
            "steps": 40,
        }
        headers = {
            "Authorization": f"Bearer {self._stability_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._STABILITY_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(
                        f"Stability AI returned {resp.status}: {text[:200]}"
                    )
                data = await resp.json()

        import base64
        b64 = data["artifacts"][0]["base64"]
        image_bytes = base64.b64decode(b64)
        sha = hashlib.sha256(image_bytes).hexdigest()

        return GeneratedImage(
            image_id=str(uuid.uuid4()),
            prompt=prompt,
            provider="stability",
            image_bytes=image_bytes,
            width=1024,
            height=1024,
            sha256_hash=sha,
        )

    # ── Mock provider (testing) ───────────────────────────────────────────────

    def _generate_mock(self, prompt: str, batch_id: str) -> GeneratedImage:
        """
        Return a synthetic 100x100 JPEG placeholder.
        Useful for running the full pipeline without API keys.
        """
        from PIL import Image, ImageDraw, ImageFont
        import io as _io

        img = Image.new("RGB", (100, 100), color=(70, 130, 180))
        draw = ImageDraw.Draw(img)
        draw.text((10, 40), "MOCK", fill=(255, 255, 255))

        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        image_bytes = buf.getvalue()
        sha = hashlib.sha256(image_bytes).hexdigest()

        return GeneratedImage(
            image_id=str(uuid.uuid4()),
            prompt=prompt,
            provider="mock",
            image_bytes=image_bytes,
            width=100,
            height=100,
            sha256_hash=sha,
        )

    # ── Disk I/O ──────────────────────────────────────────────────────────────

    async def _save_image(self, img: GeneratedImage, directory: Path) -> None:
        """Save image bytes to disk as JPEG."""
        filename = f"{img.image_id}.jpg"
        dest = directory / filename
        dest.write_bytes(img.image_bytes)
        img.local_path = str(dest)
        logger.debug(f"Saved image to {dest}")

    # ── Deduplication ─────────────────────────────────────────────────────────

    @staticmethod
    def deduplicate(images: List[GeneratedImage]) -> List[GeneratedImage]:
        """Remove exact-duplicate images by SHA-256 hash."""
        seen: set = set()
        unique: List[GeneratedImage] = []
        for img in images:
            if img.sha256_hash not in seen:
                seen.add(img.sha256_hash)
                unique.append(img)
            else:
                logger.debug(f"Duplicate image removed: {img.image_id}")
        return unique
