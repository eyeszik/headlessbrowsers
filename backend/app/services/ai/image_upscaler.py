"""
Image upscaling service.

Backends (tried in order):
  1. realesrgan  — GPU-accelerated Real-ESRGAN 4x (best quality; requires NVIDIA GPU + realesrgan package)
  2. pillow      — CPU bicubic/Lanczos upscaling (always available, lower quality)

The active backend is selected by UPSCALER_BACKEND env var (default: pillow).
Falling back to Pillow automatically when Real-ESRGAN is unavailable.

Output is always saved as a high-quality JPEG (95) with sRGB colour profile
and 300 DPI metadata — meeting the minimum requirements of Shutterstock,
Adobe Stock, Getty Images, and iStock.
"""
from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Real-ESRGAN is optional
try:
    from realesrgan import RealESRGANer  # type: ignore
    from basicsr.archs.rrdbnet_arch import RRDBNet  # type: ignore
    REALESRGAN_AVAILABLE = True
except ImportError:
    REALESRGAN_AVAILABLE = False
    logger.info("realesrgan not installed — Pillow fallback active. "
                "Install with: pip install realesrgan basicsr")

from PIL import Image


@dataclass
class UpscaledImage:
    """Result of a single upscale operation."""

    source_image_id: str
    original_width: int
    original_height: int
    upscaled_width: int
    upscaled_height: int
    backend_used: str
    image_bytes: bytes
    local_path: str = ""
    dpi: Tuple[int, int] = (300, 300)


