from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class ProductVariation:
    """
    Represents a specific version of a product that differs from other versions by attributes
    """
    name: str
    cost: float = 0


@dataclass
class Product:
    """
    Represents a product in the online shop.
    """
    # _mapper = {"product_id": "file_name"}
    product_id: str
    name: str
    price: float
    description: str = ''
    variations: dict[str, list[ProductVariation]] = field(default_factory=dict)
    images: list[str] = field(default_factory=list)

    @property
    def sku(self) -> str:
        """
        Dynamically generate SKU by joining attribute values in alphabetical key order.
        Example: {"color": "red", "size": "M"} → "red-m"
        """
        # Sort keys for consistent order, lowercase values
        parts = [self.variations[key].lower() for key in sorted(self.variations.keys())]
        return "-".join(parts)


@dataclass
class CartItem(Product):
    quantity: int = 0
    attributes: list[ProductVariation] = field(default_factory=list)


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
    phone: str
    first_name: str
    last_name: str


@dataclass
class Order:
    """
    Represents an order placed by a customer
    """
    customer_id: str
    transaction_id: str
    status: str  # e.g., 'pending', 'shipped', 'delivered', 'cancelled'
    gateway: str  # e.g, 'paypal', 'stripe', 'square'
    checkout_url: str
    order_created: str
    subtotal: float
    tax_total: float
    shipping_total: float
    discount_total: float
    currency_code: str
    order_items: list
    shipping: Shipping
