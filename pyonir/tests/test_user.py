import os
from pyonir.models.user import User, UserMeta, Roles

test_user_file = os.path.join(os.path.dirname(__file__), 'contents', 'test_user.json')


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