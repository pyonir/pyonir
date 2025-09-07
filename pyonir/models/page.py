import base64
import re
from datetime import datetime
import os, pytz
from pathlib import Path
from typing import Any, Union, Optional

from pyonir.models.database import BasePagination
from pyonir.models.parser import DeserializeFile
from pyonir.utilities import get_attr

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


class BaseFile:
    """Represents a single file on file system"""

    def __init__(self, path: str = None, contents_dirpath: str = None):
        self.file_path = str(path or __file__)
        self.file_ext = os.path.splitext(self.file_path)[1]

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
    def file_status(self) -> str:  # String
        return PageStatus.PROTECTED if self.file_name.startswith('_') else \
            PageStatus.FORBIDDEN if self.file_name.startswith('.') else PageStatus.PUBLIC

    @property
    def created_on(self):  # Datetime
        return datetime.fromtimestamp(os.path.getctime(self.file_path), tz=pytz.UTC)

    @property
    def modified_on(self):  # Datetime
        return datetime.fromtimestamp(os.path.getmtime(self.file_path), tz=pytz.UTC)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__

# @dataclass
class BasePage:
    """Represents a single page returned from a web request"""
    _orm_options = {"mapper": {'created_on': 'file_created_on', 'modified_on': 'file_modified_on'}}
    url: str = ''
    slug: str = ''
    title: str = ''
    content: str = ''
    template: str = 'pages.html'
    created_on: datetime = None
    modified_on: datetime = None
    entries: BasePagination = None

    def __lt__(self, other) -> bool:
        """Compares two BasePage instances based on their created_on attribute."""
        if not isinstance(other, BasePage):
            return True
        return self.created_on < other.created_on

#
# class BaseMedia(BaseFile):
#     """Represents an image file and its details."""
#
#     def __init__(self, path: str = None):
#         super().__init__(path)
#         filename_meta = self.decode_filename(self.file_name)
#         self.data = filename_meta or self.get_media_data(self.file_path)
#         self.has_encoded_filename = bool(filename_meta)
#         pass
#
#     @property
#     def file_name(self):
#         name, ext = os.path.splitext(os.path.basename(self.file_path))
#         self.file_ext = ext
#         return name
#
#     @property
#     def file_dirpath(self):
#         return os.path.dirname(self.file_path)
#
#     @property
#     def file_dirname(self):
#         return os.path.basename(os.path.dirname(self.file_path))
#
#     @property
#     def file_status(self) -> str:  # String
#         return PageStatus.PROTECTED if self.file_name.startswith('_') else \
#             PageStatus.FORBIDDEN if self.file_name.startswith('.') else PageStatus.PUBLIC
#
#     @property
#     def slug(self):
#         return f"{self.file_dirname}/{self.file_name}{self.file_ext}"
#
#     def rename_media_file(self) -> None:
#         """Renames media file as b64 encoded value"""
#         encoded_filename = self.encode_filename(self.file_path, self.data)
#         new_filepath = self.file_path.replace(self.file_name+self.file_ext, encoded_filename)
#         os.rename(self.file_path, new_filepath)
#         self.file_path = new_filepath
#
#     def open_image(self):
#         from PIL import Image
#         raw_img = Image.open(self.file_path)
#         return raw_img
#
#     def resize(self, sizes=None):
#         '''
#         Resize each image and save to the upload path in corresponding image size and paths
#         This happens after full size images are saved to the filesystem
#         '''
#         from PIL import Image
#         from pyonir import Site
#         raw_img = self.open_image()
#         if sizes is None:
#             sizes = [Site.THUMBNAIL_DEFAULT]
#         try:
#             for dimensions in sizes:
#                 width, height = dimensions
#                 # self._sizes.append(dimensions)
#                 img = raw_img.resize((width, height), Image.Resampling.BICUBIC)
#                 file_name = f'{self.file_name}--{width}x{height}'
#                 img_dirpath = os.path.dirname(self.file_path)
#                 Path(img_dirpath).mkdir(parents=True, exist_ok=True)
#                 filepath = os.path.join(img_dirpath, Site.UPLOADS_THUMBNAIL_DIRNAME, file_name + '.' + self.file_ext)
#                 if not os.path.exists(filepath): img.save(filepath)
#         except Exception as e:
#             raise
#
#     @staticmethod
#     def decode_filename(encoded_filename: str) -> Optional[dict]:
#         """ Reverse of encode_filename. """
#         from urllib.parse import parse_qs
#
#         try:
#             # restore padding
#             padding = "=" * (-len(encoded_filename) % 4)
#             encoded_filename = encoded_filename.replace("_", ".") + padding
#             raw = base64.urlsafe_b64decode(encoded_filename.encode()).decode()
#             parsed = parse_qs(raw)
#             return parsed
#         except Exception as e:
#             return None
#
#     @staticmethod
#     def encode_filename(file_path: str, meta_data: dict = None) -> str:
#         """
#         Build filename as url encoded string, then Base64 encode (URL-safe, no '.' in output).
#         """
#         from urllib.parse import urlencode
#
#         file_name, file_ext = os.path.splitext(os.path.basename(file_path))
#         created_date = int(datetime.now().timestamp())
#         raw = urlencode(meta_data) if meta_data else f'name={file_name}&ext={file_ext}&created_date={created_date}'
#         # URL-safe base64 (no + or /), strip padding '='
#         b64 = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
#         return b64+file_ext
#
#     @staticmethod
#     async def save_upload(file, img_folder_abspath) -> str:
#         """Saves base64 file contents into file system"""
#         file_name, file_ext = os.path.splitext(file.filename)
#         new_dir_path = Path(img_folder_abspath)
#         new_dir_path.mkdir(parents=True, exist_ok=True)
#         new_file_path = os.path.join(img_folder_abspath, file_name + file_ext)
#         file_contents = await file.read()
#         if not file_contents: return ''
#         with open(str(new_file_path), 'wb') as f:
#             f.write(file_contents)
#         return new_file_path
#
#     @staticmethod
#     def get_media_data(media_file_path: str):
#         from pymediainfo import MediaInfo
#         media_info = MediaInfo.parse(media_file_path)
#         media_track_file = media_info.tracks.pop(0)
#         created_on = media_track_file.file_creation_date
#         for track in media_info.tracks:
#             if track.track_type == "Image":
#                 return {
#                     "name": media_track_file.file_name,
#                     "created_on": created_on,
#                     "width": track.width,
#                     "height": track.height,
#                 }
#             if track.track_type == "Audio":
#                 dur = track.duration / 1000 if track.duration else None # ms → seconds
#                 return {
#                     "codec": track.codec,
#                     "duration": dur,
#                     "bit_rate": track.bit_rate,
#                     "channels": track.channel_s,
#                     "sampling_rate": track.sampling_rate,
#                 }
#             if track.track_type == "Video":
#                 return {
#                     "codec": track.codec,
#                     "duration": track.duration / 1000 if track.duration else None,  # ms → seconds
#                     "width": track.width,
#                     "height": track.height,
#                     "frame_rate": track.frame_rate,
#                     "bit_rate": track.bit_rate,
#                 }
