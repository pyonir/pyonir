import os, re, json
from typing import Tuple, Dict, List, Any, Optional, Union

from pyonir.core.utils import get_file_created, open_file, get_attr

# Pre-compile regular expressions for better performance
_RE_LEADING_SPACES = re.compile(r'^\s+')

# Constants
DICT_DELIM = ": "
LST_DLM = ":-"
LST_DICT_DLM = "-"
STR_DLM = ":` "
ILN_DCT_DLM = ":: "
BLOCK_DELIM = ":|"
BLOCK_PREFIX_STR = "==="
BLOCK_CODE_FENCE = "````"
SINGLE_LN_COMMENT = '#'
MULTI_LN_COMMENT = '#|'
LOOKUP_EMBED_PREFIX = '$'
LOOKUP_DIR_PREFIX = '$dir'
LOOKUP_DATA_PREFIX = '$data'
LOOKUP_CALLER_PREFIX = '$call'
FILTER_KEY = '@filter'
VIRTUAL_ROUTES_FILENAME: str = '.virtual_routes'

# Global cache
FileCache: Dict[str, Any] = {}
NS: List[str] = []
RETRY_MAP: Dict = {}

class FileStatuses(str):
    UNKNOWN = "unknown"
    """Read only by the system often used for temporary and unknown files"""

    PROTECTED = "protected"
    """Requires authentication and authorization. can be READ and WRITE."""

    FORBIDDEN = "forbidden"
    """System only access. READ ONLY"""

    PUBLIC = "public"
    """Access external and internal with READ and WRITE."""


