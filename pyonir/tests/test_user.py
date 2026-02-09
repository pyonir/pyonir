import os

from pyonir.tests.conftest import PyonirMocks
from pyonir.core.authorizer import (
    PyonirUser,
    PyonirUserMeta,
    PermissionLevel,
    RequestInput,
    INVALID_EMAIL_MESSAGE,
    INVALID_PASSWORD_MESSAGE,
)

# Path to a (possibly present) test fixture file. Tests will build users from the PyonirMocks fixture
test_user_file = os.path.join(os.path.dirname(__file__), "contents", "mock_data", "test_user.json")

valid_credentials = {"email": "test@example.com", "password": "secure123"}


def make_request_input(email=None, password=None, flow=None):
    """Create a RequestInput instance without invoking BaseSchema.__init__ to avoid enum coercion side-effects."""
    ri = object.__new__(RequestInput)
    # set minimal attributes used by tests
    ri.email = email
    ri.password = password
    ri.flow = flow
    ri._errors = []
    return ri


def test_user_credentials():
    """RequestInput.from_dict handles missing email by reporting the invalid-email message."""
    creds = make_request_input(email=None, password="securepass", flow="session")
    creds.validate_email()
    assert len(creds._errors) >= 1
    assert INVALID_EMAIL_MESSAGE in creds._errors[0]


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


# RequestInput tests using the real RequestInput validators

def test_valid_signin():
    signin = make_request_input(email=valid_credentials["email"], password=valid_credentials["password"])
    # explicitly re-run validators to be deterministic
    signin.validate_email()
    signin.validate_password()

    assert signin.is_valid()
    assert signin.email == valid_credentials["email"]
    assert signin.password == valid_credentials["password"]


def test_invalid_email_format():
    signin = make_request_input(email="invalid-email", password="secure123")
    signin.validate_email()

    assert hasattr(signin, "_errors")
    assert any(INVALID_EMAIL_MESSAGE in e for e in signin._errors)


def test_empty_email():
    signin = make_request_input(email="", password="secure123")
    signin.validate_email()

    assert hasattr(signin, "_errors")
    assert not signin.is_valid()
    assert any(INVALID_EMAIL_MESSAGE in e for e in signin._errors)


def test_empty_password():
    signin = make_request_input(email="test@example.com", password="")
    signin.validate_password()

    assert hasattr(signin, "_errors")
    assert not signin.is_valid()
    assert any(INVALID_PASSWORD_MESSAGE in e for e in signin._errors)


def test_short_password():
    signin = make_request_input(email="test@example.com", password="12345")
    signin.validate_password()

    assert hasattr(signin, "_errors")
    assert not signin.is_valid()
    assert any(INVALID_PASSWORD_MESSAGE in e for e in signin._errors)
