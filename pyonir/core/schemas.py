import json, os, uuid
import re
from datetime import datetime
from enum import StrEnum, IntEnum, Enum
from typing import Type, Tuple, TypeVar, Any, Optional, List, Set, Dict

from sqlalchemy import Table

from pyonir.core.parser import LOOKUP_DATA_PREFIX

from pyonir.core.utils import json_serial, get_attr, generate_uuid

T = TypeVar("T")
SYSTEM_COLUMNS = ('created_on', 'created_by')
SYSTEM_COLUMN_TYPES = (('created_on', datetime), ('created_by', str))

def get_active_user() -> str:
    from pyonir import Site
    active_uid = Site.name if Site else "pyonir_system"
    user = Site.server.request.security.authenticated_user if Site and Site.server.is_active else None
    if user:
        active_uid = user.uid
    return active_uid

def process_schema(schema_cls: Type[T],
            table_name: Optional[str] = None,
            unique_keys: Optional[List[str]] = None,
            foreign_keys: Optional[List[str]] = None,
            file_name: Optional[str] = None,
            is_singleton: bool = False,
            **kwargs):
    """Process the schema class to extract fields, primary keys, foreign keys, and generate SQL statements."""
    # from .schemas import SYSTEM_COLUMNS, get_active_user, BaseSchema, generate_sqla, generate_sqla_table
    from .mapper import normalize_types, unwrap_type, UnwrappedType
    from .utils import generate_date
    fields = normalize_types(schema_cls)
    setattr(schema_cls, "__params__", fields)
    if not table_name: return

    foreign_keys = foreign_keys or set()
    unique_keys = unique_keys or []
    nullable_keys = set()
    foreign_fields = set()
    foreign_field_names = set()

    foreign_key_options = kwargs.get("fk_options", {})
    timestamps_keys     = kwargs.get("timestamp_keys", set())
    lookup_table_key    = kwargs.get("lookup_table", False)
    mutable_columns     = kwargs.get("mutable_columns", False)
    primary_key         = kwargs.get("primary_key", '')
    alias               = kwargs.get("alias_map", {})
    frozen              = kwargs.get("frozen", False)

    timestamps_keys.add("created_on")
    private_keys = list()
    returning_cols = []
    has_sys_cols = []
    _all_unique = '*' in unique_keys
    created_by: str = get_active_user
    created_on: datetime = generate_date

    if _all_unique: unique_keys = list()

    def is_fk(typ: any) -> bool:
        is_base_schema = typ and issubclass(typ, BaseSchema) and getattr(typ, '__table_name__', None)
        is_fk_col_type = typ in foreign_keys
        return is_fk_col_type or is_base_schema

    for norm_field_type in fields: # Configure field types and metadata for SQL generation and mapping
        norm_field_type: UnwrappedType = norm_field_type
        if norm_field_type.is_private: continue
        if norm_field_type.column_name in SYSTEM_COLUMNS:
            has_sys_cols.append(norm_field_type.column_name)

        is_pk = primary_key == norm_field_type.column_name
        is_unique_column = _all_unique and norm_field_type.column_name not in SYSTEM_COLUMNS
        is_fk_column = is_fk(norm_field_type.base) or norm_field_type.column_name in foreign_field_names

        norm_field_type.is_pk = is_pk
        norm_field_type.is_lookup = lookup_table_key and norm_field_type.column_name == lookup_table_key
        norm_field_type.is_unique = is_unique_column
        norm_field_type.is_fk = is_fk_column

        if is_unique_column:
            unique_keys.append(norm_field_type.column_name)

    for syscol in SYSTEM_COLUMNS:
        if syscol in has_sys_cols: continue
        default_fn = created_by if syscol == 'created_by' else created_on
        ctype = str if syscol == 'created_by' else datetime
        col = unwrap_type(ctype, syscol, default=default_fn)
        fields.append(col)
        setattr(schema_cls, syscol, default_fn)


    setattr(schema_cls, "__alias__", alias)
    setattr(schema_cls, "__frozen__", frozen)
    setattr(schema_cls, "__table_name__", table_name)

    setattr(schema_cls, "__primary_key__", primary_key)
    setattr(schema_cls, "__primary_key_value__", None)
    setattr(schema_cls, "__foreign_keys__", foreign_fields)
    setattr(schema_cls, "__fk_options__", foreign_key_options)
    setattr(schema_cls, "_private_keys", private_keys)
    setattr(schema_cls, "_foreign_key_names", foreign_field_names)
    setattr(schema_cls, "_mutable_columns", mutable_columns)
    setattr(schema_cls, "_unique_keys", unique_keys)
    setattr(schema_cls, "_nullable_keys", nullable_keys)
    setattr(schema_cls, "_timestamp_keys", timestamps_keys)
    setattr(schema_cls, "_lookup_table", lookup_table_key)
    setattr(schema_cls, "_file_name", file_name or schema_cls.__name__.lower())
    setattr(schema_cls, "_file_path", None)
    setattr(schema_cls, "_is_singleton", is_singleton)

    sqla_table = generate_sqla_table(schema_cls)
    setattr(schema_cls, "_sqla_table", sqla_table)
    setattr(schema_cls, "_sql_create_table", generate_sqla(sqla_table, True))
    setattr(schema_cls, "_sql_insert", generate_sqla(sqla_table, is_insert=True, returning_cols=returning_cols, update_cols=mutable_columns))
    setattr(schema_cls, "_sql_upsert", generate_sqla(sqla_table, returning_cols=returning_cols, update_cols=mutable_columns))

