product_id: ${file_name}
name: Pyonir Tee
price: 15
images:- 
    https://mms-images.out.customink.com/mms/images/catalog/18636f421a51687be8b9242cde60da03/colors/176139/views/alt/front_large.png
    https://mms-images.out.customink.com/mms/images/catalog/8beca5c25b2adfd6dc22b69712e9ec42/colors/176113/views/alt/front_large.png
    https://mms-images.out.customink.com/mms/images/catalog/3c753355d220b536c47c12c8849118fd/colors/176178/views/alt/front_large.png
variations:
    sizes:- $dir/../variations/sizes.md#data.sizes
    colors:- $dir/../variations/colors.md#data.colors
    styles:- $dir/../variations/shirts.md#data.shirts
inventory: $dir/product_variants/{file_name}.{file_ext}
===
Product Variation orders matter when generating product variants. 
Variations skus are generated based on order of variation names.