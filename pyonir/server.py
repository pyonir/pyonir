import asyncio
import os, typing, json, inspect

from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from pyonir import ASSETS_ROUTE, UPLOADS_ROUTE, PAGINATE_LIMIT
from pyonir.parser import ParselyPage
from pyonir.types import IApp, PyonirRequest, PyonirServer, PyonirHooks
from pyonir.utilities import Collection, create_file, get_attr

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
    event = request.query_params.get('event')
    retry = request.query_params.get('retry', 1000)
    close_id = request.query_params.get('close')
    interval = 1  # time between events
    client_id = request.query_params.get('id', request.headers.get('user-agent') + f"{generate_id()}")
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


def pyonir_file_delete(request: PyonirRequest):
    """Deletes a file located in the uploads directory"""
    from pyonir import Site
    from pyonir.parser import ParselyMedia
    redirect = request.query_params.get('redirect') + '?success=true'
    doc = os.path.join(Site.contents_dirpath, request.query_params.get('file'))
    img = ParselyMedia(doc, Site.files_ctx)
    if img.file_exists:
        os.remove(doc)
        for _, timg in img.thumbnails.items():
            os.remove(timg.abspath)
    return {"redirect": redirect}


async def pyonir_file_upload(request: PyonirRequest):
    """File upload handler"""
    from pyonir.parser import ParselyMedia
    from pyonir import Site
    folder_name = request.form.get('foldername')
    uploads = []
    for doc in request.files:
        parselyMedia = await ParselyMedia.save_upload(doc, os.path.join(Site.uploads_dirpath, folder_name))
        parselyMedia.resize()
        uploads.append(parselyMedia.data)
    return uploads


def pyonir_index(request: PyonirRequest):
    """Catch all routes for all web request"""
    return f"Pyonir default controller."


async def apply_plugin_resolvers(page: ParselyPage, request: PyonirRequest):
    """Resolves api definitions for plugins"""
    from pyonir import Site, utilities, CONTROLLERS_DIRNAME
    resolver_path = page.data.get('@resolver', {}).get(request.method)
    if not resolver_path: return
    pkg, meth_name = resolver_path.split('.', 1)
    if pkg == 'pyonir':
        resolver = get_attr(Site.server.resolvers, meth_name)
    else:
        pkg_path = os.path.join(Site.backend_dirpath, CONTROLLERS_DIRNAME, pkg, '__init__.py')
        module, resolver = utilities.get_module(pkg_path, meth_name)

    if not resolver: return
    is_async = inspect.iscoroutinefunction(resolver)
    rdata = await resolver(**request.args) if is_async else resolver(**request.args) if callable(resolver) else resolver
    return rdata if inspect.iscoroutine(rdata) or inspect.isasyncgen(rdata) else page.output_json(rdata)


async def process_request_data(request: PyonirRequest):
    """Get form data and file contents from request"""
    from pyonir import Site
    # from pyonir.parser import ParselyMedia
    from .utilities import secure_upload_filename
    try:
        try:
            ajson = await request.server_request.json()
            if isinstance(ajson, str): ajson = json.loads(ajson)
            request.form.update(ajson)
        except Exception as ee:
            # multipart/form-data
            form = await request.server_request.form()
            files = []
            for name, content in form.multi_items():
                if name == 'files':
                    # filedata = await content.read()
                    mediaFile = (secure_upload_filename(content.filename), content, Site.uploads_dirpath)
                    request.files.append(mediaFile)
                else:
                    request.form[name] = content
    except Exception as e:
        raise