class DeserializeFile:
    """Context for parsely file processing"""
    _virtual_route_filename: str = f'{VIRTUAL_ROUTES_FILENAME}.md'
    _routes_dirname: str = "pages"
    """Directory name that contains page files served as file based routing"""
    _invalidate_cache: bool = False
    """Flag to invalidate file cache on next access"""

    def __new__(cls, *args, **kwargs):
        file_path = args[0] if args else kwargs.get('file_path')
        if file_path and FileCache.get(file_path):
            return FileCache.get(file_path)
        return super().__new__(cls)

    def __init__(self,
                file_path: str,
                app_ctx: "AppCtx" = None,
                model: object = None,
                text_string: str = None):
        # print(f"__init__ skipped for file_path: {file_path} (already initialized)")
        # if FileCache.get(file_path): return
        name, ext = os.path.splitext(os.path.basename(file_path))
        self.app_ctx = app_ctx
        self._blob_keys = []
        self.schema = model
        self.file_ext = ext
        self.file_name = name
        self.file_path = str(file_path)
        self.file_dirpath = os.path.dirname(file_path)  # path to files contents directory
        self.file_dirname = os.path.basename(self.file_dirpath)
        self.file_contents_dirpath = None
        # file data processing
        self.text_string = text_string
        self.file_lines = None
        self.file_line_count = None
        self.data: Dict = {}
        self.is_virtual_route = None
        self.is_page = None
        # Page specific attributes
        if not self.text_string:
            ctx_name, ctx_url, contents_dirpath, ssg_path, datastore_path = app_ctx or ("", "", "", "", "",)
            contents_relpath = (
                file_path.replace(contents_dirpath, "").lstrip("/")
                if contents_dirpath
                else ""
            )
            contents_dirname = contents_relpath.split("/")[0]
            is_page = contents_dirname == self._routes_dirname
            self.file_contents_dirpath = contents_dirpath or self.file_dirpath
            self.is_page = is_page
            self.is_home = (
                is_page and contents_relpath == f"{self._routes_dirname}/index"
            )
            self.is_virtual_route = self.file_path.endswith(
                self._virtual_route_filename
            )
            # page attributes
            if not self.is_virtual_route:
                surl = (
                    re.sub(rf"\b{contents_dirname}/\b|\bindex\b", "", contents_relpath)
                    if is_page
                    else contents_relpath
                )
                slug = (
                    f"{ctx_url or ''}/{surl}".lstrip("/")
                    .rstrip("/")
                    .lower()
                    .replace(self.file_ext, "")
                )
                url = "/" if self.is_home else "/" + slug
                self.data["url"] = url
                self.data["slug"] = slug

        # process file data
        self.deserializer()
        # Post-processing
        self.apply_filters()
        # if self.file_exists and self.is_page:
        #     # Cache object
        #     FileCache[self.file_path] = self

    def replay_retry(self):
        """Replays deserializing line"""
        fd = self.__dict__
        retries = RETRY_MAP.get(self.file_path)
        if not retries:
            return
        for key, value in retries:
            lookup_fpath, file_name, app_ctx, has_attr_path, query_params = value
            lookup_fpath = self.process_site_filter('pyformat', lookup_fpath, fd) if '{' in lookup_fpath else lookup_fpath
            v = parse_ref_to_files(lookup_fpath, file_name, app_ctx, attr_path=has_attr_path, query_params=query_params)
            update_nested(key, self.data, data_update=v)
            pass

        RETRY_MAP.clear()

    def apply_filters(self):
        """Applies filter methods to data attributes"""
        from pyonir import Site

        if not bool(self.data):
            return
        filters = self.data.get(FILTER_KEY)
        if not filters or not Site:
            return
        for filtr, datakeys in filters.items():
            for key in datakeys:
                mod_val = self.process_site_filter(
                    filtr, get_attr(self.data, key), {"page": self.data}
                )
                update_nested(key, self.data, data_update=mod_val)
        # del self.data[FILTER_KEY]

    def deserializer(self):
        """Deserialize file line strings into map object"""
        if self.file_ext == ".md" or self.text_string:
            lines = open_file(self.file_path) or self.text_string
            self.file_lines = lines.strip().split("\n") if lines else []
            self.file_line_count = len(self.file_lines)
            if self.file_line_count > 0:
                # from pyonir.core.parsely import process_lines
                process_lines(self.file_lines, cursor=0, data_container=self.data, file_ctx=self)
        elif self.file_ext == ".json":
            self.data = open_file(self.file_path, rtn_as="json") or {}
        return True

    def __lt__(self, other: 'DeserializeFile') -> bool:
        """Compares two DeserializeFile instances based on their created_on attribute."""
        if not isinstance(other, DeserializeFile):
            return True
        return self.file_created_on < other.file_created_on

    @property
    def file_exists(self):
        return os.path.exists(self.file_path)

    @property
    def file_modified_on(self):  # Datetime
        from datetime import datetime
        import pytz

        return (
            datetime.fromtimestamp(os.path.getmtime(self.file_path), tz=pytz.UTC)
            if self.file_exists
            else None
        )

    @property
    def file_created_on(self):  # Datetime
        return get_file_created(self.file_path) if self.file_exists else None

    @property
    def file_status(self) -> str:  # String
        return (
            FileStatuses.PROTECTED
            if self.file_name.startswith("_")
            else FileStatuses.FORBIDDEN
            if self.file_name.startswith(".")
            else FileStatuses.PUBLIC
        )

    @staticmethod
    def process_site_filter(filter_name: str, value: any, kwargs=None):
        from pyonir import Site

        if not Site or (not Site.SSG_IN_PROGRESS and not Site.server.is_active):
            return value
        site_filter = Site.Parsely_Filters.get(filter_name)
        return site_filter(value, kwargs)

    @classmethod
    def load(cls, json_str: str) -> dict:
        """converts parsely string to python dictionary object"""
        f = cls("", text_string=json_str)
        return f.data

    @staticmethod
    def loads(data: dict) -> str:
        """converts python dictionary object to parsely string"""
        return serializer(data)

    def refresh_data(self):
        """Parses file and update data values"""
        self.data = {}
        self._blob_keys.clear()
        self.deserializer()
        self.apply_filters()

    def prev_next(self):
        from pyonir.core.database import CollectionQuery

        if self.file_dirname != "pages" or self.is_home:
            return None
        return CollectionQuery.prev_next(self)

    def to_named_tuple(self):
        """Returns a tuple representation of the file data"""
        from collections import namedtuple

        file_keys = [
            *self.data.keys(),
            "file_name",
            "file_ext",
            "file_path",
            "file_dirpath",
            "file_dirname",
        ]
        PageTuple = namedtuple("PageTuple", file_keys)
        return PageTuple(
            **self.data,
            file_name=self.file_name,
            file_ext=self.file_ext,
            file_path=self.file_path,
            file_dirpath=self.file_dirpath,
            file_dirname=self.file_dirname,
        )

    def to_dict(self):
        """Returns a dictionary representation of the file data"""
        return {
            **self.data,
            "file_name": self.file_name,
            "file_created_on": self.file_created_on,
            "file_modified_on": self.file_modified_on,
            "file_dirname": self.file_dirname,
        }

    def output_html(self, req: "PyonirRequest") -> str:
        """Renders and html output"""
        from pyonir import Site
        from pyonir.core.page import BasePage
        from pyonir.core.mapper import cls_mapper


        # from pyonir.core.mapper import add_props_to_object
        # refresh_model = get_attr(req, 'query_params.rmodel')
        page = cls_mapper(self, self.schema or BasePage)
        Site.apply_globals({"prevNext": self.prev_next, "page": page})
        html = Site.TemplateEnvironment.get_template(page.template).render()
        Site.TemplateEnvironment.block_pull_cache.clear()
        return html

    def output_json(self, data_value: any = None, as_str=True) -> str:
        """Outputs a json string"""
        from .utils import json_serial

        data = data_value or self
        # if not as_str:
        #     return data
        return json.dumps(data, default=json_serial)

    def generate_static_file(self, page_request=None, rtn_results=False):
        """Generate target file as html or json. Takes html or json content to save"""
        from pyonir import Site
        from pyonir.core.utils import create_file

        count = 0
        html_data = None
        json_data = None
        ctx_static_path = (
            self.app_ctx[3] if self.app_ctx and len(self.app_ctx) > 3 else ""
        )
        slug = self.data.get("slug")

        def render_save():
            # -- Render Content --
            html_data = self.output_html(page_request)
            json_data = self.to_dict()
            # -- Save contents --
            create_file(path_to_static_html, html_data)
            create_file(path_to_static_api, json_data)
            return 2

        # -- Get static paths --
        path_to_static_api = os.path.join(
            ctx_static_path, Site.API_DIRNAME, slug, "index.json"
        )
        path_to_static_html = os.path.join(ctx_static_path, slug, "index.html")

        count += render_save()

        if page_request:
            for pgnum in range(1, page_request.paginate):
                path_to_static_html = os.path.join(
                    self.file_ssg_html_dirpath, str(pgnum + 1), "index.html"
                )
                path_to_static_api = os.path.join(
                    self.file_ssg_api_dirpath, str(pgnum + 1), "index.json"
                )
                page_request.query_params["pg"] = pgnum + 1
                count += render_save()

        # -- Return contents without saving --
        if rtn_results:
            return html_data, json_data

        return count

