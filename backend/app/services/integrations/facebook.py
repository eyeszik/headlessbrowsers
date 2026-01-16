"""
Facebook Graph API integration.
"""
from typing import Dict, Any, Optional, List
import aiohttp
import logging
from .base import BasePlatformIntegration

logger = logging.getLogger(__name__)


class FacebookIntegration(BasePlatformIntegration):
    """Facebook Graph API integration."""

    BASE_URL = "https://graph.facebook.com/v18.0"

    async def publish_content(
        self,
        content: Dict[str, Any],
        media_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Publish post to Facebook.

        Args:
            content: Dict with 'message', 'link', 'published' (bool)
            media_urls: List of image/video URLs

        Returns:
            Dict with 'platform_post_id', 'url', 'published_at'
        """
        async def _publish():
            page_id = content.get("page_id")
            if not page_id:
                raise ValueError("page_id required for Facebook posting")

            post_data = {
                "message": content.get("message", ""),
                "access_token": self.access_token
            }

            # Add link if provided
            if "link" in content:
                post_data["link"] = content["link"]

            # Scheduled publishing
            if "scheduled_publish_time" in content:
                post_data["published"] = False
                post_data["scheduled_publish_time"] = content["scheduled_publish_time"]

            # Handle media
            endpoint = f"/{page_id}/feed"
            if media_urls:
                if len(media_urls) == 1:
                    # Single photo or video
                    media_type = self._get_media_type(media_urls[0])
                    if media_type == "photo":
                        endpoint = f"/{page_id}/photos"
                        post_data["url"] = media_urls[0]
                    elif media_type == "video":
                        endpoint = f"/{page_id}/videos"
                        post_data["file_url"] = media_urls[0]
                else:
                    # Multiple photos - use batch upload
                    endpoint = f"/{page_id}/feed"
                    # Attach photos (would need media IDs from prior upload)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}{endpoint}",
                    data=post_data
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

                    post_id = result["id"]
                    return {
                        "platform_post_id": post_id,
                        "url": f"https://www.facebook.com/{post_id}",
                        "published_at": result.get("created_time")
                    }

        return await self.execute_with_retry(_publish)

    def _get_media_type(self, url: str) -> str:
        """Determine media type from URL."""
        url_lower = url.lower()
        if url_lower.endswith((".mp4", ".mov", ".avi")):
            return "video"
        elif url_lower.endswith((".jpg", ".jpeg", ".png", ".gif")):
            return "photo"
        return "unknown"

    async def fetch_analytics(
        self,
        post_id: str,
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch post analytics.

        Args:
            post_id: Facebook post ID
            metrics: List of metrics

        Returns:
            Dict with analytics data
        """
        async def _fetch():
            if metrics is None:
                fields = "insights.metric(post_impressions,post_engaged_users,post_clicks,post_reactions_by_type_total),shares,likes.summary(true),comments.summary(true)"
            else:
                fields = f"insights.metric({','.join(metrics)})"

            async with aiohttp.ClientSession() as session:
                params = {
                    "fields": fields,
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

                    # Extract engagement metrics
                    likes = result.get("likes", {}).get("summary", {}).get("total_count", 0)
                    comments = result.get("comments", {}).get("summary", {}).get("total_count", 0)
                    shares = result.get("shares", {}).get("count", 0)

                    return {
                        "impressions": insights.get("post_impressions", 0),
                        "reach": insights.get("post_engaged_users", 0),
                        "likes": likes,
                        "comments": comments,
                        "shares": shares,
                        "clicks": insights.get("post_clicks", 0),
                        "engagement_count": likes + comments + shares,
                        "platform_metrics": {
                            "reactions": insights.get("post_reactions_by_type_total", {}),
                        }
                    }

        return await self.execute_with_retry(_fetch)

    async def delete_content(self, post_id: str) -> bool:
        """Delete Facebook post."""
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
