import asyncio
import os, typing, json, inspect

from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect
from pyonir.core import PyonirApp, PyonirRequest
from pyonir.pyonir_types import PyonirServer, PyonirHooks, AppEndpoint, PyonirRouters, \
    PyonirRestResponse
from pyonir.utilities import create_file, get_attr, cls_mapper

TEXT_RES = 'text/html'
JSON_RES = 'application/json'
EVENT_RES = 'text/event-stream'

ConnClients = {}


async def pyonir_ws_handler(websocket: WebSocket):
    """ws connection handler"""
    from pyonir.utilities import generate_id

    async def get_data(ws: WebSocket):
        assert ws.application_state == WebSocketState.CONNECTED and ws.client_state == WebSocketState.CONNECTED
        wsdata = await ws.receive()

        if wsdata.get('text'):
            wsdata = wsdata['text']
            swsdata = json.loads(wsdata)
            swsdata['value'] = swsdata.get('value')
            wsdata = json.dumps(swsdata)
        elif wsdata.get('bytes'):
            wsdata = wsdata['bytes'].decode('utf-8')

        return wsdata

    async def broadcast(message: str, ws_id: str = None):
        for id, ws in ConnClients.items():
            if active_id == id and hasattr(ws, 'send_text'): continue
            await ws.send_text(message)

    async def on_disconnect(websocket: WebSocket):
        del ConnClients[active_id]
        client_data.update({"action": "ON_DISCONNECTED", "id": active_id})
        await broadcast(json.dumps(client_data))

    async def on_connect(websocket: WebSocket):
        client_data.update({"action": "ON_CONNECTED", "id": active_id})
        await websocket.send_text(json.dumps(client_data))

    active_id = generate_id()
    client_data = {}
    await websocket.accept()  # Accept the WebSocket connection
    print("WebSocket connection established!")
    ConnClients[active_id] = websocket
    await on_connect(websocket)
    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            # Wait for a message from the client
            data = await get_data(websocket)
            print(f"Received from client: {data}")
            # Respond to the client
            await broadcast(data)
        await on_disconnect(data)
    except Exception as e:
        del ConnClients[active_id]
        print(f"WebSocket connection closed: {active_id}")


async def pyonir_sse_handler(request: PyonirRequest) -> typing.AsyncGenerator:
    """Handles sse web request by pyonir"""
    from pyonir.utilities import generate_id
    request.type = EVENT_RES  # assign the appropriate streaming headers
    # set sse client
    event = get_attr(request.query_params, 'event')
    retry = get_attr(request.query_params, 'retry') or 1000
    close_id = get_attr(request.query_params, 'close')
    interval = 1  # time between events
    client_id = get_attr(request.query_params, 'id') or request.headers.get('user-agent')
    client_id += f"{client_id}{generate_id()}"
    if close_id and ConnClients.get(close_id):
        del ConnClients[close_id]
        return
    last_client = ConnClients.get(client_id, {
        "retry": retry,
        "event": event,
        "id": client_id,
        "data": {
            "time": 0
        },
    })
    # register new client
    if not ConnClients.get(client_id):
        ConnClients[client_id] = last_client

    while True:
        last_client["data"]["time"] = last_client["data"]["time"] + 1
        is_disconnected = await request.server_request.is_disconnected()
        if is_disconnected or close_id:
            del ConnClients[client_id]
            break
        await asyncio.sleep(interval)  # Wait for 5 seconds before sending the next message
        res = process_sse(last_client)
        yield res


async def pyonir_docs_handler(request: PyonirRequest):
    """Documentation for every endpoint by pyonir"""
    return {"routes": request.server_request.app.url_map, "configs": request.auth.app._env}


def pyonir_index(request: PyonirRequest):
    """Catch all routes for all web request"""
    pass


