"""
Notion Database Setup Script.

Creates a properly-structured Notion database for the stock image pipeline.
Run once before using the pipeline with Notion integration enabled.

Usage:
    python scripts/setup_notion_database.py --page-id <your_notion_page_id>

Prerequisites:
    1. Create a Notion integration at https://www.notion.so/my-integrations
    2. Copy the "Internal Integration Token" → NOTION_API_TOKEN in .env
    3. Share the target Notion page with your integration
    4. Get the page ID from the page URL:
         https://notion.so/My-Page-<PAGE_ID_HERE>?v=...
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Allow running from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def setup(page_id: str, db_name: str) -> None:
    from dotenv import load_dotenv
    load_dotenv()

    from backend.app.core.config import settings

    if not settings.NOTION_API_TOKEN:
        print("\n[ERROR] NOTION_API_TOKEN is not set in your .env file.")
        print("Steps:")
        print("  1. Visit https://www.notion.so/my-integrations")
        print("  2. Create a new integration and copy the token")
        print("  3. Add to .env: NOTION_API_TOKEN=secret_...")
        sys.exit(1)

    try:
        from backend.app.services.integrations.notion import NotionIntegration
    except ImportError as exc:
        print(f"\n[ERROR] {exc}")
        print("Run: pip install notion-client==2.2.1")
        sys.exit(1)

    notion = NotionIntegration(api_token=settings.NOTION_API_TOKEN)

    print(f"\nConnecting to Notion …")
    health = await notion.health_check()
    if health["status"] != "healthy":
        print(f"[ERROR] Notion connection failed: {health.get('error')}")
        sys.exit(1)
    print(f"  Connected as: {health.get('user', 'unknown')}")

    print(f"\nCreating database '{db_name}' under page {page_id} …")
    db_id = await notion.create_database(
        parent_page_id=page_id,
        db_name=db_name,
    )

    print(f"\n{'='*60}")
    print("Database created successfully!")
    print(f"{'='*60}")
    print(f"  Database ID: {db_id}")
    print()
    print("Add to your .env file:")
    print(f"  NOTION_DATABASE_ID={db_id}")
    print()
    print("The database includes these columns:")
    columns = [
        "Name", "Category", "Style", "Keywords", "Color Palette",
        "Resolution", "AI Generated", "Upload Status", "Target Platforms",
        "Generation Date", "Batch ID", "Confidence Score", "Description",
    ]
    for col in columns:
        print(f"  ✓ {col}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create Notion database for stock images")
    parser.add_argument(
        "--page-id",
        required=True,
        help="Notion page ID to create the database under",
    )
    parser.add_argument(
        "--name",
        default="Stock Images",
        help="Database display name (default: 'Stock Images')",
    )
    args = parser.parse_args()
    asyncio.run(setup(args.page_id, args.name))
