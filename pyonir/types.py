from __future__ import annotations
from dataclasses import dataclass, field
import typing, os, sqlite3
from enum import Enum
from typing import Any, List, Optional, Tuple, Dict

from jinja2 import Environment
from starlette.applications import Starlette
from starlette.requests import Request as StarletteRequest


# Environments
DEV_ENV:str = 'LOCAL'
STAGE_ENV:str = 'STAGING'
PROD_ENV:str = 'PROD'

TEXT_RES: str = 'text/html'
JSON_RES: str = 'application/json'
EVENT_RES: str = 'text/event-stream'
PAGINATE_LIMIT: int = 6

RoutePath: str = str()
RouteFunction: callable = callable
RouteMethods: list[str] = []
PyonirRoute: [RoutePath, RouteFunction, RouteMethods] = []
PyonirEndpoints: [(RoutePath, [PyonirRoute])] = []

AppName: str = str()
ModuleName: str = str()
AppEndpoint: str = str()
AppPaths: list[str] = []
AppContentsPath: str = str()
AppSSGPath: str = str()
AppContextPaths: list[AppName, RoutePath, AppPaths] = []
AppCtx: list[ModuleName, RoutePath, AppContentsPath, AppSSGPath] = []
AppRequestPaths: tuple[RoutePath, AppPaths] = '',''

class PyonirSchema:
    default_file_attributes = ['file_name','file_path','file_dirname','file_data_type','file_ctx','file_created_on']

    """Schema class enables validation when model class initializes"""
    # Schemas configs
    # PROTECTED_FIELD_PREFIX = '@'
    # # Private fields should can be read and written but should not be exposed
    # PRIVATE_FIELDS = ('password', 'ssn', 'auth_token', 'id', 'uid', 'privateKey')
    # # Protected fields are allowed to be read but are not allowed to be changed directly
    # PROTECTED_FIELDS = (
    #                        'created_on', 'modified_on', 'modified_by', 'last_modified_by',
    #                        'date_created', 'date_modified', 'raw', 'provider_model') + PRIVATE_FIELDS

    def validate(self):
        """validates a given property with accessible validation method"""
        for name, value in self.__dict__.items():
            if name.startswith('_'): continue
            validator_fn = getattr(self, f'validate_{name}', None)
            if validator_fn: validator_fn()
        pass

    def __post_init__(self):
        self._validation_errors = []
        self.validate()

    @staticmethod
    def generic_query_model(model_fields: str):
        if not model_fields: return None
        schema_defaults = {k.strip(): None for k in PyonirSchema.default_file_attributes+model_fields.split(',')}
        return type('GenericQueryModel', (object,), schema_defaults)

@dataclass
class PyonirOptions:
    contents_dirpath: str  = '' # base directory path for markdown files
    use_file_based_routing: bool = None # toggles use of file based routing directory
    routes_dirpath: str = ''    # path for resolving file based routing
    routes_api_dirpath: str = '' # path for resolving file based API configured endpoints
    file_based_routes: dict = field(default_factory=list) # configurations for resolving file based routes that contain dynamic path params

@dataclass
class PyonirConfig:
    _mapper_merge: bool = True # merges any data object into class properties
    pass

@dataclass
class ParselyCollection:
    limit: int = 0
    max_count: int = 0
    curr_page: int = 0
    page_nums: list[int, int] = field(default_factory=list)
    items: list['Parsely'] = field(default_factory=list)

class Parsely:
    resolver: callable | None
    app_ctx: AppCtx # application context for file
    file_path: str
    file_dirpath: str # path to files contents directory
    file_contents: str # contents of a file
    file_contents_dirpath: str # contents directory path used when querying refs
    data: dict
    schema: any
    is_page: bool
    is_home: bool # is home page of site
    file_ctx: str # the application context name
    file_dirname: str # nearest parent directory for file
    file_data_type: str # data type based on root contents directory name
    file_name: str # the file name
    file_ext: str # the file extenstion
    file_ssg_api_dirpath: str # the files static generated api endpoint
    file_ssg_html_dirpath: str # the files static generated html endpoint


