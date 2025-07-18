from dataclasses import dataclass, field
from typing import List, Optional, Dict

from pyonir.types import AppCtx


@dataclass
class ProductVariation:
    """
    Represents a specific version of a product that differs from other versions by attributes
    """
    name: str
    cost: float = 0

@dataclass
class ProductInventory:
    """
    Represents a specific version of a product that differs from other versions by attributes
    """
    product_id: str
    variant_id: str
    variation: ProductVariation
    cost: float = 0


@dataclass
class Product:
    """
    Represents a product in the online shop.
    """
    product_id: str
    name: str
    price: float
    stock: int = 0
    description: str = ''
    variations: Optional[dict[str, list[ProductVariation]]] = field(default_factory=dict)
    images: list[str] = field(default_factory=list)
    file_name: str = ''
    inventory: dict = field(default_factory=dict)

    @property
    def sku(self) -> str:
        from pyonir.utilities import generate_base64_id
        return generate_base64_id(self.file_name).decode("utf-8")

    @staticmethod
    def generate_variant_sku(attributes: list) -> str:
        if not attributes: return ''
        return ",".join(attributes).replace(" ",'-')

    def generate_variants(self) -> tuple[str, dict, list]:
        """Generates product variants based on configured variations on product"""
        import itertools
        product_code = self.product_id
        variation_names = list(self.variations.keys())
        option_combinations = list(itertools.product(*(self.variations[k] for k in variation_names)))
        variant_columns = ','.join(variation_names)
        skus = []
        variant_matrix = {"column_order": variation_names}

        for combo in option_combinations:
            variation_values = [str(val.name) for val in combo]
            sku_cost = sum(getattr(val,'cost', 0) for val in combo)
            variant_value = Product.generate_variant_sku(variation_values)
            variant_sku = f"{product_code}|{variant_value}"
            # zip(variation_names, variation_values)
            skus.append(variant_sku)
            variant_data = dict(stock=-1, cost=sku_cost)
            variant_matrix[variant_value] = variant_data
            # skus.append((f"{product_code}|{variant_columns}|{variation_sku}", variant_data))

        return product_code, variant_matrix, skus



@dataclass
class CartItem(Product):
    quantity: int = 0
    attributes: list[ProductVariation] = field(default_factory=list)

    def __post_init__(self):
        # generate sku associated with attributes on cart item
        pass

@dataclass
class Address:
    """
    Represents a customers address
    """
    name: str
    street: str
    city: str
    state: str
    zip: int
    country: str


@dataclass
class Shipping:
    """
    Represents shipping details for an order.
    """
    full_name: str
    address_line1: str
    address_line2: Optional[str]
    city: str
    state: str
    postal_code: str
    country: str
    phone_number: Optional[str] = None
    delivery_instructions: Optional[str] = None


@dataclass
class Customer:
    """
    Represents a customer
    """
    email: str
    first_name: str
    last_name: str
    phone: str = ''


@dataclass
class Order:
    """
    Represents an order placed by a customer
    """
    order_id: str
    status: str  # e.g., 'pending', 'shipped', 'delivered', 'cancelled'
    gateway: str  # e.g, 'paypal', 'stripe', 'square'
    order_items: list
    shipping: dict = field(default_factory=dict)
    customer: Customer = field(default_factory=dict)
    currency_code: str = 'USD'
    subtotal: float = 0
    tax_total: float = 0
    shipping_total: float = 0
    discount_total: float = 0
    file_name: str = ''

    @staticmethod
    def from_file(file_path: str, app_ctx: AppCtx):
        from pyonir.utilities import get_all_files_from_dir
        return get_all_files_from_dir(file_path, app_ctx, entry_type=Order)

    def save(self, orders_dirpath) -> bool:
        """Saves an order to the filesystem in json format"""
        if not self.order_id: return False
        import os
        from pyonir.utilities import create_file
        filename = str(self.order_id)
        return create_file(os.path.join(orders_dirpath,self.gateway, filename+".json"), self.__dict__, True)