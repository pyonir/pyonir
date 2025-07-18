@filter.pyformat:- @resolvers.GET.args.order_id, @resolvers.GET.redirect
@resolvers.GET:
    args: 
        order_id: {request.query_params.token}
    call: ecommerce.orderService.create_order
    redirect: /my-shop/thank-you?order_id={request.query_params.token}
===