"""
Notion API integration for stock image organization.

Uploads images, creates database entries, attaches metadata files.
Uses Notion API v2 via the official notion-client SDK.
"""
from typing import Dict, Any, Optional, List
import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# notion-client is optional — fail gracefully if not installed
try:
    from notion_client import AsyncClient as NotionAsyncClient
    from notion_client.errors import APIResponseError
    NOTION_AVAILABLE = True
except ImportError:
    NOTION_AVAILABLE = False
    logger.warning("notion-client not installed. Run: pip install notion-client==2.2.1")


class NotionIntegration:
    """
    Notion workspace integration for stock image pipeline.

    Responsibilities:
    - Create / retrieve the target database
    - Upload image entries with all metadata properties
    - Attach metadata .txt files as page content blocks
    - Query and update upload status per entry

    Rate limit: Notion enforces 3 requests/second per integration token.
    This class uses a simple asyncio.sleep throttle to stay compliant.
    """

    # Notion enforces 3 req/s; sleep between bulk operations
    _REQUEST_INTERVAL = 0.4  # seconds (2.5 req/s — safely under limit)

    def __init__(self, api_token: str, database_id: Optional[str] = None):
        if not NOTION_AVAILABLE:
            raise RuntimeError(
                "notion-client is required. Install with: pip install notion-client==2.2.1"
            )
        self.client = NotionAsyncClient(auth=api_token)
        self.database_id = database_id
        self._last_request_at: float = 0.0

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _throttle(self):
        """Enforce Notion rate limit (3 req/s)."""
        import time
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._REQUEST_INTERVAL:
            await asyncio.sleep(self._REQUEST_INTERVAL - elapsed)
        self._last_request_at = time.monotonic()

    def _text_prop(self, value: str) -> Dict[str, Any]:
        return {"rich_text": [{"text": {"content": value[:2000]}}]}

    def _title_prop(self, value: str) -> Dict[str, Any]:
        return {"title": [{"text": {"content": value[:255]}}]}

    def _select_prop(self, value: str) -> Dict[str, Any]:
        return {"select": {"name": value}}

    def _multi_select_prop(self, values: List[str]) -> Dict[str, Any]:
        return {"multi_select": [{"name": v[:100]} for v in values[:50]]}

    def _date_prop(self, dt: datetime) -> Dict[str, Any]:
        return {"date": {"start": dt.isoformat()}}

    def _checkbox_prop(self, value: bool) -> Dict[str, Any]:
        return {"checkbox": value}

    # ── Database management ───────────────────────────────────────────────────

    async def create_database(self, parent_page_id: str, db_name: str = "Stock Images") -> str:
        """
        Create a new Notion database for stock images.

        Args:
            parent_page_id: Notion page ID to nest the database under.
            db_name: Display name for the database.

        Returns:
            New database ID string.
        """
        await self._throttle()
        schema = {
            "Name":         {"title": {}},
            "Category":     {"select": {"options": [
                {"name": "Business", "color": "blue"},
                {"name": "Nature",   "color": "green"},
                {"name": "Lifestyle","color": "yellow"},
                {"name": "Abstract", "color": "purple"},
                {"name": "Technology","color": "gray"},
                {"name": "Food",     "color": "orange"},
                {"name": "Travel",   "color": "pink"},
                {"name": "Other",    "color": "default"},
            ]}},
            "Style":        {"select": {"options": [
                {"name": "Photorealistic", "color": "blue"},
                {"name": "Artistic",       "color": "purple"},
                {"name": "3D Render",      "color": "green"},
                {"name": "Illustration",   "color": "yellow"},
            ]}},
            "Keywords":     {"multi_select": {}},
            "Color Palette":{"multi_select": {"options": [
                {"name": "Warm",      "color": "orange"},
                {"name": "Cool",      "color": "blue"},
                {"name": "Vibrant",   "color": "red"},
                {"name": "Muted",     "color": "gray"},
                {"name": "Monochrome","color": "default"},
                {"name": "Dark",      "color": "default"},
                {"name": "Bright",    "color": "yellow"},
            ]}},
            "Resolution":   {"rich_text": {}},
            "AI Generated": {"checkbox": {}},
            "Upload Status":{"select": {"options": [
                {"name": "Pending",    "color": "gray"},
                {"name": "Uploaded",   "color": "green"},
                {"name": "Rejected",   "color": "red"},
                {"name": "Processing", "color": "yellow"},
            ]}},
            "Target Platforms": {"multi_select": {"options": [
                {"name": "Shutterstock", "color": "red"},
                {"name": "Adobe Stock",  "color": "orange"},
                {"name": "Getty Images", "color": "blue"},
                {"name": "iStock",       "color": "purple"},
            ]}},
            "Generation Date": {"date": {}},
            "Batch ID":     {"rich_text": {}},
            "Confidence Score": {"number": {"format": "percent"}},
            "Description":  {"rich_text": {}},
        }

        response = await self.client.databases.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            title=[{"type": "text", "text": {"content": db_name}}],
            properties=schema,
        )
        db_id = response["id"]
        self.database_id = db_id
        logger.info(f"Created Notion database '{db_name}' with ID: {db_id}")
        return db_id

    async def get_database(self) -> Dict[str, Any]:
        """Retrieve database metadata."""
        if not self.database_id:
            raise ValueError("database_id not set")
        await self._throttle()
        return await self.client.databases.retrieve(database_id=self.database_id)

    # ── Page / entry management ───────────────────────────────────────────────

    async def create_image_entry(
        self,
        title: str,
        description: str,
        keywords: List[str],
        category: str,
        style: str,
        color_palette: List[str],
        resolution: str,
        batch_id: str,
        confidence_score: float,
        generation_date: datetime,
        target_platforms: List[str],
        metadata_text: str,
        generation_prompt: str = "",
    ) -> str:
        """
        Create a Notion database page for one stock image.

        Args:
            title: SEO-optimized image title.
            description: Long-form image description.
            keywords: List of SEO keywords.
            category: Image category (Business, Nature, etc.).
            style: Visual style label.
            color_palette: Dominant color descriptors.
            resolution: e.g. "6000x4000".
            batch_id: UUID of the generation batch.
            confidence_score: AI metadata confidence (0–1).
            generation_date: When the image was generated.
            target_platforms: List of target stock platforms.
            metadata_text: Full metadata .txt content to embed as a code block.
            generation_prompt: Original prompt used to generate the image.

        Returns:
            Notion page ID of the created entry.
        """
        if not self.database_id:
            raise ValueError("database_id not set — call create_database() or pass database_id")

        await self._throttle()

        props = {
            "Name":             self._title_prop(title),
            "Description":      self._text_prop(description),
            "Keywords":         self._multi_select_prop(keywords),
            "Category":         self._select_prop(category),
            "Style":            self._select_prop(style),
            "Color Palette":    self._multi_select_prop(color_palette),
            "Resolution":       self._text_prop(resolution),
            "AI Generated":     self._checkbox_prop(True),
            "Upload Status":    self._select_prop("Pending"),
            "Target Platforms": self._multi_select_prop(target_platforms),
            "Generation Date":  self._date_prop(generation_date),
            "Batch ID":         self._text_prop(batch_id),
            "Confidence Score": {"number": round(confidence_score, 4)},
        }

        # Page body: metadata file as code block + generation prompt
        children = [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"text": {"content": "Metadata File"}}]
                },
            },
            {
                "object": "block",
                "type": "code",
                "code": {
                    "language": "plain text",
                    "rich_text": [{"text": {"content": metadata_text[:2000]}}],
                },
            },
        ]

        if generation_prompt:
            children += [
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": "Generation Prompt"}}]
                    },
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": generation_prompt[:2000]}}]
                    },
                },
            ]

        response = await self.client.pages.create(
            parent={"database_id": self.database_id},
            properties=props,
            children=children,
        )
        page_id = response["id"]
        logger.info(f"Created Notion page for '{title}': {page_id}")
        return page_id

    async def update_upload_status(self, page_id: str, status: str) -> None:
        """
        Update the Upload Status property on an existing page.

        Args:
            page_id: Notion page ID.
            status: One of Pending / Processing / Uploaded / Rejected.
        """
        await self._throttle()
        await self.client.pages.update(
            page_id=page_id,
            properties={"Upload Status": self._select_prop(status)},
        )
        logger.debug(f"Page {page_id} status → {status}")

    async def query_pending_entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return all database entries with Upload Status = Pending."""
        if not self.database_id:
            raise ValueError("database_id not set")
        await self._throttle()
        response = await self.client.databases.query(
            database_id=self.database_id,
            filter={
                "property": "Upload Status",
                "select": {"equals": "Pending"},
            },
            page_size=min(limit, 100),
        )
        return response.get("results", [])

    async def bulk_create_entries(
        self,
        entries: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Create multiple Notion pages sequentially with rate-limit throttling.

        Args:
            entries: List of kwargs dicts for create_image_entry().

        Returns:
            List of created page IDs.
        """
        page_ids: List[str] = []
        for entry in entries:
            try:
                page_id = await self.create_image_entry(**entry)
                page_ids.append(page_id)
            except Exception as exc:
                logger.error(f"Failed to create Notion entry for '{entry.get('title')}': {exc}")
                page_ids.append("")
        return page_ids

    async def health_check(self) -> Dict[str, Any]:
        """Verify Notion API token is valid and database is accessible."""
        try:
            await self._throttle()
            user = await self.client.users.me()
            result: Dict[str, Any] = {
                "status": "healthy",
                "user": user.get("name", "unknown"),
                "timestamp": datetime.utcnow().isoformat(),
            }
            if self.database_id:
                db = await self.get_database()
                result["database_title"] = (
                    db.get("title", [{}])[0].get("plain_text", "unknown")
                )
            return result
        except Exception as exc:
            return {
                "status": "unhealthy",
                "error": str(exc),
                "timestamp": datetime.utcnow().isoformat(),
            }
