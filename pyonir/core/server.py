from __future__ import annotations

import os, sys
from dataclasses import dataclass
from typing import Optional, Callable, List, Union

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.staticfiles import StaticFiles

from pyonir.core.app import BaseApp
from pyonir.core.utils import dict_to_class
from pyonir.pyonir_types import PyonirRoute

TEXT_RES: str = 'text/html'
JSON_RES: str = 'application/json'
EVENT_RES: str = 'text/event-stream'

# Environments
LOCAL_ENV:str = 'LOCAL'
DEV_ENV:str = 'DEV'
PROD_ENV:str = 'PROD'

def generate_nginx_conf(app: BaseApp) -> bool:
    """Generates a NGINX conf file based on App configurations"""
    from pyonir.core.utils import get_attr, create_file
    nginx_app_baseurl = get_attr(app.env, "nginx.baseurl")
    nginx_conf = app.TemplateEnvironment.get_template("nginx.jinja.conf") \
        .render(
        app_name=app.name,
        app_name_id=app.name.replace(' ', '_').lower(),
        domain=app.domain_name,
        is_dev=app.is_dev,
        is_secure=app.is_secure,
        ssl_cert_file=app.ssl_cert_file,
        ssl_key_file=app.ssl_key_file,
        site_dirpath=app.app_dirpath,
        site_logs_dirpath=app.logs_dirpath,
        app_socket_filepath=app.unix_socket_filepath,
        app_ignore_logs=f"{app.PUBLIC_ASSETS_DIRNAME}|{app.UPLOADS_DIRNAME}|{app.FRONTEND_ASSETS_DIRNAME}",
        frontend_assets_route=app.frontend_assets_route,
        frontend_assets_dirpath=app.frontend_assets_dirpath,
        public_assets_route=app.public_assets_route,
        public_assets_dirpath=app.public_assets_dirpath,
        site_uploads_route=app.uploads_route,
        site_uploads_dirpath=app.uploads_dirpath,
        site_ssg_dirpath=app.ssg_dirpath,
        custom_nginx_locations=get_attr(app.server, 'nginx_locations')
    )

    return create_file(app.nginx_config_filepath, nginx_conf, False)

def route_wrapper(route: RouteConfig, **kwargs):
    """Wraps route function with additional logic for request handling, security checks, and response building"""
    async def dec_wrapper(star_req):
        """Wrapper function for handling incoming requests, performing security checks, and building responses"""
        from pyonir.core.authorizer import PyonirBaseRequest
        pyonir_request: PyonirBaseRequest = PyonirBaseRequest(star_req, star_req.app.pyonir_app)
        star_req.app.pyonir_app.server.request = pyonir_request
        await pyonir_request.set_request_input()
        await pyonir_request.set_page_file()
        pyonir_request.security.responses.load_responses(pyonir_request.file.data)
        if pyonir_request.security.is_denied:
            pyonir_request.server_response.set_redirect_response(pyonir_request.security.redirect_to or '/')
        res = await pyonir_request.build_response(route)
        return res
    return dec_wrapper

@dataclass
class RouteConfig:
    doc: str
    endpoint: str
    route: str
    path: str
    methods: List[str]
    name: str
    static_path: str
    func: Optional[Callable]
    params: dict
    use_security: bool
    use_sse: bool
    use_ws: bool
    is_async: bool
    is_async_gen: bool
    is_static: bool

    @property
    def is_index(self):
        return self.path == '/'

class PyonirDebugRequestMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and attach user credentials to the request state."""

    async def dispatch(self, request: Request, call_next):
        is_file = '.' in str(request.url)
        if not is_file:
            if 'count' not in request.session:
                request.session['count'] = 1
            else:
                request.session['count'] = int(request.session['count']) + 1
            print("SESSION:", request.session, request.url)
            print("COOKIE HEADER:", request.headers.get("cookie"))

        return await call_next(request)

class PyonirServer(Starlette):
    """Extends Starlette server"""

    def __init__(self, pyonir_app: BaseApp):
        super().__init__()
        from starlette_wtf import CSRFProtectMiddleware
        from starlette.middleware.sessions import SessionMiddleware
        from starlette.middleware.trustedhost import TrustedHostMiddleware
        # from starlette.middleware.gzip import GZipMiddleware
        self.route_map = {}
        self.static_map = {}
        self.url_map = {}
        self.endpoints = set()
        self.is_active: bool = False
        self.request = None
        self.pyonir_app: BaseApp = pyonir_app
        # self.add_middleware(PyonirDebugRequestMiddleware)
        self.add_middleware(SessionMiddleware,
                            https_only=False,
                            domain=self.pyonir_app.domain,
                            max_age=3600,
                            secret_key=self.pyonir_app.salt,
                            session_cookie=self.pyonir_app.session_key,
                            same_site='lax'
                            )
        self.add_middleware(TrustedHostMiddleware)
        self.add_middleware(CSRFProtectMiddleware, csrf_secret=self.pyonir_app.salt)
        # star_app.add_middleware(GZipMiddleware, minimum_size=500)

    def register_route(self, path, route_func: Union[str, Callable], methods: list = None, params: dict = None):
        import inspect

        is_async = inspect.iscoroutinefunction(route_func) if route_func else False
        is_asyncgen = inspect.isasyncgenfunction(route_func) if route_func else False
        methods = ['GET'] if methods is None else ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'] if methods == '*' else methods
        params = {} if not params else params
        is_secure = params.pop('@security', False)
        is_sse = params.pop('@sse', False)
        is_ws = params.pop('@ws', False)
        is_static_path = os.path.exists(route_func) if isinstance(route_func, str) else False
        route_name = route_func.__name__ if route_func else params.get('name', None)
        docs = route_func.__doc__ if route_func else None
        base_endpoint, _, endpoint_path = (path[1:]).partition('/')
        is_index_path = path == '/' or _ == ""
        if endpoint_path:
            endpoint_path = endpoint_path.split('/{')[0]
        _path = '/' if is_index_path else f'/{base_endpoint}/{endpoint_path}'

        new_route = RouteConfig(**{
            "doc": docs,
            "endpoint": base_endpoint,
            "params": params,
            "route": path,  # has regex pattern
            "path": _path,
            "methods": methods,
            "name": route_name,
            "func": route_func if not is_static_path else None,
            "static_path": route_func,
            "use_security": is_secure,
            "use_sse": is_sse,
            "use_ws": is_ws,
            "is_async": is_async,
            "is_async_gen": is_asyncgen,
            "is_static": is_static_path,
        })

        if is_static_path:
            self.static_map[_path] =new_route
            return new_route
        # Add route path into categories
        self.endpoints.add(f"{base_endpoint}{_path}")
        self.url_map[path] = new_route
        self.route_map[route_name] = new_route

    def mount_pyonir_route_config(self, new_route: RouteConfig):
        route_func_wrapper = route_wrapper(new_route)
        if new_route.is_static:
            self.add_static_route(new_route.route, new_route.static_path)
        elif new_route.use_ws:
            self.add_websocket_route(new_route.route, new_route.func, new_route.name)
        else:
            self.add_route(path=new_route.route, route=route_func_wrapper, methods=new_route.methods, **new_route.params)

    def register_routes(self, routes: List[PyonirRoute], endpoint: str = None):
        """Registers multiple route configurations at once"""
        for path, route_func, methods, *opts in routes:
            args = {} if not opts else opts[0]
            self.register_route(path=f'{(endpoint or "")}{path}', route_func=route_func, methods=methods, params=args)
            pass

    def add_static_route(self, url: str, directory_path: str):
        if not os.path.exists(directory_path):
            print(f"Unable to mount '{url}' static files at {directory_path}")
            return
        self.mount(url, StaticFiles(directory=directory_path))

    def init_default_static_routes(self):
        if self.pyonir_app.use_themes:
            self.add_static_route(self.pyonir_app.frontend_assets_route, self.pyonir_app.themes.active_theme.static_dirpath)
        else:
            self.add_static_route(self.pyonir_app.frontend_assets_route, self.pyonir_app.frontend_assets_dirpath)
        self.add_static_route(self.pyonir_app.public_assets_route, self.pyonir_app.public_assets_dirpath)
        self.add_static_route(self.pyonir_app.uploads_route, self.pyonir_app.uploads_dirpath)
        # self.add_static_route("/{__file_path__:path}", self.pyonir_app.public_assets_dirpath)

    def init_routes(self):
        """Mounts registered routes into the server"""
        for path, route in self.url_map.items():
            self.mount_pyonir_route_config(route)

    def run_uvicorn_server(self, uvicorn_options: dict = None):
        """Starts the uvicorn web service"""
        import uvicorn
        from pathlib import Path

        # """Uvicorn web server configurations"""
        # Uvicorn’s config only allows one binding method at a time:
        # TCP socket → use host + port (+ optional SSL)
        # Unix domain socket → use uds (+ optional SSL)
        uvicorn_options = uvicorn_options or {}
        if not uvicorn_options:
            if self.pyonir_app.is_dev:
                uvicorn_options.update({
                    "port": self.pyonir_app.port,
                    "host": self.pyonir_app.host,
                })
            else:
                uvicorn_options = {'uds': self.pyonir_app.unix_socket_filepath}

            if self.pyonir_app.is_secure:
                uvicorn_options["ssl_keyfile"] = self.pyonir_app.ssl_key_file
                uvicorn_options["ssl_certfile"] = self.pyonir_app.ssl_cert_file

        # Setup logs
        Path(self.pyonir_app.logs_dirpath).mkdir(parents=True, exist_ok=True)
        mode = "http" if self.pyonir_app.is_dev else "sock"
        env = "DEV" if self.pyonir_app.is_dev else "PROD"

        print(f"""
        /************** ASGI APP SERVER RUNNING on {mode} ****************/
        
            - App env: {env}:{self.pyonir_app.VERSION}
            - App name: {self.pyonir_app.name}
            - App domain: {self.pyonir_app.domain}
            - App domain_name: {self.pyonir_app.domain_name}
            - App host: {self.pyonir_app.host}
            - App port: {self.pyonir_app.port}
            - App sock: {self.pyonir_app.unix_socket_filepath}
            - App ssl_key: {self.pyonir_app.ssl_key_file}
            - App ssl_cert: {self.pyonir_app.ssl_cert_file}
            - App Server: Uvicorn
            - NGINX config: {self.pyonir_app.nginx_config_filepath}
            - System Version: {sys.version_info}
        """)
        print(uvicorn_options)
        print(self.pyonir_app.domain)
        self.init_default_static_routes()
        self.init_routes()
        self.is_active = True
        uvicorn.run(self, **uvicorn_options)

    @staticmethod
    def serve_static(path):
        from starlette.responses import FileResponse, PlainTextResponse
        code = 400 if not os.path.exists(path) else 200
        res = FileResponse(path, code)
        return res

    @staticmethod
    def generate_nginx_conf(app: BaseApp) -> bool:
        """Generates a NGINX conf file based on App configurations"""
        return generate_nginx_conf(app)