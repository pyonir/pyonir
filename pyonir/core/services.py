import os
from abc import ABC
from typing import Optional, get_type_hints

from pyonir.core.generators import gen_template

from pyonir.core.app import BaseApp


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

