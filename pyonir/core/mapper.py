import os, json, inspect
from dataclasses import dataclass
from datetime import datetime
from enum import EnumType, Enum
from types import UnionType, NoneType
from typing import get_type_hints, Any, Tuple, List, Type, Optional
from typing import get_origin, get_args, Union, Callable, Mapping, Iterable, Generator
from collections.abc import Iterable as ABCIterable, Mapping as ABCMapping, Generator as ABCGenerator
from sqlmodel import SQLModel

from pyonir.core.parser import DeserializeFile, parse_lookup_path
from pyonir.core.utils import get_attr, deserialize_datestr


def is_iterable(tp):
    origin = get_origin(tp) or tp
    return isinstance(origin, type) and issubclass(origin, ABCIterable) and not issubclass(origin, (str, bytes))

def is_generator(tp):
    origin = get_origin(tp) or tp
    return isinstance(origin, type) and issubclass(origin, ABCGenerator)

def is_mappable_type(tp):
    if tp == dict: return True
    origin = get_origin(tp)
    return isinstance(origin, type) and issubclass(origin, ABCMapping)

def is_scalar_type(tp):
    sclrs = (int, float, str, bool, EnumType)
    return tp in sclrs or (isinstance(tp, type) and issubclass(tp, sclrs))

def is_custom_class(tp):
    return isinstance(tp, type) and not tp.__module__ == "builtins"

is_sqlmodel_field = lambda t: callable(getattr(t,'default_factory', None))
is_sqlmodel = lambda t: isinstance(t, type) and issubclass(t, SQLModel)

@dataclass(slots=True)
class UnwrappedType:
    base: Union['Graphiti', 'BaseSchema', None, Type[Any]]
    args: Optional[Tuple['UnwrappedType']]
    optional: bool
    kind: str  # "scalar" | "iterable" | "mapping" | "generator" | "union"
    union: Optional[tuple["UnwrappedType"]] = None
    is_fk: bool = False
    is_pk: bool = False
    is_lookup: bool = False
    is_unique: bool = False
    column_name: Optional[str] = None
    mapper_fn: Optional[Callable] = None
    default_fn: Optional[Callable] = None
    _default_value: Optional[Any] = None
    is_graphiti: bool = False
    is_schema: bool = False

    def __str__(self):
        base_name = getattr(self.base, "__name__", str(self.base))
        return (
            f"UnwrappedType("
            f"column_name={self.column_name}, "
            f"base={base_name}, "
            f"kind={self.kind}, "
            f"optional={self.optional}"
            f")"
        )

    def __repr__(self):
        return self.__str__()

    @property
    def is_private(self):
        return self.column_name[0] == '_' if self.is_schema else False

    @property
    def is_empty(self):
        return inspect.Parameter.empty in (self._default_value, self.default_fn)

    @property
    def default_value(self):
        if self.is_empty: return None
        return self.default_fn() if self.default_fn else self._default_value

    @property
    def table_name(self) -> str:
        return self.base.__table_name__ if self.base and hasattr(self.base, '__table_name__') else ''

    @property
    def is_optional(self) -> bool:
        return self.optional

    @property
    def is_scalar(self) -> bool:
        return self.kind == "scalar"

    @property
    def is_datetime(self) -> bool:
        return self.kind == "datetime"

    @property
    def is_iterable(self) -> bool:
        return self.kind == "iterable"

    @property
    def is_mapping(self) -> bool:
        return self.kind == "mapping"

    @property
    def is_object(self) -> bool:
        return self.kind == "object"

    @property
    def is_union(self) -> bool:
        return self.kind == "union"

    def verify_type(self, value: Any, enforce_type: bool = False) -> Any:
        value = self.default_value if value is None else value
        err_msg = f"{self.base} Expected {self.column_name} value type of {self.base}, got {type(value)}"
        try:
            if not self.is_empty:
                return value
            # if self.is_required and not has_param:
            #     raise AttributeError(err_msg)
            if not self.is_optional and value is None:
                raise ValueError(err_msg)
            if enforce_type and not self.is_union and not isinstance(value, self.base):
                raise TypeError(err_msg)
            return value
        except Exception as e:
            raise

    def coerce_value(self, value: Any, enforce_type: bool = False, skip_coerce: bool = False) -> Any:
        if skip_coerce: return value
        ft = self.base
        ft_params = self.args
        value = self.verify_type(value, enforce_type=enforce_type)

        if is_sqlmodel_field(value):
            return value.default_factory()

        if self.is_union:
            last_error = None
            for ut in self.union:
                try:
                    return ut.coerce_value(value, enforce_type=True)
                except Exception as e:
                    last_error = e
            raise TypeError(f"Value {value} does not match any union types") from last_error

        has_container_type = isinstance(value, ft)
        if (has_container_type and self.is_scalar) or (self.is_optional and value is None):
            return value

        if self.is_optional and (value is None or value == ''):
            return None

        if self.is_datetime:
            return deserialize_datestr(value)

        if self.is_scalar:
            if not has_container_type and enforce_type:
                raise TypeError(f"{self.column_name} Expected type {ft} for value {value}, got {type(value)}")
            if not has_container_type and self.mapper_fn:
                return self.mapper_fn(value)
            return self.base(value) if value is not None else None

        if self.is_object:
            if self.is_fk and isinstance(value, str):
                from pyonir import Site
                app_ctx = Site.app_ctx if Site else []
                data_dir = Site.datastore_dirpath if Site else ''
                _input_value = lookup_fk(value, data_dir, app_ctx, self.is_lookup)
                return dto_mapper(_input_value, self)
            return value if has_container_type else dto_mapper(value, self, is_fk=self.is_fk)

        if self.is_mapping:
            if not ft_params and has_container_type: return value
            if not has_container_type:
                if enforce_type:
                    raise TypeError(f"Expected type {ft} for value {value}, got {type(value)}")
                return value

            coerced_value = ft()
            key_type, value_type = ft_params
            for k, v in value.items():
                has_key_type = key_type.coerce_value(k)
                has_value_type = value_type.coerce_value(v)
                coerced_value[has_key_type] = has_value_type

            return coerced_value

        if self.is_iterable:
            if not ft_params and has_container_type: return value
            if not has_container_type:
                if enforce_type:
                    raise TypeError(f"Expected parameter '{self.column_name}' type {ft} for value {value}, got {type(value)}")
                return self.default_value or None
            coerced_value = ft()
            for v in value:
                value_type: UnwrappedType = ft_params[0] if ft_params else any
                _v = value_type.coerce_value(v, enforce_type=enforce_type)
                coerced_value.append(_v)

            return coerced_value

