from __future__ import annotations

import inspect
import os, base64
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Tuple, Any, Dict, Optional, Union, Callable, Type
from enum import Enum, StrEnum

from pyonir.core.mapper import func_request_mapper
from pyonir.core.parser import DeserializeFile, VIRTUAL_ROUTES_FILENAME
from pyonir.core.schemas import BaseSchema
from pyonir.core.server import BaseApp, RouteConfig
# from pyonir.core.user import User, Role, PermissionLevel, Roles, UserSignIn
from pyonir.core.utils import merge_dict, get_attr, dict_to_class

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.requests import Request as StarletteRequest

from pyonir.pyonir_types import PyonirHooks, EVENT_RES, TEXT_RES, JSON_RES

INVALID_EMAIL_MESSAGE: str = "Invalid email address format"
INVALID_PASSWORD_MESSAGE: str = "Incorrect password"

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

@dataclass
class PyonirBaseRestResponse:
    """Represents a REST response from the server."""

    status_code: int = 000
    """HTTP status code of the response, e.g., 200 for success, 404 for not found."""

    message: str = ''
    """Response message, typically a string describing the result of the request."""

    data: dict = field(default_factory=dict)
    """Response data, typically a dictionary containing the response payload."""

    _cookies: dict = field(default_factory=dict)
    _html: str = None
    _stream: any = None
    _media_type: str = None
    _file_response: any = None
    # _server_response: object = None
    _redirect_response = None
    _headers: dict = field(default_factory=dict)

    @property
    def is_redirect(self):
        return self._redirect_response

    @property
    def is_ok(self) -> bool:
        """Indicates if the response status code represents a successful request."""
        return 200 <= self.status_code < 300

    @property
    def headers(self): return self._headers

    @property
    def content(self) -> Optional['Response']:
        from starlette.responses import Response, StreamingResponse
        content = ''
        media_type = self._media_type
        if self._file_response:
            self._media_type = 'static'
            return self._file_response
        elif self._stream:
            media_type = EVENT_RES
            return StreamingResponse(content=self._stream, media_type=EVENT_RES)
        elif self._html:
            media_type = TEXT_RES
            content = self._html
        else:
            media_type = JSON_RES
            content = self.to_json()
        self._media_type = media_type
        return Response(content=content, media_type=media_type) if content else None

    def to_dict(self, context_data: dict = None) -> dict:
        """Converts the response to a dictionary."""
        from pyonir import Site
        return {
            'status_code': self.status_code,
            'message': Site.TemplateEnvironment.render_python_string(self.message or ''),
            'data': self.data,
            **(context_data or {})
        }

    def to_json(self) -> str:
        """Converts the response to a JSON serializable dictionary."""
        from pyonir.core.utils import json_serial
        import json
        return json.dumps(self.to_dict(), default=json_serial)

    # def render(self):
    #     return self._server_response

    def set_header(self, key, value):
        """Sets header values"""
        self._headers[key] = value
        return self

    def set_json(self, value: dict):
        # json = request.file.output_json()
        self.data = value
        return self

    def set_html(self, value: str):
        """Sets the html response value"""
        self._html = value
        return self

    def set_stream(self, value: any):
        """Sets the stream response value"""
        self._stream = value
        return self

    def set_file_response(self, value: any):
        """Sets the file response value"""
        from starlette.responses import PlainTextResponse, Response
        if not isinstance(value, Response):
            value = None
        self._file_response = value or PlainTextResponse("File not found", status_code=404)

    def set_redirect_response(self, url: str, code: int = 302):
        from starlette.responses import RedirectResponse
        res = RedirectResponse(url, status_code=code)
        self._redirect_response = res
        return self

    def build(self):
        """Builds the response object"""
        from starlette.exceptions import HTTPException
        if self.status_code >= 400:
            raise HTTPException(status_code=self.status_code, detail=self.message or "An error occurred")
        self.set_header('Server', 'Pyonir Web Framework')
        res = self.content
        if self.headers and res.headers:
            for key, value in self.headers.items():
                res.headers[key] = str(value)

        if self._cookies:
            for key, value in self._cookies.items():
                res.set_cookie(key=key, value=value)

        if self._redirect_response:
            return self._redirect_response
        return res

    def set_media(self, media_type: str):
        self._media_type = media_type

    def set_cookie(self, cookie: dict):
        """
        :param cookie:
            key="access_token"
            value=jwt_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=3600,
        :return:
        """
        self._cookies.update(cookie)

    def set_headers_from_dict(self, headers: dict):
        """Sets multiple header values from a dictionary"""
        if headers:
            self._headers.update(headers)

