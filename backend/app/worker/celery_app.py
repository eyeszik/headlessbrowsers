"""
Celery application with scheduled tasks.
"""
from celery import Celery
from celery.schedules import crontab
from datetime import datetime, timedelta
import logging

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "content_automation",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Scheduled tasks configuration
celery_app.conf.beat_schedule = {
    # Process scheduled posts every minute
    "process-scheduled-posts": {
        "task": "backend.app.worker.tasks.process_scheduled_posts",
        "schedule": 60.0,  # Every 60 seconds
    },
    # Fetch analytics every hour
    "fetch-analytics-batch": {
        "task": "backend.app.worker.tasks.fetch_analytics_batch",
        "schedule": crontab(minute=0),  # Every hour
    },
    # Cleanup old data daily at 2 AM
    "cleanup-old-data": {
        "task": "backend.app.worker.tasks.cleanup_old_data",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    # Backup database daily at 3 AM
    "backup-database": {
        "task": "backend.app.worker.tasks.backup_database",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
    },
}