def parse_markdown(content, kwargs):
    """Parse markdown string using mistletoe with htmlattributesrenderer"""
    import html, mistletoe

    # from mistletoe.html_attributes_renderer import HTMLAttributesRenderer
    if not content:
        return content
    res = mistletoe.markdown(content)
    # res = mistletoe.markdown(content, renderer=HTMLAttributesRenderer)
    return html.unescape(res)


def count_tabs(str_value: str, tab_width: int = 4) -> int:
    """Returns number of tabs for provided string using cached regex"""
    try:
        match = _RE_LEADING_SPACES.match(str_value.replace('\n', ''))
        return round(len(match.group()) / tab_width) if match else 0
    except Exception:
        return 0

def update_nested(attr_path, data_src: dict, data_merge=None, data_update=None, find=None) -> tuple[bool, dict]:
    """
    Finds or updates target value based on an attribute path.

    Args:
        attr_path (list): Attribute path as list or dot-separated string.
        data_src (dict): Source data to search or update.
        data_merge (Any, optional): Value to merge.
        data_update (Any, optional): Value to replace at path.
        find (bool, optional): If True, only retrieve the value.

    Returns:
        tuple[bool, Any]: (completed, updated data or found value)
    """

    def update_value(target, val):
        """Mutates target with val depending on type compatibility."""
        if isinstance(target, list):
            if isinstance(val, list):
                target.extend(val)
            else:
                target.append(val)
        elif isinstance(target, dict) and isinstance(val, dict):
            target.update(val)
        elif isinstance(target, str) and isinstance(val, str):
            return val
        return target

    # Normalize attribute path
    if isinstance(attr_path, str):
        attr_path = attr_path.strip().split('.')
    if not attr_path:
        return True, update_value(data_src, data_merge)

    completed = len(attr_path) == 1

    # Handle list source at top-level
    if isinstance(data_src, list):
        _, merged_val = update_nested(attr_path, {}, data_merge)
        return update_nested(None, data_src, merged_val)

    # Navigate deeper if not at last key
    if not completed:
        current_data = {}
        for i, key in enumerate(attr_path):
            if find:
                current_data = (data_src.get(key) if not current_data else current_data.get(key))
            else:
                completed, current_data = update_nested(
                    attr_path[i + 1:],
                    data_src.get(key, current_data),
                    find=find,
                    data_merge=data_merge,
                    data_update=data_update
                )
                update_value(data_src, {key: current_data})
                if completed:
                    break
    else:
        # Last key operations
        key = attr_path[-1].strip()

        if find:
            return True, data_src.get(key)

        if data_update is not None:
            return completed, update_value(data_src, {key: data_update})

        # If key not in dict, wrap merge value in a dict
        if isinstance(data_src, dict) and data_src.get(key) is None:
            data_merge = {key: data_merge}

        if isinstance(data_merge, (str, int, float, bool)):
            data_src[key] = data_merge
        elif isinstance(data_src, dict):
            update_value(data_src.get(key, data_src), data_merge)
        else:
            update_value(data_src, data_merge)

    return completed, (data_src if not find else current_data)

