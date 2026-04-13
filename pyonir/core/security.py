import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Optional, Tuple, Union

from pyonir.core.server import RouteConfig
from pyonir import PyonirRequest, BaseApp
from pyonir.core.schemas import BaseSchema

from starlette.requests import Request as StarletteRequest

INVALID_EMAIL_MESSAGE: str = "Invalid email address format"
INVALID_PASSWORD_MESSAGE: str = "Incorrect password"

class AuthenticationTypes(StrEnum):
    BASIC = "basic"
    OAUTH2 = "oauth2"
    SAML = "saml"

class AuthMethod(StrEnum):
    BASIC = "basic"
    BEARER = "bearer"
    SESSION = "session"
    API_KEY = "api_key"
    BODY = "body"
    NONE = "none"

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

    def to_dict(self, **kwargs) -> str:
        return self.name

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

    @classmethod
    def all_roles(cls):
        return [cls.SUPER, cls.ADMIN, cls.AUTHOR, cls.CONTRIBUTOR, cls.GUEST]


class PyonirUserMeta(BaseSchema):
    """Represents personal details about a user"""
    password: str = None
    """Protected password hash for the user"""
    avatar: Optional[str] = ''
    email: Optional[str] = ''
    username: Optional[str] = ''
    first_name: Optional[str] = ''
    last_name: Optional[str] = ''
    gender: Optional[str] = ''
    age: Optional[int] = 0
    height: Optional[int] = 0
    weight: Optional[int] = 0
    phone: Optional[str] = ''
    about_you: Optional[str] = ''

class PyonirUser(BaseSchema, table_name='users'):
    """Represents an app user"""

    meta: PyonirUserMeta = None
    """User's personal details"""

    uid: str = None
    """Unique identifier for the user"""

    auth_token: Optional[str] = None
    """Authentication token used during user sign-in"""

    role: Optional[Role] = ''
    """User role that determines permissions and access levels"""

    _file_path: Optional[str] = ''
    """File path for user-specific profile"""

    _file_dirpath: Optional[str] = ''
    """Directory path for user-specific files"""

    @property
    def account_dirpath(self) -> str:
        """Relative path to user personal directory"""
        return self.file_dirpath or os.path.join(self.__table_name__, self.uid)

    @property
    def account_profile_path(self) -> str:
        """Relative path to user profile data"""
        return os.path.join(self.account_dirpath, 'profile.json')

    @property
    def account_sqlite_path(self) -> str:
        """Relative path to user sqlite db file"""
        return os.path.join(self.account_dirpath, f'{self.uid}_sqlite.db')

    @property
    def email(self) -> str:
        return self.meta and self.meta.email or ''

    @property
    def password(self) -> str:
        return self.meta and self.meta.password or ''

    @property
    def perms(self) -> list[PermissionLevel]:
        """Returns the permissions for the user based on their role"""
        user_role = getattr(Roles, self.role.name.upper())
        return user_role.perms if user_role else []

    def has_perm(self, action: PermissionLevel) -> bool:
        """Checks if the user has a specific permission based on their role"""
        user_role = getattr(Roles, self.role.name.upper(), Roles.GUEST)
        is_allowed = action in user_role.perms
        return is_allowed

    def has_perms(self, actions: list[PermissionLevel]) -> bool:
        return any([self.has_perm(action) for action in actions])

    def _after_init(self):
        """Generates a unique user ID based on email and salt"""
        from pyonir import Site
        if self.email and not self.uid:
            self.uid = generate_user_id(self.email, Site.salt, 16) #if self.email else BaseSchema.generate_id()
            self.created_by = self.uid
        if isinstance(self.role, str):
            self.role = self.map_to_role(self.role)

    @staticmethod
    def map_to_role(role_value: str) -> Role:
        """Maps a string role value to a Role instance"""
        if isinstance(role_value, Role): return role_value
        r = getattr(Roles, str(role_value).upper(), None)
        return Role(name=role_value, perms=[]) if r is None else r


