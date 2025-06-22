from __future__ import annotations
import os
import typing
from typing import Generator, Iterable, Mapping, get_origin, get_args, get_type_hints
from collections.abc import Iterable as ABCIterable
from sortedcontainers import SortedList

from pyonir.types import PyonirApp, PyonirRequest, ParselyCollection, Parsely


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
    params = get_type_hints(cls)
    if is_scalar_type(cls):
        return cls(file_obj)
    if not params: return file_obj
    mapper_keys = cls._mapper if hasattr(cls, '_mapper') else {}
    data = get_attr(file_obj, 'data') or {}
    _parsely_data_key = '.'.join(['data', get_attr(cls, '_mapper_key') or cls.__name__.lower()])
    kdata = get_attr(file_obj, _parsely_data_key)
    if kdata: data.update(**kdata)
    cls_args = {}
    res = None
    if hasattr(cls, 'from_dict'): # allows manual mapping of class instance
        return cls.from_dict(file_obj)

    for param_name, param_type in params.items():
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
    try:
        if not from_request: res = cls(**cls_args)
    except Exception as e:
        raise
    if from_request: return cls_args
    # assign all other non-model attributes
    if hasattr(cls, '_mapper_merge'): # auto sets properties from file obj to class instance
        for key, value in data.items():
            if isinstance(getattr(cls, key, None), property): continue
            if params.get(key) or key[0]=='_': continue
            setattr(res, key, value)

    if hasattr(file_obj, 'file_created_on'):
        setattr(res, '@model', cls.__name__)
        setattr(res, 'file_created_on', get_attr(file_obj, 'file_created_on'))

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
    # etype = Parsely  # ParselySchema if 'schemas' in path else Parsely
    pgs = allFiles(path, app_ctx=app_ctx, entry_type=file_model)
    res = type(key, (object,), {'_update': update, '_ctx': app_ctx})()
    for pg in pgs:
        name = getattr(pg, 'file_name', getattr(pg, 'name', None))
        setattr(res, name, pg)
        # setattr(res, name, pg if file_model else dict_to_class({**pg.data, '_path': pg.file_path}, name))
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


def allFiles(abs_dirpath: str,
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
        pf = Parsely(filepath, app_ctx)
        if ismedia:
            return cls_mapper(pf, ParselyMedia)
        return cls_mapper(pf, entry_type or Page) #if entry_type else pf


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
    from .parser import Parsely, ParselyMedia
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, (Generator, PyonirCollection)):
        return list(obj)
    elif isinstance(obj, Parsely):
        return obj.data
    elif hasattr(obj, 'to_json'):
        return obj.to_json()
    else:
        return None if not hasattr(obj, '__dict__') else obj.__dict__


def secure_upload_filename(filename):
    import re
    # Strip leading and trailing whitespace from the filename
    filename = filename.strip()

    # Replace spaces with underscores
    filename = filename.replace(' ', '_')

    # Remove any remaining unsafe characters using a regular expression
    # Allow only alphanumeric characters, underscores, hyphens, dots, and slashes
    filename = re.sub(r'[^a-zA-Z0-9_.-]', '', filename)

    # Ensure the filename doesn't contain multiple consecutive dots (.) or start with one
    filename = re.sub(r'\.+', '.', filename).lstrip('.')

    # Return the filename as lowercase for consistency
    return filename.lower()

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


