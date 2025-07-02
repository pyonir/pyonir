import os, pytz, re, json
from datetime import datetime
from dataclasses import dataclass, field

from .types import PyonirRequest, ParselyCollection, PyonirCollection, PyonirSchema
from .utilities import dict_to_class, get_attr, get_all_files_from_dir, deserialize_datestr, create_file, get_module, cls_mapper

ALLOWED_CONTENT_EXTENSIONS = ('prs', 'md', 'json', 'yaml')
IGNORE_FILES = ('.vscode', '.vs', '.DS_Store', '__pycache__', '.git', '.', '_', '<', '>', '(', ')', '$', '!', '._')

REG_ILN_LIST = r'([-$@\s*=\w.]+)(\:-)(.*)'
REG_MAP_LST = r'(^[-$@\s*=\w.]+)(\:[`:`-]?)(.*)'
REG_METH_ARGS = r"\(([^)]*)\)"
DICT_DELIM = ": "
LST_DLM = ":-"
STR_DLM = ":` "
ILN_DCT_DLM = ":: "
BLOCK_PREFIX_STR = "==="
LOOKUP_EMBED_PREFIX = '$'
LOOKUP_FILE_PREFIX = '$file'
# LOOKUP_CONTENT_PREFIX = '$content'
LOOKUP_DIR_PREFIX = '$dir'
FILTER_KEY = '@filter'
RESOLVER_KEY = '@resolvers'
DEFAULT_IGNORE_FIELDS = ()
EmbeddedTypes = dict()

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
    import html, mistletoe
    from mistletoe.html_attributes_renderer import HTMLAttributesRenderer
    res = mistletoe.markdown(content, renderer=HTMLAttributesRenderer)
    return html.unescape(res)


@dataclass
class Page:
    """Represents a single page returned from a web request"""
    _mapper = {'created_on': 'file_created_on', 'modified_on': 'file_modified_on'}
    _mapper_merge = True # merges additional data properties to model
    url: str
    created_on: datetime = None
    modified_on: datetime = None
    tags: list = None
    date: datetime = None
    category: str = ''
    template: str = ''
    order: int = 0
    title: str = ''
    content: str = ''
    slug: str = ''
    author: str = 'pyonir'
    entries: ParselyCollection = None
    gallery: dict = None
    file_name: str = ''
    file_path: str = ''
    contents_relpath: str = ''

    def to_json(self) -> dict:
        """Json serializable repr"""
        return {k:v for k,v in self.__dict__.items() if k[0]!='_' and k!='app_ctx'}



@dataclass
class ParselyMedia:
    name: str
    group: str
    url: str
    width: int
    height: int
    file_size: int
    thumbnails: dict = field(default_factory=dict)
    slug: str = ''
    is_thumb: bool = False
    captions: str = ''
    full_url: str = ''
    file_name: str = ''
    app_ctx: list = None
    file_ext: str = ''
    file_path: str = ''
    file_dirpath: str = ''
    file_exists: bool = False
    _sizes: list = field(default_factory=list)

    def open_image(self):
        from PIL import Image
        raw_img = Image.open(self.file_path)
        self.width = get_attr(raw_img, "width", None)
        self.height = get_attr(raw_img, "height", None)
        return raw_img

    def to_json(self) -> dict:
        """Json serializable repr"""
        return {k:v for k,v in self.__dict__.items() if k[0]!='_' and k!='app_ctx'}

    @staticmethod
    def createImagefolders(folderpath: str):
        thumbspath = os.path.join(folderpath, 'thumbnails')
        if not os.path.exists(folderpath):
            os.makedirs(folderpath)
        if not os.path.exists(thumbspath):
            os.makedirs(thumbspath)

    @staticmethod
    async def save_upload(upload_doc, img_folder_abspath, app_ctx) -> 'ParselyMedia':
        """Saves base64 file contents into file system"""
        filename, filedata, rootpath = upload_doc
        file_name, file_ext = os.path.splitext(filename)
        ParselyMedia.createImagefolders(img_folder_abspath)
        new_img_path = os.path.join(img_folder_abspath, file_name + file_ext)
        file_contents = await filedata.read()
        with open(new_img_path, 'wb') as f:
            f.write(file_contents)
        parselyMedia = ParselyMedia.from_path(str(new_img_path), app_ctx)
        return parselyMedia

    @classmethod
    def from_path(cls, file_path, app_ctx):
        p = Parsely(file_path, app_ctx)
        return p.map_to_model(cls)

    def resize(self, sizes=None):
        '''
        Resize each image and save to the upload path in corresponding image size and paths
        This happens after full size images are saved to the filesystem
        '''
        from PIL import Image
        from pyonir import Site
        raw_img = self.open_image()
        if sizes is None:
            sizes = [Site.THUMBNAIL_DEFAULT]
        try:
            for dimensions in sizes:
                width, height = dimensions
                self._sizes.append(dimensions)
                img = raw_img.resize((width, height), Image.Resampling.BICUBIC)
                file_name = f'{self.file_name}--{width}x{height}'
                img_dirpath = os.path.dirname(self.file_path)
                self.createImagefolders(img_dirpath)
                filepath = os.path.join(img_dirpath, Site.UPLOADS_THUMBNAIL_DIRNAME, file_name + '.' + self.file_ext)
                if not os.path.exists(filepath): img.save(filepath)
        except Exception as e:
            raise

    def generate_thumb(self, width, height) -> str:
        """Generates an image accordion to width and height parameters and returns url to the new resized image"""
        self._sizes.append((width, height))
        if not self.thumbnails.get(f'{width}x{height}'): self.resize([(width, height)])
        return self.thumbnails.get(f'{width}x{height}')

    def get_all_thumbnails(self) -> dict | None:
        """Collects thumbnails for the image"""
        if self.is_thumb: return None
        from pyonir import Site
        if self.group != Site.UPLOADS_DIRNAME: self.group = f'{Site.UPLOADS_DIRNAME}/{self.group}'
        thumbs_dir = os.path.join(self.file_dirpath, self.group, Site.UPLOADS_THUMBNAIL_DIRNAME)
        files = get_all_files_from_dir(str(thumbs_dir), app_ctx=self.app_ctx)
        target_name = self.file_name
        thumbs = {}
        # filter files based on name
        for file in files:
            if file.file_name[:len(target_name)] != target_name: continue
            w = file.width
            h = file.height
            thumbs[f'{w}x{h}'] = file
            pass
        return thumbs

