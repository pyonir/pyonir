import os, time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple, Any, Dict, Optional

from starlette_wtf import csrf_token

from pyonir.models.user import User, Role, PermissionLevel, Roles, UserSignIn
from pyonir.pyonir_types import PyonirRequest, PyonirApp, PyonirRestResponse


@dataclass
class UserCredentials:
    """Represents user credentials for login"""
    email: str
    """User's email address is required for login"""

    password: str = ''
    """User's password for login is optional, can be empty for SSO"""

    remember_me: bool = False
    """Flag to remember user session, defaults to False"""

    has_session: bool = False
    """Flag to indicate if the login is via Single Sign-On (SSO)"""

    token: str = ''
    """User auth token"""

    @classmethod
    def from_request(cls, request: PyonirRequest) -> 'UserCredentials':
        """New sign in user"""
        email = request.form.get('email')
        password = request.form.get('password')
        remember_me = request.form.get('remember_me')
        if not email and not password: return cls(email='***')
        return cls(email=email, password=password, remember_me=remember_me)

    @classmethod
    def from_session(cls, session_data: dict) -> 'UserCredentials':
        """Create an instance from session data."""
        uid = session_data.get('user')
        return cls(email='***', has_session=bool(uid), token=uid) if uid else None

    @classmethod
    def from_header(cls, auth: 'Auth') -> 'UserCredentials':
        """Decodes the authorization header to extract user credentials."""
        from pyonir import Site
        auth_header = auth.request.headers.get('authorization')
        if auth_header is None:
            return None
        username = ''
        password = ''
        site_salt = auth.app.SECRET_SAUCE
        auth_type, auth_token = auth_header.split(' ', 1)
        if auth_type.startswith('Basic'):
            import base64
            decoded = base64.b64decode(auth_token).decode('utf-8')
            email, password = decoded.split(':', 1)
        if auth_type.startswith('Bearer'):
            # Handle Bearer token if needed
            user_creds = jwt_decoder(auth_token, site_salt)
            email, password = user_creds.get('username'), user_creds.get('password')
            pass
        return cls(email=username, password=password, has_session=True) if username and password else None


def auth_required(role: Role = None, perms: PermissionLevel = None):
    """
    Decorator for Auth methods to ensure the instance model is valid
    before executing the method.
    Raises ValueError if validation fails.
    """
    from functools import wraps

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from pyonir import Site
            import inspect
            is_async = inspect.iscoroutinefunction(func)

            authorizer = Auth(request=Site.server.request, app=Site)
            if not authorizer.user:
                formatted_msg = authorizer.responses.UNAUTHORIZED.message.format(
                    user=authorizer.user_creds,
                    request=authorizer.request
                )
                authorizer.response = authorizer.responses.UNAUTHORIZED.response(message=formatted_msg)
                # authorizer.response.data = authorizer.user_creds._errors
                return authorizer.response
            return await func(*args, **kwargs) if is_async else func(*args, **kwargs)
        return wrapper

    return decorator

@auth_required()
def test_auth(request: PyonirRequest, app: PyonirApp) -> 'AuthResponse':
    authorizer = Auth(request, app)
    authorizer.response = authorizer.responses.SUCCESS if authorizer.user else authorizer.responses.UNAUTHORIZED
    if authorizer.user:
        authorizer.response.data = authorizer.user
    return authorizer.response

def generate_id(from_email=None) -> str:
    """Generates a unique identifier based on the from_email address."""
    import uuid
    if from_email is None:
        return str(uuid.uuid1())
    (name, domain) = from_email.strip().split('@') if '@' in from_email else (from_email, 'no_domain_specified')
    ext = domain.split('.').pop()
    return f"{ext}_{name}@{domain.replace('.' + ext, '')}"

def hash_password(password_str: str) -> str:
    """Hashes a password string using Argon2."""
    from argon2 import PasswordHasher
    ph = PasswordHasher()
    return ph.hash(password_str.strip())


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

def format_time_remaining(time_remaining):
    # Format time in human-readable way
    mins, secs = divmod(int(time_remaining), 60)
    hrs, mins = divmod(mins, 60)

    if hrs:
        time_str = f"{hrs}h {mins}m {secs}s"
    elif mins:
        time_str = f"{mins}m {secs}s"
    else:
        time_str = f"{secs}s"
    return time_str

