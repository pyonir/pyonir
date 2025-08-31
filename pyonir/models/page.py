import base64
from datetime import datetime
import os, pytz
from pathlib import Path
from typing import Any

from pyonir.utilities import deserialize_datestr

IMG_FILENAME_DELIM = '::'  # delimits the file name and description

class PageStatus(str):
    UNKNOWN = 'unknown'
    """Read only by the system often used for temporary and unknown files"""

    PROTECTED = 'protected'
    """Requires authentication and authorization. can be READ and WRITE."""

    FORBIDDEN = 'forbidden'
    """System only access. READ ONLY"""

    PUBLIC = 'public'
    """Access external and internal with READ and WRITE."""


class BasePage:
    """Represents a single page returned from a web request"""
    content: str = None
    template: str = None
    status: str = PageStatus.PUBLIC

    def __init__(self, path: str = None):
        self.file_path = str(path or __file__)
        name, ext = os.path.splitext(os.path.basename(self.file_path))
        self.file_name = name
        self.file_ext = ext[1:]
        self.file_dirpath = os.path.dirname(self.file_path)
        self.file_dirname = os.path.basename(os.path.dirname(self.file_path))
        relpath = os.path.relpath(self.file_path)


    @property
    def file_status(self) -> str:  # String
        return PageStatus.PROTECTED if self.file_name.startswith('_') else \
            PageStatus.FORBIDDEN if self.file_name.startswith('.') else PageStatus.PUBLIC

    @property
    def url(self): return f'/{self.slug}'

    @property
    def slug(self): return

    @property
    def canonical(self):
        from pyonir import Site
        return f"{Site.domain}{self.url}" if Site else self.url

    @property
    def created_on(self):  # Datetime
        return datetime.fromtimestamp(os.path.getctime(self.file_path), tz=pytz.UTC)

    @property
    def modified_on(self):  # Datetime
        return datetime.fromtimestamp(os.path.getmtime(self.file_path), tz=pytz.UTC)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__


class BaseMedia(BasePage):
    """Represents an image file and its file captions.
    Caption are extracted from the file name {name}|{caption}--{width}x{height}.{ext}"""

    def __init__(self, path: str = None):
        super().__init__(path)
        self.width = None
        self.height = None
        self.thumbnails = dict()
        self.meta = self.decode_filename(self.file_name)
        self.open_image()
        pass

    @property
    def slug(self):
        return f"{self.file_dirname}/{self.file_name}.{self.file_ext}"

    def open_image(self, file_path: str = None):
        """Opens selected image into memory to retrieve dimensions"""
        from PIL import Image
        from pyonir.utilities import get_attr
        try:
            raw_img = Image.open(file_path or self.file_path)
        except Exception as ie:
            raw_img = None
            print(f"Unable to open {self.file_path}: {ie}")
        self.width = get_attr(raw_img, "width", None)
        self.height = get_attr(raw_img, "height", None)
        return raw_img

    @staticmethod
    async def save_upload(file, img_folder_abspath) -> str:
        """Saves base64 file contents into file system"""
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
    def get_image_dimensions(file_path: str):
        """Opens selected image into memory to retrieve dimensions"""
        from PIL import Image
        from pyonir.utilities import get_attr
        try:
            raw_img = Image.open(file_path)
        except Exception as ie:
            raw_img = None
            print(f"Unable to open {file_path}: {ie}")
        width = get_attr(raw_img, "width", None)
        height = get_attr(raw_img, "height", None)
        return width, height

    @staticmethod
    def get_media_dimensions(media_file_path: str):
        from pymediainfo import MediaInfo
        media_info = MediaInfo.parse(media_file_path)
        for track in media_info.tracks:
            if track.track_type == "Image":
                return {
                    "format": track.format,
                    "width": track.width,
                    "height": track.height,
                    "bit_depth": getattr(track, "bit_depth", None),
                    "compression_mode": getattr(track, "compression_mode", None),
                    "color_space": getattr(track, "color_space", None),
                }
            if track.track_type == "Audio":
                return {
                    "codec": track.codec,
                    "duration": track.duration / 1000 if track.duration else None,  # ms → seconds
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

    @staticmethod
    def encode_filename(name: str, caption: str = ' ') -> str:
        """
        Build filename as {name}::{caption}::{created_date},
        then Base64 encode (URL-safe, no '.' in output).
        """
        name, ext = os.path.splitext(name)
        created_date = int(datetime.now().timestamp())
        raw = f"{name}{IMG_FILENAME_DELIM}{caption}{IMG_FILENAME_DELIM}{created_date}"

        # URL-safe base64 (no + or /), strip padding '='
        b64 = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")

        return b64+ext

    @staticmethod
    def decode_filename(encoded: str):
        """
        Reverse of encode_filename.
        """
        import re
        # restore padding
        padding = "=" * (-len(encoded) % 4)
        encoded = encoded.replace("_", ".") + padding
        raw = base64.urlsafe_b64decode(encoded.encode()).decode()

        # split into parts
        name_caption, ext = os.path.splitext(raw)
        parts = name_caption.split(IMG_FILENAME_DELIM)
        if len(parts) != 3:
            raise ValueError(f"Invalid encoded filename: {raw}")

        name, caption, created_date = parts
        display_name = re.sub(r'[^a-zA-Z0-9]+', ' ', name).title() # initial cap name
        return {
            "name": name,
            "display_name": display_name,
            "caption": caption,
            "created_date": deserialize_datestr(datetime.fromtimestamp(int(created_date))),
        }