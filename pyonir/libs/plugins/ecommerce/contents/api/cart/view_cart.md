@resolvers:
    GET.call: ecommerce.cartService.view_cart
===
Display the contents of a user's shopping cart.

Returns:
    List[Product]: A list of product instances in the cart.
        