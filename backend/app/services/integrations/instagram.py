"""
Instagram Graph API integration.
"""
from typing import Dict, Any, Optional, List
import aiohttp
import logging
from .base import BasePlatformIntegration

logger = logging.getLogger(__name__)


class InstagramIntegration(BasePlatformIntegration):
    """Instagram Graph API integration (uses Facebook Graph API)."""

    BASE_URL = "https://graph.facebook.com/v18.0"

    async def publish_content(
        self,
        content: Dict[str, Any],
        media_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Publish post to Instagram.

        Args:
            content: Dict with 'caption', 'location_id', 'user_tags'
            media_urls: List of image/video URLs (required)

        Returns:
            Dict with 'platform_post_id', 'url', 'published_at'
        """
        async def _publish():
            ig_user_id = content.get("ig_user_id")
            if not ig_user_id:
                raise ValueError("ig_user_id required for Instagram posting")

            if not media_urls or len(media_urls) == 0:
                raise ValueError("Instagram requires at least one media URL")

            caption = content.get("caption", "")

            # Step 1: Create media container
            container_data = {
                "access_token": self.access_token,
                "caption": caption,
            }

            # Single media or carousel
            if len(media_urls) == 1:
                media_type = self._get_media_type(media_urls[0])
                if media_type == "video":
                    container_data["media_type"] = "VIDEO"
                    container_data["video_url"] = media_urls[0]
                else:
                    container_data["image_url"] = media_urls[0]

                # Optional: location, user tags
                if "location_id" in content:
                    container_data["location_id"] = content["location_id"]

                if "user_tags" in content:
                    container_data["user_tags"] = content["user_tags"]
            else:
                # Carousel (multiple images)
                container_data["media_type"] = "CAROUSEL"
                # Would need to create children containers first

            async with aiohttp.ClientSession() as session:
                # Create container
                async with session.post(
                    f"{self.BASE_URL}/{ig_user_id}/media",
                    data=container_data
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    creation_id = result["id"]

                # Step 2: Publish container
                publish_data = {
                    "creation_id": creation_id,
                    "access_token": self.access_token
                }

                async with session.post(
                    f"{self.BASE_URL}/{ig_user_id}/media_publish",
                    data=publish_data
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

                    media_id = result["id"]
                    return {
                        "platform_post_id": media_id,
                        "url": f"https://www.instagram.com/p/{media_id}/",
                        "published_at": None  # Not provided in response
                    }

        return await self.execute_with_retry(_publish)

    def _get_media_type(self, url: str) -> str:
        """Determine media type from URL."""
        url_lower = url.lower()
        if url_lower.endswith((".mp4", ".mov")):
            return "video"
        return "image"

    async def fetch_analytics(
        self,
        post_id: str,
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch Instagram post analytics.

        Args:
            post_id: Instagram media ID
            metrics: List of metrics

        Returns:
            Dict with analytics data
        """
        async def _fetch():
            if metrics is None:
                metric_list = "engagement,impressions,reach,saved,video_views"
            else:
                metric_list = ",".join(metrics)

            async with aiohttp.ClientSession() as session:
                params = {
                    "fields": f"insights.metric({metric_list}),like_count,comments_count",
                    "access_token": self.access_token
                }

                async with session.get(
                    f"{self.BASE_URL}/{post_id}",
                    params=params
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

                    # Parse insights
                    insights = {}
                    if "insights" in result and "data" in result["insights"]:
                        for insight in result["insights"]["data"]:
                            insights[insight["name"]] = insight["values"][0]["value"]

                    return {
                        "impressions": insights.get("impressions", 0),
                        "reach": insights.get("reach", 0),
                        "likes": result.get("like_count", 0),
                        "comments": result.get("comments_count", 0),
                        "saves": insights.get("saved", 0),
                        "shares": 0,  # Not directly available
                        "engagement_count": insights.get("engagement", 0),
                        "platform_metrics": {
                            "video_views": insights.get("video_views", 0),
                        }
                    }

        return await self.execute_with_retry(_fetch)

    async def delete_content(self, post_id: str) -> bool:
        """Delete Instagram post."""
        async def _delete():
            async with aiohttp.ClientSession() as session:
                params = {
                    "access_token": self.access_token
                }

                async with session.delete(
                    f"{self.BASE_URL}/{post_id}",
                    params=params
                ) as response:
                    response.raise_for_status()
                    return True

        return await self.execute_with_retry(_delete)
