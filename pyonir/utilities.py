from __future__ import annotations
import os
import typing
from typing import Generator, Iterable, Mapping, get_origin, get_args, get_type_hints
from collections.abc import Iterable as ABCIterable

from pyonir.types import PyonirRequest, PyonirSchema


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

def cls_mapper(file_obj: any, cls: typing.Callable, from_request: PyonirRequest = None):
    if hasattr(cls, '__skip_parsely_deserialization__'): return file_obj
    param_type_map = get_type_hints(cls)
    is_generic = cls.__name__ == 'GenericQueryModel'
    if is_scalar_type(cls):
        return cls(file_obj)
    if is_generic:
        print('isgeneric', file_obj.file_name)
    mapper_keys = cls._mapper if hasattr(cls, '_mapper') else {}
    data = get_attr(file_obj, 'data') or {}
    _parsely_data_key = '.'.join(['data', get_attr(cls, '_mapper_key') or cls.__name__.lower()])
    kdata = get_attr(file_obj, _parsely_data_key)
    if kdata: data.update(**kdata)
    cls_args = {}
    res = cls() if is_generic else None
    if hasattr(cls, 'from_dict'): # allows manual mapping of class instance
        return cls.from_dict(file_obj)

    for param_name, param_type in param_type_map.items():
        try:
            mapper_key = get_attr(mapper_keys, param_name) or param_name
            param_value = get_attr(data, mapper_key) or get_attr(file_obj, mapper_key)
            if param_type == PyonirRequest and from_request:
                param_value = from_request
            if param_value is None or param_name[0]=='_' or param_name=='return':
                continue
            if is_iterable(param_type):
                iter_ptype = get_args(param_type)
                is_mapp = is_mappable_type(param_type)
                if is_mapp:
                    ktype, vtype = iter_ptype
                    is_list = is_iterable(vtype)
                    if is_list: vtype = get_args(vtype)[0]
                    cls_args[param_name] = {ktype(key): [cls_mapper(lval, vtype) for lval in value] if is_list else cls_mapper(value, vtype) for key, value in param_value.items()}
                else:
                    cls_args[param_name] = [cls_mapper(itm, iter_ptype[0]) for itm in param_value]
            else:
                is_instance = param_value == param_type
                is_typed = isinstance(param_value, param_type)
                # is_typed = isinstance(param_value, type(param_value)) or not isinstance(param_value, param_type)
                if is_instance and from_request:
                    param_value = cls_mapper(from_request.form, param_type) #param_type(**from_request.form)
                cls_args[param_name] = param_value if is_typed or is_instance else param_type(param_value)
        except Exception as e:
            raise
    if from_request: return cls_args
    if not from_request and param_type_map: res = cls(**cls_args)
    # assign all other non-model attributes
    if is_generic or hasattr(cls, '_mapper_merge'):
        for key, value in data.items():
            if not param_type_map and not hasattr(cls, key): continue # assumes a GenericQueryModel was provided
            if isinstance(getattr(cls, key, None), property): continue
            if param_type_map.get(key) or key[0]=='_': continue
            setattr(res, key, value)

    # if hasattr(file_obj, 'file_created_on'):
    setattr(res, '@model', cls.__name__)
    for attr in PyonirSchema.default_file_attributes:
        v = get_attr(file_obj, attr)
        if v is None: continue
        setattr(res, attr, v)

    return res


def process_contents(path, app_ctx=None, file_model: any = None):
    """Deserializes all files within the contents directory"""
    from pyonir.parser import Parsely

    def update(self):
        for key in self.__dict__.keys():
            val = get_attr(self, key)
            if not hasattr(val, '_path'): continue
            pval = Parsely(val._path, app_ctx)
            setattr(self, key, dict_to_class({**pval.data, '_path': pval.file_path}, key))
        pass

    key = os.path.basename(path)
    res = type(key, (object,), {})() # generic map
    pgs = get_all_files_from_dir(path, app_ctx=app_ctx, entry_type=file_model)
    for pg in pgs:
        name = getattr(pg, 'file_name')
        setattr(res, name, pg)
    return res


def dict_to_class(data: dict, name: str = 'T'):
    """
    Converts a dictionary into a class object with the given name.

    Args:
        data (dict): The dictionary to convert.
        name (str): The name of the class.

    Returns:
        object: An instance of the dynamically created class with attributes from the dictionary.
    """
    # Dynamically create a new class
    cls = type(name, (object,), {})

    # Create an instance of the class
    instance = cls()

    # Assign dictionary keys as attributes of the instance
    for key, value in data.items():
        if isinstance(getattr(cls, key, None), property): continue
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


def deserialize_datestr(datestr, timestr="00:00", fmt="%Y-%m-%d %H:%M:%S %p", zone="US/Eastern", auto_correct=True):
    from datetime import datetime
    import pytz
    if not isinstance(datestr, str): return datestr

    def correct_format(date_str):
        try:
            date_str = date_str.strip().replace('/', '-')
            date_str, _, timestr = date_str.partition(" ")
            timestr = timestr if timestr != "" else '12:13:14 AM'
            has_period = timestr.endswith("M")
            if not has_period:
                timestr += " AM"
            y, m, *d = date_str.split("-")
            d = "".join(d)
            fdate = f"{y}-{int(m):02d}-{d}"
            if int(y) < int(d):
                fdate = f"{d}-{int(y):02d}-{m}"
                print(f"\tIncorrect format on date string {date_str}. it should be {fdate}")
                return fdate
            return f"{fdate} {timestr}"
        except Exception as e:
            return None

    try:
        return pytz.utc.localize(datetime.strptime(datestr, fmt))
    except ValueError as e:
        # return str(e)
        if not auto_correct: return str(e)
        datestr = correct_format(datestr)
        return pytz.utc.localize(datetime.strptime(datestr, fmt)) if datestr else None


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


