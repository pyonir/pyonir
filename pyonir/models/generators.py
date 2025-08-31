from __future__ import annotations

import inspect, os
from pyonir.utilities import create_file

gen_template = """\
@resolvers:
    {methods}.call: {import_method_path}
    {gen_params}
===
{docs}
"""

def generate_file(method: str, **kwargs):
    def decorator(func):
        func._generate_file = (method, kwargs)
        return func
    return decorator

class APIGen:
    def __init_subclass__(cls):
        orig_init = cls.__init__

        def __init__(self, *args, **kwargs):
            orig_init(self, *args, **kwargs)
            cls_name = cls.__name__
            namespace = getattr(self, '_apigen_namespace', cls_name)
            print(f"Generating {cls_name} API endpoint definitions for:")
            for name, fn in cls.__dict__.items():
                if hasattr(fn, "_generate_file"):
                    method, params = fn._generate_file
                    fn_docs = inspect.getdoc(fn)
                    fn_name = fn.__name__
                    import_method_path = f"{namespace}.{fn_name}"
                    gen_params = "\n\t".join([f"{k}: {v}" for k, v in params.items()]) if params else ""
                    file_path = os.path.join(self.app.api_dirpath,namespace, fn_name+'.md')
                    create_file(str(file_path), gen_template.format(gen_params=gen_params, methods=method, import_method_path=import_method_path, docs=fn_docs))
                    print(f"\t{fn_name} at {file_path}")

        cls.__init__ = __init__
