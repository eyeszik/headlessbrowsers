"""
SEO metadata optimizer for stock photography.

Generates per-image:
  - Title (50–70 chars, keyword-rich, human-readable)
  - Description (200–500 chars, narrative, natural keyword integration)
  - Keywords (30–50 tags, hierarchical broad → specific → conceptual)
  - Platform-specific validation (Shutterstock, Adobe Stock, Getty, iStock)
  - Formatted metadata .txt file content

Uses OpenAI GPT-4, Anthropic Claude, or Google Gemini depending on METADATA_AI_PROVIDER.
Falls back to heuristic template generation if no API key is configured.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Platform constraints ──────────────────────────────────────────────────────
PLATFORM_CONSTRAINTS: Dict[str, Dict[str, Any]] = {
    "shutterstock": {
        "title_max":   70,
        "desc_max":    200,
        "keywords_max": 50,
        "keywords_min": 5,
    },
    "adobe_stock": {
        "title_max":   200,
        "desc_max":    1000,
        "keywords_max": 49,
        "keywords_min": 1,
    },
    "getty": {
        "title_max":   200,
        "desc_max":    2000,
        "keywords_max": 50,
        "keywords_min": 10,
    },
    "istock": {
        "title_max":   200,
        "desc_max":    1000,
        "keywords_max": 50,
        "keywords_min": 5,
    },
}


@dataclass
class ImageMetadata:
    """Complete metadata for one stock image."""

    image_id: str
    title: str
    description: str
    keywords: List[str]
    category: str
    style: str
    color_palette: List[str]
    confidence_score: float
    generation_prompt: str
    platform_validation: Dict[str, bool] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.utcnow)

    # ── Derived properties ────────────────────────────────────────────────────

    def to_txt(
        self,
        resolution: str = "6000x4000",
        file_size_mb: float = 0.0,
        provider: str = "",
        batch_id: str = "",
    ) -> str:
        """Render metadata as the .txt file that ships alongside each image."""
        platform_lines = "\n".join(
            f"{'✓' if ok else '✗'} {platform.replace('_', ' ').title()}"
            for platform, ok in self.platform_validation.items()
        )
        return (
            f"TITLE:\n{self.title}\n\n"
            f"DESCRIPTION:\n{self.description}\n\n"
            f"KEYWORDS:\n{', '.join(self.keywords)}\n\n"
            f"CATEGORY: {self.category}\n"
            f"STYLE: {self.style}\n"
            f"COLOR PALETTE: {', '.join(self.color_palette)}\n\n"
            f"TECHNICAL SPECS:\n"
            f"  Resolution : {resolution}\n"
            f"  Format     : JPEG, sRGB, 300 DPI\n"
            f"  File Size  : {file_size_mb:.1f} MB\n\n"
            f"PLATFORM READINESS:\n{platform_lines}\n\n"
            f"GENERATION DATA:\n"
            f"  Provider   : {provider or 'AI'}\n"
            f"  Prompt     : {self.generation_prompt[:200]}\n"
            f"  Batch ID   : {batch_id}\n"
            f"  Date       : {self.generated_at.isoformat()}\n"
            f"  Confidence : {self.confidence_score:.2f}\n"
        )

    def validate_for_platform(self, platform: str) -> bool:
        """True if this metadata satisfies a given platform's constraints."""
        c = PLATFORM_CONSTRAINTS.get(platform)
        if not c:
            return True
        return (
            len(self.title) <= c["title_max"]
            and len(self.description) <= c["desc_max"]
            and c["keywords_min"] <= len(self.keywords) <= c["keywords_max"]
        )