def get_client_ip(request):
    # Handle reverse proxy / load balancer headers first
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

def get_geolocation(ip_address: str) -> Dict[str, Any]:
    """Returns geolocation information for the given IP address."""
    if not ip_address:
        return None
    from requests import get
    loc = get(f'https://ipapi.co/{ip_address}/json/')
    loc = loc.json()
    return loc

def client_location(request: PyonirRequest) -> Optional[dict]:
    """Returns the requester's location information."""
    if not request or not request.headers:
        return None
    ip = get_client_ip(request)
    if not ip: return None
    location = get_geolocation(ip)
    return location

def jwt_decoder(jwt_token: str, salt: str)-> dict:
    """Returns decoded jwt object"""
    import jwt
    return jwt.decode(jwt_token, salt, algorithms=['HS256'])


class AuthResponse(PyonirRestResponse):
    """
    Represents a standardized authentication response.

    Attributes:
        message (str): A human-readable message describing the response.
        status_code (int): The associated HTTP status code for the response.
    """
    def response(self, message: str = None, status_code: int = None) -> 'AuthResponse':
        """Returns a new AuthResponse with updated message and status code, or defaults to current values."""
        return AuthResponse(
            message=message or self.message,
            status_code=status_code or self.status_code
        )


class AuthResponses:
    """Enum-like class that provides standardized authentication responses."""

    ERROR = AuthResponse(
        message="Authentication failed",
        status_code=400
    )
    """AuthResponse: Indicates an authentication error due to invalid credentials or bad input (HTTP 400)."""

    INVALID_CREDENTIALS = AuthResponse(
        message="The credentials provided is incorrect.",
        status_code=401
    )
    """AuthResponse: Indicates failed credential authentication (HTTP 401)."""

    SUCCESS = AuthResponse(
        message="Authentication successful",
        status_code=200
    )
    """AuthResponse: Indicates successful authentication (HTTP 200)."""

    ACTIVE_SESSION = AuthResponse(
        message="Authentication successful. session is active",
        status_code=200
    )
    """AuthResponse: Active authentication session (HTTP 200)."""

    UNAUTHORIZED = AuthResponse(
        message="Unauthorized access",
        status_code=401
    )
    """AuthResponse: Indicates missing or invalid authentication credentials (HTTP 401)."""

    SESSION_EXPIRED = AuthResponse(
        message="Session has expired. New Sign in required",
        status_code=401
    )
    """AuthResponse: Indicates missing or invalid authentication credentials (HTTP 401)."""

    NO_ACCOUNT_EXISTS = AuthResponse(message="Account not found.", status_code=409)
    """Error: The requested action cannot be completed because the user does not have an account."""

    USER_SIGNED_OUT = AuthResponse(message="User signed out", status_code=200)
    """AuthResponse: User signed out"""

    ACCOUNT_EXISTS = AuthResponse(message="Account already exists", status_code=409)
    """AuthResponse: Indicates that the user account already exists (HTTP 409)."""

    SOMETHING_WENT_WRONG = AuthResponse(message="Something went wrong, please try again later", status_code=422)
    """AuthResponse: Indicates a general error occurred during authentication (HTTP 422)."""

    TOO_MANY_REQUESTS = AuthResponse(message="Too many requests. Try again later", status_code=429)
    """AuthResponse: Indicates too many requests have been made, triggering rate limiting (HTTP 429)."""

    def __init__(self, responses: dict = None) -> None:
        """Initializes the AuthResponses enum with custom responses if provided."""
        if not responses: return
        for key, res_obj in responses.items():
            message = res_obj.get('message', '')
            status_code = res_obj.get('status_code', 200)
            setattr(self, key.upper(), AuthResponse(message=message, status_code=status_code))


class TaskAuthority:
    """
    Represents a standardized task authority for specific application actions.

    Attributes:
        name (str): A human-readable name describing the task.
        roles (Any): The roles authorized to perform a task.
    """
    def __init__(self, name: str, roles: Optional[Any] = None) -> None:
        self.name: str = name
        self.roles: list[Role] = roles if roles is not None else {}

    def create(self, name: Optional[str] = None, roles: Optional[Any] = None) -> 'TaskAuthority':
        """
        Returns a new TaskAuthority with updated name and roles,
        defaulting to the current instance values if not provided.
        """
        return TaskAuthority(
            name=name or self.name,
            roles=roles or self.roles
        )


