from abc import ABC
from typing import Optional

from pyonir import PyonirRequest

from pyonir.core.app import BaseApp
from pyonir.core.server import PyonirJSONResponse
from pyonir.core.security import PyonirSecurity, PyonirUser


class BaseService(ABC):
    """
    Abstract base class defining a generic service interface for Pyonir applications.
    """
    app: Optional[BaseApp]
    """Pyonir plugin app instance"""

    name: str
    """Name of the service"""

    version: str
    """Version of the service"""

    endpoint: str
    """API endpoint for the service"""

    @property
    def active_user(self) -> Optional[PyonirUser]:
        """Returns the currently authenticated user, if any."""
        security: PyonirSecurity = self.app.server.request.security if self.pyonir_app.server.request else None
        user = security.authenticated_user if security else None
        return user

    @property
    def pyonir_app(self) -> BaseApp:
        """Main pyonir application"""
        from pyonir import Site
        return self.app or Site

    @property
    def endpoint_url(self) -> str:
        """Construct the full URL for the service endpoint."""
        return f"{self.endpoint}/{self.version}" if self.version else self.endpoint

    def generate_api(self, namespace: str = '') -> None:
        """Generate API resolvers for the service."""
        if not self.app:
            raise ValueError("Pyonir application instance is not available.")
        if self.app.server.is_active: return
        import os
        base_path = os.path.join(self.app.contents_dirpath, self.app.API_DIRNAME)
        self.app.generate_resolvers(self, output_dirpath=base_path, namespace=namespace or self.name)


class PyonirAuthService:
    """
    Abstract base class defining authentication and authorization route resolvers,
    including role and permission checks.
    """

    @staticmethod
    def save_image_from_url(url: str, directory: str) -> str:
        """
        Download an image from a URL and save it to a local directory.

        Args:
            url: External image URL
            directory: Local directory where image will be saved

        Returns:
            Path to the saved image
        """
        import requests
        from pathlib import Path
        from urllib.parse import urlparse
        parsed = urlparse(url)
        url_path = Path(parsed.path)

        url_name = url_path.stem or "image"
        url_ext = url_path.suffix

        path = Path(directory)

        if path.suffix:  # file path provided
            filepath = path.with_suffix(url_ext) if url_ext else path
            filepath.parent.mkdir(parents=True, exist_ok=True)
        else:  # directory provided
            path.mkdir(parents=True, exist_ok=True)
            filepath = path / (url_name + url_ext)

        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)

        return str(filepath)

    @staticmethod
    async def sign_up(request: PyonirRequest) -> PyonirJSONResponse:
        """
        Handles the user sign-up process for the authentication system.
        ---
        @resolvers.POST:
            call: {method_import_path}
        @security.responses:
            account_exists:
                status_code: 409
                message: An account with this email already exists. Please use a different email or <a href="/onboard/sign-in">Sign In</a>.
            success:
                status_code: 201
                message: Account created successfully with {user.email}.Try signing in to your account. here <a href="/onboard/sign-in">Sign In</a>.
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
            PyonirJSONResponse:
                An authentication response containing status, message, and
                additional data (e.g., user ID or error details).
        """
        security = request.security
        if security.creds.is_valid():
            existing_user = security.get_user_profile()
            if existing_user:
                response = security.responses.ACCOUNT_EXISTS
                response.status_code = 409
            else:
                response = security.responses.SERVER_OK
        else:
            response = security.responses.ERROR
            response.status_code = 400

        return response

    @staticmethod
    async def sign_in(request: PyonirRequest) -> PyonirJSONResponse:
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
        :return: PyonirAuthResponse - A JWT or session token if authentication is successful, otherwise None.
        """
        security = request.security
        security.set_signin_attempt()
        if not security.creds.is_valid():
            server_response = security.responses.INVALID_CREDENTIALS
        else:
            if security.has_signin_exceeded():
                server_response = security.responses.TOO_MANY_REQUESTS
            else:
                _user = security.authenticated_user
                if not _user:
                    server_response = security.responses.NO_ACCOUNT_EXISTS
                else:
                    security.create_session(_user)
                    server_response = security.responses.SUCCESS
                    security.reset_signin_attempts()

        return server_response

    @staticmethod
    async def sign_out(request: PyonirRequest) -> PyonirJSONResponse:
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
        authorizer = request.security
        authorizer.end_session()
        return authorizer.responses.USER_SIGNED_OUT

    @staticmethod
    async def refresh_token(request: PyonirRequest) -> Optional[str]:
        """
        Refresh an expired access token.

        :param request: BaseRequest - The web request.
        :return: Optional[str] - A new access token if successful, otherwise None.
        """
        authorizer = request.security
        authorizer.refresh_token()
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