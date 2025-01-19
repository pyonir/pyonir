import os
from pyonir.types import IPlugin, PyonirRequest, IApp
from pyonir.parser import ParselySchema
from pyonir.utilities import parse_all


class Navigation(IPlugin):
    """Assembles a map of navigation menus based on file configurations"""
    name = 'Navigation Plugin'

    def __init__(self, app: 'IApp'):
        menu_schema_dirpath = os.path.join(os.path.dirname(__file__), 'backend/contents/schemas')
        self.schemas = parse_all(menu_schema_dirpath, app.files_ctx, ParselySchema)
        self.menus = {}
        pass

    async def on_request(self, request: PyonirRequest, app: IApp):
        from pyonir.utilities import Collection, allFiles
        if app is None: return None
        assert hasattr(app, 'pages_dirpath'), "Get menus 'app' parameter does not have a pages dirpath property"
        refresh_nav = bool(request.query_params.get('rnav'))
        curr_nav = app.TemplateParser.globals.get('navigation')
        if curr_nav and not refresh_nav: return False
        pages = {}
        subpages = {}
        active_page = request.path

        file_list = allFiles(app.pages_dirpath, app_ctx=app.files_ctx)  # return files using menu schema model

        for pg in file_list:
            page = self.schemas.menu.map_to_schema(pg)
            pstatus = page.get('status')
            purl = page.get('url')
            menu_group = page.get('menu')  # parent level menu item
            menu_parent = page.get('menu_parent')  # child level menu item
            if pstatus == 'hidden' or not purl or (not menu_group and not menu_parent): continue
            page['active'] = active_page == page.get('url')
            if menu_group:
                pages[purl] = page
            elif menu_parent:
                _ref = subpages.get(menu_parent)
                if not _ref:
                    subpages[menu_parent] = [page]
                else:
                    _ref.append(page)

        if subpages:
            for k, m in subpages.items():
                pmenu = pages.get(k)
                if not pmenu: continue
                pmenu.update({"sub_menu": m})

        res = Collection(pages.values(), sortBy='order').groupedBy('menu')
        self.menus[app.name] = res
        app.TemplateParser.globals['navigation'] = res
