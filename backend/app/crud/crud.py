"""
CRUD operations for all database models.
"""
from typing import List, Optional, Dict, Any, Type, TypeVar
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from datetime import datetime

from backend.app.models.models import (
    SocialAccount,
    MediaAsset,
    ContentTemplate,
    Campaign,
    Content,
    ContentVariant,
    ContentAnalytics,
    TaskState,
    AssumptionLog,
    ContentStatus,
    TaskStatus,
)

ModelType = TypeVar("ModelType")


class CRUDBase:
    """Base CRUD operations."""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: int) -> Optional[ModelType]:
        """Get a single record by ID."""
        return db.get(self.model, id)

    def get_multi(
        self, db: Session, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """Get multiple records with pagination."""
        statement = select(self.model).offset(skip).limit(limit)
        return db.exec(statement).all()

    def create(self, db: Session, obj_in: Dict[str, Any]) -> ModelType:
        """Create a new record."""
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self, db: Session, db_obj: ModelType, obj_in: Dict[str, Any]
    ) -> ModelType:
        """Update an existing record."""
        for field, value in obj_in.items():
            setattr(db_obj, field, value)
        if hasattr(db_obj, "updated_at"):
            db_obj.updated_at = datetime.utcnow()
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, id: int) -> Optional[ModelType]:
        """Delete a record."""
        obj = db.get(self.model, id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj


class CRUDSocialAccount(CRUDBase):
    """CRUD operations for SocialAccount."""

    def get_by_platform(
        self, db: Session, platform: str, account_id: str
    ) -> Optional[SocialAccount]:
        """Get account by platform and account_id."""
        statement = select(SocialAccount).where(
            SocialAccount.platform == platform,
            SocialAccount.account_id == account_id
        )
        return db.exec(statement).first()

    def get_active_accounts(
        self, db: Session, platform: Optional[str] = None
    ) -> List[SocialAccount]:
        """Get all active accounts, optionally filtered by platform."""
        statement = select(SocialAccount).where(SocialAccount.is_active == True)
        if platform:
            statement = statement.where(SocialAccount.platform == platform)
        return db.exec(statement).all()

    def update_last_used(self, db: Session, id: int) -> Optional[SocialAccount]:
        """Update the last_used_at timestamp."""
        account = self.get(db, id)
        if account:
            account.last_used_at = datetime.utcnow()
            db.add(account)
            db.commit()
            db.refresh(account)
        return account


class CRUDMediaAsset(CRUDBase):
    """CRUD operations for MediaAsset."""

    def get_by_hash(self, db: Session, sha256_hash: str) -> Optional[MediaAsset]:
        """Get media asset by SHA-256 hash."""
        statement = select(MediaAsset).where(MediaAsset.sha256_hash == sha256_hash)
        return db.exec(statement).first()

    def get_by_tags(self, db: Session, tags: List[str]) -> List[MediaAsset]:
        """Get media assets that have any of the specified tags."""
        # Note: JSON querying would be database-specific
        # This is a simplified version
        statement = select(MediaAsset)
        results = db.exec(statement).all()
        return [
            asset for asset in results
            if asset.tags and any(tag in asset.tags.get("tags", []) for tag in tags)
        ]


class CRUDContentTemplate(CRUDBase):
    """CRUD operations for ContentTemplate."""

    def get_by_name(self, db: Session, name: str) -> Optional[ContentTemplate]:
        """Get template by name."""
        statement = select(ContentTemplate).where(ContentTemplate.name == name)
        return db.exec(statement).first()

    def get_active(self, db: Session) -> List[ContentTemplate]:
        """Get all active templates."""
        statement = select(ContentTemplate).where(ContentTemplate.is_active == True)
        return db.exec(statement).all()

    def get_by_category(self, db: Session, category: str) -> List[ContentTemplate]:
        """Get templates by category."""
        statement = select(ContentTemplate).where(ContentTemplate.category == category)
        return db.exec(statement).all()

    def increment_usage(self, db: Session, id: int) -> Optional[ContentTemplate]:
        """Increment usage counter."""
        template = self.get(db, id)
        if template:
            template.times_used += 1
            template.last_used_at = datetime.utcnow()
            db.add(template)
            db.commit()
            db.refresh(template)
        return template


class CRUDCampaign(CRUDBase):
    """CRUD operations for Campaign."""

    def get_active(self, db: Session) -> List[Campaign]:
        """Get all active campaigns."""
        statement = select(Campaign).where(Campaign.is_active == True)
        return db.exec(statement).all()

    def get_by_date_range(
        self, db: Session, start_date: datetime, end_date: datetime
    ) -> List[Campaign]:
        """Get campaigns within a date range."""
        statement = select(Campaign).where(
            Campaign.start_date >= start_date,
            Campaign.end_date <= end_date
        )
        return db.exec(statement).all()

    def update_spent(self, db: Session, id: int, amount: float) -> Optional[Campaign]:
        """Update campaign spending."""
        campaign = self.get(db, id)
        if campaign:
            campaign.spent += amount
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
        return campaign


class CRUDContent(CRUDBase):
    """CRUD operations for Content."""

    def get_with_relationships(self, db: Session, id: int) -> Optional[Content]:
        """Get content with all relationships loaded."""
        statement = (
            select(Content)
            .where(Content.id == id)
            .options(
                selectinload(Content.social_account),
                selectinload(Content.campaign),
                selectinload(Content.variants),
                selectinload(Content.analytics),
            )
        )
        return db.exec(statement).first()

    def get_scheduled(
        self, db: Session, before: datetime
    ) -> List[Content]:
        """Get content scheduled before a certain time."""
        statement = select(Content).where(
            Content.status == ContentStatus.SCHEDULED,
            Content.scheduled_time <= before
        )
        return db.exec(statement).all()

    def get_by_status(
        self, db: Session, status: ContentStatus
    ) -> List[Content]:
        """Get content by status."""
        statement = select(Content).where(Content.status == status)
        return db.exec(statement).all()

    def get_by_campaign(
        self, db: Session, campaign_id: int
    ) -> List[Content]:
        """Get all content for a campaign."""
        statement = select(Content).where(Content.campaign_id == campaign_id)
        return db.exec(statement).all()

    def update_status(
        self, db: Session, id: int, status: ContentStatus, error: Optional[str] = None
    ) -> Optional[Content]:
        """Update content status."""
        content = self.get(db, id)
        if content:
            content.status = status
            content.updated_at = datetime.utcnow()
            if status == ContentStatus.PUBLISHED:
                content.published_at = datetime.utcnow()
            if error:
                content.last_error = error
            db.add(content)
            db.commit()
            db.refresh(content)
        return content

    def increment_retry(self, db: Session, id: int) -> Optional[Content]:
        """Increment retry counter."""
        content = self.get(db, id)
        if content:
            content.retry_count += 1
            db.add(content)
            db.commit()
            db.refresh(content)
        return content

    def get_dependencies_met(self, db: Session, content: Content) -> bool:
        """Check if all dependencies are met (all dependent content is published)."""
        if not content.depends_on:
            return True

        for dep_id in content.depends_on:
            dep = self.get(db, dep_id)
            if not dep or dep.status != ContentStatus.PUBLISHED:
                return False
        return True


class CRUDContentVariant(CRUDBase):
    """CRUD operations for ContentVariant."""

    def get_by_content(
        self, db: Session, content_id: int
    ) -> List[ContentVariant]:
        """Get all variants for a content piece."""
        statement = select(ContentVariant).where(
            ContentVariant.content_id == content_id
        )
        return db.exec(statement).all()

    def get_active_variants(
        self, db: Session, content_id: int
    ) -> List[ContentVariant]:
        """Get active variants for A/B testing."""
        statement = select(ContentVariant).where(
            ContentVariant.content_id == content_id,
            ContentVariant.is_active == True
        )
        return db.exec(statement).all()

    def update_performance(
        self, db: Session, id: int, impressions: int, engagement_rate: float
    ) -> Optional[ContentVariant]:
        """Update variant performance metrics."""
        variant = self.get(db, id)
        if variant:
            variant.impressions = impressions
            variant.engagement_rate = engagement_rate
            db.add(variant)
            db.commit()
            db.refresh(variant)
        return variant


class CRUDContentAnalytics(CRUDBase):
    """CRUD operations for ContentAnalytics."""

    def get_by_content(
        self, db: Session, content_id: int
    ) -> List[ContentAnalytics]:
        """Get all analytics for a content piece."""
        statement = select(ContentAnalytics).where(
            ContentAnalytics.content_id == content_id
        ).order_by(ContentAnalytics.collected_at.desc())
        return db.exec(statement).all()

    def get_by_platform_post(
        self, db: Session, platform_post_id: str
    ) -> Optional[ContentAnalytics]:
        """Get analytics by platform post ID."""
        statement = select(ContentAnalytics).where(
            ContentAnalytics.platform_post_id == platform_post_id
        )
        return db.exec(statement).first()

    def get_aggregated_by_campaign(
        self, db: Session, campaign_id: int
    ) -> Dict[str, Any]:
        """Get aggregated analytics for a campaign."""
        # Get all content for the campaign
        content_list = crud_content.get_by_campaign(db, campaign_id)
        content_ids = [c.id for c in content_list]

        if not content_ids:
            return {}

        # Get all analytics
        statement = select(ContentAnalytics).where(
            ContentAnalytics.content_id.in_(content_ids)
        )
        analytics = db.exec(statement).all()

        # Aggregate
        total = {
            "impressions": sum(a.impressions for a in analytics),
            "reach": sum(a.reach for a in analytics),
            "engagement_count": sum(a.engagement_count for a in analytics),
            "likes": sum(a.likes for a in analytics),
            "comments": sum(a.comments for a in analytics),
            "shares": sum(a.shares for a in analytics),
            "saves": sum(a.saves for a in analytics),
            "clicks": sum(a.clicks for a in analytics),
        }

        # Calculate average engagement rate
        if analytics:
            total["avg_engagement_rate"] = sum(
                a.engagement_rate for a in analytics
            ) / len(analytics)
        else:
            total["avg_engagement_rate"] = 0.0

        return total


class CRUDTaskState(CRUDBase):
    """CRUD operations for TaskState."""

    def get_by_task_id(self, db: Session, task_id: str) -> Optional[TaskState]:
        """Get task state by task_id."""
        statement = select(TaskState).where(TaskState.task_id == task_id)
        return db.exec(statement).first()

    def get_by_dag(self, db: Session, dag_id: str) -> List[TaskState]:
        """Get all tasks in a DAG."""
        statement = select(TaskState).where(TaskState.dag_id == dag_id)
        return db.exec(statement).all()

    def get_by_status(
        self, db: Session, status: TaskStatus
    ) -> List[TaskState]:
        """Get tasks by status."""
        statement = select(TaskState).where(TaskState.status == status)
        return db.exec(statement).all()

    def update_status(
        self,
        db: Session,
        task_id: str,
        status: TaskStatus,
        error: Optional[str] = None
    ) -> Optional[TaskState]:
        """Update task status."""
        task = self.get_by_task_id(db, task_id)
        if task:
            task.status = status
            task.updated_at = datetime.utcnow()

            if status == TaskStatus.RUNNING:
                task.started_at = datetime.utcnow()
            elif status in [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.ROLLED_BACK]:
                task.completed_at = datetime.utcnow()
                if task.started_at:
                    task.duration_seconds = (
                        task.completed_at - task.started_at
                    ).total_seconds()

            if error:
                task.error_message = error

            db.add(task)
            db.commit()
            db.refresh(task)
        return task


class CRUDAssumptionLog(CRUDBase):
    """CRUD operations for AssumptionLog."""

    def get_by_content(
        self, db: Session, content_id: int
    ) -> List[AssumptionLog]:
        """Get all assumption logs for a content piece."""
        statement = select(AssumptionLog).where(
            AssumptionLog.content_id == content_id
        )
        return db.exec(statement).all()

    def get_hallucinations(self, db: Session) -> List[AssumptionLog]:
        """Get all detected hallucinations."""
        statement = select(AssumptionLog).where(
            AssumptionLog.hallucination_detected == True
        )
        return db.exec(statement).all()

    def get_low_confidence(
        self, db: Session, threshold: float = 0.5
    ) -> List[AssumptionLog]:
        """Get assumptions with confidence below threshold."""
        statement = select(AssumptionLog).where(
            AssumptionLog.confidence_level < threshold
        )
        return db.exec(statement).all()


# Create CRUD instances
crud_social_account = CRUDSocialAccount(SocialAccount)
crud_media_asset = CRUDMediaAsset(MediaAsset)
crud_content_template = CRUDContentTemplate(ContentTemplate)
crud_campaign = CRUDCampaign(Campaign)
crud_content = CRUDContent(Content)
crud_content_variant = CRUDContentVariant(ContentVariant)
crud_content_analytics = CRUDContentAnalytics(ContentAnalytics)
crud_task_state = CRUDTaskState(TaskState)
crud_assumption_log = CRUDAssumptionLog(AssumptionLog)
