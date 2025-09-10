import os
from pyonir.models.user import User, UserMeta, Roles, UserSignIn

test_user_file = os.path.join(os.path.dirname(__file__), 'contents', 'test_user.json')
valid_credentials = {
    "email": "test@example.com",
    "password": "secure123"
}

def test_from_file():
    # Test loading user from file
    user = User.from_file(test_user_file)

    assert isinstance(user, User)
    assert user.email == "pyonir@site.com"
    assert user.name == "PyonirUserName"
    assert isinstance(user.meta, UserMeta)
    assert user.meta.first_name == "Test"
    assert user.meta.last_name == "User"
    assert user.role == "contributor"

def test_permissions_after_load():
    from pyonir.models.user import PermissionLevel
    user = User.from_file(test_user_file)

    # Test permissions based on role
    assert user.has_perm(PermissionLevel.READ)
    assert user.has_perm(PermissionLevel.WRITE)
    assert not user.has_perm(PermissionLevel.ADMIN)

def test_private_keys_excluded():
    user = User.from_file(test_user_file)
    serialized = user.to_dict()

    # Check private keys are excluded
    assert 'password' not in serialized
    assert 'auth_token' not in serialized
    assert 'id' not in serialized


# UserSignIn tests

def test_valid_signin():
    signin = UserSignIn(**valid_credentials)
    signin.validate_email()
    signin.validate_password()

    assert signin.is_valid()
    assert signin.email == valid_credentials["email"]
    assert signin.password == valid_credentials["password"]

def test_invalid_email_format():
    signin = UserSignIn(email="invalid-email", password="secure123")
    signin.validate_email()

    assert hasattr(signin, '_errors')
    assert "Invalid email address" in signin._errors[0]

def test_empty_email():
    signin = UserSignIn(email="", password="secure123")
    signin.validate_email()

    assert hasattr(signin, '_errors')
    assert not signin.is_valid()
    assert "Email cannot be empty" in signin._errors[0]
    test_invalid_email_format()

def test_empty_password():
    signin = UserSignIn(email="test@example.com", password="")
    signin.validate_password()

    assert hasattr(signin, '_errors')
    assert not signin.is_valid()
    assert "Password cannot be empty" in signin._errors[0]

def test_short_password():
    signin = UserSignIn(email="test@example.com", password="12345")
    signin.validate_password()

    assert hasattr(signin, '_errors')
    assert not signin.is_valid()
    assert "Password must be at least 6 characters long" in signin._errors[0]