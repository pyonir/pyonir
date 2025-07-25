from dataclasses import dataclass, field
from enum import StrEnum
import os
from typing import Optional, Union, Callable, List, Tuple

from starlette.applications import Starlette

TEXT_RES: str = 'text/html'
JSON_RES: str = 'application/json'
EVENT_RES: str = 'text/event-stream'
PAGINATE_LIMIT: int = 6


# === Route Definitions ===

RoutePath = str
"""Represents the URL path of a route (e.g., '/about', '/api/data')."""

RouteFunction = Callable
"""A callable that handles a specific route request (e.g., controller function)."""

RouteMethods = List[str]
"""HTTP methods supported by a route (e.g., ['GET', 'POST'])."""

PyonirRoute = Tuple[RoutePath, RouteFunction, RouteMethods]
"""A single route entry containing the path, its handler function, and allowed HTTP methods."""

PyonirRouters = List[Tuple[RoutePath, List[PyonirRoute]]]
"""A list of route groups, each keyed by a base path and containing multiple PyonirRoute entries."""


# === Application Module Definitions ===

AppName = str
"""The name identifier for an app module."""

ModuleName = str
"""The Python module name used for import or registration."""

AppEndpoint = str
"""The base endpoint path where the app is mounted."""

AppPaths = List[str]
"""A list of file or URL paths associated with the app."""

AppContentsPath = str
"""The root path to the static or content files of the app."""

AppSSGPath = str
"""The path used for static site generation output."""

AppContextPaths = Tuple[AppName, RoutePath, AppPaths]
"""Context binding tuple that connects an app name to a route and its associated paths."""

AppCtx = Tuple[ModuleName, RoutePath, AppContentsPath, AppSSGPath]
"""Full application context including module reference and content/static paths."""

AppRequestPaths = Tuple[RoutePath, AppPaths]
"""Tuple representing an incoming request path and all known paths for resolution."""

@dataclass
class ParselyPagination:
    limit: int = 0
    max_count: int = 0
    curr_page: int = 0
    page_nums: list[int, int] = field(default_factory=list)
    items: list['Parsely'] = field(default_factory=list)


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

class PyonirOptions:
    contents_dirpath: str  = '' # base directory path for markdown files
    use_file_based_routing: bool = None # toggles use of file based routing directory
    routes_dirpath: str = ''    # path for resolving file based routing
    routes_api_dirpath: str = '' # path for resolving file based API configured endpoints
    file_based_routes: dict = {}# configurations for resolving file based routes that contain dynamic path params

class Pagination:
    page_num: int = 1
    limit: int = 0

class PyonirHooks(StrEnum):
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


class Parsely:
    default_file_attributes = ['file_name','file_path','file_dirname','file_data_type','file_ctx','file_created_on']
    resolver: Optional[callable]
    route: Optional[callable]
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
    file_exists: bool # determines if file exists on filesystem
    file_ssg_api_dirpath: str # the files static generated api endpoint
    file_ssg_html_dirpath: str # the files static generated html endpoint

    async def process_route(self, pyonir_request, app_ctx): pass

    async def process_resolver(self, pyonir_request): pass

    async def process_response(self, pyonir_request): pass


class PyonirCollection:
    SortedList: list
    get_attr: callable
    dict_to_class: callable
    collections: list[Parsely]

class PyonirThemes:
    """Represents sites available and active theme(s) within the frontend directory."""
    themes_dirpath: str # directory path to available site themes
    _available_themes: PyonirCollection | None # collection of themes available in frontend/themes directory

    @property
    def active_theme(self) -> Theme | None: pass

    def _get_available_themes(self) -> PyonirCollection | None: pass

class TemplateEnvironment:
    themes: PyonirThemes