class PyonirCollection:
    SortedList = None
    get_attr =  None
    dict_to_class = None

    def __init__(self, items: typing.Iterable, sort_key: str = None):
        from sortedcontainers import SortedList
        from pyonir.utilities import get_attr, dict_to_class
        self.SortedList = SortedList
        self.get_attr = get_attr
        self.dict_to_class = dict_to_class

        self._query_path = ''
        key = lambda x: self.get_attr(x, sort_key or 'file_created_on')
        try:
            # l = list(items)
            self.collection = SortedList(items, key=key)
        except Exception as e:
            raise

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
        from pyonir.utilities import get_all_files_from_dir
        gen_data = get_all_files_from_dir(query_path, app_ctx=app_ctx, entry_type=data_model, include_only=include_only,
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
        return self.dict_to_class({"next": nxt, "prev": prv})

    def find(self, value: any, from_attr: str = 'file_name'):
        """Returns the first item where attr == value"""
        return next((item for item in self.collection if getattr(item, from_attr, None) == value), None)

    def where(self, attr, op="=", value=None):
        """Returns a list of items where attr == value"""
        # if value is None:
        #     # assume 'op' is actually the value if only two args were passed
        #     value = op
        #     op = "="

        def match(item):
            actual = self.get_attr(item, attr)
            if not hasattr(item, attr):
                return False
            if actual and not value:
                return True # checking only if item has an attribute
            elif op == "=":
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
        req_pg = self.get_attr(request.query_params, 'pg') or 1
        limit = query_params.get('limit', request.limit)
        curr_pg = int(query_params.get('pg', req_pg)) or 1
        sort_key = query_params.get('sort_key')
        where_key = query_params.get('where')
        if sort_key:
            self.collection = self.SortedList(self.collection, lambda x: self.get_attr(x, sort_key))
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


@dataclass
class Pagination:
    page_num: int = 1
    limit: int = 0


class PyonirRequest:

    def __init__(self, server_request: StarletteRequest):
        from pyonir.utilities import get_attr

        self.server_response = None
        self.file: Parsely | None = None
        self.server_request: StarletteRequest = server_request
        self.raw_path = "/".join(str(self.server_request.url).split(str(self.server_request.base_url)))
        self.method = self.server_request.method
        self.path = self.server_request.url.path
        self.path_params = self.server_request.path_params
        self.url = f"{self.path}"
        self.slug = self.path.lstrip('/').rstrip('/')
        self.query_params = self.get_params(self.server_request.url.query)
        self.parts = self.slug.split('/') if self.slug else []
        self.limit = get_attr(self.query_params, 'limit', PAGINATE_LIMIT)
        self.model = get_attr(self.query_params, 'model')
        self.is_home = (self.path == '')
        self.is_api = False
        self.form = {}
        self.files = []
        self.ip = self.server_request.client.host
        self.host = str(self.server_request.base_url).rstrip('/')
        self.protocol = self.server_request.scope.get('type') + "://"
        self.headers = PyonirRequest.process_header(self.server_request.headers)
        self.browser = self.headers.get('user-agent', '').split('/').pop(0) if self.headers else "UnknownAgent"
        if self.slug.startswith('api'): self.headers['accept'] = JSON_RES
        self.type: TEXT_RES | JSON_RES | EVENT_RES = self.headers.get('accept')
        self.status_code: int = 200

    async def process_request_data(self):
        """Get form data and file upload contents from request"""

        from pyonir import Site
        import json

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

        try:
            try:
                ajson = await self.server_request.json()
                if isinstance(ajson, str): ajson = json.loads(ajson)
                self.form.update(ajson)
            except Exception as ee:
                # multipart/form-data
                form = await self.server_request.form()
                files = []
                for name, content in form.multi_items():
                    if name == 'files':
                        # filedata = await content.read()
                        mediaFile = (secure_upload_filename(content.filename), content, Site.uploads_dirpath)
                        self.files.append(mediaFile)
                    else:
                        if self.form.get(name): # convert form name into a list
                            currvalue = self.form[name]
                            if isinstance(currvalue, list):
                                currvalue.append(content)
                            else:
                                self.form[name] = [currvalue, content]
                        else:
                            self.form[name] = content
        except Exception as e:
            raise

    @property
    def redirect(self):
        return self.form.get('redirect', self.form.get('redirect_to'))

    def derive_status_code(self, is_system_control: bool):
        """Create status code for web request based on a file's availability, status_code property"""
        file_code = self.file.data.get('status_code', 200)
        self.status_code = 404 if not self.file.file_exists else file_code
        # return file_code if self.file and self.file.file_exists or not is_system_control else 404

    def render_error(self):
        """Data output for an unknown file path for a web request"""
        return {
            "url": self.url,
            "method": self.method,
            "status": self.status_code,
            "res": self.server_response,
            "title": f"{self.path} was not found!",
            "content": f"Perhaps this page once lived but has now been archived or permanently removed."
        }

    @staticmethod
    def process_header(headers):
        nheaders = dict(headers)
        nheaders['accept'] = nheaders.get('accept', TEXT_RES).split(',', 1)[0]
        agent = nheaders.get('user-agent', '')
        nheaders['user-agent'] = agent.split(' ').pop().split('/', 1)[0]
        return nheaders

    @staticmethod
    def get_params(url):
        import urllib
        from pyonir.utilities import dict_to_class
        args = {params.split('=')[0]: urllib.parse.unquote(params.split("=").pop()) for params in
                url.split('&') if params != ''}
        if args.get('model'): del args['model']
        return dict_to_class(args, 'query_params')


class PyonirHooks(Enum):
    AFTER_INIT = 'AFTER_INIT'
    ON_REQUEST = 'ON_REQUEST'
    ON_PARSELY_COMPLETE = 'ON_PARSELY_COMPLETE'


class PyonirServer(Starlette):
    ws_routes = []
    sse_routes = []
    auth_routes = []
    endpoints = []
    url_map = {}
    resolvers = {}
    services = {}
    paginate: Pagination = Pagination()

    def response_renderer(self): pass
    def serve_redirect(self): pass
    def create_endpoint(self): pass
    def create_route(self): pass
    def serve_static(self): pass

    def __int__(self):
        super().__init__()

class PyonirBase:
    """Pyonir Base Application Configs"""
    pyonir_path: str = os.path.dirname(__file__)
    endpoint: str = ''
    # Default config settings
    EXTENSIONS = {"file": ".md", "settings": ".json"}
    THUMBNAIL_DEFAULT = (230, 350)
    PROTECTED_FILES = {'.', '_', '<', '>', '(', ')', '$', '!', '._'}
    IGNORE_FILES = {'.vscode', '.vs', '.DS_Store', '__pycache__', '.git'}

    PAGINATE_LIMIT: int = 6
    DATE_FORMAT: str = "%Y-%m-%d %I:%M:%S %p"
    TIMEZONE: str = "US/Eastern"
    ALLOWED_UPLOAD_EXTENSIONS = {'jpg', 'JPG', 'PNG', 'png', 'txt', 'md', 'jpeg', 'pdf', 'svg', 'gif'}

    # Base application  default directories
    # Overriding these properties will dynamicall change path properties
    SOFTWARE_VERSION: str = '' # pyonir version number
    APPS_DIRNAME: str = "apps"  # dirname for any child apps
    BACKEND_DIRNAME: str = "backend"  # dirname for all backend python files
    FRONTEND_DIRNAME: str = "frontend"  # dirname for all themes, jinja templates, html, css, and js
    CONTENTS_DIRNAME: str = "contents"  # dirname for site parsely file data
    THEMES_DIRNAME: str = "themes"  # dirname for site themes
    CONFIGS_DIRNAME: str = 'configs'
    TEMPLATES_DIRNAME: str = 'templates'
    SSG_DIRNAME: str = 'static_site'

    # Contents sub directory default names
    UPLOADS_THUMBNAIL_DIRNAME: str = "thumbnails" # resized image directory name
    UPLOADS_DIRNAME: str = "uploads" # url name for serving uploaded assets
    ASSETS_DIRNAME: str = "public" # url name for serving static assets css and js
    API_DIRNAME: str = "api" # directory for serving API endpoints and resolver routes
    PAGES_DIRNAME: str = "pages" # directory for serving HTML endpoints with file based routing
    CONFIG_FILENAME: str = "app" # main application configuration file name within contents/configs directory

    # Application paths
    app_dirpath: str = '' # directory path to site's main.py file
    app_name: str = '' # directory name for application main.py file
    app_account_name: str = '' # parent directory from the site's root directory (used for multi-site configurations)

    # Application routes
    API_ROUTE = f"/{API_DIRNAME}"  # Api base path for accessing pages as JSON
    ASSETS_ROUTE = f"/{ASSETS_DIRNAME}"  # serves static assets from configured theme
    UPLOADS_ROUTE = f"/{UPLOADS_DIRNAME}"  # Upload base path to access resources within upload directory

    @property
    def module(self):
        """The application module directory name"""
        return self.__module__.split('.').pop()


class DBManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def execute(self, query: str, params: Optional[Tuple[Any, ...]] = None) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(query, params or ())
            conn.commit()

    def fetch_one(self, query: str, params: Optional[Tuple[Any, ...]] = None) -> Optional[Tuple]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(query, params or ())
            return cur.fetchone()

    def fetch_all(self, query: str, params: Optional[Tuple[Any, ...]] = None) -> List[Tuple]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(query, params or ())
            return cur.fetchall()

    def insert(self, table: str, data: Dict[str, Any]) -> None:
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))
        values = tuple(data.values())
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        self.execute(query, values)

    def update(self, table: str, data: Dict[str, Any], where: str, where_params: Tuple) -> None:
        set_clause = ', '.join([f"{col} = ?" for col in data])
        query = f"UPDATE {table} SET {set_clause} WHERE {where}"
        self.execute(query, tuple(data.values()) + where_params)

    def delete(self, table: str, where: str, where_params: Tuple) -> None:
        query = f"DELETE FROM {table} WHERE {where}"
        self.execute(query, where_params)


