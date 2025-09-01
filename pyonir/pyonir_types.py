from dataclasses import dataclass, field
import os
from typing import Optional, Union, Callable, List, Tuple, Iterator, Dict

from jinja2 import Environment
from starlette.applications import Starlette

TEXT_RES: str = 'text/html'
JSON_RES: str = 'application/json'
EVENT_RES: str = 'text/event-stream'
PAGINATE_LIMIT: int = 6


# === Route Definitions ===
PagesPath = str
APIPath = str
RoutePath = str
"""Represents the URL path of a route (e.g., '/about', '/api/data')."""

RouteFunction = Callable
"""A callable that handles a specific route request (e.g., controller function)."""

RouteMethods = List[str]
"""HTTP methods supported by a route (e.g., ['GET', 'POST'])."""

PyonirRoute = Tuple[RoutePath, RouteFunction, RouteMethods]
"""A single route entry containing the path, its handler function, and allowed HTTP methods."""

PyonirRouters = List[Tuple[RoutePath, List[PyonirRoute]]]
"""A collection (or group) of routes, usually organized by feature or resource, and often mounted under"""


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

    def __iter__(self) -> Iterator['Parsely']:
        return iter(self.items)



class PyonirOptions:
    contents_dirpath: str  = '' # base directory path for markdown files
    use_file_based_routing: bool = None # toggles use of file based routing directory
    routes_dirpath: str = ''    # path for resolving file based routing
    routes_api_dirpath: str = '' # path for resolving file based API configured endpoints
    file_based_routes: dict = {}# configurations for resolving file based routes that contain dynamic path params

class Pagination:
    page_num: int = 1
    limit: int = 0

class PyonirHooks(str):
    AFTER_INIT = 'AFTER_INIT'
    ON_REQUEST = 'ON_REQUEST'
    ON_PARSELY_COMPLETE = 'ON_PARSELY_COMPLETE'


class Parsely:
    default_file_attributes = ['file_name','file_path','file_dirname','file_data_type','file_ctx','file_created_on']
    resolver: Optional[callable]
    route: Optional[callable]
    app_ctx: AppCtx # application context for file
    status: str
    """Status based on access rights"""

    schema: callable
    """Model object associated with file."""
    file_status: str
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

    def output_html(self, pyonir_request): pass

    def output_json(self): pass


class PyonirCollection:
    SortedList: list
    get_attr: callable
    dict_to_class: callable
    collections: list[Parsely]

class Theme:
    name: str
    theme_dirname: str
    theme_dirpath: str
    static_dirname: str
    templates_dirname: str
    static_dirpath: str

class PyonirThemes:
    """Represents sites available and active theme(s) within the frontend directory."""
    themes_dirpath: str
    """Path to the themes directory, typically 'frontend/themes'."""
    available_themes: Optional[Dict[str, Theme]] = None
    """Dictionary of available themes, keyed by theme name."""
    active_theme: Optional[Theme] = None
    """Currently active theme, if any."""

class TemplateEnvironment(Environment):

    themes: PyonirThemes
    get_template: callable
    def add_filter(self, filter_method: callable): pass
    def load_template_path(self, path: str): pass


