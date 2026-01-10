import os
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union, Iterator, Generator, List
from urllib.parse import quote_plus

from sortedcontainers import SortedList
from sqlalchemy.sql.ddl import DropTable

from pyonir.core.mapper import cls_mapper
from pyonir.core.parser import DeserializeFile
from pyonir.core.schemas import BaseSchema
from pyonir.core.app import BaseApp
from pyonir.pyonir_types import AppCtx, AbstractFSQuery, BasePagination
from pyonir.core.utils import get_attr


class Driver(StrEnum):
    MEMORY = ':memory:'
    SQLITE = 'sqlite'
    FILE_SYSTEM = 'fs'
    POSTGRES = 'postgres'
    MYSQL = 'mysql'
    ORACLE = 'ora'

class DatabaseConfig(BaseSchema):
    """Configuration settings for database connections."""
    name: str
    """Logical name for the database."""

    driver: Driver = lambda: Driver.FILE_SYSTEM
    """Database backend / driver identifier.

    Used to determine which database engine to connect to and how to build
    the connection URL.

    Examples:
        "sqlite"
        "postgresql"
        "mysql"
    """

    url: str
    """Database connection path or URL.

    For PostgreSQL and MySQL, this is the database name.
    For SQLite, this is the database file path.

    Examples:
        "app_prod"        # PostgreSQL / MySQL database
        "app_dev"         # PostgreSQL / MySQL database
        "data/app.db"     # SQLite file path
    """

    host: str
    """Database server directory path or hostname or IP address.

    Required for networked databases such as PostgreSQL and MySQL.
    Ignored when using SQLite.

    Examples:
        "localhost"
        "127.0.0.1"
        "/path/to/sqlite/dbfile"
        "db.internal"
    """

    port: int | None
    """Port number used to connect to the database server.

    Common default ports:
        5432  # PostgreSQL
        3306  # MySQL

    Ignored when using SQLite.

    Examples:
        5432
        3306
    """

    username: str | None
    """Username for database authentication.

    Required for PostgreSQL and MySQL.
    Not used for SQLite connections.

    Examples:
        "app_user"
        "readonly_user"
    """

    password: str | None
    """Password for database authentication.

    Required for PostgreSQL and MySQL.
    Not used for SQLite connections.

    This value should be provided securely (e.g., environment variables
    or a secrets manager).

    Examples:
        "supersecretpassword"
        "change_me"
    """

