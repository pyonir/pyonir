@filter.jinja:- content, title
@filter.md:- content
order: $dir/../orders/paypal/{request.query_params.order_id}.json#data
title: Thank You {{page.order.customer.first_name}}!
===
Your order number: **{{request.query_params.order_id}}**

<section>
<article>
<h3>Contact Information</h3>
<p>{{page.order.customer.email_address}}</p>
<h3>Shipping Address</h3>
<p>{{page.order.shipping.name.full_name}}</p>
<p>{{page.order.shipping.address.address_line_1}}</p>
<p>{{page.order.shipping.address.admin_area_2}} {{page.order.shipping.address.admin_area_1}} {{page.order.shipping.address.postal_code}} {{page.order.shipping.address.country_code}}</p>
</article>
</section>
