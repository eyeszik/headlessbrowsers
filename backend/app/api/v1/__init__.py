"""
API v1 routes.
"""
from fastapi import APIRouter
from backend.app.api.v1 import (
    content,
    campaigns,
    social_accounts,
    templates,
    analytics,
    media,
    stock_images,
)

api_router = APIRouter()

api_router.include_router(
    content.router,
    prefix="/content",
    tags=["content"]
)

api_router.include_router(
    campaigns.router,
    prefix="/campaigns",
    tags=["campaigns"]
)

api_router.include_router(
    social_accounts.router,
    prefix="/social-accounts",
    tags=["social-accounts"]
)

api_router.include_router(
    templates.router,
    prefix="/templates",
    tags=["templates"]
)

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["analytics"]
)

api_router.include_router(
    media.router,
    prefix="/media",
    tags=["media"]
)

api_router.include_router(
    stock_images.router,
    prefix="/stock-images",
    tags=["stock-images"]
)
