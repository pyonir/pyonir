import uuid
from datetime import datetime
from typing import Type, TypeVar, Any, Optional

from pyonir.models.mapper import collect_type_hints, cls_mapper


T = TypeVar("T")

class BaseSchema:
    """
    Interface for immutable dataclass models with CRUD and session support.
    """
    __table_name__ = str()
    __fields__ = set()
    _sql_create_table: Optional[str] = None
    _errors: list[dict[str, Any]]

    def __init_subclass__(cls, **kwargs):
        table_name = kwargs.get("table_name")
        primary_key = kwargs.get("primary_key")
        dialect = kwargs.get("dialect")
        if table_name:
            setattr(cls, "__table_name__", table_name)
        print(f'init_subclass for {cls.__name__}')
        model_fields = set((name, typ)  for name, typ in collect_type_hints(cls).items())
        setattr(cls, "__fields__", model_fields)
        setattr(cls, "__primary_key__", primary_key or "id")
        setattr(cls, "_errors", [])
        cls.generate_sql_table(dialect)

    def __init__(self, **data):
        # Get field defaults from the class and apply them if not provided
        # This ensures default_factory fields are called when value is None
        for field_name, field_type in self.__fields__:
            value = data.get(field_name)
            dvalue_type = getattr(self, field_name, None)
            if value is None and callable(dvalue_type):
                value = dvalue_type()
            setattr(self, field_name, cls_mapper(value, field_type))

    def is_valid(self) -> bool:
        """Returns True if there are no validation errors."""
        return not self._errors

    def validate_fields(self, field_name: str = None):
        """
        Validates fields by calling `validate_<fieldname>()` if defined.
        Clears previous errors on every call.
        """
        if field_name is not None:
            validator_fn = getattr(self, f"validate_{field_name}", None)
            if callable(validator_fn):
                validator_fn()
            return
        for name in self.__dict__.keys():
            if name.startswith("_"):
                continue
            validator_fn = getattr(self, f"validate_{name}", None)
            if callable(validator_fn):
                validator_fn()

    def model_post_init(self, __context):
        """sqlmodel post init callback"""
        object.__setattr__(self, "_errors", [])
        self.validate_fields()

    def __post_init__(self):
        """Dataclass post init callback"""
        self._errors = []
        self.validate_fields()

    def save_to_file(self, file_path: str) -> bool:
        """Saves the user data to a file in JSON format"""
        from pyonir.models.utils import create_file
        return create_file(file_path, self.to_dict(obfuscate=False))

    def save_to_session(self, request: 'PyonirRequest', key: str = None, value: any = None) -> None:
        """Convert instance to a serializable dict."""
        request.server_request.session[key or self.__class__.__name__.lower()] = value

    def to_dict(self, obfuscate = True):
        """Dictionary representing the instance"""

        obfuscated = lambda attr: obfuscate and hasattr(self,'_private_keys') and attr in (self._private_keys or [])
        is_ignored = lambda attr: attr in ('file_path','file_dirpath') or attr.startswith("_") or callable(getattr(self, attr)) or obfuscated(attr)
        def process_value(key, value):
            if hasattr(value, 'to_dict'):
                return value.to_dict(obfuscate=obfuscate)
            if isinstance(value, property):
                return getattr(self, key)
            if isinstance(value, (tuple, list, set)):
                return [process_value(key, v) for v in value]
            return value
        fields = self.__fields__
        return {key: process_value(key, getattr(self, key)) for key, ktype in fields if not is_ignored(key) and not obfuscated(key)}

    def to_json(self, obfuscate = True) -> str:
        """Returns a JSON serializable dictionary"""
        import json
        return json.dumps(self.to_dict(obfuscate))

    @classmethod
    def from_file(cls: Type[T], file_path: str, app_ctx=None) -> T:
        """Create an instance from a file path."""
        from pyonir.models.parser import DeserializeFile
        from pyonir.models.mapper import cls_mapper
        prsfile = DeserializeFile(file_path, app_ctx=app_ctx)
        return cls_mapper(prsfile, cls)

    @classmethod
    def generate_sql_table(cls, dialect: str = None) -> str:
        """Generate the CREATE TABLE SQL string for this model."""
        from sqlalchemy.schema import CreateTable
        from sqlalchemy.dialects import sqlite
        from sqlalchemy.dialects import postgresql
        from sqlalchemy.dialects import mysql
        from sqlalchemy import Boolean, Float, JSON, Table, Column, Integer, String, MetaData
        dialect = dialect or "sqlite"
        PY_TO_SQLA = {
            int: Integer,
            str: String,
            float: Float,
            bool: Boolean,
            dict: JSON,
            list: JSON,
        }
        primary_key = getattr(cls, "__primary_key__", None)
        table_name = getattr(cls, '__table_name__', None) or cls.__name__.lower()
        columns = []
        has_pk = False
        for name, typ in cls.__annotations__.items():
            col_type = PY_TO_SQLA.get(typ, String)
            is_pk = name == 'id' or name == primary_key and not has_pk
            kwargs = {"primary_key": is_pk}
            columns.append(Column(name, col_type, **kwargs))
            if is_pk:
                has_pk = True
        if not has_pk:
            # Ensure at least one primary key
            columns.insert(0, Column("id", Integer, primary_key=True, autoincrement=True))
        table = Table(table_name, MetaData(), *columns)

        # Pick dialect
        if dialect == "sqlite":
            dialect_obj = sqlite.dialect()
        elif dialect == "postgresql":
            dialect_obj = postgresql.dialect()
        elif dialect == "mysql":
            dialect_obj = mysql.dialect()
        else:
            raise ValueError(f"Unsupported dialect: {dialect}")

        cls._sql_create_table = str(CreateTable(table, if_not_exists=True).compile(dialect=dialect_obj))
        return cls._sql_create_table

    @staticmethod
    def generate_date(date_value: str = None) -> datetime:
        from pyonir.models.utils import deserialize_datestr
        return deserialize_datestr(date_value or datetime.now())

    @classmethod
    def generate_id(cls) -> str:
        return uuid.uuid4().hex
