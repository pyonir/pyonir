import os
from typing import Any, Callable
from pyonir.pyonir_types import EnvConfig


def load_modules_from(pkg_dirpath, as_list: bool = False, only_packages:bool = False)-> dict[Any, Any] | list[Any]:
    loaded_mods = {} if not as_list else []
    loaded_funcs = {} if not as_list else []
    if not os.path.exists(pkg_dirpath): return loaded_funcs
    for mod_file in os.listdir(pkg_dirpath):
        name,_, ext = mod_file.partition('.')
        if only_packages:
            pkg_abspath = os.path.join(pkg_dirpath, mod_file, '__init__.py')
            mod, func = get_module(pkg_abspath, name)
        else:
            if ext!='py': continue
            mod_abspath = os.path.join(pkg_dirpath, name.strip())+'.py'
            mod, func = get_module(mod_abspath, name)
        if as_list:
            loaded_funcs.append(func)
        else:
            loaded_mods[name] = mod
            loaded_funcs[name] = func

    return loaded_funcs

def import_module(pkg_path: str, callable_name: str) -> Callable:
    """Imports a module and returns the callable by name"""
    from pyonir.models.utils import get_attr
    import importlib
    mod_pkg = importlib.import_module(pkg_path)
    importlib.reload(mod_pkg)
    mod = get_attr(mod_pkg, callable_name, None)
    return mod

def get_module(pkg_path: str, callable_name: str) -> tuple[Any, Callable]:
    import importlib
    from pyonir.models.utils import get_attr
    spec = importlib.util.spec_from_file_location(callable_name, pkg_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for {callable_name} from {pkg_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    func = get_attr(module, callable_name) or get_attr(module, module.__name__)
    return module, func


def get_version(toml_file: str) -> str:
    import re
    from pathlib import Path
    try:
        content = Path(toml_file).read_text()
        return re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE).group(1)
    except Exception as e:
        print('Error: unable to parse pyonir version from project toml',e)
        return 'UNKNOWN'


def load_env(path=".env") -> EnvConfig:
    import warnings
    from collections import defaultdict
    from pyonir.models.server import DEV_ENV
    from pyonir.models.mapper import dict_to_class

    env = os.getenv('APP_ENV') or DEV_ENV
    env_data = defaultdict(dict)
    env_data['APP_ENV'] = env
    if not env:
        warnings.warn("APP_ENV not set. Defaulting to LOCAL mode. Expected one of DEV, TEST, PROD, LOCAL.", UserWarning)
    if not os.path.exists(path):
        return dict_to_class(env_data, EnvConfig)

    def set_nested(d, keys, value):
        """Helper to set value in nested dictionary using dot-separated keys."""
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Set in os.environ (flat)
            os.environ.setdefault(key, value)

            # Set in nested dict (structured)
            keys = key.split(".")
            set_nested(env_data, keys, value)

    return dict_to_class(env_data, EnvConfig)
