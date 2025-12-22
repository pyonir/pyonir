from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Optional, Union, Tuple, Callable, get_type_hints, OrderedDict, Any, List

from pyonir.core.utils import get_attr, merge_dict
from starlette.applications import Starlette
from starlette.requests import Request as StarletteRequest

from pyonir.core.app import BaseApp
from pyonir.core.parser import DeserializeFile
from pyonir.pyonir_types import PyonirRouters, PyonirHooks, PyonirRoute, VIRTUAL_ROUTES_FILENAME
from pyonir.core.utils import dict_to_class

TEXT_RES: str = 'text/html'
JSON_RES: str = 'application/json'
EVENT_RES: str = 'text/event-stream'

# Environments
LOCAL_ENV:str = 'LOCAL'
DEV_ENV:str = 'DEV'
PROD_ENV:str = 'PROD'




class BaseRequest:
    PAGINATE_LIMIT: int = 6

    def __init__(self, server_request: Optional[StarletteRequest], app: BaseApp):
        from pyonir.core.utils import get_attr
        from pyonir.core.auth import Auth

        self.server_response = None
        self.file: Optional[DeserializeFile] = None
        self.server_request: StarletteRequest = server_request
        self.raw_path = "/".join(str(self.server_request.url).split(str(self.server_request.base_url))) if server_request else ''
        self.method = self.server_request.method if server_request else 'GET'
        self.path = self.server_request.url.path if server_request else '/'
        self.path_params = dict_to_class(self.server_request.path_params,'path_params') if server_request else {}
        self.url = f"{self.path}" if server_request else {}
        self.slug = self.path.lstrip('/').rstrip('/')
        self.query_params = self.get_params(self.server_request.url.query) if server_request else {}
        self.parts = self.slug.split('/') if self.slug else []
        self.limit = get_attr(self.query_params, 'limit', self.PAGINATE_LIMIT)
        self.model = get_attr(self.query_params, 'model')
        self.is_home = (self.slug == '')
        self.is_api = self.parts and self.parts[0] == app.API_DIRNAME
        self.is_static = bool(list(os.path.splitext(self.path)).pop()) if server_request else False
        self.form = {}
        self.files = []
        # self.ip = self.server_request.client.host if server_request else ''
        self.host = str(self.server_request.base_url).rstrip('/') if server_request else app.host
        self.protocol = self.server_request.scope.get('type') + "://" if server_request else app.protocol
        self.headers = self.process_header(self.server_request.headers) if server_request else {}
        self.browser = self.headers.get('user-agent', '').split('/').pop(0) if self.headers else "UnknownAgent"
        if self.slug.startswith('api'): self.headers['accept'] = JSON_RES
        self.type: Union[TEXT_RES, JSON_RES, EVENT_RES] = self.headers.get('accept')
        self.status_code: int = 200
        self._app_ctx_ref = None
        self.app = app
        self.auth: Optional[Auth] = None
        self.flashes: dict = self.get_flash_messages() if server_request else {}
        if server_request:
            self.server_request.session['previous_url'] = self.headers.get('referer', '')

    @property
    def app_ctx_ref(self):
        return self._app_ctx_ref or self.app

    @property
    def session_token(self):
        """Returns active csrf token for user session"""
        if self.server_request and self.server_request.session:
            return self.server_request.session.get('csrf_token')

    @property
    def previous_url(self) -> str:
        return self.server_request.session.pop('previous_url') or '/'

    @property
    def redirect_to(self):
        """Returns the redirect URL from the request form data"""
        file_redirect = self.file.data.get('redirect_to', self.file.data.get('redirect'))
        return self.form.get('redirect_to', self.form.get('redirect', file_redirect))

    def ssg_request(self, page, params):
        self.file = page
        self.url = page.data.get('url')
        self.path = page.data.get('url')
        self.slug = page.data.get('slug')
        self.path_params.update(params)

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

        from pyonir.core.utils import expand_dotted_keys
        import json

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
                    if hasattr(content, "filename"):
                        setattr(content, "ext", os.path.splitext(content.filename)[1])
                        self.files.append(content)
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
        from pyonir.core.parser import FileStatuses

        code = 404
        if self.file.is_virtual_route:
            # If the file is a router method, we assume it is valid
            code = 200
        elif self.file.file_status in (FileStatuses.PROTECTED, FileStatuses.FORBIDDEN):
            self.file.data = {'template': '40x.html', 'content': f'Unauthorized access to this resource.', 'url': self.url, 'slug': self.slug}
            code = 401
        elif self.file.file_status == FileStatuses.PUBLIC or is_router_method:
            code = 200
        self.status_code = code #200 if self.file.file_exists or is_router_method else 404

    def set_app_context(self) -> None:
        """Gets the routing context from web request"""
        path_str = self.path.replace(self.app.API_ROUTE, '')
        for plg in self.app.activated_plugins:
            if not hasattr(plg, 'endpoint'): continue
            if path_str.startswith(plg.endpoint):
                self._app_ctx_ref = plg
                print(f"Request has switched to {plg.name} context")
                break

    def render_error(self):
        """Data output for an unknown file path for a web request"""
        return {
            "url": self.url,
            "method": self.method,
            "status": self.status_code,
            "res": self.server_response,
            "title": f"{self.path} was not found!",
            "content": f"Perhaps this page once lived but has now been archived or permanently removed from {self.app_ctx_ref.name}."
        }

    def fetch_virtual_route(self, app: BaseApp, url: str) -> Optional[DeserializeFile]:
        """Fetches a virtual route matching the request path for the current app context"""
        virtual_page_path = os.path.join(app.pages_dirpath, VIRTUAL_ROUTES_FILENAME) + BaseApp.EXTENSIONS['file']
        if not os.path.exists(virtual_page_path): return None
        virtual_route = DeserializeFile(virtual_page_path, app_ctx=app.app_ctx)
        vkey, vdata, vparams, wildcard_vdata = self.app.server.get_virtual(url, virtual_data=virtual_route.data)
        if vparams and vkey:
            self.path_params.update(vparams)
            virtual_route.replay_retry()
            vdata = virtual_route.data.get(vkey) if vkey else vdata
        virtual_route.data = {'url': self.url, 'slug': self.slug, **(vdata or {})}
        virtual_route.is_virtual_route = bool(vkey)
        if wildcard_vdata:
            merge_dict(wildcard_vdata, virtual_route.data)
        virtual_route.apply_filters()
        return virtual_route

    def resolve_request_to_file(self, app: BaseApp, path_str: str = None) -> DeserializeFile:
        """
        Resolve a request URL to its corresponding resource.

        The function checks plugin-provided paths first, then falls back to the main
        application's file system. If no matching file or virtual route is found,
        a 404 page is returned.
        """
        from pyonir.core.app import BaseApp
        from pyonir.core.parser import DeserializeFile
        path_str = path_str or self.path
        is_home = path_str == '/'
        ctx_route, ctx_paths = app.request_paths or ('', [])
        ctx_route = ctx_route or ''
        ctx_slug = ctx_route[1:]
        path_slug = path_str[1:]
        app_scope, *path_segments = path_slug.split('/')
        is_api_request = (len(path_segments) and path_segments[0] == app.API_DIRNAME) or path_str.startswith(app.API_ROUTE)
        # revalidate_cache = getattr(self.query_params, 'reload', False)
        # DeserializeFile._invalidate_cache = bool(revalidate_cache)
        # Normalize API prefix and path segments
        if is_api_request:
            path_str = path_str.replace(app.API_ROUTE, '')

        virtual_route = self.fetch_virtual_route(app, path_str)
        request_segments = [
            segment for segment in path_slug.split('/')
            if segment and segment not in (app.API_DIRNAME, ctx_slug)
        ]

        # Skip if no paths or route doesn't match
        if not ctx_paths or (not is_home and not path_str.startswith(ctx_route)):
            return None

        # Try resolving to actual file paths
        protected_segment = [s if i > len(request_segments)-1 else f'_{s}' for i,s in enumerate(request_segments)]

        for root_path in ctx_paths:
            if not is_api_request and root_path.endswith(app.API_DIRNAME): continue
            category_index = os.path.join(root_path, *request_segments, 'index.md')
            single_page = os.path.join(root_path, *request_segments) + BaseApp.EXTENSIONS['file']
            single_protected_page = os.path.join(root_path, *protected_segment) + BaseApp.EXTENSIONS['file']

            for candidate in (category_index, single_page, single_protected_page):
                if os.path.exists(candidate):
                    route_page = DeserializeFile(candidate, app_ctx=app.app_ctx)
                    if virtual_route:
                        merge_dict(derived=virtual_route.data, src=route_page.data)
                        # route_page.data.update(virtual_route.data)
                        route_page.apply_filters()
                    return route_page

        errorpage = DeserializeFile('404_ERROR')
        errorpage.data = self.render_error()
        return virtual_route if virtual_route and virtual_route.is_virtual_route else errorpage

    @staticmethod
    def process_header(headers):
        nheaders = dict(headers)
        nheaders['accept'] = nheaders.get('accept', TEXT_RES).split(',', 1)[0]
        agent = nheaders.get('user-agent', '')
        nheaders['user-agent'] = agent.split(' ').pop().split('/', 1)[0]
        return nheaders

    @staticmethod
    def get_params(url, as_dict=False):
        from pyonir.core.mapper import dict_to_class
        from pyonir.core.utils import parse_url_params
        args = parse_url_params(url)
        if args.get('model'): del args['model']
        return args if as_dict else dict_to_class(args, 'query_params')

    def process_resolver(self, request: 'BaseRequest') -> Optional[Union[callable, Any]]:
        """Updates request data a callable method to execute during request."""
        from pyonir import Site
        from pyonir.core.utils import get_attr
        resolver_obj = self.file.data.get('@resolvers', {})
        resolver_action = resolver_obj.get(request.method)
        if not resolver_action: return
        resolver_path = resolver_action.get('call')
        del resolver_action['call']
        self.file.data.update(resolver_action)

        app_plugin = list(filter(lambda p: p.name == resolver_path.split('.')[0], Site.activated_plugins))
        app_plugin = app_plugin[0] if len(app_plugin) else Site
        resolver = app_plugin.reload_resolver(resolver_path)

        request.type = get_attr(resolver_action, 'headers.accept') or request.type
        request.form.update(resolver_action)
        if not resolver:
            request.auth.response = request.auth.responses.ERROR.response(message=f"Unable to resolve endpoint")
        return resolver

