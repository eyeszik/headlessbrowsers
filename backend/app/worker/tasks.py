"""
Celery background tasks.
"""
from celery import Task
from datetime import datetime, timedelta
import logging
import subprocess
import os

from backend.app.worker.celery_app import celery_app
from backend.app.db.session import SessionLocal
from backend.app.crud.crud import crud_content, crud_social_account
from backend.app.models.models import ContentStatus
from backend.app.services.analytics_service import analytics_aggregator
from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task that provides database session."""

    def __init__(self):
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()


@celery_app.task(base=DatabaseTask, name="backend.app.worker.tasks.process_scheduled_posts")
def process_scheduled_posts():
    """
    Process scheduled posts (runs every minute).

    Checks for content scheduled for publishing and triggers publication.
    """
    logger.info("Processing scheduled posts...")

    db = SessionLocal()
    try:
        # Get content scheduled before now
        now = datetime.utcnow()
        scheduled_content = crud_content.get_scheduled(db, before=now)

        logger.info(f"Found {len(scheduled_content)} scheduled posts")

        published_count = 0
        failed_count = 0

        for content in scheduled_content:
            try:
                # Get social account
                account = crud_social_account.get(db, content.social_account_id)
                if not account:
                    logger.error(f"Account {content.social_account_id} not found")
                    continue

                # Mark as publishing
                crud_content.update_status(
                    db, content.id, ContentStatus.PUBLISHING
                )

                # Trigger publishing task
                publish_single_content.delay(content.id)

                published_count += 1

            except Exception as e:
                logger.error(f"Failed to process content {content.id}: {e}")
                crud_content.update_status(
                    db, content.id, ContentStatus.FAILED, str(e)
                )
                failed_count += 1

        logger.info(
            f"Processed {published_count} posts, {failed_count} failed"
        )

        return {
            "processed": published_count,
            "failed": failed_count,
            "timestamp": datetime.utcnow().isoformat()
        }

    finally:
        db.close()


@celery_app.task(name="backend.app.worker.tasks.publish_single_content")
def publish_single_content(content_id: int):
    """
    Publish a single content piece.

    Args:
        content_id: Content ID to publish
    """
    from backend.app.services.integrations import (
        YouTubeIntegration,
        TwitterIntegration,
        FacebookIntegration,
        InstagramIntegration,
        LinkedInIntegration
    )

    db = SessionLocal()
    try:
        content = crud_content.get(db, content_id)
        if not content:
            raise ValueError(f"Content {content_id} not found")

        # Get social account
        account = crud_social_account.get(db, content.social_account_id)
        if not account:
            raise ValueError(f"Account {content.social_account_id} not found")

        # Get integration
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

        # Prepare content
        content_data = {
            "title": content.title,
            "text": content.body
        }

        # Publish (synchronous version)
        import asyncio
        result = asyncio.run(integration.publish_content(content_data))

        # Update content
        crud_content.update_status(
            db, content.id, ContentStatus.PUBLISHED
        )

        logger.info(f"Published content {content_id} to {content.platform.value}")

        return result

    except Exception as e:
        logger.error(f"Failed to publish content {content_id}: {e}")
        crud_content.update_status(
            db, content_id, ContentStatus.FAILED, str(e)
        )
        raise

    finally:
        db.close()


@celery_app.task(name="backend.app.worker.tasks.fetch_analytics_batch")
def fetch_analytics_batch():
    """
    Fetch analytics for recently published content (runs hourly).
    """
    logger.info("Fetching analytics batch...")

    db = SessionLocal()
    try:
        # Run analytics collection
        import asyncio
        result = asyncio.run(
            analytics_aggregator.schedule_analytics_collection(db, hours_back=24)
        )

        logger.info(
            f"Analytics collected: {result['analytics_collected']}/{result['total_content']}"
        )

        return result

    except Exception as e:
        logger.error(f"Analytics batch failed: {e}")
        raise

    finally:
        db.close()


@celery_app.task(name="backend.app.worker.tasks.cleanup_old_data")
def cleanup_old_data():
    """
    Clean up old data (runs daily at 2 AM).

    Removes:
    - Old analytics records (> 90 days)
    - Failed content (> 30 days)
    - Expired task states (> 7 days)
    """
    logger.info("Cleaning up old data...")

    db = SessionLocal()
    try:
        from sqlmodel import delete

        # Delete old analytics (> 90 days)
        cutoff_analytics = datetime.utcnow() - timedelta(days=90)
        from backend.app.models.models import ContentAnalytics

        stmt = delete(ContentAnalytics).where(
            ContentAnalytics.collected_at < cutoff_analytics
        )
        result_analytics = db.exec(stmt)

        # Delete old failed content (> 30 days)
        cutoff_failed = datetime.utcnow() - timedelta(days=30)
        from backend.app.models.models import Content

        stmt = delete(Content).where(
            Content.status == ContentStatus.FAILED,
            Content.updated_at < cutoff_failed
        )
        result_content = db.exec(stmt)

        # Delete old task states (> 7 days)
        cutoff_tasks = datetime.utcnow() - timedelta(days=7)
        from backend.app.models.models import TaskState

        stmt = delete(TaskState).where(
            TaskState.updated_at < cutoff_tasks
        )
        result_tasks = db.exec(stmt)

        db.commit()

        logger.info(
            f"Cleanup complete: {result_analytics.rowcount} analytics, "
            f"{result_content.rowcount} content, {result_tasks.rowcount} tasks"
        )

        return {
            "analytics_deleted": result_analytics.rowcount,
            "content_deleted": result_content.rowcount,
            "tasks_deleted": result_tasks.rowcount,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(name="backend.app.worker.tasks.backup_database")
def backup_database():
    """
    Backup database to S3 (runs daily at 3 AM).
    """
    logger.info("Starting database backup...")

    try:
        # Create backup using pg_dump
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = f"/tmp/backup_{timestamp}.sql"

        pg_dump_cmd = [
            "pg_dump",
            "-h", settings.POSTGRES_SERVER,
            "-U", settings.POSTGRES_USER,
            "-d", settings.POSTGRES_DB,
            "-f", backup_file
        ]

        # Set password via environment
        env = os.environ.copy()
        env["PGPASSWORD"] = settings.POSTGRES_PASSWORD

        result = subprocess.run(
            pg_dump_cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes
        )

        if result.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {result.stderr}")

        logger.info(f"Database dumped to {backup_file}")

        # Upload to S3 if configured
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_S3_BUCKET:
            import boto3

            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )

            s3_key = f"backups/database_{timestamp}.sql"

            s3_client.upload_file(
                backup_file,
                settings.AWS_S3_BUCKET,
                s3_key
            )

            logger.info(f"Backup uploaded to S3: {s3_key}")

            # Clean up local file
            os.remove(backup_file)

            return {
                "status": "success",
                "backup_location": f"s3://{settings.AWS_S3_BUCKET}/{s3_key}",
                "timestamp": timestamp
            }
        else:
            logger.warning("S3 not configured, backup remains local")
            return {
                "status": "success",
                "backup_location": backup_file,
                "timestamp": timestamp
            }

    except Exception as e:
        logger.error(f"Backup failed: {e}")
        raise
