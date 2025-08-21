import os
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Type

from pyonir.core import PyonirSchema
from pyonir.pyonir_types import PyonirApp


class DatabaseService(ABC):
    """Stub implementation of DatabaseService with env-based config + builder overrides."""

    def __init__(self, app: PyonirApp) -> None:
        # Base config from environment
        self._config: Dict[str, Any] = getattr(getattr(app.configs, 'env', object()), 'database', None)
        self.connection: Optional[sqlite3.Connection] = None
        self._database: str = '' # the db address or name. path/to/directory, path/to/sqlite.db
        self._driver: str = '' #the db context fs, sqlite, mysql, pgresql, oracle
        self._host: str = ''
        self._port: int = ''
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
        print(f"[DEBUG] Connecting to {self.driver} database at {self.host}:{self.port}")

    @abstractmethod
    def disconnect(self) -> None:
        if self.driver == "sqlite" and self.connection:
            print("[DEBUG] Disconnecting from SQLite")
            self.connection.close()
            self.connection = None
        # FS does not need explicit disconnect

    # @abstractmethod
    # def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
    #     print(f"[DEBUG] Executing query: {query} with params: {params}")
    #     return NotImplemented

    @abstractmethod
    def insert(self, table: str, entity: Type[PyonirSchema]) -> Any:
        """Insert entity into backend."""
        table = entity.__class__.__name__.lower()
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
            # table_path = Path(self.database) / table
            # table_path.mkdir(parents=True, exist_ok=True)
            # record_id = len(list(table_path.glob("*.json"))) + 1
            # with open(table_path / f"{record_id}.json", "w") as f:
            #     json.dump(data, f, indent=2)
            return os.path.exists(entity.file_path)

    @abstractmethod
    def find(self, entity_cls: Type[PyonirSchema], filter: Dict = None) -> Any:
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



