import unittest
from dataclasses import dataclass, field
from pyonir.core import PyonirSchema
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
# from models import Base, User as UserORM
# from user_model import User  # Your immutable dataclass User

@dataclass(frozen=True)
class DemoModel(PyonirSchema):
    """
    Represents an email subscriber
    """
    email: str
    name: str
    age: int
    subscriptions: list[str] = field(default_factory=list)

    def validate_age(self) -> bool:
        if not (18 <= self.age <= 100):
            self._validation_errors.append("Age must be between 18 and 100")
            raise ValueError("Age must be between 18 and 100")

    def validate_subscriptions(self):
        if not self.subscriptions:
            self._validation_errors.append(f"Subscription is required")

    def validate_email(self):
        import re
        if not re.match(r"[^@]+@[^@]+\.[^@]+", self.email):
            self._validation_errors.append(f"Invalid email address: {self.email}")

class TestUserModel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Setup in-memory database for all tests."""
        # cls.engine = create_engine("sqlite:///:memory:", echo=False)
        # Base.metadata.create_all(cls.engine)
        # cls.SessionLocal = sessionmaker(bind=cls.engine)
        pass

    def setUp(self):
        """Start a new session before each test."""
        # self.session = self.SessionLocal()
        pass

    def tearDown(self):
        """Rollback and close session after each test."""
        # self.session.rollback()
        # self.session.close()
        pass

    def test_create_user(self):
        """Test creating a user and saving it in the database."""
        user = DemoModel.create(name="Alice", email="alice@example.com", age=25)
        # self.assertIsNotNone(user.id)
        self.assertEqual(user.name, "Alice")
        self.assertFalse(user._deleted)

    # def test_get_user(self):
    #     """Test fetching a user by ID."""
    #     created = User.create(self.session, name="Bob", email="bob@example.com", age=30)
    #     fetched = User.get(self.session, created.id)
    #     self.assertIsNotNone(fetched)
    #     self.assertEqual(fetched.name, "Bob")

    def test_patch_user(self):
        """Test patching a user (immutable copy)."""
        user = DemoModel.create(name="Carol", email="carol@example.com", age=28)
        patched = user.patch(name="Carol Updated")
        self.assertNotEqual(user, patched)  # New instance
        self.assertEqual(patched.name, "Carol Updated")
        self.assertEqual(user.name, "Carol")  # Original unchanged

    def test_update_user(self):
        """Test updating a user in the database."""
        user = DemoModel.create(name="Dan", email="dan@example.com", age=32)
        updated = user.update(age=33)
        self.assertEqual(updated.age, 33)
        self.assertNotEqual(user.age, updated.age)

    def test_delete_user(self):
        """Test deleting a user (soft delete)."""
        user = DemoModel.create(name="Eve", email="eve@example.com", age=29)
        deleted_user = user.delete()
        self.assertTrue(deleted_user._deleted)

    # def test_session_roundtrip(self):
    #     """Test storing and restoring user from session."""
    #     user = User.create(name="Frank", email="frank@example.com", age=40)
    #     session_data = user.to_session()
    #     restored = User.from_session(session_data)
    #     self.assertEqual(restored.name, user.name)
    #     self.assertEqual(restored.email, user.email)
    #     self.assertEqual(restored.id, user.id)

    def test_invalid_email_validation(self):
        """Test that invalid email raises validation error."""
        with self.assertRaises(ValueError):
            DemoModel(name="BadEmail", email="not-an-email", age=25)  # Validation in __post_init__

    def test_invalid_age_validation(self):
        """Test that invalid age raises validation error."""
        with self.assertRaises(ValueError):
            DemoModel(name="Young", email="young@example.com", age=10)

if __name__ == "__main__":
    unittest.main()
