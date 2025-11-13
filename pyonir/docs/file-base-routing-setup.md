## File based Routes (Optional) 

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
