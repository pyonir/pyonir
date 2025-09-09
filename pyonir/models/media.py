from __future__ import annotations

import os
from typing import Optional, Union
from starlette.datastructures import UploadFile

from pyonir.core import PyonirRequest
from pyonir.models.database import BaseFSQuery
from pyonir.models.page import BaseFile

from enum import Enum, unique

@unique
class AudioFormat(Enum):
    MP3  = "mp3"
    WAV  = "wav"
    FLAC = "flac"
    AAC  = "aac"
    OGG  = "ogg"
    M4A  = "m4a"

    def __str__(self):
        return self.value

@unique
class VideoFormat(Enum):
    MP4  = "mp4"
    MKV  = "mkv"
    AVI  = "avi"
    MOV  = "mov"
    WEBM = "webm"
    FLV  = "flv"

    def __str__(self):
        return self.value

@unique
class ImageFormat(Enum):
    JPG   = "jpg"
    JPEG  = "jpeg"
    PNG   = "png"
    GIF   = "gif"
    BMP   = "bmp"
    TIFF  = "tiff"
    WEBP  = "webp"
    SVG   = "svg"

    def __str__(self):
        return self.value

class BaseMedia(BaseFile):
    """Represents an image file and its details."""

    def __init__(self, path: str = None):
        super().__init__(path)
        filename_meta = self.decode_filename(self.file_name)
        self.data = filename_meta or self.get_media_data(self.file_path)
        self.has_encoded_filename = bool(filename_meta)
        pass

    @property
    def file_name(self):
        name, ext = os.path.splitext(os.path.basename(self.file_path))
        self.file_ext = ext
        return name

    @property
    def file_dirpath(self):
        return os.path.dirname(self.file_path)

    @property
    def file_dirname(self):
        return os.path.basename(os.path.dirname(self.file_path))

    @property
    def slug(self):
        return f"{self.file_dirname}/{self.file_name}{self.file_ext}"

    def rename_media_file(self) -> None:
        """Renames media file as b64 encoded value"""
        encoded_filename = self.encode_filename(self.file_path, self.data)
        new_filepath = self.file_path.replace(self.file_name+self.file_ext, encoded_filename)
        os.rename(self.file_path, new_filepath)
        self.file_path = new_filepath

    def open_image(self):
        from PIL import Image
        raw_img = Image.open(self.file_path)
        return raw_img

    def resize(self, sizes=None):
        '''
        Resize each image and save to the upload path in corresponding image size and paths
        This happens after full size images are saved to the filesystem
        '''
        from PIL import Image
        from pyonir import Site
        from pathlib import Path
        raw_img = self.open_image()
        if sizes is None:
            sizes = [Site.THUMBNAIL_DEFAULT]
        try:
            for dimensions in sizes:
                width, height = dimensions
                # self._sizes.append(dimensions)
                img = raw_img.resize((width, height), Image.Resampling.BICUBIC)
                file_name = f'{self.file_name}--{width}x{height}'
                img_dirpath = os.path.dirname(self.file_path)
                Path(img_dirpath).mkdir(parents=True, exist_ok=True)
                filepath = os.path.join(img_dirpath, Site.UPLOADS_THUMBNAIL_DIRNAME, file_name + '.' + self.file_ext)
                if not os.path.exists(filepath): img.save(filepath)
        except Exception as e:
            raise

    @staticmethod
    def decode_filename(encoded_filename: str) -> Optional[dict]:
        """ Reverse of encode_filename. """
        from urllib.parse import parse_qs
        import base64

        try:
            # restore padding
            padding = "=" * (-len(encoded_filename) % 4)
            encoded_filename = encoded_filename.replace("_", ".") + padding
            raw = base64.urlsafe_b64decode(encoded_filename.encode()).decode()
            parsed = parse_qs(raw)
            return parsed
        except Exception as e:
            return None

    @staticmethod
    def encode_filename(file_path: str, meta_data: dict = None) -> str:
        """
        Build filename as url encoded string, then Base64 encode (URL-safe, no '.' in output).
        """
        from urllib.parse import urlencode
        from datetime import datetime
        import base64

        file_name, file_ext = os.path.splitext(os.path.basename(file_path))
        created_date = int(datetime.now().timestamp())
        raw = urlencode(meta_data) if meta_data else f'name={file_name}&ext={file_ext}&created_date={created_date}'
        # URL-safe base64 (no + or /), strip padding '='
        b64 = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
        return b64+file_ext

    @staticmethod
    async def save_upload(file, img_folder_abspath) -> str:
        """Saves base64 file contents into file system"""
        from pathlib import Path
        file_name, file_ext = os.path.splitext(file.filename)
        new_dir_path = Path(img_folder_abspath)
        new_dir_path.mkdir(parents=True, exist_ok=True)
        new_file_path = os.path.join(img_folder_abspath, file_name + file_ext)
        file_contents = await file.read()
        if not file_contents: return ''
        with open(str(new_file_path), 'wb') as f:
            f.write(file_contents)
        return new_file_path

    @staticmethod
    def get_media_data(media_file_path: str):
        from pymediainfo import MediaInfo
        media_info = MediaInfo.parse(media_file_path)
        media_track_file = media_info.tracks.pop(0)
        created_on = media_track_file.file_creation_date
        for track in media_info.tracks:
            if track.track_type == "Image":
                return {
                    "name": media_track_file.file_name,
                    "created_on": created_on,
                    "width": track.width,
                    "height": track.height,
                }
            if track.track_type == "Audio":
                dur = track.duration / 1000 if track.duration else None # ms → seconds
                return {
                    "codec": track.codec,
                    "duration": dur,
                    "bit_rate": track.bit_rate,
                    "channels": track.channel_s,
                    "sampling_rate": track.sampling_rate,
                }
            if track.track_type == "Video":
                return {
                    "codec": track.codec,
                    "duration": track.duration / 1000 if track.duration else None,  # ms → seconds
                    "width": track.width,
                    "height": track.height,
                    "frame_rate": track.frame_rate,
                    "bit_rate": track.bit_rate,
                }