def serializer(json_map: dict, namespace: list = [], inline_mode: bool = False, filter_params=None) -> str:
    """Converts python dictionary into parsely string"""

    if filter_params is None:
        filter_params = {}
    mode = 'INLINE' if inline_mode else 'NESTED'
    lines = []
    multi_line_keys = []
    is_block_str = False

    def pair_map(key, val, tabs):
        is_multiline = isinstance(val, str) and len(val.split("\n")) > 2
        if is_multiline or key in filter_params.get('_blob_keys', []):
            multi_line_keys.append((f"==={key.replace('content', '')}{filter_params.get(key, '')}", val.strip()))
            return
        if mode == 'INLINE':
            ns = ".".join(namespace)
            value = f"{ns}.{key}: {val}" if bool(namespace) else f"{key}: {val.strip()}"
            lines.append(value)
        else:
            if key:
                lines.append(f"{tabs}{key}: {val}")
            else:
                lines.append(f"{tabs}{val}")

    if isinstance(json_map, (str, bool, int, float)):
        tabs = '    ' * len(namespace)
        return f"{tabs}{json_map}"

    for k, val in json_map.items():
        tab_count = len(namespace) if namespace is not None else 0
        tabs = '    ' * tab_count
        if isinstance(val, (str, int, bool, float)):
            pair_map(k, val, tabs)

        elif isinstance(val, (dict, list)):
            delim = ':' if isinstance(val, dict) else ':-'
            if len(namespace) > 0:
                namespace = namespace + [k]
            else:
                namespace = [k]

            if mode == 'INLINE' and isinstance(val, list):
                ns = ".".join(namespace)
                lines.append(f"{ns}{delim}")
            elif mode == 'NESTED':
                lines.append(f"{tabs}{k}{delim}")

            if isinstance(val, dict):
                nested_value = serializer(json_map=val, namespace=namespace, inline_mode=inline_mode)
                lines.append(f"{nested_value}")
            else:
                maxl = len(val) - 1
                has_scalar = any([isinstance(it, (str, int, float, bool)) for it in val])
                for i, item in enumerate(val):
                    list_value = serializer(json_map=item, namespace=namespace, inline_mode=False)
                    lines.append(f"{list_value}")
                    if i < maxl and not has_scalar:
                        lines.append(f"    -")
            namespace.pop()

    if multi_line_keys:
        [lines.append(f"{mlk}\n{mlv}") for mlk, mlv in multi_line_keys]
    return "\n".join(lines)

