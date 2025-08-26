from pyonir.models.app import BaseApp, BasePlugin
from pyonir.models.database import BaseCollection
from pyonir.models.schemas import BaseSchema
from pyonir.models.server import BaseRequest, BaseServer


class PyonirApp(BaseApp):

    def install_sys_plugins(self):
        """Install pyonir system plugins"""
        from pyonir.libs.plugins.navigation import Navigation
        self.plugins_installed['pyonir_navigation'] = Navigation
        self._plugins_activated.add(Navigation(self))

class PyonirServer(BaseServer): pass
class PyonirRequest(BaseRequest): pass
class PyonirCollection(BaseCollection): pass
class PyonirSchema(BaseSchema): pass
class PyonirPlugin(BasePlugin): pass