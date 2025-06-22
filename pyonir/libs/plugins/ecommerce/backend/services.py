import dataclasses, os
from typing import List, Optional
from pyonir.libs.plugins.ecommerce import Ecommerce
from pyonir.libs.plugins.ecommerce.backend.models import Product, CartItem
from pyonir.types import PyonirRequest, PyonirApp, PyonirCollection

Id: str = ''
Qty: int = 0
Items: [Id, Qty] = []

class ProductService:

    def __init__(self, ecommerce_app: Ecommerce, iapp: PyonirApp):
        # build alternate path for contents and templates
        self.shop_app = ecommerce_app
        app_ecommerce_contents_dirpath = os.path.join(iapp.plugins_dirpath, ecommerce_app.module, 'contents')

        # Setup products dirpaths
        self.products_dirpath = os.path.join(ecommerce_app.contents_dirpath, 'products')
        self.app_products_dirpath = os.path.join(app_ecommerce_contents_dirpath, 'products')

        # Setup variation dirpaths
        self.variations_dirpath = os.path.join(ecommerce_app.contents_dirpath, 'variations')
        self.app_variations_dirpath = os.path.join(app_ecommerce_contents_dirpath, 'variations')


    def add_product(self, product_id: str, name: str, price: float, description: str) -> str:
        """
        Add a new product to the catalog.
        """
        # product = Product(product_id, name, price, stock)
        # print(f'New product created! {product.name}')
        # return f'New product created! {product.name}'
        print(f'New product created! {name}')
        return f'New product created! {name}'


    def remove_product(self, product_id: str) -> None:
        """
        Remove a product from the catalog using its product ID.
        """
        pass

    def update_stock(self, product_id: str, new_stock: int) -> None:
        """
        Update the stock quantity of an existing product.
        """
        pass

    def list_products(self) -> List[Product]:
        """
        Return a list of all products available in the catalog.

        Returns:
            List[Product]: A list of product instances.
        """
        pass

    def get_product(self, product_id: str) -> Optional[Product]:
        """
        Retrieve a specific product by its ID.

        Returns:
            Product or None: The product instance if found, else None.
        """
        all_products = self.shop_app.collect_dir_files(self.shop_app.app_products_dirpath, self.shop_app.files_ctx)
        return getattr(all_products, product_id)
        # product = Product(product_id, 'fooname', 7, 'just a demo drink')
        # return product


class UserService:
    def __init__(self, ecommerce_app: Ecommerce, iapp: PyonirApp = None): self.shop_app = ecommerce_app

    def register_user(self, user_id: str, username: str, email: str) -> None:
        """
        Register a new user for the shop.
        """
        pass

@dataclasses.dataclass
class CartService:
    session_key: str = 'ecart'

    def __init__(self, ecommerce_app: Ecommerce, iapp: PyonirApp = None):
        self.shop_app = ecommerce_app
        self.productService = ecommerce_app.productService

    async def add_to_cart(self, product_id: str, quantity: int, request: PyonirRequest) -> [CartItem]:
        """
        Add a specified quantity of a product to the user's shopping cart.
        """
        new_item = [product_id, quantity]
        curr_cart: Items = request.server_request.session.get(self.session_key, [])
        has_item = [[id, qt] for id, qt in curr_cart if id == product_id] if curr_cart else 0
        if has_item:
            has_item = has_item.pop(0)
            curr_cart.remove(has_item)
            new_item = [product_id, quantity + has_item[1]]
        curr_cart.append(new_item)
        request.server_request.session[self.session_key] = curr_cart
        print('cartService', curr_cart)
        return curr_cart

    def remove_from_cart(self, product_id: str, request: PyonirRequest) -> None:
        """
        Remove a product from the user's shopping cart.
        """
        curr_cart: [CartItem] = request.server_request.session.get(self.session_key, [])
        has_item = [[id, qty] for id, qty in curr_cart if id == product_id]
        if has_item:
            curr_cart.remove(has_item.pop(0))
            request.server_request.session[self.session_key] = curr_cart
        pass

    def view_cart(self, request: PyonirRequest) -> List[Product]:
        """
        Display the contents of a user's shopping cart.

        Returns:
            List[Product]: A list of product instances in the cart.
        """
        # list[product_id, product_qty]
        cart_products: list = request.server_request.session.get(self.session_key, [])
        cart_ids = [pid for pid, qty in cart_products]

        def filter_fn(item):
            if not item.product_id in cart_ids: return
            item_qty = next((qty for pid,qty in cart_products if item.product_id == pid), None)
            item.quantity = item_qty
            return item

        if cart_products:
            all_products = PyonirCollection.query(self.productService.products_dirpath,
                                                  app_ctx=self.shop_app.app_ctx, data_model=CartItem)
            product_list = all_products.where(filter_fn)
            # product_list = all_products.where('product_id','in',[pid for pid, qty in cart_products])
            return product_list
        return []

class OrderService:
    def __init__(self, ecommerce_app: Ecommerce, iapp: PyonirApp=None): self.shop_app = ecommerce_app

    def checkout(self, user_id: str) -> str:
        """
        Process the user's cart for checkout.

        Returns:
            str: A generated order ID upon successful checkout.
        """
        pass

    def view_order_history(self, user_id: str) -> List[str]:
        """
        Display a list of past order IDs made by the user.

        Returns:
            List[str]: A list of order identifiers.
        """
        pass

    def cancel_order(self, user_id: str, order_id: str) -> None:
        """
        Cancel an existing order and restock the items.
        """
        pass


class PaymentService:
    def __init__(self, ecommerce_app: Ecommerce, iapp: PyonirApp=None): self.shop_app = ecommerce_app

    def process_payment(self, user_id: str, payment_info: dict) -> bool:
        """
        Handle payment processing using provided payment details.

        Returns:
            bool: Whether the payment was successful.
        """
        pass


class ReviewService:
    def __init__(self, ecommerce_app: Ecommerce, iapp: PyonirApp=None): self.shop_app = ecommerce_app

    def leave_review(self, user_id: str, product_id: str, rating: int, comment: str) -> None:
        """
        Allow a user to leave a review and rating for a product.
        """
        pass

