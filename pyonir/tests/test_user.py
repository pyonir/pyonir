from copy import deepcopy

from pyonir.tests.conftest import PyonirMocks, mock_request
from pyonir.core.security import (
    PyonirUser,
    PyonirUserMeta,
    PermissionLevel,
    INVALID_EMAIL_MESSAGE,
    INVALID_PASSWORD_MESSAGE, Roles,
)

valid_credentials = {"email": "test@example.com", "password": "secure123", "flow": "session"}


async def test_user_credentials(test_app: PyonirMocks.App):
    """RequestInput.from_dict handles missing email by reporting the invalid-email message."""
    invalid_creds = deepcopy(valid_credentials)
    invalid_creds["email"] = ""  # Simulate missing email
    req = await mock_request(test_app, method="POST", path="/signin", body=invalid_creds)
    req.request_input.validate_email()
    assert len(req.request_input._errors) >= 1
    assert INVALID_EMAIL_MESSAGE in req.request_input._errors[0]


def test_user_from_dict(mock_data):
    """Creating a PyonirUser from the fixture data provided by conftest.PyonirMocks."""
    user = PyonirUser(meta=mock_data, uid="test-uid")
    # PyonirUser.email property reads from meta.email
    assert user.email == mock_data["email"]
    assert isinstance(user.meta, PyonirUserMeta)


def test_from_fixture_data_directly():
    """Build a user directly from the shared fixture data and assert key fields."""
    user = PyonirUser(meta=PyonirMocks.user_meta_data, uid="test-uid")
    assert isinstance(user, PyonirUser)
    assert user.email == PyonirMocks.user_meta_data["email"]
    # PyonirUser stores username on meta
    assert user.meta.username == PyonirMocks.user_data.get("username", "")
    assert isinstance(user.meta, PyonirUserMeta)
    assert getattr(user.meta, "first_name", None) == PyonirMocks.user_meta_data.get("first_name")


def test_permissions_after_load():
    # Use a role that exists in Roles to get deterministic permissions
    user = PyonirUser(meta=PyonirMocks.user_meta_data, uid="test-uid", role=Roles.CONTRIBUTOR)

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


async def test_valid_signin(test_app: PyonirMocks.App):
    print(f"Request input: {valid_credentials}")
    req = await mock_request(test_app, method="POST", path="/signin", body=valid_credentials)
    request_input = req.request_input

    # explicitly re-run validators to be deterministic
    request_input.validate_email()
    request_input.validate_password()
    print(f"Request input errors: {request_input.is_valid()}, {request_input.email}, {request_input._errors}")
    assert request_input.is_valid()
    assert request_input.email == valid_credentials["email"]
    assert request_input.password == valid_credentials["password"]


async def test_invalid_email_format(test_app: PyonirMocks.App):
    req = await mock_request(test_app, method="POST", path="/signin", body=valid_credentials)
    request_input = req.request_input
    request_input.body['email'] = "invalid-email"
    request_input.body['password'] = "secure123"
    request_input._errors = []
    request_input.validate_email()

    assert hasattr(request_input, "_errors")
    assert any(INVALID_EMAIL_MESSAGE in e for e in request_input._errors)


async def test_empty_email(test_app: PyonirMocks.App):
    req = await mock_request(test_app, method="POST", path="/signin", body=valid_credentials)
    request_input = req.request_input
    request_input.body['email'] = ""
    request_input.body['password'] = "secure123"
    request_input._errors = []
    request_input.validate_email()

    assert hasattr(request_input, "_errors")
    assert not request_input.is_valid()
    assert any(INVALID_EMAIL_MESSAGE in e for e in request_input._errors)


async def test_empty_password(test_app: PyonirMocks.App):
    req = await mock_request(test_app, method="POST", path="/signin", body=valid_credentials)
    request_input = req.request_input
    request_input.body['email'] = "test@example.com"
    request_input.body['password'] = ""
    request_input._errors = []
    request_input.validate_password()

    assert hasattr(request_input, "_errors")
    assert not request_input.is_valid()
    assert any(INVALID_PASSWORD_MESSAGE in e for e in request_input._errors)


async def test_short_password(test_app: PyonirMocks.App):
    req = await mock_request(test_app, method="POST", path="/signin", body=valid_credentials)
    request_input = req.request_input
    request_input.body['email'] = "test@example.com"
    request_input.body['password'] = "12345"
    request_input._errors = []
    request_input.validate_password()

    assert hasattr(request_input, "_errors")
    assert not request_input.is_valid()
    assert any(INVALID_PASSWORD_MESSAGE in e for e in request_input._errors)
