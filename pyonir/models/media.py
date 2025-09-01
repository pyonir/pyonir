from __future__ import annotations

import os
from typing import Optional, Any, Coroutine

from starlette.datastructures import UploadFile

from pyonir.core import PyonirRequest
from pyonir.models.database import BaseCollection
from pyonir.models.page import BaseMedia


class MediaManager:
    """Manage audio, video, and image documents."""
    default_media_dirname = 'media'

    def __init__(self, app: 'BaseApp'):
        self.app = app
        self._storage_dirpath: str = os.path.join(app.contents_dirpath, self.default_media_dirname)
        """Location on fs to save file uploads"""

    @property
    def storage_dirpath(self) -> str: return self._storage_dirpath

    def set_storage_dirpath(self, storage_dirpath):
        self._storage_dirpath = storage_dirpath
        return self

    def close(self):
        self._storage_dirpath = os.path.join(self.app.contents_dirpath, self.default_media_dirname)

    def get_user_file(self, user_id: str, media_id: str) -> list[BaseMedia]:
        """Retrieves user paginated media files"""
        mpath = os.path.join(self.storage_dirpath, user_id)
        files = BaseCollection.query(mpath)
        pass

    def get_user_files(self, file_type: str) -> list[BaseMedia]:
        """Retrieves user paginated media files"""
        mpath = os.path.join(self.storage_dirpath, file_type)
        files = BaseCollection.query(mpath, model=BaseMedia, force_all=True)
        return list(files)

    def delete_media(self, media_id: str) -> bool:
        """Delete an audio file by ID. Returns True if deleted."""
        path = os.path.join(self.storage_dirpath, media_id)
        pass

    # --- General Uploading ---
    async def upload(self, request: PyonirRequest, directory_name: str = None, file_name: str = None, limit: int = None) -> tuple[list[str | None], list[Any]]:
        """Uploads a resource into specified directory
        :param request: PyonirRequest instance
        :param directory_name: directory name
        :param file_name: strict file name for resource
        :param limit: maximum number of files to upload
        """
        resource_file_ids = []
        file_names = []
        for file in request.files:
            if limit and len(resource_file_ids) == limit: break
            if file_name:
                file._filename = file_name
            resource_file_id = await self.upload_bytes(file, directory_name=directory_name or self.default_media_dirname)
            resource_file_ids.append(resource_file_id)
            file_names.append(file.filename)
        return resource_file_ids, file_names

    async def upload_bytes(self, file: UploadFile, directory_name: str = None, caption: str = None) -> Optional[str]:
        """
        Save an uploaded video file to disk and return its filename.
        or upload a video to Cloudflare R2 and return the object key.
        """
        from pathlib import Path
        import base64
        filename = file.filename
        _strict_name = getattr(file, '_filename', None)
        if not filename: return None
        resource_id = [f"{directory_name.strip()}", f"{_strict_name.strip() if _strict_name else BaseMedia.encode_filename(filename, caption=caption)}"]
        path = os.path.join(self.storage_dirpath, *resource_id)
        Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                buffer.write(chunk)

        return "/".join(resource_id)



