"""
YouTube Data API v3 integration.
"""
from typing import Dict, Any, Optional, List
import aiohttp
import logging
from .base import BasePlatformIntegration

logger = logging.getLogger(__name__)


class YouTubeIntegration(BasePlatformIntegration):
    """YouTube Data API v3 integration."""

    BASE_URL = "https://www.googleapis.com/youtube/v3"
    UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"

    def __init__(self, api_key: str, access_token: str, **kwargs):
        super().__init__(access_token, **kwargs)
        self.api_key = api_key

    async def publish_content(
        self,
        content: Dict[str, Any],
        media_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Publish video to YouTube.

        Args:
            content: Dict with 'title', 'description', 'category_id', 'privacy_status'
            media_urls: List with single video URL

        Returns:
            Dict with 'platform_post_id', 'url', 'published_at'
        """
        async def _publish():
            if not media_urls or len(media_urls) == 0:
                raise ValueError("YouTube requires a video URL")

            video_url = media_urls[0]

            # Prepare video metadata
            snippet = {
                "title": content.get("title", "")[:100],  # Max 100 chars
                "description": content.get("description", "")[:5000],  # Max 5000 chars
                "categoryId": content.get("category_id", "22"),  # 22 = People & Blogs
                "tags": content.get("tags", [])[:500],  # Max 500 tags
            }

            status = {
                "privacyStatus": content.get("privacy_status", "public"),
                "selfDeclaredMadeForKids": content.get("made_for_kids", False),
            }

            # Upload video
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                }

                # Note: Actual video upload would use multipart/related
                # This is a simplified version
                params = {
                    "part": "snippet,status",
                    "key": self.api_key
                }

                data = {
                    "snippet": snippet,
                    "status": status
                }

                async with session.post(
                    self.UPLOAD_URL,
                    headers=headers,
                    params=params,
                    json=data
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

                    return {
                        "platform_post_id": result["id"],
                        "url": f"https://www.youtube.com/watch?v={result['id']}",
                        "published_at": result["snippet"]["publishedAt"]
                    }

        return await self.execute_with_retry(_publish)

    async def fetch_analytics(
        self,
        post_id: str,
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch video analytics.

        Args:
            post_id: YouTube video ID
            metrics: List of metrics (views, likes, comments, etc.)

        Returns:
            Dict with analytics data
        """
        async def _fetch():
            if metrics is None:
                metrics_str = "views,likes,dislikes,comments,estimatedMinutesWatched"
            else:
                metrics_str = ",".join(metrics)

            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.access_token}"
                }

                # Get video statistics
                params = {
                    "part": "statistics,snippet",
                    "id": post_id,
                    "key": self.api_key
                }

                async with session.get(
                    f"{self.BASE_URL}/videos",
                    headers=headers,
                    params=params
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

                    if not result.get("items"):
                        raise ValueError(f"Video not found: {post_id}")

                    item = result["items"][0]
                    stats = item["statistics"]

                    return {
                        "impressions": int(stats.get("viewCount", 0)),
                        "likes": int(stats.get("likeCount", 0)),
                        "comments": int(stats.get("commentCount", 0)),
                        "shares": 0,  # Not directly available
                        "platform_metrics": {
                            "dislikes": int(stats.get("dislikeCount", 0)),
                            "favorites": int(stats.get("favoriteCount", 0)),
                        }
                    }

        return await self.execute_with_retry(_fetch)

    async def delete_content(self, post_id: str) -> bool:
        """Delete YouTube video."""
        async def _delete():
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.access_token}"
                }

                params = {
                    "id": post_id,
                    "key": self.api_key
                }

                async with session.delete(
                    f"{self.BASE_URL}/videos",
                    headers=headers,
                    params=params
                ) as response:
                    response.raise_for_status()
                    return True

        return await self.execute_with_retry(_delete)
