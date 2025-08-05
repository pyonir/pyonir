from dataclasses import dataclass, field
from enum import StrEnum

from pyonir.core import PyonirSchema


class PermissionLevel(StrEnum):
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
    given_name: str = ''
    last_name: str = ''
    gender: str = ''
    age: int = 0
    height: int = 0
    weight: int = 0
    phone: str = ''
    about_you: str = ''

@dataclass
class User(PyonirSchema):
    """Represents an app user"""
    # user signup fields
    email: str
    password: str = ''
    name: str = ''
    avatar: str = ''
    signin_locations: list = field(default_factory=list)
    # private user details
    meta: UserMeta = field(default_factory=UserMeta)
    # system specific fields
    id: str = ''
    """Unique identifier for the user"""
    role: str = ''
    """Role assigned to the user, defaults to 'none'"""
    verified_email: bool = False
    """Flag indicating if the user's email is verified"""
    file_path: str = ''
    """File path for user-specific files"""
    file_dirpath: str = ''
    """Directory path for user-specific files"""
    auth_token: str = ''
    """Authentication token for the user"""
    auth_from: str = 'email'
    """Authentication method used by the user (e.g., 'google', 'email')"""
    _private_keys: list[str] = field(default_factory=lambda: ['id'])
    """List of private keys that should not be included in JSON serialization"""

    def __post_init__(self):
        """Post-initialization to set default values and validate role"""
        if not self.role:
            self.role = Roles.NONE.name
        if not self.avatar:
            self.avatar = '/static/images/default-avatar.png'

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

    def to_json(self, obfuscate = True) -> dict:
        """Returns the user data as a JSON serializable dictionary"""
        # obfuscate = self._private_keys
        return {key: ('***' if obfuscate and key in self._private_keys else value) for key, value in self.__dict__.items() if key[0] != '_'}


@dataclass
class UserCredentials(PyonirSchema):
    """Represents user credentials for login"""
    email: str
    """User's email address is required for login"""

    password: str = ''
    """User's password for login is optional, can be empty for SSO"""

    remember_me: bool = False
    """Flag to remember user session, defaults to False"""

    is_sso: bool = False
    """Flag to indicate if the login is via Single Sign-On (SSO)"""

    def validate_email(self):
        """Validates the email format"""
        if self.is_sso: return False
        import re
        if not self.email:
            self.errors.append("Email cannot be empty")
        if not re.match(r"[^@]+@[^@]+\.[^@]+", self.email):
            self.errors.append(f"Invalid email address: {self.email}")

    def validate_password(self):
        """Validates the password for login"""
        if self.is_sso: return False
        if not self.password:
            self.errors.append("Password cannot be empty")
        elif len(self.password) < 6:
            self.errors.append("Password must be at least 6 characters long")

    @classmethod
    def sso(cls):
        """Creates an instance for Single Sign-On (SSO) without password"""
        return cls(email='', password='', remember_me=False, is_sso=True)

if __name__ == "__main__":
    user = User(email="test@example.com", role=Roles.ADMIN.name)
    print(user.perms)  # ['read', 'write', 'update', 'delete']
    print(user.has_perm(PermissionLevel.WRITE))  # True
