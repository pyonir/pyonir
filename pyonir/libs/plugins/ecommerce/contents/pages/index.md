title: Shop Home
menu.group: primary
entries: $dir/../products?model=name,url,price,images,product_id
product: $dir/../products/{{request and request.query_params.product_id}}.md
template: home-javascript.html
@routes:-
    /{product_id:str}
    /{product_id:str}/{variant:int}
=== head.js
<script type="importmap">
      {
        "imports": { "optiml": "http://localhost:3000/index.js" }
      }
</script>