class BaseModel:
    __params__: list[T] = None
    _errors: list[str] = []

    # def __init_subclass__(cls, **kwargs):
    #     process_schema(cls, **kwargs)

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
        for typ in self.schema_columns():
            name = typ.column_name
            validator_fn = getattr(self, f"validate_{name}", None)
            if callable(validator_fn):
                validator_fn()

class BaseSchema(BaseModel):
    """
    Interface for immutable dataclass models with CRUD and session support.
    """
    _file_path: str = None
    _file_name: str = None
    __table_name__: str = ""
    __table_columns__: list[str] = None
    __primary_key_value__: int
    _unique_keys: list[str] = None
    _lookup_table: str = None
    _sql_create_table: str = None
    _sql_upsert: str = None
    _sql_insert: str = None
    _foreign_key_names: str = None
    _nullable_keys: list[str] = None

    def __init_subclass__(cls, **kwargs):
        process_schema(cls, **kwargs)

    def __init__(self, _disable_type_checker: bool = False, **data):
        from pyonir.core.mapper import UnwrappedType

        pkv = data.get('__primary_key_value__', None)

        for field_type in self.schema_columns():
            field_type: UnwrappedType = field_type
            if field_type.is_private: continue
            field_name = field_type.column_name
            input_value = data.get(field_name)
            input_value = field_type.coerce_value(input_value, enforce_type=_disable_type_checker)
            setattr(self, field_name, input_value)
        if pkv:
            self.set_primary_key(pkv)

        self._errors = []
        self.validate_fields()
        self._after_init()

    def set_primary_key(self, value: any):
        self.__primary_key_value__ = value

    @classmethod
    def from_file(cls: Type[T], file_path: str, app_ctx=None) -> T:
        """Create an instance from a file path."""
        from pyonir.core.parser import DeserializeFile
        from pyonir.core.mapper import dto_mapper
        prsfile = DeserializeFile(file_path, app_ctx=app_ctx)
        return dto_mapper(prsfile, cls)

    @classmethod
    def sql_after_create(cls, dbc: 'PyonirDatabaseService'):
        """Initialize sql after table creation."""
        pass

    @property
    def id(self):
        return self.__primary_key_value__ if hasattr(self, '__primary_key_value__') else None

    @classmethod
    def fks(cls):
        return [c for c in cls.schema_columns() if c.is_fk]

    @classmethod
    def pk(cls):
        for c in cls.schema_columns():
            if c.is_pk:
                return c.column_name
        return None

    @classmethod
    def unique_keys(cls):
        return cls._unique_keys or []

    @property
    def is_lookup_table(self):
        if not hasattr(self, '_lookup_table'): return None
        return bool(self._lookup_table)

    @property
    def lookup_table_ref_url(self) -> Optional[str]:
        """Creates the lookup table reference path"""
        if not self.is_lookup_table: return None
        file_name = getattr(self, self._lookup_table)
        if not file_name:
            raise AttributeError("Lookup table value is not defined")
        file_name = os.path.basename(self.file_path) if self.file_path else f'{self.formated_filename(file_name)}.json'
        with_attr_path = f".{self._lookup_table}" if self._unique_keys else ""
        return f"{LOOKUP_DATA_PREFIX}/{self.table_name}/{file_name}#data{with_attr_path}"

    @property
    def table_name(self):
        return self.__table_name__

    @property
    def foreign_key_names(self):
        return self._foreign_key_names

    @property
    def sql_create(self):
        return self._sql_create_table

    @property
    def sql_upsert(self):
        return self._sql_upsert

    @property
    def sql_insert(self):
        return self._sql_insert

    @property
    def pyonir_app(self):
        from pyonir import Site
        return Site if Site else None

    @property
    def file_dirpath(self):
        return os.path.dirname(self._file_path) if self._file_path else None

    @property
    def file_path(self):
        return self._file_path

    @classmethod
    def schema_columns(cls) -> list['UnwrappedType']:
        return cls.__params__

    def model_post_init(self, __context):
        """sqlmodel post init callback"""
        object.__setattr__(self, "_errors", [])
        self.validate_fields()

    def _after_init(self):
        """Hook for additional initialization in subclasses."""
        pass

    def __post_init__(self):
        """Dataclass post init callback"""
        self._errors = []
        self.validate_fields()

    def formated_filename(self, filename: str = None):
        return filename

    def remove_file(self):
        if hasattr(self, 'file_path'):
            os.remove(self.file_path)

    def save_to_file(self, file_path: str = None, with_props: list = None):
        from pyonir.core.utils import create_file
        from pyonir.core.parser import LOOKUP_DATA_PREFIX
        from pyonir import Site
        from pyonir.core.security import PyonirUser, PyonirUserMeta
        from pyonir.core.mapper import UnwrappedType

        if not file_path:
            file_path = self.file_path if self.file_path else f"{self.__class__.__name__.lower()}.json"
        _filename = os.path.basename(file_path).split('.')[0]
        file_data = self.to_dict(obfuscate=False, with_props=with_props)
        active_user_id = get_attr(Site.server.request, 'security.user.uid') or self.created_by
        use_filename_as_pk = active_user_id if isinstance(self, (PyonirUser, PyonirUserMeta)) else _filename
        _pk_value = get_attr(self, getattr(self, '__primary_key__')) or use_filename_as_pk
        _datastore = Site.datastore_dirpath if Site else os.path.dirname(file_path)

        if not self.file_path:
            self._file_path = file_path
        if not self.created_by:
            self.created_by = active_user_id

        for fk_type in self.fks():
            fk_type: UnwrappedType = fk_type
            k = fk_type.column_name
            fk_schema_inst: BaseSchema = getattr(self, k, None)
            if fk_schema_inst and hasattr(fk_schema_inst, "save_to_file"):
                fk_table_name = fk_schema_inst.table_name
                data_path = os.path.join(_datastore, fk_table_name)
                if fk_schema_inst.is_lookup_table:
                    # For lookup tables, we reference static file already generated during startup
                    fk_lookup_path = fk_schema_inst.lookup_table_ref_url

                else:
                    fk_schema_inst.created_by = active_user_id
                    # use main schema pk value as the fk file name to show relationship
                    fk_file_name = use_filename_as_pk + '.json'
                    fk_file_path = os.path.join(data_path, fk_file_name)
                    fk_schema_inst.save_to_file(fk_file_path)
                    fk_lookup_path = f"{LOOKUP_DATA_PREFIX}/{fk_table_name}/{fk_file_name}#data"
                # set relationship path on parent schema
                file_data[k] = fk_lookup_path

        return create_file(file_path, file_data)

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
        for typ in self.schema_columns():
            name = typ.column_name
            validator_fn = getattr(self, f"validate_{name}", None)
            if callable(validator_fn):
                validator_fn()

    def update(self, data: object) -> 'BaseSchema':
        """Update mutable fields of the schema instance."""
        for col_type in self.schema_columns():
            key = col_type.column_name
            curr_value = getattr(self, key, None)
            nxt_value = get_attr(data, key) or None
            if nxt_value is not None and curr_value != nxt_value:
                setattr(self, key, nxt_value)
        return self

    def to_dict(self, obfuscate: bool = True, with_props: list = None) -> dict:
        """Dictionary representing the instance"""
        is_property = lambda attr: isinstance(getattr(self.__class__, attr, None), property)
        obfuscated = lambda attr: obfuscate and getattr(self,'_private_keys', None) and attr in (self._private_keys or [])
        is_ignored = lambda attr: attr in ('file_path','file_dirpath') or attr.startswith("_") or is_property(attr) or callable(getattr(self, attr)) or obfuscated(attr)

        def process_value(key, value):
            if hasattr(value, 'to_dict'):
                return value.to_dict(obfuscate=obfuscate, with_props=with_props)
            if isinstance(value, property):
                return getattr(self, key)
            if isinstance(value, (tuple, list, set)):
                return [process_value(key, v) for v in value]
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, Enum):
                return value.value
            return value

        res = {key.column_name: process_value(key.base, getattr(self, key.column_name)) for key in self.schema_columns() if not is_ignored(key.column_name) and not obfuscated(key)}
        # save primary key value under a special key for lookup when reconstructing from file
        if with_props:
            for prop in with_props:
                if not hasattr(self, prop): continue
                if not obfuscated(prop):
                    res[prop] = process_value(prop, getattr(self, prop))
        if hasattr(self, '__primary_key_value__'):
            res["__primary_key_value__"] = self.id
        return res

    def to_json(self, obfuscate = True) -> str:
        """Returns a JSON serializable dictionary"""
        import json
        return json.dumps(self.to_dict(obfuscate))

    def generate_uuid(self) -> str:
        from_unique_keys = "".join([getattr(self, k, None) for k in self._unique_keys]) if self._unique_keys else None
        return generate_uuid(from_string=from_unique_keys)

    @staticmethod
    def generate_uuid(from_string: str = None) -> str:
        return generate_uuid(from_string=from_string)

    @staticmethod
    def generate_date(date_value: str = None) -> datetime:
        from pyonir.core.utils import generate_date
        return generate_date(date_value)

