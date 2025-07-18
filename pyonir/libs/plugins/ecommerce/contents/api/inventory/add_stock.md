@resolvers:
    GET.call: ecommerce.inventoryService.add_stock
===
Add new stock for a given product.

Parameters:
- product_id: The ID of the product.
- quantity: Number of units to add.
        