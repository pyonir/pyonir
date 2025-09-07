from __future__ import annotations

import json
import os
import typing
from typing import Union, Generator, Iterable, Callable, Mapping, get_origin, get_args, get_type_hints, Any
from collections.abc import Iterable as ABCIterable
from datetime import datetime
from typing import Optional, Union
import pytz

from pyonir.pyonir_types import AppCtx, EnvConfig


def is_iterable(tp):
    if not isinstance(tp, Iterable): return False
    origin = get_origin(tp) or tp
    return issubclass(origin, ABCIterable)

def is_generator(tp):
    origin = get_origin(tp) or tp
    return issubclass(origin, Generator)

def is_mappable_type(tp) -> bool:
    origin = get_origin(tp)
    args = get_args(tp)

    # Check if the base is a Mapping (like dict) and it has two type arguments
    return (
        origin is not None and
        issubclass(origin, Mapping) and
        len(args) == 2
    )

def is_scalar_type(tp) -> bool:
    origin = get_origin(tp) or tp
    return origin in (int, float, str, bool)

def is_custom_class(t):
    return t.__init__.__annotations__ #isinstance(t, type) and not t.__module__ == "builtins"

def is_optional_type(t):
    if get_origin(t) is not Union: return t
    return [arg for arg in get_args(t) if arg is not type(None)][0]

def is_callable_type(pt) -> bool:
    return get_origin(pt) is Callable or pt.__name__=='callable'

def cls_mapper(file_obj: object, cls: typing.Callable, from_request: 'PyonirRequest' = None):
    from pyonir.core import PyonirRequest, PyonirApp
    param_name, param_type, param_value = ['','','']
    orm_opts = getattr(cls, "__orm_options", {})
    mapper_keys = orm_opts.get("mapper", {})
    try:
        if hasattr(cls, '__skip_parsely_deserialization__'):
            return file_obj

        param_type_map = get_type_hints(cls)
        is_generic = cls.__name__ == 'GenericQueryModel'

        if is_scalar_type(cls):
            return cls(file_obj)

        # mapper_keys = getattr(cls, "_mapper", {})
        data = get_attr(file_obj, 'data') or {}
        # access nested object using mapper_key
        _model_access_key = '.'.join(['data', orm_opts.get('mapper_key') or cls.__name__.lower()])
        kdata = get_attr(file_obj, _model_access_key)
        if kdata:
            data.update(**kdata)

        cls_args = {}
        res = cls() if is_generic else None

        # if hasattr(cls, 'from_dict'):  # allows manual mapping of class instance
        #     return cls.from_dict(data)

        # Build constructor args
        for param_name, param_type in param_type_map.items():
            param_type = is_optional_type(param_type)
            mapper_key = get_attr(mapper_keys, param_name) or param_name
            param_value = get_attr(data, mapper_key) or get_attr(file_obj, mapper_key)
            use_value = False

            if from_request and param_type in (PyonirApp, PyonirRequest):
                from pyonir import Site
                use_value = True
                param_value = Site if param_type == PyonirApp else from_request

            if (param_value == param_type) or param_value is None or param_name[0] == '_' or param_name == 'return':
                continue
            # param_value = is_optional_type(param_value) # unwrap optional types
            if is_callable_type(param_type):
                cls_args[mapper_key] = param_value
            elif is_iterable(param_type):
                iter_ptype = get_args(param_type)
                is_mapp = is_mappable_type(param_type)
                if is_mapp:
                    ktype, vtype = iter_ptype
                    is_list = is_iterable(vtype)
                    if is_list:
                        vtype = get_args(vtype)[0]
                    cls_args[param_name] = {
                        ktype(key): [cls_mapper(lval, vtype) for lval in value] if is_list else cls_mapper(value, vtype)
                        for key, value in param_value.items()
                    }
                else:
                    cls_args[param_name] = [cls_mapper(itm, iter_ptype[0]) for itm in param_value]
            else:
                is_typed = param_value == param_type
                is_instance = isinstance(param_value, param_type)
                is_option_null = is_optional_type(param_value) == param_type and from_request
                # if not use_value and is_instance and from_request:
                #     param_val = cls_mapper(from_request.form, param_type)
                #     print('debug???', param_type, param_name, param_val)
                should_spread = isinstance(param_value, dict)
                use_value = use_value or is_typed or is_instance
                v = (
                    param_value if use_value
                    else param_type(**param_value) if should_spread
                    else None if is_option_null else param_type(param_value)
                )
                cls_args[param_name] = v

        if from_request:
            return cls_args

        if not from_request and param_type_map:
            res = cls(**cls_args)

        # Generic class post-processing
        if is_generic:
            for key in cls.__dict__.keys():
                if key[0] == '_':
                    continue
                value = get_attr(data, key) or get_attr(file_obj, key)
                setattr(res, key, value)

        # ✅ Check ORM options for "frozen"
        if not orm_opts.get("frozen"):
            for key, value in data.items():
                if isinstance(getattr(cls, key, None), property):
                    continue  # skip properties
                if param_type_map.get(key) or key[0] == '_':
                    continue  # skip private or declared attributes
                setattr(res, key, value)

        return res

    except Exception as e:
        print(f"Cls Mapper failed to create a {cls.__name__} instance due to map '{param_name}' parameter wasn't a type of {param_type} : {type(param_value)}")
        raise


