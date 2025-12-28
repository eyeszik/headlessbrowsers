"""
Multi-platform analytics aggregation service.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
from sqlmodel import Session

from backend.app.models.models import (
    Content,
    ContentAnalytics,
    Campaign,
    SocialAccount,
    PlatformType
)
from backend.app.crud.crud import crud_content_analytics
from backend.app.services.integrations import (
    YouTubeIntegration,
    TwitterIntegration,
    FacebookIntegration,
    InstagramIntegration,
    LinkedInIntegration
)

logger = logging.getLogger(__name__)


class AnalyticsAggregator:
    """
    Aggregate analytics from multiple social media platforms.

    Features:
    - Multi-platform data collection
    - KPI tracking and validation
    - Automated collection scheduling
    - Campaign-level aggregation
    """

    def __init__(self):
        self.platform_integrations = {
            PlatformType.YOUTUBE: YouTubeIntegration,
            PlatformType.TWITTER: TwitterIntegration,
            PlatformType.FACEBOOK: FacebookIntegration,
            PlatformType.INSTAGRAM: InstagramIntegration,
            PlatformType.LINKEDIN: LinkedInIntegration,
        }

    async def fetch_content_analytics(
        self,
        db: Session,
        content: Content,
        social_account: SocialAccount
    ) -> Optional[ContentAnalytics]:
        """
        Fetch analytics for a single content piece.

        Args:
            db: Database session
            content: Content object
            social_account: Social account used for publishing

        Returns:
            ContentAnalytics object or None if failed
        """
        try:
            # Get platform integration
            integration_class = self.platform_integrations.get(content.platform)
            if not integration_class:
                logger.error(f"No integration for platform {content.platform}")
                return None

            # Initialize integration
            integration = integration_class(
                access_token=social_account.access_token,
                rate_limit_per_hour=social_account.rate_limit_per_hour
            )

            # Get platform post ID from existing analytics or content metadata
            existing = crud_content_analytics.get_by_content(db, content.id)
            if existing and len(existing) > 0:
                platform_post_id = existing[0].platform_post_id
            else:
                # Would need to get this from content publishing result
                logger.warning(
                    f"No platform post ID found for content {content.id}"
                )
                return None

            # Fetch analytics from platform
            analytics_data = await integration.fetch_analytics(platform_post_id)

            # Create or update analytics record
            analytics = ContentAnalytics(
                content_id=content.id,
                social_account_id=social_account.id,
                platform_post_id=platform_post_id,
                impressions=analytics_data.get("impressions", 0),
                reach=analytics_data.get("reach", 0),
                engagement_count=analytics_data.get("engagement_count", 0),
                likes=analytics_data.get("likes", 0),
                comments=analytics_data.get("comments", 0),
                shares=analytics_data.get("shares", 0),
                saves=analytics_data.get("saves", 0),
                clicks=analytics_data.get("clicks", 0),
                platform_metrics=analytics_data.get("platform_metrics"),
                collected_at=datetime.utcnow()
            )

            # Calculate engagement rate
            if analytics.impressions > 0:
                analytics.engagement_rate = (
                    analytics.engagement_count / analytics.impressions
                ) * 100

            # Calculate click-through rate
            if analytics.impressions > 0 and analytics.clicks > 0:
                analytics.click_through_rate = (
                    analytics.clicks / analytics.impressions
                ) * 100

            # Validate against KPIs if campaign exists
            if content.campaign_id:
                analytics = self._validate_kpis(db, analytics, content.campaign_id)

            db.add(analytics)
            db.commit()
            db.refresh(analytics)

            logger.info(
                f"Fetched analytics for content {content.id}: "
                f"{analytics.impressions} impressions, "
                f"{analytics.engagement_rate:.2f}% engagement"
            )

            return analytics

        except Exception as e:
            logger.error(f"Failed to fetch analytics for content {content.id}: {e}")
            return None

    async def fetch_batch_analytics(
        self,
        db: Session,
        content_list: List[Content],
        social_accounts: Dict[int, SocialAccount]
    ) -> List[ContentAnalytics]:
        """
        Fetch analytics for multiple content pieces in batch.

        Args:
            db: Database session
            content_list: List of Content objects
            social_accounts: Dict mapping social_account_id to SocialAccount

        Returns:
            List of ContentAnalytics objects
        """
        results = []

        for content in content_list:
            social_account = social_accounts.get(content.social_account_id)
            if not social_account:
                logger.warning(
                    f"Social account {content.social_account_id} not found"
                )
                continue

            analytics = await self.fetch_content_analytics(
                db, content, social_account
            )
            if analytics:
                results.append(analytics)

        logger.info(
            f"Fetched analytics for {len(results)}/{len(content_list)} content pieces"
        )

        return results

    def _validate_kpis(
        self,
        db: Session,
        analytics: ContentAnalytics,
        campaign_id: int
    ) -> ContentAnalytics:
        """
        Validate analytics against campaign KPI targets.

        Args:
            db: Database session
            analytics: ContentAnalytics object
            campaign_id: Campaign ID

        Returns:
            Updated ContentAnalytics with KPI validation
        """
        from backend.app.crud.crud import crud_campaign

        campaign = crud_campaign.get(db, campaign_id)
        if not campaign:
            return analytics

        kpi_scores = {}
        meets_targets = True

        # Check impressions target
        if campaign.target_impressions:
            impressions_score = min(
                1.0,
                analytics.impressions / campaign.target_impressions
            )
            kpi_scores["impressions"] = impressions_score
            if impressions_score < 1.0:
                meets_targets = False

        # Check engagement rate target
        if campaign.target_engagement_rate:
            if analytics.engagement_rate >= campaign.target_engagement_rate:
                kpi_scores["engagement_rate"] = 1.0
            else:
                kpi_scores["engagement_rate"] = (
                    analytics.engagement_rate / campaign.target_engagement_rate
                )
                meets_targets = False

        analytics.meets_kpi_targets = meets_targets
        analytics.kpi_scores = kpi_scores

        return analytics

    def aggregate_campaign_analytics(
        self,
        db: Session,
        campaign_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Aggregate analytics for entire campaign.

        Args:
            db: Database session
            campaign_id: Campaign ID
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Dict with aggregated metrics
        """
        aggregated = crud_content_analytics.get_aggregated_by_campaign(
            db, campaign_id
        )

        # Add campaign info
        from backend.app.crud.crud import crud_campaign
        campaign = crud_campaign.get(db, campaign_id)

        if campaign:
            aggregated["campaign_name"] = campaign.name
            aggregated["campaign_start"] = campaign.start_date
            aggregated["campaign_end"] = campaign.end_date

            # Calculate KPI achievement
            kpi_achievement = {}

            if campaign.target_impressions:
                kpi_achievement["impressions"] = (
                    aggregated["impressions"] / campaign.target_impressions
                ) * 100

            if campaign.target_engagement_rate:
                kpi_achievement["engagement_rate"] = (
                    aggregated["avg_engagement_rate"] /
                    campaign.target_engagement_rate
                ) * 100

            aggregated["kpi_achievement"] = kpi_achievement

        return aggregated

    def get_top_performing_content(
        self,
        db: Session,
        metric: str = "engagement_rate",
        limit: int = 10,
        platform: Optional[PlatformType] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get top performing content by metric.

        Args:
            db: Database session
            metric: Metric to sort by
            limit: Number of results
            platform: Optional platform filter
            days: Number of days to look back

        Returns:
            List of content with analytics
        """
        from sqlmodel import select
        from sqlalchemy import desc

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Build query
        statement = (
            select(ContentAnalytics, Content)
            .join(Content)
            .where(ContentAnalytics.collected_at >= cutoff_date)
        )

        if platform:
            statement = statement.where(Content.platform == platform)

        # Sort by metric
        if metric == "engagement_rate":
            statement = statement.order_by(desc(ContentAnalytics.engagement_rate))
        elif metric == "impressions":
            statement = statement.order_by(desc(ContentAnalytics.impressions))
        elif metric == "engagement_count":
            statement = statement.order_by(desc(ContentAnalytics.engagement_count))

        statement = statement.limit(limit)

        results = db.exec(statement).all()

        # Format results
        top_content = []
        for analytics, content in results:
            top_content.append({
                "content_id": content.id,
                "title": content.title,
                "platform": content.platform.value,
                "published_at": content.published_at,
                "impressions": analytics.impressions,
                "engagement_rate": analytics.engagement_rate,
                "engagement_count": analytics.engagement_count,
                "likes": analytics.likes,
                "comments": analytics.comments,
                "shares": analytics.shares
            })

        return top_content

    async def schedule_analytics_collection(
        self,
        db: Session,
        hours_back: int = 24
    ) -> Dict[str, Any]:
        """
        Collect analytics for all recently published content.

        Args:
            db: Database session
            hours_back: How many hours back to collect analytics

        Returns:
            Collection summary
        """
        from backend.app.crud.crud import crud_content, crud_social_account
        from backend.app.models.models import ContentStatus

        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

        # Get recently published content
        from sqlmodel import select
        statement = select(Content).where(
            Content.status == ContentStatus.PUBLISHED,
            Content.published_at >= cutoff_time
        )

        content_list = db.exec(statement).all()

        # Get social accounts
        account_ids = {c.social_account_id for c in content_list}
        social_accounts = {
            acc.id: acc
            for acc in [
                crud_social_account.get(db, acc_id)
                for acc_id in account_ids
            ]
            if acc is not None
        }

        # Fetch analytics
        analytics_list = await self.fetch_batch_analytics(
            db, content_list, social_accounts
        )

        return {
            "total_content": len(content_list),
            "analytics_collected": len(analytics_list),
            "success_rate": len(analytics_list) / len(content_list)
            if content_list else 0,
            "timestamp": datetime.utcnow()
        }


# Global instance
analytics_aggregator = AnalyticsAggregator()
