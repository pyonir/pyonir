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
    space = "\t"
    for key, value in parsely.data.items():
        test_case = textwrap.dedent(f"""
        {space}def test_{key}(self):
            {space}self.assertEqual({json.dumps(value)}, self.parselyFile.data.get('{key}'))
        """)
        cases.append(test_case)

    case_meths = "\n".join(cases)
    test_class = textwrap.dedent(f"""\
import unittest, os
true = True
class {name}Tests(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        from pyonir.parser import Parsely
        from pyonir import init
        App = init(__file__)
        cls.parselyFile = Parsely(os.path.join(os.path.dirname(__file__), 'test.md'), App.app_ctx)
    {case_meths}
    """)

    parsely.save(os.path.join(os.path.dirname(__file__), 'generated_test.py'), test_class)

if __name__=='__main__':
    # generate_pyonir_types()
    App = init(__file__)
    # file = App.parsely_file('test.md')
    # generate_tests(file)
    # print(file.data)
    pass