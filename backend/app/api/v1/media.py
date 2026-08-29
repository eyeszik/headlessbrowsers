"""Media management endpoints."""
import io
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from backend.app.db.session import get_session
from backend.app.models.models import MediaAsset, PlatformType
from backend.app.services.media_manager import media_manager

router = APIRouter()


class GenerateSocialImageRequest(BaseModel):
    prompt: str = Field(min_length=5, max_length=1000)
    platform: PlatformType
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=1000)
    keywords: List[str] = Field(default_factory=list)
    use_case: str = Field(default="draft", pattern="^(draft|published)$")
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class GenerateSocialImageResponse(BaseModel):
    success: bool
    media_asset_id: Optional[int] = None
    image_url: Optional[str] = None
    platform: str
    width: Optional[int] = None
    height: Optional[int] = None
    confidence_score: Optional[float] = None
    confidence_breakdown: Optional[dict] = None
    requires_review: Optional[bool] = None
    retry_count: Optional[int] = None
    integrity_verified: Optional[bool] = None
    governance_failures: Optional[dict] = None
    error: Optional[str] = None


@router.post("/upload", response_model=MediaAsset)
async def upload_media(
    file: UploadFile = File(...),
    alt_text: str = None,
    db: Session = Depends(get_session)
):
    """Upload media file."""
    media_asset = await media_manager.upload_media(
        file.file,
        file.filename,
        file.content_type,
        alt_text=alt_text
    )
    return media_asset


@router.post("/generate-social-image", response_model=GenerateSocialImageResponse)
async def generate_social_image(
    request: GenerateSocialImageRequest,
    db: Session = Depends(get_session),
):
    """
    Generate a platform-optimized image via DALL-E 3, run governance checks,
    persist it through MediaManager, and verify upload integrity.

    Sequence: governance checks -> DALL-E generation -> resize to platform
    dimensions -> S3 upload (via MediaManager, with SHA-256 dedup) ->
    post-upload integrity re-check.
    """
    from backend.app.services.governance import run_all_checks, all_passed, collect_failures
    from backend.app.services.ai.social_image_generator import (
        social_image_generator,
        SocialImageGenerationError,
    )

    # 1. Governance checks run before spending an API call.
    governance_results = run_all_checks(
        text_fields={
            "prompt": request.prompt,
            "title": request.title,
            "description": request.description,
            "keywords": " ".join(request.keywords),
        },
        ai_disclosure_present=True,  # this endpoint always discloses AI generation
    )
    if not all_passed(governance_results):
        failures = collect_failures(governance_results)
        raise HTTPException(
            status_code=403,
            detail={"error": "Governance check failed", "failures": failures},
        )

    # 2. Generate the image.
    try:
        result = await social_image_generator.generate(
            prompt=request.prompt,
            platform=request.platform,
            confidence_threshold=request.confidence_threshold,
            use_case=request.use_case,
        )
    except SocialImageGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 3. Persist via the existing media pipeline (handles S3 + dedup + DB row).
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in request.title)
    filename = f"{safe_title}_{request.platform.value}_{result.image_id[:8]}.png"

    media_asset = await media_manager.upload_media(
        io.BytesIO(result.image_bytes),
        filename,
        "image/png",
        alt_text=request.description or request.title,
        tags={
            "ai_generated": True,
            "platform": request.platform.value,
            "prompt": request.prompt,
            "keywords": request.keywords,
            "confidence_score": result.confidence_score,
        },
    )

    # 4. Verify the upload actually matches what we generated.
    integrity_ok = media_manager.verify_upload_integrity(media_asset)
    if not integrity_ok:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Upload integrity check failed for asset {media_asset.id}: "
                "downloaded hash did not match generated hash"
            ),
        )

    return GenerateSocialImageResponse(
        success=True,
        media_asset_id=media_asset.id,
        image_url=media_manager.get_media_url(media_asset),
        platform=request.platform.value,
        width=result.width,
        height=result.height,
        confidence_score=result.confidence_score,
        confidence_breakdown=result.confidence_breakdown,
        requires_review=result.requires_review,
        retry_count=result.retry_count,
        integrity_verified=integrity_ok,
    )


@router.get("/{media_id}/url")
def get_media_url(
    media_id: int,
    db: Session = Depends(get_session)
):
    """Get accessible URL for media."""
    from backend.app.crud.crud import crud_media_asset

    media_asset = crud_media_asset.get(db, media_id)
    if not media_asset:
        raise HTTPException(status_code=404, detail="Media not found")

    url = media_manager.get_media_url(media_asset)
    return {"url": url}