def unwrap_fn_params(func: Callable, skip_types: list = None) -> List[UnwrappedType]:
    sig = inspect.signature(func)
    res = []
    for name, param in sig.parameters.items():
        param_type = param.annotation if param.annotation is not inspect.Parameter.empty else Any
        res.append(unwrap_type(param_type, column_name=name, default=param.default, skip_types=skip_types))

    return res

def unwrap_type(tp, column_name: str = None, default: Callable | Any = None, skip_types: list = None) -> UnwrappedType:
    from pyonir.core.schemas import BaseSchema, Graphiti

    origin = get_origin(tp) or tp
    is_union = origin is Union or isinstance(tp, UnionType)
    skip_type_args = tp in skip_types if skip_types else False
    is_cls = is_custom_class(tp)
    is_scalr = is_scalar_type(tp)
    is_graf = isinstance(tp, Graphiti)
    is_schema = issubclass(tp, BaseSchema) if is_cls and not is_union else False
    has_args = hasattr(tp, '__params__')
    is_date = tp is datetime if not is_union else False
    args = tuple() if skip_type_args \
        else tp.schema_columns() if is_schema \
        else tp.__params__ if has_args \
        else normalize_types(tp) if is_cls \
        else get_args(tp)
    mapper_fn = getattr(tp, f"map_to_{column_name}", None)

    base = origin
    kind = "scalar" if is_scalr else f"unknown unwrapped type {type(tp)}"
    union = None

    if not mapper_fn: # mapper methods are passed arguments
        if hasattr(base, 'from_value'):
            mapper_fn = base.from_value

    is_empty = default is inspect.Parameter.empty
    if default and hasattr(default, 'default_factory'):
        default = default.default_factory
    default_fn = inspect.Parameter.empty if is_empty else default if callable(default) else None
    _default_value = inspect.Parameter.empty if is_empty else default if not default_fn else None
    optional = is_optional_type(tp) or NoneType in args or any((_default_value, default_fn))

    # --- Union / Optional ---
    if is_union:
        union_args = tuple(unwrap_type(a,column_name=column_name, default=default, skip_types=skip_types) for a in args if a is not type(None))

        # Collapse single-type unions
        if len(union_args) == 1:
            single = union_args[0]
            single.optional = optional
            return single

        return UnwrappedType(
            base=None,
            args=None,
            optional=optional,
            kind="union",
            union=union_args,
            mapper_fn=mapper_fn,
            default_fn=default_fn,
            _default_value=_default_value,
            column_name=column_name,
            is_schema=is_schema,
            is_graphiti=is_graf,
        )

    # --- Classification ---
    if is_mappable_type(tp):
        kind = "mapping"
        args = tuple(unwrap_type(a) for a in args)

    elif is_iterable(tp):
        kind = "iterable"
        args = tuple(unwrap_type(a) for a in args)

    elif is_generator(tp):
        kind = "generator"

    elif is_date:
        kind = "datetime"

    elif not is_scalr and (is_graf or is_schema or is_cls):
        kind = "object"
        if not is_graf:
            # cache args for faster post processing
            setattr(base, '__params__', args)


    # --- Single construction point ---
    return UnwrappedType(
        base=base,
        args=args,
        optional=optional,
        kind=kind,
        union=union,
        mapper_fn=mapper_fn,
        default_fn=default_fn,
        _default_value=_default_value,
        column_name=column_name,
        is_schema=is_schema,
        is_graphiti=is_graf,
    )


