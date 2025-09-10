from __future__ import annotations

import os
from collections import OrderedDict
from typing import Optional, Generator

from pyonir.utilities import get_attr, load_env, generate_id

from pyonir.pyonir_types import PyonirThemes, EnvConfig, PyonirHooks, Parsely


class Base:
    SSG_IN_PROGRESS: bool = False  # toggle when static site generator is running
    APPS_DIRNAME: str = "apps"  # dirname for any child apps
    BACKEND_DIRNAME: str = "backend"  # dirname for all backend python files
    FRONTEND_DIRNAME: str = "frontend"  # dirname for all themes, jinja templates, html, css, and js
    CONTENTS_DIRNAME: str = "contents"  # dirname for site parsely file data
    PLUGINS_DIRNAME: str = "plugins" # main application plugins directory
    THEMES_DIRNAME: str = "themes"  # dirname for site themes
    CONFIGS_DIRNAME: str = 'configs'
    TEMPLATES_DIRNAME: str = 'templates'
    SSG_DIRNAME: str = 'static_site'
    DATA_DIRNAME: str = 'data_stores'
    UPLOADS_THUMBNAIL_DIRNAME: str = "thumbnails" # resized image directory name
    UPLOADS_DIRNAME: str = "uploads" # url name for serving uploaded assets
    PUBLIC_ASSETS_DIRNAME: str = "public"
    """Global static assets directory name for serving static files"""
    FRONTEND_ASSETS_DIRNAME: str = "static"
    """Theme assets directory name for serving static files"""
    API_DIRNAME: str = "api" # directory for serving API endpoints and resolver routes
    PAGES_DIRNAME: str = "pages" # directory for serving HTML endpoints with file based routing
    LOGS_DIRNAME: str = "logs" # directory for serving HTML endpoints with file based routing
    FILTERS_DIRNAME: str = "filters" # directory for jinja template filters
    API_ROUTE = f"/{API_DIRNAME}"  # Api base path for accessing pages as JSON

    app_dirpath: str = '' # absolute path to context directory
    name: str = ''# context name
    _settings: Optional[object] # context settings
    _resolvers = Optional[dict] # resolver registry

    # FIELDS
    @property
    def app_ctx(self):
        return self.name, self.endpoint, self.contents_dirpath, self.ssg_dirpath

    @property
    def settings(self) -> object:
        """Application context settings"""
        return self._settings

    @property
    def endpoint(self):
        """Customer facing url address to access the store pages"""
        return self.settings.url if hasattr(self.settings, 'url') else None

    # ROUTES
    @property
    def frontend_assets_route(self) -> str: return f"/{self.FRONTEND_ASSETS_DIRNAME}"

    @property
    def public_assets_route(self) -> str: return f"/{self.PUBLIC_ASSETS_DIRNAME}"

    @property
    def uploads_route(self) -> str: return f"/{self.UPLOADS_DIRNAME}"

    @property
    def request_paths(self):
        """Request will search for files in the assigned directories under the qualifying endpoint"""
        return self.endpoint, {self.pages_dirpath, self.api_dirpath}

    # FILES
    @property
    def virtual_routes_filepath(self) -> Optional[str]:
        """The context virtual routes file"""
        routes_file = os.path.join(self.pages_dirpath, ".routes.md")
        return routes_file if os.path.exists(routes_file) else None

    # DIRECTORIES
    @property
    def frontend_assets_dirpath(self) -> str:
        """Directory location for template related assets"""
        return os.path.join(self.frontend_dirpath, self.FRONTEND_ASSETS_DIRNAME)

    @property
    def public_assets_dirpath(self) -> str:
        """Directory location for general assets"""
        return os.path.join(self.frontend_dirpath, self.PUBLIC_ASSETS_DIRNAME)

    @property
    def ssg_dirpath(self) -> str:
        """Directory path for site's static generated files"""
        return os.path.join(self.app_dirpath, self.SSG_DIRNAME)

    @property
    def logs_dirpath(self) -> str:
        """Directory path for site's log files"""
        return os.path.join(self.app_dirpath, self.LOGS_DIRNAME)

    @property
    def backend_dirpath(self) -> str:
        """Directory path for site's python backend files (controllers, filters)"""
        return os.path.join(self.app_dirpath, self.BACKEND_DIRNAME)

    @property
    def contents_dirpath(self) -> str:
        """Directory path for site's contents"""
        return os.path.join(self.app_dirpath, self.CONTENTS_DIRNAME)

    @property
    def template_filters_dirpath(self) -> str:
        """Directory path for jinja template filters"""
        return os.path.join(self.backend_dirpath, self.FILTERS_DIRNAME)

    @property
    def frontend_dirpath(self) -> str:
        """Directory path for site's theme folders"""
        return os.path.join(self.app_dirpath, self.FRONTEND_DIRNAME)

    @property
    def plugins_dirpath(self) -> str:
        """Directory path to site's available plugins"""
        return os.path.join(self.app_dirpath, self.PLUGINS_DIRNAME)

    @property
    def frontend_templates_dirpath(self) -> str:
        """Directory path for site's theme folders"""
        return os.path.join(self.frontend_dirpath, self.TEMPLATES_DIRNAME)

    @property
    def pages_dirpath(self) -> str:
        """Directory path to serve as file-based routing"""
        return os.path.join(self.contents_dirpath, self.PAGES_DIRNAME)

    @property
    def api_dirpath(self) -> str:
        """Directory path to serve API as file-based routing"""
        return os.path.join(self.contents_dirpath, self.API_DIRNAME)

    @property
    def configs_dirpath(self) -> str:
        """Directory path for application settings"""
        return os.path.join(self.contents_dirpath, self.CONFIGS_DIRNAME)

    @property
    def uploads_dirpath(self) -> str:
        """Directory path to site's uploaded assets"""
        return os.path.join(self.contents_dirpath, self.UPLOADS_DIRNAME)


    # RUNTIME
    def process_configs(self):
        """Processes all context settings"""
        from pyonir.models.utils import process_contents
        self._settings = process_contents(self.configs_dirpath, app_ctx=self.app_ctx)

    def parse_file(self, file_path: str) -> 'DeserializeFile':
        """Parses a file and returns a Parsely instance for the file."""
        # from pyonir.parser import Parsely
        from pyonir.models.page import DeserializeFile
        return DeserializeFile(file_path, app_ctx=self.app_ctx)

    def apply_virtual_routes(self, pyonir_request: 'BaseRequest') -> 'Parsely':
        """Reads and applies virtual .routes.md file specs onto or updates the request file"""
        from pyonir.models.parser import DeserializeFile, FileStatuses
        server = pyonir_request.app.server
        virtual_route_url, virtual_route_data, virtual_path_params = server.get_virtual(pyonir_request.path)
        if virtual_route_data:
            rfile: DeserializeFile = pyonir_request.file
            pyonir_request.path_params.update(virtual_path_params)
            if rfile.file_exists:
                rfile.data.update(virtual_route_data)
                rfile.apply_filters()
            if not rfile.file_exists and not pyonir_request.is_api:
                # replace 404page with the virtual file as the page
                request_ctx = pyonir_request.app_ctx_ref
                vfile = self.parse_file(request_ctx.virtual_routes_filepath)
                vurl_data = vfile.data.get(virtual_route_url) or {}
                vurl_data.update(**{'url': pyonir_request.path, 'slug': pyonir_request.slug})
                vfile.data = vurl_data
                vfile.status = FileStatuses.PUBLIC
                # vfile.file_ssg_html_dirpath = vfile.file_ssg_html_dirpath.replace(vfile.file_name, pyonir_request.slug)
                # vfile.file_ssg_api_dirpath = vfile.file_ssg_api_dirpath.replace(vfile.file_name, pyonir_request.slug)
                pyonir_request.file = vfile

    def register_resolver(self, name: str, cls_or_path, args=(), kwargs=None, hot_reload=False):
        import inspect
        """
        Register a class for later instantiation.

        cls_or_path - Either a class object or dotted path string
        hot_reload  - Only applies if cls_or_path is a dotted path
        """
        if inspect.isclass(cls_or_path):
            class_path = f"{cls_or_path.__module__}.{cls_or_path.__qualname__}"
            # hot_reload = False  # No reload possible if you pass the class directly
        elif isinstance(cls_or_path, str):
            class_path = cls_or_path
        else:
            raise TypeError("cls_or_path must be a class object or dotted path string")

        self._resolvers[name] = {
            "class_path": class_path,
            "args": args,
            "kwargs": kwargs or {},
            "hot_reload": hot_reload
        }

    def reload_resolver(self, name) -> Optional[callable]:
        """
        Instantiate the registered class.
        Reload if hot_reload is enabled and class was registered by path.
        """
        import importlib, sys
        from pyonir.utilities import get_attr
        from pyonir.models.loaders import load_resolver

        cls_path, meth_name = name.rsplit(".", 1)
        is_pyonir = name.startswith('pyonir')
        entry = get_attr(self._resolvers, cls_path)

        # access module instance
        if entry:
            module_path, cls_name = entry["class_path"].rsplit(".", 1)

            if entry["hot_reload"] and module_path in sys.modules:
                importlib.reload(sys.modules[module_path])
            elif module_path not in sys.modules:
                importlib.import_module(module_path)

            cls = getattr(sys.modules[module_path], cls_name)
            new_instance = cls(*entry["args"], **entry["kwargs"])
            return getattr(new_instance, meth_name)

        # access constant value or methods on application instance
        resolver = get_attr(self, name)

        # access modules from loader
        if not resolver:
            from pyonir import PYONIR_DIRPATH
            resolver = load_resolver(name,
                                          base_path=PYONIR_DIRPATH if is_pyonir else self.app_dirpath,
                                          from_system=is_pyonir)
        if not resolver:
            print(f"Unable to load {name}")

        return resolver

    @staticmethod
    def generate_resolvers(cls: callable, output_dirpath: str, namespace: str = ''):
        """Automatically generate api endpoints from service class or module."""
        import textwrap, inspect
        from pyonir.utilities import create_file

        def process_docs(meth: callable):
            docs = meth.__doc__
            if not docs: return '', docs
            res = textwrap.dedent(docs).strip()
            _r = res.split('---')
            meta = _r.pop(1) if '---' in res else ''
            return meta, "".join(_r)

        resolver_template = textwrap.dedent("""\
        {meta}
        ===
        {docs}
        """).strip()

        name = ''

        if inspect.ismodule(cls):
            name = cls.__name__
            endpoint_meths = [
                m for m, obj in inspect.getmembers(cls, inspect.isfunction)
                if obj.__module__ == name
            ]
            call_path_fn = lambda meth_name: f"{namespace}.{name}.{meth_name}"

        else:  # Means cls is an instance
            klass = type(cls)
            name = klass.__name__
            output_dirpath = os.path.join(output_dirpath, namespace)
            call_path_fn = lambda meth_name: f"{namespace}.{meth_name}"
            endpoint_meths = [
                m for m in dir(cls)
                if not m.startswith('_') and callable(getattr(cls, m))
            ]

        print(f"Generating {name} API endpoint definitions for:")
        for meth_name in endpoint_meths:
            file_path = os.path.join(output_dirpath, meth_name+'.md')
            method_import_path = call_path_fn(meth_name)
            meth: callable = getattr(cls, meth_name)
            meta, docs = process_docs(meth)
            if not meta: continue
            meta = textwrap.dedent(meta.replace('{method_import_path}', method_import_path)).strip()
            m_temp = resolver_template.format(docs=docs, meta=meta)
            create_file(file_path, m_temp)
            print(f"\t{meth_name} at {file_path}")

    @staticmethod
    def query_files(dir_path: str, app_ctx: tuple, model_type: any = None) -> object:
        from pyonir.utilities import process_contents
        return process_contents(dir_path, app_ctx, model_type)



