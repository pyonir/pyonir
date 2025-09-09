import json
import os
import re

from pyonir.models.mapper import cls_mapper
from pyonir.models.utils import create_file
from pyonir.utilities import get_attr, import_module, parse_query_model_to_object, get_file_created

REG_ILN_LIST = r'([-$@\s*=\w.]+)(\:-)(.*)'
REG_MAP_LST = r'(^[-$@\s*=\w.]+)(\:[`:`-]?)(.*)'
REG_METH_ARGS = r"\(([^)]*)\)"
DICT_DELIM = ": "
LST_DLM = ":-"
STR_DLM = ":` "
ILN_DCT_DLM = ":: "
BLOCK_DELIM = ":|"
BLOCK_PREFIX_STR = "==="
BLOCK_CODE_FENCE = "````"
LOOKUP_EMBED_PREFIX = '$'
LOOKUP_DIR_PREFIX = '$dir'
FILTER_KEY = '@filter'
EmbeddedTypes = dict()

class FileStatuses(str):
    UNKNOWN = 'unknown'
    """Read only by the system often used for temporary and unknown files"""

    PROTECTED = 'protected'
    """Requires authentication and authorization. can be READ and WRITE."""

    FORBIDDEN = 'forbidden'
    """System only access. READ ONLY"""

    PUBLIC = 'public'
    """Access external and internal with READ and WRITE."""

def parse_markdown(content, kwargs):
    """Parse markdown string using mistletoe with htmlattributesrenderer"""
    import html, mistletoe
    # from mistletoe.html_attributes_renderer import HTMLAttributesRenderer
    if not content: return content
    res = mistletoe.markdown(content)
    # res = mistletoe.markdown(content, renderer=HTMLAttributesRenderer)
    return html.unescape(res)