def process_contents(path, app_ctx=None, file_model: any = None) -> object:
    """Deserializes all files within the contents directory"""
    from pyonir.models.database import query_fs
    key = os.path.basename(path)
    res = type(key, (object,), {"__name__": key})() # generic map
    pgs = query_fs(path, app_ctx=app_ctx, model=file_model)
    for pg in pgs:
        name = getattr(pg, 'file_name')
        setattr(res, name, pg.map_to_model(None) if hasattr(pg, 'map_to_model') else pg)
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

def get_attr(rowObj, attrPath=None, default=None, rtn_none=True):
    """
    Resolves nested attribute or dictionary key paths.

    Args:
        obj: the root object
        attr_path: dot-separated string or list for nested access
        default: fallback value if the target is None or missing
        return_none: if True, returns `None` on missing keys/attrs instead of the original object

    Returns:
        The nested value, or `default`, or `obj` based on fallback rules.
    """
    if attrPath == None: return rowObj
    attrPath = attrPath if isinstance(attrPath, list) else attrPath.split('.')
    targetObj = None
    for key in attrPath:
        try:
            if targetObj:
                targetObj = targetObj[key]
            else:
                targetObj = rowObj.get(key)
            pass
        except (KeyError, AttributeError, TypeError) as e:
            if targetObj:
                targetObj = getattr(targetObj, key, None)
            else:
                targetObj = getattr(rowObj, key, None)
            pass
    if targetObj is None and rtn_none:
        return default or None

    return targetObj


def remove_html_tags(text):
    """Remove html tags from a excerpt string"""
    import re
    clean_style = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL)
    clean_html = re.sub(re.compile('<.*?>'), '', clean_style)
    return clean_html.replace('\n', ' ')


def camel_to_snake(camel_str):
    """Converts camelcase into snake case. Thanks Chat GPT"""
    import re
    snake_str = re.sub(r'(?<!^)(?=[A-Z])', '_', camel_str).lower()
    return snake_str

def get_file_created(file_path: str, platform: str = 'ios') -> datetime:
    from datetime import datetime
    import pathlib

    # create a file path
    path = pathlib.Path(file_path)

    if platform == 'ios':
        # get modification time
        timestamp = path.stat().st_mtime
        # convert time to dd-mm-yyyy hh:mm:ss
        m_time = datetime.fromtimestamp(timestamp)
        # print(f'Modified Date/Time: {os.path.basename(file_path)}', m_time)
        return m_time
    if platform == 'windows':
        # get creation time on windows
        current_timestamp = path.stat().st_ctime
        c_time = datetime.fromtimestamp(current_timestamp)
        # print('Created Date/Time on:', c_time)
        return c_time