class PyonirSecurity:
    MAX_SIGNIN_ATTEMPTS = 3
    """Maximum number of sign-in attempts allowed before locking the account."""

    MAX_LOCKOUT_TIME = 300
    """Time in seconds to lock the account after exceeding sign-in attempts."""

    _prefix = f"@security"

    _user_model: Optional[PyonirUser] = PyonirUser

    def __init__(self, request: PyonirRequest, route_config: RouteConfig = None):
        self._user = None
        self._request: PyonirRequest = request
        self._route_config: RouteConfig = route_config
        self._signin_attempts: int = 0
        self._signin_locked_until: str = ''
        self._security_configs: dict = None

    @property
    def is_denied(self) -> bool:
        """Checks if the user is authorized to access the route."""
        user = self.authenticated_user
        security_configs = self._security_configs or {}
        requires_basic_auth = bool(security_configs and security_configs.get('type') == 'basic')
        is_denied = requires_basic_auth and (self.authenticated_user is None)
        self._user = user
        return is_denied

    @property
    def responses(self):
        return self.request.server_response.responses

    @property
    def creds(self):
        return self.request.request_input if self.request else None

    @property
    def session(self) -> dict:
        if not self._request or not self._request.session: return {}
        return self._request.session

    @property
    def user_model(self):
        return self._user_model

    @property
    def pyonir_app(self) -> BaseApp:
        return self.request.pyonir_app

    @property
    def request(self) -> PyonirRequest:
        return self._request if self._request else None

    @property
    def redirect_to(self):
        return self.creds.body.get('redirect_to')

    @property
    def authenticated_user(self):
        if self._user:
            return self._user
        flow = self.request.request_input.flow
        creds = self.creds

        if flow in {AuthMethod.BASIC, AuthMethod.BODY}:
            # check creds with datasource
            _user: PyonirUser = self._get_user_profile(creds.email)
            if not _user: return None
            requested_passw = self.harden_password(self.pyonir_app.salt, creds.password, _user.auth_token)
            has_valid_creds = check_pass(_user.password, requested_passw)
            return _user if has_valid_creds else None

        elif flow == AuthMethod.SESSION:
            # check active session and query user details
            if not self.session:
                return None
            _user = self._get_user_profile()
            if not _user:
                self.end_session()
            return _user

        elif flow == AuthMethod.BEARER:
            pass

        return None

    def secure_credentials(self, password: str) -> Tuple[str, str]:
        """Generates a new auth token and hashes the password."""
        from starlette_wtf import csrf_token
        auth_token = csrf_token(self.request.server_request)
        hashed_password = hash_password(self.harden_password(self.pyonir_app.salt, password, token=auth_token))
        return auth_token, hashed_password

    def _create_jwt(self, user_id: str = None, user_role: str = '', exp_time=None):
        """Returns session jwt object based on profile info"""
        import datetime
        exp_time = exp_time or self.MAX_LOCKOUT_TIME
        exp_in = (datetime.datetime.now() + datetime.timedelta(minutes=exp_time)).timestamp()
        user_jwt = {
            "sub": user_id,
            "role": user_role,
            "remember_for": exp_time,
            "iat": datetime.datetime.now(),
            "iss": self.pyonir_app.domain,
            "exp": exp_in
            }
        jwt_token = _encode_jwt(user_jwt, self.pyonir_app.salt)
        return jwt_token

    def _get_user_profile(self, user_email: str = None) -> Optional[PyonirUser]:
        """Pyonir queries the file system for user account based on the provided credentials"""
        # access user guid from session or email if available
        has_session = self.creds.session_id
        uid = has_session if has_session else generate_user_id(from_email=user_email or self.creds.email, salt=self.pyonir_app.salt)
        # directory path to query a user profile from file system
        model_file_name = getattr(self.user_model, '_file_name', 'profile.json')
        user_account_path = os.path.join(self.pyonir_app.datastore_dirpath, self.user_model.__table_name__, uid or '', model_file_name)
        user_account = self.user_model.from_file(user_account_path, app_ctx=self.request.app_ctx_ref.app_ctx) if os.path.exists(user_account_path) else None
        return user_account

    def _reset_signin_attempts(self):
        """Resets the sign-in attempts counter in the session."""
        if self.session:
            if 'signin_attempts' in self.session:
                del self.session['signin_attempts']
            if 'signin_locked_until' in self.session:
                del self.session['signin_locked_until']

    def end_session(self):
        """Ends the user session by clearing the session data."""
        if self.session and self.session.get(self.pyonir_app.session_key):
            del self.session[self.pyonir_app.session_key]
            self._reset_signin_attempts()
        pass

    def get_user_profile(self, user_email: str = None) -> Optional[PyonirUser]:
        """Pyonir queries the file system for user account based on the provided credentials"""
        # access user guid from session or email if available
        has_session = self.creds.session_id
        uid = has_session if has_session else generate_user_id(from_email=user_email or self.creds.email, salt=self.pyonir_app.salt)
        # directory path to query a user profile from file system
        model_file_name = self.user_model._file_name if hasattr(self.user_model, '_file_name') else 'profile.json'
        user_account_path = os.path.join(self.pyonir_app.datastore_dirpath, self.user_model.__table_name__, uid or '', model_file_name)
        user_account = self.user_model.from_file(user_account_path, app_ctx=self.request.app_ctx_ref.app_ctx) if os.path.exists(user_account_path) else None
        return user_account

    def create_session(self, user: PyonirUser):
        """Creates a user session for the authenticated user."""
        user_jwt = self._create_jwt(user_id=user.uid, user_role=user.role.name, exp_time=1440 if self.creds.remember_me else 60)
        self.session[self.pyonir_app.session_key] = user_jwt

    def has_signin_exceeded(self) -> bool:
        """Checks if the maximum sign-in attempts have been exceeded."""
        _signin_attempts = self.session.get('signin_attempts', 0)
        time_remaining, lockout_expired = self.get_lockout_time()
        max_attempt_exceeded = _signin_attempts >= self.MAX_SIGNIN_ATTEMPTS
        is_spamming = max_attempt_exceeded and time_remaining
        if is_spamming or max_attempt_exceeded:
            return True
        return False

    def set_signin_attempt(self):
        """Increments the sign-in attempts counter in the session."""
        if self.request.server_request:
            current_attempts = self.request.server_request.session.get('signin_attempts', 0)
            self.request.server_request.session['signin_attempts'] = current_attempts + 1

    def set_timeout_signin(self):
        """Locks the sign-in attempts for a specified duration."""
        import time
        self._signin_locked_until = time.time() + self.MAX_LOCKOUT_TIME
        self.session['signin_locked_until'] = self._signin_locked_until

    def get_lockout_time(self) -> Tuple[str, bool]:
        """Checks if lockout time has expired to allow signin"""
        import time

        if not self.request.server_request: return '', False
        lock_timeout = self.session.get('signin_locked_until', 0)
        if lock_timeout:
            now = time.time()
            time_remaining = lock_timeout - now
            fmt_remaining = format_time_remaining(time_remaining)
            print(fmt_remaining)
            if time_remaining <= 0:
                print("lockout time expired!!")
                self.reset_signin_attempts()
                return fmt_remaining, True
            return fmt_remaining, False
        return '', False

    def reset_signin_attempts(self):
        """Resets the sign-in attempts counter in the session."""
        if self.session:
            if 'signin_attempts' in self.session:
                del self.session['signin_attempts']
            if 'signin_locked_until' in self.session:
                del self.session['signin_locked_until']

    @staticmethod
    def harden_password(site_salt: str, password: str, token: str):
        """Strengthen all passwords by adding a site salt and token."""
        if not site_salt or not password or not token:
            raise ValueError("site_salt, password, and token must be provided")
        return f"{site_salt}${password}${token}"

    @classmethod
    def set_user_model(cls, model):
        cls._user_model = model



