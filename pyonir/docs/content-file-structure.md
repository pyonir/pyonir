# Metadata

Metadata defines structured information about a page. Pyonir supports three ways to declare metadata depending on how you want it exposed to templates.

---

## Top-Level Metadata

Metadata declared outside of a fenced block becomes a top-level property on the page.

Example:

```text
title: About
author: Jane Doe
category: Tutorials
reading_time: 5 min
```

Template usage:

```html
{{ page.title }}
{{ page.author }}
{{ page.category }}
{{ page.reading_time }}
```

This is the recommended approach for commonly used page properties such as `title`, `description`, and `template`.

---

## Grouped Metadata

Wrapping metadata in a fenced block groups it under the fence's language name.

Example:

```text
    ````yml
    author: Jane Doe
    category: Tutorials
    reading_time: 5 min
    ````
```

Template usage:

```html
{{ page.yml.author }}
{{ page.yml.category }}
{{ page.yml.reading_time }}
```

The fence language determines the namespace while also providing syntax highlighting in your editor.

---

## Aliased Metadata

A fenced block may optionally define an alias.

The alias becomes the namespace instead of the language name.

Example:

```text
    ````yml book
    author: Jane Doe
    category: Tutorials
    reading_time: 5 min
    ````
```

Template usage:

```html
{{ page.book.author }}
{{ page.book.category }}
{{ page.book.reading_time }}
```

This is useful when a page contains multiple metadata sections or when you want a more descriptive namespace.

---

## Example

A page may combine all three approaches.

```text

    title: My Library
    template: pages.html
    
    ````info
    site_name: Pyonir
    version: 1.0
    ````
    
    ````yml book
    author: Jane Doe
    category: Tutorials
    reading_time: 5 min
    ````
    
    ````md html.body
    # Welcome
    
    This page demonstrates multiple metadata sections.
    ````

```

Template usage:

```html
<h1>{{ page.title }}</h1>
<p>Site: {{ page.info.site_name }}</p>
<p>Author: {{ page.book.author }}</p>
<p>Category: {{ page.book.category }}</p>
<body>
{{ page.html.body }}
</body>
```

---

## Why Use Fenced Metadata?

Fenced metadata provides several benefits:

- IDE syntax highlighting.
- Logical grouping of related data.
- Multiple metadata sections using different formats.
- Custom namespaces through aliases.
- Easy extension by plugins without polluting the top-level page object.
````
