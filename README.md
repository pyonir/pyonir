# Pyonir
[![PyPI Version](https://img.shields.io/pypi/v/pyonir)](https://pypi.org/project/pyonir/)
[![Python Version](https://img.shields.io/pypi/pyversions/pyonir)](https://pypi.org/project/pyonir/)
[![License](https://img.shields.io/github/license/pyonir/pyonir)](https://github.com/pyonir/pyonir/blob/main/LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/pyonir/pyonir?style=social)](https://github.com/pyonir/pyonir)

> A modern Python flat-file web framework with static site generation, file-based routing, and an AI-friendly project structure.


[Documentation](https://pyonir.dev) • [GitHub](https://github.com/pyonir/pyonir) • [PyPI](https://pypi.org/project/pyonir/)

---

## Why Pyonir?

Pyonir combines the simplicity of flat-file CMSs with the flexibility of a modern Python web framework.

* 📄 Markdown-first content
* 📁 File-based routing
* ⚡ Static site generation
* 🎨 Jinja2 templates
* 🔌 Plugin architecture
* 🎭 Theme support
* 🌐 API endpoints
* 🚀 No database required


---

## Installation

**Requirements**

* Python 3.9+

Install Pyonir:

```bash
> pip install pyonir
```

---

## Create a Project

1. Generate a starter application:

```bash
> pyonir init
```

2. Start the development server:

```bash
> python main.py
```

3. Open your browser:

```
http://localhost:5000
```

---

## Manual Setup

1. Create a `main.py` file:

```python
from pyonir import Pyonir

app = Pyonir(__file__)

app.run()
```

2. Create your first page:

```
contents/
└── pages/
    └── index.md
```

```markdown
title: Home
description: Welcome to Pyonir!
===

# Hello, Pyonir!

Your website is running.
```

Create a template:

```
frontend/
└── templates/
    └── pages.html
```

```html
<h1>{{ page.title }}</h1>

{{ page.contents }}
```

Run the server:

```bash
> python main.py
```

---

## Installing Plugins

```bash
> pyonir install plugin:<owner>/<repository>#<branch>
```

Example:

```bash
> pyonir install plugin:example/comments#main
```

---

## Installing Themes

```bash
pyonir install theme:<owner>/<repository>#<branch>
```

Example:

```bash
pyonir install theme:example/blog-theme#main
```
