# Pyonir Web Framework

Pyonir is a static site generator and flat file web framework written in Python. It allows you to create dynamic websites using simple markdown files and a powerful plugin architecture.

### Install Pyonir

From pypi:

`pip install pyonir`


### Create a new project

Manually create a `main.py` file from an empty directory with the following values.

**Example**
```markdown
your_project/
    |─ __init__.py # makes this project a package
    └─ main.py     # entry point to your application
```

**Example main.py file**
```python
import pyonir
app = pyonir.init(__file__)
```

**Scaffold a demo web application from the cli:**

```bash
> pyonir init
```

This will generate the following directory structure

```md
your_project/
    ├─ backend/
    |  └─ README.md
    |  └─ __init__.py
    ├─ contents/
    |  ├─ pages/
    |     └─ index.md
    ├─ frontend/
    |  └─ README.md
    |  └─ pages.html
    └─ main.py
    └─ __init__.py
```

**Install plugins from the pyonir plugins registry on github**

```bash
> pyonir install plugin:<repo_owner>/<repo_name>#<repo_branch>
```

**Install themes from the pyonir theme registry on github**

```bash
> pyonir install theme:<repo_owner>/<repo_name>#<repo_branch>
```

### Configure Contents

Site content is stored in special markdown files within the contents directory. 
Each sub directory within the `contents` folder represents the `content type` for any contained markdown files.

### Content Types

Organizes a collection of files by specified type in a directory. Type directory can be named anything you want.
`pages`, `api`, and `configs` are reserved directory name used by the system but can override.

**Config Type: `contents/configs`**

Represents mutable site configurations that can change while app is running.
Override this directory name by setting `your_app.CONFIGS_DIRNAME`

**Page Type: `contents/pages`** 

Represents routes accessible from a URL. A file from `contents/pages/about.md` can be accessed from a URL of `https:0.0.0.0/about`
All pages files are served as `text/html` resources. You can configure your pages to be serverd from a different directory by overriding the `Site.PAGES_DIRNAME` default value.

Override this directory name by setting `your_app.PAGES_DIRNAME`

**API Type: `contents/api`**

Files within this folder represents API endpoints. Files here can define the response of the request and call python functions.
A file from `contents/api/new_post.md` can be accessed from a URL of `https:0.0.0.0/api/new_post`.
You can configure your api pages to be serverd from a different directory by overriding the `Site.API_DIRNAME` default value.

Override this directory name by setting `your_app.API_DIRNAME`

### Generate static site

```python
import pyonir
app = pyonir.init(__file__)

app.generate_static_website()
```

### Configure Route Controllers

Configuration based routing defined at startup. All routes live in one place — easier for introspection or auto-generation.
This allows flexibility for functions to be access from virtual routes and registered at startup.

```python
def demo_route(user_id: int = 5):
    # perform logic using the typed arguments passed to this function on request
    return f"user id is {user_id}"

routes: list['PyonirRoute'] = [
    ['/user/{user_id:int}', demo_route, ["GET"]],
]

# Define an endpoint routers
router: 'PyonirRouters' = [
    ('/api/demo', routes)
]
```

### Run Web server

Pyonir uses the starlette webserver by default to process web request. Below is an example of how to install a route
handler.

```python
import pyonir

def demo_route(user_id: int = 5):
    # perform logic using the typed arguments passed to this function on request
    return f"user id is {user_id}"

routes: list['PyonirRoute'] = [
    ['/user/{user_id:int}', demo_route, ["GET"]],
]

# Define an endpoint routers
router: 'PyonirRouters' = [
    ('/api/demo', routes)
]

app = pyonir.init(__file__)

app.run(routes=router)
```

### Configure Virtual Page Routes

**Virtual routes `.routes.md`**

A virtual route generates a page from aggregated data sources, giving you greater control over the request and response.
Just add `.routes.md` file in the `contents/pages` directory.

**JSON response** 

any pattern that begins with the default API name are automatically returning JSON.

```md
/api/some_data/{data_id:str}: 
    GET.response: application/json
    data: hello {request.path_param.data_id} world
```

results from request `http:0.0.0.0/api/some_data/a3b3c3`

```json
{
  "data": "hello a3b3c3 world"
}
```

**HTML response**

The `page` attribute value will be passed into the page request. The page url and slug are auto set from the request.
Any scalar values will be passed as the page contents value. Only GET requests permitted by default.

```md
/products/{tag:str}:
    title: Products grouped by tag.
    contents: Listing of all products grouped by tags.
    template: product-tags.html
    entries: $dir/../products?groupby={request.path_params[tag])}
```

**Server-sent events**

```md
/api/sse/user/notifications:
    GET.call: reference.path.to.sse.notifications.controller
    GET.headers.accept: text/event-stream
```

**Websockets**

```md
/api/ws/user/chat:
    GET.call: path.to.websocket.module
    GET.headers.accept: text/event-stream
```




### Configure Frontend

The `frontend` directory organizes your application themes. Each theme uses jinja template logic to generate data into
HTML. Theme templates are stored in `frontend/themes/{THEME_NAME}/layouts` directory.

### Configure Static Assets
...

### Configure Plugins
...