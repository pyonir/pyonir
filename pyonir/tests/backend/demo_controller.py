from pyonir.pyonir_types import PyonirRequest, PyonirApp
from pyonir.tests.backend.models.email_subscriber import EmailSubscriber

async def dynamic_lambda(request: PyonirRequest) -> str:
    return "hello battle rap forever!"

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

async def some_route(name: str = 'pyonir'):
    return f"hello router annotation {name}"

class DemoService:

    def __init__(self, app: PyonirApp):
        self.items = ['python','javascript']
        self.app = app

    @staticmethod
    def get_numbers(num: int):
        return 42, num or 88, 86

    def get_items(self):
        return self.items + ['purejs','optimljs']