import os, json, inspect
from dataclasses import dataclass
from datetime import datetime
from enum import EnumType, Enum
from types import UnionType
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
    union: Optional[List["UnwrappedType"]] = None
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
    def default_value(self):
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

    def coerce_value(self, value: Any, enforce_type: bool = False) -> Any:
        ft = self.base
        ft_params = self.args
        value = self.default_value if value is None else value

        if is_sqlmodel_field(value):
            return value.default_factory()

        if self.is_union:
            last_error = None
            for ut in self.union:
                try:
                    return ut.coerce_value(value, enforce_type=True)
                    # return _verify_type(ut, value, enforce_type=enforce_type)
                except Exception as e:
                    last_error = e
            raise TypeError(f"Value {value} does not match any union types") from last_error

        has_container_type = isinstance(value, ft)
        if (has_container_type and self.is_scalar) or (self.is_optional and value is None):
            return value

        if self.is_datetime:
            return deserialize_datestr(value)

        if self.is_optional and value is None:
            return None

        if self.is_scalar:
            if not has_container_type and enforce_type:
                raise TypeError(f"Expected type {ft} for value {value}, got {type(value)}")
            return self.base(value) if value is not None else None
            # return _convert_type(value, self)

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
        param_default = param.default if param.default is not inspect.Parameter.empty else None
        res.append(unwrap_type(param_type, column_name=name, default=param_default, skip_types=skip_types))

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
    args = None if skip_type_args \
        else tp.schema_columns() if is_schema \
        else tp.__params__ if has_args \
        else normalize_types(tp) if is_cls \
        else get_args(tp)
    optional = is_optional_type(tp)
    mapper_fn = getattr(tp, f"map_to_{column_name}", None)

    base = origin
    kind = "scalar" if is_scalr else f"unknown unwrapped type {type(tp)}"
    union = None

    if not mapper_fn: # mapper methods are passed arguments
        if hasattr(base, 'from_value'):
            mapper_fn = base.from_value

    if default and hasattr(default, 'default_factory'):
        default = default.default_factory
    default_fn = default if callable(default) else None
    default_value = default if not callable(default) else None

    # --- Union / Optional ---
    if is_union:
        union_args = [
            unwrap_type(a, column_name=column_name, default=default, skip_types=skip_types)
            for a in get_args(tp)
            if a is not type(None)
        ]

        # Collapse single-type unions
        if len(union_args) == 1:
            single = union_args[0]
            single.optional = optional
            return single
            # return UnwrappedType(
            #     base=single.base,
            #     args=single.args,
            #     optional=True if optional else single.optional,
            #     kind=single.kind,
            #     union=None,
            #     default_fn=default_fn,
            #     _default_value=default_value,
            #     column_name=column_name,
            #     is_schema=is_schema,
            #     is_graphiti=is_graf,
            # )

        return UnwrappedType(
            base=None,
            args=None,
            optional=optional,
            kind="union",
            union=union_args,
            mapper_fn=mapper_fn,
            default_fn=default_fn,
            _default_value=default_value,
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
        _default_value=default_value,
        column_name=column_name,
        is_schema=is_schema,
        is_graphiti=is_graf,
    )

def unwrap_optional(tp):
    """Unwrap Optional[T] → T, else return tp unchanged"""
    origin_tp = get_origin(tp)
    if is_mappable_type(origin_tp):
        arg_tuple = get_args(tp)
        key_tp, value_tp = arg_tuple if len(arg_tuple) == 2 else (None, None)
        return origin_tp, key_tp, get_args(value_tp)
    if is_iterable(origin_tp):
        value_tps = get_args(tp)
        return origin_tp, None, value_tps
    if origin_tp is Union or isinstance(tp, UnionType):
        args = [unwrap_optional(a) for a in get_args(tp) if a is not type(None)]
        if len(args):
            args = args[0]
            return args[0], None, args[1]
            # res = [arg for arg, *rest in args]
    return tp, None, None

def is_optional_type(tp):
    return get_origin(tp) is Union and type(None) in get_args(tp)

