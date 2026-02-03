import os, json
from datetime import datetime
from enum import EnumType
from types import UnionType
from typing import get_type_hints, Any, Tuple
from typing import get_origin, get_args, Union, Callable, Mapping, Iterable, Generator
from collections.abc import Iterable as ABCIterable, Mapping as ABCMapping, Generator as ABCGenerator

from sqlmodel import SQLModel

from pyonir.core.parser import DeserializeFile, LOOKUP_DATA_PREFIX
from pyonir.core.schemas import GenericQueryModel
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
    args = get_args(tp)
    return isinstance(origin, type) and issubclass(origin, ABCMapping)

def is_scalar_type(tp):
    sclrs = (int, float, str, bool, EnumType)
    return tp in sclrs or (isinstance(tp, type) and issubclass(tp, sclrs))

def is_custom_class(tp):
    return isinstance(tp, type) and not tp.__module__ == "builtins"

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

def coerce_unions(union_types: list[type], v: any):

    _value = None
    for utyp in union_types:
        if _value is not None: break
        try:
            _value = utyp(v)
        except Exception as exc:
            print(f"failed to coerce {v} into {utyp}")
            pass
    return _value


def collect_type_hints(t, public_only=True):
    hints = get_type_hints(t)
    try:
        init_hints = get_type_hints(t.__init__)
        hints.update(init_hints)
        if hints.get('return'):
            del hints['return']
    except Exception as exc:
        pass
    return {k:v for k,v in hints.items() if public_only and k[0]!='_'}

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

is_sqlmodel_field = lambda t: callable(getattr(t,'default_factory', None))
is_sqlmodel = lambda t: isinstance(t, type) and issubclass(t, SQLModel)

def func_request_mapper(func: Callable, pyonir_request: 'PyonirRequest') -> dict:
    """Map request data to function parameters"""
    from pyonir import PyonirRequest
    from pyonir import Pyonir
    from pyonir.core.authorizer import PyonirSecurity
    import inspect
    # param_type_map = collect_type_hints(func)
    default_args = pyonir_request.request_input.body
    # default_args.update(**pyonir_request.path_params.__dict__)
    # default_args.update(**pyonir_request.query_params.__dict__)
    # default_args.update(**pyonir_request.form)
    cls_args = {}


    sig = inspect.signature(func)
    hints = get_type_hints(func)
    params_info = {}

    for name, param in sig.parameters.items():
        param_type = hints.get(name, Any)
        param_value = default_args.get(name)
        default = (
            param.default if param.default is not inspect.Parameter.empty else None
        )
        if param_type in (Pyonir, PyonirRequest):
            param_value = pyonir_request.pyonir_app if param_type == Pyonir else pyonir_request
        elif issubclass(param_type, PyonirSecurity):
            param_value = param_type(pyonir_request)
        else:
            param_value = cls_mapper(param_value, param_type) if param_value else default
        set_attr(cls_args, name, param_value)
        params_info[name] = {"type": param_type, "default": param_value or default}

    return cls_args

def lookup_fk(value: str, data_dir: str, app_ctx: list):
    _, _, has_lookup = value.partition(LOOKUP_DATA_PREFIX+'/') if isinstance(value, str) else [None,None,None]
    value = DeserializeFile(os.path.join(data_dir, has_lookup), app_ctx=app_ctx) if has_lookup else json.loads(value) if isinstance(value, str) else value
    return value

def coerce_value_to_type(value: Any, target_type: Union[type, Tuple[type]], factory_fn: Callable = None) -> Any:
    """Coerce a value to the specified target type."""
    is_nullable = is_optional_type(target_type)
    actual_type, map_key_type, union_types = unwrap_optional(target_type) if not isinstance(target_type, tuple) else (None,None, target_type)
    if is_nullable and value is None:
        return None

    if union_types:
        _value = None
        if is_mappable_type(actual_type) and map_key_type:
            _value = {map_key_type(k): coerce_value_to_type(v, union_types) for k, v in value.items()}
        elif is_iterable(actual_type):
            _value = [coerce_value_to_type(v, union_types) for v in value]
        else:
            has_type = type(value) in union_types
            _value = value if has_type else coerce_unions(union_types, value)
        return _value
    # try:
    if isinstance(value, actual_type):
        return value
    # except TypeError:
    #     raise
    if value is None and callable(factory_fn):
        return factory_fn()
    elif value is None and is_sqlmodel_field(factory_fn):
        return factory_fn.default_factory()
    elif value is not None and is_scalar_type(actual_type):
        return actual_type(value) #if isinstance(value, actual_type) else value
    elif issubclass(actual_type, datetime):
        return deserialize_datestr(value)
    elif is_custom_class(actual_type):
        return cls_mapper(value, actual_type)
    else:
        return value

