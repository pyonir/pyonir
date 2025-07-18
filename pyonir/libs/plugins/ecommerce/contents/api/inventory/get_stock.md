@resolvers:
    GET.call: ecommerce.inventoryService.get_stock
===
Get the current stock level for a product.

Returns:
- int: Current quantity in stock.
        