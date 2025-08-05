# Pyonir Web Framework

A static website generator and flat file web framework written in Python.

### Install Pyonir

From pypi:

`pip install pyonir`


### Create a new project

Manually create a `main.py` file from an empty directory with the following values.

**Example**
```markdown
your_project/
    └─ main.py
```

**Example main.py file**
```python
import pyonir
app = pyonir.init(__file__)

app.run()
```

or scaffold a demo web application from the cli:

```bash
> pyonir-create
```

This will generate the following directory structure

```md
your_project/
    ├─ backend/
    ├─ contents/
    ├─ frontend/
    └─ main.py
```

### Configure Contents

Site content is stored in special markdown files within the contents directory. 
Each sub directory within the `contents` folder represents the `content type` for any contained markdown files.

### Content Types

Organizes a collection of files by specified types in a directory.

**Configs: `contents/configs`**

Represents mutable site configurations that can change while app is running.

**Pages: `contents/pages`** 

Represents routes accessible from a URL. A file from `contents/pages/about.md` can be accessed from a URL of `https:0.0.0.0/about`
All pages files are served as `text/html` resources. You can configure your pages to be serverd from a different directory by overriding the `Site.PAGES_DIRNAME` default value.

**API: `contents/api`**

Files within this folder represents API endpoints. Files here can define the response of the request and call python functions.
A file from `contents/api/new_post.md` can be accessed from a URL of `https:0.0.0.0/api/new_post`.
You can configure your api pages to be serverd from a different directory by overriding the `Site.API_DIRNAME` default value.


### Generate static site

```python
import pyonir
app = pyonir.init(__file__)

app.generate_static_website()
```

### Run Web server

Pyonir uses the starlette webserver by default.

```python
import pyonir
app = pyonir.init(__file__)

app.run(routes=[])
```

### Configure Virtual Page Routes

**Virtual routes**

A virtual route can generate a page from aggregated data sources and giving more control on request response.
Virtual routes can be defined within the `contents/pages` directory within a hidden `.routes.md` file.
virtual routes can return the following response types:

- HTML response
- JSON response
- WebSocket
- Sever-Sent Events
- Static file

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
/products/tags: 
    page:
        title: Products grouped by tags.
        contents: Listing of all products grouped by tags.
        template: product-tags.html
        entries: $dir/../products?groupby=tags
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
    GET.call: path/to/websocket.py#module
    GET.headers.accept: text/event-stream
```


### Configure Route Controllers

Configuration based routing defined at startup. All routes live in one place — easier for introspection or auto-generation.
This allows flexibility for functions to be access from virtual routes and registered at startup.

```python
def find_user(user_id: int):
    # perform logic using the typed arguments passed to this function on request
    pass

routes: list[PyonirRoute] = [
    ['/user/{user_id:int}', find_user, ["GET"]],
]
```

### Configure Frontend

The `frontend` directory organizes your application themes. Each theme uses jinja template logic to generate data into
HTML. Theme templates are stored in `frontend/themes/{THEME_NAME}/layouts` directory.

### Configure Static Assets
...

### Configure Plugins
...