class PyonirDatabaseService:
    """Database service with env-based config."""
    _drivers = Driver
    def __init__(self, app: BaseApp) -> None:
        from pyonir.core.utils import get_attr
        db_env_configs = get_attr(app.env, 'database') or {}
        dc = cls_mapper(db_env_configs, DatabaseConfig)
        self.connection: Optional[sqlite3.Connection] = None
        self.app = app
        self._datastore_dirpath: str = ""
        self._dbconfig: DatabaseConfig = dc

    @property
    def datastore_path(self):
        """Path to the app datastore directory"""
        return self._datastore_dirpath or self.app.datastore_dirpath

    @property
    def db_name(self) -> str:
        return self._dbconfig.name or self.app.name

    @property
    def driver(self) -> str:
        return self._dbconfig.driver or Driver.SQLITE.value

    @property
    def host(self) -> str:
        return self._dbconfig.host

    @property
    def port(self) -> Optional[int]:
        return self._dbconfig.port

    @property
    def username(self) -> Optional[str]:
        return self._dbconfig.username

    @property
    def password(self) -> Optional[str]:
        return self._dbconfig.password

    @property
    def url(self) -> str:
        """Return the SQLAlchemy database URL."""
        if self.driver == Driver.SQLITE or self.driver == Driver.FILE_SYSTEM:
            # File-based or in-memory SQLite
            if self.db_name == ":memory:":
                return "sqlite:///:memory:"
            database_dirpath = os.path.join(self.datastore_path, self.db_name)
            return f"{database_dirpath}.db"

        # Networked databases
        auth_creds = ""
        if self.username:
            pwd = quote_plus(self.password or "")
            auth_creds = f"{self.username}:{pwd}@"

        host = self.host or "localhost"
        port = f":{self.port}" if self.port else ""

        return f"{self.driver}://{auth_creds}{host}{port}/{self.db_name}"

    def use(self, db_url: str) -> "PyonirDatabaseService":
        """Set the database to use."""
        db_type, database, host, port, username, password = self.parse_db_url(db_url)
        dbc = PyonirDatabaseService(self.app)
        dbc.set_driver(db_type)
        dbc.set_dbname(os.path.basename(database))
        dbc.set_datastore_path(os.path.dirname(database))
        dbc.connect()
        return dbc

    def set_driver(self, driver: str) -> "PyonirDatabaseService":
        self._dbconfig.driver = Driver(driver)
        return self

    def set_dbname(self, name: str) -> "PyonirDatabaseService":
        self._dbconfig.name = name
        return self

    def set_datastore_path(self, path: str) -> "PyonirDatabaseService":
        self._datastore_dirpath = path
        return self

    # --- Database operations ---
    def exists(self) -> bool:
        """Check if the database exists."""
        if self.driver == Driver.SQLITE or self.driver == Driver.FILE_SYSTEM:
            return os.path.exists(self.url)
        else:
            raise NotImplementedError("Existence check is only implemented for SQLite and File System in this stub.")

    def build_tables_from_models(self, models: List[Type[BaseSchema]]):
        """Create tables in the database from a list of models."""
        self.connect()
        for model in models:
            self.build_table_from_model(model)
        self.disconnect()

    def build_table_from_model(self, model: Type[BaseSchema]):
        """Create a table in the database."""
        sql_create = model.generate_sql_table(self.driver)
        assert sql_create is not None, "SQL create statement must be provided."
        if self.driver != Driver.SQLITE:
            raise NotImplementedError("Create operation is only implemented for SQLite in this stub.")
        if not self.connection:
            raise ValueError("Database connection is not established.")
        if self.has_table(model.__table_name__):
            return self
        cursor = self.connection.cursor()
        cursor.execute(sql_create)
        return self

    def get_existing_columns(self, table_name: str) -> Dict[str, str]:
        cursor = self.connection.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        return {row[1]: row[2] for row in cursor.fetchall()}

    def get_table_pk(self, table: str, with_columns: bool = False):
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


    @staticmethod
    def parse_db_url(db_url: str) -> tuple[str, str, str | None, int | None, str | None, str | None]:
        """
        Parse a database URL into its components.
        Returns:
            (
                db_type,     # dialect / driver (e.g. "sqlite", "postgresql", "mysql+pymysql")
                database,    # database name or sqlite file path
                host,        # hostname or None
                port,        # port number or None
                username,    # username or None
                password,    # password or None
            )
        """
        from urllib.parse import urlparse, unquote
        parsed = urlparse(db_url)

        db_type = parsed.scheme

        # SQLite special cases
        if db_type == Driver.SQLITE:
            if parsed.path == "/:memory:":
                database = Driver.MEMORY
            else:
                # Remove leading slash for relative paths
                database, ext = os.path.splitext(parsed.path)
            return db_type, database, None, None, None, None

        username = unquote(parsed.username) if parsed.username else None
        password = unquote(parsed.password) if parsed.password else None
        host = parsed.hostname
        port = parsed.port
        database = parsed.path.lstrip("/") if parsed.path else None

        return db_type, database, host, port, username, password

    def destroy(self):
        """Destroy the database or datastore."""
        if self.driver == Driver.SQLITE:
            if os.path.exists(self.url): os.remove(self.url)
            print(f"[DEBUG] SQLite database at {self.url} has been destroyed.")
        elif self.driver == Driver.FILE_SYSTEM and self.url and os.path.exists(self.url):
            import shutil
            shutil.rmtree(self.url)
            print(f"[DEBUG] File system datastore at {self.url} has been destroyed.")
        else:
            raise ValueError(f"Cannot destroy unknown driver or non-existent database: {self.driver}:{self.url}")

    def connect(self):
        if not self.url:
            raise ValueError("Database must be set before connecting")

        if self.driver.startswith(Driver.SQLITE):
            print(f"[DEBUG] Connecting to SQLite database at {self.url}")
            self.connection = sqlite3.connect(self.url)
            self.connection.row_factory = sqlite3.Row
        elif self.driver == Driver.FILE_SYSTEM:
            print(f"[DEBUG] Using file system path at {self.url}")
            Path(self.url).mkdir(parents=True, exist_ok=True)
        else:
            raise ValueError(f"Unknown driver: {self.driver}")
        return self

    def disconnect(self):
        print(f"[DEBUG] Disconnecting from {self.url}")
        if self.driver == Driver.SQLITE and self.connection:
            self.connection.close()
            self.connection = None
        return self

    @abstractmethod
    def insert(self, entity: Type[BaseSchema], table: str = None) -> Any:
        """Insert entity into backend."""

        if self.driver == Driver.FILE_SYSTEM:
            # Save JSON file per record
            entity.save_to_file(entity.file_path)
            return os.path.exists(entity.file_path)

        else:
            self.connect()
            self.build_table_from_model(entity)
            # perform nested inserts for foreign keys if any
            for fk_name, fk_type in getattr(entity, '__foreign_keys__', []):
                fk_entity = getattr(entity, fk_name, None)
                if fk_entity and isinstance(fk_entity, BaseSchema):
                    fk_primary_id = self.insert(fk_entity)
                    # set foreign key reference in main entity
                    setattr(fk_entity, getattr(fk_entity, '__primary_key__'), fk_primary_id)
            table = entity.__table_name__ if hasattr(entity, '__table_name__') else table
            keys, values = BaseSchema.dict_to_tuple(entity) if isinstance(entity, dict) else entity.to_tuple()
            placeholders = ', '.join('?' for _ in values)
            query = f"INSERT INTO {table} {keys} VALUES ({placeholders})"
            cursor = self.connection.cursor()
            cursor.execute(query, values)
            self.connection.commit()
            primary_id_value = getattr(entity, get_attr(entity,'__primary_key__'), cursor.lastrowid)
            return primary_id_value


    @abstractmethod
    def find(self, table: str, filter: Dict = None) -> Any:
        results = []

        if self.driver == Driver.SQLITE:
            where_clause = ''
            params = ()
            if filter:
                where_clause = 'WHERE ' + ' AND '.join(f"{k} = ?" for k in filter)
                params = tuple(filter.values())
            query = f"SELECT * FROM {table} {where_clause}"
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]

        elif self.driver == Driver.FILE_SYSTEM:
            pass

        return results

    @abstractmethod
    def update(self, table: str, id: Any, data: Dict) -> bool:
        """Update entity row using table primary key."""

        if self.driver == Driver.SQLITE:
            pk = self.get_pk(table)
            columns, values = BaseSchema.dict_to_tuple(data, as_update_keys=True)
            query = f"UPDATE {table} SET {columns} WHERE {pk} = ?"
            values = list(values) + [id]
            cursor = self.connection.cursor()
            cursor.execute(query, values)
            self.connection.commit()
            return cursor.rowcount > 0
        return False

    @abstractmethod
    def delete(self, table: str, key_value: Any) -> bool:
        """Delete entity from backend using primary key."""
        if self.driver == Driver.SQLITE:
            if not self.connection:
                raise ValueError("Database connection is not established.")

            # Get schema class to find primary key
            schema_cls = None
            for row in self.connection.execute(f"SELECT * FROM {table} LIMIT 1"):
                schema_cls = type(table.capitalize(), (BaseSchema,), {k: None for k in dict(row).keys()})
                break

            pk_field = getattr(schema_cls, '_primary_key', 'id') if schema_cls else 'id'

            # Build DELETE query
            query = f"DELETE FROM {table} WHERE {pk_field} = ?"
            values = (key_value,)

            try:
                cursor = self.connection.cursor()
                cursor.execute(query, values)
                self.connection.commit()
                return cursor.rowcount > 0
            except sqlite3.Error as e:
                print(f"[ERROR] SQLite delete failed: {e}")
                return False

        return False

