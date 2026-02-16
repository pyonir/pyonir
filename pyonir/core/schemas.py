import json, os, uuid
from datetime import datetime
from typing import Type, TypeVar, Any, Optional, List, Set, Dict

from pyonir.core.parser import LOOKUP_DATA_PREFIX

from pyonir.core.utils import json_serial, get_attr

T = TypeVar("T")

def get_active_user() -> str:
    from pyonir import Site
    active_uid = "pyonir_system"
    if Site and Site.server.is_active and Site.server.request.security.has_session:
        active_uid = Site.server.request.security.user and Site.server.request.security.user.uid
    return active_uid

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
    __fk_options__: Dict = None
    __table_columns__: Set[Any] = None
    _sql_create_table: Optional[str] = None
    _errors: list[str]
    _private_keys: Optional[list[str]]
    _foreign_key_names: set[str]
    _unique_keys: Set['BaseSchema']
    _nullable_keys: Set[str]
    _timestamp_keys: Set[str]
    _lookup_table: str

    created_by: str = staticmethod(lambda: get_active_user())
    created_on: datetime = staticmethod(lambda: BaseSchema.generate_date())
    _file_path: str
    # _file_dirpath: str

    def __init_subclass__(cls, **kwargs):
        from pyonir.core.mapper import collect_type_hints, unwrap_optional
        table_name = kwargs.get("table_name")
        primary_key = kwargs.get("primary_key")
        dialect = kwargs.get("dialect")
        alias = kwargs.get("alias_map", {})
        frozen = kwargs.get("frozen", False)
        foreign_keys = kwargs.get("foreign_keys", False)
        foreign_key_options = kwargs.get("fk_options", {})
        unique_keys = kwargs.get("unique_keys", {})
        timestamps_keys = kwargs.get("timestamp_keys", set())
        lookup_table_key = kwargs.get("lookup_table", False)
        nullable_keys = set()
        if table_name:
            setattr(cls, "__table_name__", table_name)
        foreign_fields = set()
        foreign_field_names = set()
        model_fields = set()
        table_columns = set()
        timestamps_keys.add("created_on")
        def is_fk(name, typ):
            if foreign_keys and typ in foreign_keys:
                foreign_fields.add((name, typ))
                foreign_field_names.add(name)
                return True
            return False

        def is_factory(val):
            if callable(val):
                setattr(cls, name, staticmethod(val))

        for name, typ in collect_type_hints(cls).items():
            fktyp, *t = unwrap_optional(typ)
            is_nullable = typ != fktyp
            if is_nullable:
                nullable_keys.add(name)
            is_fk(name, fktyp)
            is_factory(getattr(cls, name, None))
            model_fields.add((name, fktyp))
            table_columns.add(name)

        setattr(cls, "__fields__", model_fields)
        setattr(cls, "__primary_key__", primary_key or "id")
        setattr(cls, "__foreign_keys__", foreign_fields)
        setattr(cls, "__fk_options__", foreign_key_options)
        setattr(cls, "__table_columns__", table_columns)
        setattr(cls, "__alias__", alias)
        setattr(cls, "__frozen__", frozen)
        setattr(cls, "_errors", [])
        setattr(cls, "_foreign_key_names", foreign_field_names)
        setattr(cls, "_unique_keys", unique_keys)
        setattr(cls, "_nullable_keys", nullable_keys)
        setattr(cls, "_timestamp_keys", timestamps_keys)
        setattr(cls, "_lookup_table", lookup_table_key)
        setattr(cls, "_file_path", None)
        # setattr(cls, "_file_dirpath", None)
        cls.generate_sql_table(dialect)

    def __init__(self, **data):
        from pyonir.core.mapper import coerce_value_to_type, cls_mapper
        for field_name, field_type in self.__fields__:
            value = data.get(field_name)
            if data:
                custom_mapper_fn = getattr(self, f'map_to_{field_name}', None)
                type_factory = getattr(self, field_name, custom_mapper_fn)
                # is_opt = field_name in self._nullable_keys
                has_correct_type = isinstance(value, field_type)
                # has_correct_type = (not is_opt and isinstance(value, field_type)) or (value is None and (type_factory is None or callable(type_factory)))
                if not has_correct_type:
                    if field_name in self._foreign_key_names:
                        value = cls_mapper(value, field_type, type_factory=type_factory, is_fk=True) #if should_call_factory else value
                        # should_call_factory = not value and callable(type_factory)
                        # value = type_factory() if should_call_factory else cls_mapper(value, field_type, is_fk=True) if not has_correct_type else value
                    else:
                        value = coerce_value_to_type(value, field_type, factory_fn=type_factory) if (value is not None) or type_factory else None
            setattr(self, field_name, value)

        self._errors = []
        self.validate_fields()
        self._after_init()

    @property
    def file_dirpath(self):
        return os.path.dirname(self._file_path) if self.file_path else None

    @property
    def file_path(self):
        return self._file_path

    @property
    def is_lookup_table(self):
        return bool(self._lookup_table)

    @property
    def lookup_table_ref_url(self):
        """Creates the lookup table reference path"""
        fk_lookup_path = ""
        if self.is_lookup_table:
            file_name = os.path.basename(self.file_path) if self.file_path else getattr(self, self._lookup_table)+'.json'
            fk_lookup_path = f"{LOOKUP_DATA_PREFIX}/{self.__table_name__}/{file_name}#data.{self._lookup_table}"

        return fk_lookup_path

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
        for name, typ in self.__fields__:
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

    def remove_file(self):
        if hasattr(self, 'file_path'):
            os.remove(self.file_path)

    def save_to_file(self, file_path: str = None):
        from pyonir.core.utils import create_file
        from pyonir.core.parser import LOOKUP_DATA_PREFIX
        from pyonir import Site
        from pyonir.core.authorizer import PyonirUser, PyonirUserMeta
        if not file_path:
            file_path = self.file_path if self.file_path else f"{self.__class__.__name__.lower()}.json"
        _filename = os.path.basename(file_path).split('.')[0]
        file_data = self.to_dict(obfuscate=False, with_extras=False)
        active_user_id = get_attr(Site.server.request, 'security.user.uid') or self.created_by
        use_filename_as_pk = active_user_id if isinstance(self, (PyonirUser, PyonirUserMeta)) else _filename
        _pk_value = getattr(self, self.__primary_key__, use_filename_as_pk)
        _datastore = Site.datastore_dirpath if Site else os.path.dirname(file_path)

        if not self.file_path:
            self._file_path = file_path
        if not self.created_by:
            self.created_by = active_user_id

        for k, fk_type in self.__foreign_keys__:
            data_path = os.path.join(_datastore, fk_type.__table_name__)
            fk_schema_inst: BaseSchema = getattr(self, k, None)
            if fk_schema_inst and hasattr(fk_schema_inst, "save_to_file"):
                if fk_schema_inst.is_lookup_table:
                    # For lookup tables, we reference static file already generated during startup
                    fk_lookup_path = fk_schema_inst.lookup_table_ref_url

                else:
                    fk_schema_inst.created_by = fk_schema_inst.created_by or active_user_id
                    # use main schema pk value as the fk file name to show relationship
                    fk_file_name = (_pk_value or BaseSchema.generate_id()) + '.json'
                    fk_file_path = os.path.join(data_path, fk_file_name)
                    fk_schema_inst.save_to_file(fk_file_path)
                    fk_lookup_path = f"{LOOKUP_DATA_PREFIX}/{fk_type.__table_name__}/{fk_file_name}#data"
                # set relationship path on parent schema
                file_data[k] = fk_lookup_path

        return create_file(file_path, file_data)

    def to_dict(self, obfuscate:bool = True, with_extras: bool = False) -> dict:
        """Dictionary representing the instance"""
        is_property = lambda attr: isinstance(getattr(self.__class__, attr, None), property)
        obfuscated = lambda attr: obfuscate and hasattr(self,'_private_keys') and attr in (self._private_keys or [])
        is_ignored = lambda attr: attr in ('file_path','file_dirpath') or attr.startswith("_") or is_property(attr) or callable(getattr(self, attr)) or obfuscated(attr)
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

    def to_tuple(self) -> tuple:
        """Returns a tuple of the model's column values in order."""
        from pyonir.core.mapper import is_optional_type

        columns = []
        values = []
        for name, fkmodel in self.__fields__:
            columns.append(name)
            v = getattr(self, name)
            if (name, fkmodel) in self.__foreign_keys__:
                v = get_attr(v, fkmodel.__primary_key__)
            is_optional_schema = isinstance(v, BaseSchema) and is_optional_type(fkmodel)
            v = json.dumps(v, default=json_serial) if is_optional_schema or isinstance(v,(BaseSchema, dict, list, tuple, set)) else v
            values.append(v)
        return tuple(columns), tuple(values)

    @staticmethod
    def dict_to_tuple(data: dict, as_update_keys: bool = False) -> tuple:
        """Convert a dictionary to a tuple of values in the model's column order."""
        keys = ', '.join(data.keys()) if not as_update_keys else ', '.join(f"{k}=?" for k in data.keys())
        values = tuple(json.dumps(v) if isinstance(v,(dict, list, tuple, set)) else v for v in data.values())
        return keys, values

    def _after_init(self):
        """Hook for additional initialization in subclasses."""
        pass

    @staticmethod
    def init_lookup_table(dbc: 'PyonirDatabaseService'):
        """Initialize lookup table for this model if it has foreign keys."""
        return NotImplementedError("init_lookup_table must be implemented in subclasses with foreign keys to initialize related data.")

    @classmethod
    def from_file(cls: Type[T], file_path: str, app_ctx=None) -> T:
        """Create an instance from a file path."""
        from pyonir.core.parser import DeserializeFile
        from pyonir.core.mapper import cls_mapper
        prsfile = DeserializeFile(file_path, app_ctx=app_ctx)
        return cls_mapper(prsfile, cls)

    @classmethod
    def generate_sql_table(cls, dialect: str = None) -> str:
        """Generate the CREATE TABLE SQL string for this model, including foreign keys.
        Ensure referenced tables are present in the same MetaData so ForeignKey targets can be resolved.
        """
        from sqlalchemy.schema import CreateTable
        from sqlalchemy.dialects import sqlite, postgresql, mysql
        from sqlalchemy import text, Boolean, Float, JSON, Table, Column, Integer, String, MetaData, ForeignKey
        from pyonir.core.mapper import is_optional_type

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

        metadata = MetaData()
        columns = []
        has_pk = False
        fk_set = getattr(cls, "__foreign_keys__", set())
        unq_set = getattr(cls, "_unique_keys", set())
        is_lookup = getattr(cls, "_lookup_table", False)

        # Create minimal stub tables for all referenced foreign key targets so SQLAlchemy can resolve them.
        for fk_name, fk_typ in fk_set:
            if hasattr(fk_typ, "__table_name__"):
                fk_ref_table = getattr(fk_typ, "__table_name__", None) or fk_typ.__name__.lower()
                fk_ref_pk = getattr(fk_typ, "__primary_key__", "id")
                # determine pk column type from referenced model fields
                pk_col_type = String
                for f_name, f_typ in getattr(fk_typ, "__fields__", set()):
                    if f_name == fk_ref_pk:
                        pk_col_type = PY_TO_SQLA.get(f_typ, String)
                        break
                # register a stub table in the same metadata if not already present
                if fk_ref_table not in metadata.tables:
                    Table(fk_ref_table, metadata, Column(fk_ref_pk, pk_col_type, primary_key=True), extend_existing=True)

        for name, typ in cls.__fields__:
            # determine SQL column type
            col_type = PY_TO_SQLA.get(typ, String)

            # determine if this column is a primary key
            is_pk = name == 'id' or (primary_key and name == primary_key and not has_pk)
            is_fk = (name in cls._foreign_key_names)
            is_nullable = (name in cls._nullable_keys) and not is_pk
            is_unique = name in unq_set
            use_auto_timestamp = name in cls._timestamp_keys and not is_pk and not is_fk
            kwargs = {"primary_key": is_pk, "nullable": is_nullable, "unique": is_unique}

            # collect column positional args (type, optional ForeignKey)
            col_args = [col_type]

            # if this field is registered as a foreign key, add ForeignKey constraint
            if is_fk and hasattr(typ, "__table_name__"):
                fk_options = cls.__fk_options__.get(name, {})
                ref_table = getattr(typ, "__table_name__", None) or typ.__name__.lower()
                ref_pk = getattr(typ, "__primary_key__", "id")
                col_args.append(ForeignKey(f"{ref_table}.{ref_pk}", **fk_options))
            if use_auto_timestamp:
                kwargs["server_default"] = text("CURRENT_TIMESTAMP")
            columns.append(Column(name, *col_args, **kwargs))

            if is_pk:
                has_pk = True

        if not has_pk:
            # Ensure at least one primary key
            columns.insert(0, Column("id", Integer, primary_key=True, autoincrement=True))

        # Create main table with the same metadata so FK resolution works
        table = Table(table_name, metadata, *columns)

        # Pick dialect
        inserts = None
        if dialect == "sqlite":
            dialect_obj = sqlite.dialect()
            inserts = sqlite.insert
        elif dialect == "postgresql":
            dialect_obj = postgresql.dialect()
        elif dialect == "mysql":
            dialect_obj = mysql.dialect()
        else:
            raise ValueError(f"Unsupported dialect: {dialect}")

        cls._sql_create_table = str(CreateTable(table, if_not_exists=True).compile(dialect=dialect_obj))
        return cls._sql_create_table

    @classmethod
    def generate_date(cls, date_value: str = None) -> datetime:
        from pyonir.core.utils import deserialize_datestr
        return deserialize_datestr(date_value or datetime.now())

    @classmethod
    def generate_id(cls) -> str:
        return uuid.uuid4().hex

def generate_sqlite_upsert(table, insert, dialect, returning_cols) -> str:
    """
    Generates a reusable SQLite UPSERT string with placeholders.
    Targets the Primary Key for conflicts and updates all other columns.
    """
    # 1. Create the base insert
    stmt = insert(table)

    # 2. Identify the Primary Key columns for 'index_elements'
    pk_columns = [col.name for col in table.primary_key]

    if returning_cols:
        target_return = [table.c[col] for col in returning_cols]
    else:
        target_return = [table.c[name] for name in pk_columns]

    # 3. Identify columns to update (everything NOT in the primary key)
    update_columns = {
        col.name: stmt.excluded[col.name]
        for col in table.columns if not col.primary_key
    }

    # 4. Construct the full Upsert with RETURNING
    upsert_stmt = (
        stmt.on_conflict_do_update(
            index_elements=pk_columns,
            set_=update_columns
        )
        .returning(*target_return)
    )

    # 5. Compile to string using the SQLite dialect
    return str(upsert_stmt.compile(
        dialect=dialect,
        compile_kwargs={"render_postcompile=True": True}
    ))

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