def generate_sqla_table(cls) -> Optional[Table]:
    """Generate the CREATE TABLE SQL string for this model, including foreign keys.
    Ensure referenced tables are present in the same MetaData so ForeignKey targets can be resolved.
    """
    table_name = getattr(cls, '__table_name__', None)
    if not table_name: return None
    from sqlalchemy import text, UniqueConstraint, Boolean, Float, JSON, Table, Column, Integer, String, MetaData, ForeignKey
    from pyonir.core.mapper import UnwrappedType

    metadata = MetaData()
    columns = []
    columns_names = []

    PY_TO_SQLA = {
        int: Integer,
        str: String,
        float: Float,
        bool: Boolean,
        dict: JSON,
        list: JSON,
    }

    primary_key = getattr(cls, "__primary_key__", None)
    unq_set = getattr(cls, "_unique_keys", list())
    # fk_set = getattr(cls, "__foreign_keys__", set())
    # mutable_columns = getattr(cls, "_mutable_columns", list())
    # is_lookup = getattr(cls, "_lookup_table", False)

    for schema_column in cls.schema_columns():
        # determine SQL column type
        schema_column: UnwrappedType = schema_column
        if schema_column.is_private: continue # skip private columns
        name = schema_column.column_name
        is_pk = schema_column.is_pk
        is_fk = schema_column.is_fk
        is_nullable = schema_column.is_optional
        is_unique = schema_column.is_unique
        use_auto_timestamp = name in cls._timestamp_keys and not is_pk and not is_fk
        default_value = getattr(cls, name, None)
        column_type = schema_column.base or str

        col_type = PY_TO_SQLA.get(column_type, String)
        col_args = [] if is_fk else [col_type]


        kwargs = {"primary_key": is_pk, "nullable": is_nullable, "default": default_value}

        # if this field is registered as a foreign key, add ForeignKey constraint
        if is_fk:
            column_type: BaseSchema = column_type
            fk_options = cls.__fk_options__.get(name, {})
            fk_table_name = column_type.__table_name__
            # fk_pks = column_type.__primary_keys__
            fk_pk, fk_pk_type = ('id', PY_TO_SQLA.get(int))
            fk_pk_type = PY_TO_SQLA.get(int)
            col_args.append(ForeignKey(f"{fk_table_name}.{fk_pk}", **fk_options))
            Table(fk_table_name, metadata, Column(fk_pk, fk_pk_type, primary_key=True), extend_existing=True)

        if use_auto_timestamp:
            kwargs["server_default"] = text("CURRENT_TIMESTAMP")
        columns.append(Column(name, *col_args, **kwargs))
        columns_names.append(name)


    if not primary_key:
        # Ensure at least one primary key
        cls.__primary_key__ = 'id'
        columns.insert(0, Column("id", Integer, primary_key=True, autoincrement=True))
    if unq_set:
        constraint_name = f"uq_{table_name}_{'_'.join(unq_set)}"
        columns.append(UniqueConstraint(*unq_set, name=constraint_name))
    # Create main table with the same metadata so FK resolution works
    table = Table(table_name, metadata, *columns)
    return table