def setup_starlette_server(iapp: PyonirApp) -> PyonirServer:
    """Setup Starlette web server"""

    from starlette_wtf import CSRFProtectMiddleware
    from starlette.middleware.sessions import SessionMiddleware

    from starlette.middleware.trustedhost import TrustedHostMiddleware
    from starlette.middleware.gzip import GZipMiddleware
    from starlette.responses import Response, StreamingResponse
    from starlette.routing import Router, Route

    def render_response(value, media_type):
        if media_type == EVENT_RES:
            return StreamingResponse(content=value, media_type=media_type)
        return Response(content=value, media_type=media_type)

    def redirect(url, code=302):
        from starlette.responses import RedirectResponse
        res = RedirectResponse(url=url.strip(), status_code=code)
        res.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        res.headers["Pragma"] = "no-cache"
        res.headers["Expires"] = "0"
        return res

    def get_staticroute(assets_dir):
        from starlette.staticfiles import StaticFiles
        return StaticFiles(directory=assets_dir)

    allowed_hosts = ['localhost', '*.localhost']
    star_app = PyonirServer()  # inherits from Starlette
    star_app.add_middleware(TrustedHostMiddleware)
    # star_app.add_middleware(GZipMiddleware, minimum_size=500)
    star_app.add_middleware(SessionMiddleware,
                            https_only=False,
                            secret_key=iapp.SECRET_SAUCE,
                            session_cookie=iapp.SESSION_KEY,
                            same_site='lax'
                            )
    star_app.add_middleware(CSRFProtectMiddleware, csrf_secret=iapp.SECRET_SAUCE)

    # Interface properties required for pyonir to process web request
    setattr(star_app, 'response_renderer', render_response)
    setattr(star_app, 'serve_redirect', redirect)
    setattr(star_app, 'create_endpoint', Router)
    setattr(star_app, 'create_route', Route)
    setattr(star_app, 'serve_static', get_staticroute)

    return star_app


# def url_for(name, attr='path'):
#     """returns application route value based on named class function name"""
#     from pyonir import Site
#     if not Site: return None
#     urlmap = Site.server.url_map
#     return urlmap.get(name, {}).get(attr)


def init_app_endpoints(endpoints: 'Endpoints'):
    for endpoint, routes in endpoints:
        for path, func, methods, *opts in routes:
            _add_route(func, f'{endpoint}{path}', methods, *opts)
            pass


def init_pyonir_endpoints(app: PyonirApp):
    # app_frontend = (app.frontend_assets_route, app.frontend_assets_dirpath)
    # app_public = (app.public_assets_route, app.public_assets_dirpath)
    # app_uploads = (app.uploads_route, app.uploads_dirpath)
    # for route, static_abspath in (app_frontend, app_uploads, app_public):
    #     if not os.path.exists(static_abspath): continue
    #     _add_route(None, route, static_path=static_abspath)

    _add_route(pyonir_ws_handler, "/sysws", ws=True)
    _add_route(pyonir_index, "/", methods='*')
    _add_route(pyonir_index, "/{path:path}", methods='*')

def process_sse(data: dict) -> str:
    """Formats a string and an event name in order to follow the event stream convention.
    'event: Jackson 5\\ndata: {"abc": 123}\\n\\n'
    """
    sse_payload = ""
    for key, val in data.items():
        val = json.dumps(val) if key == 'data' else val
        sse_payload += f"{key}: {val}\n"
    return sse_payload + "\n"


def serve_static(app: PyonirApp, request: PyonirRequest):
    from starlette.responses import FileResponse, PlainTextResponse
    from_frontend = request.path.startswith(app.frontend_assets_route)
    from_public = request.path.startswith(app.public_assets_route)
    base_path = app.frontend_assets_dirpath if from_frontend else app.public_assets_dirpath if from_public else ''
    req_path = request.parts[1:] if len(request.parts) > 1 else request.parts
    path = os.path.join(base_path, *req_path)
    print('Pyonir: serving static: '+ path)
    return FileResponse(path, 200) if os.path.exists(path) else PlainTextResponse(f"{request.path} not found",
                                                                                  status_code=404)


def route(dec_func: typing.Callable,
          url: str = '',
          methods=None,
          auth: bool = None,
          ws: bool = None,
          sse: bool = None,
          static_path: str = None) -> typing.Callable:
    if dec_func is None and static_path is None:
        dec_func = pyonir_index
    return _add_route(dec_func, path=url, methods=methods, auth=auth, ws=ws, sse=sse, static_path=static_path)