class TaskAuthorities:
    """
    Collection of standardized TaskAuthority instances for the application.

    You can also provide a dictionary of custom responses to dynamically add authorities.
    """

    UPLOAD_FILE = TaskAuthority(
        name="UploadFile",
        roles=[Roles.CONTRIBUTOR]
    )

    DELETE_FILE = TaskAuthority(
        name="DeleteFile",
        roles=[Roles.CONTRIBUTOR, Roles.AUTHOR]
    )

    def __init__(self, tasks_map: dict = None) -> None:
        """
        Initializes the TaskAuthorities collection with custom tasks_map if provided.

        Args:
            tasks_map (dict): A mapping of authority name → dict with 'name' and 'roles'.
                              Example:
                              {
                                  "export_data": {
                                      "name": "ExportData",
                                      "roles": [Role("Exporter"), Role("Admin")]
                                  }
                              }
        """
        if not tasks_map:
            return

        for key, res_obj in tasks_map.items():
            name = res_obj.get("name", "")
            roles = [Role.from_string(r) for r in res_obj.get("roles", [])]
            setattr(self, key.upper(), TaskAuthority(name=name, roles=roles))



class AuthSecurity:
    """Handles authentication security settings for a web request."""

    def __init__(self, authorizer: "Auth") -> None:
        self._is_authorized = None
        self._is_authenticated = None
        self._accepted: bool = None
        self.type: str = ""  # Allowed values: basic | oauth2 | saml
        self.redirect_to: str = ""
        self.role: str = None
        self.perms: list[PermissionLevel] = []

        definitions = getattr(authorizer.request.file, "data", {}).get("@auth") \
            if getattr(authorizer.request, "file", None) else None

        if definitions:
            for key, value in definitions.items():
                if key=='role': key = key.upper()
                setattr(self, key, value)

    @property
    def is_authenticated(self) -> bool:
        return self._is_authenticated

    @property
    def is_authorized(self) -> bool:
        return self._is_authorized

    @property
    def accepted(self) -> bool:
        return self._accepted

    @property
    def is_required(self) -> bool:
        return bool(self.type)

    @property
    def verify_authorization(self) -> Optional[TaskAuthorities]:
        """Returns a map of Authorization Tasks. Each tasks provided authorization for roles"""
        return None

    def check(self, authorizer: "Auth") -> 'AuthSecurity':
        """Checks if route requires authentication and if the user is authorized."""
        if not self.is_required: return None # nothing is required here
        requires_authentication = self.type in {"basic", "oauth2", "saml"}
        route_perms = getattr(Roles, self.role) if self.role else None
        has_authentication = requires_authentication and authorizer.user is not None
        has_authorization = has_authentication and route_perms and authorizer.user.has_perms(route_perms)
        self._accepted = has_authorization or has_authentication
        self._is_authorized = has_authorization
        self._is_authenticated = has_authentication
        return self


