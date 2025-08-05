import os, time

from starlette_wtf import csrf_token

from pyonir.models.user import UserCredentials, User
from pyonir.pyonir_types import PyonirRequest, PyonirApp, PyonirRestResponse

def validate_credentials(method):
    """
    Decorator for Auth methods to ensure the instance model is valid
    before executing the method.
    Raises ValueError if validation fails.
    """
    from functools import wraps
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if self.user_creds and not self.user_creds.is_valid():
            formatted_msg = self.responses.ERROR.message.format(
                user=self.user_creds,
                request=self.request
            )
            self.response = self.responses.ERROR.response(message=formatted_msg)
            self.response.data = self.user_creds.errors
            return self.response
        return method(self, *args, **kwargs)
    return wrapper

def generate_id(email=None) -> str:
    """Generates a unique identifier based on the email address."""
    import uuid
    if email is None:
        return str(uuid.uuid1())
    (name, domain) = email.strip().split('@')
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

def encode_jwt(jwt_data):
    """Returns base64 encoded jwt token"""
    import jwt
    from pyonir import Site
    try:
        enc_jwt = jwt.encode(jwt_data, Site.SECRET_SAUCE, algorithms=['HS256'])
        return enc_jwt
    except Exception as e:
        print(f"Something went wrong refreshing jwt token. {e}")
        raise

def decode_jwt(jwt_token):
    """Returns decoded jwt object"""
    from pyonir import Site
    import jwt
    try:
        return jwt.decode(jwt_token, Site.SECRET_SAUCE, algorithms=['HS256'])
    except Exception as e:
        print(f"{__name__} method - {str(e)}: {type(e).__name__}")
        return False

def auth_decode(authorization_header: str) -> UserCredentials | None:
    """Decodes the authorization header to extract user credentials."""
    if not authorization_header:
        return None
    email = ''
    password = ''
    auth_type, auth_token = authorization_header.split(' ', 1)
    if auth_type.startswith('Basic '):
        import base64
        decoded = base64.b64decode(auth_token).decode('utf-8')
        email, password = decoded.split(':', 1)
    if auth_type.startswith('Bearer '):
        # Handle Bearer token if needed
        user_creds = decode_jwt(auth_token)
        email, password = user_creds.get('email'), user_creds.get('password')
        pass
    return UserCredentials(email, password)

def sign_up(request: PyonirRequest, app: PyonirApp) -> 'AuthResponse':
    """Registers a new user with the provided credentials."""
    authorizer = Auth(request, app)
    authorizer.create_email_account()
    if request.redirect_to:
        authorizer.session['sign_up'] = authorizer.response.to_json()
    return authorizer.response

def sign_in(request: PyonirRequest, app: PyonirApp) -> 'AuthResponse':
    """Logs in a user with the provided credentials."""
    authorizer = Auth(request, app)
    authorizer.create_signin()
    authorizer.session['sign_in'] = authorizer.response.to_json()
    return authorizer.response

def sign_out(request: PyonirRequest) -> None:
    raise NotImplementedError()

def client_location(request: PyonirRequest) -> dict | None:
    """Returns the requester's location information."""
    if not request or not request.headers:
        return None
    import json, urllib
    try:
        r = urllib.request.urlopen('https://ident.me/json').read().decode('utf8')
        j = json.loads(r)
        j["device"] = request.headers.get('user-agent')
        return j
    except Exception:
        return None

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

    SUCCESS = AuthResponse(
        message="Authentication successful",
        status_code=200
    )
    """AuthResponse: Indicates successful authentication (HTTP 200)."""

    UNAUTHORIZED = AuthResponse(
        message="Unauthorized access",
        status_code=401
    )
    """AuthResponse: Indicates missing or invalid authentication credentials (HTTP 401)."""

    ACCOUNT_EXISTS = AuthResponse(message="Account already exists", status_code=409)
    """AuthResponse: Indicates that the user account already exists (HTTP 409)."""

    SOMETHING_WENT_WRONG = AuthResponse(message="Something went wrong, please try again later", status_code=422)
    """AuthResponse: Indicates a general error occurred during authentication (HTTP 422)."""

    TOO_MANY_REQUESTS = AuthResponse(message="Too many requests", status_code=429)
    """AuthResponse: Indicates too many requests have been made, triggering rate limiting (HTTP 429)."""

    def __init__(self, responses: dict = None) -> None:
        """Initializes the AuthResponses enum with custom responses if provided."""
        if not responses: return
        for key, res_obj in responses.items():
            message = res_obj.get('message', '')
            status_code = res_obj.get('status_code', 200)
            setattr(self, key.upper(), AuthResponse(message=message, status_code=status_code))


