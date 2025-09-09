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


class BasePage:
    """Represents a single page returned from a web request"""
    _orm_options = {"mapper": {'created_on': 'file_created_on', 'modified_on': 'file_modified_on'}}
    # url: str = ''
    # slug: str = ''
    # title: str = ''
    # content: str = ''
    template: str = 'pages.html'
    created_on: datetime = None
    modified_on: datetime = None
    # entries: BasePagination = None

    def __lt__(self, other) -> bool:
        """Compares two BasePage instances based on their created_on attribute."""
        if not isinstance(other, BasePage):
            return True
        return self.created_on < other.created_on
