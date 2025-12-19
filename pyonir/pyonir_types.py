from enum import unique, Enum
from typing import Optional, Callable, List, Tuple
from pyonir.core.templating import TemplateEnvironment, PyonirThemes, Theme

TEXT_RES: str = 'text/html'
JSON_RES: str = 'application/json'
EVENT_RES: str = 'text/event-stream'
PAGINATE_LIMIT: int = 6
VIRTUAL_ROUTES_FILENAME: str = '.virtual_routes'

# === Route Definitions ===
PagesPath = str
APIPath = str
RoutePath = str
"""Represents the URL path of a route (e.g., '/about', '/api/data')."""

RouteFunction = Callable
"""A callable that handles a specific route request (e.g., controller function)."""

RouteMethods = List[str]
"""HTTP methods supported by a route (e.g., ['GET', 'POST'])."""

RouteOptions = Optional[dict]
"""Additional options for a route, such as authentication requirements."""

PyonirRoute = Tuple[RoutePath, RouteFunction, RouteMethods, RouteOptions]
"""A single route entry containing the path, its handler function, and allowed HTTP methods."""

PyonirRouters = List[Tuple[RoutePath, List[PyonirRoute]]]
"""A collection (or group) of routes, usually organized by feature or resource, and often mounted under"""


# === Application Module Definitions ===

AppName = str
"""The name identifier for an app module."""

ModuleName = str
"""The Python module name used for import or registration."""

AppEndpoint = str
"""The base endpoint path where the app is mounted."""

AppPaths = List[str]
"""A list of file or URL paths associated with the app."""

AppContentsPath = str
"""The root path to the static or content files of the app."""

AppSSGPath = str
"""The path used for static site generation output."""

AppContextPaths = Tuple[AppName, RoutePath, AppPaths]
"""Context binding tuple that connects an app name to a route and its associated paths."""

AppCtx = Tuple[ModuleName, RoutePath, AppContentsPath, AppSSGPath]
"""Full application context including module reference and content/static paths."""

AppRequestPaths = Tuple[RoutePath, AppPaths]
"""Tuple representing an incoming request path and all known paths for resolution."""

class EnvConfig:
    """Application Configurations"""
    APP_ENV: str
    APP_KEY: str
    APP_DEBUG: bool
    APP_URL: str
    DB_CONNECTION: str
    DB_HOST: str
    DB_PORT: int
    DB_DATABASE: str
    DB_USERNAME: str
    DB_PASSWORD: str

class PyonirHooks(str):
    AFTER_INIT = 'AFTER_INIT'
    ON_REQUEST = 'ON_REQUEST'
    ON_PARSELY_COMPLETE = 'ON_PARSELY_COMPLETE'

@unique
class BaseEnum(Enum):
    def __str__(self):
        return self.value

    @classmethod
    def contains(cls, item: str) -> bool:
        if not isinstance(item, str):
            return False
        item = item.lower()
        return any(
            item == member.value or item == member.name.lower()
            for member in cls
        )