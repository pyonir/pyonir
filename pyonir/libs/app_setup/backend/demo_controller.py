from pyonir.types import PyonirRequest
from .models.EmailSubscriber import EmailSubscriber


async def dynamic_lambda(request: PyonirRequest) -> str:
    return "hello battle rap forever yay"

async def demo_items(request: PyonirRequest, sample_id: int=99, version_id: str='0.1'):
    """Home route handler"""
    return f"Main app ITEMS route {sample_id}! {version_id}"

async def subscriber_model(subscriber: EmailSubscriber):
    """Demo takes request body as parameter argument"""
    print(subscriber)
    return subscriber

async def subscriber_values(email: str, subscriptions: list[str]):
    """Demo takes request body as parameter arguments"""
    print(email, subscriptions)
    return f"subscribing {email} to {subscriptions}"

async def some_route(request: PyonirRequest):
    return "hello router annotation"
