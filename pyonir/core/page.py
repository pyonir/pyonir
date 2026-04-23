from dataclasses import dataclass
from datetime import datetime
import os, pytz
from typing import Any
from pathlib import Path
from typing import Tuple, List

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


@dataclass
class BasePage:
    """Represents a single page returned from a web request"""
    __alias__ = {'created_on': 'file_created_on', 'modified_on': 'file_modified_on'}
    template: str = 'pages.html'
    url: str = ''
    slug: str = ''
    created_on: datetime = None
    modified_on: datetime = None
    _category: str = ''
    _subcategories: str = ''

    def __lt__(self, other) -> bool:
        """Compares two BasePage instances based on their created_on attribute."""
        if not isinstance(other, BasePage):
            return True
        return self.created_on < other.created_on

    def __post_init__(self):
        cat, subcats = self.parse_taxonomy(self.slug)
        if cat:
            self._subcategories = subcats
            self._category = cat

    @property
    def category(self):
        return self._category

    @property
    def subcategory(self):
        return self._subcategories[0]

    @staticmethod
    def parse_taxonomy(path: str) -> Tuple[str, List[str]]:
        p = Path(path)

        # remove filename
        parts = p.parts[:-1]

        # remove leading slash if present
        parts = [p for p in parts if p != "/"]

        if not parts:
            return None, []

        category = parts[0]
        subcategories = list(parts[1:])

        return category, subcategories

    def to_dict(self, **kwargs):
        cat, sub_cat = self.parse_taxonomy(self.slug)
        res = {"category": cat}
        res.update(self.__dict__)
        return res