def deserialize_datestr(
    datestr: Union[str, datetime],
    fmt: str = "%Y-%m-%d %I:%M:%S",   # %I for 12-hour format
    zone: str = "US/Eastern",
    auto_correct: bool = True
) -> Optional[datetime]:
    """
    Convert a date string into a timezone-aware datetime.

    Args:
        datestr: Input string or datetime.
        fmt: Expected datetime format (default "%Y-%m-%d %I:%M:%S %p").
        zone: Timezone name (default "US/Eastern").
        auto_correct: Whether to attempt corrections for sloppy inputs.

    Returns:
        Timezone-aware datetime (in UTC), or None if parsing fails.
    """
    if isinstance(datestr, datetime):
        return pytz.utc.localize(datestr) if datestr.tzinfo is None else datestr.astimezone(pytz.utc)
    if not isinstance(datestr, str):
        return None

    tz = pytz.timezone(zone)

    def correct_format(raw: str, dfmt: str) -> tuple[str, str]:
        """Try to normalize sloppy date strings like 2025/8/9 13:00."""
        try:
            raw = raw.strip().replace("/", "-")
            if 'T' in raw:
                date_part, _, time_part = raw.partition('T')
            else:
                date_part, _, time_part = raw.partition(" ")

            # Use fallback timestr if missing
            time_part = time_part or "12:00:00.0000"
            hr,*minsec = time_part.split(':')
            is_military_tme = "%H" in dfmt or int(hr) > 12
            dfmt = dfmt.replace("%I", "%H") if is_military_tme else fmt

            parts = date_part.split("-")
            if len(parts) != 3:
                return raw, dfmt

            y, m, d = parts
            # Pad month/day
            m, d = f"{int(m):02d}", f"{int(d):02d}"

            # Basic sanity check: if year looks like day
            if int(y) < int(d):
                # Swap year/day (common human error)
                y, d = d, y
                print(f"⚠️  Corrected malformed date string: {raw} → {y}-{m}-{d}")

            return f"{y}-{m}-{d} {time_part}", dfmt
        except Exception as e:
            return raw, dfmt

    try:
        # Try direct nomalizing of date value into correct format first
        dt = datetime.strptime(datetime.fromisoformat(datestr).strftime(fmt), fmt)
    except ValueError:
        if not auto_correct:
            return None
        corrected, fmt = correct_format(datestr, fmt)
        if not corrected:
            return None
        try:
            dt = datetime.strptime(corrected, fmt)
        except ValueError:
            return None

    # Localize to input zone, then convert to UTC
    return tz.localize(dt).astimezone(pytz.utc)


def sortBykey(listobj, sort_by_key="", limit="", reverse=True):
    """Sorts list of obj by key"""

    def get_path_object(rowObj, path):
        targetObj = None
        for key in path.split('.'):
            try:
                if targetObj:
                    targetObj = targetObj[key]
                else:
                    targetObj = rowObj[key]
                pass
            except Exception as error:
                raise error
        return targetObj

    try:
        sorted_dict = sorted(getattr(listobj, 'data', listobj), key=lambda obj: get_path_object(obj, sort_by_key),
                             reverse=reverse)
        # sorted_dict = sorted(getattr(listobj,'data', listobj), key = lambda x:x[sort_by_key], reverse=reverse)
        if limit:
            return sorted_dict[:limit]
        return sorted_dict
    except Exception as e:
        return listobj

def parse_query_model_to_object(model_fields: str) -> object:
    if not model_fields: return None
    mapper = {}
    params = {"_orm_options": {'mapper': mapper},'file_created_on': None, 'file_name': None}
    for k in model_fields.split(','):
        if ':' in k:
            k,_, src = k.partition(':')
            mapper[k] = src
        params[k] = None
    return type('GenericQueryModel', (object,), params)
