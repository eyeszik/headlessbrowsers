"""
Platform-specific content formatting service.
"""
from typing import Dict, Any, List, Optional
import re
import logging

from backend.app.models.models import PlatformType

logger = logging.getLogger(__name__)


class ContentFormatter:
    """
    Format content for specific social media platforms.

    Features:
    - Character limit enforcement
    - Hashtag optimization
    - Link shortening placeholders
    - Platform-specific markup
    - Emoji handling
    """

    def __init__(self):
        self.platform_limits = {
            PlatformType.TWITTER: {
                "text": 280,
                "hashtags": 2,
                "mentions": 10
            },
            PlatformType.FACEBOOK: {
                "text": 63206,
                "hashtags": 30,
                "mentions": 50
            },
            PlatformType.INSTAGRAM: {
                "text": 2200,
                "hashtags": 30,
                "mentions": 30
            },
            PlatformType.LINKEDIN: {
                "text": 3000,
                "hashtags": 5,
                "mentions": 30
            },
            PlatformType.YOUTUBE: {
                "description": 5000,
                "title": 100,
                "hashtags": 15
            }
        }

    def format_for_platform(
        self,
        content: Dict[str, Any],
        platform: PlatformType,
        truncate: bool = True
    ) -> Dict[str, Any]:
        """
        Format content for specific platform.

        Args:
            content: Dict with 'text', 'hashtags', 'mentions', etc.
            platform: Target platform
            truncate: Whether to truncate if exceeding limits

        Returns:
            Formatted content dict
        """
        formatted = content.copy()

        if platform == PlatformType.TWITTER:
            formatted = self._format_for_twitter(formatted, truncate)
        elif platform == PlatformType.FACEBOOK:
            formatted = self._format_for_facebook(formatted, truncate)
        elif platform == PlatformType.INSTAGRAM:
            formatted = self._format_for_instagram(formatted, truncate)
        elif platform == PlatformType.LINKEDIN:
            formatted = self._format_for_linkedin(formatted, truncate)
        elif platform == PlatformType.YOUTUBE:
            formatted = self._format_for_youtube(formatted, truncate)

        return formatted

    def _format_for_twitter(
        self,
        content: Dict[str, Any],
        truncate: bool
    ) -> Dict[str, Any]:
        """Format content for Twitter."""
        text = content.get("text", "")
        hashtags = content.get("hashtags", [])

        # Limit hashtags
        limits = self.platform_limits[PlatformType.TWITTER]
        hashtags = hashtags[:limits["hashtags"]]

        # Build tweet text
        hashtag_text = " ".join(f"#{tag}" for tag in hashtags)
        full_text = f"{text} {hashtag_text}".strip()

        # Handle character limit
        if len(full_text) > limits["text"]:
            if truncate:
                # Reserve space for ellipsis and hashtags
                available = limits["text"] - len(hashtag_text) - 4
                text = text[:available] + "..."
                full_text = f"{text} {hashtag_text}".strip()
            else:
                logger.warning(
                    f"Twitter text exceeds {limits['text']} characters"
                )

        return {
            **content,
            "text": full_text,
            "hashtags": hashtags,
            "platform_metadata": {
                "character_count": len(full_text),
                "within_limits": len(full_text) <= limits["text"]
            }
        }

    def _format_for_facebook(
        self,
        content: Dict[str, Any],
        truncate: bool
    ) -> Dict[str, Any]:
        """Format content for Facebook."""
        text = content.get("text", "")
        hashtags = content.get("hashtags", [])

        limits = self.platform_limits[PlatformType.FACEBOOK]
        hashtags = hashtags[:limits["hashtags"]]

        # Facebook allows hashtags inline or at end
        # Place at end for better readability
        hashtag_text = "\n\n" + " ".join(f"#{tag}" for tag in hashtags) if hashtags else ""
        full_text = f"{text}{hashtag_text}"

        if len(full_text) > limits["text"] and truncate:
            available = limits["text"] - len(hashtag_text) - 4
            text = text[:available] + "..."
            full_text = f"{text}{hashtag_text}"

        return {
            **content,
            "message": full_text,  # Facebook uses 'message' not 'text'
            "hashtags": hashtags,
            "platform_metadata": {
                "character_count": len(full_text)
            }
        }

    def _format_for_instagram(
        self,
        content: Dict[str, Any],
        truncate: bool
    ) -> Dict[str, Any]:
        """Format content for Instagram."""
        text = content.get("text", "")
        hashtags = content.get("hashtags", [])

        limits = self.platform_limits[PlatformType.INSTAGRAM]
        hashtags = hashtags[:limits["hashtags"]]

        # Instagram: hashtags can be inline or grouped at end
        # Best practice: 5-10 relevant hashtags at the end
        hashtag_text = "\n.\n.\n.\n" + " ".join(f"#{tag}" for tag in hashtags) if hashtags else ""
        full_text = f"{text}{hashtag_text}"

        if len(full_text) > limits["text"] and truncate:
            available = limits["text"] - len(hashtag_text) - 4
            text = text[:available] + "..."
            full_text = f"{text}{hashtag_text}"

        return {
            **content,
            "caption": full_text,  # Instagram uses 'caption'
            "hashtags": hashtags,
            "platform_metadata": {
                "character_count": len(full_text),
                "hashtag_count": len(hashtags)
            }
        }

    def _format_for_linkedin(
        self,
        content: Dict[str, Any],
        truncate: bool
    ) -> Dict[str, Any]:
        """Format content for LinkedIn."""
        text = content.get("text", "")
        hashtags = content.get("hashtags", [])

        limits = self.platform_limits[PlatformType.LINKEDIN]

        # LinkedIn: Use hashtags sparingly (3-5 max)
        hashtags = hashtags[:limits["hashtags"]]

        # Add line breaks for better readability
        if "\n" not in text and len(text) > 300:
            # Add breaks at sentence boundaries
            text = self._add_line_breaks(text)

        hashtag_text = "\n\n" + " ".join(f"#{tag}" for tag in hashtags) if hashtags else ""
        full_text = f"{text}{hashtag_text}"

        if len(full_text) > limits["text"] and truncate:
            available = limits["text"] - len(hashtag_text) - 4
            text = text[:available] + "..."
            full_text = f"{text}{hashtag_text}"

        return {
            **content,
            "text": full_text,
            "hashtags": hashtags,
            "platform_metadata": {
                "character_count": len(full_text),
                "professional_format": True
            }
        }

    def _format_for_youtube(
        self,
        content: Dict[str, Any],
        truncate: bool
    ) -> Dict[str, Any]:
        """Format content for YouTube."""
        title = content.get("title", "")
        description = content.get("description", "")
        hashtags = content.get("hashtags", [])

        limits = self.platform_limits[PlatformType.YOUTUBE]

        # Truncate title
        if len(title) > limits["title"] and truncate:
            title = title[:limits["title"] - 3] + "..."

        # Limit hashtags (first 3 in description appear above title)
        hashtags = hashtags[:limits["hashtags"]]

        # YouTube description format:
        # - First 3 hashtags appear above title
        # - Description text
        # - Additional hashtags at end
        # - Timestamps, links, etc.
        first_hashtags = hashtags[:3]
        remaining_hashtags = hashtags[3:]

        formatted_description = ""

        if first_hashtags:
            formatted_description += " ".join(f"#{tag}" for tag in first_hashtags) + "\n\n"

        formatted_description += description

        if remaining_hashtags:
            formatted_description += "\n\n" + " ".join(f"#{tag}" for tag in remaining_hashtags)

        # Add timestamps if provided
        if "timestamps" in content:
            formatted_description += "\n\n📍 TIMESTAMPS:\n"
            for timestamp in content["timestamps"]:
                formatted_description += f"{timestamp['time']} - {timestamp['label']}\n"

        if len(formatted_description) > limits["description"] and truncate:
            formatted_description = formatted_description[:limits["description"] - 3] + "..."

        return {
            **content,
            "title": title,
            "description": formatted_description,
            "hashtags": hashtags,
            "platform_metadata": {
                "title_length": len(title),
                "description_length": len(formatted_description)
            }
        }

    def _add_line_breaks(self, text: str, max_paragraph_length: int = 400) -> str:
        """Add line breaks at sentence boundaries for readability."""
        sentences = re.split(r'([.!?]+\s+)', text)
        result = []
        current_paragraph = []
        current_length = 0

        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            separator = sentences[i + 1] if i + 1 < len(sentences) else ""

            sentence_with_sep = sentence + separator
            current_length += len(sentence_with_sep)
            current_paragraph.append(sentence_with_sep)

            if current_length >= max_paragraph_length:
                result.append("".join(current_paragraph).strip())
                result.append("\n\n")
                current_paragraph = []
                current_length = 0

        if current_paragraph:
            result.append("".join(current_paragraph).strip())

        return "".join(result)

    def extract_hashtags(self, text: str) -> List[str]:
        """Extract hashtags from text."""
        pattern = r'#(\w+)'
        matches = re.findall(pattern, text)
        return matches

    def extract_mentions(self, text: str) -> List[str]:
        """Extract @mentions from text."""
        pattern = r'@(\w+)'
        matches = re.findall(pattern, text)
        return matches

    def validate_for_platform(
        self,
        content: Dict[str, Any],
        platform: PlatformType
    ) -> Dict[str, Any]:
        """
        Validate content against platform requirements.

        Returns:
            Dict with validation results
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        limits = self.platform_limits.get(platform, {})
        text = content.get("text", content.get("description", ""))

        # Check text length
        if "text" in limits and len(text) > limits["text"]:
            result["valid"] = False
            result["errors"].append(
                f"Text exceeds {limits['text']} characters ({len(text)} chars)"
            )

        # Check hashtag count
        hashtags = content.get("hashtags", [])
        if "hashtags" in limits and len(hashtags) > limits["hashtags"]:
            result["warnings"].append(
                f"Hashtag count exceeds recommended limit of {limits['hashtags']}"
            )

        return result


# Global instance
content_formatter = ContentFormatter()
