import os
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Type, Iterable, Callable, Union, Iterator, Generator

from sortedcontainers import SortedList

from pyonir.models.mapper import cls_mapper
from pyonir.models.parser import DeserializeFile
from pyonir.models.schemas import BaseSchema
from pyonir.pyonir_types import PyonirApp, AppCtx

@dataclass
class BasePagination:
    limit: int = 0
    max_count: int = 0
    curr_page: int = 0
    page_nums: list[int, int] = field(default_factory=list)
    items: list['DeserializeFile'] = field(default_factory=list)

    def __iter__(self) -> Iterator['DeserializeFile']:
        return iter(self.items)

class DatabaseService(ABC):
    """Stub implementation of DatabaseService with env-based config + builder overrides."""

    def __init__(self, app: PyonirApp) -> None:
        # Base config from environment
        from pyonir.utilities import get_attr
        self._config: object = get_attr(app.env, 'database')
        self.connection: Optional[sqlite3.Connection] = None
        self._database: str = '' # the db address or name. path/to/directory, path/to/sqlite.db
        self._driver: str = '' #the db context fs, sqlite, mysql, pgresql, oracle
        self._host: str = ''
        self._port: int = 0
        self._username: str = ''
        self._password: str = ''

    @property
    def driver(self) -> Optional[str]:
        return self._driver

    @property
    def host(self) -> Optional[str]:
        return self._host

    @property
    def port(self) -> Optional[int]:
        return self._port

    @property
    def username(self) -> Optional[str]:
        return self._username

    @property
    def password(self) -> Optional[str]:
        return self._password

    @property
    def database(self) -> Optional[str]:
        return self._database

    # --- Builder pattern overrides ---
    def set_driver(self, driver: str) -> "DatabaseService":
        self._driver = driver
        return self

    def set_database(self, database: str) -> "DatabaseService":
        self._database = database
        return self

    def set_host(self, host: str) -> "DatabaseService":
        self._host = host
        return self

    def set_port(self, port: int) -> "DatabaseService":
        self._port = port
        return self

    def set_username(self, username: str) -> "DatabaseService":
        self._username = username
        return self

    def set_password(self, password: str) -> "DatabaseService":
        self._password = password
        return self

    # --- Database operations ---
    @abstractmethod
    def connect(self) -> None:
        if not self.database:
            raise ValueError("Database must be set before connecting")

        if self.driver == "sqlite":
            print(f"[DEBUG] Connecting to SQLite database at {self.database}")
            self.connection = sqlite3.connect(self.database)
            self.connection.row_factory = sqlite3.Row
        elif self.driver == "fs":
            print(f"[DEBUG] Using file system path at {self.database}")
            Path(self.database).mkdir(parents=True, exist_ok=True)
        else:
            raise ValueError(f"Unknown driver: {self.driver}")

    @abstractmethod
    def disconnect(self) -> None:
        print(f"[DEBUG] Disconnecting from {self.driver}:{self.database}")
        if self.driver == "sqlite" and self.connection:
            self.connection.close()
            self.connection = None
        # FS needs to reset its database location

    # @abstractmethod
    # def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
    #     print(f"[DEBUG] Executing query: {query} with params: {params}")
    #     return NotImplemented

    @abstractmethod
    def insert(self, table: str, entity: Type[BaseSchema]) -> Any:
        """Insert entity into backend."""
        table = table or entity.__class__.__name__.lower()
        data = entity.to_dict()

        if self.driver == "sqlite":
            keys = ', '.join(data.keys())
            placeholders = ', '.join('?' for _ in data)
            query = f"INSERT INTO {table} ({keys}) VALUES ({placeholders})"
            cursor = self.connection.cursor()
            cursor.execute(query, tuple(data.values()))
            self.connection.commit()
            return cursor.lastrowid

        elif self.driver == "fs":
            # Save JSON file per record
            entity.save_to_file(entity.file_path)
            return os.path.exists(entity.file_path)

    @abstractmethod
    def find(self, entity_cls: Type[BaseSchema], filter: Dict = None) -> Any:
        import json
        table = entity_cls.__name__.lower()
        results = []

        if self.driver == "sqlite":
            where_clause = ''
            params = ()
            if filter:
                where_clause = 'WHERE ' + ' AND '.join(f"{k} = ?" for k in filter)
                params = tuple(filter.values())
            query = f"SELECT * FROM {table} {where_clause}"
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]

        elif self.driver == "fs":
            table_path = Path(self.database) / table
            if table_path.exists():
                for file_path in table_path.glob("*.json"):
                    with open(file_path) as f:
                        record = json.load(f)
                        if filter:
                            match = all(record.get(k) == v for k, v in filter.items())
                            if match:
                                results.append(record)
                        else:
                            results.append(record)

        return results