def _add_route(dec_func: typing.Callable,
               path: str = '',
               methods=None,
               auth: bool = None,
               ws: bool = None,
               sse: bool = None,
               static_path: str = None) -> typing.Callable:
    """Route decorator"""
    from pyonir import Site

    is_async = inspect.iscoroutinefunction(dec_func) if dec_func else False
    is_asyncgen = inspect.isasyncgenfunction(dec_func) if dec_func else False
    # list_of_args = list(inspect.signature(dec_func).parameters.keys()) if dec_func else None
    if methods == '*':
        methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
    if methods is None:
        methods = ['GET']

    if static_path:
        from starlette.staticfiles import StaticFiles
        static_route = Site.server.serve_static(static_path)
        Site.server.mount(path, static_route)
        Site.server.url_map[path.lstrip('/')
        .replace('/', '_')] = {'path': path, 'dir': static_path, 'exists': os.path.exists(static_path)}
        return

    route_name = dec_func.__name__
    docs = dec_func.__doc__
    route_path = path.split('/{')[0]
    name = route_name
    endpoint_route = path.split('/', 1)[0]
    # req_models = Site.server.url_map.get(route_name, {}).get('models') or {}

    new_route = {
        "doc": docs,
        "endpoint": endpoint_route,
        "params": {k: v.__name__ for k, v in dec_func.__annotations__.items()},
        "route": path,  # has regex pattern
        "path": route_path,
        "methods": methods,
        # "models": req_models,
        "name": name,
        "auth": auth,
        "sse": sse,
        "ws": ws,
        "async": is_async,
        "async_gen": is_asyncgen,
    }
    # Add route path into categories
    Site.server.endpoints.append(f"{endpoint_route}{route_path}")
    Site.server.url_map[name] = new_route
    if sse:
        Site.server.sse_routes.append(f"{endpoint_route}{route_path}")
    if auth:
        Site.server.auth_routes.append(f"{endpoint_route}{route_path}")
    if ws:
        Site.server.ws_routes.append(f"{endpoint_route}{route_path}")
        return Site.server.add_websocket_route(path, dec_func, dec_func.__name__)

    async def dec_wrapper(star_req):
        from pyonir.core import PyonirRequest
        pyonir_request = PyonirRequest(star_req, Site)
        return await create_response(pyonir_request, dec_func)

    # async def dec_wrapper(star_req):
    #     from pyonir.core import PyonirRequest
    #     # Resolve page file route
    #     pyonir_request = PyonirRequest(star_req)
    #     if pyonir_request.is_static: return serve_static(Site, pyonir_request)
    #     await pyonir_request.process_request_data()
    #
    #     # Update template global
    #     Site.TemplateEnvironment.globals['request'] = pyonir_request
    #     # pyonir_request.is_api = pyonir_request.parts and pyonir_request.parts[0] == Site.API_DIRNAME
    #
    #     # Query File system for Page from request
    #     app_ctx, req_file = pyonir_request.resolve_request_to_file(star_req.url.path, Site)
    #     pyonir_request.file = req_file
    #     pyonir_request.app_ctx_name = app_ctx.name
    #
    #     # Preprocess routes or resolver endpoint from file
    #     await req_file.process_route(pyonir_request, app_ctx)
    #     await req_file.process_resolver(pyonir_request)
    #     route_func = dec_func if not req_file.resolver else req_file.resolver
    #
    #     # Get router endpoint from map
    #     if callable(route_func):
    #         is_async = inspect.iscoroutinefunction(route_func)
    #
    #         default_args = dict(typing.get_type_hints(route_func))
    #         default_args.update(**pyonir_request.path_params)
    #         default_args.update(**pyonir_request.query_params.__dict__)
    #         default_args.update(**pyonir_request.form)
    #         args = cls_mapper(default_args, route_func, from_request=pyonir_request)
    #         pyonir_request.router_args = args
    #
    #         # Check resolver route security
    #
    #         # Resolve route decorator methods
    #         pyonir_request.server_response = await route_func(**args) if is_async else route_func(**args)
    #
    #     else:
    #         pyonir_request.server_response = req_file.resolver or req_file.route
    #     # Execute plugins hooks initial request
    #     pyonir_request.derive_status_code(Site.server.url_map.get(route_func.__name__) and not default_system_router)
    #     await Site.run_async_plugins(PyonirHooks.ON_REQUEST, pyonir_request)
    #     # Finalize response output
    #     if pyonir_request.path not in Site.server.sse_routes + Site.server.ws_routes:
    #         pyonir_request.server_response = await req_file.process_response(pyonir_request)
    #
    #     if pyonir_request.redirect_to:
    #         return Site.server.serve_redirect(pyonir_request.redirect_to)
    #
    #     return build_response(pyonir_request)

    dec_wrapper.__name__ = dec_func.__name__
    dec_wrapper.__doc__ = dec_func.__doc__
    Site.server.add_route(path, dec_wrapper, methods=methods)


