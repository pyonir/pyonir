from dataclasses import dataclass
from pyonir.core import PyonirSchema


@dataclass
class EmailSubscriber(PyonirSchema):
    """
    Represents an email subscriber
    """
    email: str
    subscriptions: list[str]

    def validate_subscriptions(self):
        if not self.subscriptions:
            self._validation_errors.append(f"Subscription is required")

    def validate_email(self):
        import re
        if not re.match(r"[^@]+@[^@]+\.[^@]+", self.email):
            self._validation_errors.append(f"Invalid email address: {self.email}")