#
# def query_files(abs_dirpath: str,
#                 app_ctx: AppCtx = None,
#                 model: Union[object, str] = None,
#                 name_pattern: str = None,
#                 exclude_dirs: tuple = None,
#                 exclude_names: tuple = None,
#                 force_all: bool = True) -> Generator:
#     """Returns a generator of files from a directory path"""
#     from pathlib import Path
#     from pyonir.parser import Parsely, Page
#     from pyonir.models.media import BaseMedia
#
#     # results = []
#     hidden_file_prefixes = ('.', '_', '<', '>', '(', ')', '$', '!', '._')
#     allowed_content_extensions = ('prs', 'md', 'json', 'yaml')
#     def get_datatype(filepath) -> Union[object, Parsely, BaseMedia]:
#         if model == 'path': return str(filepath)
#         if model == BaseMedia: return BaseMedia(filepath)
#         pf = Parsely(str(filepath), app_ctx=app_ctx, model=model)
#         if model == 'parsely': return pf
#         if pf.is_page and not model: pf.schema = Page
#         res = pf.map_to_model(pf.schema)
#         return res if pf.schema else pf
#
#     def skip_file(file_path: Path) -> bool:
#         """Checks if the file should be skipped based on exclude_dirs and exclude_file"""
#         is_private_file = file_path.name.startswith(hidden_file_prefixes)
#         is_excluded_file = exclude_names and file_path.name in exclude_names
#         is_allowed_file = file_path.suffix[1:] in allowed_content_extensions
#         if not is_private_file and force_all: return False
#         return is_excluded_file or is_private_file or not is_allowed_file
#
#     for path in Path(abs_dirpath).rglob(name_pattern or "*"):
#         if skip_file(path): continue
#         yield get_datatype(path)



def delete_file(full_filepath):
    import shutil
    if os.path.isdir(full_filepath):
        shutil.rmtree(full_filepath)
        return True
    elif os.path.isfile(full_filepath):
        os.remove(full_filepath)
        return True
    return False


def create_file(file_abspath: str, data: any = None, is_json: bool = False, mode='w') -> bool:
    """Creates a new file based on provided data
    Args:
        file_abspath: str = path to proposed file
        data: any = contents to write into file
        is_json: bool = strict json file
        mode: str = write mode for file w|w+|a
    Returns:
        bool: The return value if file was created successfully
    """
    def write_file(file_abspath, data, is_json=False, mode='w'):
        with open(file_abspath, mode, encoding="utf-8") as f:
            if is_json:
                json.dump(data, f, indent=2, sort_keys=True, default=json_serial)
            else:
                f.write(data)

    if not os.path.exists(os.path.dirname(file_abspath)):
        os.makedirs(os.path.dirname(file_abspath))
    try:
        is_json = is_json or file_abspath.endswith('.json')
        write_file(file_abspath, data, is_json=is_json, mode=mode)
        return True
    except Exception as e:
        print(f"Error create_file method: {str(e)}")
        return False


def copy_assets(src: str, dst: str, purge: bool = True):
    """Copies files from a source directory into a destination directory with option to purge destination"""
    import shutil
    from shutil import ignore_patterns
    # print(f"{PrntColrs.OKBLUE}Coping `{src}` resource into {dst}{PrntColrs.RESET}")
    try:
        if os.path.exists(dst) and purge:
            shutil.rmtree(dst)
        if os.path.isfile(src):
            shutil.copyfile(src, dst)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=ignore_patterns('__pycache__', '*.pyc', 'tmp*', 'node_modules', '.*'))
    except Exception as e:
        raise



def json_serial(obj):
    """JSON serializer for nested objects not serializable by default jsonify"""
    from datetime import datetime
    from .models.parser import DeserializeFile
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, Generator) or hasattr(obj, 'mapping'):
        return list(obj)
    elif isinstance(obj, DeserializeFile):
        return obj.data
    elif hasattr(obj, 'to_dict'):
        return obj.to_dict()
    else:
        return obj if not hasattr(obj, '__dict__') else obj.__dict__


