"""
SQLModel database models with comprehensive schemas.
"""
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum
from sqlmodel import SQLModel, Field, Column, JSON, Relationship
from pydantic import validator
import hashlib


class PlatformType(str, Enum):
    """Supported social media platforms."""
    YOUTUBE = "youtube"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    LINKEDIN = "linkedin"


class ContentStatus(str, Enum):
    """Content lifecycle states."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    ARCHIVED = "archived"


class TaskStatus(str, Enum):
    """DAG task execution states."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    ROLLED_BACK = "rolled_back"


class SocialAccount(SQLModel, table=True):
    """Social media account credentials and configuration."""
    __tablename__ = "socialaccount"

    id: Optional[int] = Field(default=None, primary_key=True)
    platform: PlatformType = Field(index=True)
    account_name: str = Field(max_length=255)
    account_id: str = Field(max_length=255, index=True)

    # Encrypted credentials (store tokens, not raw passwords)
    access_token: str
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None

    # Configuration
    is_active: bool = Field(default=True)
    rate_limit_per_hour: int = Field(default=60)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None

    # Relationships
    content: List["Content"] = Relationship(back_populates="social_account")
    analytics: List["ContentAnalytics"] = Relationship(back_populates="social_account")

    class Config:
        arbitrary_types_allowed = True


class MediaAsset(SQLModel, table=True):
    """Media files (images, videos) for content."""
    __tablename__ = "mediaasset"

    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(max_length=255)
    file_type: str = Field(max_length=50)  # image/jpeg, video/mp4, etc.
    file_size: int  # bytes

    # Storage
    storage_path: str  # S3 path or local path
    cdn_url: Optional[str] = None
    thumbnail_url: Optional[str] = None

    # Integrity validation
    sha256_hash: str = Field(index=True)

    # Dimensions (for images/videos)
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None  # seconds, for videos

    # Metadata
    alt_text: Optional[str] = None
    tags: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    uploaded_by: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('sha256_hash')
    def validate_hash(cls, v):
        """Ensure hash is valid SHA-256."""
        if len(v) != 64:
            raise ValueError("Invalid SHA-256 hash length")
        return v.lower()


class ContentTemplate(SQLModel, table=True):
    """Reusable content templates with variable substitution."""
    __tablename__ = "contenttemplate"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, index=True)
    description: Optional[str] = None

    # Template content
    template_text: str  # Supports {{variable}} syntax
    variables: Dict[str, str] = Field(sa_column=Column(JSON))  # {var_name: description}

    # Platform-specific variants
    platform_overrides: Optional[Dict[str, str]] = Field(
        default=None,
        sa_column=Column(JSON)
    )  # {platform: template_text}

    # Default media
    default_media_ids: Optional[List[int]] = Field(
        default=None,
        sa_column=Column(JSON)
    )

    # Metadata
    category: Optional[str] = None
    tags: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    is_active: bool = Field(default=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Usage tracking
    times_used: int = Field(default=0)
    last_used_at: Optional[datetime] = None


class Campaign(SQLModel, table=True):
    """Marketing campaign grouping multiple content pieces."""
    __tablename__ = "campaign"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, index=True)
    description: Optional[str] = None

    # Timeline
    start_date: datetime
    end_date: Optional[datetime] = None

    # Configuration
    target_platforms: List[str] = Field(sa_column=Column(JSON))
    goals: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # KPI Targets
    target_impressions: Optional[int] = None
    target_engagement_rate: Optional[float] = None
    target_conversions: Optional[int] = None

    # Budget
    budget: Optional[float] = None
    spent: float = Field(default=0.0)

    # Status
    is_active: bool = Field(default=True)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None

    # Relationships
    content: List["Content"] = Relationship(back_populates="campaign")


class Content(SQLModel, table=True):
    """Main content entity for scheduling and publishing."""
    __tablename__ = "content"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=500)

    # Content
    body: str
    media_ids: Optional[List[int]] = Field(default=None, sa_column=Column(JSON))

    # Platform
    social_account_id: int = Field(foreign_key="socialaccount.id", index=True)
    platform: PlatformType

    # Campaign
    campaign_id: Optional[int] = Field(default=None, foreign_key="campaign.id", index=True)

    # Scheduling
    scheduled_time: Optional[datetime] = Field(index=True)
    published_at: Optional[datetime] = None

    # Status
    status: ContentStatus = Field(default=ContentStatus.DRAFT, index=True)

    # DAG Task Dependencies
    depends_on: Optional[List[int]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="List of content IDs that must be published first"
    )

    # Integrity and rollback
    payload_hash: Optional[str] = None  # SHA-256 of content for verification
    rollback_data: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON)
    )

    # Retry tracking
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    last_error: Optional[str] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None

    # Relationships
    social_account: SocialAccount = Relationship(back_populates="content")
    campaign: Optional[Campaign] = Relationship(back_populates="content")
    variants: List["ContentVariant"] = Relationship(back_populates="content")
    analytics: List["ContentAnalytics"] = Relationship(back_populates="content")

    def compute_payload_hash(self) -> str:
        """Compute SHA-256 hash of content payload for integrity validation."""
        payload = f"{self.title}|{self.body}|{self.media_ids or []}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def verify_payload_integrity(self) -> bool:
        """Verify content hasn't been tampered with."""
        if not self.payload_hash:
            return False
        return self.compute_payload_hash() == self.payload_hash


