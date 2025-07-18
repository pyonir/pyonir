@filter.jinja:- content
title: Blogging on Pyonir
menu.group: primary
entries: $dir/pages/blogs?model=title,url,author,date:file_created_on
@routes:
    GET:-
        /revisions/{blog_id:str}/{version:int}
        /{blog_id:str}
===
Welcome to the blog page.

Render your javascript components on the server using optimljs.

{% include 'components/listing.html' %}