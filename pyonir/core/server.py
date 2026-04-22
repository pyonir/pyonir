from __future__ import annotations

import base64
import inspect
import os, sys
from dataclasses import dataclass
from typing import Optional, Callable, List, Union, AsyncGenerator, Any, Dict

from starlette.responses import FileResponse, RedirectResponse


from starlette.applications import Starlette, P
from starlette.middleware import _MiddlewareFactory
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.staticfiles import StaticFiles

from pyonir import BaseSchema, BaseApp
from pyonir.core.parser import DeserializeFile
from pyonir.core.mapper import func_request_mapper
from pyonir.pyonir_types import PyonirRoute, PyonirHooks
from pyonir.core.utils import merge_dict, dict_to_class, to_json
from starlette.requests import Request as StarletteRequest

TEXT_RES: str = 'text/html'
JSON_RES: str = 'application/json'
EVENT_RES: str = 'text/event-stream'
STATIC_RES: str = 'static'

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

def route_wrapper(route_config: RouteConfig, **kwargs):
    """Wraps route function with additional logic for request handling, security checks, and response building"""
    async def dec_wrapper(star_req):
        """Wrapper function for handling incoming requests, performing security checks, and building responses"""
        pyonir_request: PyonirRequest = PyonirRequest(star_req, star_req.app.pyonir_app)
        pyonir_response: PyonirServerResponse = await PyonirServerResponse.from_request(pyonir_request, route_config)
        return pyonir_response.build()

    return dec_wrapper