class ImageUpscaler:
    """
    Upscales AI-generated images to stock-platform-ready dimensions.

    Target:
      - Minimum 4 MP (Shutterstock), preferred 6000×4000 (24 MP)
      - JPEG, sRGB, 300 DPI, quality 95

    Usage:
        upscaler = ImageUpscaler()
        result = await upscaler.upscale(image_bytes, image_id="abc123")
    """

    def __init__(self):
        from backend.app.core.config import settings
        self._backend = settings.UPSCALER_BACKEND
        self._target_w = settings.UPSCALE_TARGET_WIDTH
        self._target_h = settings.UPSCALE_TARGET_HEIGHT
        self._realesrgan: Optional[object] = None

        if self._backend == "realesrgan":
            if REALESRGAN_AVAILABLE:
                self._realesrgan = self._init_realesrgan()
            else:
                logger.warning(
                    "UPSCALER_BACKEND=realesrgan but package not installed — "
                    "falling back to Pillow"
                )
                self._backend = "pillow"

    # ── Public API ────────────────────────────────────────────────────────────

    async def upscale(
        self,
        image_bytes: bytes,
        image_id: str,
        output_dir: Optional[Path] = None,
        filename: Optional[str] = None,
    ) -> UpscaledImage:
        """
        Upscale image bytes to target dimensions.

        Args:
            image_bytes: Raw JPEG/PNG input bytes.
            image_id: ID used for logging and output filename.
            output_dir: Save result here if provided.
            filename: Override output filename (default: {image_id}_upscaled.jpg).

        Returns:
            UpscaledImage with all metadata.
        """
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        orig_w, orig_h = img.size

        if self._backend == "realesrgan" and self._realesrgan:
            upscaled_img = self._upscale_realesrgan(img)
            backend_used = "realesrgan"
        else:
            upscaled_img = self._upscale_pillow(img)
            backend_used = "pillow"

        # Ensure we hit target dimensions exactly (crop/pad if needed)
        upscaled_img = self._fit_to_target(upscaled_img)
        out_w, out_h = upscaled_img.size

        # Encode as high-quality JPEG with 300 DPI
        buf = io.BytesIO()
        upscaled_img.save(
            buf,
            format="JPEG",
            quality=95,
            optimize=True,
            dpi=(300, 300),
            icc_profile=self._srgb_profile(),
        )
        out_bytes = buf.getvalue()

        result = UpscaledImage(
            source_image_id=image_id,
            original_width=orig_w,
            original_height=orig_h,
            upscaled_width=out_w,
            upscaled_height=out_h,
            backend_used=backend_used,
            image_bytes=out_bytes,
        )

        if output_dir:
            fname = filename or f"{image_id}_upscaled.jpg"
            dest = Path(output_dir) / fname
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(out_bytes)
            result.local_path = str(dest)
            logger.info(
                f"Upscaled {image_id}: {orig_w}x{orig_h} → {out_w}x{out_h} "
                f"({backend_used}) → {dest}"
            )

        return result

    async def upscale_batch(
        self,
        items: list,  # List of (image_bytes, image_id) tuples
        output_dir: Optional[Path] = None,
    ) -> list:
        """Upscale a list of (image_bytes, image_id) pairs sequentially."""
        import asyncio
        results = []
        for image_bytes, image_id in items:
            try:
                result = await self.upscale(image_bytes, image_id, output_dir)
                results.append(result)
            except Exception as exc:
                logger.error(f"Upscale failed for {image_id}: {exc}")
                results.append(None)
        return results

    # ── Backend implementations ───────────────────────────────────────────────

    def _upscale_realesrgan(self, img: Image.Image) -> Image.Image:
        """Use Real-ESRGAN 4x model to upscale."""
        import numpy as np
        img_array = np.array(img)
        output_array, _ = self._realesrgan.enhance(img_array, outscale=4)  # type: ignore
        return Image.fromarray(output_array)

    def _upscale_pillow(self, img: Image.Image) -> Image.Image:
        """
        High-quality Pillow Lanczos upscale.

        Strategy: scale to the larger of (target_w × target_h) via Lanczos,
        then crop/pad to exact target dimensions.
        """
        orig_w, orig_h = img.size
        scale = max(
            self._target_w / orig_w,
            self._target_h / orig_h,
        )
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        return img.resize((new_w, new_h), Image.LANCZOS)

    def _fit_to_target(self, img: Image.Image) -> Image.Image:
        """
        Crop/pad image to exact target dimensions (centre crop).
        Stock platforms accept images larger than minimum — we keep the
        upscaled size as-is if it's ≥ target; otherwise pad.
        """
        w, h = img.size
        tw, th = self._target_w, self._target_h

        # Already at or larger than target — centre crop
        if w >= tw and h >= th:
            left = (w - tw) // 2
            top = (h - th) // 2
            return img.crop((left, top, left + tw, top + th))

        # Smaller than target — return as-is (avoid stretching artefacts)
        logger.warning(
            f"Upscaled image ({w}x{h}) is smaller than target ({tw}x{th}). "
            "Returning without padding — check upscaler configuration."
        )
        return img

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _init_realesrgan(self) -> object:
        """Initialise RealESRGAN model (4x)."""
        model = RRDBNet(  # type: ignore
            num_in_ch=3, num_out_ch=3, num_feat=64,
            num_block=23, num_grow_ch=32, scale=4,
        )
        model_path = os.path.join(
            os.path.dirname(__file__),
            "weights", "RealESRGAN_x4plus.pth"
        )
        upsampler = RealESRGANer(  # type: ignore
            scale=4,
            model_path=model_path,
            model=model,
            tile=512,
            tile_pad=10,
            pre_pad=0,
            half=False,
        )
        logger.info("Real-ESRGAN 4x model loaded")
        return upsampler

    @staticmethod
    def _srgb_profile() -> Optional[bytes]:
        """
        Return minimal sRGB ICC profile bytes for embedding in JPEG.
        Falls back gracefully if not available.
        """
        try:
            import PIL.ImageCms as cms
            srgb = cms.createProfile("sRGB")
            buf = io.BytesIO()
            cms.ImageCmsProfile(srgb).tobytes()
            return cms.ImageCmsProfile(srgb).tobytes()
        except Exception:
            return None