class PyonirRestResponse(PyonirBaseRestResponse):
    """
    Represents a standardized authentication response.

    Attributes:
        message (str): A human-readable message describing the response.
        status_code (int): The associated HTTP status code for the response.
    """
    def response(self, message: str = None, status_code: int = None) -> 'PyonirRestResponse':
        """Returns a new PyonirAuthResponse with updated message and status code, or defaults to current values."""
        return PyonirRestResponse(
            message=message or self.message,
            status_code=status_code or self.status_code
        )

class DefaultPyonirAuthResponses:
    """Enum-like class that provides standardized authentication responses."""
    SERVER_OK = PyonirRestResponse(
        message="Server Ok",
        status_code=200
    )
    """PyonirAuthResponse: Indicates general server status of ok"""

    ERROR = PyonirRestResponse(
        message="Authentication failed",
        status_code=400
    )
    """PyonirAuthResponse: Indicates an authentication error due to invalid credentials or bad input (HTTP 400)."""

    INVALID_CREDENTIALS = PyonirRestResponse(
        message="The credentials provided is incorrect.",
        status_code=401
    )
    """PyonirAuthResponse: Indicates failed credential authentication (HTTP 401)."""

    SUCCESS = PyonirRestResponse(
        message="Authentication successful",
        status_code=200
    )
    """PyonirAuthResponse: Indicates successful authentication (HTTP 200)."""

    ACTIVE_SESSION = PyonirRestResponse(
        message="Authentication successful. session is active",
        status_code=200
    )
    """PyonirAuthResponse: Active authentication session (HTTP 200)."""

    UNAUTHORIZED = PyonirRestResponse(
        message="Unauthorized access",
        status_code=401
    )
    """PyonirAuthResponse: Indicates missing or invalid authentication credentials (HTTP 401)."""

    SESSION_EXPIRED = PyonirRestResponse(
        message="Session has expired. New Sign in required",
        status_code=401
    )
    """PyonirAuthResponse: Indicates missing or invalid authentication credentials (HTTP 401)."""

    NO_ACCOUNT_EXISTS = PyonirRestResponse(message="Account not found.", status_code=409)
    """Error: The requested action cannot be completed because the user does not have an account."""

    USER_SIGNED_OUT = PyonirRestResponse(message="User signed out", status_code=200)
    """PyonirAuthResponse: User signed out"""

    ACCOUNT_EXISTS = PyonirRestResponse(message="Account already exists", status_code=409)
    """PyonirAuthResponse: Indicates that the user account already exists (HTTP 409)."""

    SOMETHING_WENT_WRONG = PyonirRestResponse(message="Something went wrong, please try again later", status_code=422)
    """PyonirAuthResponse: Indicates a general error occurred during authentication (HTTP 422)."""

    TOO_MANY_REQUESTS = PyonirRestResponse(message="Too many requests. Try again later", status_code=429)
    """PyonirAuthResponse: Indicates too many requests have been made, triggering rate limiting (HTTP 429)."""

    def load_responses(self, responses: dict):
        """Loads custom responses into the enum."""
        _responses = get_attr(responses, '@security.responses') or {}
        for key, res_obj in _responses.items():
            message = res_obj.get('message', '')
            status_code = res_obj.get('status_code', 200)
            setattr(self, key.upper(), PyonirRestResponse(message=message, status_code=status_code))

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

    file_path: Optional[str] = ''
    """File path for user-specific files"""

    file_dirpath: Optional[str] = ''
    """Directory path for user-specific files"""

    # @property
    # def role(self) -> Role:
    #     """Role assigned to the user, defaults to 'none'"""
    #     return self.map_to_role(self.meta.role) or Roles.GUEST

    @property
    def email(self) -> str:
        return self.meta and self.meta.email or ''

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
        if not self.uid:
            self.uid = generate_user_id(self.email, Site.salt, 16) if self.email else BaseSchema.generate_id()
            self.created_by = self.uid
        if isinstance(self.role, str):
            self.role = self.map_to_role(self.role)

    @staticmethod
    def map_to_role(role_value: str) -> Role:
        """Maps a string role value to a Role instance"""
        if isinstance(role_value, Role): return role_value
        r = getattr(Roles, str(role_value).upper(), None)
        return Role(name=role_value, perms=[]) if r is None else r

