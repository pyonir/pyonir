@filter.jinja:- content
title: Blogging on Pyonir
entries: $dir/pages/blogs?model=title,url,author,date:file_created_on
===
Welcome to the blog page.

Render your javascript components on the server using optimljs.

{% include 'components/listing.html' %}