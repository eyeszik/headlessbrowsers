"""
Content management endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session

from backend.app.db.session import get_session
from backend.app.models.models import Content, ContentStatus
from backend.app.crud.crud import crud_content
from backend.app.services.scheduler import dag_scheduler

router = APIRouter()


@router.get("/", response_model=List[Content])
def list_content(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_session)
):
    """List all content."""
    return crud_content.get_multi(db, skip=skip, limit=limit)


@router.get("/{content_id}", response_model=Content)
def get_content(
    content_id: int,
    db: Session = Depends(get_session)
):
    """Get specific content."""
    content = crud_content.get(db, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return content


@router.post("/", response_model=Content)
def create_content(
    content_data: dict,
    db: Session = Depends(get_session)
):
    """Create new content."""
    # Compute payload hash for integrity
    content = Content(**content_data)
    payload_hash = content.compute_payload_hash()
    content_data["payload_hash"] = payload_hash

    return crud_content.create(db, content_data)


@router.put("/{content_id}", response_model=Content)
def update_content(
    content_id: int,
    content_data: dict,
    db: Session = Depends(get_session)
):
    """Update existing content."""
    content = crud_content.get(db, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    return crud_content.update(db, content, content_data)


@router.delete("/{content_id}")
def delete_content(
    content_id: int,
    db: Session = Depends(get_session)
):
    """Delete content."""
    content = crud_content.delete(db, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    return {"message": "Content deleted successfully"}


@router.post("/{content_id}/schedule")
def schedule_content(
    content_id: int,
    scheduled_time: str,
    db: Session = Depends(get_session)
):
    """Schedule content for publishing."""
    from datetime import datetime

    content = crud_content.get(db, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Parse datetime
    try:
        scheduled_dt = datetime.fromisoformat(scheduled_time)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    # Update content
    crud_content.update(db, content, {
        "scheduled_time": scheduled_dt,
        "status": ContentStatus.SCHEDULED
    })

    return {"message": "Content scheduled successfully"}


@router.get("/scheduled/list", response_model=List[Content])
def list_scheduled_content(
    db: Session = Depends(get_session)
):
    """Get all scheduled content."""
    return crud_content.get_by_status(db, ContentStatus.SCHEDULED)


@router.post("/publish-batch")
async def publish_batch(
    content_ids: List[int],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session)
):
    """Publish multiple content pieces using DAG scheduling."""
    # Get all content
    content_list = [crud_content.get(db, cid) for cid in content_ids]
    content_list = [c for c in content_list if c is not None]

    if not content_list:
        raise HTTPException(status_code=404, detail="No content found")

    # Validate DAG
    validation = dag_scheduler.validate_dag(content_list)
    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid DAG: {validation['errors']}"
        )

    # Schedule execution in background
    background_tasks.add_task(
        execute_publishing_dag,
        content_list,
        f"batch_{content_ids[0]}"
    )

    return {
        "message": "Publishing scheduled",
        "task_count": len(content_list),
        "dag_levels": validation["max_depth"]
    }


async def execute_publishing_dag(content_list: List[Content], dag_id: str):
    """Execute publishing DAG (background task)."""
    from backend.app.services.integrations import (
        YouTubeIntegration,
        TwitterIntegration,
        FacebookIntegration,
        InstagramIntegration,
        LinkedInIntegration
    )

    async def publish_content(content: Content):
        """Publish single content piece."""
        # Get social account
        with SessionLocal() as db:
            from backend.app.crud.crud import crud_social_account
            account = crud_social_account.get(db, content.social_account_id)

            if not account:
                raise ValueError(f"Social account {content.social_account_id} not found")

            # Get appropriate integration
            integration_map = {
                "youtube": YouTubeIntegration,
                "twitter": TwitterIntegration,
                "facebook": FacebookIntegration,
                "instagram": InstagramIntegration,
                "linkedin": LinkedInIntegration,
            }

            integration_class = integration_map.get(content.platform.value)
            if not integration_class:
                raise ValueError(f"Unknown platform: {content.platform}")

            integration = integration_class(
                access_token=account.access_token,
                rate_limit_per_hour=account.rate_limit_per_hour
            )

            # Prepare content data
            content_data = {
                "title": content.title,
                "text": content.body
            }

            # Publish
            result = await integration.publish_content(content_data)

            # Store platform post ID
            crud_content.update(db, content, {
                "status": ContentStatus.PUBLISHED,
                "published_at": result.get("published_at")
            })

            return result

    # Execute DAG
    result = await dag_scheduler.execute_dag(
        content_list,
        dag_id,
        publish_content
    )

    return result


from backend.app.db.session import SessionLocal
