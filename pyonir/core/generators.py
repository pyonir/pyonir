from __future__ import annotations

import inspect

gen_template = """\
@resolvers:
    {method} 
    {gen_params}
"""

def generate_file(method: str, **kwargs):
    def decorator(func):
        fn_docs = inspect.getdoc(func)
        gen_params = "\n\t".join([f"{k}: {v}" for k, v in kwargs.items()]) if kwargs else ""
        _method = f"{method}.call: "+"{method_import_path}"
        t = gen_template.format(method=_method, gen_params=gen_params, docs=fn_docs)
        func._generate_file = t, fn_docs, (method, gen_params)
        return func
    return decorator

