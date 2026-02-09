from dataclasses import dataclass, field
from enum import unique, Enum
from typing import Any, Dict, Generator, Optional, Union, Callable, List, Tuple, Iterator

from pyonir.core.parser import DeserializeFile, VIRTUAL_ROUTES_FILENAME
from pyonir.core.templating import TemplateEnvironment, PyonirThemes, Theme
from pyonir.core.utils import get_attr, set_attr
from datetime import datetime

from sortedcontainers import SortedList


TEXT_RES: str = 'text/html'
JSON_RES: str = 'application/json'
EVENT_RES: str = 'text/event-stream'
PAGINATE_LIMIT: int = 6

# === Route Definitions ===
PagesPath = str
APIPath = str
RoutePath = str
"""Represents the URL path of a route (e.g., '/about', '/api/data')."""

RouteFunction = Callable
"""A callable that handles a specific route request (e.g., controller function)."""

RouteMethods = List[str]
"""HTTP methods supported by a route (e.g., ['GET', 'POST'])."""

RouteOptions = Optional[dict]
"""Additional options for a route, such as authentication requirements."""

PyonirRoute = Tuple[RoutePath, RouteFunction, RouteMethods, RouteOptions]
"""A single route entry containing the path, its handler function, and allowed HTTP methods."""

PyonirRouters = List[Tuple[RoutePath, List[PyonirRoute]]]
"""A collection (or group) of routes, usually organized by feature or resource, and often mounted under"""


# === Application Module Definitions ===

AppName = str
"""The name identifier for an app module."""

ModuleName = str
"""The Python module name used for import or registration."""

AppEndpoint = str
"""The base endpoint path where the app is mounted."""

AppPaths = List[str]
"""A list of file or URL paths associated with the app."""

AppContentsPath = str
"""The root path to the static or content files of the app."""

AppSSGPath = str
"""The path used for static site generation output."""

AppContextPaths = Tuple[AppName, RoutePath, AppPaths]
"""Context binding tuple that connects an app name to a route and its associated paths."""

AppCtx = Tuple[ModuleName, RoutePath, AppContentsPath, AppSSGPath]
"""Full application context including module reference and content/static paths."""

AppRequestPaths = Tuple[RoutePath, AppPaths]
"""Tuple representing an incoming request path and all known paths for resolution."""

class EnvConfig:
    """Application configuration values loaded from environment variables.

    This class defines all required configuration fields for the application,
    including feature flags and database connection settings.
    """
    salt: str
    """Secret salt value used for hashing and security operations."""
    use_ssl: bool
    """Enable or disable SSL for the application."""
    use_themes: bool
    """Enable or disable application theme support."""

    def add(self, key: str, value: Any, is_nested: bool = False) -> None:
        """Adds a configuration value to the environment settings."""
        set_attr(self, key, value)


class PyonirHooks(str):
    AFTER_INIT = 'AFTER_INIT'
    ON_REQUEST = 'ON_REQUEST'
    ON_PARSELY_COMPLETE = 'ON_PARSELY_COMPLETE'

@unique
class BaseEnum(Enum):
    def __str__(self):
        return self.value

    @classmethod
    def contains(cls, item: str) -> bool:
        if not isinstance(item, str):
            return False
        item = item.lower()
        return any(
            item == member.value or item == member.name.lower()
            for member in cls
        )

@dataclass
class BasePagination:
    limit: int = 0
    max_count: int = 0
    curr_page: int = 0
    page_nums: list[int] = field(default_factory=list)
    items: list[DeserializeFile] = field(default_factory=list)

    def __iter__(self) -> Iterator[DeserializeFile]:
        return iter(self.items)

    def to_dict(self) -> dict:
        from pyonir.core.utils import json_serial
        return {
            "limit": self.limit,
            "max_count": self.max_count,
            "curr_page": self.curr_page,
            "page_nums": self.page_nums,
            "items": [json_serial(item) for item in self.items]
        }

