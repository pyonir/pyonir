import dataclasses
import typing, os
from enum import Enum
from jinja2 import Environment
from starlette.applications import Starlette
from starlette.requests import Request as StarletteRequest

from pyonir.utilities import parse_all


class Parsely:
    app_ctx: tuple
    abspath: str
    absdir: str
    contents_relpath: str
    file_ctx: str
    file_dir: str
    file_type: str
    file_name: str
    file_ext: str
    file_relpath: str
    file_contents: str
    file_lines: str
    file_line_count: str
    data: dict
    schema: 'schema'


@dataclasses.dataclass
class PyonirRequest:
    raw_path: str
    method: str
    path: str
    path_params: str
    url: str
    slug: str
    query_params: dict
    parts: list
    limit: int
    model: str
    is_home: bool
    form: dict
    files: list
    ip: str
    host: str
    protocol: str
    headers: dict
    browser: str
    type: str
    status_code: int
    auth: any
    use_endpoints: bool
    server_response = ""
    server_request: StarletteRequest
    file: Parsely | None


# RoutePath: str = ''
# Route = List[RoutePath, Callable, List[str]]
# Endpoint = Tuple[RoutePath, List[Route]]
# Endpoints = Tuple[Endpoint]

class PyonirHooks(Enum):
    ON_REQUEST = 'ON_REQUEST'
    ON_PARSELY_COMPLETE = 'ON_PARSELY_COMPLETE'


class PyonirServer(Starlette):
    ws_routes = []
    sse_routes = []
    auth_routes = []
    endpoints = []
    url_map = {}
    resolvers = {}
    response_renderer: typing.Callable
    create_route: typing.Callable
    create_endpoint: typing.Callable
    serve_static: typing.Callable
    serve_redirect: typing.Callable

    def __int__(self):
        super().__init__()


class IApp:
    def __init__(self):
        self.pages_dirpath = None
        self.frontend_dirpath = None
        self.backend_dirpath = None
        self.contents_dirpath = None
        self.files_ctx = None
        self.theme_static_dirpath = None
        self.server: PyonirServer = None
        self.site_logs_dirpath = None
        self.TemplateParser: Environment = None
        self.app_nginx_conf_filepath = None
        self.app_socket_filepath = None
        self.theme_assets_dirpath = None
        self.ssg_dirpath = None
        self.uploads_dirpath = None
        self.configs = None
        self.domain = None
        self.env = None
        self.is_dev = None
        self.is_secure = None
        self.host = None
        self.port = None
        self.name = None
        self.app_dirpath = None

    pass

    def run_plugins(self, hook: PyonirHooks, pyonir_request): pass


class IPlugin:
    name: str
    hooks: PyonirHooks
    @staticmethod
    def collect_dir_files(dir_path: str, app_ctx: tuple, file_type: any) -> [Parsely]:
        return parse_all(dir_path, app_ctx, file_type)
    @staticmethod
    def uninstall(app):
        """Uninstall plugin from system. this method will destroy any traces of the plugin and its files"""
        pass

    @staticmethod
    def register_templates(dir_paths: [str], app: IApp):
        """Loads new jinja templates paths to application instance"""
        if not hasattr(app.TemplateParser,'loader'): return None
        for path in dir_paths:
            if path in app.TemplateParser.loader.searchpath: continue
            app.TemplateParser.loader.searchpath.append(path)

    @staticmethod
    def unregister_templates(dir_paths: [str], app: IApp):
        """Loads new jinja templates paths to application instance"""
        if not hasattr(app.TemplateParser,'loader'): return None
        for path in dir_paths:
            if path in app.TemplateParser.loader.searchpath: continue
            app.TemplateParser.loader.searchpath.remove(path)