class BaseServer(Starlette):

    def __init__(self, app: BaseApp):
        self.is_active = False
        self.app = app
        self.ws_routes = []
        self.sse_routes = []
        self.auth_routes = []
        self.endpoints = set()
        self.url_map = {} # named reference to routes by function name
        self.route_map = {} # named reference to routes by path
        self.resolvers = {}
        self.services = {}
        self.request: Optional[BaseRequest] = None
        self.virtual_routes: Optional[OrderedDict] = None

        self.initialize_starlette()


    @property
    def allowed_hosts(self):
        """Returns a list of domains allowed to access the web application"""
        return ['localhost', '*.localhost']

    def run_uvicorn_server(self, uvicorn_options: dict = None):
        """Starts the webserver"""
        import uvicorn, sys
        from pathlib import Path

        # """Uvicorn web server configurations"""
        # Uvicorn’s config only allows one binding method at a time:
        # TCP socket → use host + port (+ optional SSL)
        # Unix domain socket → use uds (+ optional SSL)
        uvicorn_options = uvicorn_options or {}
        if not uvicorn_options:
            if self.app.is_dev:
                uvicorn_options.update({
                    "port": self.app.port,
                    "host": self.app.host,
                })
            else:
                uvicorn_options = {'uds': self.app.unix_socket_filepath}

            if self.app.is_secure:
                uvicorn_options["ssl_keyfile"] = self.app.ssl_key_file
                uvicorn_options["ssl_certfile"] = self.app.ssl_cert_file

        # Setup logs
        Path(self.app.logs_dirpath).mkdir(parents=True, exist_ok=True)
        # Initialize routers
        self.init_pyonir_endpoints(self.app)
        print(f"/************** ASGI APP SERVER RUNNING on {'http' if self.app.is_dev else 'sock'} ****************/")
        print(f"\
        \n\t- App env: {'DEV' if self.app.is_dev else 'PROD'}:{self.app.VERSION}\
        \n\t- App name: {self.app.name}\
        \n\t- App domain: {self.app.domain_name}\
        \n\t- App host: {self.app.host}\
        \n\t- App port: {self.app.port}\
        \n\t- App sock: {self.app.unix_socket_filepath}\
        \n\t- App ssl_key: {self.app.ssl_key_file}\
        \n\t- App ssl_cert: {self.app.ssl_cert_file}\
        \n\t- App Server: Uvicorn \
        \n\t- NGINX config: {self.app.nginx_config_filepath} \
        \n\t- System Version: {sys.version_info}")
        print(uvicorn_options)
        self.app.run_plugins(PyonirHooks.AFTER_INIT)
        # self.app.run_hooks(PyonirHooks.AFTER_INIT)
        self.is_active = True
        uvicorn.run(self.app.server, **uvicorn_options)

    def init_app_routes(self, routes: List[PyonirRoute], endpoint: str = ''):
        for path, func, methods, opts in routes:
            self.create_route(dec_func=func, path=f'{endpoint}{path}', methods=methods, **opts)
            pass

    def init_app_router(self, router: PyonirRouters):
        for endpoint, routes in router:
            self.init_app_routes(routes, endpoint=endpoint)

    @staticmethod
    def init_pyonir_endpoints(app: BaseApp):
        from pyonir.tests.backend.demo_controller import pyonir_ws_handler, pyonir_index
        # app.server.create_route(pyonir_ws_handler, "/sysws", ws=True)
        # app.server.create_route(pyonir_index, "/", methods='*')
        app.server.create_route(pyonir_index, "/{path:path}", methods='*')

    @staticmethod
    def create_static_route(assets_dir: str):
        """Creates a route for serving static files"""
        from starlette.staticfiles import StaticFiles
        return StaticFiles(directory=assets_dir)

    def create_route(self, dec_func: Optional[Callable],
                path: str = '',
                methods=None,
                static_path: str = None,
                auth: bool = None,
                ws: bool = None,
                sse: bool = None,
                **options: dict) -> Optional[Callable]:
        """A mapping of an HTTP method and an endpoint to a handler function."""
        import inspect

        is_async = inspect.iscoroutinefunction(dec_func) if dec_func else False
        is_asyncgen = inspect.isasyncgenfunction(dec_func) if dec_func else False
        if methods == '*':
            methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
        if methods is None:
            methods = ['GET']

        if static_path:
            static_route = self.create_static_route(static_path)
            self.mount(path, static_route)
            self.url_map[path.lstrip('/')
            .replace('/', '_')] = {'path': path, 'dir': static_path, 'exists': os.path.exists(static_path)}
            return None

        route_name = dec_func.__name__ if dec_func else None
        docs = dec_func.__doc__ if dec_func else None
        route_path = path.split('/{')[0]
        name = route_name
        endpoint_route = path.split('/', 1)[0]
        # req_models = Site.server.url_map.get(route_name, {}).get('models') or {}

        new_route = {
            "doc": docs,
            "endpoint": endpoint_route,
            # "params": get_type_hints(dec_func) if dec_func else None,
            "route": path,  # has regex pattern
            "path": route_path,
            "methods": methods,
            "name": name,
            "auth": auth or options.pop('@auth', None),
            "sse": sse,
            "ws": ws,
            "async": is_async,
            "async_gen": is_asyncgen,
            "func": dec_func
        }
        # Add route path into categories
        self.endpoints.add(f"{endpoint_route}{route_path}")
        self.url_map[name] = new_route
        self.route_map[path] = new_route
        if sse:
            self.sse_routes.append(f"{endpoint_route}{route_path}")
        if auth:
            self.auth_routes.append(f"{endpoint_route}{route_path}")
        if ws:
            self.ws_routes.append(f"{endpoint_route}{route_path}")
            return self.add_websocket_route(path, dec_func, dec_func.__name__)

        async def dec_wrapper(star_req):
            pyonir_request = BaseRequest(star_req, self.app)
            res = await self.build_response(pyonir_request, dec_func)
            # self.app.reload_module(dec_func)
            return res

        if dec_func:
            dec_wrapper.__name__ = dec_func.__name__
            dec_wrapper.__doc__ = dec_func.__doc__
        self.add_route(path, dec_wrapper, methods=methods)

    def initialize_starlette(self):
        """Setup Starlette web server"""
        super().__init__()
        from starlette_wtf import CSRFProtectMiddleware
        from starlette.middleware.sessions import SessionMiddleware
        from starlette.middleware.trustedhost import TrustedHostMiddleware
        # from starlette.middleware.gzip import GZipMiddleware

        self.add_middleware(TrustedHostMiddleware)
        # star_app.add_middleware(GZipMiddleware, minimum_size=500)
        self.add_middleware(SessionMiddleware,
                                https_only=False,
                                secret_key=self.app.SECRET_SAUCE,
                                session_cookie=self.app.SESSION_KEY,
                                same_site='lax'
                                )
        self.add_middleware(CSRFProtectMiddleware, csrf_secret=self.app.SECRET_SAUCE)

    def get_virtual(self, url: str, virtual_data: dict = None) -> Union[tuple[str, dict, dict, dict], tuple[None, None, None, dict]]:
        """Performs url pattern matching against virtual routes and returns vitual page data and new path parameter values."""
        _data = (virtual_data or {})
        wildcard_data = _data.pop('*') if _data.get('*') else {}
        for vurl, vdata in _data.items():
            has_match = self.matching_route(url, vurl)
            if has_match:
                return vurl, vdata, has_match, wildcard_data
        return None, None, None, wildcard_data

    @staticmethod
    async def build_response(pyonir_request: BaseRequest, dec_func: callable):
        import inspect
        from pyonir import Site
        from pyonir.core.auth import Auth
        from pyonir.core.mapper import cls_mapper, func_request_mapper

        default_system_router = dec_func.__name__ == 'pyonir_index' if dec_func else False
        Site.server.request = pyonir_request
        if not default_system_router and dec_func and Site.is_dev:
            dec_func = pyonir_request.app.reload_module(dec_func, reload=True)

        # Init Web response object
        pyonir_response = BaseRestResponse(status_code=pyonir_request.status_code)

        # Preprocess request form data
        await pyonir_request.process_request_data()

        # Init Auth handler
        pyonir_request.auth = Auth(pyonir_request, Site)

        # Update template globals for request
        Site.TemplateEnvironment.globals['request'] = pyonir_request

        # File processing for request
        pyonir_request.set_app_context()
        req_file = pyonir_request.resolve_request_to_file(pyonir_request.app_ctx_ref)
        pyonir_request.file = req_file
        # app_ctx.apply_virtual_routes(pyonir_request) # disabled virtual routes in favor of module
        resolver = pyonir_request.process_resolver(pyonir_request)
        custom_response_headers = get_attr(pyonir_request.file.data, '@response.headers', {})

        route_func = dec_func if not callable(resolver) else resolver

        # Check resolver route security
        security = pyonir_request.auth.security.check(pyonir_request.auth)
        if security and not security.accepted:
            return Site.server.serve_redirect(security.redirect_to or '/')

        # Get router endpoint from map
        is_async = inspect.iscoroutinefunction(route_func)
        args = func_request_mapper(route_func, pyonir_request)
        if not pyonir_request.is_static:
            if callable(route_func):
                pyonir_request.server_response = await route_func(**args) if is_async else route_func(**args)
            else:
                pyonir_request.server_response = req_file.resolver or req_file.data

        # Perform redirects
        if pyonir_request.redirect_to:
            return Site.server.serve_redirect(pyonir_request.redirect_to)

        # Derive status code
        is_router = Site.server.url_map.get(route_func.__name__ if route_func else '') and not default_system_router
        pyonir_request.derive_status_code(is_router_method=is_router)

        # Execute plugins hooks initial request
        await Site.run_async_plugins(PyonirHooks.ON_REQUEST, pyonir_request)

        # Finalize response output
        if isinstance(pyonir_request.server_response, BaseRestResponse):
            pyonir_response = pyonir_request.server_response
        elif pyonir_request.is_static:
            pyonir_request.server_response = Site.server.resolve_static(Site, pyonir_request) or (await route_func(**args) if is_async else route_func(**args))
            pyonir_response.set_file_response(pyonir_request.server_response)
        else:
            if pyonir_request.type == JSON_RES:
                pyonir_response.set_json(pyonir_request.server_response or pyonir_request.file.data)
            elif pyonir_request.type == TEXT_RES:
                pyonir_response.set_html(pyonir_request.file.output_html(pyonir_request))
            else:
                print(f'{pyonir_request.type} doesnt have a handler')
            pyonir_response.set_media(pyonir_request.type)

        # Set headers
        if custom_response_headers:
            pyonir_response.set_headers_from_dict(custom_response_headers)

        # Generate response
        return pyonir_response.build()

    @staticmethod
    def matching_route(route_path: str, regex_path: str, api_endpoint: str = '') -> Optional[dict]:
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

    @staticmethod
    def resolve_static(app: BaseApp, request: BaseRequest) -> Union['FileResponse', 'PlainTextResponse']:
        from_frontend = request.path.startswith(app.frontend_assets_route)
        from_public = request.path.startswith(app.public_assets_route)
        base_path = app.frontend_assets_dirpath if from_frontend else app.public_assets_dirpath if from_public else ''
        req_path = request.parts[1:] if len(request.parts) > 1 else request.parts
        path = os.path.join(base_path, *req_path)
        has_path = os.path.exists(path)
        if not has_path: print('Pyonir: skipping static: '+ path)
        return BaseServer.serve_static(path) if has_path else None

    @staticmethod
    def serve_static(path: str) -> Optional['FileResponse']:
        from starlette.responses import FileResponse, PlainTextResponse
        has_path = os.path.exists(path)
        res = FileResponse(path, 200) if has_path else None
        if has_path and path.endswith('.js'):
            res.headers["Cross-Origin-Opener-Policy"] = "same-origin"
            res.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        return res

    @staticmethod
    def response_renderer(value, media_type):
        from starlette.responses import Response, StreamingResponse
        if media_type == EVENT_RES:
            return StreamingResponse(content=value, media_type=media_type)
        return Response(content=value, media_type=media_type)

    @staticmethod
    def serve_redirect(url: str, code=302):
        from starlette.responses import RedirectResponse
        res = RedirectResponse(url=url.strip(), status_code=code)
        res.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        res.headers["Pragma"] = "no-cache"
        res.headers["Expires"] = "0"
        return res

    @staticmethod
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

