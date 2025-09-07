# -*- coding: utf-8 -*-
import os, sys
from pyonir import utilities
from pyonir.models.app import BaseApp, Optional
from pyonir.core import PyonirApp
from pyonir.utilities import get_version

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

__version__: str = get_version(PYONIR_TOML_FILE)
Site: Optional[BaseApp] = None

def init(entry_file_path: str, use_themes: bool = None):
    """Initializes existing Pyonir application"""
    global Site
    # Set Global Site instance
    # if options: options = PyonirOptions(**(options or {}))
    sys.path.insert(0, os.path.dirname(os.path.dirname(entry_file_path)))
    Site = PyonirApp(entry_file_path, use_themes=use_themes)
    Site.process_configs()
    if use_themes:
        Site.configure_themes()
    return Site