class AbstractFSQuery:
    """
    Abstract base for filesystem queries.
    Subclasses must implement `_get_query_generator()` which should return a generator
    of items to be queried (files or mapped objects).
    """
    _cache: Dict[str, Any] = {}
    order_by: str = 'file_created_on' # column name to order items by
    order_dir: str = 'asc' # asc or desc
    limit: int = 0
    max_count: int = 0
    curr_page: int = 0
    page_nums: list[int, int] = None
    where_key: str = None
    sorted_files: SortedList = None
    query_fs: Any = None


    def set_order_by(self, *, order_by: str, order_dir: str = 'asc'):
        self.order_by = order_by
        self.order_dir = order_dir
        return self

    def set_params(self, params: dict):
        for k in ['limit', 'curr_page','max_count','page_nums','order_by','order_dir','where_key']:
            if k in params:
                if k in ('limit', 'curr_page', 'max_count') and params[k]:
                    try:
                        params[k] = int(params[k])
                    except ValueError:
                        params[k] = 0
                setattr(self, k, params[k])
        return self

    def sorting_key(self, x: any):
        if self.order_dir not in ("asc", "desc"):
            raise ValueError("order_dir must be 'asc' or 'desc'")

        def _invert(val):
            # For numbers and timestamps
            if isinstance(val, (int, float)):
                return -val
            # For strings: reverse lexicographic order
            if isinstance(val, str):
                return "".join(chr(255 - ord(c)) for c in val)
            # Fallback
            return val

        value = get_attr(x, self.order_by)

        # If sorting by datetime-like values
        if isinstance(value, datetime):
            value = value.timestamp()

        # If value is None, push it to the end consistently
        if value is None:
            return float("inf") if self.order_dir == "asc" else float("-inf")

        return value if self.order_dir == "asc" else _invert(value)

    def paginated_collection(self, reverse=True)-> BasePagination:
        """Paginates a list into smaller segments based on curr_pg and display limit"""
        from sortedcontainers import SortedList
        self.order_dir = 'desc' if reverse else 'asc'
        if self.order_by:
            self.sorted_files = SortedList(self.query_fs, self.sorting_key)
        if self.where_key:
            where_key = [self.parse_params(ex) for ex in self.where_key.split(',')]
            self.sorted_files = SortedList(self.where(**where_key[0]), self.sorting_key)
        force_all = not self.limit

        self.max_count = len(self.sorted_files)
        page_num = 0 if force_all else self.curr_page or 1
        start = (page_num * self.limit) - self.limit
        end = (self.limit * page_num)
        pg = (self.max_count // self.limit) + (self.max_count % self.limit > 0) if self.limit > 0 else 0
        pag_data = self.paginate(start=start, end=end, reverse=reverse) if not force_all else self.sorted_files

        return BasePagination(
            curr_page = page_num,
            page_nums = [n for n in range(1, pg + 1)] if pg else [],
            limit = self.limit,
            max_count = self.max_count,
            items = list(pag_data)
        )

    def paginate(self, start: int, end: int, reverse: bool = False):
        """Returns a slice of the items list"""
        sl = self.sorted_files.islice(start, end, reverse=reverse) if end else self.sorted_files
        return sl

    def find(self, value: any, from_attr: str = 'file_name') -> Optional[DeserializeFile]:
        """Returns the first item where attr == value"""
        return next((item for item in self.sorted_files if getattr(item, from_attr, None) == value), None)

    def where(self, attr, op="=", value=None) -> 'AbstractFSQuery':
        """Returns a list of items where attr == value"""
        from pyonir.core.utils import get_attr

        def match(item):
            actual = get_attr(item, attr)
            if not hasattr(item, attr):
                return False
            if actual and not value:
                return True # checking only if item has an attribute
            elif op == "=":
                return actual == value
            elif op == "in" or op == "contains":
                return actual in value if actual is not None else False
            elif op == ">":
                return actual > value
            elif op == "<":
                return actual < value
            elif op == ">=":
                return actual >= value
            elif op == "<=":
                return actual <= value
            elif op == "!=":
                return actual != value
            return False
        if callable(attr): match = attr
        if not self.sorted_files:
            self.sorted_files = SortedList(self.query_fs, lambda x: get_attr(x, self.order_by) or x)
        target = list(self.sorted_files)
        self.sorted_files = filter(match, target)
        return self

    def __len__(self):
        return self.sorted_files and len(self.sorted_files) or 0

    def __iter__(self):
        return iter(self.sorted_files)

    @staticmethod
    def parse_params(param: str) -> dict:
        k, _, v = param.partition(':')
        op = '='
        is_eq = lambda x: x[1]=='='
        if v.startswith('>'):
            eqs = is_eq(v)
            op = '>=' if eqs else '>'
            v = v[1:] if not eqs else v[2:]
        elif v.startswith('<'):
            eqs = is_eq(v)
            op = '<=' if eqs else '<'
            v = v[1:] if not eqs else v[2:]
            pass
        elif v[0]=='=':
            v = v[1:]
        else:
            pass
        return {"attr": k.strip(), "op":op, "value": AbstractFSQuery.coerce_bool(v)}

    @staticmethod
    def coerce_bool(value: str) -> Union[bool, str]:
        d = ['false', 'true']
        try:
            i = d.index(value.lower().strip())
            return True if i else False
        except ValueError as e:
            return value.strip()

    @staticmethod
    def prev_next(input_file: 'DeserializeFile'):
        """Returns the previous and next files relative to the input file"""
        from pyonir.core.mapper import dict_to_class
        from pyonir.core.database import query_fs
        prv = None
        nxt = None
        _collection: Generator[DeserializeFile] = query_fs(input_file.file_dirpath)
        # _collection = iter(bfsquery.query_fs)
        for cfile in _collection:
            if cfile.file_status == 'hidden': continue
            if cfile.file_path == input_file.file_path:
                nxt = next(_collection, None)
                break
            else:
                prv = cfile
        return dict_to_class({"next": nxt, "prev": prv})
