@resolvers:
    GET.call: ecommerce.inventoryService.list_stock_levels
===
Return a dictionary mapping product IDs to their current stock levels.

Returns:
- dict: {product_id: stock_quantity}
        