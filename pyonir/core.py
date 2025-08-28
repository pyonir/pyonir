from pyonir.models.app import BaseApp, BasePlugin
from pyonir.models.database import BaseCollection
from pyonir.models.schemas import BaseSchema
from pyonir.models.server import BaseRequest, BaseServer


class PyonirApp(BaseApp):pass
class PyonirServer(BaseServer): pass
class PyonirRequest(BaseRequest): pass
class PyonirCollection(BaseCollection): pass
class PyonirSchema(BaseSchema): pass
class PyonirPlugin(BasePlugin): pass