"""
Base class for social media platform integrations.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import asyncio
import time
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter with token bucket algorithm."""

    def __init__(self, requests_per_hour: int = 60):
        self.requests_per_hour = requests_per_hour
        self.tokens = requests_per_hour
        self.last_update = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Acquire a token, waiting if necessary."""
        async with self.lock:
            now = time.time()
            time_passed = now - self.last_update
            self.tokens = min(
                self.requests_per_hour,
                self.tokens + time_passed * (self.requests_per_hour / 3600)
            )
            self.last_update = now

            if self.tokens < 1:
                sleep_time = (1 - self.tokens) * (3600 / self.requests_per_hour)
                await asyncio.sleep(sleep_time)
                self.tokens = 1

            self.tokens -= 1


class BasePlatformIntegration(ABC):
    """
    Abstract base class for social media platform integrations.

    Implements:
    - Rate limiting
    - Exponential backoff retry
    - Error handling
    - Payload integrity validation
    """

    def __init__(
        self,
        access_token: str,
        rate_limit_per_hour: int = 60,
        max_retries: int = 3
    ):
        self.access_token = access_token
        self.rate_limiter = RateLimiter(rate_limit_per_hour)
        self.max_retries = max_retries
        self.retry_delays = [2, 4, 8]  # Exponential backoff in seconds

    @abstractmethod
    async def publish_content(
        self,
        content: Dict[str, Any],
        media_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Publish content to the platform.

        Args:
            content: Content dictionary with platform-specific fields
            media_urls: List of media URLs to attach

        Returns:
            Dict with platform_post_id and other metadata
        """
        pass

    @abstractmethod
    async def fetch_analytics(
        self,
        post_id: str,
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch analytics for a published post.

        Args:
            post_id: Platform-specific post ID
            metrics: List of metrics to fetch

        Returns:
            Dict with analytics data
        """
        pass

    @abstractmethod
    async def delete_content(self, post_id: str) -> bool:
        """
        Delete published content (for rollback).

        Args:
            post_id: Platform-specific post ID

        Returns:
            True if successful
        """
        pass

    async def execute_with_retry(
        self,
        func,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a function with exponential backoff retry.

        Args:
            func: Async function to execute
            *args, **kwargs: Arguments to pass to function

        Returns:
            Result from function

        Raises:
            Exception: After max retries exceeded
        """
        await self.rate_limiter.acquire()

        last_exception = None
        for attempt in range(self.max_retries):
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {str(e)}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"All {self.max_retries} attempts failed. "
                        f"Last error: {str(e)}"
                    )

        raise last_exception

    def validate_payload_integrity(
        self,
        content: Dict[str, Any],
        expected_hash: str
    ) -> bool:
        """
        Validate payload integrity using SHA-256.

        Args:
            content: Content dictionary
            expected_hash: Expected SHA-256 hash

        Returns:
            True if hash matches
        """
        import hashlib
        import json

        # Create deterministic JSON representation
        payload = json.dumps(content, sort_keys=True)
        actual_hash = hashlib.sha256(payload.encode()).hexdigest()

        return actual_hash == expected_hash

    async def health_check(self) -> Dict[str, Any]:
        """
        Check if the integration is healthy.

        Returns:
            Dict with health status
        """
        try:
            # Override in subclasses with platform-specific check
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