def generate_sqla(
    table: Table,
    is_create: bool = False,
    is_insert: bool = False,
    dialect: Optional[str] = None,
    toggle_columns: Optional[List[str]] = None,
    returning_cols: Optional[List[str]] = None,
    update_cols: Optional[List[str]] = None,
) -> str:
    """
    Generate CREATE TABLE, INSERT, or UPSERT SQL string for a given SQLAlchemy table.
    """

    from sqlalchemy.dialects import sqlite, postgresql, mysql
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from sqlalchemy import bindparam, UniqueConstraint, or_, Integer
    from sqlalchemy.schema import CreateTable

    # ---------------------------
    # Pick dialect
    # ---------------------------
    dialect_insert = sqlite_insert
    dialect_obj = sqlite.dialect()

    if dialect == "postgresql":
        dialect_obj = postgresql.dialect()
        dialect_insert = postgresql.insert
    elif dialect == "mysql":
        dialect_obj = mysql.dialect()
        dialect_insert = mysql.insert

    # ---------------------------
    # CREATE TABLE
    # ---------------------------
    if is_create:
        return str(CreateTable(table, if_not_exists=True).compile(dialect=dialect_obj))

    toggle_columns = toggle_columns or []

    insert_values = {}
    pk_columns = []
    updatable_columns = []

    # ---------------------------
    # Inspect columns
    # ---------------------------
    for col in table.columns:
        name = col.name

        if col.primary_key:
            pk_columns.append(name)

            # Only include PK if not auto-generated
            if not (
                col.autoincrement
                or col.default is not None
                or col.server_default is not None
            ):
                insert_values[name] = bindparam(name)

        else:
            insert_values[name] = bindparam(name)
            updatable_columns.append(name)

    # Determine conflict target
    constraint_cols: Optional[List[str]] = None

    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint):
            constraint_cols = [c.name for c in constraint.columns]
            break

    if not constraint_cols and pk_columns:
        constraint_cols = pk_columns
    # ---------------------------
    # Base INSERT
    # ---------------------------
    stmt = dialect_insert(table).values(insert_values)

    # ============================================================
    # SIMPLE INSERT MODE
    # ============================================================
    if is_insert:
        if returning_cols:
            stmt = stmt.returning(*[table.c[c] for c in returning_cols])
        else:
            stmt = stmt.returning(*[table.c[c] for c in pk_columns])
        if constraint_cols:
            stmt = stmt.on_conflict_do_nothing()
        return str(
            stmt.compile(
                dialect=dialect_obj,
                compile_kwargs={"render_postcompile": True},
            )
        )

    # ============================================================
    # UPSERT MODE
    # ============================================================


    columns_to_update = update_cols or updatable_columns
    upsert_set = {}
    where_conditions = []

    for name in columns_to_update:
        col = table.c[name]

        if name in toggle_columns and isinstance(col.type, Integer):
            upsert_set[name] = 1 - col
        else:
            upsert_set[name] = stmt.excluded[name]
            where_conditions.append(col.is_not(stmt.excluded[name]))

    where_clause = or_(*where_conditions) if where_conditions else None

    if constraint_cols and upsert_set:
        stmt = stmt.on_conflict_do_update(
            index_elements=constraint_cols,
            set_=upsert_set,
            # where=where_clause,
        )

    # RETURNING
    if returning_cols:
        stmt = stmt.returning(*[table.c[c] for c in returning_cols])
    elif pk_columns:
        stmt = stmt.returning(*[table.c[c] for c in pk_columns])

    return str(
        stmt.compile(
            dialect=dialect_obj,
            compile_kwargs={"render_postcompile": True},
        )
    )


