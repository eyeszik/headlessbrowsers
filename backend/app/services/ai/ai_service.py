"""
AI content generation service with OpenAI and Anthropic integration.

Implements:
- Caption generation with platform optimization
- Hallucination prevention guardrails
- Assumption logging with confidence levels
"""
from typing import Dict, Any, Optional, List
import openai
import anthropic
import logging
import json
from datetime import datetime

from backend.app.core.config import settings
from backend.app.models.models import AssumptionLog, PlatformType

logger = logging.getLogger(__name__)


class AIContentGenerator:
    """
    AI-powered content generation with multiple providers.

    Features:
    - Multi-provider support (OpenAI, Anthropic)
    - Platform-specific optimization
    - Hallucination detection
    - Assumption logging
    - Confidence scoring
    """

    def __init__(self):
        self.openai_client = None
        self.anthropic_client = None

        # Initialize clients if API keys are available
        if settings.OPENAI_API_KEY:
            openai.api_key = settings.OPENAI_API_KEY
            self.openai_client = openai

        if settings.ANTHROPIC_API_KEY:
            self.anthropic_client = anthropic.Anthropic(
                api_key=settings.ANTHROPIC_API_KEY
            )

        # Platform-specific constraints
        self.platform_constraints = {
            PlatformType.TWITTER: {
                "max_length": 280,
                "hashtag_limit": 2,
                "tone": "concise and engaging"
            },
            PlatformType.FACEBOOK: {
                "max_length": 63206,
                "hashtag_limit": 5,
                "tone": "conversational and friendly"
            },
            PlatformType.INSTAGRAM: {
                "max_length": 2200,
                "hashtag_limit": 30,
                "tone": "visual-focused and inspiring"
            },
            PlatformType.LINKEDIN: {
                "max_length": 3000,
                "hashtag_limit": 3,
                "tone": "professional and informative"
            },
            PlatformType.YOUTUBE: {
                "max_length": 5000,
                "hashtag_limit": 15,
                "tone": "descriptive and searchable"
            }
        }

    async def generate_caption(
        self,
        prompt: str,
        platform: PlatformType,
        provider: str = "openai",
        context: Optional[Dict[str, Any]] = None,
        content_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate platform-optimized caption.

        Args:
            prompt: Content description or topic
            platform: Target platform
            provider: "openai" or "anthropic"
            context: Additional context (campaign info, brand voice, etc.)
            content_id: Content ID for assumption logging

        Returns:
            Dict with:
                - caption: Generated text
                - hashtags: List of hashtags
                - confidence: Confidence score 0-1
                - assumptions: List of assumptions made
                - guardrails_triggered: List of triggered guardrails
        """
        constraints = self.platform_constraints.get(
            platform,
            {"max_length": 1000, "hashtag_limit": 5, "tone": "engaging"}
        )

        # Build system prompt with guardrails
        system_prompt = self._build_system_prompt(platform, constraints, context)

        # Generate content
        if provider == "openai" and self.openai_client:
            result = await self._generate_with_openai(prompt, system_prompt)
        elif provider == "anthropic" and self.anthropic_client:
            result = await self._generate_with_anthropic(prompt, system_prompt)
        else:
            raise ValueError(f"Provider {provider} not available or not configured")

        # Apply guardrails
        result = self._apply_guardrails(result, platform, constraints)

        # Log assumptions if content_id provided
        if content_id and result.get("assumptions"):
            await self._log_assumptions(
                content_id,
                provider,
                result["assumptions"],
                result.get("confidence", 0.5)
            )

        return result

    def _build_system_prompt(
        self,
        platform: PlatformType,
        constraints: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build system prompt with platform-specific guidelines."""
        prompt = f"""You are an expert social media content creator specializing in {platform.value}.

**Platform Guidelines:**
- Maximum length: {constraints['max_length']} characters
- Hashtag limit: {constraints['hashtag_limit']}
- Tone: {constraints['tone']}

**Content Requirements:**
1. Create engaging, authentic content that resonates with the platform's audience
2. Use appropriate hashtags strategically (don't overuse)
3. Keep within character limits
4. Maintain brand voice consistency

**CRITICAL GUARDRAILS:**
- DO NOT make factual claims without verification
- DO NOT use copyrighted or trademarked content without permission
- DO NOT make misleading or deceptive statements
- DO NOT use offensive or inappropriate language
- ALWAYS disclose if content is AI-generated when required by platform
- ALWAYS flag any assumptions made with confidence levels

**Output Format:**
Return a JSON object with:
{{
    "caption": "The generated caption text",
    "hashtags": ["hashtag1", "hashtag2"],
    "assumptions": [
        {{
            "assumption": "What was assumed",
            "confidence": 0.0-1.0,
            "needs_verification": true/false
        }}
    ],
    "hallucination_risk": "low/medium/high",
    "explanation": "Brief explanation of creative choices"
}}
"""

        if context:
            if "brand_voice" in context:
                prompt += f"\n**Brand Voice:** {context['brand_voice']}"
            if "target_audience" in context:
                prompt += f"\n**Target Audience:** {context['target_audience']}"
            if "campaign_goals" in context:
                prompt += f"\n**Campaign Goals:** {context['campaign_goals']}"

        return prompt

    async def _generate_with_openai(
        self,
        prompt: str,
        system_prompt: str
    ) -> Dict[str, Any]:
        """Generate content using OpenAI GPT-4."""
        try:
            response = await self.openai_client.ChatCompletion.acreate(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=settings.OPENAI_MAX_TOKENS,
                temperature=0.7,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            result = json.loads(content)

            return {
                "caption": result.get("caption", ""),
                "hashtags": result.get("hashtags", []),
                "confidence": self._calculate_confidence(result),
                "assumptions": result.get("assumptions", []),
                "hallucination_risk": result.get("hallucination_risk", "medium"),
                "explanation": result.get("explanation", ""),
                "provider": "openai"
            }

        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise

    async def _generate_with_anthropic(
        self,
        prompt: str,
        system_prompt: str
    ) -> Dict[str, Any]:
        """Generate content using Anthropic Claude."""
        try:
            message = self.anthropic_client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=settings.ANTHROPIC_MAX_TOKENS,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            content = message.content[0].text

            # Parse JSON response
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # If not JSON, treat as plain caption
                result = {
                    "caption": content,
                    "hashtags": [],
                    "assumptions": [],
                    "hallucination_risk": "medium"
                }

            return {
                "caption": result.get("caption", ""),
                "hashtags": result.get("hashtags", []),
                "confidence": self._calculate_confidence(result),
                "assumptions": result.get("assumptions", []),
                "hallucination_risk": result.get("hallucination_risk", "medium"),
                "explanation": result.get("explanation", ""),
                "provider": "anthropic"
            }

        except Exception as e:
            logger.error(f"Anthropic generation failed: {e}")
            raise

    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        """Calculate overall confidence score based on various factors."""
        confidence = 0.8  # Base confidence

        # Reduce if assumptions present
        assumptions = result.get("assumptions", [])
        if assumptions:
            avg_assumption_confidence = sum(
                a.get("confidence", 0.5) for a in assumptions
            ) / len(assumptions)
            confidence *= avg_assumption_confidence

        # Reduce based on hallucination risk
        risk = result.get("hallucination_risk", "medium")
        risk_penalties = {"low": 0.0, "medium": 0.1, "high": 0.3}
        confidence -= risk_penalties.get(risk, 0.1)

        return max(0.0, min(1.0, confidence))

    def _apply_guardrails(
        self,
        result: Dict[str, Any],
        platform: PlatformType,
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply guardrails to generated content.

        Checks:
        - Length constraints
        - Hashtag limits
        - Hallucination detection keywords
        - Offensive language
        """
        guardrails_triggered = []

        caption = result.get("caption", "")
        hashtags = result.get("hashtags", [])

        # Length constraint
        max_length = constraints["max_length"]
        if len(caption) > max_length:
            caption = caption[:max_length - 3] + "..."
            guardrails_triggered.append("length_exceeded")

        # Hashtag limit
        hashtag_limit = constraints["hashtag_limit"]
        if len(hashtags) > hashtag_limit:
            hashtags = hashtags[:hashtag_limit]
            guardrails_triggered.append("hashtag_limit_exceeded")

        # Hallucination detection (basic keyword matching)
        hallucination_keywords = [
            "guarantee", "proven fact", "scientifically proven",
            "definitely", "always works", "100% effective"
        ]
        caption_lower = caption.lower()
        if any(keyword in caption_lower for keyword in hallucination_keywords):
            guardrails_triggered.append("potential_hallucination")
            result["hallucination_risk"] = "high"

        # Offensive language check (basic)
        # In production, use a proper content moderation API
        offensive_keywords = ["offensive1", "offensive2"]  # Placeholder
        if any(keyword in caption_lower for keyword in offensive_keywords):
            guardrails_triggered.append("offensive_language_detected")
            # Would typically reject or flag for review

        result["caption"] = caption
        result["hashtags"] = hashtags
        result["guardrails_triggered"] = guardrails_triggered

        return result

    async def _log_assumptions(
        self,
        content_id: int,
        provider: str,
        assumptions: List[Dict[str, Any]],
        overall_confidence: float
    ):
        """Log AI assumptions to database for audit trail."""
        from backend.app.db.session import SessionLocal

        with SessionLocal() as db:
            for assumption in assumptions:
                log_entry = AssumptionLog(
                    content_id=content_id,
                    ai_service=provider,
                    assumption_type="content_generation",
                    assumption_text=assumption.get("assumption", ""),
                    confidence_level=assumption.get("confidence", overall_confidence),
                    validated=None,
                    hallucination_detected=assumption.get("needs_verification", False),
                    created_at=datetime.utcnow()
                )
                db.add(log_entry)

            db.commit()

    async def batch_generate(
        self,
        prompts: List[str],
        platform: PlatformType,
        provider: str = "openai"
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple captions in batch.

        Args:
            prompts: List of prompts
            platform: Target platform
            provider: AI provider

        Returns:
            List of generated results
        """
        results = []
        for prompt in prompts:
            try:
                result = await self.generate_caption(
                    prompt, platform, provider
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Batch generation failed for prompt: {e}")
                results.append({
                    "error": str(e),
                    "caption": "",
                    "confidence": 0.0
                })

        return results


# Global instance
ai_generator = AIContentGenerator()
