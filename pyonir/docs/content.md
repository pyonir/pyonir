# Contents

The `contents` directory contains the data and content that powers your Pyonir application.
Content is stored as human-readable files, allowing your application to be managed without a database or specialized tooling.
Pyonir uses content directories to organize different types of application data.

## Common formats include:

- Markdown

Text-based configuration files

## Default Structure

```text
contents/
├── pages/       # Website pages and routes
│ └── index.md
├── api/         # API endpoint definitions
│ └── docs.md
└── configs/     # Application configuration
│ └── app.md
```

> Content directory names can be customized through Pyonir configuration.

---

# Content Types

Each directory inside `contents` represents a content type.

Content types define how Pyonir processes and exposes files.

## Pages

The `pages` directory contains website pages.

Example:

```text
contents/
└── pages/
    ├── index.md
    ├── about.md
    └── blog/
        └── post.md
```

Files automatically map to URLs:

```text
index.md        → /
about.md        → /about
blog/post.md    → /blog/post
```

See:

`docs/file-routing.md`

---

## API

The `api` directory contains API resources and endpoint definitions.

Example:

```text
contents/
└── api/
    └── users.md
```

A file can define API responses, connect to backend functions, and expose application data.

Example route:

```text
/api/users
```

See:

`docs/file-routing.md#api`

---

## Configs

The `configs` directory stores application configuration data.

Use configs for values that may change while the application is running.

Example:

```text
contents/
└── configs/
    └── site.yml
```

Configuration files can be accessed by your application and plugins.

See:

`docs/file-routing.md#configs`

---

# Content Files

Pyonir content files are designed to be:

* Human-readable
* Version-control friendly
* Easy to edit
* Easy for tools and AI assistants to understand

Common formats include:

* Markdown
* YAML
* JSON
* Text-based configuration files

---

# Working With Content

A typical workflow:

1. Create content files inside the appropriate directory.
2. Add metadata and content blocks.
3. Render content through templates or routes.
4. Deploy as a dynamic application or generate a static website.

