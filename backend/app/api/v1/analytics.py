"""Analytics endpoints."""
from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.app.db.session import get_session
from backend.app.services.analytics_service import analytics_aggregator

router = APIRouter()


@router.get("/top-performing")
def get_top_performing(
    metric: str = "engagement_rate",
    limit: int = 10,
    platform: str = None,
    days: int = 30,
    db: Session = Depends(get_session)
):
    """Get top performing content."""
    from backend.app.models.models import PlatformType

    platform_type = None
    if platform:
        try:
            platform_type = PlatformType(platform)
        except ValueError:
            pass

    return analytics_aggregator.get_top_performing_content(
        db, metric, limit, platform_type, days
    )


@router.post("/collect")
async def collect_analytics(
    hours_back: int = 24,
    db: Session = Depends(get_session)
):
    """Trigger analytics collection for recent content."""
    result = await analytics_aggregator.schedule_analytics_collection(
        db, hours_back
    )
    return result
