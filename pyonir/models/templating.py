import os
from dataclasses import dataclass
from typing import Optional, Dict

from jinja2 import Environment
from pyonir.models.app import BaseApp


class TemplateEnvironment(Environment):

    def __init__(self, app: BaseApp):
        if not os.path.exists(app.frontend_dirpath) and app.use_themes:
            raise ValueError(f"Frontend directory {app.frontend_dirpath} does not exist. Please ensure the frontend directory is set up correctly.")
        from jinja2 import FileSystemLoader, ChoiceLoader
        from pyonir import PYONIR_JINJA_TEMPLATES_DIRPATH, PYONIR_JINJA_FILTERS_DIRPATH, PYONIR_JINJA_EXTS_DIRPATH
        from webassets.ext.jinja2 import AssetsExtension
        from pyonir.utilities import load_modules_from

        installed_extensions = load_modules_from(PYONIR_JINJA_EXTS_DIRPATH, True)
        app_extensions = [AssetsExtension, *installed_extensions]
        jinja_template_paths = ChoiceLoader([FileSystemLoader(app.frontend_templates_dirpath), FileSystemLoader(PYONIR_JINJA_TEMPLATES_DIRPATH)])
        super().__init__(loader=jinja_template_paths, extensions=app_extensions)

        #  Custom filters
        sys_filters = load_modules_from(PYONIR_JINJA_FILTERS_DIRPATH)
        app_filters = load_modules_from(app.template_filters_dirpath)
        app_filters = {**sys_filters, **app_filters}
        self.filters.update(**app_filters)

        def url_for(path):
            rmaps = app.server.url_map if app.server else {}
            return rmaps.get(path, {}).get('path', '/'+path)

        # Include globals
        self.globals['url_for'] = url_for
        self.globals['request'] = None
        self.globals['user'] = None


    def load_template_path(self, template_path: str):
        """Adds template path to file loader"""
        from jinja2 import FileSystemLoader
        app_loader = self.loader
        if not app_loader: return
        self.loader.loaders.append(FileSystemLoader(template_path))

    def add_filter(self, filter: callable):
        name = filter.__name__
        print(f"Installing filter:{name}")
        self.filters.update({name: filter})
        pass

@dataclass
class Theme:
    _orm_options = {'mapper': {'theme_dirname': 'file_dirname', 'theme_dirpath': 'file_dirpath'}}
    name: str
    theme_dirname: str = ''
    """Directory name for theme folder within frontend/themes directory"""
    theme_dirpath: str = ''
    """Directory path for theme folder within frontend/themes directory"""
    details: Optional['Parsely'] = None
    """Represents a theme available in the frontend/themes directory."""
    _template_dirname = 'templates'
    _static_dirname = 'static'

    def __post_init__(self):
        self.details = self.readme()
        for k, v in self.details.data.items():
            if k in ('static_dirname', 'templates_dirname'):
                setattr(self, k, v)

    @property
    def static_dirname(self):
        """directory name for theme's jinja templates"""
        return self.details.data.get('static_dirname', self._static_dirname) if self.details else self._static_dirname

    @property
    def templates_dirname(self):
        """directory name for theme's jinja templates"""
        return self.details.data.get('templates_dirname', self._template_dirname) if self.details else self._template_dirname

    @property
    def static_dirpath(self):
        """directory to serve static theme assets"""
        return os.path.join(self.theme_dirpath, self.static_dirname)

    @property
    def jinja_template_path(self):
        return os.path.join(self.theme_dirpath, self.templates_dirname)

    def readme(self):
        """Returns the theme's README.md file content if available"""
        from pyonir import Site
        from pyonir.models.parser import DeserializeFile
        theme_ctx = list(Site.app_ctx)
        theme_ctx[2] = Site.frontend_dirpath
        theme_readme = os.path.join(self.theme_dirpath,'README.md')
        theme_readme =  theme_readme if os.path.exists(theme_readme) else os.path.join(self.theme_dirpath,'readme.md')
        readme = DeserializeFile(theme_readme, app_ctx=theme_ctx)
        if not readme.file_exists:
            raise ValueError(f"Theme {self.name} does not have a README.md file.")
        return readme

class PyonirThemes:
    """Represents sites available and active theme(s) within the frontend directory."""

    def __init__(self, theme_dirpath: str):
        if not os.path.exists(theme_dirpath):
            raise ValueError(f"Theme directory {theme_dirpath} does not exist.")
        self.themes_dirpath: str = theme_dirpath # directory path to available site themes
        self.available_themes: Optional[Dict[str, Theme]] = self.query_themes() # collection of themes available in frontend/themes directory

    @property
    def active_theme(self) -> Optional[Theme]:
        from pyonir import Site
        from pyonir.models.utils import get_attr
        if not Site or not self.available_themes: return None
        site_theme = get_attr(Site.settings, 'app.theme_name')
        site_theme = self.available_themes.get(site_theme)
        return site_theme

    def query_themes(self) -> Optional[Dict[str, Theme]]:
        """Returns a collection of available themes within the frontend/themes directory"""
        from pyonir import Site
        themes_map = {}
        for theme_dir in os.listdir(self.themes_dirpath):
            if theme_dir.startswith(BaseApp.IGNORE_WITH_PREFIXES): continue
            theme = Theme(name=theme_dir, theme_dirname=theme_dir,
                          theme_dirpath=os.path.join(self.themes_dirpath, theme_dir))
            theme._template_dirname = Site.TEMPLATES_DIRNAME
            theme._static_dirname = Site.FRONTEND_ASSETS_DIRNAME
            themes_map[theme_dir] = theme
        return themes_map if themes_map else None