class BaseFSQuery:
    """Base class for querying files and directories"""
    _cache: Dict[str, Any] = {}

    def __init__(self, query_path: str,
                app_ctx: AppCtx = None,
                model: Optional[object] = None,
                name_pattern: str = None,
                exclude_dirs: tuple = None,
                exclude_names: tuple = None,
                force_all: bool = True) -> None:

        self.query_path = query_path
        self.sort_by: str = 'file_created_on'
        self.limit: int = 0
        self.max_count: int = 0
        self.curr_page: int = 0
        self.page_nums: list[int, int] = None
        self.where_key: str = None
        self.sorted_files: SortedList = None
        self.files: Generator[DeserializeFile] = query_fs(query_path,
                              app_ctx = app_ctx,
                              model = model,
                              name_pattern = name_pattern,
                              exclude_dirs = exclude_dirs,
                              exclude_names = exclude_names,
                              force_all = force_all)

    def set_params(self, params: dict):
        for k in ['sort_by', 'limit', 'curr_page','max_count','page_nums']:
            if k in params:
                if k in ('limit', 'curr_page', 'max_count') and params[k]:
                    params[k] = int(params[k])
                setattr(self, k, params[k])
        return self

    def paginated_collection(self)-> Optional[BasePagination]:
        """Paginates a list into smaller segments based on curr_pg and display limit"""
        from sortedcontainers import SortedList
        from pyonir.models.utils import get_attr

        if self.sort_by:
            self.sorted_files = SortedList(self.files, lambda x: get_attr(x, self.sort_by) or x)
        if self.where_key:
            where_key = [self.parse_params(ex) for ex in self.where_key.split(',')]
            self.sorted_files = SortedList(self.where(**where_key[0]), lambda x: get_attr(x, self.sort_by))
        force_all = not self.limit

        self.max_count = len(self.sorted_files)
        page_num = 0 if force_all else int(self.curr_page)
        start = (page_num * self.limit) - self.limit
        end = (self.limit * page_num)
        pg = (self.max_count // self.limit) + (self.max_count % self.limit > 0) if self.limit > 0 else 0
        pag_data = self.paginate(start=start, end=end, reverse=True) if not force_all else self.sorted_files

        return BasePagination(
            curr_page = page_num,
            page_nums = [n for n in range(1, pg + 1)] if pg else None,
            limit = self.limit,
            max_count = self.max_count,
            items = list(pag_data)
        )

    def paginate(self, start: int, end: int, reverse: bool = False):
        """Returns a slice of the items list"""
        sl = self.sorted_files.islice(start, end, reverse=reverse) if end else self.sorted_files
        return sl

    @staticmethod
    def prev_next(input_file: 'DeserializeFile'):
        """Returns the previous and next files relative to the input file"""
        from pyonir.models.mapper import dict_to_class
        prv = None
        nxt = None
        pc = BaseFSQuery(input_file.file_dirpath)
        _collection = iter(pc.files)
        for cfile in _collection:
            if cfile.file_status == 'hidden': continue
            if cfile.file_path == input_file.file_path:
                nxt = next(_collection, None)
                break
            else:
                prv = cfile
        return dict_to_class({"next": nxt, "prev": prv})

    def find(self, value: any, from_attr: str = 'file_name'):
        """Returns the first item where attr == value"""
        return next((item for item in self.sorted_files if getattr(item, from_attr, None) == value), None)

    def where(self, attr, op="=", value=None):
        """Returns a list of items where attr == value"""
        from pyonir.models.utils import get_attr
        # if value is None:
        #     # assume 'op' is actually the value if only two args were passed
        #     value = op
        #     op = "="

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
            self.sorted_files = SortedList(self.files, lambda x: get_attr(x, self.sort_by) or x)
        return filter(match, list(self.sorted_files or self.files))

    def __len__(self):
        return self.sorted_files and len(self.sorted_files) or 0

    def __iter__(self):
        return iter(self.sorted_files)

    @staticmethod
    def parse_params(param: str):
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
        else:
            pass
        return {"attr": k.strip(), "op":op, "value":BaseFSQuery.coerce_bool(v)}

    @staticmethod
    def coerce_bool(value: str):
        d = ['false', 'true']
        try:
            i = d.index(value.lower().strip())
            return True if i else False
        except ValueError as e:
            return value.strip()


def query_fs(abs_dirpath: str,
                app_ctx: AppCtx = None,
                model: Union[object, str] = None,
                name_pattern: str = None,
                exclude_dirs: tuple = None,
                exclude_names: tuple = None,
                force_all: bool = True) -> Generator:
    """Returns a generator of files from a directory path"""
    from pathlib import Path
    from pyonir.models.page import BasePage, DeserializeFile
    from pyonir.models.media import BaseMedia

    # results = []
    hidden_file_prefixes = ('.', '_', '<', '>', '(', ')', '$', '!', '._')
    allowed_content_extensions = ('prs', 'md', 'json', 'yaml')
    def get_datatype(filepath) -> Union[object, BasePage, BaseMedia]:
        if model == 'path': return str(filepath)
        if model == BaseMedia: return BaseMedia(filepath)
        pf = DeserializeFile(str(filepath), app_ctx=app_ctx)
        if model == 'file':
            return pf
        pf.schema = BasePage if (pf.is_page and not model) else model
        res = cls_mapper(pf, pf.schema) if pf.schema else pf
        return res

    def skip_file(file_path: Path) -> bool:
        """Checks if the file should be skipped based on exclude_dirs and exclude_file"""
        is_private_file = file_path.name.startswith(hidden_file_prefixes)
        is_excluded_file = exclude_names and file_path.name in exclude_names
        is_allowed_file = file_path.suffix[1:] in allowed_content_extensions
        if not is_private_file and force_all: return False
        return is_excluded_file or is_private_file or not is_allowed_file

    for path in Path(abs_dirpath).rglob(name_pattern or "*"):
        if skip_file(path) or path.is_dir(): continue
        yield get_datatype(path)