async def create_response(pyonir_request: PyonirRequest, dec_func: callable):
    from pyonir import Site
    from pyonir.models.auth import Auth

    star_req = pyonir_request.server_request
    Site.server.request = pyonir_request
    default_system_router = dec_func.__name__ == 'pyonir_index'
    # Serve static urls
    if pyonir_request.is_static:
        return serve_static(Site, pyonir_request)

    # Preprocess request data
    await pyonir_request.process_request_data()
    pyonir_request.auth = Auth(pyonir_request, Site)

    # Update template globals
    Site.TemplateEnvironment.globals['request'] = pyonir_request

    # Process file associated with request
    app_ctx, req_file = pyonir_request.resolve_request_to_file(star_req.url.path, Site)
    pyonir_request.file = req_file
    pyonir_request.app_ctx_name = app_ctx.name

    # Preprocess routes or resolver endpoint from file
    req_file = await Site.virtual_router(pyonir_request)
    await req_file.process_resolver(pyonir_request)

    route_func = dec_func if not callable(req_file.resolver) else req_file.resolver

    # Check resolver route security
    security = pyonir_request.auth.security.check(pyonir_request.auth)
    if security and not security.accepted:
        return Site.server.serve_redirect(security.redirect_to or '/')

    # Get router endpoint from map
    if callable(route_func):
        is_async = inspect.iscoroutinefunction(route_func)

        default_args = dict(typing.get_type_hints(route_func))
        default_args.update(**pyonir_request.path_params)
        default_args.update(**pyonir_request.query_params.__dict__)
        default_args.update(**pyonir_request.form)
        args = cls_mapper(default_args, route_func, from_request=pyonir_request)
        pyonir_request.router_args = args

        # Resolve route decorator methods
        pyonir_request.server_response = await route_func(**args) if is_async else route_func(**args)

    else:
        pyonir_request.server_response = req_file.resolver or req_file.data

    # Perform redirects
    if pyonir_request.redirect_to:
        return Site.server.serve_redirect(pyonir_request.redirect_to)

    # Derive status code
    pyonir_request.derive_status_code(Site.server.url_map.get(route_func.__name__ if route_func else '') and not default_system_router)

    # Execute plugins hooks initial request
    await Site.run_async_plugins(PyonirHooks.ON_REQUEST, pyonir_request)
    # await Site.run_async_hooks(PyonirHooks.ON_REQUEST, pyonir_request)

    # Finalize response output
    is_auth_res = isinstance(pyonir_request.server_response, PyonirRestResponse)
    pyonir_response = pyonir_request.server_response if is_auth_res else PyonirRestResponse(status_code=pyonir_request.status_code)
    if not is_auth_res:
        if pyonir_request.type == JSON_RES:
            pyonir_response.set_json(pyonir_request.server_response or pyonir_request.file.data)
        else:
            pyonir_response.set_html(req_file.output_html(pyonir_request))

    # Set headers
    pyonir_response.set_media(pyonir_request.type)
    pyonir_response.set_header('Server', 'Pyonir Web Framework')
    pyonir_response.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    pyonir_response.set_header("Pragma", "no-cache")
    pyonir_response.set_header("Expires", "0")

    # Generate response
    pyonir_response.set_server_response()
    return pyonir_response.render()

def get_route_ctx(app: PyonirApp, path_str: str) -> tuple:
    """Gets the routing context from web request"""
    path_str = path_str.replace('api/', '')
    req_trgt = path_str.split('/').pop()
    res = None
    for ctxp in app.request_paths:
        app_ctx, route, pths, prunes = ctxp
        ishome = route == path_str
        prunes = [p for p in prunes if p != req_trgt or ishome]
        if not path_str.startswith(route.lstrip('/')): continue
        if ishome: route = ''
        res = (app if isinstance(app_ctx, str) else app_ctx), route, pths, prunes
    return res


