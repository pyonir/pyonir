import os, json, textwrap
from pyonir.parser import Parsely
from pyonir import init

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
        f"{indent*2}App = init(__file__)\n"
        f"{indent*2}cls.parselyFile = Parsely(os.path.join(os.path.dirname(__file__),'contents', 'test.md'), App.app_ctx)\n\n"
        f"{case_meths}"
    )

    parsely.save(os.path.join(os.path.dirname(__file__), 'generated_test.py'), test_class)

if __name__=='__main__':
    # generate_pyonir_types()
    App = init(__file__)
    file = App.parse_file(os.path.join(os.path.dirname(__file__),'contents','test.md'))
    generate_tests(file)
    # print(file.data)
    pass