import os
import uuid
from datetime import datetime
from typing import Type, TypeVar, Any, Optional, List, Set


T = TypeVar("T")

class BaseSchema:
    """
    Interface for immutable dataclass models with CRUD and session support.
    """
    __table_name__ = str()
    __fields__ = set()
    __alias__ = dict()
    __primary_key__ = str()
    __frozen__ = bool()
    __foreign_keys__: Set[Any] = None
    _sql_create_table: Optional[str] = None
    _errors: list[dict[str, Any]]
    _private_keys: Optional[list[str]]

    created_by: str = staticmethod(lambda: "pyonir_system")
    created_at: datetime = staticmethod(lambda: datetime.now())

    def __init_subclass__(cls, **kwargs):
        from pyonir.core.mapper import collect_type_hints
        table_name = kwargs.get("table_name")
        primary_key = kwargs.get("primary_key")
        dialect = kwargs.get("dialect")
        alias = kwargs.get("alias_map", {})
        frozen = kwargs.get("frozen", False)
        foreign_keys = kwargs.get("foreign_keys", False)
        if table_name:
            setattr(cls, "__table_name__", table_name)
        foreign_fields = set()
        model_fields = set()

        def is_fk(name, typ):
            if foreign_keys and typ in foreign_keys:
                foreign_fields.add((name, typ))
                return True
            return False
        for name, typ in collect_type_hints(cls).items():
            is_fk(name, typ)
            model_fields.add((name, typ))
        # model_fields = set((name, typ, is_fk(name,typ)) for name, typ in collect_type_hints(cls).items())
        setattr(cls, "__fields__", model_fields)
        setattr(cls, "__primary_key__", primary_key or "id")
        setattr(cls, "__foreign_keys__", foreign_fields)
        setattr(cls, "__alias__", alias)
        setattr(cls, "__frozen__", frozen)
        setattr(cls, "_errors", [])
        cls.generate_sql_table(dialect)

    def __init__(self, **data):
        from pyonir.core.mapper import coerce_value_to_type

        for field_name, field_type in self.__fields__:
            value = data.get(field_name)
            custom_mapper_fn = getattr(self, f'map_to_{field_name}', None)
            type_factory = getattr(self, field_name, custom_mapper_fn)
            value = coerce_value_to_type(value, field_type, default_factory=type_factory) if value or type_factory else None
            setattr(self, field_name, value)

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
        from pyonir.core.utils import create_file
        from pyonir.core.parser import LOOKUP_DATA_PREFIX
        from pyonir import Site
        # file_path = app_datastore if Site and not file_path else file_path
        active_user = getattr(Site.server.request, 'active_user', None)
        filename_as_pk = os.path.basename(file_path).split('.')[0]
        schema_pk_value = getattr(self, self.__primary_key__, None) if self.__primary_key__!='id' else filename_as_pk
        if self.__foreign_keys__:
            app_datastore = Site.datastore_dirpath if Site else os.path.dirname(file_path)
            for k, fk_type in self.__foreign_keys__:
                data_path = os.path.join(app_datastore, fk_type.__table_name__)
                fk_schema_inst = getattr(self, k, None)
                if fk_schema_inst and hasattr(fk_schema_inst, "save_to_file"):
                    fk_schema_inst.created_by = active_user.uid if active_user else fk_schema_inst.created_by
                    fk_pk_value = getattr(fk_schema_inst, fk_schema_inst.__primary_key__, None)
                    fk_entry_name = (fk_pk_value if fk_pk_value and fk_pk_value!='id' else schema_pk_value) + '.json'
                    fk_file_path = os.path.join(data_path, fk_entry_name)
                    fk_schema_inst.save_to_file(fk_file_path)
                    setattr(self,k, f"{LOOKUP_DATA_PREFIX}/{fk_schema_inst.__table_name__}/{fk_entry_name}")
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
            if isinstance(value, datetime):
                return value.isoformat()
            return value

        return {key: process_value(key, getattr(self, key)) for key, ktype in self.__fields__ if not is_ignored(key) and not obfuscated(key)}

    def to_json(self, obfuscate = True) -> str:
        """Returns a JSON serializable dictionary"""
        import json
        return json.dumps(self.to_dict(obfuscate))

    @classmethod
    def from_file(cls: Type[T], file_path: str, app_ctx=None) -> T:
        """Create an instance from a file path."""
        from pyonir.core.parser import DeserializeFile
        from pyonir.core.mapper import cls_mapper
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
        for name, typ in cls.__fields__:
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
        from pyonir.core.utils import deserialize_datestr
        return deserialize_datestr(date_value or datetime.now())

    @classmethod
    def generate_id(cls) -> str:
        return uuid.uuid4().hex


class GenericQueryModel:
    """A generic model to hold dynamic fields from query strings."""
    file_created_on: str
    file_name: str
    def __init__(self, model_str: str):
        aliases = {}
        fields = set()
        for k in model_str.split(','):
            if ':' in k:
                k,_, src = k.partition(':')
                aliases[k] = src
            fields.add((k, str))

        setattr(self, "__fields__", fields)
        setattr(self, "__alias__", aliases)