@dataclass
class RouteConfig:
    doc: str = None
    endpoint: str = None
    route: str = None
    path: str = None
    methods: List[str] = None
    name: str = None
    static_path: str = None
    func: Optional[Callable] = None
    configs: dict = None
    params: dict = None
    use_security: bool = None
    use_sse: bool = None
    use_ws: bool = None
    is_async: bool = None
    is_async_gen: bool = None
    is_static: bool = None

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
        self.route_map = {}
        self.static_map = {}
        self.url_map = {}
        self.endpoints = set()
        self.is_active: bool = False
        self.request = None
        self.pyonir_app: BaseApp = pyonir_app
        self._installed_middleware = set()

    def _init_framework_middleware(self):
        from starlette_wtf import CSRFProtectMiddleware
        from starlette.middleware.sessions import SessionMiddleware
        from starlette.middleware.trustedhost import TrustedHostMiddleware
        # from starlette.middleware.gzip import GZipMiddleware
        # self.add_middleware(PyonirDebugRequestMiddleware)
        self.add_middleware(SessionMiddleware,
                            https_only=not self.pyonir_app.is_dev,
                            secret_key=self.pyonir_app.salt,
                            session_cookie=self.pyonir_app.session_key,
                            max_age=3600,
                            same_site='lax'
                            )
        self.add_middleware(TrustedHostMiddleware)
        self.add_middleware(CSRFProtectMiddleware, csrf_secret=self.pyonir_app.salt)
        # star_app.add_middleware(GZipMiddleware, minimum_size=500)

    def add_middleware(
        self,
        middleware_class: _MiddlewareFactory[P],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        if middleware_class in self._installed_middleware: return
        self._installed_middleware.add(middleware_class)
        super().add_middleware(middleware_class, *args, **kwargs)

    def build_middleware_stack(self):
        self._init_framework_middleware()
        return super().build_middleware_stack()

    def register_route(self, path, route_func: Union[str, Callable], methods: list = None, params: dict = None):
        import inspect

        is_async = inspect.iscoroutinefunction(route_func) if route_func else False
        is_asyncgen = inspect.isasyncgenfunction(route_func) if route_func else False
        methods = ['GET'] if methods is None else ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'] if methods == '*' else methods
        params = {} if not params else params
        configs = dict(params)
        is_secure = params.pop('@security', False)
        is_sse = params.pop('@sse', False)
        is_ws = params.pop('@ws', False)
        is_static_path = os.path.exists(route_func) if isinstance(route_func, str) else False
        route_name = params.get('name', route_func.__name__ if route_func else '')
        docs = route_func.__doc__ if route_func else None
        base_endpoint, _, endpoint_path = (path[1:]).partition('/')
        is_index_path = path == '/' or _ == ""
        if endpoint_path:
            endpoint_path = endpoint_path.split('/{')[0]
        _path = '/' if is_index_path else f'/{base_endpoint}/{endpoint_path}'

        new_route = RouteConfig(**{
            "name": route_name,
            "doc": docs,
            "endpoint": base_endpoint,
            "route": path,  # has regex pattern
            "func": route_func if not is_static_path else None,
            "static_path": route_func,
            "methods": methods,
            "configs": configs,
            "params": params,
            "path": _path,
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
        if not isinstance(new_route, RouteConfig):
            return
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

    def add_url_route(self, name: str, path: str):
        self.route_map[name] = RouteConfig(path=path)

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
        if not self.endpoints:
            self.register_route('/', pyonir_home, '*')
            self.register_route('/{path:path}', pyonir_home, '*')
            pass

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
        self.pyonir_app.plugin_manager.run_plugins(PyonirHooks.AFTER_INIT)

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

class PyonirJSONResponse:

    def __init__(self, message: str = None, status_code: int = None,  data: dict = None):
        self.status_code: int = status_code or 000
        """HTTP status code of the response, e.g., 200 for success, 404 for not found."""

        self.message: str = message
        """Response message, typically a string describing the result of the request."""

        self.data: dict = data or {}
        """Response data, typically a dictionary containing the response payload."""

    @property
    def is_ok(self) -> bool:
        """Indicates if the response status code represents a successful request."""
        return 200 <= self.status_code < 300

    def response(self, message: str = None, status_code: int = None,  data: dict = None):
        self.message = message or self.message
        self.status_code = status_code or self.status_code
        self.data = data or self.data
        return self

    def to_dict(self, context_data: dict = None) -> dict:
        """Converts the response to a dictionary."""
        from pyonir import Site
        return {
            'status_code': self.status_code,
            'message': Site.TemplateEnvironment.render_python_string(self.message or ''),
            'data': self.data,
            **(context_data or {})
        }

class PyonirJSONResponses:
    """Enum-like class that provides standardized authentication responses."""
    SERVER_OK = PyonirJSONResponse(
        message="Server Ok",
        status_code=200
    )
    """PyonirAuthResponse: Indicates general server status of ok"""

    ERROR = PyonirJSONResponse(
        message="Authentication failed",
        status_code=400
    )
    """PyonirAuthResponse: Indicates an authentication error due to invalid credentials or bad input (HTTP 400)."""

    INVALID_CREDENTIALS = PyonirJSONResponse(
        message="The credentials provided is incorrect.",
        status_code=401
    )
    """PyonirAuthResponse: Indicates failed credential authentication (HTTP 401)."""

    SUCCESS = PyonirJSONResponse(
        message="Authentication successful",
        status_code=200
    )
    """PyonirAuthResponse: Indicates successful authentication (HTTP 200)."""

    ACTIVE_SESSION = PyonirJSONResponse(
        message="Authentication successful. session is active",
        status_code=200
    )
    """PyonirAuthResponse: Active authentication session (HTTP 200)."""

    UNAUTHORIZED = PyonirJSONResponse(
        message="Unauthorized access",
        status_code=401
    )
    """PyonirAuthResponse: Indicates missing or invalid authentication credentials (HTTP 401)."""

    SESSION_EXPIRED = PyonirJSONResponse(
        message="Session has expired. New Sign in required",
        status_code=401
    )
    """PyonirAuthResponse: Indicates missing or invalid authentication credentials (HTTP 401)."""

    NO_ACCOUNT_EXISTS = PyonirJSONResponse(message="Account not found.", status_code=409)
    """Error: The requested action cannot be completed because the user does not have an account."""

    USER_SIGNED_OUT = PyonirJSONResponse(message="User signed out", status_code=200)
    """PyonirAuthResponse: User signed out"""

    ACCOUNT_EXISTS = PyonirJSONResponse(message="Account already exists", status_code=409)
    """PyonirAuthResponse: Indicates that the user account already exists (HTTP 409)."""

    SOMETHING_WENT_WRONG = PyonirJSONResponse(message="Something went wrong, please try again later", status_code=422)
    """PyonirAuthResponse: Indicates a general error occurred during authentication (HTTP 422)."""

    TOO_MANY_REQUESTS = PyonirJSONResponse(message="Too many requests. Try again later", status_code=429)
    """PyonirAuthResponse: Indicates too many requests have been made, triggering rate limiting (HTTP 429)."""

    @classmethod
    def response(cls, message: str, status_code: int = 200, data: dict = None):
        data = data or {}
        return PyonirJSONResponse(message=message, status_code=status_code, data=data)

    def add(self,response_name: str, message: str, status_code: int, data: dict = None):
        data = data or {}
        setattr(self, response_name.upper(), PyonirJSONResponse(message=message, status_code=status_code, data=data))

    def add_responses(self, responses: dict):
        for res_name, res_obj in (responses or {}).items():
            message = res_obj.get('message', '')
            status_code = res_obj.get('status_code', 200)
            data = {}
            for key, value in res_obj.items():
                if key.lower() in ('message', 'status_code'): continue
                data[key] = value
            self.add(res_name, message, status_code, data)

class PyonirServerResponse:

    def __init__(self, status_code: int = None, media_type: Union[TEXT_RES, JSON_RES, EVENT_RES, STATIC_RES] = None):
        # from pyonir.core.authorizer import PyonirRequest, DefaultPyonirAuthResponses
        self.status_code: int = status_code or 404
        self.media_type: Union[TEXT_RES, JSON_RES, EVENT_RES] = media_type
        self._json: Optional[str] = None
        self._html: Optional[str] = None
        self._stream: Optional[AsyncGenerator] = None
        self._message: Optional[str] = None
        self._headers: dict = {'Server': 'Pyonir Web Framework'}
        self._data: Any = None
        self._pyonir_request: Optional[PyonirRequest] = None
        self._redirect: Optional[RedirectResponse] = None
        self._responses = PyonirJSONResponses()

        self._security_configs: dict = None
        self._route_security_configs: dict = None

    @property
    def responses(self) -> 'DefaultPyonirAuthResponses':
        return self._responses

    def set_json(self, json_data: dict):
        self.media_type = self.media_type or JSON_RES
        self._json = to_json({
            'status_code': self.status_code,
            'message': self._message,
            'data': json_data,
        })
        return self

    def set_html(self, html: str):
        self.media_type = self.media_type or TEXT_RES
        self._html = html
        return self

    def set_stream(self, stream_obj: AsyncGenerator):
        self.media_type = self.media_type or EVENT_RES
        self._stream = stream_obj
        return self

    def set_data(self, value: Any):
        if isinstance(value, FileResponse):
            self.media_type = STATIC_RES
        self._data = value
        return self

    def set_headers(self, key, value):
        self._headers[key] = value

    async def setup_security(self, route_config: RouteConfig):
        # TODO: route_config should pass security params to request for more dynamic security checks (e.g. based on route params or query params)
        from .utils import get_attr
        file = self._pyonir_request.file
        if file:
            self.status_code = 200
            if self._pyonir_request.is_api: self.set_json(file)
            else: self.set_html(file.output_html(self._pyonir_request))
        file_data = file.data if file else None
        route_headers_configs = get_attr(route_config.configs, '@response.headers', {})
        route_security_configs = get_attr(route_config.configs, '@security', {})
        route_security_response = get_attr(route_config.configs, '@security.responses', {})

        file_headers_configs = get_attr(file_data, '@response.headers', {})
        file_security_configs = get_attr(file_data, '@security', {})
        file_security_response = get_attr(file_data, '@security.responses', {})

        security_responses = {**route_security_response, **file_security_response}
        response_headers = {**route_headers_configs, **file_headers_configs}
        security_configs = {**route_security_configs, **file_security_configs}

        security_auth = self._pyonir_request.security
        security_auth._route_config = route_config
        security_auth._security_configs = security_configs
        self._headers.update(response_headers)
        self._responses.add_responses(security_responses)

        if security_auth.is_denied:
            self.set_redirect(security_auth.redirect_to or '/')

    @classmethod
    async def from_request(cls, pyonir_request: 'PyonirRequest', route_config: RouteConfig) -> PyonirServerResponse:
        pyonir_request.pyonir_app.server.request = pyonir_request
        res = pyonir_request.server_response
        res._pyonir_request = pyonir_request
        await pyonir_request.set_request_input()
        await pyonir_request.set_page_file()
        await res.setup_security(route_config)
        if not res._redirect:
            # extract response file data
            router_func = pyonir_request.file_resolver or route_config.func

            # auto reload router functions during local dev
            if callable(router_func) and pyonir_request.pyonir_app.is_dev:
                router_func = pyonir_request.pyonir_app.reload_module(router_func, reload=True)

            is_async = inspect.iscoroutinefunction(router_func) # verify dynamic and static async route funcs
            args = func_request_mapper(router_func, pyonir_request)
            router_func_response = await router_func(**args) if is_async else router_func(**args)
            if isinstance(router_func_response, PyonirServerResponse):
                router_func_response._pyonir_request = pyonir_request
                return router_func_response
            res.set_data(router_func_response)
        return res

    def set_redirect(self, url: str, code: int = 302):
        from starlette.responses import RedirectResponse
        self._redirect = RedirectResponse(url, status_code=code)
        return self

    def error_page(self):
        """Creates a error page"""
        f = DeserializeFile('')
        f.data = self._pyonir_request.render_error()
        return f

    def build(self):
        """Builds the Starlette server response object"""
        from starlette.exceptions import HTTPException
        from starlette.responses import Response, StreamingResponse
        from pyonir.core.utils import to_json
        has_form_redirect = not self._redirect and self._pyonir_request.security.creds.body.get('redirect')
        if has_form_redirect:
            self.set_redirect(has_form_redirect)

        if self.status_code >= 500:
            raise HTTPException(status_code=self.status_code, detail="System error occurred")
        if self._redirect:
            return self._redirect

        if self.media_type == STATIC_RES:
            return self._data
        if self.media_type == EVENT_RES:
            return StreamingResponse(content=self._stream, media_type=EVENT_RES)

        content = self._data or self._html or self._json
        is_404 = not content
        if is_404:
            self.media_type = JSON_RES if self._pyonir_request.is_api else TEXT_RES
            _e = self.error_page()
            content = to_json(_e) if self._pyonir_request.is_api else _e.output_html(self._pyonir_request)

        server_res = Response(content=content, media_type=self.media_type, status_code=self.status_code)

        if self._headers and server_res.headers:
            for key, value in self._headers.items():
                server_res.headers[key] = str(value)

        return server_res

class PyonirRequestInput(BaseSchema):
    body: Dict = {}
    headers: Dict = {}
    session: Dict = {}
    files: list = []
    jwt: dict = {}

    # ---------- Body ----------

    @property
    def email(self) -> str:
        if self.basic_credentials:
            return self.basic_credentials[0]
        return self.body.get("email", "")

    @property
    def password(self) -> str:
        if self.basic_credentials:
            return self.basic_credentials[1]
        return self.body.get("password", "")

    @property
    def remember_me(self) -> bool:
        return self.body.get("remember_me", False)

    # ---------- Headers ----------

    @property
    def authorization(self) -> str | None:
        return self.headers.get("authorization")

    @property
    def bearer_token(self) -> str | None:
        auth = self.authorization
        if not auth:
            return None

        auth_type, auth_value = auth.split(" ", 1)

        if auth_type.lower() == "bearer":
            return auth_value

        return None

    @property
    def basic_credentials(self) -> tuple[str, str] | None:
        auth = self.authorization
        if not auth:
            return None

        auth_type, auth_value = auth.split(" ", 1)

        if auth_type.lower() == "basic":
            decoded = base64.b64decode(auth_value).decode("utf-8")
            return tuple(decoded.split(":", 1))

        return None

    # ---------- Session ----------

    @property
    def session_id(self) -> str | None:
        from pyonir.core.security import decode_jwt

        if not self.pyonir_app:
            return None
        session_key = self.pyonir_app.session_key or "pyonir_session"
        _session_id = self.session.get(session_key)
        _jwt = decode_jwt(_session_id, self.pyonir_app.salt)
        if _jwt:
            _session_id = _jwt.get('sub')
        else:
            _session_id = None
        return _session_id

    # ---------- Auth Flow ----------

    @property
    def flow(self) -> AuthMethod:
        from pyonir.core.security import AuthMethod

        if self.basic_credentials:
            return AuthMethod.BASIC

        if self.bearer_token:
            return AuthMethod.BEARER

        if self.session_id:
            return AuthMethod.SESSION

        if self.email and self.password:
            return AuthMethod.BODY

        return AuthMethod.NONE

    def validate_email(self):
        """Validates the email format"""
        import re
        from pyonir.core.security import INVALID_EMAIL_MESSAGE
        if not self.email or not re.match(r"[^@]+@[^@]+\.[^@]+", self.email):
            self._errors.append(INVALID_EMAIL_MESSAGE)

    def validate_password(self):
        """Validates the password for login"""
        from pyonir.core.security import INVALID_PASSWORD_MESSAGE
        if not self.password or len(self.password) < 6:
            self._errors.append(INVALID_PASSWORD_MESSAGE)

    # ---------- Constructors ----------

    @classmethod
    async def from_request(
        cls,
        request: StarletteRequest,
        pyonir_app: BaseApp = None
    ) -> "PyonirRequestInput":
        """Extracts user credentials and request data from the incoming request."""
        from .security import preprocess_request_body
        headers = dict(request.headers)
        session = dict(request.session)
        path_params = dict(request.path_params) or {}
        query_params = dict(request.query_params) or {}

        body, files = await preprocess_request_body(request)

        if path_params or query_params:
            body.update(path_params)
            body.update(query_params)

        return cls(
            body=body,
            headers=headers,
            session=session,
            files=files,
        )

class PyonirRequest:
    PAGINATE_LIMIT: int = 6

    def __init__(self, server_request: Optional[StarletteRequest], app: BaseApp):
        from pyonir.core.security import PyonirSecurity

        self.pyonir_app: BaseApp = app
        self.file: Optional[DeserializeFile] = None
        self.file_resolver: Optional[Callable] = None
        self.server_request: StarletteRequest = server_request
        self.server_response: PyonirServerResponse = PyonirServerResponse()
        self.request_input: PyonirRequestInput = PyonirRequestInput() if not server_request else None
        self.security: Optional[PyonirSecurity] = PyonirSecurity(self)

        # path params
        self.host = str(server_request.base_url).rstrip('/') if server_request else app.host
        self.protocol = server_request.scope.get('type') + "://" if server_request else app.protocol
        self.raw_path = "/".join(str(server_request.url).split(str(server_request.base_url))) if server_request else ''
        self.method = server_request.method if server_request else 'GET'
        self.path = server_request.url.path if server_request else '/'
        self.url = self.path if server_request else {}
        self.slug = self.path.lstrip('/').rstrip('/')
        self.parts = self.slug.split('/') if self.slug else []
        self._path_params: object = None
        self._query_params: object = None
        # self.path_params: Dict[str, Any] = dict(self.server_request.path_params) if server_request else {}

        # boolean flags
        self.is_home = (self.slug == '')
        self.is_api = self.parts and self.parts[0] == app.API_DIRNAME
        self.is_static = bool(list(os.path.splitext(self.path)).pop()) if server_request else False
        self.is_sse = server_request and EVENT_RES in server_request.headers.get("accept", "")
        if self.is_api:
            self.path = self.path.replace(app.API_ROUTE, '')  # normalize api path

        # application context
        self.flashes: dict = self.get_flash_messages() if server_request and not self.is_static else {}
        self._app_ctx_ref = None

        # Update template globals for request
        app.TemplateEnvironment.globals['request'] = self

    @property
    def csrf_token(self):
        from starlette_wtf import csrf_token
        return csrf_token(self.server_request)

    @property
    def app_ctx_ref(self) -> BaseApp:
        return self._app_ctx_ref or self.pyonir_app

    @property
    def headers(self) -> dict:
        """Returns the headers from the server request"""
        return dict(self.server_request.headers) if self.server_request else {}

    @property
    def path_params(self) -> object:
        """Returns the path parameters from the server request"""
        if not self._path_params:
            self._path_params = dict_to_class(self.server_request.path_params if self.server_request else {}, 'path_params', True)
        return self._path_params

    @property
    def query_params(self) -> object:
        """Returns the query parameters from the server request"""
        if not self._query_params:
            self._query_params = dict_to_class(self.server_request.query_params if self.server_request else {}, 'query_params', True)
        return self._query_params

    @property
    def files(self):
        """Returns uploaded files from the request input"""
        return self.request_input.files if self.request_input else []

    @property
    def form(self):
        """Returns form data from the request input"""
        return self.request_input.body if self.request_input else {}

    @property
    def user(self) -> Optional[Type[PyonirUser]]:
        """Returns the authenticated user for the current request"""
        return self.security.authenticated_user

    @property
    def session_token(self):
        """Returns active csrf token for user session"""
        if self.server_request and self.server_request.session:
            return self.server_request.session.get('csrf_token')

    @property
    def session(self):
        if self.server_request and hasattr(self.server_request, 'session'):
            return self.server_request.session
        return {}

    @property
    def redirect_to(self):
        """Returns the redirect URL from the request form data"""
        if not self.file: return None
        file_redirect = self.request_input.body.get('redirect_to', self.request_input.body.get('redirect'))
        return file_redirect

    def add_page_context(self, context: dict):
        """Safely adds context data onto existing page file"""
        if not self.file:
            raise AttributeError("Page file was not discovered.")
        self.file.data.update(context)
        self.file.apply_filters()

    def redirect(self, url: str, code: int = 302) -> PyonirRestResponse:
        """Redirects web request to the provided route or redirect_to value"""
        self.file = None
        return self.server_response.set_redirect(url, code=code)

    def render(self,
               media_type: Union[TEXT_RES, JSON_RES, EVENT_RES] = None,
               data: Any = None,
               status_code: int = 200, template: str = None
               ) -> PyonirResponse:
        """Renders web response object based on parameters"""
        res = PyonirServerResponse(status_code=status_code, media_type=JSON_RES if self.is_api else None)
        res._pyonir_request = self

        if not data: return res

        if not self.file:
            self.file = DeserializeFile('')
            self.file.data = {
                "url": self.url,
                "slug": self.slug,
            }

        if isinstance(data, dict) and template is not None:
            data['template'] = template
            self.add_page_context(data)

        html = self.file.output_html(self)
        json_data = self.file.data
        if self.is_api or media_type == JSON_RES:
            res.set_json(json_data)
        elif media_type == TEXT_RES:
            res.set_html(html)

        return res

    async def set_request_input(self, data: Optional[Dict] = None):
        """Sets the request input data from the web request. This gathers credentials and query parameters into a single PyonirRequestInput object."""
        # If there is no server request, just initialize from provided data
        if not self.server_request:
            self.request_input = PyonirRequestInput.from_dict(data or {})
            return

        self.request_input = await PyonirRequestInput.from_request(self.server_request, self.pyonir_app)
        if data:
            self.request_input.body.update(data)

    async def set_app_context(self) -> None:
        """Sets the application context for the current request based on the URL path."""

        path_str = self.path.replace(self.pyonir_app.API_ROUTE, '')
        for plg in self.pyonir_app.activated_plugins:
            if not hasattr(plg, 'endpoint'): continue
            if path_str.startswith(plg.endpoint):
                self._app_ctx_ref = plg
                print(f"Request has switched to {plg.name} context")
                break

    async def set_page_file(self) -> None:
        """
        Sets the page file for the current request based on resolved path

        The function checks plugin-provided paths first, then falls back to the main
        application's file system. If no matching file or virtual route is found,
        a 404 page is returned.
        """
        from pyonir.core.parser import DeserializeFile
        await self.set_app_context()
        app_ctx = self.app_ctx_ref
        path_str = self.path
        is_home = self.is_home
        ctx_route, ctx_paths = app_ctx.request_paths or ('', [])
        ctx_route = ctx_route or ''
        ctx_slug = ctx_route[1:]
        path_slug = path_str[1:]

        virtual_route, virtual_path = self.get_virtual_route()
        request_segments = [
            segment for segment in path_slug.split('/')
            if segment and segment not in (app_ctx.API_DIRNAME, ctx_slug)
        ]

        # Skip if no paths or route doesn't match
        if not ctx_paths or (not is_home and not path_str.startswith(ctx_route)):
            return None

        # Try resolving to actual file paths
        protected_segment = [s if i > len(request_segments)-1 else f'_{s}' for i,s in enumerate(request_segments)]

        for root_path in ctx_paths:
            if not self.is_api and root_path.endswith(app_ctx.API_DIRNAME): continue
            category_index = os.path.join(root_path, *request_segments, 'index.md')
            single_page = os.path.join(root_path, *request_segments) + BaseApp.EXTENSIONS['file']
            generated_page = os.path.join(root_path,app_ctx.GENERATED_API_DIRNAME, *request_segments) + BaseApp.EXTENSIONS['file']
            single_protected_page = os.path.join(root_path, *protected_segment) + BaseApp.EXTENSIONS['file']

            for candidate in (category_index, single_page, generated_page, single_protected_page):
                if os.path.exists(candidate):
                    route_page = DeserializeFile(candidate, app_ctx=app_ctx.app_ctx)
                    if virtual_route:
                        merge_dict(derived=virtual_route.data, src=route_page.data)
                        route_page.apply_filters()
                    self.file = route_page
                    self.server_response.status_code = 200
                    self.set_file_resolver()
                    return None
        if not virtual_path:
            self.server_response.status_code = 404
            if self.is_static: return
        else:
            virtual_route.replay_retry()
            self.file = virtual_route
            self.server_response.status_code = 200
            self.set_file_resolver()

    def set_file_resolver(self):
        """Updates request data a callable method to execute during request."""
        from pyonir import Site
        from pyonir.core.utils import get_attr
        if not self.file: return
        resolver_obj = self.file.data.get('@resolvers', {})
        resolver_action = resolver_obj.get(self.method)
        if not resolver_action: return
        resolver_path = resolver_action.pop('call')

        # TODO: use the app ctx activated plugins instead of global app
        app_plugin = list(filter(lambda p: p.name == resolver_path.split('.')[0], Site.activated_plugins))
        app_plugin = app_plugin[0] if len(app_plugin) else self.pyonir_app
        resolver = app_plugin.reload_resolver(resolver_path)
        custom_response_headers = get_attr(resolver_action, 'headers', {})

        if custom_response_headers:
            for k, v in custom_response_headers.items():
                self.server_response.set_headers(k,v)
            resolver_action.pop('headers')

        self.file.data.update(resolver_action)
        self.request_input.body.update(resolver_action)
        self.file_resolver = resolver


    def render_error(self):
        """Data output for an unknown file path for a web request"""
        return {
            "url": self.url,
            "title": f"{self.path} was not found!",
            "content": f"Perhaps this page once lived but has now been archived or permanently removed from {self.app_ctx_ref.name}."
        }

    def get_virtual_route(self) -> Union[tuple[DeserializeFile, str], None]:
        """Applies virtual route data to the current request file if available."""
        app_ctx = self.app_ctx_ref
        ctx_virtual_file = app_ctx.virtual_routes_file
        vkey, vdata, vpath_params, wildcard_vdata = self._get_virtual_params(ctx_virtual_file.data)

        if vpath_params and vkey:
            self.path_params.update(vpath_params)
            ctx_virtual_file.replay_retry()
            vdata = ctx_virtual_file.data.get(vkey) if vkey else vdata
        ctx_virtual_file.data = {'url': self.url, 'slug': self.slug, **(vdata or {})}
        ctx_virtual_file.is_virtual_route = bool(vkey)
        if wildcard_vdata:
            merge_dict(wildcard_vdata, ctx_virtual_file.data)
        ctx_virtual_file.apply_filters()
        return ctx_virtual_file, vkey

    def _get_virtual_params(self, virtual_data: Dict = None) -> Union[tuple[str, dict, dict, dict], tuple[None, None, None, dict]]:
        """Performs url pattern matching against virtual routes and returns vitual page data and new path parameter values."""
        _data = (virtual_data or {})
        wildcard_data = _data.pop('*') if _data.get('*') else {}
        virtual_api_url = self.is_api and self.url.replace(self.app_ctx_ref.API_ROUTE, '')
        for vurl, vdata in _data.items():
            has_match = self._matching_route(self.url, vurl)
            # virtual routes may require api access without the need to define separate routes
            if virtual_api_url and not has_match:
                has_match = self._matching_route(virtual_api_url, vurl)
            if has_match:
                return vurl, vdata, has_match, wildcard_data
        return None, None, None, wildcard_data

    def get_flash_messages(self) -> dict:
        """Pops and returns all flash messages from session"""
        if self.server_request:
            session_data = self.server_request.session
            flashes = session_data.get('__flash__') or {}
            if flashes:
                del session_data['__flash__']
            return flashes
        return {}

    def add_flash(self, key: str, value: any):
        flash_obj = self.server_request.session.get('__flash__') or {}
        flash_obj[key] = value
        self.server_request.session['__flash__'] = flash_obj

    def pull_flash(self, key):
        return self.flashes.get(key)

    @staticmethod
    def _matching_route(route_path: str, regex_path: str) -> Optional[dict]:
        """Returns path parameters when match is found for virtual routes"""
        from starlette.routing import compile_path
        path_regex, path_format, *args = compile_path(regex_path)
        match = path_regex.match(route_path)# check if request path matches the router regex
        trail_match = match or path_regex.match(route_path+'/')
        if trail_match:
            params = args[0] if args else {}
            res = trail_match.groupdict()
            for key, converter in params.items():
                res[key] = converter.convert(res[key])
            return res

async def pyonir_home() -> None:
    return None