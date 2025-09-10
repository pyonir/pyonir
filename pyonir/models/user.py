from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

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
    perms: list[str]

    @classmethod
    def from_string(cls, role_name: str) -> "Role":
        """
        Create a Role instance from a string definition.

        Format: "RoleName:perm1,perm2,perm3"
        - RoleName is required.
        - Permissions are optional; defaults to [].

        Example:
            Role.from_string("Admin:read,write")
            -> Role(name="Admin", perms=["read", "write"])
        """
        role_name, perms = role_name.split(':')
        return cls(name=role_name.strip(), perms=perms.strip().split(',') if perms else [])


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

class UserMeta(PyonirSchema):
    """Represents details about a user"""
    first_name: Optional[str] = ''
    last_name: Optional[str] = ''
    gender: Optional[str] = ''
    age: Optional[int] = 0
    height: Optional[int] = 0
    weight: Optional[int] = 0
    phone: Optional[str] = ''
    about_you: Optional[str] = ''

class User(PyonirSchema):
    """Represents an app user"""

    # user signup fields
    email: str
    """User's email address is required for signup"""
    password: str = ''
    """User's password to authenticate"""

    # configurable user details
    name: str = ''
    avatar: str = '/public/images/default-avatar.png'
    meta: UserMeta = UserMeta()

    # system specific fields
    id: str = ''
    """Unique identifier for the user"""
    role: str = Roles.NONE.name
    """Role assigned to the user, defaults to 'none'"""
    verified_email: bool = False
    """Flag indicating if the user's email is verified"""
    file_path: str = ''
    """File path for user-specific files"""
    file_dirpath: str = ''
    """Directory path for user-specific files"""
    auth_from: Optional[str] = 'basic'
    """Authentication method used by the user (e.g., 'google', 'email')"""
    signin_locations: Optional[list] = []
    """Locations capture during signin"""
    auth_token: Optional[str] = ''
    """Authentication token verifying the user"""
    _private_keys: list[str] = ['id', 'password', 'auth_token']
    """List of private keys that should not be included in JSON serialization"""

    @property
    def perms(self) -> list[PermissionLevel]:
        """Returns the permissions for the user based on their role"""
        user_role = getattr(Roles, self.role.upper()) or Roles.NONE
        return user_role.perms

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