class Auth:
    """Handles user authentication and account management."""
    SIGNIN_ATTEMPTS = 3
    """Maximum number of sign-in attempts allowed before locking the account."""

    LOCKOUT_TIME = 300
    """Time in seconds to lock the account after exceeding sign-in attempts."""

    user_model = User
    """User model used for authentication, defaults to User class."""

    def __init__(self, request: PyonirRequest, app: PyonirApp):
        self.app: PyonirApp = app
        self.request: PyonirRequest = request

        self.request_token = self.request.headers.get('X-CSRF-Token', self.request.form.get('csrf_token'))
        """CSRF token for the request, used to prevent cross-site request forgery."""

        self.response: AuthResponse = None
        """AuthResponse: The current authentication response."""

        self.user_creds: UserCredentials = self.get_user_creds()
        """User credentials extracted from the request."""

        self.user: User = None
        """"User: The authenticated user object."""

        if self.user_creds and self.user_creds.has_session:
            self.user = self.get_auth_user()

        self.app.TemplateEnvironment.globals['user'] = self.user


    @property
    def security(self) -> AuthSecurity:
        return AuthSecurity(self)

    @property
    def session(self) -> dict:
        """Returns the session object from the request."""
        return self.request.server_request.session if self.request.server_request else None

    @property
    def responses(self) -> AuthResponses:
        """AuthResponses: Provides standardized authentication responses. Overrides can be provided via request data."""
        return AuthResponses(self.request.file.data.get('responses') if self.request.file else None)

    def create_jwt(self, user_id: str = None, user_role: str = '', exp_time=None):
        """Returns session jwt object based on profile info"""
        import datetime
        exp_time = exp_time or self.LOCKOUT_TIME
        exp_in = (datetime.datetime.now() + datetime.timedelta(minutes=exp_time)).timestamp()
        user_jwt = {
            "sub": user_id or self.user.id,
            "role": user_role or self.user.role,
            "remember_for": exp_time,
                "iat": datetime.datetime.now(),
                "iss": self.app.domain,
                "exp": exp_in
            }
        jwt_token = self._encode_jwt(user_jwt)
        return jwt_token

    def _encode_jwt(self, jwt_data: dict):
        """Returns base64 encoded jwt token encoded with pyonir app secret"""
        import jwt
        try:
            enc_jwt = jwt.encode(jwt_data, self.app.SECRET_SAUCE, algorithm='HS256')
            return enc_jwt
        except Exception as e:
            print(f"Something went wrong refreshing jwt token. {e}")
            raise

    def create_signin(self, user: User = None):
        """Signs in a user account based on the provided credentials."""
        if self.user:
            self.response = self.responses.ACTIVE_SESSION
            return
        if self.signin_has_exceeded(): return
        self.response = self.responses.SOMETHING_WENT_WRONG

        user = self.query_account() if not user else user
        if not user:
            self.response = self.responses.NO_ACCOUNT_EXISTS
        if user:
            if user.auth_from == 'oauth2':
                # TODO: handle checking oauth
                user_jwt = self.create_jwt(user.id, user.role)
                self.log_user_location(user)
                user.save_to_file(user.file_path)
                user.save_to_session(self.request, value=user_jwt)
                pass

            elif user.auth_from == 'basic':
                salt = self.app.salt
                requested_passw = Auth.harden_password(salt, self.user_creds.password, user.auth_token)
                has_valid_creds = Auth.verify_password(user.password, requested_passw)
                if has_valid_creds:
                    user_jwt = self.create_jwt(user.id, user.role)
                    # update csrf token after successful login for better security
                    user.auth_token = csrf_token(self.request.server_request)
                    user.password = self.hash_password(self.user_creds.password, with_token=user.auth_token)
                    user.save_to_session(self.request, key='csrf_token', value=user.auth_token)
                    user.save_to_session(self.request, value=user_jwt)
                    self.log_user_location(user)
                    user.save_to_file(user.file_path)


                    self.response = self.responses.SUCCESS
                    self.response.data['auth_token'] = user_jwt
                    self.response.data['access_token'] = user.auth_token
                else:
                    self.response = self.responses.INVALID_CREDENTIALS

    def log_user_location(self, user: User):
        """logs user signin location"""
        new_location = client_location(self.request)
        if not new_location: return
        match_keys = ["ip", "device"]
        locations = user.signin_locations or []
        print(new_location)
        # Find matches using list comprehension
        matches = [loc for loc in locations if all(loc[k] == new_location[k] for k in match_keys)]

        if matches:
            matches[0]["signin_count"] = matches[0].get("signin_count", 0) + 1
        else:
            new_loc = dict(new_location)
            new_loc["signin_count"] = 1
            locations.append(new_loc)


    def refresh(self) -> bool:
        new_jwt = self.create_jwt()
        self.user.save_to_session(self.request, value=new_jwt)

    def create_profile(self, user: User = None) -> bool:
        """Creates a user profile and saves it to the filesystem."""
        if self.user:
            self.response = self.responses.ACTIVE_SESSION
            return False

        user_token = csrf_token(self.request.server_request)
        if not user:
            hashed_password = self.hash_password(self.user_creds.password, with_token=user_token)
            user = User(email=self.user_creds.email, password=hashed_password, auth_token=user_token)
        uid = generate_id(user.email)
        user_account_path = os.path.join(self.app.contents_dirpath, 'users', uid, 'profile.json')
        user.id = uid
        user.file_path = user_account_path
        user.file_dirpath = os.path.dirname(user_account_path)
        if os.path.exists(user_account_path):
            self.response = self.responses.ACCOUNT_EXISTS
            return False

        self.log_user_location(user)

        created = user.save_to_file(user_account_path)
        if created:
            formated_msg = self.responses.SUCCESS.message.format(user=user, request=self.request)
            self.response = self.responses.SUCCESS.response(formated_msg)
        else:
            self.response = self.responses.SOMETHING_WENT_WRONG
            print(f"Failed to create user account at {user_account_path}")
        return created

    def signin_has_exceeded(self):
        """Logs a user login attempt."""
        if not self.request.server_request: return
        time_remaining, lockout_expired = self.signin_lockout_expired()
        max_attempts = self.signin_attempt_exceeded()
        if max_attempts and not time_remaining:
            # start the lock out timer
            self.session['locked_until'] = time.time() + self.LOCKOUT_TIME

        if max_attempts and time_remaining:
            print("LOCKOOUT FOR TOO MANY REQUREST")
            self.response = self.responses.TOO_MANY_REQUESTS
            return True
        current_session = self.session.get('login_attempts', 0)
        self.session['login_attempts'] = current_session + 1
        return False

    def signin_lockout_expired(self) -> Tuple[str, bool]:
        """Checks if lockout time has expired to allow signin"""
        if not self.request.server_request: return '', False
        lock_timeout = self.session.get('locked_until', 0)
        if lock_timeout:
            now = time.time()
            time_remaining = lock_timeout - now
            fmt_remaining = format_time_remaining(time_remaining)
            print(fmt_remaining)
            if time_remaining <= 0:
                print("time expired!!")
                self.session['login_attempts'] = 0
                self.session.pop('locked_until')
                return fmt_remaining, True
            return fmt_remaining, False
        return '', False

    def signin_attempt_exceeded(self) -> bool:
        """Checks if the user has exceeded the maximum number of sign-in attempts."""
        if not self.request.server_request: return False
        return self.session.get('login_attempts', 0) >= self.SIGNIN_ATTEMPTS

    def get_auth_user(self) -> Optional[User]:
        user = self.query_account()
        if not user:
            self.response = self.responses.SESSION_EXPIRED
            self.session.clear()
            return None
        # update jwt expiration time
        user.save_to_session(self.request, value=self.create_jwt(user.id, user.role))
        self.response = self.responses.ACTIVE_SESSION
        return user


    def query_account(self, user_email: str = None) -> User:
        """Queries the user account based on the provided credentials."""
        uid =  generate_id(self.user_creds.email) if not self.user_creds.has_session else user_email or self.user_creds.email
        user_account_path = os.path.join(self.app.contents_dirpath, 'users', uid or '', 'profile.json')
        user_account = User.from_file(user_account_path, app_ctx=self.app.app_ctx) if os.path.exists(user_account_path) else None
        return user_account

    def get_user_creds(self) -> 'UserCredentials':
        """Decodes the authorization header to extract user credentials."""
        auth_header = self.request.headers.get('authorization')
        username = ''
        auth_type, auth_token = auth_header.split(' ', 1) if auth_header else (None, None)
        session_id = self.session.get('user')
        if session_id:
            session_user = self.decode_jwt(session_id) or {}
            username = session_user.get('sub')
        elif auth_type and auth_type.startswith('Bearer'):
            # Handle Bearer token if needed
            user_creds = self.decode_jwt(auth_token)
            email, _ = user_creds.get('username')
        elif auth_type and auth_type.startswith('Basic'):
            import base64
            decoded = base64.b64decode(auth_token).decode('utf-8')
            email, password = decoded.split(':', 1)
            return UserCredentials(email=email, password=password)
        else:
            return UserCredentials.from_request(self.request)

        return UserCredentials(email=username, has_session=True)


    def send_email(self):
        """Sends an email to the user."""
        raise NotImplementedError("Email sending is not implemented yet.")

    def is_user_authenticated(self) -> bool:
        """Checks if the user is authenticated."""
        raise NotImplementedError()

    def hash_password(self, password: str = None, with_token: str = None) -> str:
        """Rehashes the user's password with the current site salt and request token."""
        salt = self.app.salt
        return hash_password(self.harden_password(salt, password, with_token or self.request.session_token))

    def decode_jwt(self, jwt_token) -> dict:
        """Returns decoded jwt object"""
        from pyonir import Site
        from jwt import DecodeError, ExpiredSignatureError
        try:
            return jwt_decoder(jwt_token, Site.SECRET_SAUCE)
        except ExpiredSignatureError as ee:
            print(f"JWT token expired: {ee}")
            # TODO: set user creds from the request perhaps?
            self.response = self.responses.SESSION_EXPIRED
            self.session.clear()
        except Exception as e:
            print(f"{__name__} method - {str(e)}: {type(e).__name__}")

    @staticmethod
    def verify_password(encrypted_pwd, input_password) -> bool:
        """Check User credentials"""
        return check_pass(encrypted_pwd, input_password)

    @staticmethod
    def harden_password(site_salt: str, password: str, token: str):
        """Strengthen all passwords by adding a site salt and token."""
        if not site_salt or not password or not token:
            raise ValueError("site_salt, password, and token must be provided")
        return f"{site_salt}${password}${token}"


