from __future__ import annotations
import typing, os
from collections import defaultdict

from jinja2 import Environment
from starlette.requests import Request as StarletteRequest

from pyonir.pyonir_types import PyonirServer, Theme, PyonirHooks, Parsely, ParselyPagination, AppRequestPaths, AppCtx, \
    PyonirRouters, RoutePath, PyonirRestResponse, PyonirAppSettings, EnvConfig, PagesPath, APIPath
from pyonir.utilities import expand_dotted_keys, get_attr

# Environments
DEV_ENV:str = 'LOCAL'
STAGE_ENV:str = 'STAGING'
PROD_ENV:str = 'PROD'

TEXT_RES: str = 'text/html'
JSON_RES: str = 'application/json'
EVENT_RES: str = 'text/event-stream'
PAGINATE_LIMIT: int = 6

from dataclasses import dataclass, field, replace, asdict
from typing import Optional, Type, TypeVar

T = TypeVar("T", bound="PyonirSchema")

class PyonirSchema:
    """
    Interface for immutable dataclass models with CRUD and session support.
    Provides per-instance validation and session helpers.
    """

    def __init__(self):
        # Each instance gets its own validation error list
        self._errors: list[str] = []
        self._deleted: bool = False
        self._private_keys: list[str] = []

    def is_valid(self) -> bool:
        """Returns True if there are no validation errors."""
        return not self._errors

    def validate(self):
        """
        Validates fields by calling `validate_<fieldname>()` if defined.
        Clears previous errors on every call.
        """
        for name in self.__dict__.keys():
            if name.startswith("_"):
                continue
            validator_fn = getattr(self, f"validate_{name}", None)
            if callable(validator_fn):
                validator_fn()

    def __post_init__(self):
        """
        Called automatically in dataclasses after initialization.
        Ensures validation runs for each instance.
        """
        # Reset errors for new instance
        self._errors = []
        self.validate()

    # --- Database helpers ---
    def save_to_file(self, file_path: str) -> bool:
        """Saves the user data to a file in JSON format"""
        from pyonir.utilities import create_file
        return create_file(file_path, self.to_dict(obfuscate=False))

    def save_to_session(self: T, request: PyonirRequest,key: str = None, value: any = None) -> None:
        """Convert instance to a serializable dict."""
        request.server_request.session[key or self.__class__.__name__.lower()] = value

    @classmethod
    def create(cls: Type[T], **data) -> T:
        """Create and return a new instance (validation runs in __post_init__)."""
        instance = cls(**data)
        return instance

    @classmethod
    def from_file(cls: Type[T], file_path: str, app_ctx) -> T:
        """Create an instance from a file path."""
        from pyonir.parser import Parsely
        parsely = Parsely(file_path, app_ctx=app_ctx)
        return parsely.map_to_model(cls)

    @classmethod
    def from_dict(cls, data: typing.Dict) -> typing.Self:
        """Instantiate entity from dict."""
        from pyonir.parser import Parsely
        values = data if isinstance(data, dict) else data.data if isinstance(data, Parsely) else data
        return cls(**values)

    @classmethod
    def create_table(cls) -> str:
        """Return SQL query to create the table for this entity."""
        columns = []
        for attr, typ in cls.__annotations__.items():
            if typ == str:
                columns.append(f"{attr} TEXT")
            elif typ == int:
                columns.append(f"{attr} INTEGER")
            else:
                columns.append(f"{attr} TEXT")  # fallback
        columns_sql = ", ".join(columns)
        return f"CREATE TABLE IF NOT EXISTS {cls.__name__.lower()} (id INTEGER PRIMARY KEY AUTOINCREMENT, {columns_sql})"

    def patch(self: T, **changes) -> T:
        """Return a new instance with updated fields (no DB)."""
        return replace(self, **changes)

    def delete(self: T) -> T:
        """Mark the model as deleted (soft-delete)."""
        return replace(self, _deleted=True)

    def to_dict(self, obfuscate = True):
        """Returns the instance as a dict"""
        def process_value(key, value):
            if obfuscate and hasattr(self,'_private_keys') and key in self._private_keys:
                return '***'
            if hasattr(value, 'to_dict'):
                return value.to_dict(obfuscate=obfuscate)
            return value
        return {key: process_value(key,value) for key, value in self.__dict__.items() if key[0] != '_'}
        # return {key: ('***' if obfuscate and hasattr(self,'_private_keys') and key in self._private_keys else value) for key, value in self.__dict__.items() if key[0] != '_'}

    def to_json(self, obfuscate = True) -> str:
        """Returns the user data as a JSON serializable dictionary"""
        import json
        return json.dumps(self.to_dict(obfuscate))
        # obfuscate = self._private_keys
        # return {key: ('***' if obfuscate and hasattr(self,'_private_keys') and key in self._private_keys else value) for key, value in self.__dict__.items() if key[0] != '_'}



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
            # items = list(items)
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
    def query(cls,
                query_path: str,
                app_ctx: AppCtx = None,
                model: object | str = None,
                name_pattern: str = None,
                exclude_dirs: tuple = None,
                exclude_names: tuple = None,
                force_all: bool = True,
                sort_key: str = None):
        """queries the file system for list of files"""
        from pyonir.utilities import query_files
        gen_data = query_files(query_path, app_ctx=app_ctx, model=model, name_pattern=name_pattern,
                               exclude_dirs=exclude_dirs, exclude_names=exclude_names, force_all=force_all)
        # gen_data = get_all_files_from_dir(query_path, app_ctx=app_ctx, entry_type=data_model, include_only=include_only,
        #                                   exclude_dirs=exclude_dirs, exclude_file=exclude_file, force_all=force_all)
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

    def paginated_collection(self, query_params=None)-> ParselyPagination | None:
        """Paginates a list into smaller segments based on curr_pg and display limit"""
        if query_params is None: query_params = {}
        from pyonir import Site
        if not Site: return None
        from pyonir.core import ParselyPagination
        request: PyonirRequest = Site.TemplateEnvironment.globals['request'] if Site.TemplateEnvironment else None
        if not request or not hasattr(request, 'limit'): return None
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

        return ParselyPagination(**{
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


class PyonirRequest:

    def __init__(self, server_request: StarletteRequest, app: PyonirApp):
        from pyonir.utilities import get_attr

        self.server_response = None
        self.file: typing.Optional[Parsely] = None
        self.server_request: StarletteRequest = server_request
        self.raw_path = "/".join(str(self.server_request.url).split(str(self.server_request.base_url)))
        self.method = self.server_request.method
        self.path = self.server_request.url.path
        self.path_params = dict(self.server_request.path_params)
        self.url = f"{self.path}"
        self.slug = self.path.lstrip('/').rstrip('/')
        self.query_params = self.get_params(self.server_request.url.query)
        self.parts = self.slug.split('/') if self.slug else []
        self.limit = get_attr(self.query_params, 'limit', PAGINATE_LIMIT)
        self.model = get_attr(self.query_params, 'model')
        self.is_home = (self.slug == '')
        self.is_api = self.parts and self.parts[0] == app.API_DIRNAME
        self.is_static = bool(list(os.path.splitext(self.path)).pop())
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
        self.app_ctx_name: str = app.name
        self.auth: Auth | None = None #Auth(self, app)
        self.flashes: dict = self.get_flash_messages()
        self.server_request.session['previous_url'] = self.headers.get('referer', '')

    @property
    def session_token(self):
        """Returns active csrf token for user session"""
        if self.server_request and self.server_request.session:
            return self.server_request.session.get('csrf_token')

    @property
    def previous_url(self) -> str:
        return self.server_request.session.pop('previous_url')
        # return self.headers.get('referer', '')

    @property
    def redirect_to(self):
        """Returns the redirect URL from the request form data"""
        file_redirect = self.file.data.get('redirect_to', self.file.data.get('redirect'))
        return self.form.get('redirect_to', self.form.get('redirect', file_redirect))

    def redirect(self, url: str):
        """Sets the redirect URL in the request form data"""
        self.form['redirect_to'] = url

    def get_flash_messages(self) -> dict:
        """Pops and returns all flash messages from session"""
        if self.server_request and self.server_request.session:
            session_data = self.server_request.session
            flashes = session_data.pop('__flash__') if session_data.get('__flash__') else {}
            return flashes
        return {}

    def pull_flash(self, key):
        return self.flashes.get(key)

    def add_flash(self, key: str, value: any):
        flash_obj = self.server_request.session.get('__flash__') or {}
        flash_obj[key] = value
        self.server_request.session['__flash__'] = flash_obj

    def from_session(self, session_key: str) -> any:
        """Returns data from the session"""
        return self.server_request.session.get(session_key, None)

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
        self.form = expand_dotted_keys(self.form, return_as_dict=True)

    def derive_status_code(self, is_router_method: bool):
        """Create status code for web request based on a file's availability, status_code property"""
        from pyonir.parser import ParselyFileStatus

        code = 404
        if self.file.is_router:
            # If the file is a router method, we assume it is valid
            code = 200
        elif self.file.status in (ParselyFileStatus.PROTECTED, ParselyFileStatus.FORBIDDEN):
            self.file.data = {'template': '40x.html', 'content': f'Unauthorized access to this resource.', 'url': self.url, 'slug': self.slug}
            code = 401
        elif self.file.file_status == ParselyFileStatus.PUBLIC or is_router_method:
            code = 200
        self.status_code = code #200 if self.file.file_exists or is_router_method else 404

    def api_response(self) -> PyonirRestResponse:
        """Format the response data for REST API requests"""
        if isinstance(self.server_response, PyonirRestResponse): return self.server_response
        res = self.server_response or self.file
        return PyonirRestResponse(message='', data=res, status_code=self.status_code)

    def render_error(self):
        """Data output for an unknown file path for a web request"""
        return {
            "url": self.url,
            "method": self.method,
            "status": self.status_code,
            "res": self.server_response,
            "title": f"{self.path} was not found!",
            "content": f"Perhaps this page once lived but has now been archived or permanently removed from {self.app_ctx_name}."
        }

    def resolve_request_to_file(
        self,
        path_str: str,
        app: PyonirApp,
        plugin_routing_ctx: tuple = None,
    ) -> typing.Tuple[PyonirApp, typing.Optional[Parsely]]:
        """Resolve a request URL to a file on disk, checking plugin paths first, then the main app."""
        from pyonir import Site
        from pyonir.parser import Parsely
        is_home = path_str == '/'
        # app_has_plugins = hasattr(app, 'plugins_activated')
        # ctx_api_route, ctx_route, ctx_paths = plugin_routing_ctx or app.request_paths
        ctx_route, ctx_paths = app.request_paths or ('', [])
        ctx_route = ctx_route or ''
        ctx_slug = ctx_route[1:]
        path_slug = path_str[1:]
        app_scope, *path_segments = path_slug.split('/')
        is_api_request = (len(path_segments) and path_segments[0] == app.API_DIRNAME) or path_str.startswith(app.API_ROUTE)

        # First, check plugins if available and not home
        # if not plugin_routing_ctx:
        #     for plg_ctx in app.plugin_routing_paths:
        #         plugin_api_url, plugin_url, plugin_routes = plg_ctx
        #         _url = plugin_api_url if is_api_request else plugin_url
        #         if not is_home and path_str.startswith(_url):
        #             _, parsed = self.resolve_request_to_file(path_str, app, plugin_routing_ctx=plg_ctx)
        #             if parsed and parsed.file_exists:
        #                 return app, parsed

        if not is_home and hasattr(app, 'plugins_activated'):
            for plugin in app.plugins_activated:
                if not plugin.request_paths or (is_api_request and plugin.module != app_scope): continue
                if plugin.module == app_scope and is_api_request:
                    path_str = path_str.replace('/'+app_scope, '')
                resolved_app, parsed = self.resolve_request_to_file(path_str, plugin)
                if parsed and parsed.file_exists:
                    return resolved_app, parsed


        # Normalize API prefix and path segments
        if is_api_request:
            path_str = path_str.replace('/api', '')

        request_segments = [
            segment for segment in path_slug.split('/')
            if segment and segment not in ('api', ctx_slug)
        ]

        # Skip if no paths or route doesn't match
        if not ctx_paths or (not is_home and not path_str.startswith(ctx_route)):
            return app, None

        # Try resolving to actual file paths
        protected_segment = [s if i > len(request_segments)-1 else f'_{s}' for i,s in enumerate(request_segments)]
        # virtual_path = None
        for root_path in ctx_paths:
            # if root_path.endswith('.routes.md'): virtual_path = root_path
            if not is_api_request and root_path.endswith(app.API_DIRNAME): continue
            category_index = os.path.join(root_path, *request_segments, 'index.md')
            single_page = os.path.join(root_path, *request_segments) + Site.EXTENSIONS['file']
            single_protected_page = os.path.join(root_path, *protected_segment) + Site.EXTENSIONS['file']

            for candidate in (category_index, single_page, single_protected_page):
                if os.path.exists(candidate):
                    return app, Parsely(candidate, app.app_ctx)

        # if plugin_routing_ctx and virtual_path:
        #     plg_base = os.path.dirname(os.path.dirname(virtual_path))
        #     plg_name = os.path.basename(plg_base)
        #     virtural_page = Parsely(virtual_path, (plg_name, ctx_route, plg_base, os.path.join(app.ssg_dirpath,ctx_route.lstrip('/')) ))
        #     if virtural_page.file_exists: return app, virtural_page

        errorpage = Parsely('404_ERROR', app.app_ctx)
        errorpage.data = self.render_error()
        return app, errorpage

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


class PyonirBase:
    """Pyonir Base Application Configs"""
    pyonir_path: str = os.path.dirname(__file__)
    endpoint: str | None = None
    # Default config settings
    EXTENSIONS = {"file": ".md", "settings": ".json"}
    THUMBNAIL_DEFAULT = (230, 350)
    PROTECTED_FILES = {'.', '_', '<', '>', '(', ')', '$', '!', '._'}
    IGNORE_FILES = {'.vscode', '.vs', '.DS_Store', '__pycache__', '.git'}
    IGNORE_WITH_PREFIXES = ('.', '_', '<', '>', '(', ')', '$', '!', '._')

    PAGINATE_LIMIT: int = 6
    DATE_FORMAT: str = "%Y-%m-%d %I:%M:%S %p"
    TIMEZONE: str = "US/Eastern"
    # ALLOWED_UPLOAD_EXTENSIONS: set[str] = {'jpg', 'JPG', 'PNG', 'png', 'txt', 'md', 'jpeg', 'pdf', 'svg', 'gif'}
    MEDIA_EXTENSIONS = (
        # Audio
        ".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma", ".aiff", ".alac",

        # Video
        ".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".mpeg", ".mpg", ".3gp",

        # Images
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg", ".heic",

        # Raw Image Formats
        ".raw", ".cr2", ".nef", ".orf", ".arw", ".dng",

        # Media Playlists / Containers
        ".m3u", ".m3u8", ".pls", ".asx", ".m4v", ".ts"
    )
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
    DATA_DIRNAME: str = 'data_stores'

    SSG_IN_PROGRESS: bool = False

    # Contents sub directory default names
    UPLOADS_THUMBNAIL_DIRNAME: str = "thumbnails" # resized image directory name
    UPLOADS_DIRNAME: str = "uploads" # url name for serving uploaded assets
    PUBLIC_ASSETS_DIRNAME: str = "public"
    """Global static assets directory name for serving static files"""
    FRONTEND_ASSETS_DIRNAME: str = "static"
    """Theme assets directory name for serving static files"""
    API_DIRNAME: str = "api" # directory for serving API endpoints and resolver routes
    PAGES_DIRNAME: str = "pages" # directory for serving HTML endpoints with file based routing
    CONFIG_FILENAME: str = "app" # main application configuration file name within contents/configs directory
    PLUGINS_DIRNAME: str = "plugins" # main application plugins directory

    # Application paths
    app_dirpath: str = '' # directory path to site's main.py file
    app_name: str = '' # directory name for application main.py file
    app_account_name: str = '' # parent directory from the site's root directory (used for multi-site configurations)

    # Application routes
    API_ROUTE = f"/{API_DIRNAME}"  # Api base path for accessing pages as JSON
    TemplateEnvironment: TemplateEnvironment = None # Template environment configurations
    routing_paths: list[PagesPath, APIPath] = []

    _resolvers = {}

    @property
    def frontend_assets_route(self) -> str: return f"/{self.FRONTEND_ASSETS_DIRNAME}"

    @property
    def public_assets_route(self) -> str: return f"/{self.PUBLIC_ASSETS_DIRNAME}"

    @property
    def uploads_route(self) -> str: return f"/{self.UPLOADS_DIRNAME}"

    @property
    def request_paths(self) -> tuple[str, list[PagesPath, APIPath]]:
        return self.endpoint, self.routing_paths
        # return self.endpoint, f"/{self.API_DIRNAME}{self.endpoint}", self.routing_paths

    @property
    def module(self):
        """The application module directory name"""
        return self.__module__.split('.').pop()

    @property
    def app_ctx(self) -> AppCtx: pass

    async def virtual_router(self, pyonir_request: PyonirRequest) -> Parsely | None:
        virtual_route_path = os.path.join(self.pages_dirpath, '.routes.md')
        if os.path.exists(virtual_route_path):
            virtual_route = self.parse_file(virtual_route_path)
            await virtual_route.process_route(pyonir_request, self)
        return pyonir_request.file

    def register_resolver(self, name: str, cls_or_path, args=(), kwargs=None, hot_reload=False):
        import inspect
        """
        Register a class for later instantiation.

        cls_or_path - Either a class object or dotted path string
        hot_reload  - Only applies if cls_or_path is a dotted path
        """
        if inspect.isclass(cls_or_path):
            class_path = f"{cls_or_path.__module__}.{cls_or_path.__qualname__}"
            # hot_reload = False  # No reload possible if you pass the class directly
        elif isinstance(cls_or_path, str):
            class_path = cls_or_path
        else:
            raise TypeError("cls_or_path must be a class object or dotted path string")

        self._resolvers[name] = {
            "class_path": class_path,
            "args": args,
            "kwargs": kwargs or {},
            "hot_reload": hot_reload
        }

    def reload_resolver(self, name) -> callable | None:
        """
        Instantiate the registered class.
        Reload if hot_reload is enabled and class was registered by path.
        """
        import importlib, sys
        from pyonir.utilities import get_attr
        from pyonir.parser import Parsely

        cls_path, meth_name = name.rsplit(".", 1)
        is_pyonir = name.startswith('pyonir')
        entry = get_attr(self._resolvers, cls_path)

        # access module instance
        if entry:
            module_path, cls_name = entry["class_path"].rsplit(".", 1)

            if entry["hot_reload"] and module_path in sys.modules:
                importlib.reload(sys.modules[module_path])
            elif module_path not in sys.modules:
                importlib.import_module(module_path)

            cls = getattr(sys.modules[module_path], cls_name)
            new_instance = cls(*entry["args"], **entry["kwargs"])
            # setattr(self, name, new_instance)
            return getattr(new_instance, meth_name)

        # access constant value or methods on application instance
        resolver = get_attr(self, name)

        # access modules from loader
        if not resolver:
            resolver = Parsely.load_resolver(name,
                                          base_path=self.pyonir_path if is_pyonir else self.app_dirpath,
                                          from_system=is_pyonir)
        if not resolver:
            print(f"Unable to load {name}")

        return resolver

    @staticmethod
    def generate_resolvers(cls: callable, output_dirpath: str, namespace: str = ''):
        """Automatically generate api endpoints from service class or module."""
        import textwrap, inspect
        from pyonir.utilities import create_file

        def process_docs(meth: callable):
            docs = meth.__doc__
            if not docs: return '', docs
            res = textwrap.dedent(docs).strip()
            _r = res.split('---')
            meta = _r.pop(1) if '---' in res else ''
            return meta, "".join(_r)

        default_template = textwrap.dedent("""\
        @resolvers:
            POST.call: {method_import_path}
        ===
        {docs}
        """).strip()

        resolver_template = textwrap.dedent("""\
        {meta}
        ===
        {docs}
        """).strip()

        name = ''
        # endpoint_meths = []

        if inspect.ismodule(cls):
            name = cls.__name__
            endpoint_meths = [
                m for m, obj in inspect.getmembers(cls, inspect.isfunction)
                if obj.__module__ == name
            ]
            call_path_fn = lambda meth_name: f"{namespace}.{name}.{meth_name}"

        else:  # Means cls is an instance
            klass = type(cls)
            name = klass.__name__
            output_dirpath = os.path.join(output_dirpath, namespace)

            # call_path = name[0].lower() + name[1:]
            call_path_fn = lambda meth_name: f"{namespace}.{meth_name}"
            endpoint_meths = [
                m for m in dir(cls)
                if not m.startswith('_') and callable(getattr(cls, m))
            ]

        print(f"Generating {name} API endpoint definitions for:")
        for meth_name in endpoint_meths:
            file_path = os.path.join(output_dirpath, meth_name+'.md')
            # if os.path.exists(file_path): continue
            method_import_path = call_path_fn(meth_name)
            meth: callable = getattr(cls, meth_name)
            meta, docs = process_docs(meth)
            if not meta: continue
            meta = textwrap.dedent(meta.replace('{method_import_path}', method_import_path)).strip()
            m_temp = resolver_template.format(docs=docs, meta=meta)
            create_file(file_path, m_temp)
            print(f"\t{meth_name} at {file_path}")

    def parse_file(self, file_path: str) -> Parsely:
        """Parses a file and returns a Parsely instance for the file."""
        from pyonir.parser import Parsely
        return Parsely(file_path, app_ctx=self.app_ctx)

    def generate_static_website(self):
        """Generates Static website into the specified static_site_dirpath"""
        import time
        # from pyonir.server import generate_nginx_conf
        from pyonir import utilities

        self.SSG_IN_PROGRESS = True
        count = 0
        print(f"{utilities.PrntColrs.OKBLUE}1. Coping Assets")
        try:
            self.run()
            site_map_path = os.path.join(self.ssg_dirpath, 'sitemap.xml')
            # generate_nginx_conf(self)
            print(f"{utilities.PrntColrs.OKCYAN}3. Generating Static Pages")

            self.TemplateEnvironment.globals['is_ssg'] = True
            start_time = time.perf_counter()

            all_pages = utilities.query_files(self.pages_dirpath, app_ctx=self.app_ctx)
            xmls = []
            for page in all_pages:
                self.TemplateEnvironment.globals['request'] = page  # pg_req
                count += page.generate_static_file()
                t = f"<url><loc>{self.protocol}://{self.domain}{page.url}</loc><priority>1.0</priority></url>\n"
                xmls.append(t)
                self.TemplateEnvironment.block_pull_cache.clear()

            # Compile sitemap
            smap = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{self.domain}</loc><priority>1.0</priority></url> {"".join(xmls)} </urlset>'
            utilities.create_file(site_map_path, smap, 0)

            # Copy theme static css, js files into ssg directory
            utilities.copy_assets(self.frontend_assets_dirpath, os.path.join(self.ssg_dirpath, self.FRONTEND_ASSETS_DIRNAME))
            utilities.copy_assets(self.public_assets_dirpath, os.path.join(self.ssg_dirpath, self.PUBLIC_ASSETS_DIRNAME))

            end_time = time.perf_counter() - start_time
            ms = end_time * 1000
            count += 3
            msg = f"SSG generated {count} html/json files in {round(end_time, 2)} secs :  {round(ms, 2)} ms"
            print(f'\033[95m {msg}')
        except Exception as e:
            msg = f"SSG encountered an error: {str(e)}"
            raise

        self.SSG_IN_PROGRESS = False
        response = {"status": "COMPLETE", "msg": msg, "files": count}
        print(response)
        print(utilities.PrntColrs.RESET)
        return response


class PyonirPlugin(PyonirBase):

    def __init__(self, app: PyonirApp, app_entrypoint: str = None):
        self._app_ctx = None
        self.app: PyonirApp = app
        self.app_entrypoint: str = app_entrypoint # plugin application initializing file
        self.app_dirpath: str = os.path.dirname(app_entrypoint) # plugin directory path
        self.name: str = os.path.basename(self.app_dirpath) # web url to serve application pages
        self.CONFIG_FILENAME = self.module
        self.available_models = {}
        self.routing_paths = []

    @property
    def request_paths(self) -> AppRequestPaths | None:
        """Request context for route resolution"""
        if not self.routing_paths and self.endpoint: return None
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
        return self._app_ctx or [self.name, self.endpoint, self.contents_dirpath, self.ssg_dirpath]

    def register_routing_dirpaths(self, dir_paths: list):
        """Registers a new pages directory path for resolving web based request"""
        for path in dir_paths:
            self.routing_paths.insert(0, path)
        pass

    def register_templates(self, dir_paths: list):
        """Registers additional paths for jinja templates. Templates will load in order of priority."""
        from jinja2 import FileSystemLoader

        if not hasattr(self.app.TemplateEnvironment, 'loader'): return None
        for path in dir_paths:
            if path in self.app.TemplateEnvironment.loader.loaders: continue
            self.app.TemplateEnvironment.loader.loaders.insert(0, FileSystemLoader(path))
        pass

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
    endpoint = '/'
    """Web url to access application resources."""

    server: PyonirServer = None
    """Starlette server instance"""

    TemplateEnvironment: TemplateEnvironment = None
    """Template environment for jinja templates"""

    plugins_installed: dict = dict()
    """Represents plugins installed within the site plugins directory"""

    plugins_activated: set = set()
    """All enabled plugins instances"""

    def __init__(self, app_entrypoint: str, serve_frontend: bool = None):
        from pyonir.utilities import generate_id, get_attr, load_env
        from pyonir import __version__
        from pyonir.parser import parse_markdown
        self._subscribers = defaultdict(list)
        self.SOFTWARE_VERSION = __version__
        # self.get_attr = get_attr
        self.app_entrypoint: str = app_entrypoint # application main.py file or the initializing file
        self.app_dirpath: str = os.path.dirname(app_entrypoint) # application main.py file or the initializing file
        self.name: str = os.path.basename(self.app_dirpath) # web url to serve application pages
        self.SECRET_SAUCE = generate_id()
        self.SESSION_KEY = f"pyonir_{self.name}"
        self._env: EnvConfig = load_env(os.path.join(self.app_dirpath, '.env'))
        self.settings: PyonirAppSettings = None
        self.themes: PyonirThemes = None
        self.routing_paths = [self.pages_dirpath, self.api_dirpath]
        self.Parsely_Filters = {'jinja': self.parse_jinja, 'pyformat': self.parse_pyformat,
                                 'md': parse_markdown}

        # self._plugin_routing_paths: typing.List[AppCtx] = []
        # """Path context for plugin pages"""
        self.serve_frontend = serve_frontend if serve_frontend is not None else True
        """Serve frontend files from the frontend directory for HTML requests"""
        self.TemplateEnvironment = TemplateEnvironment(self)

    @property
    def nginx_config_filepath(self):
        return os.path.join(self.app_dirpath, self.name + '.conf')

    @property
    def unix_socket_filepath(self):
        """WSGI socket file reference"""
        return os.path.join(self.app_dirpath, self.name+'.sock')

    @property
    def frontend_assets_dirpath(self) -> str:
        """Directory location for template related assets"""
        theme_assets_dirpath = self.themes.active_theme.static_dirpath if self.themes else None
        return theme_assets_dirpath or os.path.join(self.frontend_dirpath, self.FRONTEND_ASSETS_DIRNAME)

    @property
    def public_assets_dirpath(self) -> str:
        """Directory location for general assets"""
        return os.path.join(self.frontend_dirpath, self.PUBLIC_ASSETS_DIRNAME)

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
        """Directory path for site's contents"""
        return os.path.join(self.app_dirpath, self.CONTENTS_DIRNAME)

    @property
    def datastore_dirpath(self) -> str:
        """Directory path for datastorage"""
        return os.path.join(self.app_dirpath, self.DATA_DIRNAME)

    @property
    def frontend_dirpath(self) -> str:
        """Directory path for site's theme folders"""
        return os.path.join(self.app_dirpath, self.FRONTEND_DIRNAME)

    @property
    def frontend_templates_dirpath(self) -> str:
        """Directory path for site's theme folders"""
        return os.path.join(self.frontend_dirpath, self.TEMPLATES_DIRNAME)

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
    def jinja_filters_dirpath(self) -> str:
        """Directory path to site's available Jinja filters"""
        return os.path.join(self.backend_dirpath, "filters")

    @property
    def ssl_cert_file(self):
        """Path to the SSL certificate file for the application"""
        return os.path.join(self.app_dirpath, "server.crt")

    @property
    def ssl_key_file(self):
        """Path to the SSL key file for the application"""
        return os.path.join(self.app_dirpath, "server.key")

    @property
    def app_ctx(self) -> AppCtx:
        return self.name, self.endpoint, self.contents_dirpath, self.ssg_dirpath

    @property
    def use_ssl(self) -> str: return get_attr(self.env, 'app.use_ssl')

    @property
    def salt(self) -> str: return get_attr(self.env, 'app.salt')

    @property
    def env(self) -> str: return self._env

    @property
    def is_dev(self) -> bool: return getattr(self.env, 'APP_ENV')== DEV_ENV

    @property
    def host(self) -> str: return get_attr(self._env, 'app.host', '0.0.0.0') #if self.configs else '0.0.0.0'

    @property
    def port(self) -> int:
        return int(get_attr(self._env, 'app.port', 5000)) #if self.configs else 5000

    @property
    def protocol(self) -> str: return 'https' if self.is_secure else 'http'

    @property
    def is_secure(self) -> bool:
        """Check if the application is configured to use SSL"""
        has_ssl_files = os.path.exists(self.ssl_cert_file) and os.path.exists(self.ssl_key_file)
        return has_ssl_files and self.use_ssl

    @property
    def domain_name(self) -> str: return get_attr(self._env, 'app.domain', self.host) # if self.configs else self.host

    @property
    def domain(self) -> str: return f"{self.protocol}://{self.domain_name}{':'+str(self.port) if self.is_dev else ''}".replace('0.0.0.0','localhost') # if self.configs else self.host

    # @property
    # def plugin_routing_paths(self):
    #     return self._plugin_routing_paths

    def insert(self, file_path: str, contents: dict, app_ctx: AppCtx = None) -> Parsely:
        """Creates a new file"""
        from pyonir import Parsely
        contents = Parsely.serializer(contents) if isinstance(contents, dict) else contents
        return Parsely.create_file(file_path, contents, app_ctx=app_ctx or self.app_ctx)

    @staticmethod
    def query_files(dir_path: str, app_ctx: tuple, model_type: any = None) -> list[Parsely]:
        from pyonir.utilities import process_contents
        # return PyonirCollection.query(dir_path, app_ctx, model_type)
        return process_contents(dir_path, app_ctx, model_type)

    # def add_routing_path(self, endpoint: str,api_endpoint: str, paths: list[str]):
    #     self._plugin_routing_paths.append((endpoint, api_endpoint, paths))

    def subscribe_hook(self, callback: callable, hook: PyonirHooks):
        """registers callback methods that execute during server runtime"""
        import inspect
        is_async = inspect.iscoroutinefunction(callback)
        self._subscribers[hook].append((is_async, callback))

    def load_plugin(self, plugin: callable | list[callable]):
        """Make the plugin known to the pyonir application"""
        if isinstance(plugin, list):
            for plugin in plugin:
                self.load_plugin(plugin)
        else:
            plg_pkg_name = plugin.__module__.split('.').pop()
            self.plugins_installed[plg_pkg_name] = plugin


    def _activate_plugins(self):
        """Active plugins enabled based on configurations"""
        from pyonir.utilities import get_attr
        is_configured = get_attr(self.settings.app, 'enabled_plugins', None)
        for plg_id, plugin in self.plugins_installed.items():
            if is_configured and plg_id not in self.settings.app.enabled_plugins: continue
            self.plugins_activated.add(plugin(self))

    def install_sys_plugins(self):
        """Install pyonir plugins"""
        from pyonir.libs.plugins.navigation import Navigation
        self.plugins_installed['pyonir_navigation'] = Navigation

    def run_hooks(self, hook: PyonirHooks, request: PyonirRequest = None):
        subs = self._subscribers[hook]
        for is_async, callback in subs:
            callback(self, request)

    async def run_async_hooks(self, hook: PyonirHooks, request: PyonirRequest = None):
        subs = self._subscribers[hook]
        for is_async, callback in subs:
            if is_async:
                await callback(self, request)
            else:
                callback(self, request)

    def run_plugins(self, hook: PyonirHooks, data_value=None):
        if not hook or not self.plugins_activated: return
        hook = hook.lower()
        for plg in self.plugins_activated:
            if not hasattr(plg, hook): continue
            hook_method = getattr(plg, hook)
            hook_method(data_value, self)

    async def run_async_plugins(self, hook: PyonirHooks, data_value=None):
        if not hook or not self.plugins_activated: return
        hook_method_name = hook.lower()
        for plg in self.plugins_activated:
            if not hasattr(plg, hook_method_name): continue
            hook_method = getattr(plg, hook_method_name)
            await hook_method(data_value, self)

    def parse_jinja(self, string, context=None) -> str:
        """Render jinja template fragments"""
        if not context: context = {}
        if not self.TemplateEnvironment or not string: return string
        try:
            return self.TemplateEnvironment.from_string(string).render(configs=self.settings, **context)
        except Exception as e:
            raise


    def parse_pyformat(self, string, context=None) -> str:
        """Formats python template string"""
        ctx = self.TemplateEnvironment.globals if self.TemplateEnvironment else {}
        try:
            if context is not None: ctx.update(context)
            return string.format(**ctx)
        except Exception as e:
            print('parse_pyformat', e)
            return string

    def setup_templates(self):
        self.TemplateEnvironment = TemplateEnvironment(self)

    def setup_themes(self):
        """Configure site themes"""
        from pyonir.utilities import get_attr

        themes_dir_path = os.path.join(self.frontend_dirpath, PyonirApp.THEMES_DIRNAME)
        if not self.serve_frontend or not os.path.exists(themes_dir_path):
            print(f"Site is not configured to serve themes. {themes_dir_path} is not created or app isn't serving a frontend")
            return

        self.themes = PyonirThemes(themes_dir_path)
        app_active_theme = self.themes.active_theme
        if app_active_theme is None:
            raise ValueError(f"No active theme name {get_attr(self.settings, 'app.theme_name')} found in {self.frontend_dirpath} themes directory. Please ensure a theme is available.")

        # Configure theme templates
        self.TemplateEnvironment.load_template_path(app_active_theme.jinja_template_path)


    def setup_configs(self):
        """Setup site configurations and template environment"""
        from pyonir.utilities import process_contents
        self.settings = process_contents(os.path.join(self.contents_dirpath, self.CONFIGS_DIRNAME), self.app_ctx)
        self.TemplateEnvironment.globals['configs'] = self.settings.app



    def run(self, routes: PyonirRouters = None):
        """Runs the Uvicorn webserver"""
        from .server import (setup_starlette_server, start_uvicorn_server,)
        from pyonir.server import generate_nginx_conf

        # Initialize Application settings and templates
        self.install_sys_plugins()
        self._activate_plugins()
        generate_nginx_conf(self)
        # Run uvicorn server
        if self.SSG_IN_PROGRESS: return
        # Initialize Server instance
        if not self.salt:
            raise ValueError(f"You are attempting to run the application without proper configurations. .env file must include app.salt to protect the application.")
        self.server = setup_starlette_server(self)
        start_uvicorn_server(self, routes)


class TemplateEnvironment(Environment):

    def __init__(self, app: PyonirApp):

        if not os.path.exists(app.frontend_dirpath) and app.serve_frontend:
            raise ValueError(f"Frontend directory {app.frontend_dirpath} does not exist. Please ensure the frontend directory is set up correctly.")
        from jinja2 import FileSystemLoader, ChoiceLoader
        from pyonir import PYONIR_JINJA_TEMPLATES_DIRPATH, PYONIR_JINJA_FILTERS_DIRPATH, PYONIR_JINJA_EXTS_DIRPATH
        from webassets.ext.jinja2 import AssetsExtension
        from pyonir.utilities import load_modules_from

        jinja_template_paths = ChoiceLoader([FileSystemLoader(PYONIR_JINJA_TEMPLATES_DIRPATH),FileSystemLoader(app.frontend_templates_dirpath)])
        sys_filters = load_modules_from(PYONIR_JINJA_FILTERS_DIRPATH)
        app_filters = load_modules_from(app.jinja_filters_dirpath)
        installed_extensions = load_modules_from(PYONIR_JINJA_EXTS_DIRPATH, True)
        app_extensions = [AssetsExtension, *installed_extensions]
        app_filters = {**sys_filters, **app_filters}
        super().__init__(loader=jinja_template_paths, extensions=app_extensions)

        #  Custom filters
        self.filters.update(**app_filters)

        def url_for(path):
            rmaps = app.server.url_map if app.server else {}
            return rmaps.get(path, {}).get('path', '/'+path)

        # Include globals
        self.globals['url_for'] = url_for
        self.globals['request'] = None
        self.globals['user'] = None


    def load_template_path(self, template_path: str):
        """Adds template path to file loader"""
        from jinja2 import FileSystemLoader
        app_loader = self.loader
        if not app_loader: return
        self.loader.loaders.append(FileSystemLoader(template_path))
        # app_loader.searchpath.append(template_path)

    def add_filter(self, filter: callable):
        name = filter.__name__
        print(f"Installing filter:{name}")
        self.filters.update({name: filter})
        pass

@dataclass
class Theme:
    _orm_options = {'mapper': {'theme_dirname': 'file_dirname', 'theme_dirpath': 'file_dirpath'}}
    name: str
    theme_dirname: str = ''
    """Directory name for theme folder within frontend/themes directory"""
    theme_dirpath: str = ''
    """Directory path for theme folder within frontend/themes directory"""
    details: Parsely | None = None
    """Represents a theme available in the frontend/themes directory."""

    def __post_init__(self):
        self.details = self.readme()
        for k, v in self.details.data.items():
            if k in ('static_dirname', 'templates_dirname'):
                setattr(self, k, v)

    @property
    def static_dirname(self):
        """directory name for theme's jinja templates"""
        return self.details.data.get('static_dirname', 'static') if self.details else 'static'

    @property
    def templates_dirname(self):
        """directory name for theme's jinja templates"""
        return self.details.data.get('templates_dirname', 'layouts') if self.details else 'layouts'

    @property
    def static_dirpath(self):
        """directory to serve static theme assets"""
        return os.path.join(self.theme_dirpath, self.static_dirname)

    @property
    def jinja_template_path(self):
        return os.path.join(self.theme_dirpath, self.templates_dirname)

    def readme(self):
        """Returns the theme's README.md file content if available"""
        from pyonir.parser import Parsely
        from pyonir import Site
        theme_ctx = list(Site.app_ctx)
        theme_ctx[2] = Site.frontend_dirpath
        theme_readme = os.path.join(self.theme_dirpath,'README.md')
        theme_readme =  theme_readme if os.path.exists(theme_readme) else os.path.join(self.theme_dirpath,'readme.md')
        readme = Parsely(theme_readme, app_ctx=theme_ctx)
        if not readme.file_exists:
            raise ValueError(f"Theme {self.name} does not have a README.md file.")
        return readme

class PyonirThemes:
    """Represents sites available and active theme(s) within the frontend directory."""

    def __init__(self, theme_dirpath: str):
        if not os.path.exists(theme_dirpath):
            raise ValueError(f"Theme directory {theme_dirpath} does not exist.")
        self.themes_dirpath: str = theme_dirpath # directory path to available site themes
        self.available_themes: PyonirCollection | None = self.query_themes() # collection of themes available in frontend/themes directory

    @property
    def active_theme(self) -> Theme | None:
        from pyonir import Site
        from pyonir.parser import get_attr
        if not Site or not self.available_themes: return None
        # self.available_themes = self.query_themes()
        site_theme = get_attr(Site._env, 'app.theme_name')
        site_theme = self.available_themes.get(site_theme)
        return site_theme

    def query_themes(self) -> dict[str, Theme] | None:
        """Returns a collection of available themes within the frontend/themes directory"""
        themes_map = {}
        for theme_dir in os.listdir(self.themes_dirpath):
            if theme_dir.startswith(PyonirBase.IGNORE_WITH_PREFIXES): continue
            theme = Theme(name=theme_dir, theme_dirname=theme_dir, theme_dirpath=os.path.join(self.themes_dirpath, theme_dir))
            themes_map[theme_dir] = theme
        return themes_map if themes_map else None


