from abc import ABC
from typing import Optional, get_type_hints

from pyonir import PyonirApp

class BaseService(ABC):
    """
    Abstract base class defining a generic service interface for Pyonir applications.
    """
    app: Optional[PyonirApp]
    """Pyonir application instance"""

    name: str
    """Name of the service"""

    version: str
    """Version of the service"""

    endpoint: str
    """API endpoint for the service"""

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
        self.app.generate_resolvers(self, base_path, namespace=namespace)

    def __init_subclass__(cls, **kwargs):
        """Validate that required attributes are defined in subclasses."""
        super().__init_subclass__(**kwargs)

        required_attrs = get_type_hints(cls)

        for attr_name, expected_type in required_attrs.items():
            if attr_name == 'app':
                continue
            if not hasattr(cls, attr_name):
                raise TypeError(
                    f"{cls.__name__} must define class attribute '{attr_name}'"
                )

            attr_value = getattr(cls, attr_name)
            if not isinstance(attr_value, expected_type):
                raise TypeError(
                    f"{cls.__name__}.{attr_name} must be of type {expected_type.__name__}, "
                    f"got {type(attr_value).__name__}"
                )

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        # SERVICE_INSTANCES.append(instance)
        return instance