def is_optional_type(tp):
    return get_origin(tp) is Union and type(None) in get_args(tp)

def normalize_types(cls: Type) -> list[UnwrappedType]:
    params = {}
    is_private = lambda k: k[0]=='_'
    # walk inheritance chain
    for base in reversed(cls.__mro__):
        hints = get_type_hints(base) or getattr(base.__init__, "__annotations__", {})

        for name, typ in hints.items():
            if is_private(name): continue
            default = getattr(base, name, inspect.Parameter.empty)
            ut = unwrap_type(typ, column_name=name, default=default)
            params[name] = ut

    return list(params.values())

# def _normalize_types(t: Type) -> list[UnwrappedType]:
#     hints = get_type_hints(t)
#     try:
#         init_hints = get_type_hints(t.__init__)
#         hints.update(init_hints)
#         if hints.get('return'):
#             del hints['return']
#     except Exception as exc:
#         pass
#     is_private = lambda k: k[0]=='_'
#
#     foreign_fields = list(hints.keys())
#     local_fields = list(t.__annotations__.keys()) if hasattr(t, '__annotations__') else []
#
#     for foreign_field in foreign_fields:
#         if is_private(foreign_field): continue
#         if foreign_field not in local_fields:
#             # includes fields from extended classes, but prioritizes local fields in case of name conflicts
#             local_fields.append(foreign_field)
#
#     return [unwrap_type(hints.get(k), column_name=k, default=getattr(t, k, None)) for k in local_fields]

def set_attr(target: object, attr: str, value: Any):
    if isinstance(target, dict):
        target.update({attr: value})
    else:
        setattr(target, attr, value)

def func_request_mapper(func: Callable, pyonir_request: 'PyonirRequest',*, enforce_type_checker: bool = False) -> dict:
    """Map request data to function parameters"""
    from pyonir import Pyonir, PyonirRequest
    from pyonir.core.security import PyonirSecurity
    from starlette.websockets import WebSocket

    input_args = pyonir_request.request_input.body or {}
    params_types = unwrap_fn_params(func, skip_types=[Pyonir, PyonirRequest, PyonirSecurity])
    param_args = {}
    for param in params_types:
        param_type = param.base
        param_name = param.column_name
        if param_type in (Pyonir, PyonirRequest):
            target_value = pyonir_request.pyonir_app if param_type == Pyonir else pyonir_request
        elif issubclass(param_type, PyonirSecurity):
            target_value = param_type(pyonir_request)
        elif param_type == WebSocket:
            target_value = pyonir_request.server_request
        else:
            value = input_args.get(param_name)
            skip_coerce = not param.is_empty and param_name not in input_args # Only skip coerce step when parameter has default value
            target_value = param.coerce_value(value, enforce_type=enforce_type_checker, skip_coerce=skip_coerce)
        set_attr(param_args, param_name, target_value)
    return param_args

