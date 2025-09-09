from dataclasses import is_dataclass
from datetime import datetime
from typing import get_type_hints, Any
from typing import get_origin, get_args, Union, Callable, Mapping, Iterable, Generator
from collections.abc import Iterable as ABCIterable, Mapping as ABCMapping, Generator as ABCGenerator

from sqlmodel import SQLModel

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
        args = [unwrap_optional(a) for a in get_args(tp) if a is not type(None)]
        if len(args):
            res = [arg for arg, *rest in args]
            return res
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

def collect_type_hints(t):
    hints = get_type_hints(t)
    try:
        init_hints = get_type_hints(t.__init__)
        hints.update(init_hints)
        del hints['return']
    except Exception as exc:
        pass
    return hints

# def add_props_to_object(res, data: dict, file_src: object =None, attrs: list = None):
#     """Add all properties from data and file_src to res object"""
#     itr = [*data.keys(), *(attrs or [])]
#     for key in itr:
#         if key[0] == '_': continue
#         # if frozen and not hasattr(res, key): continue
#         # if isinstance(val, property): continue
#         value = get_attr(data, key) or get_attr(file_src, key)
#         setattr(res, key, value)
#     return res

def required_parameters(cls):
    import inspect
    sig = inspect.signature(cls.__init__)
    required = []
    for name, param in sig.parameters.items():
        if name in ("self","args","kwargs"):  # skip self, *args, **kwargs
            continue
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return required

def set_attr(target: object, attr: str, value: Any):
    if isinstance(target, dict):
        target.update({attr: value})
    else:
        setattr(target, attr, value)

def func_request_mapper(func: Callable, data: object) -> dict: pass

def cls_mapper(file_obj: object, cls: Union[type, list[type]], from_request=None):
    """Recursively map dict-like input into `cls` with type-safe field mapping."""
    from pyonir.core import PyonirRequest, PyonirApp

    if hasattr(cls, '__skip_parsely_deserialization__'):
        return file_obj

    # Union types
    if isinstance(cls, (list, tuple, set)):
        _value = None
        for ct in cls:
            if isinstance(file_obj, ct):
                _value = ct(file_obj)
            if _value is not None: break
            _value = coerce_union(ct, file_obj)
        return _value

    # datetime passthrough
    if cls == datetime:
        return file_obj

    # Scalars just wrap
    if is_scalar_type(cls):
        return cls(file_obj)
    is_sqlmodel = lambda t: isinstance(t, type) and issubclass(t, SQLModel)
    is_dclass = is_dataclass(cls) or len(required_parameters(cls)) > 0
    is_generic_type = cls.__name__ == 'GenericQueryModel'
    param_type_map =  {k: field.annotation for k, field in cls.model_fields.items()} if is_sqlmodel(cls) else collect_type_hints(cls)
    data = get_attr(file_obj, 'data') or {}

    # Merge nested access if ORM opts define mapper_key
    orm_opts = getattr(cls, "_orm_options", {})
    mapper_keys = orm_opts.get("mapper", {})
    is_frozen = orm_opts.get("frozen")
    access_path_to_nested = '.'.join(['data', orm_opts.get('mapper_key', cls.__name__.lower())])
    nested_value = get_attr(file_obj, access_path_to_nested)
    if nested_value:
        data.update(**nested_value)

    cls_args = {} if from_request or is_dclass else cls()
    for name, hint in param_type_map.items():
        mapper_name = get_attr(mapper_keys, name, None) #or name
        if name.startswith("_") or name == "return":
            continue

        actual_type, *mapable = unwrap_optional(hint)
        # value = None
        for ds in (data, file_obj, cls): # try to get value from data, file_obj, cls (in that order)
            value = get_attr(ds, mapper_name or name)
            if value is not None: break

        if value is None:
            set_attr(cls_args, name, value)
            continue
        # Handle Special Pyonir objects
        if from_request and hint in (PyonirApp, PyonirRequest):
            from pyonir import Site
            value = Site if hint == PyonirApp else from_request
            set_attr(cls_args, name, value)
            continue
        if from_request and hint == value:
            set_attr(cls_args, name, None)
            continue

        # Handle containers
        custom_mapper_fn = getattr(cls, f'map_to_{name}', None)
        if custom_mapper_fn:
            value = custom_mapper_fn(value)
        elif is_sqlmodel(hint):
            value = cls_mapper(value, hint) if isinstance(value, dict) else value
        elif is_scalar_type(actual_type):
            value = actual_type(value)
        elif is_callable_type(actual_type) or callable(value):
            pass
        elif is_mappable_type(actual_type) and len(mapable) and mapable[0]:
            key_type, value_types = mapable
            vtype = value_types[0] if len(value_types)==1 else None
            value = {key_type(k): cls_mapper(v, vtype or value_types) for k, v in value.items()}
        elif is_iterable(actual_type):
            itypes = mapable[0] if len(mapable) == 1 else mapable
            itype = itypes[0] if itypes and len(itypes) == 1 else None
            value = [cls_mapper(v, itype) for v in value] if itype else value if isinstance(value, actual_type) else actual_type(value)
        elif isinstance(value, actual_type):
            pass
        elif is_custom_class(actual_type):
            value = cls_mapper(value, actual_type)
        else:
            try:
                value = actual_type(value)
            except Exception as e:
                pass
        set_attr(cls_args, name, value)

    # Methods passed from request are returned to be called later
    if callable(cls) and from_request:
        return cls_args

    res = cls(**cls_args) if is_dclass else cls_args
    if is_generic_type:
        data = file_obj if not data and isinstance(file_obj, dict) else data
        keys = list(cls.__dict__.keys()) + ['file_name','file_created_on']
        for key in keys:
            if key[0] == '_': continue
            _key = mapper_keys.get(key, key)
            value = get_attr(data, _key or key) or get_attr(file_obj, _key or key)
            set_attr(res, key, value)
        return res

    # Pass additional fields that are not specified on model
    if not is_frozen and not is_sqlmodel(cls):
        # keys = data.keys() if is_sqlmodel(cls) else data.model_fields.keys()
        for key, value in data.items():
            if isinstance(getattr(cls, key, None), property):
                continue  # skip properties
            if param_type_map.get(key) or key[0] == '_':
                continue  # skip private or declared attributes
            setattr(res, key, value)

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