def parse_ref_to_files(filepath, file_name, app_ctx, attr_path: str = None, query_params=None):
    if query_params is None:
        query_params = {}
    from pyonir.core.database import CollectionQuery, DeserializeFile
    from pyonir.core.utils import get_attr
    from pyonir.core.loaders import import_module
    from pyonir.core.schemas import GenericQueryModel
    as_dir = os.path.isdir(filepath)
    if as_dir:
        # use proper app context for path reference outside of scope is always the root level
        # Ref parameters with model will return a generic model to represent the data value
        model = None
        generic_model_properties = query_params.get('model')
        include_names = tuple(query_params.get('include_names').split('|')) if query_params.get('include_names') else None
        return_all_files = query_params.get('limit','') == '*'
        if generic_model_properties:
            if '.' in generic_model_properties:
                pkg, mod = os.path.splitext(generic_model_properties)
                mod = mod[1:]
                model = import_module(pkg, callable_name=mod)
            if not model:
                model = GenericQueryModel(generic_model_properties)

        collection = CollectionQuery(filepath, app_ctx=app_ctx,
                                     model=model,
                                     include_names=include_names,
                                     exclude_names=(file_name, 'index.md'),
                                     force_all=return_all_files)
        data = collection.set_params(query_params).paginated_collection()
    else:
        rtn_key = attr_path or 'data'
        p = DeserializeFile(filepath, app_ctx=app_ctx)
        data = get_attr(p, rtn_key) or p
    return data

def process_lookups(value_str: str, file_ctx: DeserializeFile = None) -> Optional[Union[str, dict, list]]:
    """Process $dir and $data lookups in the value string"""
    app_ctx: list = file_ctx.app_ctx
    file_contents_dirpath: str = file_ctx.file_contents_dirpath
    file_name: str = file_ctx.file_name

    value_str = value_str.strip()
    has_lookup = value_str.startswith((LOOKUP_DIR_PREFIX, LOOKUP_DATA_PREFIX, LOOKUP_CALLER_PREFIX))


    if has_lookup:
        from pyonir.core.utils import parse_url_params
        base_path = app_ctx[-1:][0] if value_str.startswith(LOOKUP_DATA_PREFIX) else file_contents_dirpath
        _query_params = value_str.split("?").pop() if "?" in value_str else False
        query_params = parse_url_params(_query_params) if _query_params else {}
        has_attr_path = value_str.split("#")[-1] if "#" in value_str else ''
        is_caller = value_str.strip().startswith(LOOKUP_CALLER_PREFIX)
        value_str = value_str.replace(f"{LOOKUP_DIR_PREFIX}/", "") \
            .replace(f"{LOOKUP_DATA_PREFIX}/", "") \
            .replace(f"{LOOKUP_CALLER_PREFIX}/", "") \
            .replace(f"?{_query_params}", "") \
            .replace(f'#{has_attr_path}', '')

        if is_caller:
            from pyonir import Site
            module_path = value_str.strip().replace(f"{LOOKUP_CALLER_PREFIX}/", "")
            func = Site.load_function_from_path(module_path) if Site else None
            data = func() if callable(func) else None
            return data

        value_str = value_str.replace('../', '').replace('/*', '')
        lookup_fpath = os.path.join(base_path, *value_str.split("/"))
        if not os.path.exists(lookup_fpath):
            print(f"[DEBUG] FileNotFoundError: {lookup_fpath}")
            if file_ctx.is_virtual_route:
                track_retry(file_ctx.file_path, (lookup_fpath, file_name, app_ctx, has_attr_path, query_params))
            return None
        return parse_ref_to_files(lookup_fpath, file_name, app_ctx, attr_path=has_attr_path, query_params=query_params)
    return value_str

