import os, pytz, re, json
from datetime import datetime
from typing import Generator

from .types import PyonirRequest
from .utilities import get_attr, allFiles, tupleconverter, deserialize_datestr, Collection, create_file, remove_html_tags

ALLOWED_CONTENT_EXTENSIONS = ('prs', 'md', 'json', 'yaml')
IGNORE_FILES = ('.vscode', '.vs', '.DS_Store', '__pycache__', '.git', '.', '_', '<', '>', '(', ')', '$', '!', '._')

REG_ILN_LIST = r'([-$@\s*=\w.]+)(\:-)(.*)'
REG_MAP_LST = r'(^[-$@\s*=\w.]+)(\:[`:`-]?)(.*)'
REG_METH_ARGS = r"\(([^)]*)\)"
DICT_DELIM = ":"
LST_DLM = ":-"
STR_DLM = ":`"
ILN_DCT_DLM = ":: "
BLOCK_PREFIX_STR = "==="
LOOKUP_EMBED_PREFIX = '$'
LOOKUP_FILE_PREFIX = '$file'
LOOKUP_CONTENT_PREFIX = '$content'
LOOKUP_DIR_PREFIX = '$dir'
FILTER_KEY = '@filter'
DEFAULT_IGNORE_FIELDS = ()
EmbeddedTypes = dict()
# Schemas configs
PROTECTED_FIELD_PREFIX = '@'
# Private fields should can be read and written but should not be exposed
PRIVATE_FIELDS = ('password', 'ssn', 'auth_token', 'id', 'uid', 'privateKey')
# Protected fields are allowed to be read but are not allowed to be changed directly
PROTECTED_FIELDS = (
                       'created_on', 'modified_on', 'modified_by', 'last_modified_by',
                       'date_created', 'date_modified', 'raw', 'provider_model') + PRIVATE_FIELDS

# Image configs
IMG_FILENAME_DELIM = '|'  # delimits the file name and description
IMAGE_FORMATS = (
    'JPEG',  # .jpg, .jpeg
    'JPG',  # .jpg, .jpeg
    'PNG',  # .png
    'GIF',  # .gif
    'BMP',  # .bmp
    'TIFF',  # .tiff, .tif
    'ICO',  # .ico
    'PPM',  # .ppm
    'PGM',  # .pgm
    'PBM',  # .pbm
    'WebP',  # .webp
    'DDS',  # .dds
    'TGA',  # .tga
    'XBM',  # .xbm
    'PCX'  # .pcx
)


def parse_markdown(content, kwargs):
    from mistletoe import markdown
    from mistletoe.html_attributes_renderer import HTMLAttributesRenderer
    return markdown(content, renderer=HTMLAttributesRenderer)