class Parsely:
    """Parsely is a static file parser"""
    _Filters = {'md': parse_markdown}  # Global filters that modify scalar values

    def __init__(self, abspth: str, app_ctx=None, generic_query_model = None):
        from pyonir import Site
        assert abspth is not None, f"Parsely was not provided. {abspth} is not a valid string!"
        __skip_parsely_deserialization__ = generic_query_model and hasattr(generic_query_model, '__skip_parsely_deserialization__')
        self._generic_query_model = generic_query_model # when available this property will only process values in model
        self._cursor = None
        self._blob_keys = []
        self.resolver = None
        self.app_ctx = app_ctx # application context for file
        self.file_path = abspth
        self.file_dirpath = os.path.dirname(abspth) # path to files contents directory
        # file data processing
        self.file_contents = ''
        self.file_lines = None
        self.file_line_count = None
        self.data = {}

        self.schema = None
        ctx_url, ctx_name, ctx_dirpath, ctx_staticpath, contents_relpath, file_name, file_ext = self.process_ctx(app_ctx)
        content_type, *content_subs = os.path.dirname(contents_relpath).split(os.path.sep) # directory at root of contents scope
        is_page = content_type in (Site.PAGES_DIRNAME, Site.API_DIRNAME)
        self.file_contents_dirpath =  ctx_dirpath # contents directory path used when querying refs
        self.is_page = is_page
        self.is_home = is_page and contents_relpath == f'{Site.PAGES_DIRNAME}/index'
        self.file_ctx = ctx_name # the application context name
        self.file_dirname = os.path.basename(self.file_dirpath) # nearest parent directory for file
        self.file_data_type = content_type
        self.file_name = file_name
        self.file_ext = file_ext.lstrip('.')

        surl = re.sub(fr'\b{Site.PAGES_DIRNAME}/\b|\bindex\b', '', contents_relpath)
        slug = f'{ctx_url}/{surl}'.lstrip('/').rstrip('/').lower()
        url = '/' if self.is_home else '/' + slug
        # page attributes
        if is_page:
            self.data['url']  = url
            self.data['slug'] = slug
            self.data['tags'] = content_subs
        self.file_ssg_api_dirpath = os.path.join(ctx_staticpath, 'api', slug)
        self.file_ssg_html_dirpath = os.path.join(ctx_staticpath, slug)
        if __skip_parsely_deserialization__: return
        self.deserializer()
        self.apply_filters()


    @property
    def file_status(self):  # String
        if not self.file_exists: return None
        return 'hidden' if self.file_name.startswith('_') else 'public'

    @property
    def file_created_on(self):  # Datetime
        return datetime.fromtimestamp(os.path.getctime(self.file_path), tz=pytz.UTC) if self.file_exists else None

    @property
    def file_modified_on(self):  # Datetime
        return datetime.fromtimestamp(os.path.getmtime(self.file_path), tz=pytz.UTC) if self.file_exists else None

    @property
    def file_exists(self):
        return os.path.exists(self.file_path) if self.file_path else None

    @property
    def template(self) -> str:
        if not self.file_exists or not isinstance(self.data, dict): return "40x.html"
        return self.data.get('template', "pages.html")

    @property
    def date(self):
        """Returns manual published date but defaults to file_created_on date"""
        file_date = self.data.get('date', self.file_created_on) if isinstance(self.data, dict) else self.file_created_on
        if isinstance(file_date, str):
            file_date = deserialize_datestr(file_date)
        return file_date

    @property
    def canonical(self):
        from pyonir import Site
        return f"{Site.origin}{self.data.get('url')}" if Site else None

    def process_ctx(self, app_ctx):
        ctx_dir, ctx_url, ctx_dirpath, ctx_staticpath = app_ctx
        _, _, content_dirpath = self.file_path.partition(ctx_dirpath)
        file_name, file_ext = os.path.splitext(os.path.basename(content_dirpath))
        content_dirpath = content_dirpath.lstrip(os.path.sep).replace(file_ext,'')
        return ctx_url, ctx_dir, ctx_dirpath, ctx_staticpath, content_dirpath, file_name, file_ext

    def set_taxonomy(self) -> list[str] | None:
        if not self.file_exists: return None
        # cat_list = os.path.dirname(self.file_relpath).lstrip('/').split('/')
        self.data['tags'] = self.data.get('tags')
        self.data['category'] = self.data.get('category')

    def set_media(self):
        """Sets data property for media files. (jpeg, png, pdf, etc)"""
        if self.file_ext.endswith(ALLOWED_CONTENT_EXTENSIONS): return
        from PIL import Image
        from pyonir import Site
        group = self.file_dirname.split(f'{Site.UPLOADS_DIRNAME}{os.path.sep}', 1).pop()
        # name = self.data.get('name')
        image_name, *image_captions = self.file_name.replace('.' + self.file_ext, '').split(IMG_FILENAME_DELIM)
        formatted_name = re.sub(r'[^a-zA-Z0-9]+', ' ', image_name).title()
        formated_caption = "".join(image_captions or formatted_name).title()
        _url = self.data.get('url')+'.'+self.file_ext
        _slug = self.data.get('slug')
        is_thumb = Site.UPLOADS_THUMBNAIL_DIRNAME in self.file_dirname
        full_url = _slug.replace(Site.UPLOADS_THUMBNAIL_DIRNAME + '/', '').split('--')[0] + f".{self.file_ext}" \
            if is_thumb else _url
        raw_img = Image.open(self.file_path)
        width = get_attr(raw_img, "width", None)
        height = get_attr(raw_img, "height", None)


        self.data = {
            'file_size': os.path.getsize(self.file_path),
            'url': _url,
            'slug': _slug,
            'name': formatted_name,
            'full_url': full_url,
            'group': group,
            'is_thumb': is_thumb,
            'captions': formated_caption,
            'width':width, 'height': height,
            # 'raw_img': raw_img,
        }

    def map_to_model(self, model):
        if not model:
            file_props = {k: v for k,v in self.__dict__.items() if k in PyonirSchema.default_file_attributes}
            return dict_to_class({**self.data, **file_props, '@model': 'GenericQueryModel'}, self.file_data_type)
        return cls_mapper(self, model)

    def to_json(self) -> dict:
        """Json serializable repr"""
        return self.data

    def apply_filters(self):
        """Applies filter methods to data attributes"""
        if not bool(self.data): return
        filters = self.data.get(FILTER_KEY)
        if not filters: return
        for filtr, datakeys in filters.items():
            ifiltr = Parsely._Filters.get(filtr)
            if not ifiltr: continue
            for key in datakeys:
                mod_val = ifiltr(get_attr(self.data, key), {"page": self.data})
                self.update_nested(key, self.data, data_update=mod_val)
        del self.data[FILTER_KEY]

    async def process_response(self, req: PyonirRequest) -> str:
        """process web request into response"""
        from pyonir.server import JSON_RES, TEXT_RES
        if not self.file_exists:
            self.data = req.render_error() if not req.form and not req.server_response else req.server_response
        else:
            if req.type == JSON_RES:
                # self.map_to_model(self.model)
                return self.output_json(req.server_response)
        return self.output_html(req) if req.type in (TEXT_RES, '*/*') else self.output_json() \
            if req.type == JSON_RES else req.server_response

    async def process_resolver(self, request: PyonirRequest):
        from pyonir import Site
        from pyonir.types import PyonirPlugin
        resolver_obj = self.data.get(RESOLVER_KEY, {}).get(request.method)
        if not resolver_obj: return
        resolver_path = resolver_obj.get('call')

        if not resolver_path: return

        pkg = resolver_path.split('.')
        meth_name = pkg.pop()
        is_system = pkg[0] == 'pyonir'
        if is_system:
            mod_path = os.path.join(Site.pyonir_path,'server.py')
            module, resolver = get_module(mod_path, meth_name)
            # resolver = get_attr(Site.server.resolvers, resolver_path)
        else:
            isplugin: PyonirPlugin = list(filter(lambda p: p.module == pkg[0], Site.available_plugins))
            if len(isplugin): isplugin = isplugin[0]
            if isplugin:
                pkg.pop(0)
                resolver = get_attr(isplugin, resolver_path)
                if not resolver:
                    mod_path = os.path.join(isplugin.resolvers_dirpath, *pkg)+'.py'
                    module, resolver = get_module(mod_path, meth_name)
            else:
                pkg_path = os.path.join(Site.backend_dirpath, *pkg) + '.py'
                if not os.path.exists(pkg_path): pkg_path = os.path.join(Site.backend_dirpath, *pkg, '__init__.py')
                module, resolver = get_module(pkg_path, meth_name)
        request.type = resolver_obj.get('headers', {}).get('accept', request.type)
        self.resolver = resolver

    def deserializer(self):
        """Deserialize file line strings into map object"""
        if not self.file_exists:
            return
        if self.file_ext == 'md' or self.file_contents:
            self.process_setup()
            if self.file_line_count > 0:
                self.process_line(0, output_data=self.data)
        elif self.file_ext == 'json':
            self.data = self.open_file(self.file_path, rtn_as='json') or {}
        elif self.file_ext.upper() in IMAGE_FORMATS:
            self.set_media()
        return True

    def process_setup(self):
        lines = self.file_contents or ''
        if self.file_exists and self.file_ext == 'md':
            lines = self.open_file(self.file_path)
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
                    if ln_frag.endswith(DICT_DELIM.strip()):
                        return (ln_frag[:-1], DICT_DELIM, "") + (methArgs,)
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
            force_scalr = delim and delim.endswith('`') or parsed_val.startswith(LOOKUP_DIR_PREFIX)
            if parsed_key and parsed_val and not force_scalr:
                has_dotpath = "." in parsed_key
                if has_dotpath or (isinstance(val_type, (list, dict)) or ("," in parsed_val)):  # inline list
                    _c = [] if delim is None else get_container_type(delim)
                    for x in parsed_val.split(','):
                        pk, vtype, pv, pmethArgs = process_iln_frag(x)
                        if vtype != '' and pk: _, pv = self.update_nested(pk, vtype, pv)
                        self.update_nested(None, _c, pv)
                    parsed_val = _c or pv

            skip_line = hasattr(self._generic_query_model, parsed_key) if parsed_key and self._generic_query_model else None
            parsed_val = self.process_value_type(parsed_val) if not skip_line else parsed_val

            return parsed_key, val_type, parsed_val, methargs

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
                            # if "|" in parsed_key:
                            #     print('Pipe filters are deprecated', self.abspath)

                        # Store objects with $ prefix
                        if parsed_key and parsed_key.startswith('$'):
                            EmbeddedTypes[parsed_key] = parsed_val
                        else:
                            # Extend objects that inheirit from other files during post processing
                            if parsed_key == '@extends':
                                if not isinstance(parsed_val, dict):
                                    print(f'{self.file_path}')
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
                # Ref parameters with model will return a generic model to represent the data value
                generic_query_model = PyonirSchema.generic_query_model(generic_model_properties)

                if as_dir:
                    file_gen = PyonirCollection.query(filepath,
                                        app_ctx=self.app_ctx,
                                        force_all=return_all_files,
                                        data_model=generic_query_model,
                                        # Ignore files with same name and index files
                                        exclude_file=(self.file_name + '.' + self.file_ext, 'index.md'))
                    d = file_gen.paginated_collection(query_params)
                else:
                    rtn_key = has_attr_path or 'data'
                    p = Parsely(filepath, self.app_ctx)
                    d = get_attr(p, rtn_key) or p
                # EmbeddedTypes[filepath] = d
                return d

            cvaluestr = valuestr.strip()
            valuestr = valuestr.strip()
            has_file_ref = valuestr.startswith(LOOKUP_FILE_PREFIX)
            has_dir_ref = valuestr.startswith(LOOKUP_DIR_PREFIX)
            if '{{' in valuestr:
                valuestr = self._Filters['jinja'](valuestr, self.data)
            if valuestr.startswith('$') and '{' in valuestr:
                valuestr = self._Filters['pyformat'](valuestr[1:] if not has_dir_ref else valuestr, self.__dict__)
            if has_dir_ref:
                query_params = valuestr.split("?").pop() if "?" in valuestr else False
                has_attr_path = valuestr.split("#")[-1] if "#" in valuestr else ''
                valuestr = valuestr.replace(f"{LOOKUP_DIR_PREFIX}/", "") \
                    .replace(f"?{query_params}", "") \
                    .replace(f'#{has_attr_path}', '')
                query_params = dict(map(lambda x: x.split("="), query_params.split('&')) if query_params else '')
                use_rel = valuestr.startswith('./')
                return_all_files = valuestr.endswith('/*')
                generic_model_properties = query_params.get('model')
                valuestr = valuestr.replace('../', '').replace('/*', '')
                dir_root = self.file_contents_dirpath if not use_rel else self.file_dirpath
                # dir_root = os.path.dirname(self.file_dirpath) if self.file_ctx and use_rel else self.file_dirpath
                lookup_fpath = os.path.join(dir_root, *valuestr.split("/"))
                if not os.path.exists(lookup_fpath):
                    return self.throw_error({
                        'ISSUE': f'FileNotFound while processing {cvaluestr}',
                        'SOLUTION': f'Make sure the `{lookup_fpath}` file exists. Note that only valid md and json files can be processed.'
                    })
                return EmbeddedTypes.get(lookup_fpath, parse_ref_to_files(lookup_fpath, os.path.isdir(lookup_fpath)))

        return valuestr.lstrip('$')

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
            if is_multiline or key in filter_params.get('_blob_keys', []):
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
                return {"error": "pyonir.parsely.Parsely.open_file", "message": str(e)} if rtn_as == "json" else []

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

    @classmethod
    def from_input(cls, input_src: dict, app_ctx: tuple):
        """Creates Parsely object setting the data from input src"""
        if not input_src: return None
        res = cls('', app_ctx)
        res.data = input_src
        return res

    @classmethod
    def create_file(cls, file_path: str, contents: dict, app_ctx: tuple) -> 'Parsely':
        """Creates new file on filesystem"""
        dir_path = os.path.dirname(file_path)
        is_json = file_path.endswith('json')
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)
        new_file = create_file(
            file_path,
            contents,
            is_json=is_json,
            mode='w+')
        new_parsely_file = cls(file_path, app_ctx) if new_file else None
        return new_parsely_file

    def throw_error(self, message: dict):
        msg = {
            'ERROR': f'{self.file_path} found an error on line {self._cursor}',
            'LINE': f'{self.file_lines[self._cursor]}', **message}
        return msg

    def refresh_data(self):
        """Parses file and update data values"""
        self.data = {}
        self._blob_keys.clear()
        self.deserializer()

    def prev_next(self):
        if self.file_dirname != 'pages' or self.is_home:
            return None
        return PyonirCollection.prev_next(self)


    def output_json(self, data_value: any = None, as_str=True):
        """Outputs a json string"""
        from .utilities import json_serial
        if not as_str: return {"data": data_value or self}
        return json.dumps({"data": data_value or self}, default=json_serial)

    def output_html(self, req: PyonirRequest):
        """Renders and html output"""
        from pyonir import Site
        Site.TemplateEnvironment.globals['prevNext'] = self.prev_next
        Site.TemplateEnvironment.globals['page'] = self.map_to_model(Page)
        html = Site.TemplateEnvironment.get_template(self.template).render()
        Site.TemplateEnvironment.block_pull_cache.clear()
        return html

    def save(self, file_path=None, contents=None, dir_path=None) -> bool:
        """Saves data into file_path"""
        file_path = file_path or self.file_path
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
        # from pyonir import Site
        # from htmlmin import minify

        count = 0
        html_data = None
        json_data = None

        def render_save():
            # -- Render Content --
            html_data = self.output_html(page_request)
            json_data = self.output_json(as_str=False)
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