class RequestInput(BaseSchema):
    email: str = ''
    """User's email address is required for login"""

    password: str = ''
    """User's password for login is optional, can be empty for SSO"""

    bearer_token: str = ''
    """User auth token"""

    session_id: str = ''
    """User session id"""

    remember_me: bool = False
    """Flag to remember user session, defaults to False"""

    flow: AuthMethod = AuthMethod.NONE
    """Authentication flow type"""

    body: Dict = {}
    """Request body data"""

    files: list = []
    """Uploaded files in the request"""

    jwt: dict = {}
    """Decoded JWT token data"""

    def validate_email(self):
        """Validates the email format"""
        import re
        if not self.email or not re.match(r"[^@]+@[^@]+\.[^@]+", self.email):
            self._errors.append(INVALID_EMAIL_MESSAGE)

    def validate_password(self):
        """Validates the password for login"""
        if not self.password or len(self.password) < 6:
            self._errors.append(INVALID_PASSWORD_MESSAGE)

    @classmethod
    def from_dict(cls, data: dict) -> 'RequestInput':
        """Creates a RequestInput instance from a dictionary."""
        return cls(**data)

    @classmethod
    async def from_request(cls, request: StarletteRequest) -> 'RequestInput':
        """Extracts user credentials from the incoming request."""
        pyonir_app: BaseApp = request.app.pyonir_app
        headers = dict(request.headers)
        # cookies = dict(request.cookies)
        session = dict(request.session)
        path_params = dict(request.path_params) or {}
        query_params = dict(request.query_params) or {}
        body, files = await preprocess_request_body(request)

        session_key = pyonir_app.session_key or 'pyonir_session'
        email = body.get('email')
        password = body.get('password')
        remember_me = body.get('remember_me', False)
        _auth_header = headers.get("authorization")
        _session_id = session.get(session_key)
        _jwt = None
        bearer_token = None
        flow = AuthMethod.NONE

        if _auth_header:
            auth_type, auth_value = _auth_header.split(" ", 1)

            if auth_type.lower() == "basic":
                flow = AuthMethod.BASIC
                decoded = base64.b64decode(auth_value).decode("utf-8")
                email, password = decoded.split(":", 1)

            elif auth_type.lower() == "bearer":
                flow = AuthMethod.BEARER
                # bearer_token = decode_jwt(auth_value, pyonir_app.salt)
                # email, _ = bearer_token.get('username') if bearer_token else None, None

        elif _session_id:
            _jwt = decode_jwt(_session_id, pyonir_app.salt)
            if _jwt:
                flow = AuthMethod.SESSION
                _session_id = _jwt.get('sub')
            else:
                _session_id = None

        elif email and password and not _auth_header:
            flow = AuthMethod.BODY
        if path_params or query_params:
            body.update(path_params)
            body.update(query_params)

        return cls(body=body,
                   files=files,
                   flow=flow,
                   jwt=_jwt,
                   session_id=_session_id,
                   email=email,
                   password=password,
                   remember_me=remember_me,
                   bearer_token=bearer_token)