class PyonirPlugin(PyonirBase):

    def __init__(self, app: PyonirApp, app_entrypoint: str = None):
        self.app: PyonirApp = app
        self.app_entrypoint: str = app_entrypoint # plugin application initializing file
        self.app_dirpath: str = os.path.dirname(app_entrypoint) # plugin directory path
        self.name: str = os.path.basename(self.app_dirpath) # web url to serve application pages
        self.routing_paths: set = set()
        self.CONFIG_FILENAME = self.module
        self.available_models = {}

    @property
    def request_paths(self):
        """Request context for route resolution"""
        return self.endpoint, self.routing_paths

    @property
    def backend_dirpath(self) -> str:
        """Directory path for site's python backend files (controllers, filters)"""
        return os.path.join(self.app_dirpath, self.BACKEND_DIRNAME)

    @property
    def contents_dirpath(self) -> str:
        """Directory path for site's theme folders"""
        return os.path.join(self.app_dirpath, self.CONTENTS_DIRNAME)

    @property
    def frontend_dirpath(self) -> str:
        """Directory path for site's theme folders"""
        return os.path.join(self.app_dirpath, self.FRONTEND_DIRNAME)

    @property
    def ssg_dirpath(self) -> str:
        """Directory path for site's static generated files"""
        return os.path.join(self.app_dirpath, self.SSG_DIRNAME)

    @property
    def app_ctx(self) -> AppCtx:
        return [self.name, self.endpoint, self.contents_dirpath, self.ssg_dirpath]

    def register_templates(self, dir_paths: list):
        """Registers additional paths for jinja templates"""
        if not hasattr(self.app.TemplateEnvironment, 'loader'): return None
        for path in dir_paths:
            if path in self.app.TemplateEnvironment.loader.searchpath: continue
            self.app.TemplateEnvironment.loader.searchpath.append(path)

    def insert(self, file_path: str, contents: dict) -> Parsely:
        """Creates a new file"""
        from pyonir import Parsely
        contents = Parsely.serializer(contents) if isinstance(contents, dict) else contents
        return Parsely.create_file(file_path, contents, app_ctx=self.app_ctx)

    @staticmethod
    def query_files(dir_path: str, app_ctx: tuple, model_type: any = None) -> list[Parsely]:
        from pyonir.utilities import process_contents
        # return PyonirCollection.query(dir_path, app_ctx, model_type)
        return process_contents(dir_path, app_ctx, model_type)

    @staticmethod
    def install_directory(plugin_src_directory: str, site_destination_directory: str):
        from pyonir.utilities import copy_assets
        copy_assets(plugin_src_directory, site_destination_directory)

