@filter.jinja:- content
title: Blogging on Pyonir
menu.group: primary
entries: $dir/pages/blogs?limit=3&model=title,url,author,date:file_created_on
===
Welcome to the blog page.

Render your javascript components on the server using optimljs.

{% include 'components/listing.html' %}