class AuthService(ABC):
    """
    Abstract base class defining authentication and authorization route resolvers,
    including role and permission checks.
    """

    @abstractmethod
    async def sign_up(self, request: PyonirRequest) -> AuthResponse:
        """
        Handles the user sign-up process for the authentication system.
        ---
        @resolvers.POST:
            call: {method_import_path}
            responses:
                account_exists:
                    message: An account with this email already exists. Please use a different email or <a href="/sign-in">Sign In</a>.
                success:
                    status_code: 200
                    message: Account created successfully with {user.email}.Try signing in to your account. here <a href="/sign-in">Sign In</a>.
                error:
                    status_code: 400
                    message: Validation errors occurred. {user.errors}
                unauthorized:
                    status_code: 401
                    message: Unauthorized access. Please log in.
        ---
        Args:
            request (PyonirRequest):
                The incoming request object containing authentication data,
                including `authorizer` with `user_creds` (email and password) and
                a `response` object to be returned to the client.

        Returns:
            AuthResponse:
                An authentication response containing status, message, and
                additional data (e.g., user ID or error details).
        """
        authorizer = request.auth
        # perform model validation on request
        signin_creds = UserSignIn(email=authorizer.user_creds.email, password=authorizer.user_creds.password)
        if signin_creds.is_valid():
            authorizer.create_profile()
            authorizer.request.add_flash('sign_up', authorizer.response.to_dict())
        return authorizer.response

    @abstractmethod
    async def sign_in(self, request: PyonirRequest) -> AuthResponse:
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
        :param request: PyonirRequest - The web request
        :return: AuthResponse - A JWT or session token if authentication is successful, otherwise None.
        """
        authorizer = request.auth
        authorizer.create_signin()
        authorizer.request.add_flash('sign_in', authorizer.response.to_dict())
        return authorizer.response

    @abstractmethod
    async def sign_out(self, request: PyonirRequest) -> AuthResponse:
        """
        Invalidate a user's active session or token.
        ---
        @resolvers.GET:
            call: {call_path}
            redirect: /sign-in
        ---
        :param request: PyonirRequest - The web request
        :return: bool - True if sign_out succeeded, otherwise False.
        """
        authorizer = request.auth
        authorizer.session.clear()
        return authorizer.responses.USER_SIGNED_OUT

    @abstractmethod
    async def refresh_token(self, request: PyonirRequest) -> Optional[str]:
        """
        Refresh an expired access token.

        :param request: PyonirRequest - The web request.
        :return: Optional[str] - A new access token if successful, otherwise None.
        """
        authorizer = request.auth
        authorizer.refresh()
        return authorizer.response

    @abstractmethod
    async def verify_authority(self, token: str, permission: str) -> bool:
        """
        Verify if the provided token grants the requested permission.

        :param token: str - The access token to check.
        :param permission: str - The permission to validate.
        :return: bool - True if the user has the permission, otherwise False.
        """
        raise NotImplementedError

    @abstractmethod
    async def check_role(self, token: str, role: str) -> bool:
        """
        Check if the user has the specified role.

        :param token: str - The access token.
        :param role: str - The required role.
        :return: bool - True if the user has the role, otherwise False.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_current_user(self, token: str) -> Optional[dict]:
        """
        Retrieve the current user's details from a token.

        :param token: str - The authentication token.
        :return: Optional[dict] - A dictionary of user details, or None if invalid.
        """
        raise NotImplementedError

