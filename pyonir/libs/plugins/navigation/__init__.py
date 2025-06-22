import dataclasses
from pyonir.types import IPlugin, PyonirRequest, PyonirApp, PyonirPlugin
from pyonir.utilities import PyonirCollection


@dataclasses.dataclass
class Menu:
    _mapper_key = 'menu'
    url: str
    slug: str = ''
    title: str = ''
    group: str = ''
    parent: str = ''
    icon: str = ''
    img: str = ''
    order: int = 0
    subtitle: str = ''
    dom_class: str = ''
    status: str = ''

    def __post_init__(self):
        self.name = self.title
        pass

class Navigation(PyonirPlugin):
    """Assembles a map of navigation menus based on file configurations"""
    name = 'Navigation Plugin'

    def __init__(self, app: PyonirApp):
        self.menus = {}
        self.active_page = None
        self.build_navigation(app=app)
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
        app.TemplateEnvironment.globals['navigation'] = self.menus.get(app.name)


    def build_plugins_navigation(self, app: PyonirApp):
        if app.available_plugins:
            for plgn in app.available_plugins:
                if not hasattr(plgn, 'pages_dirpath'): continue
                self.build_navigation(plgn)
                pass

    def build_navigation(self, app: PyonirApp):
        from pyonir.utilities import allFiles
        from pyonir import Site
        if app is None: return None
        assert hasattr(app, 'pages_dirpath'), "Get menus 'app' parameter does not have a pages dirpath property"
        menus = {}
        submenus = {}
        file_list = allFiles(app.pages_dirpath, app_ctx=app.app_ctx, entry_type=Menu)  # return files using menu schema model

        for menu in file_list:
            # menu = self.schemas.menu.map_input_to_model(pg)
            has_menu = menu.group or menu.parent
            if menu.status == 'hidden' or not menu.url or (not has_menu): continue
            menu.active = self.active_page == menu.url
            if menu.group:
                menus[menu.url] = menu
            elif menu.parent:
                _ref = submenus.get(menu.parent)
                if not _ref:
                    submenus[menu.parent] = [menu]
                else:
                    _ref.append(menu)

        if submenus:
            for k, m in submenus.items():
                pmenu = menus.get(k)
                if not pmenu: continue
                pmenu.sub_menus = m

        res = PyonirCollection(menus.values(), sort_key='order').group_by('group')
        self.menus[app.name] = res
