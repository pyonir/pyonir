from __future__ import annotations
import typing, os

from jinja2 import Environment
from starlette.requests import Request as StarletteRequest

from pyonir.pyonir_types import PyonirServer, Theme, PyonirHooks, Parsely, ParselyPagination, AppRequestPaths, AppCtx, \
    PyonirRouters, RoutePath

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
    """Interface for immutable dataclass models with CRUD and session support."""
    _validation_errors: list[str] = []
    _deleted = False

    def validate(self):
        """validates a given property with accessible validation method"""
        for name, value in self.__dict__.items():
            if name.startswith('_'): continue
            validator_fn = getattr(self, f'validate_{name}', None)
            if validator_fn: validator_fn()
        pass

    def __post_init__(self):
        # self._validation_errors = []
        self.validate()

    # --- Database helpers ---
    @classmethod
    def create(cls: Type[T], **data) -> T:
        """Create and persist a new record in DB."""
        instance = cls(**data)  # Validate via __post_init__ in dataclass
        # orm_model = instance._to_orm()
        # session.add(orm_model)
        # session.commit()
        # session.refresh(orm_model)
        return instance

    # @classmethod
    # def get_from_db(cls: Type[T], session: Session, obj_id: int) -> Optional[T]:
    #     """Fetch a record from DB by ID."""
    #     orm_model = session.query(cls._orm_model()).get(obj_id)
    #     if not orm_model:
    #         return None
    #     return cls._from_orm(orm_model)

    @classmethod
    def from_session(cls: Type[T], session_data: dict) -> T:
        return cls(**session_data)

    # --- ORM binding ---
    @classmethod
    def _orm_model(cls):
        """Should be overridden to return the ORM model class."""
        raise NotImplementedError

    @classmethod
    def _from_orm(cls: Type[T], orm_obj) -> T:
        """Should be overridden to map ORM object to dataclass."""
        raise NotImplementedError

    def patch(self: T, **changes) -> T:
        """Return a new instance with updated fields (no DB)."""
        return replace(self, **changes)

    def update(self: T, session: Session, **changes) -> T:
        """Update a record in DB and return a new immutable instance."""
        if not getattr(self, "id", None):
            raise ValueError("Cannot update without ID")

        orm_model = session.query(self._orm_model()).get(self.id)
        if not orm_model:
            raise ValueError(f"{self.__class__.__name__} not found")

        for field_name, value in changes.items():
            setattr(orm_model, field_name, value)

        session.commit()
        session.refresh(orm_model)
        return self.__class__._from_orm(orm_model)

    def delete(self: T) -> T:
        """Delete record from DB (soft-delete can be overridden)."""
        # if not getattr(self, "id", None):
        #     raise ValueError("Cannot delete without ID")
        #
        # orm_model = session.query(self._orm_model()).get(self.id)
        # if not orm_model:
        #     raise ValueError(f"{self.__class__.__name__} not found")
        #
        # session.delete(orm_model)
        # session.commit()

        return replace(self, _deleted=True)

    # --- Session helpers ---
    def to_session(self) -> dict:
        return asdict(self)

    def _to_orm(self):
        """Should be overridden to map dataclass to ORM object."""
        raise NotImplementedError

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
            items = list(items)
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
    def query(cls, query_path: str,
             app_ctx: PyonirApp = None,
             data_model: any = None,
             include_only: str = None,
             exclude_dirs: list[str] = None,
             exclude_file: list[str] = None,
             force_all: bool = True,
              sort_key: str = None):
        """queries the file system for list of files"""
        from pyonir.utilities import get_all_files_from_dir
        gen_data = get_all_files_from_dir(query_path, app_ctx=app_ctx, entry_type=data_model, include_only=include_only,
                                          exclude_dirs=exclude_dirs, exclude_file=exclude_file, force_all=force_all)
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
        request: PyonirRequest = Site.TemplateEnvironment.globals['request']
        if not hasattr(request, 'limit'): return None
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

    def __init__(self, server_request: StarletteRequest):
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
        self.is_home = (self.path == '')
        self.is_api = False
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
        self.app_ctx_name: str = ''

    @property
    def redirect(self):
        return self.form.get('redirect', self.form.get('redirect_to'))

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

    def derive_status_code(self, is_router_method: bool):
        """Create status code for web request based on a file's availability, status_code property"""
        from pyonir.parser import ParselyFileStatus

        code = 404
        if self.file.status in (ParselyFileStatus.PROTECTED, ParselyFileStatus.FORBIDDEN):
            self.file.data = {'template': '40x.html', 'content': f'Unauthorized access to this resource.', 'url': self.url, 'slug': self.slug}
            code = 401
        elif self.file.file_status == ParselyFileStatus.PUBLIC or is_router_method:
            code = 200
        self.status_code = code #200 if self.file.file_exists or is_router_method else 404

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
        skip_vanity: bool = False
    ) -> typing.Tuple[PyonirApp, typing.Optional[Parsely]]:
        """Resolve a request URL to a file on disk, checking plugin paths first, then the main app."""
        from pyonir import Site
        from pyonir.parser import Parsely
        is_home = path_str == '/'
        app_has_plugins = hasattr(app, 'plugins_activated')
        ctx_route, ctx_paths = app.request_paths or ('', [])
        ctx_route = ctx_route or ''
        ctx_slug = ctx_route[1:]
        path_slug = path_str[1:]
        app_scope, *path_segments = path_slug.split('/')
        is_api_request = (len(path_segments) and path_segments[0] == app.API_DIRNAME) or path_str.startswith(app.API_ROUTE)
        # if is_api_request and app_has_plugins and any(plg.module == app_scope for plg in app.plugins_activated):
        #     pass

        # First, check plugins if available and not home
        if not is_home and app_has_plugins:
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
        for root_path in ctx_paths:
            if not is_api_request and root_path.endswith(app.API_DIRNAME): continue
            category_index = os.path.join(root_path, *request_segments, 'index.md')
            single_page = os.path.join(root_path, *request_segments) + Site.EXTENSIONS['file']
            single_protected_page = os.path.join(root_path, *protected_segment) + Site.EXTENSIONS['file']

            for candidate in (category_index, single_page, single_protected_page):
                if os.path.exists(candidate):
                    return app, Parsely(candidate, app.app_ctx)

        # Fallback: check for .routes.md inside pages_dirpath
        if hasattr(app, 'pages_dirpath'):
            fallback_route = os.path.join(app.pages_dirpath, '.routes.md')
            if os.path.exists(fallback_route):
                return app, Parsely(fallback_route, app.app_ctx)

        return app, Parsely('404_ERROR', app.app_ctx)

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
    SSG_IN_PROGRESS: bool = False

    # Contents sub directory default names
    UPLOADS_THUMBNAIL_DIRNAME: str = "thumbnails" # resized image directory name
    UPLOADS_DIRNAME: str = "uploads" # url name for serving uploaded assets
    ASSETS_DIRNAME: str = "public" # url name for serving static assets css and js
    API_DIRNAME: str = "api" # directory for serving API endpoints and resolver routes
    PAGES_DIRNAME: str = "pages" # directory for serving HTML endpoints with file based routing
    CONFIG_FILENAME: str = "app" # main application configuration file name within contents/configs directory

    # Application paths
    app_dirpath: str = '' # directory path to site's main.py file
    app_name: str = '' # directory name for application main.py file
    app_account_name: str = '' # parent directory from the site's root directory (used for multi-site configurations)

    # Application routes
    API_ROUTE = f"/{API_DIRNAME}"  # Api base path for accessing pages as JSON
    ASSETS_ROUTE = f"/{ASSETS_DIRNAME}"  # serves static assets from configured theme
    UPLOADS_ROUTE = f"/{UPLOADS_DIRNAME}"  # Upload base path to access resources within upload directory
    TemplateEnvironment: TemplateEnvironment = None # Template environment configurations
    routing_paths: list[RoutePath] | None = []

    @property
    def request_paths(self) -> AppRequestPaths:
        return self.endpoint, self.routing_paths

    @property
    def module(self):
        """The application module directory name"""
        return self.__module__.split('.').pop()

    @property
    def app_ctx(self) -> AppCtx: pass

    @staticmethod
    def generate_resolvers(cls: callable, output_dirpath: str, namespace: str):
        """Automatically generate api endpoints from service class."""
        import textwrap
        from pyonir.utilities import create_file

        resolver_template = textwrap.dedent("""\
        @resolvers:
            GET.call: {call_path}
        ===
        {docs}
        """).strip()
        name = cls.__class__.__name__
        endpoint_meths = [a for a in dir(cls) if not a.startswith('_') and hasattr(getattr(cls, a), '__call__')]
        formatted_cls_name = name[0].lower()+name[1:]
        print(f"Generating {name} API endpoint definitions for:")
        for meth_name in endpoint_meths:
            file_path = os.path.join(output_dirpath, meth_name+'.md')
            if os.path.exists(file_path): continue
            meth: callable = getattr(cls, meth_name)
            namespace_instance_path = f"{namespace}.{formatted_cls_name}.{meth_name}"
            docs = textwrap.dedent(meth.__doc__).strip() if meth.__doc__ else ''
            m_temp = resolver_template.format(call_path=namespace_instance_path, docs=docs)
            create_file(file_path, m_temp)
            print(f"\t{meth_name} at {file_path}")

    def parse_file(self, file_path: str) -> Parsely:
        from pyonir.parser import Parsely
        return Parsely(file_path, app_ctx=self.app_ctx)

    def generate_static_website(self):
        """Generates Static website into the specified static_site_dirpath"""
        import time
        from pyonir.server import generate_nginx_conf
        from pyonir import utilities

        self.SSG_IN_PROGRESS = True
        count = 0
        print(f"{utilities.PrntColrs.OKBLUE}1. Coping Assets")
        try:
            self.run([])
            site_map_path = os.path.join(self.ssg_dirpath, 'sitemap.xml')
            # generate_nginx_conf(self)
            print(f"{utilities.PrntColrs.OKCYAN}3. Generating Static Pages")

            self.TemplateEnvironment.globals['is_ssg'] = True
            start_time = time.perf_counter()

            all_pages = utilities.get_all_files_from_dir(self.pages_dirpath, app_ctx=self.app_ctx)
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

            # Copy pyonir static assets for js and css vendor libraries into ssg directory
            # utilities.copy_assets(PYONIR_STATIC_DIRPATH, os.path.join(self.ssg_dirpath, PYONIR_STATIC_ROUTE.lstrip('/')))

            # Copy theme static css, js files into ssg directory
            utilities.copy_assets(self.TemplateEnvironment.themes.active_theme.static_dirpath, os.path.join(self.ssg_dirpath, self.ASSETS_DIRNAME))

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

    def __init__(self, app_entrypoint: str):
        from pyonir.utilities import generate_id, get_attr, process_contents
        from pyonir import __version__
        from pyonir.parser import parse_markdown
        self.SOFTWARE_VERSION = __version__
        self.get_attr = get_attr
        self.app_entrypoint: str = app_entrypoint # application main.py file or the initializing file
        self.app_dirpath: str = os.path.dirname(app_entrypoint) # application main.py file or the initializing file
        self.name: str = os.path.basename(self.app_dirpath) # web url to serve application pages
        self.SECRET_SAUCE = generate_id()
        self.SESSION_KEY = f"pyonir_{self.app_name}"
        self.configs = None
        self.routing_paths = [self.pages_dirpath, self.api_dirpath]
        self.public_assets_dirpath = os.path.join(self.frontend_dirpath, 'static')
        self.Parsely_Filters = {'jinja': self.parse_jinja, 'pyformat': self.parse_pyformat,
                                 'md': parse_markdown}

    @property
    def nginx_config_filepath(self):
        return os.path.join(self.app_dirpath, self.name + '.conf')

    @property
    def unix_socket_filepath(self):
        """WSGI socket file reference"""
        return os.path.join(self.app_dirpath, self.name+'.sock')

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
        """Directory path for site's theme folders"""
        return os.path.join(self.app_dirpath, self.CONTENTS_DIRNAME)

    @property
    def frontend_dirpath(self) -> str:
        """Directory path for site's theme folders"""
        return os.path.join(self.app_dirpath, self.FRONTEND_DIRNAME)

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
    def app_ctx(self) -> AppCtx:
        return self.name, self.endpoint, self.contents_dirpath, self.ssg_dirpath

    @property
    def env(self): return os.getenv('APPENV')

    @property
    def is_dev(self): return self.env == DEV_ENV

    @property
    def host(self): return self.get_attr(self.configs, 'app.host', '0.0.0.0') #if self.configs else '0.0.0.0'

    @property
    def port(self):
        return self.get_attr(self.configs, 'app.port', 5000) #if self.configs else 5000

    @property
    def protocol(self):return 'https' if self.is_secure else 'http'

    @property
    def is_secure(self):return self.get_attr(self.configs, 'app.use_ssl', False) #if self.configs else None

    @property
    def domain(self): return self.get_attr(self.configs, 'app.domain', self.host) # if self.configs else self.host

    def load_plugin(self, plugin: callable | list[callable]):
        """Make the plugin known to the pyonir application"""
        if isinstance(plugin, list):
            for plugin in plugin:
                self.load_plugin(plugin)
        else:
            plg_pkg_name = plugin.__module__.split('.').pop()
            self.plugins_installed[plg_pkg_name] = plugin

    # def _load_plugins(self):
    #     """Loads the plugin initializing object into runtime"""
    #     self.plugins_installed = load_modules_from(self.plugins_dirpath, only_packages=True)
    #     pass

    def _activate_plugins(self):
        """Active plugins enabled based on configurations"""
        is_configured = hasattr(self.configs, 'app') and hasattr(self.configs.app, 'enabled_plugins')
        for plg_id, plugin in self.plugins_installed.items():
            if is_configured and plg_id not in self.configs.app.enabled_plugins: continue
            self.plugins_activated.add(plugin(self))

    def install_sys_plugins(self):
        """Install pyonir plugins"""
        from pyonir.libs.plugins.navigation import Navigation
        self.plugins_installed['pyonir_navigation'] = Navigation

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
        if not self.TemplateEnvironment: return string
        try:
            return self.TemplateEnvironment.from_string(string).render(configs=self.configs, **context)
        except Exception as e:
            print(str(e))
            return string
            # raise

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


    def setup_configs(self):
        """Setup site configurations and template environment"""
        from pyonir.utilities import process_contents, load_env
        self.configs = process_contents(os.path.join(self.contents_dirpath, self.CONFIGS_DIRNAME), self.app_ctx)
        envopts = load_env(os.path.join(self.app_dirpath, '.env'))
        setattr(self.configs, 'env', envopts)
        self.setup_templates()

    def run(self, routes: PyonirRouters, plugins: list[PyonirPlugin] =None):
        """Runs the Uvicorn webserver"""
        from .server import (setup_starlette_server, start_uvicorn_server,)

        # Initialize Server instance
        self.server = setup_starlette_server(self)
        # Initialize Application settings and templates
        self.setup_configs()
        self.install_sys_plugins()
        self._activate_plugins()

        # Run uvicorn server
        if self.SSG_IN_PROGRESS: return
        start_uvicorn_server(self, routes)