class Graphiti:
    """
    Graphiti is a Graphql like method for modeling an object from strings
    """
    QUERY_KEY = "@graphiti"
    """Query parameter key that signals the system to execute logic based on URL query arguments."""

    def __init__(self, query: str = None, from_data: object = None, app_ctx: list = None):
        self.__query__ = Graphiti.parse_query(query) if isinstance(query, str) else query
        self.__as_dict__ = {}
        self.__as_scalr__ = None
        self.__app_ctx__ = app_ctx or (None, None, None, None, None)
        if query and from_data:
            self._hydrate(from_data)

    def create(self, data: Any):
        if isinstance(data, list):
            return [Graphiti(self.__query__, from_data=itm, app_ctx=self.__app_ctx__) for itm in data]
        res = Graphiti(self.__query__, app_ctx=self.__app_ctx__, from_data=data)
        return res

    def _hydrate(self, data: Any):
        from pyonir.core.mapper import lookup_fk
        _, _, _, _, data_dir = self.__app_ctx__
        for alias_key, src_key, rt_ref_key, nested in self.__query__:
            v = get_attr(data, rt_ref_key or src_key)
            if nested:
                v = lookup_fk(v, data_dir, self.__app_ctx__) if data_dir else v
                outer_value = nested.create(v)
                self._add(alias_key, outer_value)
            else:
                lv = lookup_fk(v, data_dir, self.__app_ctx__) if data_dir else v
                outer_value = get_attr(lv, src_key) if v != lv else v
                self._add(alias_key, outer_value)

        return self

    @staticmethod
    def get_alias(v: str, gobj: 'Graphiti' = None):
        """Returns a tuple of strings where the left value is the alias and right is the source"""
        src_alias, src_key = v.split(':',1) if ':' in v else (v,v)
        if gobj: gobj.set_alias(src_alias, src_key)
        return src_alias, src_key

    @staticmethod
    def parse_query(query_model: str):
        """deserialize query model"""
        has_obj = query_model.startswith('{') and query_model.endswith('}')
        if query_model[0] == '#':
            return [(None, query_model[1:], None, None)]
        query_model = query_model[1:len(query_model)-1] if has_obj else query_model
        src_keys = re.split(r',\s*(?![^{}]*\})', query_model )
        res = []
        for src_key in src_keys:
            has_nested = re.findall(r'([\w:]*|[\w.]*|[\w]){(\s?.*)}', src_key)
            if has_nested:
                for src_key, inner_keys in has_nested:
                    alias_key, src_key = Graphiti.get_alias(src_key)
                    rt_ref_key = src_key.split('.',1)[0] if '.' in src_key else None
                    res.append((alias_key, src_key, rt_ref_key, Graphiti(inner_keys)))
            else:
                alias_key, src_key = Graphiti.get_alias(src_key)
                rt_ref_key = src_key.split('.',1)[0] if '.' in src_key else None
                res.append((alias_key, src_key, rt_ref_key, None))
        return res

    def set_alias(self, src_alias: str, src_key: str):
        if src_alias != src_key:
            self.__alias__[src_alias] = src_key

    def _add(self, key, value):
        if not key:
            self.__as_scalr__ = value
            return
        self.__as_dict__[key] = value
        setattr(self, key, value)

    def to_dict(self, **kwargs):
        return self.__as_dict__ or self.__as_scalr__