class PyonirSecurity:
    """Handles route security checks including authentication and authorization."""
    MAX_SIGNIN_ATTEMPTS = 3
    """Maximum number of sign-in attempts allowed before locking the account."""

    MAX_LOCKOUT_TIME = 300
    """Time in seconds to lock the account after exceeding sign-in attempts."""

    _user_model: Type[PyonirUser] = PyonirUser

    _prefix = f"@security"

    def __init__(self, request: PyonirBaseRequest):
        self._request: PyonirBaseRequest = request
        self._user: Optional[PyonirUser] = None
        self._signin_attempts: int = 0
        self._signin_locked_until: str = ''
        self._redirect_route = '/'
        self.responses = DefaultPyonirAuthResponses()

    @property
    def requires_authentication(self) -> bool:
        """Indicates if authentication is required for route based on type."""
        security_data = self.request.file.data.get(self._prefix, {}) if self.request.file else {}
        auth_type = security_data.get('type','')
        is_req = auth_type in set(AuthenticationTypes)
        return is_req

    @property
    def user_model(self):
        return self._user_model

    @property
    def pyonir_app(self):
        return self.request.pyonir_app

    @property
    def request(self) -> PyonirBaseRequest:
        return self._request if self._request else None

    @property
    def session(self):
        """Starlette server session"""
        return self.request.server_request.session if self.request else {}

    @property
    def redirect_to(self):
        return self.request.request_input.body.get('redirect_to', self._redirect_route)

    @property
    def user(self) -> Optional[Type[PyonirUser]]:
        if not self._user:
            self._user = self.get_authenticated_user(AuthMethod.SESSION)
        return self._user

    @property
    def is_denied(self) -> bool:
        """Checks if the user is authorized to access the route."""
        if not self.requires_authentication:
            return False
        return not self.is_authenticated

    @property
    def is_authenticated(self) -> bool:
        """Criteria to assert an authenticated user"""
        return self.user is not None

    @property
    def has_session(self) -> bool:
        return bool(self.request.request_input.session_id) if self.request.request_input else False

    @property
    def signin_attempts(self) -> int:
        """Returns the current number of sign-in attempts from session."""
        return self.session.get('signin_attempts', 0)

    @property
    def creds(self):
        return self.request.request_input

    def get_user_profile(self, user_email: str = None) -> Optional[PyonirUser]:
        """Pyonir queries the file system for user account based on the provided credentials"""
        # access user guid from session or email if available
        uid = self.request.request_input.session_id if self.has_session else generate_user_id(from_email=user_email or self.creds.email, salt=self.pyonir_app.salt)
        # directory path to query a user profile from file system
        user_account_path = os.path.join(self.pyonir_app.datastore_dirpath, self.user_model.__table_name__, uid or '', 'profile.json')
        user_account = self.user_model.from_file(user_account_path, app_ctx=self.request.app_ctx_ref.app_ctx) if os.path.exists(user_account_path) else None
        return user_account

    def create_session(self, user: PyonirUser):
        """Creates a user session for the authenticated user."""
        user_jwt = self.create_jwt(user_id=user.uid, user_role=user.role.name, exp_time=1440 if self.creds.remember_me else 60)
        self.session[self.pyonir_app.session_key] = user_jwt

    def create_user(self) -> PyonirUser:
        """Creates a new user instance of user_model based on the provided credentials."""
        user = self.user_model(meta={'email': self.creds.email,
                                     'username': self.creds.email.split('@')[0]},)
        self.secure_user_credentials(user)
        user.file_path = os.path.join(self.pyonir_app.datastore_dirpath, getattr(user, '__table_name__', ''), user.uid, 'profile.json')
        user.file_dirpath = os.path.dirname(user.file_path)
        return user

    def secure_user_credentials(self, user: PyonirUser = None):
        """Generates a new auth token for the user."""
        from starlette_wtf import csrf_token
        if not user:
            user = self.user
        auth_token = csrf_token(self.request.server_request)
        hashed_password = hash_password(self.harden_password(self.pyonir_app.salt, self.creds.password, token=auth_token))
        user.auth_token = auth_token
        user.meta.password = hashed_password

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

    def create_jwt(self, user_id: str = None, user_role: str = '', exp_time=None):
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

    @classmethod
    def set_user_model(cls, model: Type[PyonirUser]):
        cls._user_model = model

    @abstractmethod
    def get_authenticated_user(self, flow: AuthMethod = None) -> Optional[PyonirUser]:
        """Retrieves the user associated with the request based on credentials."""
        # check user credentials
        flow = flow or self.request.request_input.flow
        creds = self.request.request_input
        salt = self.pyonir_app.salt

        if flow in {AuthMethod.BASIC, AuthMethod.BODY}:
            # check creds with datasource
            _user: PyonirUser = self.get_user_profile(creds.email)
            if not _user: return None
            requested_passw = self.harden_password(salt, creds.password, _user.auth_token)
            has_valid_creds = check_pass(_user.meta.password, requested_passw)
            return _user if has_valid_creds else None

        elif flow == AuthMethod.SESSION:
            # check active session and query user details
            if not self.has_session:
                return None #self.end_session()
            return self.get_user_profile()

        elif flow == AuthMethod.BEARER:
            pass

        return None

    @staticmethod
    def harden_password(site_salt: str, password: str, token: str):
        """Strengthen all passwords by adding a site salt and token."""
        if not site_salt or not password or not token:
            raise ValueError("site_salt, password, and token must be provided")
        return f"{site_salt}${password}${token}"

    def end_session(self):
        """Ends the user session by clearing the session data."""
        if self.session:
            del self.session[self.pyonir_app.session_key]
            self.reset_signin_attempts()
        pass


