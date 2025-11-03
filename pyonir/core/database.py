import os
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union, Iterator, Generator

from sortedcontainers import SortedList

from pyonir.core.mapper import cls_mapper
from pyonir.core.parser import DeserializeFile
from pyonir.core.schemas import BaseSchema
from pyonir.pyonir_types import PyonirApp, AppCtx
from pyonir.core.utils import get_attr


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

    def __init__(self, app: PyonirApp, db_name: str = '') -> None:
        # Base config from environment
        from pyonir.core.utils import get_attr
        self.app = app
        self.connection: Optional[sqlite3.Connection] = None
        self._db_name: str = db_name
        self._config: object = get_attr(app.env, 'database')
        self._database: str = '' # the db address or name. path/to/directory, path/to/sqlite.db
        self._driver: str = 'sqlite' #the db context fs, sqlite, mysql, pgresql, oracle
        self._host: str = ''
        self._port: int = 0
        self._username: str = ''
        self._password: str = ''

    @property
    def datastore_path(self):
        """Path to the app datastore directory"""
        return self.app.datastore_dirpath

    @property
    def db_name(self) -> str:
        return self._db_name

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

    def set_database(self, database_dirpath: str = None) -> "DatabaseService":
        if self.driver.startswith('sqlite') or self.driver == 'fs':
            assert self.db_name is not None
            database_dirpath = os.path.join(database_dirpath or self.datastore_path, self.db_name)
        self._database = database_dirpath
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

    def set_db_name(self, name: str):
        self._db_name = name
        return self

    # --- Database operations ---
    def get_existing_columns(self, table_name: str) -> Dict[str, str]:
        cursor = self.connection.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        return {row[1]: row[2] for row in cursor.fetchall()}

    def get_pk(self, table: str, with_columns: bool = False):
        cursor = self.connection.cursor()
        cursor.execute(f"PRAGMA table_info('{table}')")
        pk = "id"
        columns = {}
        for col in cursor.fetchall():
            cid, name, type_, notnull, dflt_value, pk = col
            columns[name] = type_
            if pk == 1:
                pk = name
                if not with_columns: break
        columns.update({"__pk__": pk})
        return pk if not with_columns else columns

    def rename_table_columns(self, table_name: str, rename_map: dict):
        """
        Renames columns in database schema table
        :param table_name: database table
        :param rename_map: dict with key as existing column name and value as the new name
        :return:
        """
        cursor = self.connection.cursor()
        existing_cols = self.get_existing_columns(table_name)

        for old_name, new_name in rename_map.items():
            if old_name in existing_cols and new_name not in existing_cols:
                sql = f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name};"
                cursor.execute(sql)
                print(f"[RENAME] {old_name} → {new_name}")
        self.connection.commit()

    def add_table_columns(self, table_name: str, column_map: dict):
        """
        Adds new table column in database schema table
        :param table_name: database table
        :param column_map: dict with key as column name and value as the type
        :return:
        """
        cursor = self.connection.cursor()
        existing_cols = self.get_existing_columns(table_name)

        for col, dtype in column_map.items():
            if col not in existing_cols:
                sql = f"ALTER TABLE {table_name} ADD COLUMN {col} {dtype};"
                cursor.execute(sql)
                print(f"[ADD] Column '{col}' added ({dtype})")
        self.connection.commit()


    def has_table(self, table_name: str) -> bool:
        """checks if table exists"""
        if not self.connection:
            raise RuntimeError('Database service has not been initialized')
        cursor = self.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return bool(cursor.fetchone())

    @abstractmethod
    def destroy(self):
        """Destroy the database or datastore."""
        if self.driver == "sqlite" and self.database and os.path.exists(self.database):
            os.remove(self.database)
            print(f"[DEBUG] SQLite database at {self.database} has been deleted.")
        elif self.driver == "fs" and self.database and os.path.exists(self.database):
            import shutil
            shutil.rmtree(self.database)
            print(f"[DEBUG] File system datastore at {self.database} has been deleted.")
        else:
            raise ValueError(f"Cannot destroy unknown driver or non-existent database: {self.driver}:{self.database}")

    @abstractmethod
    def create_table_from_model(self, model: BaseSchema) -> 'DatabaseService':
        sql = model.generate_sql_table(self.driver)
        self.create_table(sql)
        return self

    @abstractmethod
    def create_table(self, sql_create: str) -> 'DatabaseService':
        """Create a table in the database."""
        if self.driver != "sqlite":
            raise NotImplementedError("Create operation is only implemented for SQLite in this stub.")
        if not self.connection:
            raise ValueError("Database connection is not established.")
        if self.has_table(sql_create):
            raise RuntimeError(f"Table {sql_create} already exists.")
        cursor = self.connection.cursor()
        cursor.execute(sql_create)
        return self

    @abstractmethod
    def connect(self) -> None:
        if not self.database:
            raise ValueError("Database must be set before connecting")

        if self.driver.startswith("sqlite"):
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

    @abstractmethod
    def insert(self, table: str, entity: BaseSchema) -> Any:
        """Insert entity into backend."""
        import json
        data = entity if isinstance(entity, dict) else entity.to_dict()

        if self.driver == "sqlite":
            keys = ', '.join(data.keys())
            placeholders = ', '.join('?' for _ in data)
            query = f"INSERT INTO {table} ({keys}) VALUES ({placeholders})"
            values = tuple(json.dumps(v) if isinstance(v,(dict, list, tuple, set)) else v for v in data.values())
            cursor = self.connection.cursor()
            cursor.execute(query, values)
            self.connection.commit()
            return getattr(entity, entity.__primary_key__) if hasattr(entity,'__primary_key__') else cursor.lastrowid

        elif self.driver == "fs":
            # Save JSON file per record
            entity.save_to_file(entity.file_path)
            return os.path.exists(entity.file_path)

    @abstractmethod
    def find(self, table: str, filter: Dict = None) -> Any:
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
            pass

        return results

    @abstractmethod
    def update(self, table: str, key_value: Any, data: Dict) -> bool:
        """Update entity in backend using primary key."""
        if self.driver == "sqlite":
            if not self.connection:
                raise ValueError("Database connection is not established.")

            # Get schema class to find primary key
            schema_cls = None
            for row in self.connection.execute(f"SELECT * FROM {table} LIMIT 1"):
                schema_cls = type(table.capitalize(), (BaseSchema,), {k: None for k in dict(row).keys()})
                break

            pk_field = getattr(schema_cls, '_primary_key', 'id') if schema_cls else 'id'

            # Build UPDATE query
            set_clause = ', '.join(f"{k} = ?" for k in data.keys())
            query = f"UPDATE {table} SET {set_clause} WHERE {pk_field} = ?"
            values = list(data.values()) + [key_value]

            try:
                cursor = self.connection.cursor()
                cursor.execute(query, values)
                self.connection.commit()
                return cursor.rowcount > 0
            except sqlite3.Error as e:
                print(f"[ERROR] SQLite update failed: {e}")
                return False

        return False

