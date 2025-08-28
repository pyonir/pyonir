from typing import get_type_hints
from typing import get_origin, get_args, Union, Callable, Mapping, Iterable, Generator
from collections.abc import Iterable as ABCIterable, Mapping as ABCMapping, Generator as ABCGenerator

from pyonir.utilities import get_attr


def is_iterable(tp):
    origin = get_origin(tp) or tp
    return isinstance(origin, type) and issubclass(origin, ABCIterable) and not issubclass(origin, (str, bytes))

def is_generator(tp):
    origin = get_origin(tp) or tp
    return isinstance(origin, type) and issubclass(origin, ABCGenerator)

def is_mappable_type(tp):
    if tp == dict: return True
    origin = get_origin(tp)
    args = get_args(tp)
    return isinstance(origin, type) and issubclass(origin, ABCMapping)

def is_scalar_type(tp):
    return tp in (int, float, str, bool)

def is_custom_class(tp):
    return isinstance(tp, type) and not tp.__module__ == "builtins"

def unwrap_optional(tp):
    """Unwrap Optional[T] → T, else return tp unchanged"""
    origin_tp = get_origin(tp)
    if is_mappable_type(origin_tp):
        key_tp, value_tp = get_args(tp)
        return origin_tp, key_tp, unwrap_optional(value_tp)
    if is_iterable(origin_tp):
        value_tps = get_args(tp)
        return origin_tp, value_tps
    if origin_tp is Union:
        args = [a for a in get_args(tp) if a is not type(None)]
        if len(args):
            return args
    return tp, None

def is_callable_type(tp):
    return get_origin(tp) is Callable

def is_optional_type(tp):
    return get_origin(tp) is Union and type(None) in get_args(tp)

def is_option_type(t):
    if get_origin(t) is not Union: return t
    return [arg for arg in get_args(t) if arg is not type(None)][0]

def coerce_union(t, v):
    try:
        return t(v)
    except Exception as exc:
        print(f"failed to coerce {v} into {t}")
        return None

def add_props_to_object(res, data, file_src=None):
    itr = [*data.keys(), *(file_src.default_file_attributes if file_src else [])]
    for key in itr:
        if key[0] == '_': continue
        # if frozen and not hasattr(res, key): continue
        # if isinstance(val, property): continue
        value = get_attr(data, key) or get_attr(file_src, key)
        setattr(res, key, value)
    return res

def cls_mapper(file_obj: object, cls: Union[type, list[type]], from_request=None):
    """Recursively map dict-like input into `cls` with type-safe field mapping."""
    from pyonir.core import PyonirRequest, PyonirApp

    if hasattr(cls, '__skip_parsely_deserialization__'):
        return file_obj

    # Union types
    if isinstance(cls, list):
        _value = None
        for ct in cls:
            if isinstance(file_obj, ct):
                _value = ct(file_obj)
            if _value is not None: break
            _value = coerce_union(ct, file_obj)
        return _value

    # Scalars just wrap
    if is_scalar_type(cls):
        return cls(file_obj)

    is_generic_type = cls.__name__ == 'GenericQueryModel'
    param_type_map = get_type_hints(cls)
    data = get_attr(file_obj, 'data', {}) or {}

    # Merge nested access if ORM opts define mapper_key
    orm_opts = getattr(cls, "_orm_options", {})
    mapper_keys = orm_opts.get("mapper", {})
    is_frozen = orm_opts.get("frozen")
    access_path_to_nested = '.'.join(['data', orm_opts.get('mapper_key', cls.__name__.lower())])
    nested_value = get_attr(file_obj, access_path_to_nested)
    if nested_value:
        data.update(**nested_value)

    cls_args = cls() if is_generic_type else {}
    for name, hint in param_type_map.items():
        # name = get_attr(mapper_keys, name, None) or name
        if name.startswith("_") or name == "return":
            continue

        actual_type, *mapable = unwrap_optional(hint)
        value = get_attr(data, name) or get_attr(file_obj, name)
        if value is None:
            cls_args[name] = None
            continue
        # Handle Special Pyonir objects
        if from_request and hint in (PyonirApp, PyonirRequest):
            from pyonir import Site
            value = Site if hint == PyonirApp else from_request
            cls_args[name] = value
            continue
        if from_request and hint == value:
            cls_args[name] = None
            continue

        # Handle containers
        if is_mappable_type(actual_type) and len(mapable) and mapable[0]:
            key_type, value_types = mapable
            vtype = value_types[0] if len(value_types) == 1 else None
            cls_args[name] = {key_type(k): cls_mapper(v, vtype or value_types) for k, v in value.items()} #if vtype else actual_type(value)

        elif is_iterable(actual_type):
            itypes = mapable[0] if len(mapable) == 1 else mapable
            itype = itypes[0] if itypes and len(itypes) == 1 else None
            cls_args[name] = [cls_mapper(v, itype) for v in value] if itype else value if isinstance(value, actual_type) else actual_type(value)

        elif is_callable_type(actual_type):
            cls_args[name] = value

        elif callable(value) or isinstance(value, actual_type):
            cls_args[name] = value
        elif is_custom_class(actual_type):
            cls_args[name] = cls_mapper(value, actual_type)

        else:
            try:
                cls_args[name] = actual_type(value)
            except Exception as e:
                cls_args[name] = value # fallback if constructor fails

    # Methods passed from request are returned to be called later
    if callable(cls) and from_request:
        return cls_args

    res = cls() if is_generic_type else cls(**cls_args)
    # Pass additional fields that are not specified on model
    if is_generic_type:
        res = add_props_to_object(res, data, file_src=file_obj)

    if not is_frozen:
        for key, value in data.items():
            if isinstance(getattr(cls, key, None), property):
                continue  # skip properties
            if param_type_map.get(key) or key[0] == '_':
                continue  # skip private or declared attributes
            setattr(res, key, value)

    return res
    # return cls(**cls_args)