# class _DatabaseService(ABC):
#     """Stub implementation of DatabaseService with env-based config + builder overrides."""
#
#     def __init__(self, app: BaseApp, db_name: str = '') -> None:
#         # Base config from environment
#         from pyonir.core.utils import get_attr
#         self.app = app
#         self.connection: Optional[sqlite3.Connection] = None
#         self._db_name: str = db_name
#         self._config: object = get_attr(app.env, 'database')
#         self._database: str = '' # the db address or name. path/to/directory, path/to/sqlite.db
#         self._driver: str = 'sqlite' #the db context fs, sqlite, mysql, pgresql, oracle
#         self._host: str = ''
#         self._port: int = 0
#         self._username: str = ''
#         self._password: str = ''
#
#     @property
#     def datastore_path(self):
#         """Path to the app datastore directory"""
#         return self.app.datastore_dirpath
#
#     @property
#     def db_name(self) -> str:
#         return self._db_name
#
#     @property
#     def driver(self) -> Optional[str]:
#         return self._driver
#
#     @property
#     def host(self) -> Optional[str]:
#         return self._host
#
#     @property
#     def port(self) -> Optional[int]:
#         return self._port
#
#     @property
#     def username(self) -> Optional[str]:
#         return self._username
#
#     @property
#     def password(self) -> Optional[str]:
#         return self._password
#
#     @property
#     def database(self) -> Optional[str]:
#         return self._database
#
#     # --- Builder pattern overrides ---
#     def set_driver(self, driver: str) -> "DatabaseService":
#         self._driver = driver
#         return self
#
#     def set_database(self, database_dirpath: str = None) -> "DatabaseService":
#         if self.driver.startswith('sqlite') or self.driver == 'fs':
#             assert self.db_name is not None
#             basepath = database_dirpath or self.datastore_path
#             database_dirpath = os.path.join(basepath, self.db_name)
#         self._database = database_dirpath
#         return self
#
#     def set_host(self, host: str) -> "DatabaseService":
#         self._host = host
#         return self
#
#     def set_port(self, port: int) -> "DatabaseService":
#         self._port = port
#         return self
#
#     def set_username(self, username: str) -> "DatabaseService":
#         self._username = username
#         return self
#
#     def set_password(self, password: str) -> "DatabaseService":
#         self._password = password
#         return self
#
#     def set_db_name(self, name: str):
#         self._db_name = name
#         return self
#
#     # --- Database operations ---
#     def get_existing_columns(self, table_name: str) -> Dict[str, str]:
#         cursor = self.connection.cursor()
#         cursor.execute(f"PRAGMA table_info({table_name});")
#         return {row[1]: row[2] for row in cursor.fetchall()}
#
#     def get_pk(self, table: str, with_columns: bool = False):
#         cursor = self.connection.cursor()
#         cursor.execute(f"PRAGMA table_info('{table}')")
#         pk = "id"
#         columns = {}
#         for col in cursor.fetchall():
#             cid, name, type_, notnull, dflt_value, pk = col
#             columns[name] = type_
#             if pk == 1:
#                 pk = name
#                 if not with_columns: break
#         columns.update({"__pk__": pk})
#         return pk if not with_columns else columns
#
#     def rename_table_columns(self, table_name: str, rename_map: dict):
#         """
#         Renames columns in database schema table
#         :param table_name: database table
#         :param rename_map: dict with key as existing column name and value as the new name
#         :return:
#         """
#         cursor = self.connection.cursor()
#         existing_cols = self.get_existing_columns(table_name)
#
#         for old_name, new_name in rename_map.items():
#             if old_name in existing_cols and new_name not in existing_cols:
#                 sql = f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name};"
#                 cursor.execute(sql)
#                 print(f"[RENAME] {old_name} → {new_name}")
#         self.connection.commit()
#
#     def add_table_columns(self, table_name: str, column_map: dict):
#         """
#         Adds new table column in database schema table
#         :param table_name: database table
#         :param column_map: dict with key as column name and value as the type
#         :return:
#         """
#         cursor = self.connection.cursor()
#         existing_cols = self.get_existing_columns(table_name)
#
#         for col, dtype in column_map.items():
#             if col not in existing_cols:
#                 sql = f"ALTER TABLE {table_name} ADD COLUMN {col} {dtype};"
#                 cursor.execute(sql)
#                 print(f"[ADD] Column '{col}' added ({dtype})")
#         self.connection.commit()
#
#
#     def has_table(self, table_name: str) -> bool:
#         """checks if table exists"""
#         if not self.connection:
#             raise RuntimeError('Database service has not been initialized')
#         cursor = self.connection.cursor()
#         cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
#         return bool(cursor.fetchone())
#
#     @abstractmethod
#     def destroy(self):
#         """Destroy the database or datastore."""
#         if self.driver == "sqlite" and self.database and os.path.exists(self.database):
#             os.remove(self.database)
#             print(f"[DEBUG] SQLite database at {self.database} has been deleted.")
#         elif self.driver == "fs" and self.database and os.path.exists(self.database):
#             import shutil
#             shutil.rmtree(self.database)
#             print(f"[DEBUG] File system datastore at {self.database} has been deleted.")
#         else:
#             raise ValueError(f"Cannot destroy unknown driver or non-existent database: {self.driver}:{self.database}")
#
#     @abstractmethod
#     def create_table_from_model(self, model: BaseSchema) -> 'DatabaseService':
#         sql = model.generate_sql_table(self.driver)
#         self.create_table(sql)
#         return self
#
#     @abstractmethod
#     def create_table(self, sql_create: str) -> 'DatabaseService':
#         """Create a table in the database."""
#         if self.driver != "sqlite":
#             raise NotImplementedError("Create operation is only implemented for SQLite in this stub.")
#         if not self.connection:
#             raise ValueError("Database connection is not established.")
#         if self.has_table(sql_create):
#             raise RuntimeError(f"Table {sql_create} already exists.")
#         cursor = self.connection.cursor()
#         cursor.execute(sql_create)
#         return self
#
#     @abstractmethod
#     def connect(self) -> None:
#         if not self.database:
#             raise ValueError("Database must be set before connecting")
#
#         if self.driver.startswith("sqlite"):
#             print(f"[DEBUG] Connecting to SQLite database at {self.database}")
#             self.connection = sqlite3.connect(self.database)
#             self.connection.row_factory = sqlite3.Row
#         elif self.driver == "fs":
#             print(f"[DEBUG] Using file system path at {self.database}")
#             Path(self.database).mkdir(parents=True, exist_ok=True)
#         else:
#             raise ValueError(f"Unknown driver: {self.driver}")
#
#     @abstractmethod
#     def disconnect(self) -> None:
#         print(f"[DEBUG] Disconnecting from {self.driver}:{self.database}")
#         if self.driver == "sqlite" and self.connection:
#             self.connection.close()
#             self.connection = None
#
#     @abstractmethod
#     def insert(self, table: str, entity: BaseSchema) -> Any:
#         """Insert entity into backend."""
#
#         if self.driver == "sqlite":
#             keys, values = BaseSchema.dict_to_tuple(entity) if isinstance(entity, dict) else entity.to_tuple()
#             placeholders = ', '.join('?' for _ in values)
#             query = f"INSERT INTO {table} {keys} VALUES ({placeholders})"
#             cursor = self.connection.cursor()
#             cursor.execute(query, values)
#             self.connection.commit()
#             primary_id_value = getattr(entity, get_attr(entity,'__primary_key__'), cursor.lastrowid)
#             # perform nested inserts for foreign keys if any
#             for fk_name, fk_type in getattr(entity, '__foreign_keys__', []):
#                 fk_entity = getattr(entity, fk_name, None)
#                 if fk_entity and isinstance(fk_entity, BaseSchema):
#                     self.create_table(fk_entity._sql_create_table)
#                     fk_primary_id = self.insert(fk_entity.__table_name__, fk_entity)
#             return primary_id_value
#
#         elif self.driver == "fs":
#             # Save JSON file per record
#             entity.save_to_file(entity.file_path)
#             return os.path.exists(entity.file_path)
#
#     @abstractmethod
#     def find(self, table: str, filter: Dict = None) -> Any:
#         results = []
#
#         if self.driver == "sqlite":
#             where_clause = ''
#             params = ()
#             if filter:
#                 where_clause = 'WHERE ' + ' AND '.join(f"{k} = ?" for k in filter)
#                 params = tuple(filter.values())
#             query = f"SELECT * FROM {table} {where_clause}"
#             cursor = self.connection.cursor()
#             cursor.execute(query, params)
#             results = [dict(row) for row in cursor.fetchall()]
#
#         elif self.driver == "fs":
#             pass
#
#         return results
#
#     @abstractmethod
#     def update(self, table: str, id: Any, data: Dict) -> bool:
#         """Update entity row using table primary key."""
#
#         if self.driver == "sqlite":
#             pk = self.get_pk(table)
#             columns, values = BaseSchema.dict_to_tuple(data, as_update_keys=True)
#             query = f"UPDATE {table} SET {columns} WHERE {pk} = ?"
#             values = list(values) + [id]
#             cursor = self.connection.cursor()
#             cursor.execute(query, values)
#             self.connection.commit()
#             return cursor.rowcount > 0
#         return False
#
#     @abstractmethod
#     def delete(self, table: str, key_value: Any) -> bool:
#         """Delete entity from backend using primary key."""
#         if self.driver == "sqlite":
#             if not self.connection:
#                 raise ValueError("Database connection is not established.")
#
#             # Get schema class to find primary key
#             schema_cls = None
#             for row in self.connection.execute(f"SELECT * FROM {table} LIMIT 1"):
#                 schema_cls = type(table.capitalize(), (BaseSchema,), {k: None for k in dict(row).keys()})
#                 break
#
#             pk_field = getattr(schema_cls, '_primary_key', 'id') if schema_cls else 'id'
#
#             # Build DELETE query
#             query = f"DELETE FROM {table} WHERE {pk_field} = ?"
#             values = (key_value,)
#
#             try:
#                 cursor = self.connection.cursor()
#                 cursor.execute(query, values)
#                 self.connection.commit()
#                 return cursor.rowcount > 0
#             except sqlite3.Error as e:
#                 print(f"[ERROR] SQLite delete failed: {e}")
#                 return False
#
#         return False

