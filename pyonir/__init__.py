# -*- coding: utf-8 -*-
import os, sys
from pyonir import utilities
from pyonir.parser import Parsely
from pyonir.libs.plugins.Forms import Forms
from pyonir.libs.plugins.Navigation import Navigation
from pyonir.types import PyonirHooks

SYS_USER = os.path.basename(os.environ.get('HOME'))
# Pycasso settings
PYONIR_DIRPATH = os.path.abspath(os.path.dirname(__file__))
PYONIR_LIBS_DIRPATH = os.path.join(PYONIR_DIRPATH, "libs")
PYONIR_PLUGINS_DIRPATH = os.path.join(PYONIR_LIBS_DIRPATH, 'plugins')
PYONIR_SETUPS_DIRPATH = os.path.join(PYONIR_LIBS_DIRPATH, 'app_setup')
PYONIR_JINJA_DIRPATH = os.path.join(PYONIR_LIBS_DIRPATH, 'jinja')
PYONIR_JINJA_TEMPLATES_DIRPATH = os.path.join(PYONIR_JINJA_DIRPATH, "templates")
PYONIR_JINJA_EXTS_DIRPATH = os.path.join(PYONIR_JINJA_DIRPATH, "extensions")
PYONIR_JINJA_FILTERS_DIRPATH = os.path.join(PYONIR_JINJA_DIRPATH, "filters")
PYONIR_MESSAGES_FILE = os.path.join(PYONIR_LIBS_DIRPATH, "system-messages.md")
PYONIR_SSL_KEY = os.path.join(PYONIR_SETUPS_DIRPATH, "content/certs/server.key")
PYONIR_SSL_CRT = os.path.join(PYONIR_SETUPS_DIRPATH, "content/certs/server.crt")
PYONIR_STATIC_ROUTE = "/pyonir_assets"
PYONIR_STATIC_DIRPATH = os.path.join(PYONIR_LIBS_DIRPATH, 'ui-kits', 'static')

# Environments
DEV_ENV = 'LOCAL'
STAGE_ENV = 'STAGING'
PROD_ENV = 'PROD'

###########################
#     System Config       #
###########################
EXTENSIONS = {"file": ".md", "settings": ".json"}
THUMBNAIL_DEFAULT = (230, 350)
PROTECTED_FILES = ('.', '_', '<', '>', '(', ')', '$', '!', '._',)
IGNORE_FILES = ('.vscode', '.vs', '.DS_Store', '__pycache__', '.git')

PAGINATE_LIMIT = 6
RECENT_POSTS = 2
DATE_FORMAT = "%Y-%m-%d %I:%M:%S %p"
TIMEZONE = "US/Eastern"
ALLOWED_UPLOAD_EXTENSIONS = ('jpg', 'JPG', 'PNG', 'png', 'txt', 'md', 'jpeg', 'pdf', 'svg', 'gif')

# Base application directories
APPS_DIRNAME = "apps"  # dirname for any child apps
SITES_DIRNAME = "sites"  # dirname for any sites
BACKEND_DIRNAME = "backend"  # dirname for all backend markdown files
FRONTEND_DIRNAME = "frontend"  # dirname for all html templates and themes
CONTENTS_DIRNAME = "contents"  # dirname for site markdown data

# Backend sub directories
CONTROLLERS_DIRNAME = "controllers"
PLUGINS_DIRNAME = "plugins"
FILTERS_DIRNAME = "filters"
BACKEND_SUBDIRS = (
    f"{BACKEND_DIRNAME}/{CONTROLLERS_DIRNAME}",
    f"{BACKEND_DIRNAME}/{PLUGINS_DIRNAME}"
)

# Content sub directories
API_DIRNAME = "api"
DATASTORE_DIRNAME = "datastore"
PAGES_DIRNAME = "pages"
UPLOADS_DIRNAME = "uploads"
SCHEMAS_DIRNAME = "schemas"
CERTS_DIRNAME = "certs"
USERS_DIRNAME = "users"
CONFIGS_DIRNAME = "configs"
FORMS_DIRNAME = "forms"
LOGS_DIRNAME = "logs"
CONTENTS_DIRNAMES = (
    API_DIRNAME, PAGES_DIRNAME, CONFIGS_DIRNAME, SCHEMAS_DIRNAME, DATASTORE_DIRNAME, FORMS_DIRNAME, UPLOADS_DIRNAME)