def get_all_files_from_dir(abs_dirpath: str,
                           app_ctx: list = None,
                           entry_type: any = None,
                           include_only: str = None,
                           exclude_dirs: list[str] = None,
                           exclude_file: str = None,
                           force_all: bool = True) -> Generator:
    """Returns a generator of files from a directory path"""

    from .parser import Page, Parsely, ParselyMedia
    from .parser import ALLOWED_CONTENT_EXTENSIONS, IGNORE_FILES
    if abs_dirpath in (exclude_dirs or []): return []

    _, _, pages_dirpath, _ = app_ctx

    def get_datatype(parentdir, rel_filepath):
        filepath = os.path.normpath(os.path.join(parentdir, rel_filepath))
        if entry_type == 'path':
            return filepath
        ismedia = not filepath.endswith(ALLOWED_CONTENT_EXTENSIONS)
        generic_model = entry_type if entry_type and entry_type.__name__=='GenericQueryModel' else None
        pf = Parsely(filepath, app_ctx, generic_model)
        if ismedia:
            return cls_mapper(pf, ParselyMedia)
        return cls_mapper(pf, entry_type or Page ) if entry_type or pf.is_page else pf.map_to_model(None)


    def is_public(parentdir, entry=None):
        if force_all: return True
        parentdir = parentdir.replace(pages_dirpath, "").lstrip(os.path.sep)
        is_hidden_dir = parentdir.startswith(IGNORE_FILES)
        if entry in IGNORE_FILES:
            return False
        if not entry:
            return False if is_hidden_dir else True
        else:
            is_hidden_file = entry.startswith(IGNORE_FILES)
            is_filetype = entry.endswith(ALLOWED_CONTENT_EXTENSIONS)
            return False if is_filetype and is_hidden_file or is_hidden_dir else True

    for parentdir, subs, files in os.walk(os.path.normpath(abs_dirpath)):
        folderRoot = parentdir.replace(pages_dirpath, "").lstrip(os.path.sep)
        subFolderRoot = os.path.basename(folderRoot)
        skipRoot = (folderRoot in IGNORE_FILES
                    or folderRoot.startswith(IGNORE_FILES)
                    or subFolderRoot.startswith(IGNORE_FILES))
        skipSubs = subFolderRoot in exclude_dirs if exclude_dirs else 0
        if skipRoot or skipSubs: continue

        for filename in files:
            include_only_file = (include_only and filename != include_only)
            if filename == exclude_file or include_only_file: continue
            if not force_all and not filename.endswith(ALLOWED_CONTENT_EXTENSIONS): continue
            if not is_public(parentdir, filename) or filename in IGNORE_FILES: continue
            yield get_datatype(parentdir, filename)


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
    def write_file(file_abspath, data, is_json=False, mode='w'):
        import json
        with open(file_abspath, mode, encoding="utf-8") as f:
            if is_json:
                json.dump(data, f, indent=2, sort_keys=True, default=json_serial)
            else:
                f.write(data)

    """Creates a new file based on provided data
    Args:
        file_abspath: str = path to proposed file
        data: any = contents to write into file
        is_json: bool = strict json file
        mode: str = write mode for file w|w+|a
    Returns:
        bool: The return value if file was created successfully
    """
    if not os.path.exists(os.path.dirname(file_abspath)):
        os.makedirs(os.path.dirname(file_abspath))
    try:

        if is_json:
            file_abspath = file_abspath.replace(".md", ".json")
        write_file(file_abspath, data, is_json=is_json, mode=mode)

        return True
    except Exception as e:
        print(f"Error create_file method: {str(e)}")
        return False


def copy_assets(src: str, dst: str, purge: bool = True):
    """Copies files from a source directory into a destination directory with option to purge destination"""
    import shutil
    from shutil import ignore_patterns
    print(f"\033[92mCoping `{src}` theme assets into {dst}")
    try:
        if os.path.exists(dst) and purge:
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=ignore_patterns('*.pyc', 'tmp*', 'node_modules', '.*'))
    except NotADirectoryError as e:
        shutil.copyfile(src, dst)
    except Exception as e:
        raise



def json_serial(obj):
    """JSON serializer for nested objects not serializable by default jsonify"""
    from datetime import datetime
    from .parser import Parsely
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, Generator):
        return list(obj)
    elif isinstance(obj, Parsely):
        return obj.data
    elif hasattr(obj, 'to_json'):
        return obj.to_json()
    else:
        return None if not hasattr(obj, '__dict__') else obj.__dict__


def load_modules_from(pkg_dirpath, as_list: bool = False)-> tuple[dict[str, object], dict[str, typing.Callable]]:
    loaded_mods = {} if not as_list else []
    loaded_funcs = {} if not as_list else []
    if not os.path.exists(pkg_dirpath): return loaded_funcs
    for mod_file in os.listdir(pkg_dirpath):
        name,_, ext = mod_file.partition('.')
        if ext!='py': continue
        mod_abspath = os.path.join(pkg_dirpath, name.strip())+'.py'
        mod, func = get_module(mod_abspath, name)
        if as_list:
            loaded_funcs.append(func)
        else:
            loaded_mods[name] = mod
            loaded_funcs[name] = func

    return loaded_funcs

def get_module(pkg_path: str, callable_name: str) -> tuple[any, typing.Callable]:
    from importlib import util
    mod = util.spec_from_file_location(callable_name, pkg_path).loader.load_module(callable_name)
    func = getattr(mod, callable_name)

    return (mod, func)

def generate_id():
    import uuid
    return str(uuid.uuid1())

def generate_base64_id(value):
    import base64
    return base64.b64encode(value.encode('utf-8'))

class pcolors:
    RESET = '\033[0m'
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