class PyonirRequest:

    server_response: any
    file: Optional[Parsely]
    server_request: Optional['StarletteRequest']
    raw_path: str
    method: str
    path: str
    url: str
    slug: str
    path_params: dict[str, str]
    query_params: dict[str, str]
    parts: list[str]
    limit: int
    model: str
    is_home: bool
    is_api: bool
    form: dict
    files: list
    ip: str
    host: str
    protocol: str
    headers: dict
    browser :str
    type: Union[TEXT_RES, JSON_RES, EVENT_RES]
    status_code: int

    @property
    def redirect(self): pass

    async def process_request_data(self):
        """Get form data and file upload contents from request"""
        pass

    def derive_status_code(self, is_router_method: bool):
        """Create status code for web request based on a file's availability, status_code property"""
        pass

    def render_error(self):
        """Data output for an unknown file path for a web request"""
        pass

    def resolve_request_to_file(self, path_str: str, app: 'PyonirApp', skip_vanity: bool = False) -> tuple['PyonirApp', Parsely]:pass

    @staticmethod
    def process_header(headers):pass

    @staticmethod
    def get_params(url):pass


class PyonirBase:
    PAGINATE_LIMIT: str
    DATE_FORMAT: str
    TIMEZONE: str
    SOFTWARE_VERSION: str
    APPS_DIRNAME: str
    BACKEND_DIRNAME: str
    FRONTEND_DIRNAME: str
    CONTENTS_DIRNAME: str
    THEMES_DIRNAME: str
    CONFIGS_DIRNAME: str
    TEMPLATES_DIRNAME: str
    SSG_DIRNAME: str
    SSG_IN_PROGRESS: str
    UPLOADS_THUMBNAIL_DIRNAME: str
    UPLOADS_DIRNAME: str
    ASSETS_DIRNAME: str
    API_DIRNAME: str
    PAGES_DIRNAME: str
    CONFIG_FILENAME: str

class PyonirApp(PyonirBase):
    configs: object
    request_paths: str
    nginx_config_filepath: str
    unix_socket_filepath: str
    ssg_dirpath: str
    logs_dirpath: str
    backend_dirpath: str
    contents_dirpath: str
    frontend_dirpath: str
    pages_dirpath: str
    api_dirpath: str
    plugins_dirpath: str
    uploads_dirpath: str
    resolvers_dirpath: str
    jinja_filters_dirpath: str
    app_ctx: str
    env: str
    is_dev: str
    host: str
    port: str
    protocol: str
    is_secure: str
    domain: str
    parse_jinja: callable
    parse_pyformat: callable
    setup_templates: callable
    install_sys_plugins: callable
    install_plugins: callable
    run_plugins: callable
    run_async_plugins: callable
    setup_configs: callable
    run: callable
    pyonir_path: type
    endpoint: str
    app_dirpath: str
    app_name: str
    app_account_name: str
    TemplateEnvironment: TemplateEnvironment
    server: PyonirServer
    available_plugins: dict[str, callable]

class PyonirPlugin(PyonirBase):

    _app_ctx = None
    app: PyonirApp
    app_entrypoint: str # plugin application initializing file
    app_dirpath: str # plugin directory path
    name: str # web url to serve application pages
    routing_paths: list
    CONFIG_FILENAME: str
    request_paths: AppRequestPaths
    backend_dirpath: str
    contents_dirpath: str
    frontend_dirpath: str
    ssg_dirpath: str
    app_ctx: AppCtx

    def register_routing_dirpaths(self, dir_paths: list):
        """Registers a new pages directory path for resolving web based request"""
        pass

    def register_templates(self, dir_paths: list):
        """Registers additional paths for jinja templates. Templates will load in order of priority."""
        pass

    def insert(self, file_path: str, contents: dict) -> Parsely:
        """Creates a new file"""
        pass

    @staticmethod
    def query_files(dir_path: str, app_ctx: tuple, model_type: any = None) -> list[Parsely]: pass

    @staticmethod
    def install_directory(plugin_src_directory: str, site_destination_directory: str): pass