def setup_starlette_server(iapp: IApp) -> PyonirServer:
    """Setup Starlette web server"""

    from starlette_wtf import CSRFProtectMiddleware
    from starlette_session import SessionMiddleware
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    from starlette.middleware.gzip import GZipMiddleware
    from starlette.responses import Response, StreamingResponse
    # from starlette.requests import Request
    from starlette.routing import Router, Route

    def render_response(value, media_type):
        if media_type == EVENT_RES:
            return StreamingResponse(content=value, media_type=media_type)
        return Response(content=value, media_type=media_type)

    def redirect(url, code=302):
        from starlette.responses import RedirectResponse
        res = RedirectResponse(url=url.strip(), status_code=code)
        return res

    def get_staticroute(assets_dir):
        from starlette.staticfiles import StaticFiles
        return StaticFiles(directory=assets_dir)

    allowed_hosts = ['localhost', '*.localhost']
    secret_sauce = getattr(iapp.configs.app, 'secret_sauce', iapp.SECRET_SAUCE)
    session_key = getattr(iapp.configs.app, 'session_key', iapp.SESSION_KEY)
    star_app = PyonirServer()  # inherits from Starlette
    star_app.add_middleware(TrustedHostMiddleware)
    # star_app.add_middleware(GZipMiddleware, minimum_size=500)
    star_app.add_middleware(SessionMiddleware,
                            https_only=True,
                            secret_key=secret_sauce,
                            cookie_name=session_key
                            )
    star_app.add_middleware(CSRFProtectMiddleware, csrf_secret=secret_sauce)

    # Interface properties required for pyonir to process web request
    setattr(star_app, 'response_renderer', render_response)
    setattr(star_app, 'serve_redirect', redirect)
    setattr(star_app, 'create_endpoint', Router)
    setattr(star_app, 'create_route', Route)
    setattr(star_app, 'serve_static', get_staticroute)

    return star_app


def url_for(name, attr='path'):
    """returns application route value based on named class function name"""
    from pyonir import Site
    if not Site: return None
    urlmap = Site.server.url_map
    return urlmap.get(name, {}).get(attr)


def init_endpoints(endpoints: 'Endpoints'):
    for endpoint, routes in endpoints:
        for path, func, methods, *opts in routes:
            args = opts[0] if opts else {}
            kwargs = {'models': {}}
            for k, v in args.items():
                if k in ('ws', 'sse', 'static_path'):
                    kwargs[k] = v
                kwargs['models'].update({k: v})
            r = add_route(f'{endpoint}{path}', func, methods, **kwargs)
            pass


def init_parsely_endpoints(app: IApp):
    for r, static_abspath in ((ASSETS_ROUTE, app.theme_static_dirpath), (UPLOADS_ROUTE, app.uploads_dirpath)):
        if not os.path.exists(static_abspath): continue
        add_route(r, None, static_path=static_abspath)
    add_route("/syssse", pyonir_sse_handler, sse=True)
    add_route("/sysws", pyonir_ws_handler, ws=True)
    add_route("/", pyonir_index, methods='*')
    add_route("/{path:path}", pyonir_index, methods='*')


def get_params(url):
    import urllib
    args = {params.split('=')[0]: urllib.parse.unquote(params.split("=").pop()) for params in
            url.split('&') if params != ''}
    if args.get('model'): del args['model']
    return args


def process_sse(data: dict) -> str:
    """Formats a string and an event name in order to follow the event stream convention.
    'event: Jackson 5\\ndata: {"abc": 123}\\n\\n'
    """
    sse_payload = ""
    for key, val in data.items():
        val = json.dumps(val) if key == 'data' else val
        sse_payload += f"{key}: {val}\n"
    return sse_payload + "\n"


def serve_favicon(app):
    from starlette.responses import FileResponse
    return FileResponse(os.path.join(app.theme_static_dirpath,'favicon.ico'), 200)