class PyonirCollection:

    @staticmethod
    def coerce_bool(value: str):
        d = ['false', 'true']
        try:
            i = d.index(value.lower().strip())
            return True if i else False
        except ValueError as e:
            return value.strip()

    @staticmethod
    def parse_params(param: str):
        k, _, v = param.partition(':')
        op = '='
        is_eq = lambda x: x[1]==':'
        if v.startswith('>'):
            eqs = is_eq(v)
            op = '>=' if eqs else '>'
            v = v[1:] if not eqs else v[2:]
        elif v.startswith('<'):
            eqs = is_eq(v)
            op = '<=' if eqs else '<'
            v = v[1:] if not eqs else v[2:]
            pass
        else:
            pass
        # v = True if v.strip()=='true' else v.strip()
        return {"attr": k.strip(), "op":op, "value":PyonirCollection.coerce_bool(v)}

    @classmethod
    def query(cls, query_path: str,
             app_ctx: PyonirApp = None,
             data_model: any = None,
             include_only: str = None,
             exclude_dirs: list[str] = None,
             exclude_file: str = None,
             force_all: bool = True,
              sort_key: str = None):
        """queries the file system for list of files"""
        gen_data = allFiles(query_path, app_ctx=app_ctx, entry_type=data_model, include_only=include_only,
                            exclude_dirs=exclude_dirs, exclude_file=exclude_file, force_all=force_all)
        return cls(gen_data, sort_key=sort_key)

    def prev_next(self, input_file: Parsely):
        """Returns the previous and next files relative to the input file"""
        prv = None
        nxt = None
        pc = self.query(input_file.file_dirpath)
        pc.collection = iter(pc.collection)
        for cfile in pc.collection:
            if cfile.file_status == 'hidden': continue
            if cfile.file_path == input_file.file_path:
                nxt = next(pc.collection, None)
                break
            else:
                prv = cfile
        return dict_to_class({"next": nxt, "prev": prv})

    def __init__(self, items: typing.Iterable, sort_key: str = None):
        from sortedcontainers import SortedList
        self._query_path = ''
        key = lambda x: get_attr(x, sort_key or 'file_created_on')
        self.collection = SortedList(items, key=key)

    def find(self, value: any, from_attr: str = 'file_name'):
        """Returns the first item where attr == value"""
        return next((item for item in self.collection if getattr(item, from_attr, None) == value), None)

    def where(self, attr, op="=", value=None):
        """Returns a list of items where attr == value"""
        if value is None:
            # assume 'op' is actually the value if only two args were passed
            value = op
            op = "="

        def match(item):
            actual = get_attr(item, attr)
            if op == "=":
                return actual == value
            elif op == "in" or op == "contains":
                return actual in value if actual is not None else False
            elif op == ">":
                return actual > value
            elif op == "<":
                return actual < value
            elif op == ">=":
                return actual >= value
            elif op == "<=":
                return actual <= value
            elif op == "!=":
                return actual != value
            return False
        if isinstance(attr, typing.Callable): match = attr
        return PyonirCollection(filter(match, list(self.collection)))

    def paginate(self, start: int, end: int, reversed: bool = False):
        """Returns a slice of the items list"""
        sl = self.collection.islice(start, end, reverse=reversed) if end else self.collection
        return sl #self.collection[start:end]

    def group_by(self, key: str | typing.Callable):
        """
        Groups items by a given attribute or function.
        If `key` is a string, it will group by that attribute.
        If `key` is a function, it will call the function for each item.
        """
        from collections import defaultdict
        grouped = defaultdict(list)

        for item in self.collection:
            k = key(item) if callable(key) else getattr(item, key, None)
            grouped[k].append(item)

        return dict(grouped)

    def paginated_collection(self, query_params=None)-> ParselyCollection | None:
        """Paginates a list into smaller segments based on curr_pg and display limit"""
        if query_params is None: query_params = {}
        from pyonir import Site
        if not Site: return None
        request: PyonirRequest = Site.TemplateEnvironment.globals['request']
        if not hasattr(request, 'limit'): return None
        req_pg = get_attr(request.query_params, 'pg') or 1
        limit = query_params.get('limit', request.limit)
        curr_pg = int(query_params.get('pg', req_pg)) or 1
        sort_key = query_params.get('sort_key')
        where_key = query_params.get('where')
        if sort_key:
            self.collection = SortedList(self.collection, lambda x: get_attr(x, sort_key))
        if where_key:
            where_key = [PyonirCollection.parse_params(ex) for ex in where_key.split(',')]
            self.collection = self.where(**where_key[0])
        force_all = limit=='*'

        max_count = len(self.collection)
        limit = 0 if force_all else int(limit)
        page_num = 0 if force_all else int(curr_pg)
        start = (page_num * limit) - limit
        end = (limit * page_num)
        pg = (max_count // limit) + (max_count % limit > 0) if limit > 0 else 0

        pag_data = self.paginate(start=start, end=end, reversed=True) if not force_all else self.collection

        return ParselyCollection(**{
            'curr_page': page_num,
            'page_nums': [n for n in range(1, pg + 1)] if pg else None,
            'limit': limit,
            'max_count': max_count,
            'items': list(pag_data)
        })

    def __len__(self):
        return self.collection._len

    def __iter__(self):
        return iter(self.collection)

