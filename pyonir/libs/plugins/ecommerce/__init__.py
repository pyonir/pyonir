import os

from pyonir import process_contents
from pyonir.types import PyonirApp, PyonirRequest, PyonirPlugin
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

        # Setup services
        self.productService = ProductService(self, app)
        self.inventoryService = InventoryService(self, app)
        self.userService = UserService(self, app)
        self.cartService = CartService(self, app)
        self.orderService = OrderService(self, app)
        self.paymentService = PaymentService(self, app)
        self.configs = process_contents(os.path.join(self.contents_dirpath), app_ctx=self.app_ctx)
        app.TemplateEnvironment.add_filter(babelmoney)

        plugin_template_paths = [self.frontend_dirpath]
        should_install_locally = None #self.__class__.__name__ in app.configs.app.enabled_plugins


        if should_install_locally:
            # build alternate path for contents and templates
            app_ecommerce_contents_dirpath = os.path.join(app.plugins_dirpath, self.module, self.CONTENTS_DIRNAME)
            app_ecommerce_pages_dirpath = os.path.join(app.plugins_dirpath, self.module, self.PAGES_DIRNAME)
            app_ecommerce_api_dirpath = os.path.join(app.plugins_dirpath, self.module, self.API_DIRNAME)
            app_ecommerce_template_dirpath = os.path.join(app.plugins_dirpath, self.module, self.TEMPLATES_DIRNAME)

            # copy demo shop pages into site plugins on startup
            self.install_directory(self.contents_dirpath, app_ecommerce_contents_dirpath)
            self.install_directory(self.frontend_dirpath, app_ecommerce_template_dirpath)

            # Include additional paths when resolving web requests from application context
            self.routing_paths.add(app_ecommerce_pages_dirpath)
            self.routing_paths.add(app_ecommerce_api_dirpath)

            plugin_template_paths.append(app_ecommerce_template_dirpath)
        else:
            # Include additional paths when resolving web requests
            self.routing_paths.add(os.path.join(self.contents_dirpath, 'pages'))
            self.routing_paths.add(os.path.join(self.contents_dirpath, 'api'))

        # Register plugin template directory paths
        self.register_templates(plugin_template_paths)
        route(None, f'/public/{self.name}', static_path=str(os.path.join(self.frontend_dirpath, 'static')))
        # app.available_models.update({
        #     "Product": Product
        # })

    async def on_request(self, request: PyonirRequest, app: PyonirApp):
        if request.method == 'POST': return
        cart_items = self.cartService.view_cart(request)
        app.TemplateEnvironment.globals['cart_items'] = cart_items
        pass