class TemplateEnvironment(Environment):

    def __init__(self, app: PyonirApp):
        from jinja2 import FileSystemLoader, ChoiceLoader
        from webassets import Environment as AssetsEnvironment
        from pyonir import PYONIR_JINJA_TEMPLATES_DIRPATH, PYONIR_JINJA_FILTERS_DIRPATH, PYONIR_JINJA_EXTS_DIRPATH
        from webassets.ext.jinja2 import AssetsExtension
        from pyonir.utilities import load_modules_from

        self.themes = PyonirThemes(os.path.join(app.frontend_dirpath, PyonirApp.THEMES_DIRNAME))

        jinja_template_paths = ChoiceLoader([FileSystemLoader(self.themes.active_theme.jinja_template_path),
                                             FileSystemLoader(PYONIR_JINJA_TEMPLATES_DIRPATH)])
        sys_filters = load_modules_from(PYONIR_JINJA_FILTERS_DIRPATH)
        app_filters = load_modules_from(app.jinja_filters_dirpath)
        installed_extensions = load_modules_from(PYONIR_JINJA_EXTS_DIRPATH, True)
        app_extensions = [AssetsExtension, *installed_extensions]
        app_filters = {**sys_filters, **app_filters}
        super().__init__(loader=jinja_template_paths, extensions=app_extensions)

        def url_for(path):
            rmaps = app.server.url_map if app.server else {}
            return rmaps.get(path, {}).get('path', app.ASSETS_ROUTE)

        app_active_theme = self.themes.active_theme
        #  Custom filters
        self.filters.update(**app_filters)
        # load assests tag
        self.assets_environment = AssetsEnvironment(app_active_theme.static_dirpath, app.ASSETS_ROUTE)
        # Add paths containing static assets
        # self.assets_environment.load_path.append(app_active_theme.static_dirpath)
        self.url_expire = False
        self.globals['url_for'] = url_for
        self.globals['configs'] = app.configs.app
        self.globals['request'] = None
        # self.globals.update(**app.jinja_template_globals)


    def add_jinja_path(self, path: str):
        pass

    def add_filter(self, filter: callable):
        name = filter.__name__
        print(name)
        self.filters.update({name: filter})
        pass


class PyonirThemes:
    """Represents sites available and active theme(s) within the frontend directory."""

    def __init__(self, theme_dirpath: str):
        self.themes_dirpath: str = theme_dirpath # directory path to available site themes
        self._available_themes: PyonirCollection | None = None # collection of themes available in frontend/themes directory

    @property
    def active_theme(self) -> Theme | None:
        from pyonir import Site
        from pyonir.parser import get_attr
        if not Site: return None
        self._available_themes = self._get_available_themes()
        site_theme = get_attr(Site.configs, 'app.theme_name')
        site_theme = self._available_themes.find(site_theme, from_attr='theme_dirname')
        return site_theme

    def _get_available_themes(self) -> PyonirCollection | None:
        from pyonir import Site
        if not Site: return None
        fe_ctx = list(Site.app_ctx)
        fe_ctx[2] = Site.frontend_dirpath
        pc = PyonirCollection.query(self.themes_dirpath, fe_ctx, include_only='README.md', data_model=Theme)
        return pc