@dataclass
class PyonirRestResponse:
    """Represents a REST response from the server."""
    
    status_code: int = 000
    """HTTP status code of the response, e.g., 200 for success, 404 for not found."""

    message: str = ''
    """Response message, typically a string describing the result of the request."""

    data: dict = field(default_factory=dict)
    """Response data, typically a dictionary containing the response payload."""

    _cookies: list = field(default_factory=list)
    _html: str = None
    _stream: any = None
    _media_type: str = None
    _server_response: object = None
    _headers: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'status_code': self.status_code,
            'message': self.message,
            'data': self.data
        }

    def to_json(self) -> str:
        """Converts the response to a JSON serializable dictionary."""
        from .utilities import json_serial
        import json
        return json.dumps(self.to_dict(), default=json_serial)

    def render(self):
        return self._server_response

    def set_header(self, key, value):
        """Sets header values"""
        self._headers[key] = value

    def set_json(self, value: dict):
        # json = request.file.output_json()
        self.data = value
    
    def set_html(self, value: str):
        """Sets the html response value"""
        # html = request.file.output_html(request)
        self._html = value

    def set_server_response(self):
        """Renders the starlette web response"""
        from starlette.responses import Response, StreamingResponse

        if self._media_type == EVENT_RES and self._stream:
            return StreamingResponse(content=self._stream, media_type=EVENT_RES)

        content = self._html if self._html else self.to_json()
        media_type = TEXT_RES if self._html else JSON_RES
        self._server_response = Response(content=content, media_type=media_type)
        if self._headers:
            self._server_response.headers.update(self._headers)
        # if self._cookies:
        #     for cookie in self._cookies:
        #         self._server_response.set_cookie(**cookie)


    def set_media(self, media_type: str):
        self._media_type = media_type

    def set_cookie(self, cookie: dict):
        """
        :param cookie:
            key="access_token"
            value=jwt_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=3600,
        :return:
        """
        self._cookies.append(cookie)

class PyonirRequest:

    server_response: PyonirRestResponse
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
    is_static: bool
    form: dict
    files: list
    ip: str
    host: str
    protocol: str
    headers: dict
    browser :str
    type: Union[TEXT_RES, JSON_RES, EVENT_RES]
    status_code: int
    auth: 'Auth'
    session_token: Optional[str]
    redirect_to: Optional[str]
    """URL to redirect to after processing the request."""

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

class PyonirServer(Starlette):
    ws_routes = []
    sse_routes = []
    auth_routes = []
    endpoints = []
    url_map = {}
    resolvers = {}
    services = {}
    paginate: Pagination = Pagination()
    request: PyonirRequest = None
    def response_renderer(self): pass
    def serve_redirect(self, url: str): pass
    def create_endpoint(self): pass
    def create_route(self): pass
    def serve_static(self): pass

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

    def parse_file(self) -> Parsely:
        """Parses a file and returns a Parsely instance for the file."""
        pass

class EnvConfig:
    """Application Configurations"""
    APP_ENV: str
    APP_KEY: str
    APP_DEBUG: bool
    APP_URL: str
    DB_CONNECTION: str
    DB_HOST: str
    DB_PORT: int
    DB_DATABASE: str
    DB_USERNAME: str
    DB_PASSWORD: str

class PyonirAppSettings:
    name: str
    domain: str
    theme: Optional[str]

class PyonirApp(PyonirBase):

    PUBLIC_ASSETS_DIRNAME: str
    FRONTEND_ASSETS_DIRNAME: str
    PLUGINS_DIRNAME: str
    uploads_route: str

    frontend_route: str
    assets_route: str

    ssl_key_file: Optional[str]
    ssl_cert_file: Optional[str]

    SECRET_SAUCE: str
    settings: PyonirAppSettings
    env: EnvConfig
    request_paths: str
    nginx_config_filepath: str
    unix_socket_filepath: str
    static_assets_dirpath: str
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
    is_dev: bool
    host: str
    port: str
    protocol: str
    is_secure: bool
    domain: str
    parse_jinja: callable
    parse_pyformat: callable
    setup_templates: callable
    install_sys_plugins: callable
    install_plugins: callable
    run_plugins: callable
    run_async_plugins: callable
    setup_configs: callable
    generate_resolvers: callable
    run: callable
    pyonir_path: type
    endpoint: str
    name: str
    app_dirpath: str
    app_name: str
    app_account_name: str
    TemplateEnvironment: TemplateEnvironment
    themes: PyonirThemes
    server: PyonirServer
    plugins_installed: dict[str, callable]
    plugins_activated: dict[str, callable]

    def subscribe_hook(self, caller:callable, hook:str): pass

    def add_routing_path(self,api_endpoint:str, endpoint: str, paths: list[str]): pass


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