def resolve_path_to_file(path_str: str, app: PyonirApp, skip_vanity: bool = False) -> typing.Tuple[PyonirApp, str]:
    from pyonir import Site
    path_result = None
    is_home = path_str == '/'
    if not is_home and hasattr(app, 'available_plugins'):
        for plg in app.available_plugins:
            if not hasattr(plg, 'request_paths') or not plg.endpoint: continue
            plg, path_result = resolve_path_to_file(path_str, plg)
            if path_result: break
        if path_result: return plg, path_result

    ctx_route, ctx_paths = app.request_paths
    check_wildcard = ctx_route != '/' and (
                path_str.startswith(ctx_route) or path_str.replace('/api', '').startswith(ctx_route))
    # ctx_route = ctx_route.replace('/*','')
    ctx_slug = ctx_route[1:]
    path_slug = path_str[1:]
    reqst_path = [p for p in path_slug.split('/') if p not in ('api', ctx_slug)]
    if path_str.startswith('/api'): path_str = path_str.replace('/api', '')
    if not is_home and not path_str.startswith(ctx_route): return app, None

    for rootp in ctx_paths:
        is_cat = os.path.join(rootp, *reqst_path, 'index.md')
        is_page = os.path.join(rootp, *reqst_path) + Site.EXTENSIONS['file']
        for pp in (is_cat, is_page):
            if not os.path.exists(pp): continue
            path_result = pp
            break
        if path_result: break
    if path_result is None and check_wildcard:
        dynamic_paths = [os.path.join(app.pages_dirpath, *reqst_path[:i], "index.md") for i in
                         range(len(reqst_path), -1, -1) if
                         os.path.exists(os.path.join(app.pages_dirpath, *reqst_path[:i], "index.md"))]
        path_result = dynamic_paths[0]
    return app, path_result


def generate_nginx_conf(app: PyonirApp) -> bool:
    """Generates a NGINX conf file based on App configurations"""

    nginx_conf = app.TemplateEnvironment.get_template("nginx.jinja.conf") \
        .render(
        app_name=app.name,
        app_name_id=app.name.replace(' ', '_').lower(),
        domain=app.domain,
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
        custom_nginx_locations=get_attr(app._env, 'nginx_locations')
    )

    return create_file(app.nginx_config_filepath, nginx_conf, False)


def start_uvicorn_server(app: PyonirApp, endpoints: PyonirRouters = None):
    """Starts the webserver"""
    import uvicorn, sys

    # """Uvicorn web server configurations"""
    uvicorn_options = {
        "port": app.port,
        "host": app.host
    }
    if app.is_secure:
        uvicorn_options["ssl_keyfile"] = app.ssl_key_file
        uvicorn_options["ssl_certfile"] = app.ssl_cert_file
    if not app.is_dev:
        uvicorn_options['uds'] = app.unix_socket_filepath

    # Initialize routers
    if endpoints: init_app_endpoints(endpoints)
    init_pyonir_endpoints(app)
    print(f"/************** ASGI APP SERVER RUNNING on {'http' if app.is_dev else 'sock'} ****************/")
    print(f"\
    \n\t- App env: {'DEV' if app.is_dev else 'PROD'}\
    \n\t- App name: {app.name}\
    \n\t- App domain: {app.domain}\
    \n\t- App host: {app.host}\
    \n\t- App port: {app.port}\
    \n\t- App sock: {app.unix_socket_filepath}\
    \n\t- App ssl_key: {app.ssl_key_file}\
    \n\t- App ssl_cert: {app.ssl_cert_file}\
    \n\t- App Server: Uvicorn \
    \n\t- NGINX config: {app.nginx_config_filepath} \
    \n\t- System Version: {sys.version_info}")
    app.run_plugins(PyonirHooks.AFTER_INIT)
    # app.run_hooks(PyonirHooks.AFTER_INIT)
    uvicorn.run(app.server, **uvicorn_options)