def load_modules_from(pkg_dirpath, as_list: bool = False, only_packages:bool = False)-> dict[Any, Any] | list[Any]:
    loaded_mods = {} if not as_list else []
    loaded_funcs = {} if not as_list else []
    if not os.path.exists(pkg_dirpath): return loaded_funcs
    for mod_file in os.listdir(pkg_dirpath):
        name,_, ext = mod_file.partition('.')
        if only_packages:
            pkg_abspath = os.path.join(pkg_dirpath, mod_file, '__init__.py')
            mod, func = get_module(pkg_abspath, name)
        else:
            if ext!='py': continue
            mod_abspath = os.path.join(pkg_dirpath, name.strip())+'.py'
            mod, func = get_module(mod_abspath, name)
        if as_list:
            loaded_funcs.append(func)
        else:
            loaded_mods[name] = mod
            loaded_funcs[name] = func

    return loaded_funcs

def import_module(pkg_path: str, callable_name: str) -> typing.Callable:
    """Imports a module and returns the callable by name"""
    import importlib
    mod_pkg = importlib.import_module(pkg_path)
    importlib.reload(mod_pkg)
    mod = get_attr(mod_pkg, callable_name, None)
    return mod

def get_module(pkg_path: str, callable_name: str) -> tuple[typing.Any, typing.Callable]:
    import importlib
    spec = importlib.util.spec_from_file_location(callable_name, pkg_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for {callable_name} from {pkg_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    func = get_attr(module, callable_name) or get_attr(module, module.__name__)
    return module, func

def generate_id():
    import uuid
    return str(uuid.uuid1())

def generate_base64_id(value):
    import base64
    return base64.b64encode(value.encode('utf-8'))

def load_env(path=".env") -> EnvConfig:
    import warnings
    from collections import defaultdict
    from pyonir.models.server import DEV_ENV

    env = os.getenv('APP_ENV') or DEV_ENV
    env_data = defaultdict(dict)
    env_data['APP_ENV'] = env
    if not env:
        warnings.warn("APP_ENV not set. Defaulting to LOCAL mode. Expected one of DEV, TEST, PROD, LOCAL.", UserWarning)
    if not os.path.exists(path): return dict_to_class(env_data, EnvConfig)

    def set_nested(d, keys, value):
        """Helper to set value in nested dictionary using dot-separated keys."""
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Set in os.environ (flat)
            os.environ.setdefault(key, value)

            # Set in nested dict (structured)
            keys = key.split(".")
            set_nested(env_data, keys, value)

    return dict_to_class(env_data, EnvConfig)

def expand_dotted_keys(flat_data: dict, return_as_dict: bool = False):
    """
    Convert a dict with dotted keys into a nested structure.

    Args:
        flat_data (dict): Input dictionary with dotted keys.
        return_as_dict (bool): If True, return a nested dict.
                               If False, return nested dynamic objects.
    """

    def make_object(name="Generic"):
        return type(name, (object,), {"__name__": "generic"})()

    root = {} if return_as_dict else make_object("Root")

    for dotted_key, value in flat_data.items():
        parts = dotted_key.split(".")
        current = root

        for i, part in enumerate(parts):
            # Last part -> assign value
            if i == len(parts) - 1:
                if return_as_dict:
                    current[part] = value
                else:
                    setattr(current, part, value)
            else:
                if return_as_dict:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                else:
                    if not hasattr(current, part):
                        setattr(current, part, make_object(part.capitalize()))
                    current = getattr(current, part)

    return root


def get_version(toml_file: str) -> str:
    import re
    from pathlib import Path
    try:
        # Try using installed metadata first
        from importlib.metadata import version
        return version("pyonir")
    except Exception:
        pass

    try:
        content = Path(toml_file).read_text()
        return re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE).group(1)
    except Exception as e:
        print('Error: unable to parse pyonir version from project toml',e, toml_file)
        return 'UNKNOWN'

class PrntColrs:
    RESET = '\033[0m'
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\x1b[0;92;49m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