class PyonirApp(PyonirBase):
    """Pyonir Application"""

    # Application data structures
    server: PyonirServer = None
    TemplateEnvironment: TemplateEnvironment = None
    available_plugins: set = set()

    def __init__(self, app_entrypoint: str):
        from pyonir.utilities import generate_id, get_attr, process_contents
        from pyonir import __version__
        from pyonir.parser import Parsely
        self.SOFTWARE_VERSION = __version__
        self.get_attr = get_attr
        self.app_entrypoint: str = app_entrypoint # application main.py file or the initializing file
        self.app_dirpath: str = os.path.dirname(app_entrypoint) # application main.py file or the initializing file
        self.name: str = os.path.basename(self.app_dirpath) # web url to serve application pages
        self.SECRET_SAUCE = generate_id()
        self.SESSION_KEY = f"pyonir_{self.app_name}"
        self.configs = None
        Parsely._Filters['jinja'] = self.parse_jinja

    @property
    def request_paths(self) -> AppRequestPaths:
        return {self.endpoint, (self.pages_dirpath, self.api_dirpath)}

    @property
    def nginx_config_filepath(self):
        return os.path.join(self.app_dirpath, self.name + '.conf')

    @property
    def unix_socket_filepath(self):
        """WSGI socket file reference"""
        return os.path.join(self.app_dirpath, self.name+'.sock')

    @property
    def ssg_dirpath(self) -> str:
        """Directory path for site's static generated files"""
        return os.path.join(self.app_dirpath, self.SSG_DIRNAME)

    @property
    def logs_dirpath(self) -> str:
        """Directory path for site's log files"""
        return os.path.join(self.app_dirpath, 'logs')

    @property
    def backend_dirpath(self) -> str:
        """Directory path for site's python backend files (controllers, filters)"""
        return os.path.join(self.app_dirpath, self.BACKEND_DIRNAME)

    @property
    def contents_dirpath(self) -> str:
        """Directory path for site's theme folders"""
        return os.path.join(self.app_dirpath, self.CONTENTS_DIRNAME)

    @property
    def frontend_dirpath(self) -> str:
        """Directory path for site's theme folders"""
        return os.path.join(self.app_dirpath, self.FRONTEND_DIRNAME)

    @property
    def pages_dirpath(self) -> str:
        """Directory path to serve as file-based routing"""
        return os.path.join(self.contents_dirpath, self.PAGES_DIRNAME)

    @property
    def api_dirpath(self) -> str:
        """Directory path to serve API as file-based routing"""
        return os.path.join(self.contents_dirpath, self.API_DIRNAME)

    @property
    def plugins_dirpath(self) -> str:
        """Directory path to site's available plugins"""
        return os.path.join(self.app_dirpath, "plugins")

    @property
    def uploads_dirpath(self) -> str:
        """Directory path to site's available plugins"""
        return os.path.join(self.contents_dirpath, self.UPLOADS_DIRNAME)

    @property
    def resolvers_dirpath(self) -> str:
        """Directory path to site's available python server functions"""
        return os.path.join(self.backend_dirpath, "resolvers")

    @property
    def jinja_filters_dirpath(self) -> str:
        """Directory path to site's available Jinja filters"""
        return os.path.join(self.backend_dirpath, "filters")

    @property
    def app_ctx(self) -> AppCtx:
        return [self.name, self.endpoint, self.contents_dirpath, self.ssg_dirpath]

    @property
    def env(self): return os.getenv('APPENV')

    @property
    def is_dev(self): return self.env == DEV_ENV

    @property
    def host(self): return self.get_attr(self.configs, 'app.host', '0.0.0.0') #if self.configs else '0.0.0.0'

    @property
    def port(self):
        return self.get_attr(self.configs, 'app.port', 5000) #if self.configs else 5000

    @property
    def protocol(self):return 'https' if self.is_secure else 'http'

    @property
    def is_secure(self):return self.get_attr(self.configs, 'app.use_ssl', False) #if self.configs else None

    @property
    def domain(self): return self.get_attr(self.configs, 'app.domain', self.host) # if self.configs else self.host

    def parse_jinja(self, string, context=None) -> str:
        """Render jinja template fragments"""
        if not context: context = {}
        if not self.TemplateEnvironment: return string
        try:
            return self.TemplateEnvironment.from_string(string).render(configs=self.configs, **context)
        except Exception as e:
            print(str(e), string)
            # return string
            raise

    def parse_format(self, string, context=None) -> str:
        """Formats python template string"""
        ctx = self.TemplateEnvironment.globals
        if context is not None: ctx.update(**context)
        if not self.TemplateEnvironment: return string
        return string.format(**ctx)

    def setup_templates(self):
        self.TemplateEnvironment = TemplateEnvironment(self)

    def install_plugins(self, plugins: list):
        is_configured = hasattr(self.configs, 'app') and hasattr(self.configs.app, 'enabled_plugins')
        for plugin in plugins:
            plg_id = plugin.__name__
            # if is_configured and plg_id not in self.configs.app.enabled_plugins: continue
            print(f'Installing {plg_id} plugin')
            self.available_plugins.add(plugin(self))
        pass

    def run_plugins(self, hook: PyonirHooks, data_value=None):
        if not hook or not self.available_plugins: return
        hook = hook.name.lower()
        for plg in self.available_plugins:
            if not hasattr(plg, hook): continue
            hook_method = getattr(plg, hook)
            hook_method(data_value, self)

    async def run_async_plugins(self, hook: PyonirHooks, data_value=None):
        if not hook or not self.available_plugins: return
        hook = hook.name.lower()
        for plg in self.available_plugins:
            if not hasattr(plg, hook): continue
            hook_method = getattr(plg, hook)
            await hook_method(data_value, self)

    def run(self, endpoints: PyonirEndpoints, plugins=None):
        """Runs the Uvicorn webserver"""
        from pyonir.libs.plugins.ecommerce import Ecommerce
        from pyonir.libs.plugins.forms import Forms
        from pyonir.libs.plugins.navigation import Navigation
        from pyonir.libs.plugins.fileuploader import FileUploader
        from pyonir.utilities import process_contents
        if plugins is None:
            plugins = [Ecommerce, Forms, Navigation, FileUploader]
        from .server import (setup_starlette_server, start_uvicorn_server,)
        # Initialize Server instance
        self.server = setup_starlette_server(self)
        # Initialize Application settings and templates
        self.configs = process_contents(os.path.join(self.contents_dirpath, self.CONFIGS_DIRNAME), self.app_ctx)
        self.setup_templates()
        self.install_plugins(plugins)

        # Run uvicorn server
        start_uvicorn_server(self, endpoints)

    def generate_static_website(self): pass


