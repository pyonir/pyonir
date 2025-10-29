from pyonir.core.app import BaseApp, BasePlugin
from pyonir.core.database import BaseFSQuery
from pyonir.core.schemas import BaseSchema
from pyonir.core.server import BaseRequest, BaseServer


class PyonirApp(BaseApp):pass
class PyonirServer(BaseServer): pass
class PyonirRequest(BaseRequest): pass
class PyonirCollection(BaseFSQuery): pass
class PyonirSchema(BaseSchema): pass
class PyonirPlugin(BasePlugin): pass