def lookup_fk(value: str, data_dir: str, app_ctx: list, ignore_attr_path: bool = False):
    is_json = value.strip().startswith(('{','[')) if isinstance(value, str) else False
    lookup_path, query_params, has_attr_path, is_caller = parse_lookup_path(value, base_path=data_dir)
    if lookup_path:
        is_file_path = os.path.exists(lookup_path)
        value = DeserializeFile(lookup_path, app_ctx=app_ctx) if is_file_path else value
        if has_attr_path and not ignore_attr_path:
            value = get_attr(value, has_attr_path)
    if is_json:
        value = json.loads(value)
    return value

def dto_mapper(input_value: Union[Any, DeserializeFile], cls: Union['BaseSchema', UnwrappedType, type], is_fk: bool = False) -> object:
    from .schemas import BaseSchema
    is_file = isinstance(input_value, DeserializeFile)

    # Normalize output type
    unwrapped_type: UnwrappedType = cls if isinstance(cls, UnwrappedType) else unwrap_type(cls)

    if unwrapped_type.mapper_fn:
        return unwrapped_type.mapper_fn(input_value)

    if unwrapped_type.is_scalar:
        return unwrapped_type.coerce_value(input_value)

    if unwrapped_type.is_graphiti:
        return unwrapped_type.base.create(input_value.data if is_file else input_value)

    if unwrapped_type.is_schema or unwrapped_type.is_object:
        # assign primary fields
        processed = set()

        cls_args = {}
        field_hints: tuple[UnwrappedType] = unwrapped_type.args
        alias_keymap = unwrapped_type.base.__alias__ if hasattr(unwrapped_type.base, '__alias__') else {}
        is_frozen = unwrapped_type.base.__frozen__ if hasattr(unwrapped_type.base, '__frozen__') else False

        # normalize data source
        file_pkv = get_attr(input_value, 'data.__primary_key_value__') or None
        nested_key = getattr(cls, '__nested_field__', None)
        nested_data = get_attr(input_value, nested_key) if nested_key else {}
        data = get_attr(input_value, 'data') or {}
        vectors = (nested_data, data, input_value)

        for hint in field_hints:
            name = hint.column_name
            if hint.is_private: continue
            value = None
            alias_key = get_attr(alias_keymap, name, None)
            for vector in vectors:
                value = get_attr(vector, alias_key or name)
                if value is not None: break
            value = hint.coerce_value(value, enforce_type=False)
            set_attr(cls_args, name, value)
            processed.add(name)

        res: BaseSchema = unwrapped_type.base(**cls_args)
        if is_file:
            if unwrapped_type.is_schema: res.set_primary_key(file_pkv)
            res._file_path = input_value.file_path

        if not is_frozen:
            for key, value in data.items():
                if isinstance(getattr(cls, key, None), property): continue  # skip properties
                if not value or key in processed or key[0] == '_': continue  # skip private or declared attributes
                setattr(res, key, value)
    else:
        raise TypeError(f"Unknown mapper type {unwrapped_type}")
    return res

def dict_to_class(data: dict, name: Union[str, callable] = None, deep: bool = True) -> object:
    """
    Converts a dictionary into a class object with the given name.

    Args:
        data (dict): The dictionary to convert.
        name (str): The name of the class.
        deep (bool): If True, convert all dictionaries recursively.
    Returns:
        object: An instance of the dynamically created class with attributes from the dictionary.
    """
    # Dynamically create a new class
    cls = type(name or 'T', (object,), {}) if not callable(name) and deep!='update' else name

    # Create an instance of the class
    instance = cls() if deep!='update' else cls
    setattr(instance, 'update', lambda d: dict_to_class(d, instance, 'update') )
    # Assign dictionary keys as attributes of the instance
    for key, value in data.items():
        if isinstance(getattr(cls, key, None), property): continue
        if deep and isinstance(value, dict):
            value = dict_to_class(value, key)
        setattr(instance, key, value)

    return instance
