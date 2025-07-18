title: Shop Home
menu.group: primary
entries: $dir/../products?model=name,url,price,images,product_id
template: ecommerce-home.html
@routes:
    /products/{product_id:str}: ecommerce.productService.get_product_page
    /products/tags/{product_tag:str}: entries: $dir/../products
=== head.js
<script type="importmap">
{
"imports": { "optiml": "http://localhost:3000/index.js" }
}
</script>
===
When using server routes, the request.path_params variable is available to access path parameters to query product data.
however, if you are using dynamic wildcard routes using the @routes within index.md will provide dynamic routing capabilities.