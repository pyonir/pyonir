@filter.jinja:- content
title: Shop Home
menu.group: primary
entries: $dir/../products
product: $dir/../products/{{request and request.query_params.product_id}}.md
template: home.html
@routes:
    /{product_id: str}
    /{product_id: str}/{version: int}
===