def normalize_types(t: Type) -> list[UnwrappedType]:
    hints = get_type_hints(t)
    try:
        init_hints = get_type_hints(t.__init__)
        hints.update(init_hints)
        if hints.get('return'):
            del hints['return']
    except Exception as exc:
        pass
    is_private = lambda k: k[0]=='_'

    foreign_fields = list(hints.keys())
    local_fields = list(t.__annotations__.keys()) if hasattr(t, '__annotations__') else []

    for foreign_field in foreign_fields:
        if is_private(foreign_field): continue
        if foreign_field not in local_fields:
            # includes fields from extended classes, but prioritizes local fields in case of name conflicts
            local_fields.append(foreign_field)

    return [unwrap_type(hints.get(k), column_name=k, default=getattr(t, k, None)) for k in local_fields]

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

    default_args = pyonir_request.request_input.body or {}
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
            value = default_args.get(param_name)
            target_value = param.coerce_value(value, enforce_type=enforce_type_checker)
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

        res: 'BaseSchema' = unwrapped_type.base(**cls_args)
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


# def _convert_type(value: any, target_type: Type) -> any:
#     """Converts the value to the target type if possible."""
#     try:
#         if issubclass(target_type, datetime):
#             return deserialize_datestr(value)
#         if hasattr(target_type, 'from_value') and callable(getattr(target_type, 'from_value')):
#             return target_type.from_value(value)
#         if isinstance(value, target_type):
#             return value
#         return value
#     except Exception as e:
#         raise TypeError(f"Failed to convert value '{value}' of type {type(value).__name__} to {target_type.__name__}: {e}")

# class CoercionPolicy(Enum):
#     STRICT = "strict"        # no coercion
#     RELAXED = "relaxed"      # safe coercions only

# def _verify_type(unwrapped_type: UnwrappedType, value: any, enforce_type: bool = True) -> Optional[any]:
#     """Checks if the value matches any of the provided field types, including handling for generic container types."""
#
#     if unwrapped_type.is_optional and value is None:
#         return None
#
#     if unwrapped_type.is_union:
#         last_error = None
#         for ut in unwrapped_type.union:
#             try:
#                 return _verify_type(ut, value, enforce_type=enforce_type)
#             except Exception as e:
#                 last_error = e
#         raise TypeError(f"Value {value} does not match any union types") from last_error
#
#     ft = unwrapped_type.base
#     ft_params = unwrapped_type.args
#     has_container_type = isinstance(value, ft)
#     value = unwrapped_type.default_value if value is None else value
#
#     if unwrapped_type.is_object:
#         return dto_mapper(value, ft, is_fk=unwrapped_type.is_fk)
#
#     if unwrapped_type.is_scalar:
#         return _convert_type(value, ft)
#
#     if unwrapped_type.is_mapping:
#         if not ft_params and has_container_type: return value
#         if not has_container_type:
#             if enforce_type:
#                 raise TypeError(f"Expected type {ft} for value {value}, got {type(value)}")
#             return value
#
#         coerced_value = ft()
#         key_type, value_type = ft_params if ft_params else (any, any)
#         for k, v in value.items():
#             has_key_type = isinstance(k, key_type)
#             has_value_type = isinstance(v, value_type)
#             if not all([has_key_type, has_value_type]) and enforce_type:
#                 raise TypeError(f"Expected dict with keys of type {ft_params[0].__name__} and values of type {ft_params[1].__name__}, got {type(value)} with key type {type(k)} and value type {type(v)}")
#             v = _convert_type(v, ft_params[1])
#             coerced_value[key_type(k)] = v
#
#         return coerced_value
#
#     if unwrapped_type.is_iterable:
#         if not ft_params and has_container_type: return value
#         if not has_container_type:
#             if enforce_type:
#                 raise TypeError(f"Expected parameter '{unwrapped_type.column_name}' type {ft} for value {value}, got {type(value)}")
#             return unwrapped_type.default_value or None
#         coerced_value = ft()
#         for v in value:
#             value_type = ft_params[0] if ft_params else any
#             has_item_type = isinstance(v, value_type)
#             if not has_item_type and enforce_type:
#                 raise TypeError(f"Expected iterable of {value_type.__name__}, got {type(value)} with item type {type(v)}")
#             _v = _convert_type(v, value_type)
#             coerced_value.append(_v)
#
#         return coerced_value

