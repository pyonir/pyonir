from __future__ import annotations

import os
from starlette.datastructures import UploadFile
from pyonir.models.page import BaseMedia


class MediaManager:
    """Manage audio, video, and image documents."""

    def __init__(self, app: 'BaseApp'):
        self.app = app

    @property
    def directory_name(self):
        """Default directory name where uploads are saved"""
        return getattr(self.app.settings, 'upload_directory_name', None) or "media_manager"

    @property
    def storage(self):
        """Location on fs to save file uploads"""
        return self.app.uploads_dirpath

    def get_media(self, media_id: str) -> BaseMedia:
        """Retrieve an audio file by ID."""
        m = BaseMedia(os.path.join(self.storage, media_id))
        pass

    def delete_media(self, media_id: str) -> bool:
        """Delete an audio file by ID. Returns True if deleted."""
        pass

    # --- General Uploading ---
    async def upload_bytes(self, file: UploadFile, directory_name: str = None) -> str:
        """
        Save an uploaded video file to disk and return its filename.
        or upload a video to Cloudflare R2 and return the object key.
        """
        from uuid import uuid4
        filename = file.filename
        object_key = f"videos/{uuid4()}-{filename}"
        path = os.path.join(self.storage, directory_name or self.directory_name, object_key)
        with open(path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                buffer.write(chunk)

        return object_key
