@resolvers:
    GET.call: ecommerce.inventoryService.reduce_stock
===
Deduct a specific quantity of stock for a product.

Parameters:
- product_id: The ID of the product.
- quantity: Number of units to deduct.
        