class BasePlugin(Base):

    def __init__(self, app, parent):
        from pyonir.core import PyonirApp
        self.app: PyonirApp = app
        self.name: str = parent.__class__.__name__.lower()

    @property
    def app_ctx(self):
        """plugins app context is relative to the application context"""
        return self.name, self.endpoint, self.contents_dirpath, os.path.join(self.app.ssg_dirpath, self.endpoint)

    @property
    def request_paths(self):
        """Request will search for files in the assigned directories under the qualifying endpoint"""
        return self.endpoint, {self.pages_dirpath, self.api_dirpath} if self.endpoint else None

    @property
    def endpoint(self):
        """Customer facing url address to access the store pages"""
        return self.settings.url if hasattr(self.settings, 'url') else None

    @property
    def contents_dirpath(self) -> str:
        """path to plugin contents within the application contents directory"""
        return os.path.join(self.app.contents_dirpath, f'@{self.name}')

    @property
    def pages_dirpath(self) -> str:
        """Directory path for serving shop pages and routes"""
        return os.path.join(self.contents_dirpath, self.app.PAGES_DIRNAME)

    @property
    def api_dirpath(self) -> str:
        """API directory for the plugin"""
        return os.path.join(self.contents_dirpath, self.app.API_DIRNAME)

    @property
    def ssg_dirpath(self) -> str:
        """SSG Directory path for generating shop pages and routes"""
        return os.path.join(self.app.ssg_dirpath, self.endpoint)

    @property
    def settings(self) -> object:
        """Plugin settings are pulled from the application settings"""
        plugin_settings = getattr(self.app.settings, self.name)
        return plugin_settings

    @property
    def env(self):
        """Application context environment configurations"""
        plugin_env_configs = getattr(self.app.env, self.name)
        return plugin_env_configs

