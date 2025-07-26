# -*- coding: utf-8 -*-
import os, sys
from pyonir import utilities
from pyonir.parser import Parsely
from pyonir.core import PyonirHooks, TemplateEnvironment, PyonirRequest, PyonirApp
from pyonir.utilities import dict_to_class, get_attr, process_contents, load_env

# Pyonir settings
PYONIR_DIRPATH = os.path.abspath(os.path.dirname(__file__))
PYONIR_LIBS_DIRPATH = os.path.join(PYONIR_DIRPATH, "libs")
PYONIR_PLUGINS_DIRPATH = os.path.join(PYONIR_LIBS_DIRPATH, 'plugins')
PYONIR_SETUPS_DIRPATH = os.path.join(PYONIR_LIBS_DIRPATH, 'app_setup')
PYONIR_JINJA_DIRPATH = os.path.join(PYONIR_LIBS_DIRPATH, 'jinja')
PYONIR_JINJA_TEMPLATES_DIRPATH = os.path.join(PYONIR_JINJA_DIRPATH, "templates")
PYONIR_JINJA_EXTS_DIRPATH = os.path.join(PYONIR_JINJA_DIRPATH, "extensions")
PYONIR_JINJA_FILTERS_DIRPATH = os.path.join(PYONIR_JINJA_DIRPATH, "filters")
# PYONIR_MESSAGES_FILE = os.path.join(PYONIR_LIBS_DIRPATH, "system-messages.md")
# PYONIR_SSL_KEY = os.path.join(PYONIR_SETUPS_DIRPATH, "content/certs/server.key")
# PYONIR_SSL_CRT = os.path.join(PYONIR_SETUPS_DIRPATH, "content/certs/server.crt")
PYONIR_STATIC_ROUTE = "/pyonir_assets"

__version__: str = '1.0.0'
Site: PyonirApp | None = None

def init(entry_file_path: str, options: dict = None):
    """Initializes existing Pyonir application"""
    global Site
    # Set Global Site instance
    # if options: options = PyonirOptions(**(options or {}))
    sys.path.insert(0, entry_file_path)
    Site = PyonirApp(entry_file_path)
    return Site