CONTENT_SUBDIRS = (
    f"{CONTENTS_DIRNAME}/{API_DIRNAME}", CONTENTS_DIRNAME + "/" + CERTS_DIRNAME,
    CONTENTS_DIRNAME + "/" + CONFIGS_DIRNAME, CONTENTS_DIRNAME + "/" + UPLOADS_DIRNAME,
    CONTENTS_DIRNAME + "/" + SCHEMAS_DIRNAME, CONTENTS_DIRNAME + "/" + FORMS_DIRNAME,
    CONTENTS_DIRNAME + "/" + DATASTORE_DIRNAME, CONTENTS_DIRNAME + "/" + PAGES_DIRNAME
)

APPLICATION_DIRS = (BACKEND_DIRNAME, FRONTEND_DIRNAME, CONTENTS_DIRNAME) + BACKEND_SUBDIRS + CONTENT_SUBDIRS

# Frontend
THEMES_DIRNAME = "themes"
THEME_STATIC_DIRNAME = "static"
THEME_TEMPLATES_DIRNAME = "layouts"
THEME_NAME = "pencil"
ASSETS_DIRNAME = "public"
SSG_DIRNAME = "static_site"
FRONTEND_SUBDIRS = (THEMES_DIRNAME, SSG_DIRNAME)

# Routes
API_ROUTE = f"/{API_DIRNAME}"  # Api base path for accessing pages as JSON
UPLOADS_ROUTE = f"/{UPLOADS_DIRNAME}"  # Upload base path to access resources within upload directory
ASSETS_ROUTE = f"/{ASSETS_DIRNAME}"  # serves static assets from configured theme
UPLOADS_THUMBNAIL_DIRNAME = "thumbnails"  # thumbnail sub directory name

