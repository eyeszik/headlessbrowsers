"""Media management endpoints."""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlmodel import Session

from backend.app.db.session import get_session
from backend.app.models.models import MediaAsset
from backend.app.services.media_manager import media_manager

router = APIRouter()


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
