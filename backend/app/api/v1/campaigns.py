"""Campaign management endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from backend.app.db.session import get_session
from backend.app.models.models import Campaign
from backend.app.crud.crud import crud_campaign
from backend.app.services.analytics_service import analytics_aggregator

router = APIRouter()


@router.get("/", response_model=List[Campaign])
def list_campaigns(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_session)
):
    """List all campaigns."""
    return crud_campaign.get_multi(db, skip=skip, limit=limit)


@router.get("/{campaign_id}", response_model=Campaign)
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_session)
):
    """Get specific campaign."""
    campaign = crud_campaign.get(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("/", response_model=Campaign)
def create_campaign(
    campaign_data: dict,
    db: Session = Depends(get_session)
):
    """Create new campaign."""
    return crud_campaign.create(db, campaign_data)


@router.get("/{campaign_id}/analytics")
def get_campaign_analytics(
    campaign_id: int,
    db: Session = Depends(get_session)
):
    """Get aggregated analytics for campaign."""
    campaign = crud_campaign.get(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    analytics = analytics_aggregator.aggregate_campaign_analytics(db, campaign_id)
    return analytics