def add_route(path: str,
              dec_func: typing.Callable,
              methods=None,
              models: dict = None,
              auth: bool = None,
              ws: bool = None,
              sse: bool = None,
              static_path: str = None) -> typing.Callable | None:
    """Route decorator"""
    from pyonir import Site

    def is_async(func):
        return inspect.isasyncgenfunction(func) or inspect.iscoroutinefunction(func)

    is_async = inspect.iscoroutinefunction(dec_func) if dec_func else False
    is_asyncgen = inspect.isasyncgenfunction(dec_func) if dec_func else False
    list_of_args = list(inspect.signature(dec_func).parameters.keys()) if dec_func else None
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
    is_pyonir_default = dec_func.__name__ == 'pyonir_index'
    req_models = Site.server.url_map.get(route_name, {}).get('models') or {}
    if models:
        for req_param, req_model in models.items():
            req_models[req_param] = req_model.__name__
            if hasattr(Site.server, 'models'):
                Site.server.models.update({req_model.__name__, req_model})
            else:
                Site.server.models = {req_model.__name__, req_model}
    new_route = {
        "doc": docs,
        "endpoint": endpoint_route,
        "route": path,  # has regex pattern
        "path": route_path,
        "methods": methods,
        "models": models or req_models,
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
        from pyonir.parser import ParselyPage
        if star_req.url.path == '/favicon.ico': return serve_favicon(Site)
        # Resolve page file route
        app_ctx, req_filepath = resolve_path_to_file(star_req.url.path)
        pyonir_request = build_request(star_req)
        await process_request_data(pyonir_request)
        if pyonir_request.type == TEXT_RES and not os.path.exists(app_ctx.frontend_dirpath):
            pyonir_request.type = JSON_RES
        route_models = app_ctx.server.url_map.get(dec_func.__name__, {}).get('models')

        args = pyonir_request.request_model(list_of_args, route_models)
        pyonir_request.args = args

        # Update template global
        app_ctx.TemplateParser.globals['request'] = pyonir_request

        # Resolve page from request
        req_file = ParselyPage(req_filepath, app_ctx.files_ctx)
        pyonir_request.file = req_file
        # Resolve route decorator methods
        pyonir_request.server_response = await dec_func(**args) if is_async else dec_func(**args)
        await app_ctx.run_plugins(PyonirHooks.ON_REQUEST, pyonir_request)
        # Finalize response output
        pyonir_request.status_code = pyonir_request.derive_status_code(is_pyonir_default)
        if pyonir_request.path not in app_ctx.server.sse_routes + app_ctx.server.ws_routes:
            pyonir_request.server_response = await req_file.process_response(pyonir_request)

        if pyonir_request.redirect:
            return Site.server.serve_redirect(pyonir_request.redirect, 303)

        return build_response(pyonir_request)

    Site.server.add_route(path, dec_wrapper, methods=methods)


def build_request(TRequest, code: int = 444) -> PyonirRequest:
    """Transforms generic server request type into Pyonir request object"""
    from pyonir import Site
    raw_path = TRequest.url.path
    method = TRequest.method
    path = TRequest.url.path
    path_params = TRequest.path_params
    url = f"{path}"
    slug = path.lstrip('/').rstrip('/')
    query_params = get_params(TRequest.url.query)
    parts = slug.split('/') if slug else []
    limit = Collection.get_attr(query_params, 'limit', PAGINATE_LIMIT)
    model = query_params.get('model')
    is_home = (path == '')
    form = {}
    files = []
    ip = TRequest.client.host
    host = str(TRequest.base_url).rstrip('/')
    protocol = TRequest.scope.get('type') + "://"
    headers = PyonirRequest.process_header(TRequest.headers)
    browser = headers.get('user-agent', '').split('/').pop(0) if headers else "UnknownAgent"
    if slug.startswith('api'): headers['accept'] = JSON_RES
    res_type = headers.get('accept')
    status_code = code
    auth = None
    use_endpoints = TRequest.url.path in Site.server.endpoints
    args = {}
    return PyonirRequest(raw_path, method, path, path_params, url, slug, query_params, parts, limit, model, is_home,
                         form, files, ip, host, protocol, headers, args, browser, res_type, status_code, auth,
                         use_endpoints=use_endpoints,
                         server_request=TRequest, file=None)


def build_response(request: PyonirRequest):
    """Create web response for web server"""
    from datetime import datetime, timedelta
    from pyonir import Site
    try:
        ishtml = request.type == TEXT_RES
        expires = datetime.utcnow() + timedelta(days=7)
        expires = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
        response = Site.server.response_renderer(request.server_response, media_type=request.type)
        if ishtml: response.headers['Expires'] = expires
        response.headers['Cache-Control'] = "no-cache" if not ishtml else "public, max-age=0"
        response.headers['Server'] = "Pyonir Web Framework"
        response.status_code = request.status_code
        return response
    except Exception as e:
        raise


def get_route_ctx(app: IApp, path_str: str) -> tuple:
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


def resolve_path_to_file(path_str: str, skip_vanity: bool = False) -> typing.Tuple[IApp, str]:
    """Returns application name and requested file path based on web path"""
    from pyonir import Site, EXTENSIONS
    app_ctx, ctx_route, ctx_paths, prunes = get_route_ctx(Site, path_str)
    reqst_path = [p for p in path_str.split('/') if p not in prunes]
    path_result = None
    for p in ctx_paths:
        is_cat = os.path.join(p, *reqst_path, 'index.md')
        is_page = os.path.join(p, *reqst_path) + EXTENSIONS['file']
        for pp in (is_cat, is_page):
            if not os.path.exists(pp): continue
            path_result = pp
            break
        if path_result: break

    # if path_result is None and not skip_vanity:
    #     path_result = Request.vanity_url('/'+path_str)
    return app_ctx, path_result


def generate_nginx_conf(app: IApp):
    """Generates a NGINX conf file based on App configurations"""
    nginxconf = app.TemplateParser.get_template("nginx.jinja.conf") \
        .render(
        app_name=app.configs.app.name,
        app_name_id=app.configs.app.name.replace(' ', '_').lower(),
        domain=app.domain,
        is_secure=app.is_secure,
        serve_static=True,
        site_dirpath=app.app_dirpath,
        site_logs_dirpath=app.site_logs_dirpath,
        app_socket_filepath=app.app_socket_filepath,
        site_assets_route='/public',
        site_theme_assets_dirpath=app.theme_assets_dirpath,
        site_uploads_route='/uploads',
        site_uploads_dirpath=app.uploads_dirpath,
        site_ssg_dirpath=app.ssg_dirpath,
        custom_nginx_locations=Collection.get_attr(app.configs, 'nginx_locations')
    )

    create_file(app.app_nginx_conf_filepath, nginxconf, False)


def start_uvicorn_server(app: IApp, endpoints: 'Endpoints'):
    """Starts the webserver"""
    import uvicorn

    # """Uvicorn web server configurations"""
    from pyonir import PYONIR_SSL_KEY, PYONIR_SSL_CRT
    uvicorn_options = {
        "port": app.port,
        "host": app.host
    }
    if app.is_secure:
        uvicorn_options["ssl_keyfile"] = PYONIR_SSL_KEY
        uvicorn_options["ssl_certfile"] = PYONIR_SSL_CRT
    if not app.is_dev:
        uvicorn_options['uds'] = app.app_socket_filename

    # Initialize routers
    init_endpoints(endpoints)
    init_parsely_endpoints(app)
    # init_controllers(self)
    print(f"/************** ASGI APP SERVER RUNNING on {'http' if app.is_dev else 'sock'} ****************/")
    print(f"\
    \n\t- Sys User: {app.SYS_USER}\
    \n\t- App Version: {app.VERSION}\
    \n\t- App env: {'DEV' if app.is_dev else 'PROD'}\
    \n\t- App name: {app.name}\
    \n\t- App domain: {app.origin}\
    \n\t- App host: {app.host}\
    \n\t- App port: {app.port}\
    \n\t- App sock: {app.app_socket_filepath}\
    \n\t- App Server: Uvicorn \
    \n\t- NGINX config: {app.app_nginx_conf_filepath} \
    \n\t- System Version: {app.SYS_VERSION}")
    uvicorn.run(app.server, **uvicorn_options)