class PyonirBaseRequest:
    PAGINATE_LIMIT: int = 6

    def __init__(self, server_request: Optional[StarletteRequest], app: BaseApp):

        self.pyonir_app: BaseApp = app
        self.file: Optional[DeserializeFile] = None
        self.file_resolver: Optional[Callable] = None
        self.server_request: StarletteRequest = server_request
        self.server_response: PyonirRestResponse = PyonirRestResponse()
        self.security: Optional[PyonirSecurity] = PyonirSecurity(self)
        self.request_input: RequestInput = RequestInput() if not server_request else None

        # path params
        self.host = str(server_request.base_url).rstrip('/') if server_request else app.host
        self.protocol = server_request.scope.get('type') + "://" if server_request else app.protocol
        self.raw_path = "/".join(str(server_request.url).split(str(server_request.base_url))) if server_request else ''
        self.method = server_request.method if server_request else 'GET'
        self.path = server_request.url.path if server_request else '/'
        self.url = self.path if server_request else {}
        self.slug = self.path.lstrip('/').rstrip('/')
        self.parts = self.slug.split('/') if self.slug else []
        self._path_params: object = None
        self._query_params: object = None
        # self.path_params: Dict[str, Any] = dict(self.server_request.path_params) if server_request else {}

        # boolean flags
        self.is_home = (self.slug == '')
        self.is_api = self.parts and self.parts[0] == app.API_DIRNAME
        self.is_static = bool(list(os.path.splitext(self.path)).pop()) if server_request else False
        self.is_sse = server_request and EVENT_RES in server_request.headers.get("accept", "")
        if self.is_api:
            self.path = self.path.replace(app.API_ROUTE, '')  # normalize api path

        # application context
        self.flashes: dict = self.get_flash_messages() if server_request and not self.is_static else {}
        self._app_ctx_ref = None

        # Update template globals for request
        app.TemplateEnvironment.globals['request'] = self

    @property
    def app_ctx_ref(self):
        return self._app_ctx_ref or self.pyonir_app

    @property
    def headers(self) -> dict:
        """Returns the headers from the server request"""
        return dict(self.server_request.headers) if self.server_request else {}

    @property
    def path_params(self) -> object:
        """Returns the path parameters from the server request"""
        if not self._path_params:
            self._path_params = dict_to_class(self.server_request.path_params if self.server_request else {}, 'path_params', True)
        return self._path_params

    @property
    def query_params(self) -> object:
        """Returns the query parameters from the server request"""
        if not self._query_params:
            self._query_params = dict_to_class(self.server_request.query_params if self.server_request else {}, 'query_params', True)
        return self._query_params

    @property
    def files(self):
        """Returns uploaded files from the request input"""
        return self.request_input.files if self.request_input else []

    @property
    def form(self):
        """Returns form data from the request input"""
        return self.request_input.body if self.request_input else {}

    @property
    def user(self) -> Optional[Type[PyonirUser]]:
        """Returns the authenticated user for the current request"""
        return self.security.user

    @property
    def session_token(self):
        """Returns active csrf token for user session"""
        if self.server_request and self.server_request.session:
            return self.server_request.session.get('csrf_token')

    @property
    def session(self):
        if self.server_request and hasattr(self.server_request, 'session'):
            return self.server_request.session
        return {}

    @property
    def redirect_to(self):
        """Returns the redirect URL from the request form data"""
        if not self.file: return None
        file_redirect = self.request_input.body.get('redirect_to', self.request_input.body.get('redirect'))
        return file_redirect

    async def build_response(self, route: RouteConfig) -> Any:
        """Builds the server response for the current request by executing the route function and processing the file."""
        route_func = self.file_resolver or route.func
        root_static_file_request = self.is_static and route.is_index
        if callable(route_func) and self.pyonir_app.is_dev:
            route_func = self.pyonir_app.reload_module(route_func, reload=True)
        is_async = inspect.iscoroutinefunction(route_func)
        args = func_request_mapper(route_func, self)
        route_func_response = None

        if callable(route_func) and not root_static_file_request:
            self.server_response.status_code = 200
            route_func_response = await route_func(**args) if is_async else route_func(**args)

        # Perform redirects
        if self.redirect_to:
            return self.server_response.set_redirect_response(self.redirect_to).build()

        # Execute plugins hooks initial request
        await self.pyonir_app.plugin_manager.run_async_plugins(PyonirHooks.ON_REQUEST, self)

        if isinstance(route_func_response, PyonirRestResponse):
            return route_func_response.build()

        if self.is_sse:
            self.server_response.set_stream(route_func_response)
        elif self.is_api:
            if route_func_response is not None and self.file.file_exists:
                self.file.data['router_content'] = route_func_response
                route_func_response = None
            self.server_response.set_json(route_func_response or self.file.data)
        elif self.is_static: # allow route functions to return file responses for static files
            self.server_response.set_file_response(route_func_response)
        else:
            self.server_response.set_html(self.file.output_html(self))
        return self.server_response.build()

    async def set_request_input(self, data: Optional[Dict] = None):
        """Sets the request input data from the web request. This gathers credentials and query parameters into a single RequestInput object."""
        # If there is no server request, just initialize from provided data
        if not self.server_request:
            self.request_input = RequestInput.from_dict(data or {})
            return

        self.request_input = await RequestInput.from_request(self.server_request)
        if data:
            self.request_input.body.update(data)

    async def set_app_context(self) -> None:
        """Sets the application context for the current request based on the URL path."""

        path_str = self.path.replace(self.pyonir_app.API_ROUTE, '')
        for plg in self.pyonir_app.activated_plugins:
            if not hasattr(plg, 'endpoint'): continue
            if path_str.startswith(plg.endpoint):
                self._app_ctx_ref = plg
                print(f"Request has switched to {plg.name} context")
                break

    async def set_page_file(self) -> None:
        """
        Sets the page file for the current request based on resolved path

        The function checks plugin-provided paths first, then falls back to the main
        application's file system. If no matching file or virtual route is found,
        a 404 page is returned.
        """
        from pyonir.core.parser import DeserializeFile
        await self.set_app_context()
        app_ctx = self.app_ctx_ref
        path_str = self.path
        is_home = self.is_home
        ctx_route, ctx_paths = app_ctx.request_paths or ('', [])
        ctx_route = ctx_route or ''
        ctx_slug = ctx_route[1:]
        path_slug = path_str[1:]

        virtual_route, virtual_path = self.get_virtual_route()
        request_segments = [
            segment for segment in path_slug.split('/')
            if segment and segment not in (app_ctx.API_DIRNAME, ctx_slug)
        ]

        # Skip if no paths or route doesn't match
        if not ctx_paths or (not is_home and not path_str.startswith(ctx_route)):
            return None

        # Try resolving to actual file paths
        protected_segment = [s if i > len(request_segments)-1 else f'_{s}' for i,s in enumerate(request_segments)]

        for root_path in ctx_paths:
            if not self.is_api and root_path.endswith(app_ctx.API_DIRNAME): continue
            category_index = os.path.join(root_path, *request_segments, 'index.md')
            single_page = os.path.join(root_path, *request_segments) + BaseApp.EXTENSIONS['file']
            single_protected_page = os.path.join(root_path, *protected_segment) + BaseApp.EXTENSIONS['file']

            for candidate in (category_index, single_page, single_protected_page):
                if os.path.exists(candidate):
                    route_page = DeserializeFile(candidate, app_ctx=app_ctx.app_ctx)
                    if virtual_route:
                        merge_dict(derived=virtual_route.data, src=route_page.data)
                        route_page.apply_filters()
                    self.file = route_page
                    self.server_response.status_code = 200
                    self.set_file_resolver()
                    return None
        if not virtual_path:
            error_page = DeserializeFile('404_ERROR')
            error_page.data = self.render_error()
            self.server_response.status_code = 404
            self.file = error_page
        else:
            virtual_route.replay_retry()
            self.file = virtual_route
            self.server_response.status_code = 200
            self.set_file_resolver()

    def set_file_resolver(self):
        """Updates request data a callable method to execute during request."""
        from pyonir import Site
        from pyonir.core.utils import get_attr
        if not self.file: return
        resolver_obj = self.file.data.get('@resolvers', {})
        resolver_action = resolver_obj.get(self.method)
        if not resolver_action: return
        resolver_path = resolver_action.pop('call')

        # TODO: use the app ctx activated plugins instead of global app
        app_plugin = list(filter(lambda p: p.name == resolver_path.split('.')[0], Site.activated_plugins))
        app_plugin = app_plugin[0] if len(app_plugin) else self.pyonir_app
        resolver = app_plugin.reload_resolver(resolver_path)
        custom_response_headers = get_attr(resolver_action, 'headers', {})

        if custom_response_headers:
            self.server_response.set_headers_from_dict(custom_response_headers)
            resolver_action.pop('headers')

        self.file.data.update(resolver_action)
        self.request_input.body.update(resolver_action)
        self.file_resolver = resolver


    def render_error(self):
        """Data output for an unknown file path for a web request"""
        return {
            "url": self.url,
            "title": f"{self.path} was not found!",
            "content": f"Perhaps this page once lived but has now been archived or permanently removed from {self.app_ctx_ref.name}."
        }

    def get_virtual_route(self) -> Union[tuple[DeserializeFile, str], None]:
        """Applies virtual route data to the current request file if available."""
        app_ctx = self.app_ctx_ref
        ctx_virtual_file_path = os.path.join(app_ctx.pages_dirpath, VIRTUAL_ROUTES_FILENAME) + BaseApp.EXTENSIONS['file']
        if not os.path.exists(ctx_virtual_file_path): return None
        ctx_virtual_file = DeserializeFile(ctx_virtual_file_path, app_ctx=app_ctx.app_ctx)
        vkey, vdata, vpath_params, wildcard_vdata = self._get_virtual_params(ctx_virtual_file.data)

        if vpath_params and vkey:
            self.path_params.update(vpath_params)
            ctx_virtual_file.replay_retry()
            vdata = ctx_virtual_file.data.get(vkey) if vkey else vdata
        ctx_virtual_file.data = {'url': self.url, 'slug': self.slug, **(vdata or {})}
        ctx_virtual_file.is_virtual_route = bool(vkey)
        if wildcard_vdata:
            merge_dict(wildcard_vdata, ctx_virtual_file.data)
        ctx_virtual_file.apply_filters()
        return ctx_virtual_file, vkey

    def _get_virtual_params(self, virtual_data: Dict = None) -> Union[tuple[str, dict, dict, dict], tuple[None, None, None, dict]]:
        """Performs url pattern matching against virtual routes and returns vitual page data and new path parameter values."""
        _data = (virtual_data or {})
        wildcard_data = _data.pop('*') if _data.get('*') else {}
        virtual_api_url = self.is_api and self.url.replace(self.app_ctx_ref.API_ROUTE, '')
        for vurl, vdata in _data.items():
            has_match = self._matching_route(self.url, vurl)
            # virtual routes may require api access without the need to define separate routes
            if virtual_api_url and not has_match:
                has_match = self._matching_route(virtual_api_url, vurl)
            if has_match:
                return vurl, vdata, has_match, wildcard_data
        return None, None, None, wildcard_data

    def get_flash_messages(self) -> dict:
        """Pops and returns all flash messages from session"""
        if self.server_request:
            session_data = self.server_request.session
            flashes = session_data.get('__flash__') or {}
            if flashes:
                del session_data['__flash__']
            return flashes
        return {}

    def add_flash(self, key: str, value: any):
        flash_obj = self.server_request.session.get('__flash__') or {}
        flash_obj[key] = value
        self.server_request.session['__flash__'] = flash_obj

    def pull_flash(self, key):
        return self.flashes.get(key)

    @staticmethod
    def _matching_route(route_path: str, regex_path: str) -> Optional[dict]:
        """Returns path parameters when match is found for virtual routes"""
        from starlette.routing import compile_path
        path_regex, path_format, *args = compile_path(regex_path)
        match = path_regex.match(route_path)# check if request path matches the router regex
        trail_match = match or path_regex.match(route_path+'/')
        if trail_match:
            params = args[0] if args else {}
            res = trail_match.groupdict()
            for key, converter in params.items():
                res[key] = converter.convert(res[key])
            return res

