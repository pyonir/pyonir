import os, re, base64
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union, Iterable, TypeVar, Generic
from io import BytesIO

from pyonir import CollectionQuery, PyonirRequest
from pyonir.pyonir_types import BaseEnum
from PIL import Image
from PIL.ImageFile import ImageFile
from starlette.datastructures import UploadFile

MAX_BYTES = 5 * 1024 * 1024  # 5 MB limit

class DocumentType(BaseEnum):
    PDF = "pdf"
    TEXT = "txt"
    RICH_TEXT = "rtf"
    MARKDOWN = "md"
    WORD = "doc"
    WORD_OPENXML = "docx"
    EXCEL = "xls"
    EXCEL_OPENXML = "xlsx"
    OPEN_DOCUMENT_SPREADSHEET = "ods"
    POWERPOINT = "ppt"
    POWERPOINT_OPENXML = "pptx"
    OPEN_DOCUMENT_PRESENTATION = "odp"
    OPEN_DOCUMENT_TEXT = "odt"
    CSV = "csv"
    TSV = "tsv"
    JSON = "json"
    XML = "xml"
    YAML = "yaml"
    TOML = "toml"
    HTML = "html"
    CSS = "css"
    JAVASCRIPT = "js"
    PYTHON = "py"
    ZIP = "zip"

class AudioFormat(BaseEnum):
    MP3 = "mp3"
    WAV = "wav"
    FLAC = "flac"
    AAC = "aac"
    OGG = "ogg"
    M4A = "m4a"

class VideoFormat(BaseEnum):
    MP4 = "mp4"
    MKV = "mkv"
    AVI = "avi"
    MOV = "mov"
    WEBM = "webm"
    FLV = "flv"
    GIF = "gif"

class ImageFormat(BaseEnum):
    JPG = "jpg"
    JPEG = "jpeg"
    PNG = "png"
    BMP = "bmp"
    TIFF = "tiff"
    WEBP = "webp"
    SVG = "svg"


@dataclass
class ImageMetadata:
    name: str
    width: int
    height: int
    size: int
    created_on: datetime


@dataclass
class VideoMetadata:
    width: int
    height: int
    duration: float | None
    codec: str | None


@dataclass
class AudioMetadata:
    duration: float | None
    codec: str | None
    channels: int | None


class MediaType(str):
    IMAGE = 'image'
    AUDIO = 'audio'
    VIDEO = 'video'
    TEXT = 'text'
    DOCUMENT = 'document'

@dataclass
class Media:
    file_path: Path
    id: str = None
    content_type: str = None
    size: int = None
    _metadata: ImageMetadata | AudioMetadata | VideoMetadata | None = None

    @property
    def metadata(self) -> ImageMetadata | AudioMetadata | VideoMetadata:
        if not self.metadata:
            self._metadata = inspect_media(self.file_path)
        return self._metadata

    @property
    def file_name(self) -> str:
        """File name with extension from file path"""
        return self.file_path.name

    @property
    def extension(self) -> str:
        return Path(self.file_path).suffix.lower().lstrip(".")

    @property
    def media_type(self) -> str:
        ext = self.extension
        if ext in (f.value for f in AudioFormat):
            return MediaType.AUDIO
        elif ext in (f.value for f in VideoFormat):
            return MediaType.VIDEO
        elif ext in (f.value for f in ImageFormat):
            return MediaType.IMAGE
        return MediaType.DOCUMENT

    def compress(self, quality: int = 85, output_path: str = None) -> None:
        """
        Auto-detect format (JPEG, PNG, WebP) and apply compression.
        """
        from PIL import Image

        if self.media_type != MediaType.IMAGE:
            return
        if not output_path: output_path = self.file_path
        img = Image.open(self.file_path)
        fmt = img.format.upper()
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

T = TypeVar("T", bound=Media)

@dataclass
class MediaUploadOptions(Generic[T]):
    directory: str | None = None
    max_files: int = 0
    series_filename: str | None = None
    compress: bool = False
    compress_quality: int = 85
    resize: tuple[int, int] | None = None
    model: T = None