class ContentVariant(SQLModel, table=True):
    """Platform-specific content variations (A/B testing)."""
    __tablename__ = "contentvariant"

    id: Optional[int] = Field(default=None, primary_key=True)
    content_id: int = Field(foreign_key="content.id", index=True)

    variant_name: str = Field(max_length=100)  # e.g., "A", "B", "mobile_optimized"

    # Variant content
    title: str = Field(max_length=500)
    body: str
    media_ids: Optional[List[int]] = Field(default=None, sa_column=Column(JSON))

    # Platform-specific formatting
    platform_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Platform-specific fields (hashtags, mentions, etc.)"
    )

    # Testing
    is_active: bool = Field(default=True)
    weight: float = Field(default=0.5, description="Traffic split percentage")

    # Performance
    impressions: int = Field(default=0)
    engagement_rate: float = Field(default=0.0)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    content: Content = Relationship(back_populates="variants")


class ContentAnalytics(SQLModel, table=True):
    """Analytics data aggregated from social platforms."""
    __tablename__ = "contentanalytics"

    id: Optional[int] = Field(default=None, primary_key=True)
    content_id: int = Field(foreign_key="content.id", index=True)
    social_account_id: int = Field(foreign_key="socialaccount.id", index=True)

    # Platform post ID
    platform_post_id: str = Field(max_length=255, index=True)

    # Core metrics
    impressions: int = Field(default=0)
    reach: int = Field(default=0)
    engagement_count: int = Field(default=0)

    # Interaction metrics
    likes: int = Field(default=0)
    comments: int = Field(default=0)
    shares: int = Field(default=0)
    saves: int = Field(default=0)
    clicks: int = Field(default=0)

    # Derived metrics
    engagement_rate: float = Field(default=0.0)
    click_through_rate: float = Field(default=0.0)

    # Platform-specific metrics
    platform_metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Additional platform-specific metrics"
    )

    # KPI validation
    meets_kpi_targets: bool = Field(default=False)
    kpi_scores: Optional[Dict[str, float]] = Field(
        default=None,
        sa_column=Column(JSON)
    )

    # Timing
    collected_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    data_period_start: Optional[datetime] = None
    data_period_end: Optional[datetime] = None

    # Relationships
    content: Content = Relationship(back_populates="analytics")
    social_account: SocialAccount = Relationship(back_populates="analytics")

    def calculate_engagement_rate(self) -> float:
        """Calculate engagement rate."""
        if self.impressions == 0:
            return 0.0
        return (self.engagement_count / self.impressions) * 100


class TaskState(SQLModel, table=True):
    """DAG task execution state for orchestration and rollback."""
    __tablename__ = "taskstate"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: str = Field(max_length=255, unique=True, index=True)
    task_name: str = Field(max_length=255)

    # DAG information
    dag_id: str = Field(max_length=255, index=True)
    dependencies: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Task IDs this task depends on"
    )

    # Execution state
    status: TaskStatus = Field(default=TaskStatus.PENDING, index=True)

    # Retry management
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    next_retry_at: Optional[datetime] = None

    # Execution tracking
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Error handling
    error_message: Optional[str] = None
    error_boundary: bool = Field(
        default=True,
        description="Whether errors are isolated to this task"
    )

    # Rollback support
    rollback_data: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON)
    )
    rolled_back_at: Optional[datetime] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AssumptionLog(SQLModel, table=True):
    """Structured logging for AI-generated content assumptions."""
    __tablename__ = "assumptionlog"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Context
    content_id: Optional[int] = Field(default=None, foreign_key="content.id")
    ai_service: str = Field(max_length=50)  # "openai" or "anthropic"

    # Assumption details
    assumption_type: str = Field(
        max_length=100,
        description="Type of assumption made"
    )
    assumption_text: str = Field(description="What was assumed")

    # Confidence and validation
    confidence_level: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score 0-1"
    )
    validated: Optional[bool] = None
    validation_notes: Optional[str] = None

    # Guardrails
    hallucination_detected: bool = Field(default=False)
    guardrail_triggered: Optional[str] = None

    # Context data
    prompt_used: Optional[str] = None
    response_data: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON)
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
