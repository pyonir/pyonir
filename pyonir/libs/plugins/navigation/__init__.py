import os
from dataclasses import dataclass

from pyonir.core import PyonirRequest, PyonirApp

@dataclass
class Menu:
    _orm_options = {'mapper_key': 'menu'}
    url: str
    slug: str = ''
    name: str = ''
    title: str = ''
    group: str = ''
    parent: str = ''
    icon: str = ''
    img: str = ''
    rank: int = 0
    subtitle: str = ''
    dom_class: str = ''
    status: str = ''

    def __post_init__(self):
        if not self.name:
            self.name = self.title
        pass

class Navigation:
    """Assembles a map of navigation menus based on file configurations"""
    name = 'pyonir_navigation'

    def __init__(self, app: PyonirApp):
        self.app = app
        self.menus = {}
        self.active_page = None
        self.build_navigation(app=app)
        # include navigation template example
        # self.register_templates([os.path.join(os.path.dirname(__file__), 'templates')])
        app.TemplateEnvironment.load_template_path(os.path.join(os.path.dirname(__file__), 'templates'))
        self.add_menus_to_environment(app)
        pass

    def after_init(self, data: any, app: PyonirApp):
        self.build_plugins_navigation(app)

    async def on_request(self, request: PyonirRequest, app: PyonirApp):
        """Executes task on web request"""
        refresh_nav = bool(getattr(request.query_params,'rnav', None))
        curr_nav = app.TemplateEnvironment.globals.get('navigation')
        if curr_nav and not refresh_nav: return None
        self.active_page = request.path
        self.build_navigation(app)
        self.add_menus_to_environment(app)

    def add_menus_to_environment(self, app: PyonirApp):
        app.TemplateEnvironment.globals['navigation'] = self.menus.get(app.name)


    def build_plugins_navigation(self, app: PyonirApp):
        if app.activated_plugins:
            for plgn in app.activated_plugins:
                if isinstance(plgn, Navigation):continue
                if not hasattr(plgn, 'pages_dirpath'): continue
                self.build_navigation(plgn)
                pass

    def build_navigation(self, app: PyonirApp):
        # from pyonir.utilities import query_files
        from pyonir.models.database import query_fs
        from collections import defaultdict
        if app is None: return None
        assert hasattr(app, 'pages_dirpath'), "Get menus 'app' parameter does not have a pages dirpath property"
        menus = {}
        submenus = {}
        file_list = query_fs(app.pages_dirpath, app_ctx=app.app_ctx, model=Menu)

        def group_by_menu(items):
            grouped = defaultdict(list)
            for item in items:
                has_menu = item.group or item.parent
                if item.status == 'hidden' or not item.url or (not has_menu): continue
                grouped[item.group].append(item)
            return dict(grouped)  # convert to plain dict if you like
        result = group_by_menu(file_list)
        self.menus[app.name] = result