class Auth:
    """Handles user authentication and account management."""
    SIGNIN_ATTEMPTS = 3
    """Maximum number of sign-in attempts allowed before locking the account."""

    LOCKOUT_TIME = 300
    """Time in seconds to lock the account after exceeding sign-in attempts."""

    def __init__(self, request: PyonirRequest, app: PyonirApp, from_sso: bool = False):
        self.app: PyonirApp = app
        self.request: PyonirRequest = request
        self.user_creds: UserCredentials = self.get_user_creds(from_sso)
        """User credentials extracted from the request."""

        self.request_token = self.request.headers.get('csrf_token', self.request.form.get('csrf_token')) or csrf_token(request.server_request)
        """CSRF token for the request, used to prevent cross-site request forgery."""

        self.responses = AuthResponses(request.file.data.get('responses'))
        """AuthResponses: Provides standardized authentication responses. Overrides can be provided via request data."""

        self.response: AuthResponse | None = None
        """AuthResponse: The current authentication response."""

        self.user: User | None = None
        """"User: The authenticated user object."""

    @property
    def session(self) -> dict | None:
        """Returns the session object from the request."""
        return self.request.server_request.session if self.request.server_request else None

    @validate_credentials
    def create_signin(self):
        """Signs in a user account based on the provided credentials."""
        if self.signin_attempt_exceeded():
            self.session['locked_until'] = time.time() + self.LOCKOUT_TIME
            self.response = self.responses.TOO_MANY_REQUESTS
            return False
        self.signin_log_attempt()
        self.response = self.responses.ERROR
        user = self.query_account()
        self.user = user
        if user:
            salt = self.app.configs.env.salt
            requested_passw = Auth.harden_password(salt, self.user_creds.password, user.auth_token)
            has_valid_creds = Auth.verify_password(user.password, requested_passw)
            if has_valid_creds:
                user_login_location = client_location(self.request)
                user.signin_locations.append(user_login_location)
                # update auth token after successful login for better security
                user.auth_token = self.request_token
                user.password = self.hash_password()
                user.save_to_file(user.file_path)
                user.save_to_session(self.request, user.id)
                self.response = self.responses.SUCCESS
                pass

    @validate_credentials
    def create_email_account(self) -> bool:
        """Creates a new user account based on the provided credentials onto the filesystem."""
        user_creds: UserCredentials = self.user_creds
        hashed_password = self.hash_password()
        new_user = User(email=user_creds.email, password=hashed_password, auth_token=self.request_token)
        self.user = new_user
        return self.create_profile(new_user)


    def create_profile(self, user: User) -> bool:
        """Creates a user profile and saves it to the filesystem."""
        uid = generate_id(user.email)
        user_account_path = os.path.join(self.app.contents_dirpath, 'users', uid, 'profile.json')
        if os.path.exists(user_account_path):
            self.response = self.responses.ACCOUNT_EXISTS
            return False

        user_login_location = client_location(self.request)
        user.signin_locations.append(user_login_location)
        user.id = uid

        created = user.save_to_file(os.path.join(user_account_path))
        if created:
            formated_msg = self.responses.SUCCESS.message.format(user=user, request=self.request)
            self.response = self.responses.SUCCESS.response(formated_msg)
        else:
            self.response = self.responses.SOMETHING_WENT_WRONG
            print(f"Failed to create user account at {user_account_path}")
        return created

    def signin_log_attempt(self):
        """Logs a user login attempt."""
        if not self.request.server_request: return
        current_session = self.session.get('login_attempts', 0)
        self.session['login_attempts'] = current_session + 1

    def signin_attempt_exceeded(self) -> bool:
        """Checks if the user has exceeded the maximum number of sign-in attempts."""
        if not self.request.server_request: return False
        lock_timeout = self.session.get('locked_until', 0)
        has_exceeded = self.session.get('login_attempts', 0) >= self.SIGNIN_ATTEMPTS
        if lock_timeout and time.time() > lock_timeout:
            self.session['login_attempts'] = 0
            has_exceeded = False
        return has_exceeded

    def get_user_creds(self, from_sso = False) -> UserCredentials:
        """Returns user credentials from request"""
        if from_sso:
            return UserCredentials.sso()
        authorization_header = self.request.headers.get('authorization')
        auth_creds = auth_decode(authorization_header)
        if not auth_creds: auth_creds = UserCredentials(email=self.request.form.get('email'), password=self.request.form.get('password',''))
        return auth_creds

    def query_account(self) -> User | None:
        """Queries the user account based on the provided credentials."""
        uid = generate_id(self.user_creds.email)
        user_account_path = os.path.join(self.app.contents_dirpath, 'users', uid, 'profile.json')
        if not os.path.exists(user_account_path):
            self.response = self.responses.ERROR
            return None
        user_account = User.from_file(user_account_path, app_ctx=self.app.app_ctx)
        return user_account

    def send_email(self):
        """Sends an email to the user."""
        raise NotImplementedError("Email sending is not implemented yet.")

    def is_user_authenticated(self) -> bool:
        """Checks if the user is authenticated."""
        raise NotImplementedError()

    def hash_password(self) -> str:
        """Rehashes the user's password with the current site salt and request token."""
        if not self.user_creds or not self.user_creds.password:
            return ''
        salt = self.app.configs.env.salt
        return hash_password(self.harden_password(salt, self.user_creds.password, self.request_token))

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