class Parsely:
    """Parsely is a static file parser"""

    Extensions = {}  # Global extensions map that modify return values for parsely file data
    Filters = {'md': parse_markdown}  # Global filters that modify scalar values

    def deserializer(self):
        """Deserialize file line strings into map object"""
        if self.file_ext == 'md' or self.file_contents:
            self.process_setup()
            if self.file_line_count > 0:
                self.process_line(0, output_data=self.data)
        elif self.file_ext == 'json':
            self.data = self.open_file(self.abspath, rtn_as='json') or {}
        return True

    def process_setup(self):
        lines = self.file_contents or ''
        if self.file_exists and self.file_ext == 'md':
            lines = self.open_file(self.abspath)
        self.file_lines = lines.strip().split("\n")
        self.file_contents = "\n".join(self.file_lines)
        self.file_line_count = len(self.file_lines)

    def process_line(self, cursor, output_data: any = None, is_blob=None, stop_str: str = '') -> tuple:
        """Deserializes string value"""

        def count_tabs(str_value: str):
            """Returns number of tabs for provided string"""
            try:
                return round(len(re.match(r'^\s+', str_value.replace('\n', '')).group()) / 4)
            except Exception as e:
                return 0

        def process_iln_frag(ln_frag, val_type=None):
            """processing inline values for nested objects"""

            def get_pairs(ln_frag):
                """partition key value pairs"""
                # faster than regex! 0.01ms vs 0.45ms
                try:
                    methArgs = ''
                    if "(" in ln_frag:
                        ma = re.search(REG_METH_ARGS, ln_frag)
                        methArgs = ma.group(1)
                        ln_frag = ln_frag.replace(ma.group(), '')

                    iln_delim = [x for x in (
                        (ln_frag.find(STR_DLM), STR_DLM),
                        (ln_frag.find(LST_DLM), LST_DLM),
                        (ln_frag.find(DICT_DELIM), DICT_DELIM),
                    ) if x[0] != -1]
                    return ln_frag.partition(iln_delim[0][1]) + (methArgs,)
                except Exception as e:
                    # print(f"`{ln_frag.strip()}` >>> {e}")
                    return (None, None, ln_frag.strip(), None)

            keystr, delim, valuestr, methargs = get_pairs(ln_frag)

            parsed_key = keystr.strip() if keystr and keystr.strip() != '' else None
            val_type = get_container_type(delim) if val_type is None else val_type
            parsed_val = valuestr.strip()
            force_scalr = delim and delim.endswith('`')
            if parsed_key and parsed_val and not force_scalr:
                has_dotpath = "." in parsed_key
                if has_dotpath or (isinstance(val_type, (list, dict)) or ("," in parsed_val)):  # inline list
                    _c = [] if delim is None else get_container_type(delim)
                    for x in parsed_val.split(','):
                        pk, vtype, pv, pmethArgs = process_iln_frag(x)
                        if vtype != '' and pk: _, pv = self.update_nested(pk, vtype, pv)
                        self.update_nested(None, _c, pv)
                    parsed_val = _c or pv

            return parsed_key, val_type, self.process_value_type(parsed_val), methargs

        def get_container_type(delim):
            if LST_DLM == delim:
                return list()
            elif DICT_DELIM == delim:
                return dict()
            else:
                return str()

        def get_stop(cur, curtabs, is_blob=None, stop_str=None):
            if cur == self.file_line_count: return '__STOPLOOKAHEAD__'
            in_limit = cur + 1 < self.file_line_count
            stop_comm_blok = self.file_lines[cur].strip().endswith(stop_str) if in_limit and stop_str else None
            nxt_curs_is_blok = in_limit and self.file_lines[cur + 1].startswith(BLOCK_PREFIX_STR)
            nxt_curs_tabs = count_tabs(self.file_lines[cur + 1]) if (in_limit and not is_blob) else -1
            return '__STOPLOOKAHEAD__' if stop_comm_blok or nxt_curs_is_blok or (
                    nxt_curs_tabs < curtabs and not is_blob) else None

        stop = False
        stop_iter = False
        while cursor < self.file_line_count:
            self._cursor = cursor
            if stop: break
            ln_frag = self.file_lines[cursor]
            is_multi_ln_comment = ln_frag.strip().startswith('{#')
            is_ln_comment = not is_blob and ln_frag.strip().startswith('#') or not is_blob and ln_frag.strip() == ''
            comment = is_multi_ln_comment or is_ln_comment
            if comment:
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
                        is_block = ln_frag.startswith(BLOCK_PREFIX_STR)
                        is_parent = True if is_block else count_tabs(
                            self.file_lines[cursor + 1]) > tabs if inlimts else False
                        parsed_key, val_type, parsed_val, methArgs = process_iln_frag(ln_frag)
                        if methArgs:
                            output_data['@args'] = [arg.replace(' ', '').split(':') for arg in methArgs.split(',')]
                        if is_parent or is_block:
                            parsed_key = parsed_val if not parsed_key else parsed_key
                            parsed_key = "content" if parsed_key == BLOCK_PREFIX_STR else parsed_key.replace(
                                BLOCK_PREFIX_STR, "").strip()
                            cursor, parsed_val = self.process_line(cursor + 1, output_data=val_type,
                                                                   is_blob=isinstance(val_type, str))
                            if isinstance(parsed_val, list) and '-' in parsed_val:  # consolidate list of maps
                                parsed_val = self.post_process_blocklist(parsed_val)
                            if "|" in parsed_key:
                                print('Pipe filters are deprecated', self.abspath)

                        # Store objects with $ prefix
                        if parsed_key and parsed_key.startswith('$'):
                            EmbeddedTypes[parsed_key] = parsed_val
                        else:
                            # Extend objects that inheirit from other files during post processing
                            if parsed_key == '@extends':
                                if not isinstance(parsed_val, dict):
                                    print(f'{self.abspath}')
                                output_data.update(parsed_val)
                                output_data['@extends'] = ln_frag.split(':').pop().strip()
                            else:
                                _, output_data = self.update_nested(parsed_key, output_data, data_merge=parsed_val)
                except Exception as e:
                    # raise Exception(f"{self.file_name}: {str(e)}")
                    raise

            stop = get_stop(cursor, tabs, is_blob, stop_str=stop_str) if stop_iter else None
            if not stop: cursor += 1

        return cursor, output_data

    def process_value_type(self, valuestr: str):
        """Deserialize string value to appropriate object type"""
        if not isinstance(valuestr, str): return valuestr

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

            def parse_ref_to_files(filepath, as_dir=0):
                # use proper app context for path reference outside of scope is always the root level
                app_ctx = self.app_ctx  # if not use_root else ("", "", os.path.dirname(self.absdir))
                if as_dir:
                    return allFiles(filepath, force_all=1, entry_type=None, app_ctx=app_ctx, **query_params)
                isschema = 'schemas' == self.file_type
                rtn_key = has_attr_path or 'data'
                p = ParselySchema.from_path(filepath, app_ctx) if isschema else Parsely(filepath, app_ctx)
                d = get_attr(p, rtn_key) or p
                EmbeddedTypes[filepath] = d
                return d

            cvaluestr = valuestr.strip()
            valuestr = valuestr.strip()
            has_file_ref = valuestr.startswith(LOOKUP_FILE_PREFIX)
            has_dir_ref = valuestr.startswith(LOOKUP_DIR_PREFIX)
            query_params = valuestr.split("?").pop() if "?" in valuestr else False
            has_attr_path = valuestr.split("#")[-1] if "#" in valuestr else ''
            valuestr = valuestr.replace(f"{LOOKUP_DIR_PREFIX}/", "") \
                .replace(f"{LOOKUP_FILE_PREFIX}/", "") \
                .replace(f"?{query_params}", "") \
                .replace(f'#{has_attr_path}', '')
            query_params = dict(map(lambda x: x.split("="), query_params.split('&')) if query_params else '')
            use_root = valuestr.startswith('../')
            valuestr = valuestr.replace('../', '')
            dir_root = os.path.dirname(self.absdir) if self.file_ctx and use_root else self.absdir
            lookup_fpath = os.path.join(dir_root, *valuestr.split("/"))
            if '{{' in lookup_fpath:
                lookup_fpath = self.Filters['jinja'](lookup_fpath, self.data)
            if not os.path.exists(lookup_fpath):
                return self.throw_error({
                    'ISSUE': f'FileNotFound while processing {cvaluestr}',
                    'SOLUTION': f'Make sure the `{lookup_fpath}` file exists. Note that only valid md and json files can be processed.'
                })
            if has_file_ref:
                val = EmbeddedTypes.get(lookup_fpath, parse_ref_to_files(lookup_fpath))
                return val
            elif has_dir_ref:
                return parse_ref_to_files(lookup_fpath, 1)

        return valuestr

    def apply_extensions(self):
        """Apply installed parsely extensions to corresponding data values based on key names"""
        if self.file_type == 'schemas' or self.data == None: return
        for ns, extCls in Parsely.Extensions.items():
            extvalue = self.data.get(ns)
            if not extvalue or isinstance(extvalue, extCls): continue
            mod_val = extCls(self)
            self.update_nested(ns, self.data, data_update=mod_val)
            pass

    def apply_filters(self):
        """Applies filter methods to data attributes"""
        if self.data == None: return
        filters = self.data.get(FILTER_KEY)
        if not filters or self.file_type == 'schemas': return
        for filtr, datakeys in filters.items():
            ifiltr = Parsely.Filters.get(filtr)
            if not ifiltr: continue
            for key in datakeys:
                mod_val = ifiltr(get_attr(self.data, key), self.data)
                self.update_nested(key, self.data, data_update=mod_val)

    @staticmethod
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
            if is_multiline or key in filter_params.get('blob_keys', []):
                multi_line_keys.append((f"==={key.replace('content', '')}{filter_params.get(key, '')}", val.strip()))
                return
            if mode == 'INLINE':
                ns = ".".join(namespace)
                value = f"{ns}.{key}: {val}" if bool(namespace) else f"{key}: {val.strip()}"
                lines.append(value)
            else:
                # if multiline:
                #     lines.append(f"=== {key}\n{val}")
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
            # block_prefx = BLOCK_PREFIX_STR + ' ' if tab_count == 0 else ''
            # print('\t'*len(namespace), k)
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
                    nested_value = Parsely.serializer(json_map=val, namespace=namespace, inline_mode=inline_mode)
                    lines.append(f"{nested_value}")
                else:
                    maxl = len(val) - 1
                    has_scalar = any([isinstance(it, (str, int, float, bool)) for it in val])
                    for i, item in enumerate(val):
                        list_value = Parsely.serializer(json_map=item, namespace=namespace, inline_mode=False)
                        lines.append(f"{list_value}")
                        if i < maxl and not has_scalar:
                            lines.append(f"    -")
                namespace.pop()

        if multi_line_keys:
            [lines.append(f"{mlk}\n{mlv}") for mlk, mlv in multi_line_keys]
        return "\n".join(lines)

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
                return {"error": "pycasso.parsely.Parsely.open_file", "message": str(e)} if rtn_as == "json" else []

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

            Parsely.update_nested(ns, src, trg)
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

    @staticmethod
    def update_nested(attr_path: list, data_src: dict, data_merge=None, data_update=None, find=None) -> dict:
        """Finds or Updates target value based on attribute path"""

        def update_value(target, val):
            """updates target object with value parameter"""
            if isinstance(target, list):
                if isinstance(val, list):
                    target += val
                else:
                    target.append(val)
            elif isinstance(target, dict) and isinstance(val, dict):
                target.update(val)
            elif isinstance(target, str) and isinstance(val, str):
                target = val

            return target

        if not attr_path:
            return True, update_value(data_src, data_merge)
        attr_path = attr_path.strip().split('.') if isinstance(attr_path, str) else attr_path
        completed = len(attr_path) == 1
        if isinstance(data_src, list):
            _, data_merge = Parsely.update_nested(attr_path, {}, data_merge)
            return Parsely.update_nested(None, data_src, data_merge)
        elif not completed:
            _data = {}
            for i, k in enumerate(attr_path):
                if find:
                    _data = data_src.get(k) if not _data else _data.get(k)
                else:
                    completed, _data = Parsely.update_nested(attr_path[i + 1:], data_src.get(k, _data), find=find,
                                                             data_merge=data_merge, data_update=data_update)
                    update_value(data_src, {k: _data})
                    if completed: break
        else:
            k = attr_path[-1].strip()
            if find:
                return True, data_src.get(k)
            if data_update: return completed, update_value(data_src, {k: data_update})
            has_mapping_key = isinstance(data_src, (dict,)) and data_src.get(k)
            if not has_mapping_key: data_merge = {k: data_merge}
            update_value(data_src.get(k, data_src), data_merge) if isinstance(data_src, dict) else update_value(
                data_src, data_merge)

        return completed, (data_src if not find else _data)

    @property
    def file_status(self):  # String
        if not self.file_exists: return None
        return 'hidden' if self.file_name.startswith('_') else 'public'

    @property
    def file_created_on(self):  # Datetime
        return datetime.fromtimestamp(os.path.getctime(self.abspath), tz=pytz.UTC) if self.file_exists else None

    @property
    def file_modified_on(self):  # Datetime
        return datetime.fromtimestamp(os.path.getmtime(self.abspath), tz=pytz.UTC) if self.file_exists else None

    @property
    def file_exists(self):
        return os.path.exists(self.abspath) if self.abspath else None

    @property
    def template(self) -> str:
        if not self.file_exists or not isinstance(self.data, dict): return "40x.html"
        context_template = "index.html" if self.is_home else "pages.html"
        return self.data.get('template') or context_template

    @classmethod
    def from_input(cls, input_src: dict, app_ctx: tuple):
        """Creates Parsely object setting the data from input src"""
        if not input_src: return None
        res = cls('', app_ctx)
        res.data = input_src
        return res

    def __init__(self, abspth, app_ctx=None):
        # assert abspth!=None, "Parsely expects an abspath to a resource"
        ctx_dir, ctx_url, ctx_dirpath, ctx_staticpath = app_ctx
        contents_relpath = abspth.split(ctx_dirpath).pop().lstrip(os.path.sep) if abspth else ''
        contents_rootdir = os.path.dirname(contents_relpath.lstrip(os.path.sep))
        fname, fext = os.path.splitext(os.path.basename(contents_relpath)) if abspth else ('', '')

        self._cursor = None
        self.app_ctx = app_ctx
        self.abspath = abspth
        self.absdir = ctx_dirpath
        self.contents_relpath = contents_relpath
        self.file_ctx = ctx_dir
        self.file_dir = os.path.dirname(contents_relpath)  # os.path.basename(os.path.dirname(abspth)) if abspth else ''
        self.file_type = contents_rootdir.split(os.path.sep)[
            0]  # os.path.basename(os.path.join(self.absdir, ctx_dir).rstrip('/'))
        self.file_name = fname
        self.file_ext = fext.split('.').pop()
        self.file_relpath = contents_relpath
        # f'{self.file_ctx + "/" if ctx_dir else ""}{self.file_dir}/{self.file_name}.{self.file_ext}'
        self.file_contents = ''
        self.file_lines = None
        self.file_line_count = None

        # file data processing
        self.blob_keys = []
        self.data = {}
        self.schema = None
        self.deserializer()
        self.apply_filters()
        self.apply_extensions()
        # page attributes
        is_pg = self.file_type != 'schemas'
        surl = re.sub(r'\bpages/\b|\bindex\b', '', contents_relpath.replace(f'.{self.file_ext}', '')) if is_pg else ''
        slug = self.data.get('url', surl.rstrip('/').lstrip('/'))

        self.is_home = not self.file_ctx and self.file_relpath == '/pages/index.md'
        self.slug = '' if self.is_home else f'{ctx_url}/{slug}'.lstrip('/') if is_pg else ''
        self.url = '/' if self.is_home else '/' + self.slug if is_pg else ''

        self.file_ssg_api_dirpath = os.path.join(ctx_staticpath, 'api', self.slug)
        self.file_ssg_html_dirpath = os.path.join(ctx_staticpath, self.slug)
        pass

    def throw_error(self, message: dict):
        msg = {
            'ERROR': f'{self.file_relpath} found an error on line {self._cursor}',
            'LINE': f'{self.file_lines[self._cursor]}', **message}
        return msg

    def set_file_schema(self, schema_name=''):
        """Sets schema model object described by file's type"""
        from . import Site
        if (not self.file_exists and not schema_name): return
        hasSite = hasattr(Site, 'schemas')
        target_schema_name = self.data.get('@schema', schema_name or self.file_type[:-1])
        # Perform lookup schema name against Site schemas
        schema_fpath = os.path.join(self.absdir, 'schemas', target_schema_name + '.md')
        schema_file = get_attr(Site.schemas, target_schema_name) if hasSite else None
        if os.path.exists(schema_fpath):
            schema_file = ParselySchema.from_path(schema_fpath, self.app_ctx)
        plugin_schema_file = None
        # Perform lookup schema name against Site plugins schemas
        if not schema_file and hasSite:
            for n, plg in Site.available_plugins.items():
                if plugin_schema_file or not hasattr(plg, 'plugin_dirname'): continue
                plgSchemas = get_attr(plg, 'schemas')
                plugin_schema_file = get_attr(plgSchemas, target_schema_name)

        self.schema = plugin_schema_file or schema_file

    def refresh_data(self):
        """Parses file and update data values"""
        self.data = {}
        self.blob_keys.clear()
        self.deserializer()

    def output_json(self, as_str: bool = None, flat: bool = None):
        """Outputs a json string"""
        from .utilities import json_serial
        d = {"data": self}
        if flat:
            pass
        return d if not as_str else json.dumps({"data": self}, default=json_serial)

    def output_html(self, req: PyonirRequest):
        """Renders and html output"""
        from pyonir import Site
        from .utilities import DB

        def set_ctx_navigation(req):
            curr_nav = Site.TemplateParser.globals.get('navigation')
            refresh_nav = bool(req.query_params.get('rnav')) if req else None
            # Get ctx navigation from plugins
            if refresh_nav or not curr_nav:
                curr_nav = DB.get_menus(active_page=self.url)

            Site.TemplateParser.globals['navigation'] = curr_nav

        # if hasattr(req.query_params, 'show_revisions'): self.set_revisions()

        # Site.reload_TemplatePaths(req.req_ctx)
        # if not self.is_api and self.file_exists:
        #     Site.TemplateParser.globals['prevNext'] = self.prev_next()
        Site.TemplateParser.globals['page'] = self
        set_ctx_navigation(req)
        html = Site.TemplateParser.get_template(self.template).render()

        Site.TemplateParser.block_pull_cache.clear()
        return html

    def save(self, file_path=None, contents=None, dir_path=None) -> bool:
        """Saves data into file_path"""
        file_path = file_path or self.abspath
        is_json = file_path.endswith('json')
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)
        return create_file(
            file_path,
            contents or self.data,
            is_json=is_json,
            mode='w+')

    def generate_static_file(self, page_request=None, rtn_results=False):
        """Generate target file as html or json. Takes html or json content to save"""
        from pyonir import Site
        # from htmlmin import minify

        count = 0
        html_data = None
        json_data = None

        def render_save():
            # -- Render Content --
            html_data = self.output_html(page_request)
            json_data = self.output_json()
            # -- Save contents --
            self.save(path_to_static_html, html_data, self.file_ssg_html_dirpath)
            self.save(path_to_static_api, json_data, self.file_ssg_api_dirpath)
            return 2

        # -- Get static paths --
        path_to_static_api = os.path.join(self.file_ssg_api_dirpath, "index.json")
        path_to_static_html = os.path.join(self.file_ssg_html_dirpath, "index.html")

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


