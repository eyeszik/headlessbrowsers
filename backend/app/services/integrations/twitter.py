"""
Twitter API v2 integration.
"""
from typing import Dict, Any, Optional, List
import aiohttp
import logging
from .base import BasePlatformIntegration

logger = logging.getLogger(__name__)


class TwitterIntegration(BasePlatformIntegration):
    """Twitter API v2 integration."""

    BASE_URL = "https://api.twitter.com/2"

    def __init__(
        self,
        access_token: str,
        bearer_token: Optional[str] = None,
        **kwargs
    ):
        super().__init__(access_token, **kwargs)
        self.bearer_token = bearer_token or access_token

    async def publish_content(
        self,
        content: Dict[str, Any],
        media_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Publish tweet to Twitter.

        Args:
            content: Dict with 'text', optional 'reply_settings', 'quote_tweet_id'
            media_urls: List of media URLs (up to 4 images or 1 video)

        Returns:
            Dict with 'platform_post_id', 'url', 'published_at'
        """
        async def _publish():
            text = content.get("text", "")

            # Twitter character limit
            if len(text) > 280:
                text = text[:277] + "..."

            tweet_data = {
                "text": text
            }

            # Add optional fields
            if "reply_settings" in content:
                tweet_data["reply_settings"] = content["reply_settings"]

            if "quote_tweet_id" in content:
                tweet_data["quote_tweet_id"] = content["quote_tweet_id"]

            # Handle media
            if media_urls:
                media_ids = await self._upload_media(media_urls)
                if media_ids:
                    tweet_data["media"] = {"media_ids": media_ids}

            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.bearer_token}",
                    "Content-Type": "application/json"
                }

                async with session.post(
                    f"{self.BASE_URL}/tweets",
                    headers=headers,
                    json=tweet_data
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

                    tweet_id = result["data"]["id"]
                    return {
                        "platform_post_id": tweet_id,
                        "url": f"https://twitter.com/i/web/status/{tweet_id}",
                        "published_at": result["data"].get("created_at")
                    }

        return await self.execute_with_retry(_publish)

    async def _upload_media(self, media_urls: List[str]) -> List[str]:
        """Upload media to Twitter and return media IDs."""
        # Note: Twitter media upload uses v1.1 API
        upload_url = "https://upload.twitter.com/1.1/media/upload.json"
        media_ids = []

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.bearer_token}"
            }

            for media_url in media_urls[:4]:  # Max 4 images
                # In production, you'd download the media and upload it
                # This is a simplified version
                logger.info(f"Uploading media: {media_url}")
                # Simulate media upload
                # media_ids.append("mock_media_id")

        return media_ids

    async def fetch_analytics(
        self,
        post_id: str,
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch tweet analytics.

        Args:
            post_id: Twitter tweet ID
            metrics: List of metrics

        Returns:
            Dict with analytics data
        """
        async def _fetch():
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.bearer_token}"
                }

                # Get tweet with metrics
                params = {
                    "tweet.fields": "public_metrics,created_at",
                    "expansions": "author_id"
                }

                async with session.get(
                    f"{self.BASE_URL}/tweets/{post_id}",
                    headers=headers,
                    params=params
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

                    if "data" not in result:
                        raise ValueError(f"Tweet not found: {post_id}")

                    metrics = result["data"]["public_metrics"]

                    return {
                        "impressions": metrics.get("impression_count", 0),
                        "likes": metrics.get("like_count", 0),
                        "comments": metrics.get("reply_count", 0),
                        "shares": metrics.get("retweet_count", 0),
                        "engagement_count": (
                            metrics.get("like_count", 0) +
                            metrics.get("reply_count", 0) +
                            metrics.get("retweet_count", 0) +
                            metrics.get("quote_count", 0)
                        ),
                        "platform_metrics": {
                            "quote_count": metrics.get("quote_count", 0),
                            "bookmark_count": metrics.get("bookmark_count", 0),
                        }
                    }

        return await self.execute_with_retry(_fetch)

    async def delete_content(self, post_id: str) -> bool:
        """Delete tweet."""
        async def _delete():
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.bearer_token}"
                }

                async with session.delete(
                    f"{self.BASE_URL}/tweets/{post_id}",
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    return True

        return await self.execute_with_retry(_delete)
