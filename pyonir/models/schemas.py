import uuid
from datetime import datetime
from typing import Type, TypeVar, Any, Optional

from sqlmodel import SQLModel
from sqlmodel.main import SQLModelMetaclass


T = TypeVar("T")
class MetaSchema(SQLModelMetaclass):
    def __new__(cls, name, bases, namespace, **kwargs):
        # Grab frozen option (default False)
        is_frozen = kwargs.pop("frozen", None)
        is_frozen = is_frozen if is_frozen is not None else False
        private_keys = kwargs.pop("private_keys", None)
        primary_key = kwargs.pop("primary_key", None)
        foreign_keys = kwargs.pop("foreign_keys", None)
        mapper_options = kwargs.pop("mapper_options", None)
        table_name = kwargs.pop("table_name", None)

        if isinstance(table_name, str):
            namespace["__tablename__"] = table_name
            # kwargs["table"] = True
        if isinstance(private_keys, (list, tuple)) and "_private_keys" not in namespace:
            namespace["_private_keys"] = private_keys + ['file_path', 'file_dirpath']

        # Build the class
        new_cls = super().__new__(cls, name, bases, namespace, **kwargs)

        return new_cls

class BaseSchema(SQLModel, metaclass=MetaSchema):
    """
    Interface for immutable dataclass models with CRUD and session support.
    """
    _errors: list[dict[str, Any]]
    _sql_create_table: Optional[str] = None
    def __init__(self, **data):
        # Get field defaults from the class and apply them if not provided
        # This ensures default_factory fields are called when value is None
        for field_name, field_info in self.__class__.model_fields.items():
            # If field has a default_factory and value is None, generate it
            if field_name in data and data[field_name] is None:
                if field_info.default_factory is not None:
                    data[field_name] = field_info.default_factory()
        super().__init__(**data)

    def generate_sql(self, dialect: str = "sqlite") -> str:
        """Generate the CREATE TABLE SQL string for this model."""
        from sqlalchemy.schema import CreateTable
        from sqlalchemy.dialects import sqlite
        from sqlalchemy.dialects import postgresql
        from sqlalchemy.dialects import mysql
        cls = self.__class__
        def table_from_class(metadata, table_name=None, primary_key=None):
            from sqlalchemy import Boolean, Float, JSON, Table, Column, Integer, String

            PY_TO_SQLA = {
                int: Integer,
                str: String,
                float: Float,
                bool: Boolean,
                dict: JSON,
                list: JSON,
            }
            table_name = table_name or cls.__name__.lower()
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
            return Table(table_name, metadata, *columns)
        pks = [k for k,m in self.__class__.model_fields.items() if hasattr(m, 'primary_key') and m.primary_key]
        pk = pks[0] if pks else None
        table = table_from_class(metadata=self.metadata, primary_key=pk)

        # Pick dialect
        if dialect == "sqlite":
            dialect_obj = sqlite.dialect()
        elif dialect == "postgresql":
            dialect_obj = postgresql.dialect()
        elif dialect == "mysql":
            dialect_obj = mysql.dialect()
        else:
            raise ValueError(f"Unsupported dialect: {dialect}")

        self._sql_create_table = str(CreateTable(table, if_not_exists=True).compile(dialect=dialect_obj))
        return self._sql_create_table

    def model_post_init(self, __context):
        object.__setattr__(self, "_errors", [])
        self.validate_fields()

    def __post_init__(self):
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
        fields = self.__class__.model_fields.keys() if hasattr(self.__class__, 'model_fields') else dir(self)
        return {key: process_value(key, getattr(self, key)) for key in fields if not is_ignored(key) and not obfuscated(key)}

    def to_json(self, obfuscate = True) -> str:
        """Returns a JSON serializable dictionary"""
        import json
        return json.dumps(self.to_dict(obfuscate))

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

    @classmethod
    def from_file(cls: Type[T], file_path: str, app_ctx=None) -> T:
        """Create an instance from a file path."""
        from pyonir.models.parser import DeserializeFile
        from pyonir.models.mapper import cls_mapper
        prsfile = DeserializeFile(file_path, app_ctx=app_ctx)
        return cls_mapper(prsfile, cls)

    @staticmethod
    def generate_date(date_value: str = None) -> datetime:
        from pyonir.models.utils import deserialize_datestr
        return deserialize_datestr(date_value or datetime.now())

    @staticmethod
    def generate_id() -> str:
        return uuid.uuid4().hex

    # def queryfs(self, model: Type[T], app_ctx=None) -> BaseFSQuery:
    #     return BaseFSQuery(self.file_dirpath, app_ctx=app_ctx, model=model, exclude_names=(self.file_name, 'index.md'), force_all=True)