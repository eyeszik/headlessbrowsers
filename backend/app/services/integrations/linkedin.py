"""
LinkedIn API v2 integration.
"""
from typing import Dict, Any, Optional, List
import aiohttp
import logging
from .base import BasePlatformIntegration

logger = logging.getLogger(__name__)


class LinkedInIntegration(BasePlatformIntegration):
    """LinkedIn API v2 integration."""

    BASE_URL = "https://api.linkedin.com/v2"

    async def publish_content(
        self,
        content: Dict[str, Any],
        media_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Publish post to LinkedIn.

        Args:
            content: Dict with 'text', 'visibility' ('PUBLIC', 'CONNECTIONS')
            media_urls: List of image URLs

        Returns:
            Dict with 'platform_post_id', 'url', 'published_at'
        """
        async def _publish():
            author_urn = content.get("author_urn")  # urn:li:person:{person_id}
            if not author_urn:
                raise ValueError("author_urn required for LinkedIn posting")

            text = content.get("text", "")

            # Build post data
            post_data = {
                "author": author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": text
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": content.get(
                        "visibility", "PUBLIC"
                    )
                }
            }

            # Handle media
            if media_urls:
                # Upload media first and get asset URNs
                media_assets = []
                for media_url in media_urls:
                    asset_urn = await self._upload_media(media_url, author_urn)
                    media_assets.append({
                        "status": "READY",
                        "media": asset_urn
                    })

                post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "IMAGE"
                post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = media_assets

            # Add link if provided
            if "link_url" in content:
                post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "ARTICLE"
                post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [{
                    "status": "READY",
                    "originalUrl": content["link_url"]
                }]

            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0"
                }

                async with session.post(
                    f"{self.BASE_URL}/ugcPosts",
                    headers=headers,
                    json=post_data
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

                    post_id = result["id"]
                    return {
                        "platform_post_id": post_id,
                        "url": f"https://www.linkedin.com/feed/update/{post_id}/",
                        "published_at": result.get("created", {}).get("time")
                    }

        return await self.execute_with_retry(_publish)

    async def _upload_media(self, media_url: str, author_urn: str) -> str:
        """Upload media to LinkedIn and return asset URN."""
        # Step 1: Register upload
        register_data = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": author_urn,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent"
                }]
            }
        }

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            async with session.post(
                f"{self.BASE_URL}/assets?action=registerUpload",
                headers=headers,
                json=register_data
            ) as response:
                response.raise_for_status()
                result = await response.json()

                asset_urn = result["value"]["asset"]
                upload_url = result["value"]["uploadMechanism"][
                    "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
                ]["uploadUrl"]

            # Step 2: Upload media (simplified - would download and upload binary)
            logger.info(f"Uploading media to LinkedIn: {media_url}")

            return asset_urn

    async def fetch_analytics(
        self,
        post_id: str,
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch LinkedIn post analytics.

        Args:
            post_id: LinkedIn post URN
            metrics: List of metrics

        Returns:
            Dict with analytics data
        """
        async def _fetch():
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "X-Restli-Protocol-Version": "2.0.0"
                }

                # Get post statistics
                params = {
                    "q": "ugcPost",
                    "ugcPost": post_id
                }

                async with session.get(
                    f"{self.BASE_URL}/socialActions",
                    headers=headers,
                    params=params
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

                    if "elements" not in result or len(result["elements"]) == 0:
                        raise ValueError(f"Post not found: {post_id}")

                    stats = result["elements"][0]

                    likes = stats.get("likesSummary", {}).get("totalLikes", 0)
                    comments = stats.get("commentsSummary", {}).get("totalComments", 0)
                    shares = stats.get("sharesSummary", {}).get("totalShares", 0)

                    # Get impressions from separate endpoint
                    impressions = 0
                    try:
                        async with session.get(
                            f"{self.BASE_URL}/organizationalEntityShareStatistics",
                            headers=headers,
                            params={"q": "organizationalEntity", "shares": [post_id]}
                        ) as imp_response:
                            imp_response.raise_for_status()
                            imp_result = await imp_response.json()
                            if "elements" in imp_result and len(imp_result["elements"]) > 0:
                                impressions = imp_result["elements"][0].get(
                                    "totalShareStatistics", {}
                                ).get("impressionCount", 0)
                    except Exception as e:
                        logger.warning(f"Could not fetch impressions: {e}")

                    return {
                        "impressions": impressions,
                        "likes": likes,
                        "comments": comments,
                        "shares": shares,
                        "clicks": stats.get("clickCount", 0),
                        "engagement_count": likes + comments + shares,
                        "platform_metrics": {
                            "uniqueImpressionsCount": stats.get("uniqueImpressionsCount", 0),
                        }
                    }

        return await self.execute_with_retry(_fetch)

    async def delete_content(self, post_id: str) -> bool:
        """Delete LinkedIn post."""
        async def _delete():
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "X-Restli-Protocol-Version": "2.0.0"
                }

                async with session.delete(
                    f"{self.BASE_URL}/ugcPosts/{post_id}",
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    return True

        return await self.execute_with_retry(_delete)