class MetadataOptimizer:
    """
    AI-powered SEO metadata generator for stock images.

    Priority:
      1. OpenAI GPT-4 (if METADATA_AI_PROVIDER=openai and key present)
      2. Anthropic Claude (if METADATA_AI_PROVIDER=anthropic and key present)
      3. Google Gemini (if METADATA_AI_PROVIDER=gemini and key present)
      4. Heuristic template fallback (no API keys needed)
    """

    _SYSTEM_PROMPT = """You are an expert stock photography SEO specialist.
Generate metadata for a stock image that maximises search discoverability on
Shutterstock, Adobe Stock, Getty Images, and iStock.

Return ONLY valid JSON with this exact schema:
{
  "title":       "<50-70 char SEO title, descriptive, no filler words>",
  "description": "<200-500 char description: subject, context, mood, commercial uses>",
  "keywords":    ["<word1>", "<word2>", ...],
  "category":    "<Business|Nature|Lifestyle|Abstract|Technology|Food|Travel|Other>",
  "style":       "<Photorealistic|Artistic|3D Render|Illustration>",
  "color_palette": ["<Warm|Cool|Vibrant|Muted|Monochrome|Dark|Bright>"],
  "confidence":  <0.0-1.0>
}

Keyword rules:
- 35-45 total keywords
- Mix: subjects (nouns), qualities (adjectives), actions (verbs), concepts (themes)
- Broad to specific: e.g. "business" → "teamwork" → "corporate brainstorming session"
- No duplicate meanings, no filler keywords
- Never include the word "stock" or "photo" as keywords
"""

    def __init__(self):
        from backend.app.core.config import settings
        self._settings = settings
        self._provider = settings.METADATA_AI_PROVIDER
        self._keyword_count = settings.METADATA_KEYWORD_COUNT
        self._desc_min = settings.METADATA_DESCRIPTION_MIN_LENGTH
        self._desc_max = settings.METADATA_DESCRIPTION_MAX_LENGTH
        self._target_platforms = [
            p.strip() for p in settings.TARGET_STOCK_PLATFORMS.split(",")
        ]

    # ── Public API ────────────────────────────────────────────────────────────

    async def generate(
        self,
        image_id: str,
        generation_prompt: str,
        theme: str = "",
        style: str = "photorealistic",
        provider: Optional[str] = None,
    ) -> ImageMetadata:
        """
        Generate complete metadata for one image.

        Args:
            image_id: Unique identifier for the image.
            generation_prompt: The original prompt used to create the image.
            theme: High-level theme/category hint.
            style: Visual style label.
            provider: Override METADATA_AI_PROVIDER for this call.

        Returns:
            ImageMetadata with all fields populated and platform validation.
        """
        provider = provider or self._provider
        context = f"Theme: {theme}. Style: {style}. " if theme else ""
        user_prompt = (
            f"{context}Image generation prompt: \"{generation_prompt}\"\n\n"
            f"Generate stock photography metadata for this image."
        )

        raw: Optional[Dict[str, Any]] = None

        if provider == "openai" and self._settings.OPENAI_API_KEY:
            raw = await self._generate_openai(user_prompt)
        elif provider == "anthropic" and self._settings.ANTHROPIC_API_KEY:
            raw = await self._generate_anthropic(user_prompt)
        elif provider == "gemini" and self._settings.GEMINI_API_KEY:
            raw = await self._generate_gemini(user_prompt)

        if raw is None:
            logger.info(f"No AI provider available — using heuristic for {image_id}")
            raw = self._heuristic_metadata(generation_prompt, theme, style)

        metadata = self._parse_response(image_id, raw, generation_prompt)
        metadata.platform_validation = {
            p: metadata.validate_for_platform(p)
            for p in self._target_platforms
        }
        return metadata

    async def generate_batch(
        self,
        items: List[Dict[str, Any]],
    ) -> List[ImageMetadata]:
        """
        Generate metadata for a list of images.

        Args:
            items: List of dicts with keys: image_id, generation_prompt, theme, style.

        Returns:
            List of ImageMetadata (one per input item).
        """
        import asyncio
        tasks = [
            self.generate(
                image_id=item["image_id"],
                generation_prompt=item["generation_prompt"],
                theme=item.get("theme", ""),
                style=item.get("style", "photorealistic"),
            )
            for item in items
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        metadata_list: List[ImageMetadata] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Metadata generation failed for item {i}: {result}")
                # Use minimal fallback metadata
                item = items[i]
                metadata_list.append(
                    self._fallback_metadata(
                        item["image_id"], item.get("generation_prompt", "")
                    )
                )
            else:
                metadata_list.append(result)   # type: ignore
        return metadata_list

    # ── AI providers ──────────────────────────────────────────────────────────

    async def _generate_openai(self, user_prompt: str) -> Optional[Dict[str, Any]]:
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self._settings.OPENAI_API_KEY)
            response = await client.chat.completions.create(
                model=self._settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": self._SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                max_tokens=800,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception as exc:
            logger.error(f"OpenAI metadata generation failed: {exc}")
            return None

    async def _generate_anthropic(self, user_prompt: str) -> Optional[Dict[str, Any]]:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self._settings.ANTHROPIC_API_KEY)
            message = client.messages.create(
                model=self._settings.ANTHROPIC_MODEL,
                max_tokens=800,
                system=self._SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = message.content[0].text
            # Strip any markdown code fences
            text = re.sub(r"```(?:json)?", "", text).strip()
            return json.loads(text)
        except Exception as exc:
            logger.error(f"Anthropic metadata generation failed: {exc}")
            return None

    async def _generate_gemini(self, user_prompt: str) -> Optional[Dict[str, Any]]:
        """Generate content using Google Gemini."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._settings.GEMINI_API_KEY)

            model = genai.GenerativeModel(
                model_name=self._settings.GEMINI_MODEL,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 800,
                }
            )

            # Gemini uses a single prompt combining system + user
            full_prompt = f"{self._SYSTEM_PROMPT}\n\n{user_prompt}"
            response = model.generate_content(full_prompt)
            text = response.text

            # Strip any markdown code fences
            text = re.sub(r"```(?:json)?", "", text).strip()
            return json.loads(text)
        except Exception as exc:
            logger.error(f"Gemini metadata generation failed: {exc}")
            return None

    # ── Parsing & validation ──────────────────────────────────────────────────

    def _parse_response(
        self,
        image_id: str,
        raw: Dict[str, Any],
        generation_prompt: str,
    ) -> ImageMetadata:
        title = str(raw.get("title", "Untitled Stock Image"))[:200]
        description = str(raw.get("description", ""))
        keywords = [str(k).lower().strip() for k in raw.get("keywords", [])]
        category = str(raw.get("category", "Other"))
        style = str(raw.get("style", "Photorealistic"))
        color_palette = [str(c) for c in raw.get("color_palette", ["Neutral"])]
        confidence = float(raw.get("confidence", 0.7))

        # Enforce keyword count
        keywords = list(dict.fromkeys(keywords))  # deduplicate, preserve order
        keywords = keywords[: self._keyword_count]

        # Enforce description length
        if len(description) > self._desc_max:
            description = description[: self._desc_max - 3] + "..."

        return ImageMetadata(
            image_id=image_id,
            title=title,
            description=description,
            keywords=keywords,
            category=category,
            style=style,
            color_palette=color_palette,
            confidence_score=confidence,
            generation_prompt=generation_prompt,
        )

    # ── Heuristic fallback (no AI required) ──────────────────────────────────

    def _heuristic_metadata(
        self, prompt: str, theme: str, style: str
    ) -> Dict[str, Any]:
        """
        Generate plausible metadata from the prompt text alone.
        Not as good as GPT-4 but functional for local testing.
        """
        # Extract first sentence of prompt as title seed
        words = prompt.split()[:12]
        title = " ".join(w.capitalize() for w in words if w.isalpha())[:70]
        if not title:
            title = f"{theme.title()} Image" if theme else "Stock Image"

        description = (
            f"{prompt.capitalize()}. "
            f"High-quality {style} image suitable for commercial use. "
            f"Ideal for websites, marketing materials, and editorial content."
        )[: self._desc_max]

        # Extract meaningful words from prompt as keywords
        stopwords = {
            "a", "an", "the", "and", "or", "in", "on", "at", "to",
            "of", "for", "with", "no", "not", "is", "are",
        }
        raw_keywords = [
            w.lower().strip(",.") for w in prompt.split()
            if len(w) > 3 and w.lower() not in stopwords
        ]
        keywords = list(dict.fromkeys(raw_keywords))[:20]
        if theme:
            keywords = [theme.lower()] + keywords
        # Pad with generic stock-photography keywords
        generic = [
            "stock photo", "commercial use", "high resolution", "professional",
            "background", "concept", "modern", "creative", "design",
        ]
        while len(keywords) < 25:
            for g in generic:
                if g not in keywords:
                    keywords.append(g)
                if len(keywords) >= 25:
                    break

        return {
            "title":         title,
            "description":   description,
            "keywords":      keywords,
            "category":      theme.title() if theme else "Other",
            "style":         style.title(),
            "color_palette": ["Neutral"],
            "confidence":    0.55,
        }

    def _fallback_metadata(self, image_id: str, prompt: str) -> ImageMetadata:
        """Minimal safe fallback when all generation attempts fail."""
        return ImageMetadata(
            image_id=image_id,
            title="Stock Image",
            description="AI-generated stock image for commercial use.",
            keywords=["stock", "image", "commercial", "professional"],
            category="Other",
            style="Photorealistic",
            color_palette=["Neutral"],
            confidence_score=0.0,
            generation_prompt=prompt,
        )