class PyonirAuthService:
    """
    Abstract base class defining authentication and authorization route resolvers,
    including role and permission checks.
    """

    @staticmethod
    async def sign_up(request: PyonirBaseRequest) -> PyonirRestResponse:
        """
        Handles the user sign-up process for the authentication system.
        ---
        @resolvers.POST:
            call: {method_import_path}
        @security.responses:
            account_exists:
                status_code: 409
                message: An account with this email already exists. Please use a different email or <a href="/sign-in">Sign In</a>.
            success:
                status_code: 201
                message: Account created successfully with {user.email}.Try signing in to your account. here <a href="/sign-in">Sign In</a>.
            error:
                status_code: 400
                message: Validation errors occurred. {user.errors}
            unauthorized:
                status_code: 401
                message: Unauthorized access. Please log in.
        ---
        Args:
            request (PyonirBaseRequest):
                The incoming request object containing authentication data,
                including `authorizer` with `user_creds` (email and password) and
                a `response` object to be returned to the client.

        Returns:
            PyonirRestResponse:
                An authentication response containing status, message, and
                additional data (e.g., user ID or error details).
        """
        authorizer = request.security
        if authorizer.creds.is_valid():
            existing_user = authorizer.get_user_profile()
            if existing_user:
                response = authorizer.responses.ACCOUNT_EXISTS
                response.status_code = 409
            else:
                response = authorizer.responses.SERVER_OK
        else:
            response = authorizer.responses.ERROR
            response.status_code = 400

        return response

    @staticmethod
    async def sign_in(request: PyonirBaseRequest) -> PyonirRestResponse:
        """
        Authenticate a user and return a JWT or session token.
        ---
        @resolvers.POST:
            call: {method_import_path}
            responses:
                success:
                    status_code: 200
                    message: You have signed in successfully.
        ---
        :param request: PyonirBaseRequest - The web request
        :return: PyonirAuthResponse - A JWT or session token if authentication is successful, otherwise None.
        """
        authorizer = request.security
        authorizer.set_signin_attempt()
        if not authorizer.creds.is_valid():
            server_response = authorizer.responses.INVALID_CREDENTIALS
        else:
            if authorizer.has_signin_exceeded():
                server_response = authorizer.responses.TOO_MANY_REQUESTS
            else:
                _user = authorizer.get_authenticated_user()
                if not _user:
                    server_response = authorizer.responses.NO_ACCOUNT_EXISTS
                else:
                    authorizer.create_session(_user)
                    server_response = authorizer.responses.SUCCESS
                    authorizer.reset_signin_attempts()

        return server_response

    @staticmethod
    async def sign_out(request: PyonirBaseRequest) -> PyonirRestResponse:
        """
        Invalidate a user's active session or token.
        ---
        @resolvers.GET:
            call: {call_path}
            redirect: /sign-in
        ---
        :param request: PyonirBaseRequest - The web request
        :return: bool - True if sign_out succeeded, otherwise False.
        """
        authorizer = request.security
        authorizer.end_session()
        return authorizer.responses.USER_SIGNED_OUT

    @staticmethod
    async def refresh_token(request: PyonirBaseRequest) -> Optional[str]:
        """
        Refresh an expired access token.

        :param request: BaseRequest - The web request.
        :return: Optional[str] - A new access token if successful, otherwise None.
        """
        authorizer = request.auth
        authorizer.refresh()
        return authorizer.response

    async def verify_authority(self, token: str, permission: str) -> bool:
        """
        Verify if the provided token grants the requested permission.

        :param token: str - The access token to check.
        :param permission: str - The permission to validate.
        :return: bool - True if the user has the permission, otherwise False.
        """
        raise NotImplementedError

    async def check_role(self, token: str, role: str) -> bool:
        """
        Check if the user has the specified role.

        :param token: str - The access token.
        :param role: str - The required role.
        :return: bool - True if the user has the role, otherwise False.
        """
        raise NotImplementedError

    async def get_current_user(self, token: str) -> Optional[dict]:
        """
        Retrieve the current user's details from a token.

        :param token: str - The authentication token.
        :return: Optional[dict] - A dictionary of user details, or None if invalid.
        """
        raise NotImplementedError
