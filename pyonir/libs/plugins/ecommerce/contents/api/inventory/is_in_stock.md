@resolvers:
    GET.call: ecommerce.inventoryService.is_in_stock
===
Check whether the required quantity is available for a product.

Returns:
- bool: True if enough stock exists, False otherwise.
        