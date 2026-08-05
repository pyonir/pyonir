# Frontend

The `frontend` directory contains the presentation layer of a Pyonir application, including templates, themes, styles, and static assets.

Pyonir supports both simple template-based applications and full theme-based applications.

## Default Structure

```text
frontend/
├── templates/              # Default templates (no theme required)
├── themes/
│   └── <theme-name>/
│       ├── templates/      # Theme templates
│       ├── styles/         # Theme stylesheets
│       └── assets/         # Theme assets
├── static/                 # Application static assets
└── public/                 # Shared/vendor assets
```

> Directory names and locations can be customized through Pyonir configuration.

---

## Templates

The `templates` directory contains Jinja templates used to render pages.

When a theme is not configured, Pyonir uses:

```text
frontend/templates/
```

Example:

```text
frontend/
└── templates/
    ├── pages.html
    ├── post.html
    └── user/
        └── profile.html
```

Templates receive page data and application context for rendering dynamic content.

---

## Themes

Themes provide an optional layer for organizing templates and visual assets.

A theme can include:

```text
themes/
└── blog/
    ├── templates/
    ├── styles/
    └── assets/
```

When a theme is enabled, Pyonir uses the theme's templates and assets instead of the default frontend templates.

Themes can be packaged and shared as reusable designs.

---

## Static Assets

Static asset directories contain files served directly to the browser.

Common examples:

* CSS
* JavaScript
* Images
* Fonts
* Icons

Default locations:

```text
frontend/
├── static/
└── public/
```

Applications may customize static asset paths to match their deployment requirements.

---

## Recommended Usage

Simple application:

```text
frontend/
└── templates/
    └── pages.html
```

Application with a custom theme:

```text
frontend/
└── themes/
    └── my-theme/
        ├── templates/
        ├── styles/
        └── assets/
```

Application with shared assets:

```text
frontend/
├── static/
└── public/
```

---

For advanced configuration, see the Pyonir documentation:

* Themes
* Templates
* Static Assets
* Configuration
