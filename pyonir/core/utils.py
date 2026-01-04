import os, json
from datetime import datetime
from collections.abc import Generator
from typing import Optional, Union, Callable, Any, Dict


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

def open_file(file_path: str, rtn_as: str = "string"):
    """Reads target file on file system"""

    if not os.path.exists(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as target_file:
        try:
            if rtn_as == "list":
                return target_file.readlines()
            elif rtn_as == "json":
                return json.load(target_file)
            else:
                return target_file.read()
        except Exception as e:
            return (
                {"error": __file__, "message": str(e)} if rtn_as == "json" else []
            )

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

def parse_url_params(param_str: str) -> dict:
    """Parses a URL query string into a dictionary"""
    from urllib.parse import parse_qs
    parsed = parse_qs(param_str)
    return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}

def process_contents(path, app_ctx=None, file_model: any = None) -> object:
    """Deserializes all files within the contents directory"""
    from pyonir.core.database import query_fs
    key = os.path.basename(path)
    res = type(key, (object,), {"__name__": key})() # generic map
    pgs = query_fs(path, app_ctx=app_ctx, model=file_model)
    for pg in pgs:
        name = getattr(pg, 'file_name')
        setattr(res, name, pg.to_named_tuple() if hasattr(pg, 'to_named_tuple') else pg)
    return res

def json_serial(obj):
    """JSON serializer for nested objects not serializable by default jsonify"""
    from datetime import datetime
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, Generator) or hasattr(obj, 'mapping'):
        return list(obj)
    elif hasattr(obj, 'to_dict'):
        return obj.to_dict()

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
    import pytz

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
            if '+' in time_part:
                time_part,_,utc_offset = time_part.partition('+')
            hr,*minsec = time_part.split(':')
            mins, sec = minsec
            sec, _, micro = sec.partition('.')
            time_part = f"{hr}:{mins}:{sec}" or "12:00:00.0000"
            has_miltary_fmt = "%H" in dfmt
            is_military_tme = (int(hr) > 12 or int(hr) < 1)
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
        # Try direct parse first
        dt = datetime.strptime(datestr, fmt)
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

def get_attr(row_obj, attr_path=None, default=None, rtn_none=True):
    """
    Resolves nested attribute or dictionary key paths.

    :param row_obj: deserialized object
    :param attr_path: dot-separated string or list for nested access
    :param default: fallback value if the target is None or missing
    :param rtn_none: if True, returns `None` on missing keys/attrs instead of the original object
    """
    if attr_path == None: return row_obj
    attr_path = attr_path if isinstance(attr_path, list) else attr_path.split('.')
    targetObj = None
    for key in attr_path:
        try:
            if targetObj:
                targetObj = targetObj[key]
            else:
                targetObj = row_obj.get(key)
            pass
        except (KeyError, AttributeError, TypeError) as e:
            if targetObj:
                targetObj = getattr(targetObj, key, None)
            else:
                targetObj = getattr(row_obj, key, None)
            pass
    if targetObj is None and rtn_none:
        return default or None

    return targetObj

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

def import_module(pkg_path: str, callable_name: str) -> Callable:
    """Imports a module and returns the callable by name"""
    import importlib
    mod_pkg = importlib.import_module(pkg_path)
    importlib.reload(mod_pkg)
    mod = get_attr(mod_pkg, callable_name, None)
    return mod

def get_module(pkg_path: str, callable_name: str) -> tuple[Any, Callable]:
    import importlib
    spec = importlib.util.spec_from_file_location(callable_name, pkg_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for {callable_name} from {pkg_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    func = get_attr(module, callable_name) or get_attr(module, module.__name__)
    return module, func

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
        import json
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

def generate_id():
    import uuid
    return str(uuid.uuid1())

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

def merge_dict(derived: Dict, src: Dict) -> None:
    """
    Merge keys from `derived` into `src` without overwriting existing values.
    - If a key from `derived` is missing in `src`, add it.
    - If the key is FILTER_KEY, merge lists/dicts from both sides.
    - If both values are same type and key exists in `src`, perform nested merge via update_nested.
    Returns the mutated `src` dict.
    """
    from pyonir.core.parser import update_nested, FILTER_KEY

    for key, value in derived.items():
        if key not in src:
            src[key] = value
            continue

        # Both have the key; handle FILTER_KEY merging specially
        src_value = src.get(key)
        if key == FILTER_KEY:
            if isinstance(src_value, list) and isinstance(value, list):
                src_value.extend(value)
                src[key] = src_value
            elif isinstance(src_value, dict) and isinstance(value, dict):
                src_value.update(value)
                src[key] = src_value
            # if types mismatch or not list/dict, keep existing src value
            continue

        # If both values are same type, perform nested merge
        if isinstance(src_value, (dict, list)) and isinstance(src_value, type(value)):
            update_nested([], src[key], data_merge=value)
        # If types mismatch, keep existing src value

def coerce_bool(value: str) -> any:
    """
    Coerce a string into a boolean.

    Truthy values:
        "true", "1", "yes", "y", "on"

    Falsy values:
        "false", "0", "no", "n", "off"

    Raises:
        ValueError if the value cannot be coerced.
    """
    if isinstance(value, bool):
        return value

    v = str(value).strip().lower()

    if v in {"true", "1", "yes", "y", "on"}:
        return True

    if value is None or v in {"false", "0", "no", "n", "off"}:
        return False

    return value

def set_attr(source, keys, value):
    """Helper to set value in nested dictionary using dot-separated keys."""
    d = {}
    keys = keys.split('.') if isinstance(keys, str) else keys
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = coerce_bool(value)
    if isinstance(source, dict):
        merge_dict(d, source)
    else:
        setattr(source, keys[0], dict_to_class(d))

def load_env(path=".env") -> 'EnvConfig':
    import warnings
    from collections import defaultdict
    from pyonir.core.server import LOCAL_ENV
    from pyonir.pyonir_types import EnvConfig
    # local is the default environment unless specified by system
    env = os.getenv('APP_ENV') or LOCAL_ENV
    env_data = defaultdict(dict)
    env_data['APP_ENV'] = env
    if not env:
        warnings.warn("APP_ENV not set. Defaulting to LOCAL mode. Expected one of LOCAL, DEV, PROD.", UserWarning)
    if not os.path.exists(path): return dict_to_class(env_data, EnvConfig)

    def set_nested(d, keys, value):
        """Helper to set value in nested dictionary using dot-separated keys."""
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = coerce_bool(value)

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