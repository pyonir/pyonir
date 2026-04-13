
## Configure Route Controllers

Configuration based routing defined at startup. All routes live in one place — easier for introspection or auto-generation.
This allows flexibility for functions to be access from virtual routes and registered at startup.

When a file is discovered and file is within a configured api directory, the response will be JSON otherwise its HTML
When a file is not discovered and app has a configured Route method returns:
    None response = 404
    render(TXT) = 200 HTML
    render(JSON) = 200 JSON
    Any[data] = 200 JSON
    

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

## Run Web server

Pyonir uses the starlette webserver by default to process web request. Below is an example of how to install a route
handler.

```python
from pyonir import Pyonir

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

app = Pyonir(__file__)

app.run(routes=router)
```