class BaseApp(Base):
    # Default config settings
    EXTENSIONS = {"file": ".md", "settings": ".json"}
    THUMBNAIL_DEFAULT = (230, 350)
    PROTECTED_FILES = {'.', '_', '<', '>', '(', ')', '$', '!', '._'}
    IGNORE_FILES = {'.vscode', '.vs', '.DS_Store', '__pycache__', '.git'}
    IGNORE_WITH_PREFIXES = ('.', '_', '<', '>', '(', ')', '$', '!', '._')
    PAGINATE_LIMIT: int = 6
    DATE_FORMAT: str = "%Y-%m-%d %I:%M:%S %p"
    TIMEZONE: str = "US/Eastern"
    MEDIA_EXTENSIONS = {
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
    }

    def __init__(self, app_entrypoint: str, use_themes: bool = None):
        from pyonir.models.templating import TemplateEnvironment
        from pyonir.core import PyonirServer
        from pyonir.models.parser import parse_markdown, DeserializeFile
        from pyonir import __version__
        DeserializeFile._routes_dirname = self.PAGES_DIRNAME
        self.VERSION = __version__
        self.SECRET_SAUCE = generate_id()
        self.SESSION_KEY = f"{self.name}_session"


        self.app_entrypoint: str = app_entrypoint # application main.py file or the initializing file
        self.app_dirpath: str = os.path.dirname(app_entrypoint) # application main.py file or the initializing file
        self.name: str = os.path.basename(self.app_dirpath) # directory name of application
        self.themes: Optional[PyonirThemes] = None # application themes
        self.plugins_installed = {}
        self._plugins_activated: set = set()
        self._resolvers = {}
        self._settings: object = None
        self._env: EnvConfig = load_env(os.path.join(self.app_dirpath, '.env'))
        self.use_themes = use_themes
        """Serve frontend files from the frontend directory for HTML requests"""
        self.TemplateEnvironment = TemplateEnvironment(self)
        """Templating manager"""
        self.server = PyonirServer(self)
        """Starlette server instance"""

        self.Parsely_Filters = {
            'jinja': self.parse_jinja,
            'pyformat': self.parse_pyformat,
            'md': parse_markdown
        }
        self.domain

    @property
    def env(self) -> EnvConfig: return self._env

    @property
    def use_ssl(self) -> bool: return get_attr(self.env, 'app.use_ssl',  '').strip().lower() in ('true', '1', 'yes')

    @property
    def salt(self) -> str: return get_attr(self.env, 'app.salt')

    @property
    def is_dev(self) -> bool:
        from pyonir.models.server import DEV_ENV
        return getattr(self.env, 'APP_ENV') == DEV_ENV and not self.SSG_IN_PROGRESS

    @property
    def host(self) -> str: return '0.0.0.0' if self.is_dev else '127.0.0.1'

    @property
    def port(self) -> int:
        return int(get_attr(self.env, 'app.port', 5000)) #if self.configs else 5000

    @property
    def protocol(self) -> str: return 'https' if self.is_secure else 'http'

    @property
    def is_secure(self) -> bool:
        """Check if the application is configured to use SSL"""
        has_ssl_files = os.path.exists(self.ssl_cert_file) and os.path.exists(self.ssl_key_file)
        return has_ssl_files and self.use_ssl

    @property
    def domain_name(self) -> str: return get_attr(self.env, 'app.domain', self.host) # if self.configs else self.host

    @property
    def domain(self) -> str:
        host = f"localhost:{self.port}" if self.is_dev else self.domain_name
        return f"{self.protocol}://{host}"

    @property
    def activated_plugins(self) -> frozenset[BasePlugin]:
        return frozenset(self._plugins_activated)

    # FILES
    @property
    def ssl_cert_file(self):
        """Path to the SSL certificate file for the application"""
        return os.path.join(self.app_dirpath, "server.crt")

    @property
    def ssl_key_file(self):
        """Path to the SSL key file for the application"""
        return os.path.join(self.app_dirpath, "server.key")

    @property
    def nginx_config_filepath(self):
        default = os.path.join(self.app_dirpath, self.name + '.conf')
        return get_attr(self.env, 'app.nginx_conf_dirpath') or default

    @property
    def unix_socket_filepath(self):
        """WSGI socket file reference"""
        default = os.path.join(self.app_dirpath, self.name+'.sock')
        return get_attr(self.env, 'app.unix_socket_dirpath') or default

    # DIRECTORIES
    @property
    def app_account_dirpath(self) -> str:
        """Parent directory location for applications"""
        return os.path.dirname(self.app_dirpath)

    @property
    def datastore_dirpath(self) -> str:
        """Directory path for file system data storage is one level above the application directory
        and labeled as {appname}_data_stores"""
        default = os.path.join(self.app_account_dirpath, f"{self.name}_{self.DATA_DIRNAME}")
        return get_attr(self.env, 'app.data_dirpath') or default

    @property
    def frontend_assets_dirpath(self) -> str:
        """Directory location for template related assets"""
        theme_assets_dirpath = self.themes.active_theme.static_dirpath if self.themes else None
        return theme_assets_dirpath or os.path.join(self.frontend_dirpath, self.FRONTEND_ASSETS_DIRNAME)

    # SETUP
    def install_sys_plugins(self):
        """Install pyonir system plugins"""
        from pyonir.libs.plugins.navigation import Navigation
        self.install_plugin(Navigation, 'pyonir_navigation')
        self._plugins_activated.add(Navigation(self))

    def configure_themes(self):
        """The Configures themes for application"""

        from pyonir.utilities import get_attr
        from pyonir.models.templating import PyonirThemes

        themes_dir_path = os.path.join(self.frontend_dirpath, self.THEMES_DIRNAME)
        if not self.use_themes or not os.path.exists(themes_dir_path):
            print(f"Site is not configured to serve themes. {themes_dir_path} is not created or app isn't serving a frontend")
            return

        self.themes = PyonirThemes(themes_dir_path)
        app_active_theme = self.themes.active_theme
        if app_active_theme is None:
            raise ValueError(f"No active theme name {get_attr(self.settings, 'app.theme_name')} found in {self.frontend_dirpath} themes directory. Please ensure a theme is available.")

        # Load theme templates
        self.TemplateEnvironment.load_template_path(app_active_theme.jinja_template_path)

    def collect_virtual_routes(self) -> None:
        """Sets a map on server instance for all virtual routes from application and plugin contexts"""
        virtual_routes = OrderedDict()
        site_routes = self.parse_file(self.virtual_routes_filepath).data
        for plg in self.activated_plugins:
            if not hasattr(plg, 'parse_file'): continue
            vroute = plg.parse_file(plg.virtual_routes_filepath).data
            virtual_routes.update(vroute)
        virtual_routes.update(site_routes)
        self.server.virtual_routes = virtual_routes

    # RUNTIME
    def load_routers(self, routers: list):
        """Loads a list of routers into the application server"""
        self.server.init_app_endpoints(routers)

    def apply_globals(self, global_vars: dict = None):
        """Updates the jinja global variables dictionary"""
        self.TemplateEnvironment.globals['site'] = self
        self.TemplateEnvironment.globals['configs'] = self.settings
        self.TemplateEnvironment.globals['env'] = self.env
        if global_vars:
            self.TemplateEnvironment.globals.update(global_vars)

    def install_plugin(self, plugin_class: callable, plugin_directory_name: str = None):
        """Installs and activates a plugin"""
        plugin_directory_name = plugin_class.__module__.split('.')[1:2].pop() if not plugin_directory_name else plugin_directory_name
        self.plugins_installed[plugin_directory_name] = plugin_class
        self.activate_plugin(plugin_directory_name)

    def activate_plugins(self):
        """Active plugins enabled based on settings"""
        from pyonir.utilities import get_attr
        has_plugin_configured = get_attr(self.settings, 'app.enabled_plugins', None)
        if not has_plugin_configured: return
        for plg_id, plugin in self.plugins_installed.items():
            self.activate_plugin(plg_id)

    def activate_plugin(self, plugin_name: str):
        """Activates an installed plugin and adds to set of activated plugins"""
        plg_cls = self.plugins_installed.get(plugin_name)
        has_plugin_configured = plugin_name in (get_attr(self.settings, 'app.enabled_plugins') or [])
        if plg_cls is None or not has_plugin_configured:
            self.deactivate_plugin(plugin_name)
            return
        self._plugins_activated.add(plg_cls(self))

    def deactivate_plugin(self, plugin_name: str):
        """Deactivates a plugin and removes it from the set of activated plugins"""
        plg_cls = self.plugins_installed.get(plugin_name)
        if plg_cls is None: return

        # Find the active plugin instance of this class
        to_remove = None
        for plugin in self._plugins_activated:
            if isinstance(plugin, plg_cls):
                to_remove = plugin
                break

        if to_remove:
            # Optional: give plugin a chance to clean up
            if hasattr(to_remove, "teardown"):
                to_remove.teardown()
            self._plugins_activated.remove(to_remove)

    def run_plugins(self, hook: PyonirHooks, data_value=None):
        if not hook or not self._plugins_activated: return
        hook = hook.lower()
        for plg in self._plugins_activated:
            if not hasattr(plg, hook): continue
            hook_method = getattr(plg, hook)
            hook_method(data_value, self)

    async def run_async_plugins(self, hook: PyonirHooks, data_value=None):
        if not hook or not self._plugins_activated: return
        hook_method_name = hook.lower()
        for plg in self._plugins_activated:
            if not hasattr(plg, hook_method_name): continue
            hook_method = getattr(plg, hook_method_name)
            await hook_method(data_value, self)

    def parse_jinja(self, string, context=None) -> str:
        """Render jinja template fragments"""
        if not context: context = {}
        if not self.TemplateEnvironment or not string: return string
        try:
            return self.TemplateEnvironment.from_string(string).render(configs=self.settings, **context)
        except Exception as e:
            raise

    def parse_pyformat(self, string, context=None) -> str:
        """Formats python template string"""
        if not context: context = {}
        if self.TemplateEnvironment:
            context.update(self.TemplateEnvironment.globals)
        try:
            return string.format(**context)
        except Exception as e:
            print('parse_pyformat', e, string)
            return string

    def run(self, uvicorn_options: list = None):
        """Runs the Uvicorn webserver"""

        self.apply_globals()
        # Initialize Application settings and templates
        self.install_sys_plugins()
        self.activate_plugins()
        self.collect_virtual_routes()

        self.server.generate_nginx_conf(self)
        # Run uvicorn server
        if self.SSG_IN_PROGRESS: return
        # Initialize Server instance
        if not self.salt:
            raise ValueError(f"You are attempting to run the application without proper configurations. .env file must include app.salt to protect the application.")
        self.server.run_uvicorn_server(uvicorn_options=uvicorn_options)

    def generate_static_website(self):
        """Generates Static website"""
        import time
        from pyonir import utilities
        from pyonir.models.server import BaseRequest
        from pyonir.models.parser import DeserializeFile
        from pyonir.models.database import query_fs
        self.SSG_IN_PROGRESS = True
        count = 0
        print(f"{utilities.PrntColrs.OKBLUE}1. Coping Assets")
        try:
            self.apply_globals()
            self.install_sys_plugins()
            self.collect_virtual_routes()
            site_map_path = os.path.join(self.ssg_dirpath, 'sitemap.xml')
            print(f"{utilities.PrntColrs.OKCYAN}3. Generating Static Pages")

            self.TemplateEnvironment.globals['is_ssg'] = True
            ssg_req = BaseRequest(None, self)
            start_time = time.perf_counter()

            all_pages: Generator[DeserializeFile] = query_fs(self.pages_dirpath, app_ctx=self.app_ctx, model='file')
            xmls = []
            for pgfile in all_pages:
                virtual_data, path_params, *rest = self.server.get_virtual(pgfile.data.get('url'))
                if path_params: ssg_req.ssg_request(pgfile, path_params)
                try:
                    pgfile.data.update(path_params or {})
                    pgfile.apply_filters()
                except Exception as e:
                    raise
                self.TemplateEnvironment.globals['request'] = ssg_req  # pg_req
                count += pgfile.generate_static_file()
                t = f"<url><loc>{self.protocol}://{self.domain}{pgfile.data.get('url')}</loc><priority>1.0</priority></url>\n"
                xmls.append(t)
                self.TemplateEnvironment.block_pull_cache.clear()

            # Compile sitemap
            smap = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{self.domain}</loc><priority>1.0</priority></url> {"".join(xmls)} </urlset>'
            utilities.create_file(site_map_path, smap, 0)

            # Copy theme static css, js files into ssg directory
            utilities.copy_assets(self.frontend_assets_dirpath, os.path.join(self.ssg_dirpath, self.FRONTEND_ASSETS_DIRNAME))
            utilities.copy_assets(self.public_assets_dirpath, os.path.join(self.ssg_dirpath, self.PUBLIC_ASSETS_DIRNAME))

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