VERSION = os.path.basename(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
HOST = 'localhost'  # '0.0.0.0'
PORT = 5000
__version__ = '1.0.0'
Site: 'IApp' = None


def init(site_path: str):
    """Initializes existing Pyonir application"""
    global Site
    # Set Global Site instance
    Site = IApp(site_path)
    return Site


class IApp:
    """Main Pyonir application"""

    SECRET_SAUCE = 'F12Zr47j\3yX R~X@H!jmM]Lwf/,?KT'  # used for salting tokens
    SESSION_KEY = 'pyonir_jwt'  # used for salting tokens
    VERSION = 'beta'  # running application version
    SYS_VERSION = VERSION
    SYS_USER = SYS_USER
    SYS_STATIC_DIRPATH = PYONIR_STATIC_DIRPATH
    endpoint = ''  # Home application

    @staticmethod
    def register_parsely_extension(plugins: list = None):
        """Registers new file parsing plugins"""
        if not plugins: return
        for plg in plugins:
            # Install parsely extension
            if hasattr(plg, 'parsely_extension'):
                Parsely.Extensions[plg.parsely_extension] = plg
        pass

    @property
    def env_home(self):
        """Returns value found in bash_profile defined for APPENV"""
        return os.environ.get('APPHOME')

    @property
    def env(self):
        """Returns value found in bash_profile defined for APPENV"""
        return os.getenv('APPENV')

    @property
    def is_dev(self):
        """Status returns if application is running in local dev mode"""
        return self.env == DEV_ENV

    @property
    def site_logs_dirpath(self):
        """Nginx conf file install location"""
        return os.path.join(self.app_dirpath, "logs")

    @property
    def app_socket_filename(self):
        """WSGI or ASGI file name"""
        return f"{self.name}.sock"

    @property
    def app_socket_filepath(self):
        """WSGI or ASGI file install location"""
        return os.path.join(self.app_dirpath, self.app_socket_filename)

    @property
    def app_nginx_conf_filepath(self):
        """NGINX configuration file"""
        return os.path.join(self.app_dirpath, self.name + '.conf')

    @property
    def app_sitemap_filepath(self):
        """WSGI or ASGI file install location"""
        return os.path.join(self.theme_static_dirpath, f"sitemap.xml")

    @property
    def domain(self):
        is_prod = (self.env is not DEV_ENV) and getattr(self.configs.app, 'domain', None)
        return self.configs.app.domain if is_prod else HOST

    @property
    def host(self):
        return self.domain

    @property
    def protocol(self):
        return 'https' if self.is_secure else 'http'

    @property
    def origin(self):
        addr = f"{self.protocol}://{self.domain}"
        return f"{addr}:{self.port}" if self.env is DEV_ENV else addr

    @property
    def port(self):
        """Port address for application"""
        return self.configs.port if hasattr(self.configs, 'port') else PORT

    @property
    def is_secure(self):
        return getattr(self.configs.app, 'use_ssl', None)

    @property
    def account_dirpath(self):
        """Site Account dirname all applications are install"""
        return os.path.dirname(self.app_dirpath)

    @property
    def account_dirname(self):
        """Site Account dirpath all applications are install"""
        return os.path.basename(os.path.dirname(self.app_dirpath))

    @property
    def themes(self):
        """Available themes installed in the frontend/themes directory"""
        return [Parsely(os.path.join(self.themes_dirpath, dirname, 'README.md')).data for dirname in
                os.listdir(self.themes_dirpath)
                if os.path.exists(os.path.join(self.themes_dirpath, dirname, 'README.md'))]

    @property
    def theme(self):
        """Active theme name displayed for website"""
        if hasattr(self, 'configs') and not hasattr(self.configs.app, 'theme_name'): return
        return self.configs.app.theme_name

    @property
    def theme_templates_dirpath(self):
        """Active Theme templates dirpath to access html files used to render a page during web requests"""
        if not self.theme: return
        return os.path.join(self.frontend_dirpath, THEMES_DIRNAME, self.theme, THEME_TEMPLATES_DIRNAME)

    @property
    def theme_layouts_and_files(self):
        """Map of all layout files and macros available inside a themes directory"""
        return os.listdir(self.theme_templates_dirpath)

    @property
    def theme_static_dirpath(self):
        """Active Theme static assets dirpath to access js,css and other web resources"""
        if not self.theme: return
        return os.path.join(self.frontend_dirpath, THEMES_DIRNAME, self.theme, THEME_STATIC_DIRNAME)

    @property
    def theme_assets_dirpath(self):
        """Active Theme static assets dirpath to access js,css and other web resources"""
        if not self.theme: return
        return os.path.join(self.theme_static_dirpath, ASSETS_DIRNAME)

    @property
    def ssg_dirpath(self):
        """Static site output directory path"""
        return os.path.join(self.app_dirpath, SSG_DIRNAME)

    @property
    def ssl_public_cert(self):
        """Static site output directory path"""
        pub_cert = utilities.Collection.get_attr(self.configs.app, 'public_cert') or 'server.crt'
        return os.path.join(self.contents_dirpath, CERTS_DIRNAME, pub_cert)

    @property
    def ssl_private_cert(self):
        """Static site output directory path"""
        priv_cert = utilities.Collection.get_attr(self.configs.app, 'private_cert') or 'server.key'
        return os.path.join(self.contents_dirpath, CERTS_DIRNAME, priv_cert)

    @property
    def request_paths(self):
        """list of base file paths to resolve web requests. includes child apps"""
        _ppth = [self.pages_dirpath, self.api_dirpath]
        _apprunes = [os.path.basename(p) for p in _ppth]
        appth = (self.name, '/', _ppth, _apprunes)
        ppth = [appth]
        return ppth

    def __init__(self, app_rootpth: str = None) -> None:
        self.server = None
        Parsely.Filters['jinja'] = self.parse_jinja
        self.name = os.path.basename(app_rootpth)
        self.app_dirpath = app_rootpth
        self.app_entrypoint = os.path.join(self.app_dirpath, 'main.py')
        self.logs_dirpath = os.path.join(app_rootpth, LOGS_DIRNAME)
        self.backend_dirpath = os.path.join(app_rootpth, BACKEND_DIRNAME)
        self.plugins_dirpath = os.path.join(self.backend_dirpath, PLUGINS_DIRNAME)
        self.filters_dirpath = os.path.join(self.backend_dirpath, FILTERS_DIRNAME)
        self.contents_dirpath = os.path.join(self.backend_dirpath, CONTENTS_DIRNAME)
        self.api_dirpath = os.path.join(self.contents_dirpath, API_DIRNAME)
        self.users_dirpath = os.path.join(self.contents_dirpath, USERS_DIRNAME)
        self.pages_dirpath = os.path.join(self.contents_dirpath, PAGES_DIRNAME)
        self.uploads_dirpath = os.path.join(self.contents_dirpath, UPLOADS_DIRNAME)
        self.datastore_dirpath = os.path.join(self.contents_dirpath, DATASTORE_DIRNAME)
        self.frontend_dirpath = os.path.join(app_rootpth, FRONTEND_DIRNAME)
        self.themes_dirpath = os.path.join(self.frontend_dirpath, THEMES_DIRNAME)
        self.files_ctx = ('', '', self.contents_dirpath, self.ssg_dirpath)
        self.messages = {}
        # self.available_plugins = {Forms(self), Navigation(self)}
        self.TemplateParser = None
        self.configs = self.process_contents(os.path.join(self.contents_dirpath, CONFIGS_DIRNAME), self.files_ctx)
        self.jinja_template_dirpaths = (self.theme_templates_dirpath, PYONIR_JINJA_TEMPLATES_DIRPATH,)
        self.setup_jinja()
        self.schemas = self.process_contents(os.path.join(self.contents_dirpath, SCHEMAS_DIRNAME), self.files_ctx)

        # Setups
        self.setup_system_msgs()
        self.available_plugins = {Forms(self), Navigation(self)}

    async def run_plugins(self, hook: PyonirHooks, data_value=None):
        if not hook or not self.available_plugins: return
        hook = hook.name.lower()
        for plg in self.available_plugins:
            if not hasattr(plg, hook): continue
            hook_method = getattr(plg, hook)
            await hook_method(data_value, self)

    def parse_jinja(self, string, context={}) -> str:
        try:
            return self.TemplateParser.from_string(string).render(configs=self.configs, **context)
        except Exception as e:
            raise

    def setup_system_msgs(self):
        """App and Pycasso system messages for logs and user display"""
        sys_msgs = Parsely(PYONIR_MESSAGES_FILE, self.files_ctx)
        app_msgs = Parsely(os.path.join(self.datastore_dirpath, 'app-messages.md'), self.files_ctx)
        self.messages.update(sys_msgs.data)
        self.messages.update(app_msgs.data)
        pass

    def setup_jinja(self):
        """Jinja parser used to generate html from jinja templates"""
        from jinja2 import Environment, FileSystemLoader
        from webassets import Environment as AssetsEnvironment
        from webassets.ext.jinja2 import AssetsExtension

        def url_for(path):
            rmaps = self.server.url_map
            return rmaps.get(path, {}).get('path', ASSETS_ROUTE)

        sysfilters = self.module_loader(PYONIR_JINJA_FILTERS_DIRPATH, default_data={})
        appfilters = self.module_loader(self.filters_dirpath, default_data={})
        self.JINJA_INSTALLED_FILTERS = {**sysfilters, **appfilters}
        self.JINJA_INSTALLED_EXTENSIONS = self.module_loader(PYONIR_JINJA_EXTS_DIRPATH, default_data=[],
                                                             rtn_attr='import_str')

        app_extensions = [AssetsExtension]
        for ext_module_str in self.JINJA_INSTALLED_EXTENSIONS:
            app_extensions.append(ext_module_str)

        self.TemplateParser = Environment(
            # '''path to find templates'''
            loader=FileSystemLoader(self.jinja_template_dirpaths),
            # '''include custom extensions'''
            extensions=app_extensions,
            # '''disable reloading of template changes'''
            auto_reload=True,
        )

        #  ''' Custom filters '''
        self.TemplateParser.filters.update(**self.JINJA_INSTALLED_FILTERS)

        # load assests tag
        self.TemplateParser.assets_environment = AssetsEnvironment(self.theme_static_dirpath, ASSETS_ROUTE)
        # Add paths containing static assets
        self.TemplateParser.assets_environment.load_path.append(self.theme_static_dirpath)
        self.TemplateParser.url_expire = False
        self.TemplateParser.globals['request'] = {}
        self.TemplateParser.globals['configs'] = self.configs.app
        self.TemplateParser.globals['url_for'] = url_for

    def generate_static_website(self):
        """Generates Static website into the specified static_site_dirpath"""
        import time
        from pyonir.server import generate_nginx_conf

        self.SSG_INPROGRESS = True
        count = 0
        print(f"{utilities.pcolors.OKBLUE}1. Coping Assets")
        try:

            static_site_dirpath = os.path.join(self.app_dirpath, SSG_DIRNAME)
            generate_nginx_conf(self)
            print(f"{utilities.pcolors.OKCYAN}3. Generating Static Pages")

            self.TemplateParser.globals['is_ssg'] = True
            start_time = time.perf_counter()

            all_pages = utilities.allFiles(self.pages_dirpath, app_ctx=self.files_ctx)
            xmls = []
            for page in all_pages:
                # pg_req = Request(self, page)
                self.TemplateParser.globals['request'] = page  # pg_req
                count += page.generate_static_file()
                t = f"<url><loc>{self.protocol}://{self.domain}{page.url}</loc><priority>1.0</priority></url>\n"
                xmls.append(t)
                self.TemplateParser.block_pull_cache.clear()
            del self.TemplateParser.globals['is_ssg']
            smap = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{self.domain}</loc><priority>1.0</priority></url> {"".join(xmls)} </urlset>'
            utilities.create_file(self.app_sitemap_filepath, smap, 0)
            utilities.copy_assets(PYONIR_STATIC_DIRPATH,
                                  os.path.join(static_site_dirpath, PYONIR_STATIC_ROUTE.lstrip('/')))
            utilities.copy_assets(self.theme_static_dirpath, os.path.join(static_site_dirpath, ASSETS_DIRNAME))
            end_time = time.perf_counter() - start_time
            ms = end_time * 1000
            count += 3
            msg = f"SSG generated {count} html/json files in {round(end_time, 2)} secs :  {round(ms, 2)} ms"
            print(f'\033[95m {msg}')
        except Exception as e:
            msg = f"SSG encountered an error: {str(e)}"
            raise

        self.SSG_INPROGRESS = False
        response = {"status": "COMPLETE", "msg": msg, "files": count}
        print(response)
        print(utilities.pcolors.RESET)
        return response

    def run(self, endpoints: 'Endpoints'):
        """Runs the Uvicorn webserver"""
        from .server import (setup_starlette_server, start_uvicorn_server,
                             pyonir_file_upload,pyonir_file_delete, pyonir_sse_handler)
        # Initialize Server instance
        self.server = setup_starlette_server(self)
        self.server.resolvers[pyonir_file_upload.__name__] = pyonir_file_upload
        self.server.resolvers[pyonir_file_delete.__name__] = pyonir_file_delete
        self.server.resolvers[pyonir_sse_handler.__name__] = pyonir_sse_handler

        # Run uvicorn server
        start_uvicorn_server(self, endpoints)

    @staticmethod
    def module_loader(path_to_modules, default_data=None, target_module_name=None, rtn_attr="", as_pkg=False) -> any:
        """
        This will preload python files from the provided modules path.
        Pycasso system and applications .py files will be accessible at runtime.
        """
        if default_data is None:
            default_data = []
        if not os.path.exists(path_to_modules): return default_data
        try:
            for module_dirname in os.listdir(path_to_modules):
                if module_dirname in IGNORE_FILES or \
                        module_dirname.startswith(PROTECTED_FILES): continue
                # convert path into module object
                module_dirname = os.path.join(module_dirname,
                                              target_module_name) if target_module_name else module_dirname
                if not os.path.exists(os.path.join(path_to_modules, module_dirname)): continue
                if not module_dirname.endswith('.py') and not as_pkg: continue
                pkg = utilities.PyonirMod(os.path.join(path_to_modules, module_dirname))
                if not pkg.class_module: continue
                name = f"{pkg.import_str}" if target_module_name else pkg.callable_name
                mod = getattr(pkg, rtn_attr, None)
                if isinstance(default_data, dict):
                    default_data.update(
                        {name: mod or pkg.class_module}
                    )
                elif isinstance(default_data, list):
                    default_data.append(mod or pkg)
        except Exception as e:
            raise
        return default_data

    @staticmethod
    def process_contents(path, app_ctx=None, astuple=None, asmap=None):
        """Deserializes all files within the contents directory"""
        key = os.path.basename(path)
        etype = Parsely  # ParselySchema if 'schemas' in path else Parsely
        ismappable = key in (CONFIGS_DIRNAME, SCHEMAS_DIRNAME)
        pgs = utilities.allFiles(path, entry_type=etype, app_ctx=app_ctx)
        if astuple or ismappable:
            res = {}
            for pgobj in pgs:
                configname = getattr(pgobj, 'file_name', getattr(pgobj, 'name', None))
                res[configname] = pgobj
                if hasattr(pgobj, 'abspath'): res['filepath'] = pgobj.abspath
                pass
            return utilities.tupleconverter(key, res)
        return list(pgs) if not asmap else {p.file_name: p for p in pgs}
