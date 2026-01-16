"""
Media asset management service.
"""
from typing import Dict, Any, Optional, BinaryIO
import hashlib
import os
from pathlib import Path
import logging
from PIL import Image
import subprocess
import aiofiles
import boto3
from botocore.exceptions import ClientError

from backend.app.core.config import settings
from backend.app.models.models import MediaAsset
from backend.app.db.session import SessionLocal

logger = logging.getLogger(__name__)


class MediaManager:
    """
    Manage media assets with S3 storage and integrity validation.

    Features:
    - SHA-256 integrity validation
    - S3 storage with CDN support
    - Thumbnail generation
    - Metadata extraction
    - Duplicate detection
    """

    def __init__(self):
        self.storage_path = Path("/tmp/media")  # Local temp storage
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize S3 client if configured
        self.s3_client = None
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )

    async def upload_media(
        self,
        file: BinaryIO,
        filename: str,
        content_type: str,
        alt_text: Optional[str] = None,
        tags: Optional[Dict[str, Any]] = None
    ) -> MediaAsset:
        """
        Upload media file with validation and metadata extraction.

        Args:
            file: File-like object
            filename: Original filename
            content_type: MIME type
            alt_text: Alternative text for accessibility
            tags: Optional metadata tags

        Returns:
            MediaAsset object
        """
        # Read file content
        content = await file.read()
        file_size = len(content)

        # Compute SHA-256 hash
        sha256_hash = hashlib.sha256(content).hexdigest()

        # Check for duplicate
        with SessionLocal() as db:
            from backend.app.crud.crud import crud_media_asset
            existing = crud_media_asset.get_by_hash(db, sha256_hash)

            if existing:
                logger.info(
                    f"Duplicate media detected: {filename} "
                    f"(matches asset {existing.id})"
                )
                return existing

        # Save to local storage temporarily
        local_path = self.storage_path / sha256_hash
        async with aiofiles.open(local_path, 'wb') as f:
            await f.write(content)

        # Extract metadata
        metadata = await self._extract_metadata(local_path, content_type)

        # Upload to S3 if configured
        storage_path = str(local_path)
        cdn_url = None
        thumbnail_url = None

        if self.s3_client and settings.AWS_S3_BUCKET:
            try:
                s3_key = f"media/{sha256_hash}/{filename}"
                storage_path = f"s3://{settings.AWS_S3_BUCKET}/{s3_key}"

                # Upload to S3
                self.s3_client.upload_file(
                    str(local_path),
                    settings.AWS_S3_BUCKET,
                    s3_key,
                    ExtraArgs={'ContentType': content_type}
                )

                # Generate CDN URL
                cdn_url = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"

                # Generate and upload thumbnail for images
                if content_type.startswith("image/"):
                    thumbnail_path = await self._generate_thumbnail(local_path)
                    if thumbnail_path:
                        thumb_key = f"media/{sha256_hash}/thumb_{filename}"
                        self.s3_client.upload_file(
                            str(thumbnail_path),
                            settings.AWS_S3_BUCKET,
                            thumb_key,
                            ExtraArgs={'ContentType': content_type}
                        )
                        thumbnail_url = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{thumb_key}"

                logger.info(f"Uploaded media to S3: {cdn_url}")

            except ClientError as e:
                logger.error(f"S3 upload failed: {e}")
                # Fall back to local storage

        # Create MediaAsset record
        with SessionLocal() as db:
            from backend.app.crud.crud import crud_media_asset

            media_asset = crud_media_asset.create(db, {
                "filename": filename,
                "file_type": content_type,
                "file_size": file_size,
                "storage_path": storage_path,
                "cdn_url": cdn_url,
                "thumbnail_url": thumbnail_url,
                "sha256_hash": sha256_hash,
                "width": metadata.get("width"),
                "height": metadata.get("height"),
                "duration": metadata.get("duration"),
                "alt_text": alt_text,
                "tags": tags
            })

            logger.info(f"Created media asset {media_asset.id}")
            return media_asset

    async def _extract_metadata(
        self,
        file_path: Path,
        content_type: str
    ) -> Dict[str, Any]:
        """
        Extract metadata from media file.

        Args:
            file_path: Path to file
            content_type: MIME type

        Returns:
            Dict with width, height, duration, etc.
        """
        metadata = {}

        try:
            if content_type.startswith("image/"):
                # Extract image dimensions
                with Image.open(file_path) as img:
                    metadata["width"] = img.width
                    metadata["height"] = img.height

            elif content_type.startswith("video/"):
                # Extract video metadata using ffprobe
                try:
                    result = subprocess.run(
                        [
                            "ffprobe",
                            "-v", "error",
                            "-select_streams", "v:0",
                            "-show_entries", "stream=width,height,duration",
                            "-of", "json",
                            str(file_path)
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )

                    if result.returncode == 0:
                        import json
                        data = json.loads(result.stdout)
                        if "streams" in data and len(data["streams"]) > 0:
                            stream = data["streams"][0]
                            metadata["width"] = stream.get("width")
                            metadata["height"] = stream.get("height")
                            metadata["duration"] = int(
                                float(stream.get("duration", 0))
                            )

                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    logger.warning(f"ffprobe failed: {e}")

        except Exception as e:
            logger.error(f"Metadata extraction failed: {e}")

        return metadata

    async def _generate_thumbnail(
        self,
        file_path: Path,
        size: tuple = (300, 300)
    ) -> Optional[Path]:
        """
        Generate thumbnail for image.

        Args:
            file_path: Path to original image
            size: Thumbnail size (width, height)

        Returns:
            Path to thumbnail or None
        """
        try:
            thumb_path = file_path.parent / f"thumb_{file_path.name}"

            with Image.open(file_path) as img:
                img.thumbnail(size, Image.Resampling.LANCZOS)
                img.save(thumb_path)

            return thumb_path

        except Exception as e:
            logger.error(f"Thumbnail generation failed: {e}")
            return None

    async def delete_media(self, media_asset: MediaAsset) -> bool:
        """
        Delete media asset and associated files.

        Args:
            media_asset: MediaAsset object

        Returns:
            True if successful
        """
        try:
            # Delete from S3 if applicable
            if media_asset.storage_path.startswith("s3://") and self.s3_client:
                # Parse S3 path
                path_parts = media_asset.storage_path.replace("s3://", "").split("/", 1)
                bucket = path_parts[0]
                key = path_parts[1]

                self.s3_client.delete_object(Bucket=bucket, Key=key)

                # Delete thumbnail if exists
                if media_asset.thumbnail_url:
                    thumb_key = f"media/{media_asset.sha256_hash}/thumb_{media_asset.filename}"
                    self.s3_client.delete_object(Bucket=bucket, Key=thumb_key)

            # Delete from local storage
            local_path = Path(media_asset.storage_path)
            if local_path.exists():
                local_path.unlink()

            # Delete database record
            with SessionLocal() as db:
                from backend.app.crud.crud import crud_media_asset
                crud_media_asset.delete(db, media_asset.id)

            logger.info(f"Deleted media asset {media_asset.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete media asset {media_asset.id}: {e}")
            return False

    def get_media_url(self, media_asset: MediaAsset) -> str:
        """
        Get accessible URL for media asset.

        Args:
            media_asset: MediaAsset object

        Returns:
            URL string
        """
        if media_asset.cdn_url:
            return media_asset.cdn_url

        # Generate presigned URL for S3 if needed
        if media_asset.storage_path.startswith("s3://") and self.s3_client:
            path_parts = media_asset.storage_path.replace("s3://", "").split("/", 1)
            bucket = path_parts[0]
            key = path_parts[1]

            try:
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket, 'Key': key},
                    ExpiresIn=3600  # 1 hour
                )
                return url
            except ClientError as e:
                logger.error(f"Failed to generate presigned URL: {e}")

        return media_asset.storage_path


# Global instance
media_manager = MediaManager()