class DeserializeFile:
    """Parsely is a static file parser"""
    _routes_filename = '.routes.md'
    _routes_dirname = 'pages'
    """Directory name that contains page files served as file based routing"""

    def __lt__(self, other: 'DeserializeFile') -> bool:
        """Compares two DeserializeFile instances based on their created_on attribute."""
        if not isinstance(other, DeserializeFile):
            return True
        return self.file_created_on < other.file_created_on

    def __init__(self, file_path: str, app_ctx: 'AppCtx' = None, model: object = None):
        name, ext = os.path.splitext(os.path.basename(file_path))
        self.app_ctx = app_ctx
        self._cursor = None
        self.schema = model
        self._blob_keys = []
        self.file_ext = ext
        self.file_name = name
        self.file_path = str(file_path)
        self.file_dirpath = os.path.dirname(file_path) # path to files contents directory
        self.file_dirname = os.path.basename(self.file_dirpath)
        self.file_exists = os.path.exists(file_path)
        # file data processing
        self.file_contents = ''
        self.file_lines = None
        self.file_line_count = None
        self.data = {}

        # Page specific attributes
        ctx_name, ctx_url, contents_dirpath, ssg_path = app_ctx or ('', '', '', '')
        contents_relpath = file_path.replace(contents_dirpath,'').lstrip('/') if contents_dirpath else ''
        contents_dirname = contents_relpath.split('/')[0]
        is_page = contents_dirname == self._routes_dirname
        self.file_contents_dirpath = contents_dirpath or self.file_dirpath
        self.is_page = is_page
        self.is_home = is_page and contents_relpath == f'{self._routes_dirname}/index'
        self.is_router = self.file_path.endswith(self._routes_filename)
        # page attributes
        # if is_page:
        surl = re.sub(fr'\b{contents_dirname}/\b|\bindex\b', '', contents_relpath) if is_page else contents_relpath
        slug = f'{ctx_url or ""}/{surl}'.lstrip('/').rstrip('/').lower().replace(self.file_ext, '')
        url = '/' if self.is_home else '/' + slug
        self.data['url']  = url
        self.data['slug'] = slug

        # cache
        # if EmbeddedTypes.get(self.file_path):
        #     print(f'Debug: returning cached lookup for {self.file_path}')
        #     self.data = EmbeddedTypes.get(self.file_path).data
        #     return

        # process file data
        self.deserializer()
        # Post-processing
        self.apply_filters()
        # EmbeddedTypes[self.file_path] = self


    @property
    def file_modified_on(self):  # Datetime
        from datetime import datetime
        import pytz
        return datetime.fromtimestamp(os.path.getmtime(self.file_path), tz=pytz.UTC) if self.file_exists else None

    @property
    def file_created_on(self):  # Datetime
        return get_file_created(self.file_path) if self.file_exists else None

    @property
    def file_status(self) -> str:  # String
        return FileStatuses.PROTECTED if self.file_name.startswith('_') else \
            FileStatuses.FORBIDDEN if self.file_name.startswith('.') else FileStatuses.PUBLIC

    def apply_template(self, prop_names: list = None, context: dict = None):
        """Render python format strings for data property values"""
        from pyonir import Site
        context = context or self.data
        prop_names = context.get('@pyformatter', [])
        for prop in prop_names:
            data_value = context.get(prop)
            data_value = Site.parse_pyformat(data_value, self.data)
            update_nested(prop, data_src=self.data, data_update=data_value)

    def apply_filters(self):
        """Applies filter methods to data attributes"""
        from pyonir import Site
        if not bool(self.data): return
        filters = self.data.get(FILTER_KEY)
        if not filters or not Site: return
        for filtr, datakeys in filters.items():
            for key in datakeys:
                mod_val = self.process_site_filter(filtr, get_attr(self.data, key), {"page": self.data})
                update_nested(key, self.data, data_update=mod_val)
        del self.data[FILTER_KEY]


    def deserializer(self):
        """Deserialize file line strings into map object"""
        if self.file_ext == '.md' or self.file_contents:
            self.process_setup()
            if self.file_line_count > 0:
                self.process_line(0, output_data=self.data)
        elif self.file_ext == '.json':
            self.data = self.open_file(self.file_path, rtn_as='json') or {}

        return True

    def process_setup(self):
        lines = self.open_file(self.file_path)
        self.file_lines = lines.strip().split("\n")
        self.file_contents = "\n".join(self.file_lines)
        self.file_line_count = len(self.file_lines)

    def process_line(self, cursor, output_data: any = None, is_blob=None, stop_str: str = '') -> tuple:
        """Deserializes string value"""

        def count_tabs(str_value: str, tab_width: int = 4):
            """Returns number of tabs for provided string"""
            try:
                return round(len(re.match(r'^\s+', str_value.replace('\n', '')).group()) / tab_width)
            except Exception as e:
                return 0

        def process_iln_frag(ln_frag, val_type=None):
            """processing inline values for nested objects"""

            def get_pairs(ln_frag):
                """partition key value pairs"""
                try:
                    methArgs = ''
                    if ln_frag.endswith(DICT_DELIM.strip()):
                        return (ln_frag[:-1], DICT_DELIM, "") + (methArgs,)
                    iln_delim = [x for x in (
                        (ln_frag.find(STR_DLM), STR_DLM),
                        (ln_frag.find(LST_DLM), LST_DLM),
                        (ln_frag.find(DICT_DELIM), DICT_DELIM),
                    ) if x[0] != -1]
                    return ln_frag.partition(iln_delim[0][1]) + (methArgs,)
                except Exception as e:
                    return (None, None, ln_frag.strip(), None)

            keystr, delim, valuestr, methargs = get_pairs(ln_frag)

            parsed_key = keystr.strip() if keystr and keystr.strip() != '' else None
            val_type = get_container_type(delim) if val_type is None else val_type
            parsed_val = valuestr.strip()
            force_scalr = delim and delim.endswith('`') or parsed_val.startswith(LOOKUP_DIR_PREFIX)
            is_inline_expression = bool(parsed_key and parsed_val) and not force_scalr
            if is_inline_expression:
                has_dotpath = "." in parsed_key
                if has_dotpath or (isinstance(val_type, list) and (", " in parsed_val)):  # inline list
                    data_container = [] if delim is None else val_type #get_container_type(delim)
                    for x in parsed_val.split(', '):
                        pk, vtype, pv, pmethArgs = process_iln_frag(x)
                        if vtype != '' and pk:
                            _, pv = update_nested(pk, vtype, pv)
                        update_nested(None, data_container, pv)
                    parsed_val = data_container or pv
                elif isinstance(val_type, list):
                    parsed_val = [parsed_val]

            parsed_val = self.process_value_type(parsed_val)

            return parsed_key, val_type, parsed_val, methargs

        def get_container_type(delim):
            if LST_DLM == delim:
                return list()
            elif DICT_DELIM == delim:
                return dict()
            else:
                return str()


        def stop_loop_block(cur, curtabs, is_blob=None, stop_str=None):
            if cur == self.file_line_count: return True
            in_limit = cur + 1 < self.file_line_count
            stop_comm_blok = self.file_lines[cur].strip().endswith(stop_str) if in_limit and stop_str else None
            nxt_curs_is_blok = in_limit and self.file_lines[cur + 1].startswith(BLOCK_PREFIX_STR)
            nxt_curs_is_blokfence = in_limit and self.file_lines[cur + 1].strip().startswith(BLOCK_CODE_FENCE)
            nxt_curs_is_blokdelim = in_limit and self.file_lines[cur + 1].strip().endswith(BLOCK_DELIM)
            nxt_curs_tabs = count_tabs(self.file_lines[cur + 1]) if (in_limit and not is_blob) else -1
            res = True if stop_comm_blok or nxt_curs_is_blokfence or nxt_curs_is_blok or nxt_curs_is_blokdelim or\
                (nxt_curs_tabs < curtabs and not is_blob) else False
            return res

        stop = False
        stop_iter = False
        while cursor < self.file_line_count:
            self._cursor = cursor
            if stop: break
            ln_frag = self.file_lines[cursor]
            is_multi_ln_comment = ln_frag.strip().startswith('{#')
            is_block_code = ln_frag.strip().startswith(BLOCK_CODE_FENCE)
            is_end_block_code = ln_frag.strip() == BLOCK_CODE_FENCE
            is_ln_comment = not is_blob and ln_frag.strip().startswith('#') or not is_blob and ln_frag.strip() == ''
            comment = is_multi_ln_comment or is_ln_comment

            if comment or is_end_block_code:
                if is_multi_ln_comment or stop_str:
                    cursor, ln_val = self.process_line(cursor + 1, '', stop_str='#}')
            else:
                tabs = count_tabs(ln_frag)
                stop_iter = tabs > 0 and not is_ln_comment or is_blob or stop_str
                try:
                    if is_blob:
                        output_data += ln_frag + "\n"
                    elif not comment and not stop_str:
                        inlimts = cursor + 1 < self.file_line_count
                        is_block = ln_frag.startswith(BLOCK_PREFIX_STR) or ln_frag.endswith("|") or is_block_code
                        # TODO: is_parent should be less restrictive on tabs vs spaces.
                        is_parent = True if is_block else count_tabs(
                            self.file_lines[cursor + 1]) > tabs if inlimts else False
                        parsed_key, val_type, parsed_val, methArgs = process_iln_frag(ln_frag)

                        if is_parent or is_block:
                            parsed_key = parsed_val if not parsed_key else parsed_key
                            parsed_key = "content" if parsed_key == BLOCK_PREFIX_STR else \
                                (parsed_key.replace(BLOCK_PREFIX_STR, "")
                                 .replace(BLOCK_DELIM,'')
                                 .replace(BLOCK_CODE_FENCE,'').strip())
                            if is_block_code:
                                fence_key, *overide_keyname = parsed_key.split(' ', 1)
                                parsed_key = overide_keyname[0] if overide_keyname else fence_key
                                pass
                            cursor, parsed_val = self.process_line(cursor + 1, output_data=val_type, is_blob=isinstance(val_type, str))
                            if isinstance(parsed_val, list) and '-' in parsed_val:  # consolidate list of maps
                                parsed_val = self.post_process_blocklist(parsed_val)

                        # Store objects with $ prefix
                        if parsed_key and parsed_key.startswith('$'):
                            EmbeddedTypes[parsed_key] = parsed_val
                        else:
                            # Extend objects that inheirit from other files during post-processing
                            if parsed_key == '@extends':
                                if not isinstance(parsed_val, dict):
                                    print(f'{self.file_path}')
                                output_data.update(parsed_val)
                                output_data['@extends'] = ln_frag.split(':').pop().strip()
                            else:
                                _, output_data = update_nested(parsed_key, output_data, data_merge=parsed_val)
                except Exception as e:
                    raise

            stop = stop_loop_block(cursor, tabs, is_blob, stop_str=stop_str) if stop_iter else None
            if not stop: cursor += 1

        return cursor, output_data

    def process_value_type(self, valuestr: str):
        """Deserialize string value to appropriate object type"""
        if not isinstance(valuestr, str):
            return valuestr

        def is_num(valstr):
            valstr = valstr.strip().replace(',', '')
            if valstr.isdigit():
                return int(valstr)
            try:
                return float(valstr)
            except ValueError:
                return 'NAN'

        valuestr = valuestr.strip()
        if EmbeddedTypes.get(valuestr):
            return EmbeddedTypes.get(valuestr)
        isnum = is_num(valuestr)
        if isnum != 'NAN':
            return isnum
        if valuestr.strip().lower() == "false":
            return False
        elif valuestr.strip().lower() == "true":
            return True
        elif valuestr.strip().startswith('$'):
            if valuestr.startswith('$') and '{' in valuestr:
                valuestr = self.process_site_filter('pyformat', (valuestr if valuestr.startswith(LOOKUP_DIR_PREFIX) else valuestr[1:]), self.__dict__)
            return self.process_lookups(valuestr)

        return valuestr.lstrip('$')


    @staticmethod
    def open_file(file_path: str, rtn_as: str = 'string'):
        """Reads target file on file system"""

        if not os.path.exists(file_path): return None
        with open(file_path, 'r', encoding='utf-8') as target_file:
            try:
                if rtn_as == "list":
                    return target_file.readlines()
                elif rtn_as == "json":
                    return json.load(target_file)
                else:
                    return target_file.read()
            except Exception as e:
                return {"error": __file__, "message": str(e)} if rtn_as == "json" else []

    @staticmethod
    def post_process_blocklist(blocklist: list):
        if not isinstance(blocklist, list): return blocklist

        def merge(src, trg):
            ns = []
            for k in src.keys():
                tv = trg.get(k)
                if tv:
                    ns.append(k)
                    trg = trg.get(k)

            update_nested(ns, src, trg)
            return src

        _temp_list_obj = {}  # used for blocks that have `-` separated maps
        results = []
        max_count = len(blocklist)
        for i, hashitem in enumerate(blocklist):
            if isinstance(hashitem, dict):
                _temp_list_obj = merge(_temp_list_obj, hashitem)
                if i + 1 == max_count:
                    results.append(dict(_temp_list_obj))
                    break
            else:
                results.append(dict(_temp_list_obj))
                _temp_list_obj.clear()
        blocklist = results
        return blocklist

    def throw_error(self, message: dict):
        msg = {
            'ERROR': f'{self.file_path} found an error on line {self._cursor}',
            'LINE': f'{self.file_lines[self._cursor]}', **message}
        return msg

    @staticmethod
    def process_site_filter(filter_name: str, value: any, kwargs = None):
        from pyonir import Site
        if not Site: return value
        site_filter = Site.Parsely_Filters.get(filter_name)
        return site_filter(value, kwargs)

    def refresh_data(self):
        """Parses file and update data values"""
        self.data = {}
        self._blob_keys.clear()
        self.deserializer()
        self.apply_filters()

    def process_lookups(self, valuestr: str):
        def parse_ref_to_files(filepath, as_dir=0):

            if as_dir:
                from pyonir.models.database import BaseFSQuery

                # use proper app context for path reference outside of scope is always the root level
                # Ref parameters with model will return a generic model to represent the data value
                model = None
                if generic_model_properties:
                    if '.' in generic_model_properties:
                        pkg, mod = os.path.splitext(generic_model_properties)
                        mod = mod[1:]
                        model = import_module(pkg, callable_name=mod)
                    if not model:
                        model = parse_query_model_to_object(generic_model_properties)
                collection = BaseFSQuery(filepath, app_ctx=self.app_ctx,
                                      model=model,
                                      exclude_names=(self.file_name + self.file_ext, 'index.md'),
                                      force_all=return_all_files)
                data = collection.set_params(query_params).paginated_collection()
            else:
                rtn_key = has_attr_path or 'data'
                p = DeserializeFile(filepath, app_ctx=self.app_ctx)
                data = get_attr(p, rtn_key) or p
            return data

        cvaluestr = valuestr.strip()
        valuestr = valuestr.strip()
        has_dir_ref = valuestr.startswith(LOOKUP_DIR_PREFIX)

        if has_dir_ref:
            query_params = valuestr.split("?").pop() if "?" in valuestr else False
            has_attr_path = valuestr.split("#")[-1] if "#" in valuestr else ''
            valuestr = valuestr.replace(f"{LOOKUP_DIR_PREFIX}/", "") \
                .replace(f"?{query_params}", "") \
                .replace(f'#{has_attr_path}', '')
            query_params = dict(map(lambda x: x.split("="), query_params.split('&')) if query_params else '')
            return_all_files = valuestr.endswith('/*')
            generic_model_properties = query_params.get('model')
            valuestr = valuestr.replace('../', '').replace('/*', '')
            lookup_fpath = os.path.join(self.file_contents_dirpath, *valuestr.split("/"))
            if not os.path.exists(lookup_fpath):
                print({
                    'ISSUE': f'FileNotFound while processing {cvaluestr}',
                    'SOLUTION': f'Make sure the `{lookup_fpath}` file exists. Note that only valid md and json files can be processed.'
                })
                return None
            return parse_ref_to_files(lookup_fpath, os.path.isdir(lookup_fpath))
        return valuestr

    def prev_next(self):
        from pyonir.models.database import BaseFSQuery
        if self.file_dirname != 'pages' or self.is_home:
            return None
        return BaseFSQuery.prev_next(self)

    def to_named_tuple(self):
        """Returns a tuple representation of the file data"""
        from collections import namedtuple
        file_keys = [*self.data.keys(),'file_name', 'file_ext', 'file_path', 'file_dirpath', 'file_dirname']
        PageTuple = namedtuple('PageTuple', file_keys)
        return PageTuple(**self.data, file_name=self.file_name, file_ext=self.file_ext, file_path=self.file_path, file_dirpath=self.file_dirpath, file_dirname=self.file_dirname)

    def output_html(self, req: 'PyonirRequest') -> str:
        """Renders and html output"""
        from pyonir import Site
        from pyonir.models.page import BasePage
        # from pyonir.models.mapper import add_props_to_object
        # refresh_model = get_attr(req, 'query_params.rmodel')
        page = cls_mapper(self, self.schema or BasePage)
        Site.apply_globals({'prevNext': self.prev_next, 'page': page})
        html = Site.TemplateEnvironment.get_template(page.template).render()
        Site.TemplateEnvironment.block_pull_cache.clear()
        return html

    def output_json(self, data_value: any = None, as_str=True) -> str:
        """Outputs a json string"""
        from .utils import json_serial
        data = data_value or self
        if not as_str: return data
        return json.dumps(data, default=json_serial)

    def generate_static_file(self, page_request=None, rtn_results=False):
        """Generate target file as html or json. Takes html or json content to save"""
        from pyonir import Site
        count = 0
        html_data = None
        json_data = None
        ctx_static_path = self.app_ctx[3] if self.app_ctx and len(self.app_ctx) > 3 else ''
        slug = self.data.get('slug')
        def render_save():
            # -- Render Content --
            html_data = self.output_html(page_request)
            json_data = self.output_json(as_str=False)
            # -- Save contents --
            create_file(path_to_static_html, html_data)
            create_file(path_to_static_api, json_data)
            return 2

        # -- Get static paths --
        path_to_static_api = os.path.join(ctx_static_path, Site.API_DIRNAME, slug, "index.json")
        path_to_static_html = os.path.join(ctx_static_path, slug, "index.html")

        count += render_save()

        if page_request:
            for pgnum in range(1, page_request.paginate):
                path_to_static_html = os.path.join(self.file_ssg_html_dirpath, str(pgnum + 1), "index.html")
                path_to_static_api = os.path.join(self.file_ssg_api_dirpath, str(pgnum + 1), "index.json")
                page_request.query_params['pg'] = pgnum + 1
                count += render_save()

        # -- Return contents without saving --
        if rtn_results:
            return html_data, json_data

        return count

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

def serializer(json_map: any, namespace: list = [], inline_mode: bool = False, filter_params=None) -> str:
        """Converts json string into parsely string"""

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