def cls_mapper(file_obj: Union[dict, DeserializeFile], cls: Union['BaseSchema', type], is_fk: bool = False) -> object:
    """Recursively map dict-like input into `cls` with type-safe field mapping."""
    from pyonir.core.schemas import BaseSchema
    from pyonir import Site
    app_ctx = Site.app_ctx if Site else []
    data_dir = Site.datastore_dirpath if Site else ''

    if hasattr(cls, '__skip_parsely_deserialization__'):
        return file_obj
    if is_fk and isinstance(file_obj, str):
        file_obj = lookup_fk(file_obj, data_dir, app_ctx)
        return cls_mapper(file_obj, cls)
    is_generic = isinstance(cls, GenericQueryModel)
    is_base = issubclass(cls, BaseSchema) if not is_generic else False
    cls_ins = cls() if is_base else {}
    field_hints = cls.__fields__ if is_base or is_generic else [(k,v) for k,v in collect_type_hints(cls).items()]
    alias_keymap = cls.__alias__ if hasattr(cls, '__alias__') else {}
    is_frozen = cls.__frozen__ if hasattr(cls, '__frozen__') else False
    fks = getattr(cls, '__foreign_keys__', set())
    # normalize data source
    nested_key = getattr(cls, '__nested_field__', None)
    nested_data = get_attr(file_obj, nested_key) or {}
    data = get_attr(file_obj, 'data') or {}

    # assign primary fields
    processed = set()
    for name, hint in field_hints:
        if name.startswith("_") or name == "return":
            continue
        name_alias = get_attr(alias_keymap, name, None)
        # access untyped value from data, file_obj, cls (in that order)
        for ds in (nested_data, data, file_obj, cls):
            value = get_attr(ds, name_alias or name)
            if value is not None: break

        if (name, hint) in fks:
            value = lookup_fk(value, data_dir, app_ctx)

        if value is None:
            set_attr(cls_ins, name, value)
            continue
        # Handle containers
        custom_mapper_fn = getattr(cls, f'map_to_{name}', None)
        if custom_mapper_fn:
            value = custom_mapper_fn(value)
        else:
            fn_factory = (value if callable(value) or is_sqlmodel_field(value) else None)
            if fn_factory:
                value = None
            value = coerce_value_to_type(value, hint, factory_fn=fn_factory)
        set_attr(cls_ins, name, value)
        processed.add(name)
    if is_generic:
        cls_ins.update({'file_name': get_attr(file_obj, 'file_name'),
                        'file_created_on': get_attr(file_obj, 'file_created_on')})
        return dict_to_class(cls_ins, 'GenericQueryModel')
    res = cls_ins if is_base else cls(**cls_ins)
    if not is_frozen:
        for key, value in data.items():
            if isinstance(getattr(cls, key, None), property): continue  # skip properties
            if key in processed or key[0] == '_': continue  # skip private or declared attributes
            setattr(res, key, value)
    return res if field_hints else coerce_value_to_type(file_obj, cls)