def deserialize_line(line_value: str, container_type: Any = None, file_ctx: DeserializeFile = None) -> Any:
    """Deserialize string value to appropriate object type"""

    if not isinstance(line_value, str):
        return line_value

    def is_num(valstr):
        valstr = valstr.strip().replace(',', '')
        if valstr.isdigit():
            return int(valstr)
        try:
            return float(valstr)
        except ValueError:
            return 'NAN'

    line_value = line_value.strip()
    has_inline_dict_expression = DICT_DELIM in line_value and ', ' not in line_value

    if has_inline_dict_expression:
        v = parse_line(line_value)
        return group_tuples_to_objects([v], parent_container=dict())

    if FileCache.get(line_value):
        return FileCache.get(line_value)
    is_num = is_num(line_value)
    if is_num != 'NAN':
        return is_num
    if line_value.lower() == "false":
        return False
    elif line_value.lower() == "true":
        return True
    elif isinstance(container_type, list):
        return [deserialize_line(v, file_ctx=file_ctx)  for v in line_value.split(', ')]
    elif line_value.startswith((LOOKUP_DIR_PREFIX, LOOKUP_DATA_PREFIX, LOOKUP_CALLER_PREFIX)):
        if '{' in line_value:
            line_value = file_ctx.process_site_filter('pyformat', line_value, file_ctx.__dict__)
        return process_lookups(line_value, file_ctx=file_ctx)
    elif line_value.startswith('$'):
        line_value = file_ctx.process_site_filter("pyformat", line_value[1:], file_ctx.__dict__)
    return line_value.lstrip('$')

def get_container_type(delim):
    if LST_DLM == delim:
        return list()
    elif DICT_DELIM == delim or DICT_DELIM.strip() == delim:
        return dict()
    else:
        return str()

def track_retry(file_path: str, value: any):
    """Tracks lines to deserialize"""
    if not RETRY_MAP.get(file_path):
        RETRY_MAP[file_path] = [(".".join(NS), value)]
    else:
        RETRY_MAP[file_path].append((".".join(NS), value))
    NS.pop()

def track_namespace(key: str, is_root: bool = False):
    """Tracks object namespace by key"""
    if not key or key.strip().startswith(FILTER_KEY): return
    if is_root:
        NS.clear()
    NS.append(key.strip())

def parse_line(line: str, from_block_str: bool = False, file_ctx: Any = None) -> tuple:
    """partition key value pairs"""

    try:
        start_fence_block = line.startswith((BLOCK_CODE_FENCE, BLOCK_PREFIX_STR))
        is_end_fence = from_block_str and (start_fence_block or line.strip().endswith((BLOCK_CODE_FENCE, BLOCK_DELIM)))
        if is_end_fence:
            return count_tabs(line), None, None, None, None
        iln_delim = None
        if not from_block_str:
            if line.endswith(DICT_DELIM.strip()): # normalize dict delim
                line = line[:-1] + DICT_DELIM
            iln_delim = [x for x in (
                (line.find(BLOCK_DELIM), BLOCK_DELIM),
                (line.find(STR_DLM), STR_DLM),
                (line.find(LST_DLM), LST_DLM),
                (line.find(DICT_DELIM), DICT_DELIM),
            ) if x[0] != -1]
        key, delim, value = line.partition(iln_delim[0][1]) if iln_delim else (None, None, line)
        line_type = get_container_type(delim) if delim else str()
        is_parent = not value and key is not None
        is_str_block = is_parent and isinstance(line_type, str)
        if start_fence_block:
            line = line.replace(BLOCK_CODE_FENCE, '').replace(BLOCK_PREFIX_STR, '')
            fence_key, *alias_key = line.split(' ', 1)
            key = alias_key[0] if alias_key else fence_key or 'content'
            value = None
            is_str_block = True
            is_parent = True
        line_count = count_tabs(line)
        track_namespace(key, is_root=(line_count==0 or is_parent))
        if not from_block_str:
            key = key.strip() if key else None
            value = deserialize_line(value, container_type=line_type, file_ctx=file_ctx) if value else None
        elif value:
            value += '\n'
        return line_count, key, line_type, value or None, (is_str_block, is_parent)
    except Exception as e:
        raise e
        # return None, None, line.strip(), None, None