class TemplateEnvironment(Environment):

    def __init__(self, app: PyonirApp):
        from jinja2 import FileSystemLoader
        from webassets import Environment as AssetsEnvironment
        from pyonir import PYONIR_JINJA_TEMPLATES_DIRPATH, PYONIR_JINJA_FILTERS_DIRPATH, PYONIR_JINJA_EXTS_DIRPATH
        from webassets.ext.jinja2 import AssetsExtension
        from pyonir.utilities import load_modules_from

        self.themes = PyonirThemes(os.path.join(app.frontend_dirpath, PyonirApp.THEMES_DIRNAME))

        jinja_template_paths = FileSystemLoader([self.themes.active_theme.jinja_template_path, PYONIR_JINJA_TEMPLATES_DIRPATH])
        sys_filters = load_modules_from(PYONIR_JINJA_FILTERS_DIRPATH)
        app_filters = load_modules_from(app.jinja_filters_dirpath)
        installed_extensions = load_modules_from(PYONIR_JINJA_EXTS_DIRPATH, True)
        app_extensions = [AssetsExtension, *installed_extensions]
        app_filters = {**sys_filters, **app_filters}
        super().__init__(loader=jinja_template_paths, extensions=app_extensions)

        def url_for(path):
            rmaps = app.server.url_map if app.server else {}
            return rmaps.get(path, {}).get('path', app.ASSETS_ROUTE)

        app_active_theme = self.themes.active_theme
        #  ''' Custom filters '''
        self.filters.update(**app_filters)
        # load assests tag
        self.assets_environment = AssetsEnvironment(app_active_theme.static_dirpath, app.ASSETS_ROUTE)
        # Add paths containing static assets
        # self.assets_environment.load_path.append(app_active_theme.static_dirpath)
        self.url_expire = False
        self.globals['url_for'] = url_for
        self.globals['configs'] = app.configs.app
        self.globals['request'] = None
        # self.globals.update(**app.jinja_template_globals)

    # @property
    # def app(self):
    #     from pyonir import Site
    #     return Site

    def add_jinja_path(self, path: str):
        pass

    def add_filter(self, filter: callable):
        name = filter.__name__
        print(name)
        self.filters.update({name: filter})
        pass