# def xcls_mapper(file_obj: object, cls: Union[type, list[type]], from_request=None):
#     """Recursively map dict-like input into `cls` with type-safe field mapping."""
#
#     from pyonir.core.schemas import BaseSchema
#
#     if hasattr(cls, '__skip_parsely_deserialization__'):
#         return file_obj
#
#     # Union types
#     if isinstance(cls, (list, tuple, set)):
#         _value = None
#         for ct in cls:
#             if isinstance(file_obj, ct):
#                 _value = ct(file_obj)
#             if _value is not None: break
#             _value = coerce_union(ct, file_obj)
#         return _value
#
#     if is_optional_type(cls) or isinstance(file_obj, cls):
#         return file_obj
#
#     # datetime passthrough
#     if cls == datetime and isinstance(file_obj, str):
#         return deserialize_datestr(file_obj)
#
#     # Scalars just wrap
#     if is_scalar_type(cls):
#         return cls(file_obj)
#     is_sqlmodel_field = lambda t: callable(getattr(value,'default_factory', None))
#     is_sqlmodel = lambda t: isinstance(t, type) and issubclass(t, SQLModel)
#     is_dclass = is_dataclass(cls) or len(required_parameters(cls)) > 0
#     is_generic_type = cls.__name__ == 'GenericQueryModel'
#     is_pyonirschema = issubclass(cls, BaseSchema)
#     param_type_map =  {k: field.annotation for k, field in cls.model_fields.items()} if is_sqlmodel(cls) else dict(cls.__fields__) if is_pyonirschema else collect_type_hints(cls)
#     data = get_attr(file_obj, 'data') or {}
#
#     # Merge nested access if ORM opts define mapper_key
#     orm_opts = getattr(cls, "_orm_options", {})
#     mapper_keys = orm_opts.get("mapper", {})
#     is_frozen = orm_opts.get("frozen")
#     access_path_to_nested = '.'.join(['data', orm_opts.get('mapper_key', cls.__name__.lower())])
#     nested_value = get_attr(file_obj, access_path_to_nested)
#     if nested_value:
#         data.update(**nested_value)
#
#     cls_args = {} if is_dclass else cls()
#     for name, hint in param_type_map.items():
#         mapper_name = get_attr(mapper_keys, name, None) #or name
#         if name.startswith("_") or name == "return":
#             continue
#
#         actual_type, *mapable = unwrap_optional(hint)
#         # value = None
#         for ds in (data, file_obj, cls): # try to get value from data, file_obj, cls (in that order)
#             value = get_attr(ds, mapper_name or name)
#             if value is not None: break
#
#         if value is None:
#             set_attr(cls_args, name, value)
#             continue
#
#         # Handle containers
#         custom_mapper_fn = getattr(cls, f'map_to_{name}', None)
#         if isinstance(value, actual_type):
#             pass
#         elif custom_mapper_fn:
#             value = custom_mapper_fn(value)
#         elif is_sqlmodel(hint):
#             value = cls_mapper(value, hint) if isinstance(value, dict) else value
#         elif is_sqlmodel_field(value):
#             value = value.default_factory()
#         elif is_scalar_type(actual_type):
#             value = actual_type(value)
#         elif is_callable_type(actual_type) or callable(value):
#             pass
#         elif is_mappable_type(actual_type) and len(mapable) and mapable[0]:
#             key_type, value_types = mapable
#             vtype = value_types[0] if len(value_types)==1 else None
#             value = {key_type(k): cls_mapper(v, vtype or value_types) for k, v in value.items()}
#         elif is_iterable(actual_type):
#             itypes = mapable[0] if len(mapable) == 1 else mapable
#             itype = itypes[0] if itypes and len(itypes) == 1 else None
#             value = [cls_mapper(v, itype) for v in value] if itype else value if isinstance(value, actual_type) else actual_type(value)
#         elif is_custom_class(actual_type):
#             value = cls_mapper(value, actual_type)
#         else:
#             try:
#                 value = actual_type(value)
#             except Exception as e:
#                 pass
#         set_attr(cls_args, name, value)
#
#     # Methods passed from request are returned to be called later
#     if callable(cls) and from_request:
#         return cls_args
#
#     res = cls(**cls_args) if is_dclass else cls_args
#     if is_generic_type:
#         data = file_obj if not data and isinstance(file_obj, dict) else data
#         keys = list(cls.__dict__.keys()) + ['file_name','file_created_on']
#         for key in keys:
#             if key[0] == '_': continue
#             _key = mapper_keys.get(key, key)
#             value = get_attr(data, _key or key) or get_attr(file_obj, _key or key)
#             set_attr(res, key, value)
#         return res
#
#     # Pass additional fields that are not specified on model
#     if not is_frozen and not is_sqlmodel(cls):
#         # keys = data.keys() if is_sqlmodel(cls) else data.model_fields.keys()
#         for key, value in data.items():
#             if isinstance(getattr(cls, key, None), property):
#                 continue  # skip properties
#             if param_type_map.get(key) or key[0] == '_':
#                 continue  # skip private or declared attributes
#             setattr(res, key, value)
#
#     return res

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