async def preprocess_request_body(request: StarletteRequest):
    """Get form data and file upload contents from request"""
    from pyonir.core.utils import expand_dotted_keys
    import json
    body = dict(request.query_params)
    files = []

    try:
        ajson = await request.json()
        if isinstance(ajson, str): ajson = json.loads(ajson)
        body.update(ajson)
    except Exception as ee:
        # multipart/form-data
        _body = await request.form()
        for name, content in _body.multi_items():
            if hasattr(content, "filename"):
                setattr(content, "ext", os.path.splitext(content.filename)[1])
                files.append(content)
            else:
                if body.get(name): # convert form name into a list
                    currvalue = body[name]
                    if isinstance(currvalue, list):
                        currvalue.append(content)
                    else:
                        body[name] = [currvalue, content]
                else:
                    body[name] = content
    body = expand_dotted_keys(body, return_as_dict=True)
    return body, files

def check_pass(protected_hash: str, password_str: str) -> bool:
    """Verifies a password against a protected hash using Argon2."""
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHashError, VerifyMismatchError

    ph = PasswordHasher()
    try:
        return ph.verify(hash=protected_hash, password=password_str)
    except (InvalidHashError, VerifyMismatchError) as e:
        print(f"Password verification failed: {e}")
        return False

def decode_jwt(jwt_token: str, salt: str)-> Optional[dict]:
    """Returns decoded jwt object"""
    import jwt
    from jwt import ExpiredSignatureError
    try:
        return jwt.decode(jwt_token, salt, algorithms=['HS256'])
    except ExpiredSignatureError as ee:
        print(f"JWT token expired: {ee}")
    except Exception as e:
        print(f"{__name__} method - {str(e)}: {type(e).__name__}")

def _encode_jwt(jwt_data: dict, secret: str):
    """Returns base64 encoded jwt token encoded with pyonir app secret"""
    import jwt
    try:
        enc_jwt = jwt.encode(jwt_data, secret, algorithm='HS256')
        return enc_jwt
    except Exception as e:
        print(f"Something went wrong refreshing jwt token. {e}")
        raise

def hash_password(password_str: str) -> str:
    """Hashes a password string using Argon2."""
    from argon2 import PasswordHasher
    ph = PasswordHasher()
    return ph.hash(password_str.strip())

def generate_user_id(from_email: str, salt: str, length: int = 16) -> str:
    """Encodes the user ID (email) to a fixed-length string."""
    import hashlib, base64
    hash_email = hashlib.sha256((salt + from_email).encode()).hexdigest()
    urlemail = base64.urlsafe_b64encode(hash_email.encode()).decode()
    return urlemail[:length]

def format_time_remaining(time_remaining: Union[int, float]) -> str:
    """Formats the remaining time in a human-readable format."""
    mins, secs = divmod(int(time_remaining), 60)
    hrs, mins = divmod(mins, 60)

    if hrs:
        time_str = f"{hrs}h {mins}m {secs}s"
    elif mins:
        time_str = f"{mins}m {secs}s"
    else:
        time_str = f"{secs}s"
    return time_str