def group_tuples_to_objects(items: list[tuple],
                            parent_container: any = None,
                            use_grouped: bool = False,
                            file_ctx: DeserializeFile = None,
                            compress_strings: bool = False) -> list[dict]:
    """Groups list of tuples into list of objects or other container types """

    grouped = []
    current = {}
    is_str = isinstance(parent_container, str) and not use_grouped
    is_list = isinstance(parent_container, list) and not use_grouped
    is_dict = isinstance(parent_container, dict) and not use_grouped
    for tab_count, key, data_type, value, is_string_block in items:
        if is_str:
            parent_container += value.strip() if compress_strings else value or ''
            continue
        elif is_list:
            v = deserialize_line(value, file_ctx=file_ctx)
            value = {key: v} if isinstance(data_type, dict) else v
            parent_container.append(value)
            continue
        elif is_dict:
            update_nested(key, data_src=parent_container, data_merge=deserialize_line(value, file_ctx=file_ctx))
            continue
        if value == LST_DICT_DLM:  # separator → start a new object
            if current:
                grouped.append(current)
                current = {}
            continue

        # Normalize value for nested lists (e.g. child elements)
        if isinstance(value, list) and all(isinstance(v, tuple) for v in value):
            value = group_tuples_to_objects(value, parent_container=data_type)

        current[key] = deserialize_line(value, file_ctx=file_ctx)

    # append last object if not empty
    if current:
        grouped.append(current)

    return grouped or parent_container

def is_comment(line: str) -> bool:
    """Fast comment check using tuple unpacking"""
    return line.startswith((SINGLE_LN_COMMENT, MULTI_LN_COMMENT))

def collect_block_lines(lines: list, curr_tabs: int, is_str_block: tuple[bool, bool] = None, parent_container: Any = None, file_ctx: DeserializeFile = None) -> Tuple[list, int]:
    """Collects lines until stop string is found"""
    collected_lines = []
    cursor = 0
    is_list_dict = False
    pis_str_block, pis_parent = is_str_block or (False, False)
    is_virtual = file_ctx and file_ctx.is_virtual_route
    max = len(lines)
    while cursor < max:
        ln = lines[cursor]
        lt, lk, ld, lv, lb = parse_line(ln, from_block_str=pis_str_block, file_ctx=file_ctx)
        if lb is None:
            if cursor == max - 1:
                cursor += 1
            break
        lis_block_str, lis_parent = lb
        is_nested = lt > curr_tabs
        end_data_block = not is_nested and not pis_str_block
        end_nested_str_block = (curr_tabs > 0 and pis_str_block) and not is_nested
        if end_nested_str_block or end_data_block: break

        if not is_list_dict:
            is_list_dict = lv==LST_DICT_DLM and not ld
        if lis_parent:
            lv, _curs = collect_block_lines(lines[cursor+1:], curr_tabs=lt, is_str_block=lb, parent_container=ld, file_ctx=file_ctx)
            cursor = cursor + _curs
        cursor += 1
        collected_lines.append((lt, lk, ld, lv, lb))

    # Finalize block collection
    compress_strings = curr_tabs > 0 and pis_str_block
    collected_lines = group_tuples_to_objects(collected_lines,
                                                  use_grouped=is_list_dict,
                                                  parent_container=parent_container,
                                                  file_ctx=file_ctx,
                                                  compress_strings=compress_strings)
    return collected_lines, cursor

def process_lines(file_lines: list[str], cursor: int = 0, data_container: Dict[str, Any] = None, file_ctx: DeserializeFile = None) -> Dict[str, Any]:
    """Process lines iteratively instead of recursively"""

    if data_container is None:
        data_container = {}

    line_count = len(file_lines)
    while cursor < line_count:
        line = file_lines[cursor]

        if not line:
            cursor += 1
            continue

        if is_comment(line):
            cursor += 1
            continue

        line_tabs, line_key, line_type, line_value, is_str_block = parse_line(line, file_ctx=file_ctx)
        if line_value is None:
            line_value, _cursor = collect_block_lines(
                file_lines[cursor+1:],
                curr_tabs=line_tabs,
                is_str_block=is_str_block,
                parent_container=line_type,
                file_ctx=file_ctx
            )
            cursor = (_cursor + cursor) + 1 #if line_tabs else _cursor
        else:
            cursor += 1

        if not line_tabs:
            update_nested(line_key, data_container, data_merge=line_value)

        # Cache the $ check
        if line_key and line_key[0] == '$':
            FileCache[line_key] = line_value
    return data_container