class CollectionQuery(AbstractFSQuery):
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
        self.order_by: str = 'file_created_on' # column name to order items by
        self.order_dir: str = 'asc' # asc or desc
        self.limit: int = 0
        self.max_count: int = 0
        self.curr_page: int = 0
        self.page_nums: list[int, int] = None
        self.where_key: str = None
        self.sorted_files: SortedList = None
        self.query_fs: Generator[DeserializeFile] = query_fs(query_path,
                              app_ctx = app_ctx,
                              model = model,
                              name_pattern = name_pattern,
                              exclude_dirs = exclude_dirs,
                              exclude_names = exclude_names,
                              include_names = include_names,
                              force_all = force_all)

    def set_order_by(self, *, order_by: str, order_dir: str = 'asc'):
        return super().set_order_by(order_by=order_by, order_dir=order_dir)

    def set_params(self, params: dict):
        return super().set_params(params)

    def sorting_key(self, x: any):
        return super().sorting_key(x)

    def paginated_collection(self, reverse=True)-> BasePagination:
        """Paginates a list into smaller segments based on curr_pg and display limit"""
        return super().paginated_collection(reverse)

    def paginate(self, start: int, end: int, reverse: bool = False) -> SortedList:
        """Returns a slice of the items list"""
        return super().paginate(start, end, reverse)

    def find(self, value: any, from_attr: str = 'file_name'):
        """Returns the first item where attr == value"""
        return super().find(value, from_attr)

    def where(self, attr, op="=", value=None):
        """Returns a list of items where attr == value"""
        return super().where(attr, op, value)



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
    from pyonir.core.parser import DeserializeFile, FileCache
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
        schema = BasePage if (pf.is_page and not model) else model
        res = cls_mapper(pf, schema) if schema else pf
        return res

    def skip_file(file_path: Path) -> bool:
        """Checks if the file should be skipped based on exclude_dirs and exclude_file"""
        is_hidden_dir = file_path.parent.name.startswith(hidden_file_prefixes)
        if is_hidden_dir:
            return True
        is_private_file = file_path.name.startswith(hidden_file_prefixes)
        is_excluded_file = exclude_names and file_path.name in exclude_names
        is_included_file = include_names and file_path.name in include_names
        is_allowed_file = file_path.suffix[1:] in allowed_content_extensions
        if is_included_file: return False
        if not is_private_file and force_all: return False
        return is_excluded_file or is_private_file or not is_allowed_file

    for path in Path(abs_dirpath).rglob(name_pattern or "*"):
        if path.is_dir() or skip_file(path): continue
        yield get_datatype(path)