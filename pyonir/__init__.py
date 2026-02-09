# -*- coding: utf-8 -*-
import os, sys
from pyonir.core.app import BaseApp, Optional
from pyonir.core.authorizer import PyonirBaseRequest
from pyonir.core.utils import get_version
from pyonir.core.app import BaseApp, BasePlugin
from pyonir.core.database import CollectionQuery
from pyonir.core.schemas import BaseSchema
from pyonir.core.server import PyonirServer

# Pyonir settings
PYONIR_DIRPATH = os.path.abspath(os.path.dirname(__file__))
PYONIR_TOML_FILE = os.path.join(os.path.dirname(PYONIR_DIRPATH), "pyproject.toml")
PYONIR_LIBS_DIRPATH = os.path.join(PYONIR_DIRPATH, "libs")
PYONIR_PLUGINS_DIRPATH = os.path.join(PYONIR_LIBS_DIRPATH, 'plugins')
PYONIR_SETUPS_DIRPATH = os.path.join(PYONIR_LIBS_DIRPATH, 'app_setup')
PYONIR_JINJA_DIRPATH = os.path.join(PYONIR_LIBS_DIRPATH, 'jinja')
PYONIR_JINJA_TEMPLATES_DIRPATH = os.path.join(PYONIR_JINJA_DIRPATH, "templates")
PYONIR_JINJA_EXTS_DIRPATH = os.path.join(PYONIR_JINJA_DIRPATH, "extensions")
PYONIR_JINJA_FILTERS_DIRPATH = os.path.join(PYONIR_JINJA_DIRPATH, "filters")

__version__: str = "0.0.53"
Site: Optional[BaseApp] = None


class PyonirRequest(PyonirBaseRequest): pass
class PyonirCollection(CollectionQuery): pass
class PyonirSchema(BaseSchema): pass
class PyonirPlugin(BasePlugin): pass

class Pyonir(BaseApp):
    """Pyonir Application"""
    def __init__(self, entry_file_path: str,
                 use_themes: bool = None,
                 salt: str = None):
        """Initializes existing Pyonir application"""
        global Site
        sys.path.insert(0, os.path.dirname(os.path.dirname(entry_file_path)))
        super().__init__(entry_file_path,
                         use_themes=use_themes,
                         salt=salt)
        Site = self
        self.process_configs()
        if self.use_themes:
            self.configure_themes()