class BaseFSQuery:
    """Base class for querying files and directories"""
    _cache: Dict[str, Any] = {}

    def __init__(self, query_path: str,
                app_ctx: AppCtx = None,
                model: Optional[object] = None,
                name_pattern: str = None,
                exclude_dirs: tuple = None,
                exclude_names: tuple = None,
                include_names: tuple = None,
                force_all: bool = True) -> None:

        self.query_path = query_path
        # self.sort_by: str = 'file_created_on'
        self.order_by: str = 'file_created_on' # column name to order items by
        self.order_dir: str = 'asc' # asc or desc
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
                              include_names = include_names,
                              force_all = force_all)

    def set_params(self, params: dict):
        for k in ['limit', 'curr_page','max_count','page_nums','order_by','order_dir','where_key']:
            if k in params:
                if k in ('limit', 'curr_page', 'max_count') and params[k]:
                    params[k] = int(params[k])
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

    def paginated_collection(self)-> Optional[BasePagination]:
        """Paginates a list into smaller segments based on curr_pg and display limit"""
        from sortedcontainers import SortedList

        if self.order_by:
            self.sorted_files = SortedList(self.files, self.sorting_key)
        if self.where_key:
            where_key = [self.parse_params(ex) for ex in self.where_key.split(',')]
            self.sorted_files = SortedList(self.where(**where_key[0]), self.sorting_key)
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
        from pyonir.core.mapper import dict_to_class
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
            self.sorted_files = SortedList(self.files, lambda x: get_attr(x, self.order_by) or x)
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
        elif v[0]=='=':
            v = v[1:]
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
                include_names: tuple = None,
                force_all: bool = True) -> Generator:
    """Returns a generator of files from a directory path"""
    from pathlib import Path
    from pyonir.core.page import BasePage
    from pyonir.core.parser import DeserializeFile
    from pyonir.core.media import BaseMedia

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
        is_included_file = include_names and file_path.name in include_names
        is_allowed_file = file_path.suffix[1:] in allowed_content_extensions
        if is_included_file: return False
        if not is_private_file and force_all: return False
        return is_excluded_file or is_private_file or not is_allowed_file

    for path in Path(abs_dirpath).rglob(name_pattern or "*"):
        if skip_file(path) or path.is_dir(): continue
        yield get_datatype(path)