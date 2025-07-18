@resolvers:
    GET.call: ecommerce.orderService.view_order_history
===
Display a list of past order IDs made by the user.

Returns:
    List[str]: A list of order identifiers.
        