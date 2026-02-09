import os

from pyonir.tests.conftest import PyonirMocks
from pyonir.core.authorizer import (
    PyonirUser,
    PyonirUserMeta,
    PermissionLevel,
    INVALID_EMAIL_MESSAGE,
    INVALID_PASSWORD_MESSAGE,
)

valid_credentials = {"email": "test@example.com", "password": "secure123", "flow": "session"}


def test_user_credentials(request_input):
    """RequestInput.from_dict handles missing email by reporting the invalid-email message."""
    request_input.email = ""  # Simulate missing email
    request_input._errors = []
    request_input.validate_email()
    assert len(request_input._errors) >= 1
    assert INVALID_EMAIL_MESSAGE in request_input._errors[0]


def test_user_from_dict(mock_data):
    """Creating a PyonirUser from the fixture data provided by conftest.PyonirMocks."""
    user = PyonirUser(meta=mock_data, uid="test-uid")
    # PyonirUser.email property reads from meta.email
    assert user.email == mock_data["email"]
    assert isinstance(user.meta, PyonirUserMeta)


def test_from_fixture_data_directly():
    """Build a user directly from the shared fixture data and assert key fields."""
    user = PyonirUser(meta=PyonirMocks.user_data, uid="test-uid")
    assert isinstance(user, PyonirUser)
    assert user.email == PyonirMocks.user_data["email"]
    # PyonirUser stores username on meta
    assert user.meta.username == PyonirMocks.user_data.get("username", "")
    assert isinstance(user.meta, PyonirUserMeta)
    assert getattr(user.meta, "first_name", None) == PyonirMocks.user_data.get("first_name")


def test_permissions_after_load():
    # Use a role that exists in Roles to get deterministic permissions
    fixture = dict(PyonirMocks.user_data)
    fixture["role"] = "contributor"
    user = PyonirUser(meta=fixture, uid="test-uid")

    # contributor role should allow read & write, but not admin
    assert user.has_perm(PermissionLevel.READ)
    assert user.has_perm(PermissionLevel.WRITE)
    assert not user.has_perm(PermissionLevel.ADMIN)


def test_meta_contains_password_field():
    # Ensure meta fields include password from fixture when present
    md = dict(PyonirMocks.user_data)
    md["password"] = "supersecret"
    user = PyonirUser(meta=md, uid="test-uid")
    # meta is a PyonirUserMeta instance and should expose the password attribute
    assert getattr(user.meta, "password", None) == "supersecret"


# RequestInput tests using the real RequestInput validators — mutate the shared instance for each test

def test_valid_signin(request_input):
    request_input.email = valid_credentials["email"]
    request_input.password = valid_credentials["password"]
    request_input._errors = []
    # explicitly re-run validators to be deterministic
    request_input.validate_email()
    request_input.validate_password()

    assert request_input.is_valid()
    assert request_input.email == valid_credentials["email"]
    assert request_input.password == valid_credentials["password"]


def test_invalid_email_format(request_input):
    request_input.email = "invalid-email"
    request_input.password = "secure123"
    request_input._errors = []
    request_input.validate_email()

    assert hasattr(request_input, "_errors")
    assert any(INVALID_EMAIL_MESSAGE in e for e in request_input._errors)


def test_empty_email(request_input):
    request_input.email = ""
    request_input.password = "secure123"
    request_input._errors = []
    request_input.validate_email()

    assert hasattr(request_input, "_errors")
    assert not request_input.is_valid()
    assert any(INVALID_EMAIL_MESSAGE in e for e in request_input._errors)


def test_empty_password(request_input):
    request_input.email = "test@example.com"
    request_input.password = ""
    request_input._errors = []
    request_input.validate_password()

    assert hasattr(request_input, "_errors")
    assert not request_input.is_valid()
    assert any(INVALID_PASSWORD_MESSAGE in e for e in request_input._errors)


def test_short_password(request_input):
    request_input.email = "test@example.com"
    request_input.password = "12345"
    request_input._errors = []
    request_input.validate_password()

    assert hasattr(request_input, "_errors")
    assert not request_input.is_valid()
    assert any(INVALID_PASSWORD_MESSAGE in e for e in request_input._errors)