@dataclass
class Theme:
    _mapper = {'theme_dirname': 'file_dirname', 'theme_dirpath': 'file_dirpath'}
    name: str
    theme_dirname: str = ''
    theme_dirpath: str = ''
    static_dirname: str = 'static' # path to serve theme's static assets (css,js,images) used to style the UI
    templates_dirname: str = 'layouts' # path to serve theme's template files used to rendering HTML pages

    @property
    def static_dirpath(self):
        """directory to serve static theme assets"""
        return os.path.join(self.theme_dirpath, self.static_dirname)

    @property
    def jinja_template_path(self):
        return os.path.join(self.theme_dirpath, self.templates_dirname)

@dataclass
class PyonirThemes:
    """Represents sites available and active theme(s) within the frontend directory."""
    themes_dirpath: str # directory path to available site themes
    _available_themes: PyonirCollection | None = None # collection of themes available in frontend/themes directory

    @property
    def active_theme(self) -> Theme | None:
        from pyonir import Site
        from pyonir.parser import get_attr
        if not Site: return None
        self._available_themes = self.get_available_themes()
        site_theme = get_attr(Site.configs, 'app.theme_name')
        site_theme = self._available_themes.find(site_theme, from_attr='theme_dirname')
        return site_theme

    def get_available_themes(self) -> PyonirCollection | None:
        from pyonir import Site

        if not Site: return None
        fe_ctx = list(Site.app_ctx)
        fe_ctx[2] = Site.frontend_dirpath
        pc = PyonirCollection.query(self.themes_dirpath, fe_ctx, include_only='README.md', data_model=Theme)
        return pc

