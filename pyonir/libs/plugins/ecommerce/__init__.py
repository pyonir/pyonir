import os

from pyonir.types import IPlugin, PyonirApp, PyonirRequest, PyonirPlugin
from .backend.filters import babelmoney


class Ecommerce(PyonirPlugin):
    endpoint = '/my-shop'

    def __init__(self, app: PyonirApp):
        """
        Initialize the online shop and compose service modules.
        """
        from pyonir.libs.plugins.ecommerce.backend.services import ProductService, UserService, CartService, OrderService, PaymentService
        self.FRONTEND_DIRNAME = 'templates'
        super().__init__(app, __file__)

        # Setup services
        self.productService = ProductService(self, app)
        self.userService = UserService(self, app)
        self.cartService = CartService(self, app)
        self.orderService = OrderService(self, app)
        self.paymentService = PaymentService(self, app)
        app.TemplateEnvironment.add_filter(babelmoney)

        # build alternate path for contents and templates
        app_ecommerce_template_dirpath = os.path.join(app.plugins_dirpath, self.module, 'templates')
        plugin_ecommerce_template_dirpath = self.frontend_dirpath

        # Include additional paths when resolving web requests
        self.routing_paths.add(os.path.join(self.contents_dirpath, 'pages'))
        self.routing_paths.add(os.path.join(self.contents_dirpath, 'api'))

        # Register plugin template directory paths
        self.register_templates([app_ecommerce_template_dirpath, plugin_ecommerce_template_dirpath])

        # copy demo shop pages into site on startup
        # if False:
        #     self.install_directory(
        #         os.path.join(os.path.dirname(__file__), 'contents'),
        #         os.path.join(app_ecommerce_contents_dirpath)
        #     )
        #     self.install_directory(
        #         os.path.join(os.path.dirname(__file__), 'templates'),
        #         os.path.join(app_ecommerce_template_dirpath)
        #     )

    async def on_request(self, request: PyonirRequest, app: PyonirApp):
        if request.method == 'POST': return
        cart_items = self.cartService.view_cart(request)
        app.TemplateEnvironment.globals['cart_items'] = cart_items #[f'cart has {len(cart_items)} items']
        pass