class ParselyPage(Parsely):
    """Page object discovered in the contents/pages directory used to resolve page web request"""
    @property
    def resolver(self):
        return self.data.get('@resolver', None)

    def __init__(self, filepath: str, ctx: str = None):
        from pyonir import PAGINATE_LIMIT
        super().__init__(filepath, app_ctx=ctx)

        self.ctx_endpoint: str = ctx[1] if ctx else None
        self.paginate = None
        self.maxCount = None
        self.pagenum = 1
        self.allow_all = None
        self.show_all = None
        self.lookup = None
        self.limit = PAGINATE_LIMIT
        self.is_resolver = self.data.get('@resolver')

    async def process_response(self, req: PyonirRequest) -> str:
        """process web request into response"""
        from pyonir.server import JSON_RES, TEXT_RES, EVENT_RES, apply_plugin_resolvers
        if not self.file_exists:
            self.data = {
                "url": req.url,
                "slug": req.slug,
                "title": f"{req.path} was not found!",
                "res": req.server_response,
                "content": f"Perhaps this page once lived but has now been archived or permananetly removed."
            }
        if self.is_resolver:
            req.type = self.resolver.get('headers',{}).get('accept', req.type)
            await apply_plugin_resolvers(self, req)
        if not self.is_resolver and req.type == JSON_RES: self.set_paginated_entries(req)
        req.status_code = 200 if self.file_exists else 404
        return self.output_html(req) if req.type == TEXT_RES else self.output_json(True) \
            if req.type == JSON_RES else self.data

    def error_page(self, req: PyonirRequest):
        self.data = {
                "url": req.url,
                "slug": req.slug,
                "title": f"{req.path} was not found!",
                "res": req.server_response,
                "content": f"Perhaps this page once lived but has now been archived or permananetly removed."
            }

    def set_paginated_entries(self, request: PyonirRequest):
        """Paginated Files contained under a content type directory"""
        limit = int(request.limit)
        pagenum = int(request.query_params.get('pg', 1))
        show_all = None
        entries = Collection(self.data.get('entries', []))
        gallery = Collection(self.gallery.get('files', []), sortBy='file_created_on') if self.gallery else None
        maxCount = entries.count or 0
        limit = int(limit)
        if self.is_api and show_all:
            limit = maxCount
        start = (pagenum * limit) - limit
        end = (limit * pagenum)
        self.limit = limit
        self.pagenum = pagenum
        self.paginate = (maxCount // limit) + (maxCount % limit > 0)
        self.entries = list(entries.paginate(start=start, end=end, reverse=True))
        if gallery:
            self.data['gallery']['files'] = list(gallery.paginate(start=start, end=end, reverse=True))

    @property
    def is_api(self):
        return self.file_dir == 'api'

    @property
    def name(self):
        return self.data.get('name', self.data.get('title', self.file_name))

    @property
    def title(self):
        return self.data.get('title', self.name)

    @property
    def date(self):
        """Returns manual published date but defaults to file_created_on date"""
        import datetime
        file_date = self.data.get('date', self.file_created_on) if isinstance(self.data, dict) else self.file_created_on
        event_date = Collection.get_attr(self.data, 'event.begins.start_datetime')
        if isinstance(file_date, str):
            file_date = deserialize_datestr(file_date)
        return event_date if isinstance(event_date, datetime.datetime) else file_date

    @property
    def created_on(self):
        return self.file_created_on

    @property
    def modified_on(self):
        return deserialize_datestr(self.data.get('@last_saved', self.file_modified_on))

    @property
    def excerpt(self):
        """Summary of content in 280 characters"""
        if not self.data or not isinstance(self.data, dict): return None
        default_excerpt = remove_html_tags(self.content or '')[0:280] + "..."
        return self.data.get('excerpt', default_excerpt)

    @property
    def content(self):
        return self.data.get('content',
                             ' ')  # self.markdown_parser(self.data.get('content')) if self.data.get('content') else ''

    @property
    def canonical(self):
        from pyonir import Site
        return f"{Site.SITE_CONFIGS.domain}{self.url}"

    @property
    def tags(self):
        if not self.file_exists: return None
        catlist = os.path.dirname(self.file_relpath).lstrip('/').split('/')
        return self.data.get('tags', '').split(',') if self.data.get('tags') else catlist

    @property
    def category(self) -> str:
        if not self.file_exists: return None
        catlist = os.path.dirname(self.file_relpath).lstrip('/').split('/')
        return self.data.get('category', catlist[-1])

    @property
    def order(self):
        return self.data.get('order', 99)

    @property
    def author(self):
        return self.data.get('author')

    @property
    def status(self):
        return self.data.get('status', self.file_status)

    @property
    def menu(self):
        if not self.data: return None
        return self.data.get('menu')

    @property
    def menu_parent(self):
        if not self.data: return None
        return self.data.get('menu_parent', None)

    @property
    def model(self):
        """overrides page schema model name"""
        return self.data.get('page_schema', None) if self.data else None

    @property
    def redirect_url(self):
        return self.data.get('redirect_url') if self.data else None

    @property
    def js(self):
        """Javascript content block"""
        if not self.file_exists or not self.data.get('js'): return None
        js_str = self.data.get('js') if isinstance(self.data.get('js'), str) else None
        jsdata = {"script": js_str}
        if isinstance(self.data.get('js'), dict):
            jsdata.update(**self.data.get('js'))
        return jsdata  # tupleconverter('js',jsdata)

    @property
    def css(self):
        """CSS styles to include on html template"""
        if not self.file_exists or not self.data.get('css'): return None
        css_str = self.data.get('css') if isinstance(self.data.get('css'), str) else None
        cssdata = {"style": css_str}
        if isinstance(self.data.get('css'), dict):
            cssdata.update(**self.data.get('css'))
        return tupleconverter('css', cssdata)

    @property
    def gallery(self):
        """Gallery plugin object"""
        return self.data.get('gallery')

    @property
    def form(self):
        """Form plugin object"""
        return self.data.get('form')

    @property
    def ctx_redirect(self):
        return self.data.get('redirect') if isinstance(self.data, dict) else None

    def prev_next(self):
        """Returns sorted dictionary for prev and next page based on date specified in file"""
        if self.file_type != 'pages' or self.is_home: return None

        def pgen():
            for item in Collection(allFiles(os.path.dirname(self.abspath))).collection:
                yield item

        # result = {"next": False, "prev": False}
        prv = None
        nxt = None
        home = {'title': self.category, 'url': os.path.dirname(self.url)}
        gen_data = pgen()
        for file in gen_data:
            if file.file_status == 'hidden' or not file.file_exists: continue
            if self.file_name == file.file_name:
                try:
                    nxt = next(gen_data)
                    break
                except StopIteration:
                    if nxt:
                        nxt.set_file_schema()
                        nxt = nxt.file_schema.map_to_schema(nxt) if nxt.file_schema else nxt
                    if prv:
                        prv.set_file_schema()
                        prv = prv.file_schema.map_to_schema(prv) if prv.file_schema else prv
                    pass
            else:
                prv = file

        return {"next": nxt or home, "prev": prv or home, "home": home}


class ParselyMedia(Parsely):
    """Represents an image or media document file"""

    @property
    def thumbnails(self):
        """Returns a map of thumbnail sizes available for media file"""
        if not hasattr(self, 'sizes'): return None
        thumbs = {}
        for dimes in self.sizes:
            w, h = dimes
            tname = '{file_name}--{width}x{height}.{ext}'.format(file_name=self.file_name, width=w, height=h,
                                                                ext=self.file_ext)
            tpath = os.path.join(os.path.dirname(self.abspath), 'thumbnails', tname)
            if not os.path.exists(tpath): continue
            thumbs[f'{w}x{h}'] = f'{self.file_dir}/thumbnails/{tname}'
        return thumbs

    def __init__(self, file_path: str = None, app_ctx=None):
        super().__init__(file_path, app_ctx)
        from pyonir import UPLOADS_ROUTE

        self.sizes = []
        self.url = f"{UPLOADS_ROUTE}{self.file_relpath.replace(self.file_type, '')}"
        self.slug = self.url.lstrip('/')
        self.is_img = None
        self.raw_img = None
        self.name = ''
        self.is_thumb = None
        self.set_data()

    def set_data(self):
        from PIL import Image
        from pyonir import UPLOADS_DIRNAME, UPLOADS_THUMBNAIL_DIRNAME
        if not self.file_exists: return
        image_name, *image_captions = self.file_name.replace('.'+self.file_ext,'')\
                                       .split(IMG_FILENAME_DELIM)

        is_thumb = UPLOADS_THUMBNAIL_DIRNAME in self.file_dir
        formatted_name = re.sub(r'[^a-zA-Z0-9]+', ' ', image_name).title()
        formated_caption = "".join(image_captions or self.name).title()
        full_img = self.url.replace(UPLOADS_THUMBNAIL_DIRNAME+'/','').split('--')[0]+f".{self.file_ext}"\
        if is_thumb else self.url
        self.raw_img = Image.open(self.abspath)
        self.name = formatted_name
        self.is_thumb = is_thumb
        self.data = {
            "@schema": "media",
            "name": self.name,
            "url": self.url,
            "full_url": full_img,
            "slug": self.slug,
            "date": self.file_created_on,
            "thumbnails": self.thumbnails,
            "type": self.file_ext,
            "group": self.file_dir.split(f'{UPLOADS_DIRNAME}{os.path.sep}', 1).pop(),
            "captions": formated_caption.title(),
            "size": os.path.getsize(self.abspath),
            "width": get_attr(self.raw_img, "width", None),
            "height": get_attr(self.raw_img, "height", None)
        }

    @staticmethod
    def createImagefolders(folderpath: str):
        thumbspath = os.path.join(folderpath, 'thumbnails')
        if not os.path.exists(folderpath):
            os.makedirs(folderpath)
        if not os.path.exists(thumbspath):
            os.makedirs(thumbspath)

    @staticmethod
    async def save_upload(upload_doc, img_folder_abspath) -> 'ParselyMedia':
        """Saves base64 file contents into file system"""
        filename, filedata, rootpath = upload_doc
        file_name, file_ext = os.path.splitext(filename)
        ParselyMedia.createImagefolders(img_folder_abspath)
        abspath = os.path.join(img_folder_abspath, file_name+file_ext)
        file_contents = await filedata.read()
        with open(abspath, 'wb') as f:
            f.write(file_contents)
        parselyMedia = ParselyMedia.new(abspath)
        return parselyMedia

    @classmethod
    def new(cls, file_path):
        from pyonir import Site
        pm = cls(file_path, Site.files_ctx)
        return pm

    def resize(self, sizes=None):
        '''
        Resize each image and save to the upload path in corresponding image size and paths
        This happens after full size images are saved to the filesystem
        '''
        from PIL import Image
        from pyonir import THUMBNAIL_DEFAULT
        if sizes is None:
            sizes = [THUMBNAIL_DEFAULT]
        try:
            for dimensions in sizes:
                width, height = dimensions
                self.sizes.append(dimensions)
                img = self.raw_img.resize((width, height), Image.Resampling.BICUBIC)
                file_name = f'{self.file_name}--{width}x{height}'
                folderpath = os.path.dirname(self.abspath)
                self.createImagefolders(folderpath)
                filepath = os.path.join(folderpath,'thumbnails', file_name + '.' + self.file_ext)
                if not os.path.exists(filepath): img.save(filepath)
        except Exception as e:
            raise

    def generate_thumb(self, width, height) -> str:
        """Generates an image accordion to width and height parameters and returns url to the new resized image"""
        self.sizes.append((width, height))
        if not self.thumbnails.get(f'{width}x{height}'): self.resize([(width, height)])
        return self.thumbnails.get(f'{width}x{height}')


class ParselySchema:
    """Schema file"""

    @property
    def data(self):
        return self.file.data

    def __init__(self, parselyfile: Parsely, table_name: str = None) -> None:

        self.foreign_schemas = {}
        """ map of foriegn keys schema definitions relative to this schema"""
        self.file: Parsely = parselyfile
        """ parsely schema definitions """
        self.table = self.file_data.get('@table', (table_name or f"{self.file.file_ctx}.{self.file.file_type}"))
        self.name = self.file.file_name or self.file_data.get('@schema', table_name or 'embedded')
        self.validator: SchemaValidator = SchemaValidator(self)
        self.file_keys: list[str] = self.file.data.keys()
        pass

    @classmethod
    def from_path(cls, path, app_ctx):
        """Creates new ParselySchema from file path"""
        if not isinstance(path, str): return None
        f = Parsely(path, app_ctx)
        return cls(f)

    @classmethod
    def from_data(cls, data, app_ctx, schema_name=None):
        f = Parsely.from_input(data, app_ctx)
        return cls(f, table_name=schema_name) if data else None

    def map_to_schema(self, src_data, block_private: bool = True):
        """Returns dict representing schema fields"""
        enabled_extensions = (dict, Parsely) + tuple(
            ext for _, ext in Parsely.Extensions.items() if hasattr(ext, 'parsely_extension'))
        protected = self.protected_fields + PROTECTED_FIELDS
        private_fields = self.private_fields or PRIVATE_FIELDS
        result = dict({})
        app_ctx = self.file.app_ctx
        # src_tbl_name = src_data.file_content_schema_tbl_name if hasattr(src_data, 'file_content_schema_tbl_name') else self.table
        result = dict({"@schema_src": f'{self.name}'})

        def prefixer(field):
            """Prefix protected symbol on field names"""
            field = field.replace('*', '').strip()
            if self.provider_model:
                field = self.provider_model.get(field, field)
            try:
                return f"{PROTECTED_FIELD_PREFIX}{field}" if field in protected and self.with_symbols and not self.is_safe else field
            except Exception as e:
                return field

        def obfuscate(key, value):
            """Hides values for any private fields in object schema"""
            if self.is_safe: return value
            return "***" if block_private and key in private_fields else value

        def validateType(value):
            return value

        def convert_sch(k) -> ParselySchema:
            """Converts embedded schema objects into ParselySchema objects"""
            embed_obj_sch = self.file_data.get(k, None)
            embed_obj_sch = embed_obj_sch[0] if isinstance(embed_obj_sch, list) else embed_obj_sch
            embed_obj_sch = embed_obj_sch.data if isinstance(embed_obj_sch, Parsely) else embed_obj_sch
            if isinstance(embed_obj_sch, str) or not embed_obj_sch: return None
            return ParselySchema.from_data(embed_obj_sch, app_ctx, k)

        def get_value(k):
            """Maps schemas for nested objects"""
            v = get_attr(src_data, k)
            v = get_attr(src_data.data, k) if not v and isinstance(src_data, Parsely) else v
            if not v: return v
            sch = convert_sch(k)
            if isinstance(v, enabled_extensions):
                v = sch.map_to_schema(v) if sch else v
            elif isinstance(v, (list, Generator, set)):
                v = [sch.map_to_schema(p) if sch else p for p in v]
            return obfuscate(k, v)

        try:
            for k in self.all_fields:
                if k in ('provider_model',): continue
                v = get_value(k)
                k = prefixer(k)
                v = validateType(v)
                result.update({k: v})

            return result
        except Exception as e:
            result.update({
                "@schema_src": "MAPPING ERROR",
                "msg": str(e)
            })
            raise

    def merge(self, input_data: dict, src_data: dict):
        sch_data = dict()
        etc_data = dict()
        for ik, iv in input_data.items():
            if ik in DEFAULT_IGNORE_FIELDS: continue
            if ik in self.all_fields:
                sch_data[ik] = iv
            etc_data[ik] = iv
        sch_data.update(etc_data)
        src_data.update(sch_data)
        return src_data

    def set_foreign_schemas(self):
        res = {}
        for fk in self.foreign_keys:
            v = self.file_data.get(fk)
            is_list = isinstance(v, list) and isinstance(v[0], dict)
            edata = v[0] if is_list else v
            fschma = ParselySchema.from_data(edata,
                                             self.table + "." + fk)  # if edata else Site.schemas if Site else None
            if not fschma: continue
            res.update({fk.lower(): fschma})
        if res:
            self.foreign_schemas = tupleconverter("ForeignSchemas", res)

    @property
    def is_safe(self):
        """Bypass prefix and obfuscating any fields"""
        if not self.file: return None
        return self.file_data.get('@safe', None)

    @property
    def with_symbols(self):
        """Returns protected attributes with special annotation prefex"""
        if not self.file_data: return None
        return self.file_data.get('@with_symbols', None)

    @property
    def file_data(self):
        if not self.file: return dict()
        return self.file.data  # if isinstance(self.file.data, dict) else self.file.data.data

    @property
    def provider_model(self) -> dict:
        """Transformer map of domain attributes to public attribute names"""
        if not self.file_data: return dict()
        return self.file_data.get('@provider_model', dict())

    @property
    def foreign_keys(self) -> tuple:
        """List of fields that are foreign keys"""
        if not self.file_data: return tuple()
        return tuple((fk for fk in self.file_data.get('@fk', tuple())))

    @property
    def primary_key(self):
        """Primary key column name"""
        if not self.file_data: return None
        return self.file_data.get('@pk', 'id')

    @property
    def private_fields(self) -> tuple:
        """List of attributes to obfuscate that includes the system defaults"""
        if not self.file_data: return tuple()
        return tuple(x for x in self.file_data.get('@private_keys', tuple()))

    @property
    def protected_fields(self) -> tuple:
        """Read only fields"""
        if not self.file_data: return tuple()
        keys = self.file_keys or []
        return tuple((f.replace('@', '') for f in keys if f.startswith('@') and f not in ("@fk", "@pk")))

    @property
    def public_fields(self) -> tuple:
        """Read and Writtable fields"""
        if not self.file_data: return ()
        # keys = self.file_keys or
        return tuple((f.replace('*', '') for f in self.file_keys if not f.startswith('@')))

    @property
    def required_fields(self) -> tuple:
        """Required field name for object and not null fields"""
        if not self.file_data: return tuple()
        keys = self.file_keys or []
        return tuple((f.replace('*', '') for f in keys if f and f.replace('@', '').startswith('*')))

    @property
    def all_fields(self):
        return tuple(set(self.required_fields + self.public_fields))


class SchemaValidator:
    """Collection of functions to validate schema values"""

    @property
    def validation_errors(self):
        return list(self.errors_bag.values()) if bool(self.errors_bag) else None

    @property
    def is_valid(self):
        return True if len(self.errors_bag) == 0 or self.schema is None else False

    def __init__(self, schema):
        self.schema = schema
        self.__schema_value = None
        self.__schema_key = None
        self.errors_bag = dict()

    def send_error(self, msg=None):
        self.errors_bag[self.__schema_key] = f"{msg or 'error found'}"

    def validate_input(self, input_data):
        """Validates input data against available schema definitions"""
        self.errors_bag.clear()
        for field in self.schema.required_fields:
            schema_methods = self.schema.file.data.get(f"*{field}")
            self.__schema_key = field
            self.__schema_value = get_attr(input_data, self.__schema_key)
            for meth in schema_methods.split('|'):
                if getattr(self, meth.strip())() is True: continue
                break
        return self

    def update(self, schema):
        self.schema = schema

    def bool(self):
        return isinstance(self.__schema_value, bool)

    def is_int(self):
        return isinstance(self.__schema_value, int) or isinstance(self.__schema_value, float)

    def string(self):
        if isinstance(self.__schema_value, str):
            return True
        else:
            self.send_error(f"{self.__schema_key} is not a string! Got an {type(self.__schema_value).__name__}")

    def is_date(self):
        import datetime
        date_obj = deserialize_datestr(self.__schema_value, auto_correct=False)
        if not isinstance(date_obj, datetime.datetime):
            self.send_error(f"{self.__schema_value} is not a valid date value. {date_obj}")
        else:
            return True

    def is_list(self):
        return isinstance(self.__schema_value, list)

    def as_address(self):
        try:
            street, city, state_zip = self.__schema_value.split(',')
            state, zip = state_zip.strip().split(' ')
            self.input_data[self.__schema_key] = {
                "street": street.strip(),
                "city": city.strip(),
                "state": state.strip(),
                "zip": zip.strip()
            }
            return True
        except Exception as e:
            self.send_error(str(e))
            return False

    def check_role(self):
        return True

    def check_email(self, email=None):
        try:
            from django.core.validators import validate_email, ValidationError
            validate_email(email or self.__schema_value)
            return True
        except ValidationError:
            self.send_error(f"{self.__schema_key.capitalize()} is not a valid.")
            # return 'Email is not valid.'
            return False

    def min(self, min_num):
        has_minimum = len(self.__schema_value) >= int(min_num)
        if not has_minimum:
            self.send_error(f"{self.__schema_key} should have a minimum of {min_num} characters.")
        return has_minimum

    def check_pwd(self):
        # from pycasso.utils import Collection
        # pswd = password or Collection.get_attr(self.schema.input_data, 'password', True)
        error = 'Password requires alpha numeric values with 6 characters.'
        if not self.__schema_value:
            error = 'Must provide a password.'
        elif not self.__schema_value.isdigit() and len(self.__schema_value) > 5:
            return True
        self.send_error(error)
        return False

    def sanitize(self):
        illegal_chars = "<,>,!,+,-,(,),~,`,\,/,:,;,&,^,%,$,#".split(',')
        for c in self.__schema_value:
            if c in illegal_chars:
                self.send_error(f"{self.__schema_key} contains an invalid character.")
                return False
        return True  # if self.__schema_value not in illegal_chars else False
