from abc import ABC, abstractmethod, ABCMeta
from dataclasses import dataclass, field
# from enum import StrEnum
from typing import Optional, Dict, Any

from pyonir.core import PyonirSchema
from pyonir.pyonir_types import PyonirRequest


class PermissionLevel(str):
    NONE = 'none'
    """Defines the permission levels for users"""

    READ = 'read'
    """Permission to read data"""

    WRITE = 'write'
    """Permission to write data"""

    UPDATE = 'update'
    """Permission to update data"""

    DELETE = 'delete'
    """Permission to delete data"""

    ADMIN = 'admin'
    """Permission to perform administrative actions"""


@dataclass
class Role:
    """Defines the permissions for each role"""
    name: str
    perms: list[PermissionLevel]


class Roles:
    """Defines the user roles and their permissions"""

    SUPER = Role(name='super', perms=[
        PermissionLevel.READ,
        PermissionLevel.WRITE,
        PermissionLevel.UPDATE,
        PermissionLevel.DELETE,
        PermissionLevel.ADMIN
    ])
    """Super user with all permissions"""
    ADMIN = Role(name='admin', perms=[
        PermissionLevel.READ,
        PermissionLevel.WRITE,
        PermissionLevel.UPDATE,
        PermissionLevel.DELETE
    ])
    """Admin user with most permissions"""
    AUTHOR = Role(name='author', perms=[
        PermissionLevel.READ,
        PermissionLevel.WRITE,
        PermissionLevel.UPDATE
    ])
    """Author user with permissions to create and edit content"""
    CONTRIBUTOR = Role(name='contributor', perms=[
        PermissionLevel.READ,
        PermissionLevel.WRITE
    ])
    """Contributor user with permissions to contribute content"""
    GUEST = Role(name='guest', perms=[
        PermissionLevel.READ
    ])
    """Contributor user with permissions to contribute content"""
    NONE = Role(name='none', perms=[
        PermissionLevel.NONE
    ])
    """No permissions assigned"""

    @classmethod
    def all_roles(cls):
        return [cls.SUPER, cls.ADMIN, cls.AUTHOR, cls.CONTRIBUTOR, cls.GUEST]

@dataclass
class UserMeta(PyonirSchema):
    """Represents details about a user"""
    first_name: str = ''
    last_name: str = ''
    gender: str = ''
    age: int = 0
    height: int = 0
    weight: int = 0
    phone: str = ''
    about_you: str = ''


@dataclass
class UserSignIn(PyonirSchema):
    """Represents a user sign in request"""

    email: str
    password: str

    def validate_email(self):
        """Validates the email format"""
        import re
        if not self.email:
            self._errors.append("Email cannot be empty")
        if not re.match(r"[^@]+@[^@]+\.[^@]+", self.email):
            self._errors.append(f"Invalid email address: {self.email}")

    def validate_password(self):
        """Validates the password for login"""
        if not self.password:
            self._errors.append("Password cannot be empty")
        elif len(self.password) < 6:
            self._errors.append("Password must be at least 6 characters long")


@dataclass
class User(PyonirSchema):
    """Represents an app user"""

    # user signup fields
    email: str
    """User's email address is required for signup"""
    password: str = ''
    """User's password to authenticate"""

    # configurable user details
    name: str = ''
    avatar: str = ''
    meta: UserMeta = field(default_factory=UserMeta)

    # system specific fields
    id: str = ''
    """Unique identifier for the user"""
    auth_token: str = ''
    """Authentication token verifying the user"""
    role: str = ''
    """Role assigned to the user, defaults to 'none'"""
    verified_email: bool = False
    """Flag indicating if the user's email is verified"""
    file_path: str = ''
    """File path for user-specific files"""
    file_dirpath: str = ''
    """Directory path for user-specific files"""
    auth_from: str = 'basic'
    """Authentication method used by the user (e.g., 'google', 'email')"""
    signin_locations: list = field(default_factory=list)
    """Locations capture during signin"""
    _private_keys: list[str] = field(default_factory=lambda: ['id', 'password', 'auth_token'])
    """List of private keys that should not be included in JSON serialization"""

    @property
    def perms(self) -> list[PermissionLevel]:
        """Returns the permissions for the user based on their role"""
        user_role = getattr(Roles, self.role.upper()) or Roles.NONE
        return user_role.perms

    def __post_init__(self):
        """Post-initialization to set default values and validate role"""
        if not self.role:
            self.role = Roles.NONE.name
        if not self.avatar:
            self.avatar = '/public/images/default-avatar.png'
        if isinstance(self.meta, dict): # TODO: this is now required to deserialize user object due to schema from_dict is present. Look into alternative way to not call from dict in mapper
            self.meta = UserMeta(**self.meta)

    def has_perm(self, action: PermissionLevel) -> bool:
        """Checks if the user has a specific permission based on their role"""
        user_role = getattr(Roles, self.role.upper(), Roles.NONE)
        is_allowed = action in user_role.perms
        return is_allowed

    def has_perms(self, actions: list[PermissionLevel]) -> bool:
        return any([self.has_perm(action) for action in actions])

    def save_to_session(self, request: PyonirRequest,key = None, value = None) -> None:
        """Convert instance to a serializable dict."""
        request.server_request.session[key or 'user'] = value or self.id


if __name__ == "__main__":
    user = User(email="test@example.com", role=Roles.ADMIN.name, auth_token='***')
    print(user.perms)  # ['read', 'write', 'update', 'delete']
    print(user.has_perm(PermissionLevel.WRITE))  # True
