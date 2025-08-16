from pyonir.pyonir_types import PyonirRoute, PyonirRouters
from .demo_controller import demo_items, subscriber_model, subscriber_values


# Define routes
routes: list[PyonirRoute] = [
    ('/items', demo_items, ["GET"]),
    ('/items/{sample_id:int}', demo_items, ["GET"]),
    ('/subscribe_values', subscriber_values, ["POST"]),
    ('/subscribe_model', subscriber_model, ["POST"]),
]

# Define an endpoint routers
router: PyonirRouters = [
    ('/api/demo', routes)
]