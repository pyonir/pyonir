import os, json, textwrap
import subprocess
import sys

from pyonir.parser import Parsely, Page
from pyonir import init
from pyonir.tests.backend.demo_controller import DemoService

def generate_pyonir_types():
    from pyonir.core import PyonirApp, PyonirRequest, PyonirPlugin

    for cls in [PyonirApp, PyonirRequest, PyonirPlugin]:
        generate_dataclass_from_class(cls)

def generate_dataclass_from_class(cls, output_dir="types"):
    from typing import get_type_hints
    attr_map = get_type_hints(cls)
    props_map = {k: type(v).__name__ for k, v in cls.__dict__.items() if isinstance(v, property)}
    meth_map = {k: callable for k, v in cls.__dict__.items() if callable(v)}
    all_map = dict(**props_map, **meth_map, **attr_map)
    lines = [f"class {cls.__name__}:"]
    if not cls.__annotations__:
        lines.append("    pass")
    else:
        for name, typ in all_map.items():
            lines.append(f"    {name}: {typ.__class__.__name__}")
    with open(os.path.join(os.path.dirname(__file__), output_dir, f"{cls.__name__}.py"), "w") as f:
        f.write("\n".join(lines))

def generate_tests(parsely: Parsely):
    cases = []
    name = parsely.__class__.__name__
    indent = " " * 4
    for key, value in parsely.data.items():
        test_case = (
            f"{indent}def test_{key}(self):\n"
            f"{indent*2}self.assertEqual({json.dumps(value)}, self.parselyFile.data.get('{key}'))\n"
        )
        cases.append(test_case)

    case_meths = "\n".join(cases)
    test_class = (
        "import unittest, os\n"
        "true = True\n"
        f"class {name}Tests(unittest.TestCase):\n"
        f"{indent}@classmethod\n"
        f"{indent}def setUpClass(cls):\n"
        f"{indent*2}from pyonir.parser import Parsely\n"
        f"{indent*2}from pyonir import init\n"
        f"{indent*2}App = init(__file__, serve_frontend=False)\n"
        f"{indent*2}cls.parselyFile = Parsely(os.path.join(os.path.dirname(__file__),'contents', 'test.md'), App.app_ctx)\n\n"
        f"{case_meths}"
    )

    parsely.save(os.path.join(os.path.dirname(__file__), 'generated_test.py'), test_class)

if __name__=='__main__':
    app_dirpath = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'libs', 'app_setup')
    # generate_pyonir_types()
    # App = init(__file__, serve_frontend=False)
    # DemoService(App)
    # # full path to module function
    # mod = Parsely.import_module('backend.demo_controller.subscriber_values')
    # # path to static class method
    # static_mod = Parsely.import_module('backend.demo_controller.DemoService.get_numbers', App.app_dirpath)
    # # path to init package class method
    # pkg_mod = Parsely.import_module('backend.models.EmailSubscriber', App.app_dirpath)

    # def paste_from_clipboard():
    #     process = subprocess.Popen('pbpaste', env={'LANG': 'en_US.UTF-8'}, stdout=subprocess.PIPE)
    #     output, error = process.communicate()
    #     return output.decode('utf-8')
    #
    # my_mod = None
    # while True:
    #
    #     mod_pth = input(f"Whats your module?").strip()
    #     if not mod_pth:
    #         mod_pth = paste_from_clipboard()
    #     my_mod = Parsely.import_module(mod_pth, App.app_dirpath)
    #     if my_mod is None:
    #         break
    #     else:
    #         res = my_mod()
    #         print(res)
    #         print(f"Module {mod_pth} is now loaded")

    file = Parsely(os.path.join(os.path.dirname(__file__),'contents','test.md'))
    # filex = App.parse_file(os.path.join(os.path.dirname(__file__),'contents','pages','form-demo.md'))


    # generate_tests(file)
    # print(file.data)

    # configs = query_files(os.path.join(app_dirpath, 'contents', 'configs'), app_ctx=App.app_ctx)
    # pages = query_files(os.path.join(app_dirpath, 'contents'), app_ctx=App.app_ctx, model=Page)
    # themes = query_files(os.path.join(app_dirpath, 'frontend'), app_ctx=App.app_ctx, model=Theme)
    pass