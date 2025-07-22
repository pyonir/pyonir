import os

from pyonir import process_contents
from pyonir.types import PyonirApp, PyonirRequest
from pyonir.core import PyonirPlugin
from .backend.filters import babelmoney


class Ecommerce(PyonirPlugin):
    endpoint = '/my-shop'

    def __init__(self, app: PyonirApp):
        """
        Initialize the online shop and compose service modules.
        """
        from pyonir.libs.plugins.ecommerce.backend.services import InventoryService, ProductService, UserService, CartService, OrderService, PaymentService
        from pyonir.libs.plugins.ecommerce.backend.models import Product
        from pyonir.server import route
        self.FRONTEND_DIRNAME = 'templates'
        super().__init__(app, __file__)

        self.configs = process_contents(os.path.join(self.contents_dirpath, 'configs'), app_ctx=self.app_ctx)
        setattr(self.configs, 'env', getattr(app.configs.env, self.name))

        # Setup services
        self.productService = ProductService(self, app)
        self.inventoryService = InventoryService(self, app)
        self.userService = UserService(self, app)
        self.cartService = CartService(self, app)
        self.orderService = OrderService(self, app)
        self.paymentService = PaymentService(self, app)
        app.TemplateEnvironment.add_filter(babelmoney)

        plugin_template_paths = [self.frontend_dirpath]
        should_install_locally = False #self.__class__.__name__ in app.configs.app.enabled_plugins

        # Generate resolvers for services
        self.generate_resolvers(self.inventoryService, os.path.join(self.contents_dirpath, self.API_DIRNAME, 'inventory'), self.module)
        self.generate_resolvers(self.orderService, os.path.join(self.contents_dirpath, self.API_DIRNAME, 'order'), self.module)
        self.generate_resolvers(self.cartService, os.path.join(self.contents_dirpath, self.API_DIRNAME, 'cart'), self.module)

        if should_install_locally:
            # build alternate path for contents and templates
            app_ecommerce_contents_dirpath = os.path.join(app.plugins_dirpath, self.module, self.CONTENTS_DIRNAME)
            app_ecommerce_pages_dirpath = os.path.join(app_ecommerce_contents_dirpath, self.PAGES_DIRNAME)
            app_ecommerce_api_dirpath = os.path.join(app_ecommerce_contents_dirpath, self.API_DIRNAME)
            app_ecommerce_template_dirpath = os.path.join(app.plugins_dirpath, self.module, self.TEMPLATES_DIRNAME)
            app_ecommerce_ssg_dirpath = os.path.join(app.ssg_dirpath, self.SSG_DIRNAME, self.module)

            # copy demo shop pages into site plugins on startup
            self.install_directory(self.contents_dirpath, app_ecommerce_contents_dirpath)
            self.install_directory(self.frontend_dirpath, app_ecommerce_template_dirpath)

            # Include additional paths when resolving web requests from application context
            self.register_routing_dirpaths([app_ecommerce_pages_dirpath,app_ecommerce_api_dirpath])

            plugin_template_paths.append(app_ecommerce_template_dirpath)
            self._app_ctx = [self.name, self.endpoint, app_ecommerce_contents_dirpath, app_ecommerce_ssg_dirpath]
        else:
            # Include additional paths when resolving web requests
            self.register_routing_dirpaths([
                os.path.join(self.contents_dirpath, 'pages'),
                os.path.join(self.contents_dirpath, 'api')])
            self.pages_dirpath = os.path.join(self.contents_dirpath, 'pages')

        # Register plugin template directory paths
        self.register_templates(plugin_template_paths)

        # route(None, self.endpoint+'/products/{product_id:str}',['GET'])
        route(None, f'/public/{self.name}', static_path=str(os.path.join(self.frontend_dirpath, 'static')))
        self.app.server.url_map[f"{self.module}.products"] = {"path": f"{self.endpoint}/products"}
        self.app.server.url_map[f"{self.module}.cart"] = {"path": f"{self.endpoint}/cart"}

    async def on_request(self, request: PyonirRequest, app: PyonirApp):
        if request.method == 'POST': return
        cart_items = self.cartService.view_cart(request)
        app.TemplateEnvironment.globals['cart_items'] = cart_items
        pass


