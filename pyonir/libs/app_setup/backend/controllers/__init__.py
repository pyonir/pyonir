from pyonir.types import PyonirRequest


async def demo_items(req: PyonirRequest, sample_id: int):
    """Home route handler"""
    return f"Main app ITEMS route {sample_id}!"


# Define routes
routes = [
    ['/items', demo_items, ["GET"]],
    ['/items/{sample_id:int}', demo_items, ["GET"]],
]

# Define an endpoint
endpoints = [
    ('/api/demo', routes)
]
