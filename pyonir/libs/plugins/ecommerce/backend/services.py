import os
from typing import List, Optional, Any, Dict
from enum import StrEnum

from pyonir.libs.plugins.ecommerce import Ecommerce
from pyonir.libs.plugins.ecommerce.backend.models import Product, CartItem, Order, Customer
from pyonir.types import PyonirRequest, PyonirApp

Id: str = ''
Qty: int = 0
Items: [Id, Qty] = []

def resolver(params=None):
    from pyonir import Site
    if not params:
        params = {}
    def resolver_wrapper(func):
        print('Hello API: '+func.__name__, params)
    return resolver_wrapper

class OrderStatus(StrEnum):
    OPEN = 'open'
    SHIPPED = 'shipped'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'

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
        self.product_variant_dirpath = os.path.join(ecommerce_app.contents_dirpath, 'product_variants')
        self.app_variations_dirpath = os.path.join(app_ecommerce_contents_dirpath, 'variations')
        self.app_product_variant_dirpath = os.path.join(app_ecommerce_contents_dirpath, 'product_variants')

        self.all_products = self.shop_app.query_files(
            self.products_dirpath,
            self.shop_app.app_ctx,
            model_type=Product
        )

    def generate_product_variant(self, product_id: str) -> Optional[Product]:
        product = getattr(self.all_products, product_id)
        if product and not product.variations:
            variant_id, variant_data, skus = product.generate_variants()
            self.add_product_variant(variant_id, variant_data)
            return skus

    def add_product(self, product_id: str, product_data: dict) -> str:
        """
        Add a new product to the product catalog.
        """
        new_product_path = os.path.join(self.products_dirpath, product_id)
        new_product = self.shop_app.insert(new_product_path, product_data)
        print(f'New product created! {product_id}')
        return f'New product created! {product_id}'


    def add_product_variant(self,  variant_id: str, variant_data: dict = None) -> str:
        """
        Add a new product variant into the inventory catalog.
        """
        new_product_variant_path = os.path.join(self.product_variant_dirpath, variant_id)+'.md'
        new_product = self.shop_app.insert(new_product_variant_path, variant_data)
        print(f'New product variant created! {variant_id}')
        return f'New product variant created for {variant_id}!'


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
        self.all_products = self.shop_app.query_files(
            self.products_dirpath,
            self.shop_app.app_ctx,
            model_type=Product
        )
        products = list(self.all_products.__dict__.values())
        return products

    def get_product(self, product_id: str) -> Optional[Product]:
        """
        Retrieve a specific product by its ID.

        Returns:
            Product or None: The product instance if found, else None.
        """
        product = getattr(self.all_products, product_id)
        if not product.inventory:
            self.generate_product_variant(product.product_id)
        return product

    # def get_product_page(self, product_id: str, req: PyonirRequest) -> dict[str, Product]:
    #     """Returns a product as a page for UI display"""
    #     product = self.get_product(product_id)
    #     req.file.data.update({"product": product})


class InventoryService:

    def __init__(self, ecommerce_app: Ecommerce, iapp: PyonirApp):
        # build alternate path for contents and templates
        """
        Initialize an inventory store to manage product stock levels.
        """
        self.shop_app = ecommerce_app
        self.inventory_dirpath = os.path.join(ecommerce_app.contents_dirpath, 'inventory')
        pass

    def add_stock(self, product_id: str, quantity: int) -> None:
        """
        Add new stock for a given product.

        Parameters:
        - product_id: The ID of the product.
        - quantity: Number of units to add.
        """
        pass

    def reduce_stock(self, product_id: str, quantity: int) -> None:
        """
        Deduct a specific quantity of stock for a product.

        Parameters:
        - product_id: The ID of the product.
        - quantity: Number of units to deduct.
        """
        pass

    def get_stock(self, product_id: str, variant_atr: str) -> dict:
        """
        Get the current stock level for a product.

        Returns:
        - int: Current quantity in stock.
        """
        product = getattr(self.shop_app.productService.all_products, product_id)
        variant = product.inventory.get(variant_atr, None)
        variant_cost = variant.get('cost') if variant else 0
        return {"price": product.price + variant_cost,
                "base_price": product.price,
                "product_id": product_id,
                **variant} if variant else {"stock": product.stock}

    def is_in_stock(self, product_id: str, required_quantity: int) -> bool:
        """
        Check whether the required quantity is available for a product.

        Returns:
        - bool: True if enough stock exists, False otherwise.
        """
        pass

    def list_stock_levels(self) -> dict:
        """
        Return a dictionary mapping product IDs to their current stock levels.

        Returns:
        - dict: {product_id: stock_quantity}
        """
        pass


class UserService:
    def __init__(self, ecommerce_app: Ecommerce, iapp: PyonirApp = None): self.shop_app = ecommerce_app

    def register_user(self, user_id: str, username: str, email: str) -> None:
        """
        Register a new user for the shop.
        """
        pass


