from __future__ import annotations

import os, re
from dataclasses import dataclass
from typing import Optional, Union, Generator
from starlette.datastructures import UploadFile

from pyonir import PyonirRequest
from pyonir.core.database import BaseFSQuery

from enum import Enum, unique
import base64
from io import BytesIO
from PIL import Image

ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB limit

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

    def __contains__(self, item):
        """Allow checks like `'png' in ImageFormat` or `ImageFormat.PNG in ImageFormat`."""
        if isinstance(item, ImageFormat):
            return True
        if isinstance(item, str):
            v = item.lower()
            return any(v == member.value or v == member.name.lower() for member in ImageFormat)
        return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a file name by removing spaces, extra dots, and unsafe characters.
    Keeps the file extension if present.

    Example:
        cmd: sanitize_filename("my file.name.txt")

        output: 'my_filename.txt'
    """
    # Split into name and extension
    name, ext = os.path.splitext(filename)

    # Replace spaces with underscores
    name = name.replace(" ", "_")

    # Remove dots and any characters not alphanumeric, underscore, or hyphen
    name = re.sub(r"[^A-Za-z0-9_-]", "", name)

    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name).strip("_")

    return f"{name}{ext}"

def rotate_image_from_exif(image):
    from PIL import ExifTags
    try:
        # image = Image.open(image_path)
        # Get EXIF data
        exif = image.getexif()

        # Find the Orientation tag
        orientation_tag = None
        for tag_id, tag_name in ExifTags.TAGS.items():
            if tag_name == 'Orientation':
                orientation_tag = tag_id
                break

        if orientation_tag in exif:
            orientation = exif[orientation_tag]
            # Rotate the image based on EXIF orientation
            if orientation == 3:
                image = image.rotate(180, expand=True)
            elif orientation == 6:
                image = image.rotate(270, expand=True)
            elif orientation == 8:
                image = image.rotate(90, expand=True)

            # Remove the orientation tag to prevent double rotation by other viewers
            if orientation_tag in image.info:
                del image.info[orientation_tag]
            if "exif" in image.info:
                image.info["exif"] = None # Clear EXIF data related to orientation

        return image

    except Exception as e:
        print(f"Error processing image: {e}")
        return None


class BaseMedia:
    """Represents an image file and its details."""

    def __init__(self, path: str = None, app_ctx: 'AppCtx' = None):
        self._app_ctx = app_ctx
        self._thumbnails = {}
        self.file_path = path
        name, ext = os.path.splitext(os.path.basename(self.file_path))
        self.file_ext = ext
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

    @property
    def url(self):
        return f"/{self.slug}"

    @property
    def is_thumb(self) -> bool:
        """Check if the file is a thumbnail based on naming convention."""
        return self.file_name.startswith(os.path.basename(self.file_dirpath))

    @property
    def thumbnails(self) -> dict:
        """Returns a dictionary all thumbnails for the image with width x height as key and url as value"""
        if not self._thumbnails:
            thumbs = self._get_all_thumbnails()
            for thumb in thumbs or []:
                width = thumb.data.get('width')
                height = thumb.data.get('height')
                self._thumbnails[f"{width}x{height}"] = thumb.url
        return self._thumbnails

    def resized_to(self, width, height) -> str:
        """Generates an image accordion to width and height parameters and returns url to the new resized image"""
        if not self._thumbnails.get(f'{width}x{height}'):
            thumbs = self.resize([(width, height)])
            self._thumbnails.update(thumbs)
        return self._thumbnails.get(f'{width}x{height}')

    def _get_all_thumbnails(self) -> Optional[Generator]:
        """Collects thumbnails for the image"""
        if self.is_thumb: return None
        from pyonir import Site
        from pyonir.core.database import query_fs
        app_ctx = Site.app_ctx if Site else self._app_ctx
        thumbs_dir = os.path.join(self.file_dirpath, self.file_name)
        files = query_fs(str(thumbs_dir), model=BaseMedia, app_ctx=app_ctx)
        return files

    def compress(self, quality: int = 85) -> None:
        """Compress image file in place."""
        self.compress_image(self.file_path, self.file_path, quality=quality)

    def rename_media_file(self, file_name: str = None) -> None:
        """Renames media file as b64 encoded value"""
        encoded_filename = self.encode_filename(self.file_path, self.data) if not self.has_encoded_filename else None
        if not (file_name or encoded_filename): return
        new_filepath = self.file_path.replace(self.file_name+self.file_ext, file_name or encoded_filename)
        os.rename(self.file_path, new_filepath)
        self.has_encoded_filename = new_filepath.endswith(os.path.basename(self.file_path))
        self.file_path = new_filepath

    def resize(self, sizes: list[tuple] = None) -> dict:
        """
        Resize each image and save to the upload path in corresponding image size and paths
        This happens after full size images are saved to the filesystem
        :param sizes: list of (width, height) tuples
        """
        from PIL import Image
        from pyonir import Site
        from pathlib import Path

        raw_img = Image.open(self.file_path)
        thumb_dirname = Site.UPLOADS_THUMBNAIL_DIRNAME if Site else self.file_name
        sizes = [Site.THUMBNAIL_DEFAULT] if not sizes and Site else sizes
        base_dirpath = os.path.dirname(self.file_path)
        resized = {}
        if sizes is None:
            raise ValueError("Sizes must be provided if Site is not configured.")
        try:
            for dimensions in sizes:
                width, height = dimensions
                # self._sizes.append(dimensions)
                img = raw_img.resize((width, height), Image.Resampling.BICUBIC)
                file_name = f'{self.file_name}--{width}x{height}'
                img_dirpath = os.path.join(base_dirpath, thumb_dirname)
                Path(img_dirpath).mkdir(parents=True, exist_ok=True)
                filepath = os.path.join(img_dirpath, file_name + self.file_ext)
                if not os.path.exists(filepath):
                    img.save(filepath)
                    resized[f'{width}x{height}'] = BaseMedia(filepath)
            return resized
        except Exception as e:
            raise

    @staticmethod
    def decode_filename(encoded_filename: str) -> Optional[dict]:
        """ Reverse of encode_filename. """
        from pyonir.core.utils import parse_url_params
        import base64

        try:
            # restore padding
            padding = "=" * (-len(encoded_filename) % 4)
            encoded_filename = encoded_filename.replace("_", ".") + padding
            raw = base64.urlsafe_b64decode(encoded_filename.encode()).decode()
            parsed = parse_url_params(raw)
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
        raw = urlencode(meta_data) if meta_data else f'name={file_name}&ext={file_ext}&created_on={created_date}'
        # URL-safe base64 (no + or /), strip padding '='
        b64 = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
        return b64+file_ext

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
                    "size": media_track_file.file_size,
                }
            if track.track_type == "Audio":
                dur = track.duration / 1000 if track.duration else None # ms → seconds
                return {
                    "codec": track.codec,
                    "duration": dur,
                    "bit_rate": track.bit_rate,
                    "channels": track.channel_s,
                    "sampling_rate": track.sampling_rate,
                    "size": media_track_file.file_size,
                }
            if track.track_type == "Video":
                return {
                    "codec": track.codec,
                    "duration": track.duration / 1000 if track.duration else None,  # ms → seconds
                    "width": track.width,
                    "height": track.height,
                    "frame_rate": track.frame_rate,
                    "bit_rate": track.bit_rate,
                    "size": media_track_file.file_size,
                }

    @staticmethod
    def compress_image(input_path: str, output_path: str, quality: int = 85) -> None:
        """
        Auto-detect format (JPEG, PNG, WebP) and apply compression.
        """

        from PIL import Image
        media_type = BaseMedia.media_type(os.path.splitext(input_path)[1])
        if media_type != "image":
            return
        img = Image.open(input_path)
        fmt = img.format.upper()  # e.g. "JPEG", "PNG", "WEBP"
        img = rotate_image_from_exif(img)

        if fmt in ("JPEG", "JPG"):
            # JPEG: lossy compression
            img.save(output_path, format="JPEG", quality=quality, optimize=True)

        elif fmt == "PNG":
            # PNG: lossless, but can optimize
            img.save(output_path, format="PNG", optimize=True)

        elif fmt == "WEBP":
            # WebP: supports both lossy/lossless
            img.save(output_path, format="WEBP", quality=quality, method=6)

        else:
            # Default fallback → save in original format
            img.save(output_path, format=fmt)

        print(f"Compressed {input_path} ({fmt}) → {output_path}")

    @staticmethod
    def media_type(ext: str) -> str:
        """Return the media type based on file extension."""
        ext = ext.lstrip('.').lower()

        if ext in (f.value for f in AudioFormat):
            return "audio"
        elif ext in (f.value for f in VideoFormat):
            return "video"
        elif ext in (f.value for f in ImageFormat):
            return "image"
        return "document"

@dataclass
class UploadOptions:
    """Options for uploading media files."""
    directory_name: str = ''
    """Directory name to save the uploaded file."""
    file_name: str = ''
    """Strict file name for the uploaded file."""
    limit: int = 0
    """Maximum number of files to upload."""
    as_series: bool = False
    """If true, appends an index to the file name for multiple uploads."""
    compress_quality: int = 55
    """Quality for image compression (1-100)."""
    dimensions: tuple = (256, 256)

class MediaManager:
    """Manage audio, video, and image documents."""
    default_media_dirname = 'media' # general directory name for all media types

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

    def delete_media_dir(self, dir_name: str) -> bool:
        """Delete all files in a directory. Returns True if deleted."""
        from pathlib import Path
        dir_path = os.path.join(self.storage_dirpath, dir_name)
        if not Path(dir_path).exists(): return False
        for file in Path(dir_path).glob("*"):
            if file.is_file():
                file.unlink()
        Path(dir_path).rmdir()
        return True

    def delete_media(self, media_id: str) -> bool:
        """Delete file by ID. Returns True if deleted."""
        from pathlib import Path
        path = os.path.join(self.storage_dirpath, media_id)
        if not Path(path).exists(): return False
        Path(path).unlink()
        return True

    # --- General Uploading ---
    async def upload(self, request: PyonirRequest, upload_options: UploadOptions = None) -> list[BaseMedia]:
        """Uploads a resource into specified directory
        :param upload_options: upload config options
        :param request: PyonirRequest instance
        """
        resource_files = []
        file_name = upload_options.file_name if upload_options else None
        limit = upload_options.limit if upload_options else None
        directory_name = upload_options.directory_name if upload_options else None
        as_series = upload_options.as_series if upload_options else False
        compress_quality = upload_options.compress_quality if upload_options else None
        for file in request.files:
            if not file.size: continue
            series_index = len(resource_files) + 1
            if limit and series_index > limit: break
            if file_name:
                file.filename = f"{file_name}_{series_index}" if as_series else file_name
            # directory_name = directory_name or BaseMedia.media_type(file.filename.split('.').pop())
            media_file: str = await self._upload_bytes(file, directory_name=directory_name)
            if media_file:
                file_media = BaseMedia(path=media_file)
                file_media.compress(quality=compress_quality)
                resource_files.append(file_media)
        return resource_files

    async def _upload_bytes(self, file: UploadFile, directory_name: str = None) -> Optional[str]:
        """
        Save an uploaded video file to disk and return its filename.
        or upload a video to Cloudflare R2 and return the object key.
        """
        from pathlib import Path
        filename = sanitize_filename(file.filename)
        if not filename: return None
        resource_id = [directory_name, filename] if directory_name else [filename]
        path = os.path.join(self.storage_dirpath, *resource_id)
        Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                buffer.write(chunk)
        return path

    def _save_base64(data_url: str, path: str):
        # 1. Validate prefix
        if not data_url.startswith("data:image/") or ";base64," not in data_url:
            raise ValueError("Invalid data URL")

        header, encoded = data_url.split(",", 1)

        # 2. Decode base64 safely
        try:
            raw = base64.b64decode(encoded, validate=True)
        except Exception:
            raise ValueError("Invalid base64 data")

        # 3. Enforce size limit
        if len(raw) > MAX_BYTES:
            raise ValueError("Image exceeds max allowed size")

        # 4. Load with Pillow (ensures it’s actually an image)
        try:
            img = Image.open(BytesIO(raw))
            img.verify()  # verifies integrity without decoding full image
        except Exception:
            raise ValueError("Decoded data is not a valid image")

        # 5. Check allowed formats
        if img.format not in ImageFormat:
            raise ValueError(f"Unsupported format: {img.format}")

        # 6. Reload (Pillow requires re-open after verify())
        img = Image.open(BytesIO(raw))

        # 7. Save to file safely
        img.save(path)

        return True

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


