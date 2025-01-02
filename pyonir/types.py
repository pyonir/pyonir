import dataclasses
import typing

from starlette.applications import Starlette
from starlette.requests import Request


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
    server_request: Request


# RoutePath: str = ''
# Route = List[RoutePath, Callable, List[str]]
# Endpoint = Tuple[RoutePath, List[Route]]
# Endpoints = Tuple[Endpoint]


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
        self.files_ctx = None
        self.theme_static_dirpath = None
        self.server: PyonirServer = None
        self.site_logs_dirpath = None
        self.TemplateParser = None
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
