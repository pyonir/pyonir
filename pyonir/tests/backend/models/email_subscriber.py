from pyonir.core import PyonirSchema

class EmailSubscriber(PyonirSchema, table="email_subscribers", private_keys=["email"]):
    """ Represents an email subscriber """

    def __init__(self, email: str, subscriptions: list[str] = None):
        self.email: str = email
        self.subscriptions: list[str] = subscriptions

    def validate_subscriptions(self):
        if not self.subscriptions:
            self._errors.append(f"Subscription is required")

    def validate_email(self):
        import re
        if not re.match(r"[^@]+@[^@]+\.[^@]+", self.email):
            self._errors.append(f"Invalid email address: {self.email}")