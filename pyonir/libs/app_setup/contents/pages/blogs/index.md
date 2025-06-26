@filter.jinja:-content
title: Blogging on Pyonir
menu.group: primary
entries: $dir/pages/blogs/*
@routes:
    GET:-
        /revisions/{blog_id:str}/{version:int}
        /{blog_id:str}
===
Welcome!
{% include 'components/listing.html' %}