@dataclass
class BaseRestResponse:
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
    _file_response: any = None
    _media_type: str = None
    _server_response: object = None
    _headers: dict = field(default_factory=dict)

    @property
    def headers(self): return self._headers

    @property
    def content(self) -> 'Response':
        from starlette.responses import Response, StreamingResponse
        content = ''
        media_type = self._media_type
        if self._file_response:
            self._media_type = 'static'
            return self._file_response
        if self._stream:
            media_type = EVENT_RES
            content = StreamingResponse(content=self._stream, media_type=EVENT_RES)
        if self._html:
            media_type = TEXT_RES
            content = self._html
        if self.data:
            media_type = JSON_RES
            content = self.to_json()
        self._media_type = media_type
        return Response(content=content, media_type=media_type)

    def to_dict(self) -> dict:
        return {
            'status_code': self.status_code,
            'message': self.message,
            'data': self.data
        }

    def to_json(self) -> str:
        """Converts the response to a JSON serializable dictionary."""
        from pyonir.core.utils import json_serial
        import json
        return json.dumps(self.to_dict(), default=json_serial)

    def render(self):
        return self._server_response

    def set_header(self, key, value):
        """Sets header values"""
        self._headers[key] = value
        return self

    def set_json(self, value: dict):
        # json = request.file.output_json()
        self.data = value
        return self

    def set_html(self, value: str):
        """Sets the html response value"""
        self._html = value
        return self

    def set_file_response(self, value: any):
        """Sets the file response value"""
        self._file_response = value

    def build(self):
        """Builds the response object"""
        self.set_header('Server', 'Pyonir Web Framework')
        res = self.content
        if self.headers:
            for key, value in self.headers.items():
                res.headers[key] = str(value)

        return self.content

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

    def set_headers_from_dict(self, headers: dict):
        """Sets multiple header values from a dictionary"""
        if headers:
            self._headers.update(headers)