class MediaService:

    default_media_dirname = "media"  # general directory name for all media types

    def __init__(self, supported_formats: dict = None):
        self.supported_formats = supported_formats or {
            ImageFormat.JPG,
            ImageFormat.PNG,
            VideoFormat.MP4,
            AudioFormat.MP3,
        }
        self._storage_dirpath: str = os.path.join(
            self.pyonir_app.contents_dirpath, self.default_media_dirname
        )
        """Location on fs to save file uploads"""

    @property
    def pyonir_app(self):
        from pyonir import Site
        return Site

    @property
    def storage_dirpath(self) -> Path:
        return Path(self._storage_dirpath)

    def is_supported(self, ext: str) -> bool:
        """Check if the media file has a supported format."""
        ext = ext.lstrip(".").lower()
        return ext in {fmt.value for fmt in self.supported_formats}

    def add_supported_format(
        self, fmt: Union[ImageFormat, AudioFormat, VideoFormat, None]
    ):
        """Add a supported media format."""
        self.supported_formats.add(fmt)

    def set_storage_dirpath(self, storage_dirpath):
        self._storage_dirpath = storage_dirpath
        return self

    def close(self):
        """Closes any open connections by resetting storage path"""
        self._storage_dirpath = os.path.join(
            self.app.contents_dirpath, self.default_media_dirname
        )

    def get_media(self, file_id: str) -> Media:
        """Retrieves user paginated media files"""
        mpath = self.storage_dirpath / file_id
        mfile = Media(file_path=mpath)
        return mfile

    def get_medias(self, file_type: str) -> list[Media]:
        """Retrieves user paginated media files"""
        files = CollectionQuery(self.storage_dirpath, model=Media, force_all=True)
        return list(files)

    def delete_media_dir(self, dir_name: str) -> bool:
        """Delete all files in a directory. Returns True if deleted."""
        from pathlib import Path

        dir_path = os.path.join(self.storage_dirpath, dir_name)
        if not Path(dir_path).exists():
            return False
        for file in Path(dir_path).glob("*"):
            if file.is_file():
                file.unlink()
        Path(dir_path).rmdir()
        return True

    def delete_media(self, media: Media) -> bool:
        """Deletes a media object on disk"""
        illegal_path = media.file_path.parent in self.storage_dirpath.parents
        if illegal_path or not media.file_path.exists():
            raise ValueError(f"Media path '{media.file_path}' does not exist or outside scope of project.")
        Path(media.file_path).unlink()
        return True

    # --- General Uploading ---
    async def upload_files(
        self,
            files: Iterable[UploadFile],
            b64_files: Iterable[str],
            upload_options: MediaUploadOptions = None
    ) -> list[T]:
        """Uploads a resource into specified directory
        :param b64_files: base64 strings
        :param files: Files from request
        :param upload_options: upload config options
        """
        resource_files: list[T] = []
        series_filename = upload_options.series_filename if upload_options else None
        limit = upload_options.max_files if upload_options else 0
        directory_path = upload_options.directory if upload_options else None
        compress_quality = upload_options.compress_quality if upload_options else None
        model = upload_options.model
        from_base64 = b64_files is not None
        targets = (files or b64_files)

        for file in targets:
            if from_base64:
                filename, file_str = file
                file = _normalize_base64_string(file_str, filename)
            if not file.size: continue
            series_index = len(resource_files) + 1
            if limit and series_index > limit: break
            if series_filename:
                ext = file.filename.split('.').pop()
                file.filename = f"{series_index}_{series_filename}.{ext}" if limit > 1 else f"{series_filename}.{ext}"
            file.filename = sanitize_filename(file.filename)

            dpath = os.path.join(directory_path or self.storage_dirpath)
            Path(dpath).mkdir(parents=True, exist_ok=True)
            output_path = Path(dpath) / file.filename
            media_file_path: Path = _save_img_file(file, output_path) if from_base64 else await self._upload_bytes(file, file_path=output_path)

            if media_file_path.exists():
                file_media = model.from_path(file_path=media_file_path) if model else Media(file_path=media_file_path)
                file_media.compress(quality=compress_quality)
                resource_files.append(file_media)

        return resource_files

    @staticmethod
    async def _upload_bytes(file: UploadFile, file_path: Path) -> Optional[Path]:
        """
        Save an uploaded video file to disk and return its filename.
        """
        import aiofiles
        async with aiofiles.open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                await buffer.write(chunk)
        return file_path


def _normalize_base64_string(data_url: str, filename: str = '') -> ImageFile:

    # 1. Validate prefix
    if not data_url.startswith("data:image/") or ";base64," not in data_url:
        raise ValueError("Invalid data URL")

    header, encoded = data_url.split(",", 1)

    # 2. Decode base64 safely
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception:
        raise ValueError("Invalid base64 data")

    # # 3. Enforce size limit
    # if len(raw) > MAX_BYTES:
    #     raise ValueError("Image exceeds max allowed size")
    try:
        img = Image.open(BytesIO(raw))
        img.verify()  # verifies integrity without decoding full image
    except Exception:
        raise ValueError("Decoded data is not a valid image")

    # 5. Check allowed formats
    if not ImageFormat.contains(img.format):
        raise ValueError(f"Unsupported format: {img.format}")

    # Reload (Pillow requires re-open after verify())
    res = Image.open(BytesIO(raw))
    if filename: res.filename = filename
    return res


def _save_img_file(file: ImageFile, output_path: Path) -> Path:
    file.save(output_path)
    return output_path


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
            if tag_name == "Orientation":
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
                image.info["exif"] = None  # Clear EXIF data related to orientation

        return image

    except Exception as e:
        print(f"Error processing image: {e}")
        return None


def inspect_media(media_file_path: Path) -> ImageMetadata | AudioMetadata | VideoMetadata:
    from pymediainfo import MediaInfo

    media_info = MediaInfo.parse(media_file_path)
    media_track_file = media_info.tracks.pop(0)
    created_on = media_track_file.file_creation_date
    for track in media_info.tracks:
        if track.track_type == "Image":
            return ImageMetadata(**{
                "name": media_track_file.file_name,
                "created_on": created_on,
                "width": track.width,
                "height": track.height,
                "size": media_track_file.file_size,
            })
        if track.track_type == "Audio":
            dur = track.duration / 1000 if track.duration else None  # ms → seconds
            return AudioMetadata(**{
                "codec": track.codec,
                "duration": dur,
                "bit_rate": track.bit_rate,
                "channels": track.channel_s,
                "sampling_rate": track.sampling_rate,
                "size": media_track_file.file_size,
            })
        if track.track_type == "Video":
            _duration =  track.duration / 1000 if track.duration else None # ms → seconds
            return VideoMetadata(**{
                "codec": track.codec,
                "duration":_duration,
                "width": track.width,
                "height": track.height,
                "frame_rate": track.frame_rate,
                "bit_rate": track.bit_rate,
                "size": media_track_file.file_size,
            })