class MediaManager:
    """Manage audio, video, and image documents."""
    default_media_dirname = 'media'

    def __init__(self, app: 'BaseApp'):
        self.app = app
        self.supported_formats = {ImageFormat.JPG, ImageFormat.PNG, VideoFormat.MP4, AudioFormat.MP3}
        self._storage_dirpath: str = os.path.join(app.contents_dirpath, self.default_media_dirname)
        """Location on fs to save file uploads"""

    @property
    def storage_dirpath(self) -> str: return self._storage_dirpath

    def is_supported(self, ext: str) -> bool:
        """Check if the media file has a supported format."""
        ext = ext.lstrip('.').lower()
        return ext in {fmt.value for fmt in self.supported_formats}

    def add_supported_format(self, fmt: Union[ImageFormat, AudioFormat, VideoFormat, None]):
        """Add a supported media format."""
        self.supported_formats.add(fmt)

    @staticmethod
    def media_type(ext: str) -> Optional[str]:
        """Return the media type based on file extension."""
        ext = ext.lstrip('.').lower()

        if ext in (f.value for f in AudioFormat):
            return "audio"
        elif ext in (f.value for f in VideoFormat):
            return "video"
        elif ext in (f.value for f in ImageFormat):
            return "image"
        return None

    def set_storage_dirpath(self, storage_dirpath):
        self._storage_dirpath = storage_dirpath
        return self

    def close(self):
        """Closes any open connections by resetting storage path"""
        self._storage_dirpath = os.path.join(self.app.contents_dirpath, self.default_media_dirname)

    def get_media(self, file_id: str) -> BaseMedia:
        """Retrieves user paginated media files"""
        mpath = os.path.join(self.storage_dirpath, file_id)
        mfile = BaseMedia(mpath)
        return mfile

    def get_medias(self, file_type: str) -> list[BaseMedia]:
        """Retrieves user paginated media files"""
        files = BaseFSQuery(self.storage_dirpath, model=BaseMedia, force_all=True)
        return list(files)

    def delete_media(self, media_id: str) -> bool:
        """Delete file by ID. Returns True if deleted."""
        from pathlib import Path
        path = os.path.join(self.storage_dirpath, media_id)
        if not Path(path).exists(): return False
        Path(path).unlink()
        return True

    # --- General Uploading ---
    async def upload(self, request: PyonirRequest, directory_name: str = None, file_name: str = None, limit: int = None) -> \
            list[BaseMedia]:
        """Uploads a resource into specified directory
        :param request: PyonirRequest instance
        :param directory_name: directory name
        :param file_name: strict file name for resource
        :param limit: maximum number of files to upload
        """
        resource_files = []
        for file in request.files:
            if limit and len(resource_files) == limit: break
            if file_name:
                file._filename = file_name
            directory_name = directory_name or self.media_type(file.ext)
            media_file: BaseMedia = await self._upload_bytes(file, directory_name=directory_name or self.default_media_dirname)
            if media_file:
                resource_files.append(media_file)
        return resource_files

    async def _upload_bytes(self, file: UploadFile, directory_name: str = None, meta_data: dict = None) -> Optional[BaseMedia]:
        """
        Save an uploaded video file to disk and return its filename.
        or upload a video to Cloudflare R2 and return the object key.
        """
        from pathlib import Path
        filename = file.filename
        _strict_name = getattr(file, '_filename', None)
        if not filename: return None
        resource_id = [f"{directory_name.strip()}", f"{_strict_name.strip() if _strict_name else filename}"]
        path = os.path.join(self.storage_dirpath, *resource_id)
        Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                buffer.write(chunk)
        file_media = BaseMedia(path=path)
        return file_media