class CartService:
    session_key: str = 'ecart'

    def __init__(self, ecommerce_app: Ecommerce, iapp: PyonirApp = None):
        self.shop_app = ecommerce_app
        self.productService = ecommerce_app.productService

    async def add_to_cart(self, request: PyonirRequest, product_id: str, quantity: int, attributes: list = []) -> [CartItem]:
        """
        Add a specified quantity of a product to the user's shopping cart.
        """
        attributes = Product.generate_variant_sku(attributes)
        new_item = [product_id, quantity, attributes]
        curr_cart: Items = request.server_request.session.get(self.session_key, [])
        has_item = [[id, qt, attrs] for id, qt, attrs in curr_cart if id == product_id and  attrs == attributes] if curr_cart else 0
        if has_item:
            has_item = has_item.pop(0)
            curr_cart.remove(has_item)
            new_item = [product_id, quantity + has_item[1], attributes]
        curr_cart.append(new_item)
        request.server_request.session[self.session_key] = curr_cart
        print('cartService', curr_cart)
        return curr_cart

    def remove_from_cart(self, product_id: str, request: PyonirRequest) -> None:
        """
        Remove a product from the user's shopping cart.
        """
        curr_cart: [CartItem] = request.server_request.session.get(self.session_key, [])
        has_item = [[id, qty, attrs] for id, qty, attrs in curr_cart if id == product_id]
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
        cart_products: list = request.server_request.session.get(self.session_key, [])
        cart_items = []
        for pid, qty, attrs in cart_products:
            product = getattr(self.productService.all_products, pid)
            cart_item = CartItem(**product.__dict__)
            cart_item.quantity = qty
            cart_item.attributes = attrs.split(',') if attrs else []
            if attrs and cart_item.inventory:
                cost = cart_item.inventory.get(attrs, {}).get('cost', 0)
                cart_item.price += cost
                cart_item.stock = cart_item.inventory.get(attrs,{}).get('stock')
            cart_items.append(cart_item)

        return cart_items


class OrderService:

    def __init__(self, ecommerce_app: Ecommerce, iapp: PyonirApp=None):
        from .gateways import PayPalClient, SquareClient
        self.gateway = 'paypal'
        self.shop_app = ecommerce_app
        self.orders_dirpath = os.path.join(ecommerce_app.contents_dirpath, 'orders')
        paypal_configs = ecommerce_app.configs.env.get(self.gateway,{}).get('sandbox' if ecommerce_app.app.is_dev else 'prod')
        square_configs = ecommerce_app.configs.env.get('square')
        self.paypalClient: PayPalClient = PayPalClient(client_secret=paypal_configs.get('secret'), client_id=paypal_configs.get('client_id'), sandbox=ecommerce_app.app.is_dev)
        self.squareClient: SquareClient = SquareClient(env_configs=square_configs, sandbox=ecommerce_app.app.is_dev)

    def _orders(self, gateway: str) -> Dict[str, Order]:
        from pyonir.utilities import get_all_files_from_dir, process_contents
        return process_contents(os.path.join(self.orders_dirpath, gateway), app_ctx=self.shop_app.app_ctx, file_model=Order)


    def _save_order(self, order_response: dict) -> str:
        order = Order(
            order_id = order_response.get('order_id'),
            status = order_response.get('status'),  # e.g., 'pending', 'shipped', 'delivered', 'cancelled'
            gateway = self.gateway,  # e.g, 'paypal', 'stripe', 'square'
            order_items = order_response.get('order_items') or order_response.get('line_items')
        )
        order_saved = order.save(self.orders_dirpath)
        return order.order_id if order_saved else f"Error saving {self.gateway} order"

    def find_order(self, order_id: str) -> Order | None:
        orders = self._orders(self.gateway)
        order = getattr(orders, order_id, None)
        return order

    @resolver(params={'GET':{'redirect':'/foo', 'args':{'order_id': '{request.path}'}}})
    def create_order(self, order_id: str) -> Order:
        """
        Creates an official order confirmed from gateway and user.
        """

        paypal_order = self.paypalClient.capture_order(order_id)
        # open existing capture
        current_order = self.find_order(order_id)
        # update order status
        if current_order:
            paypal_shipping = paypal_order.get('purchase_units')[0].get('shipping')
            paypal_customer = paypal_order.get('payer')
            customer = Customer(email=paypal_customer['email_address'], first_name=paypal_customer['name']['given_name'], last_name=paypal_customer['name']['surname'])
            current_order.status = paypal_order.get('status')
            current_order.shipping = paypal_shipping
            current_order.customer = customer
            current_order.save(self.orders_dirpath)
        return current_order

    def checkout(self, order: dict, gateway: str) -> dict[str, Any]:
        """
        Process the user's cart for checkout.

        Returns:
            dict: A generated order ID upon successful checkout.
        """
        if gateway == 'paypal':
            self.gateway = 'paypal'
            order_created, order_response = self.paypalClient.create_checkout(**order)
        if gateway == 'square':
            self.gateway = 'square'
            order_created, order_response = self.squareClient.create_checkout_link(**order)
        if order_created:
            order_response['status'] = OrderStatus.OPEN
            self._save_order(order_response)
        return order_response

    @resolver
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

