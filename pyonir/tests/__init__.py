import os, json
import textwrap

from pyonir.models.parser import DeserializeFile
from pyonir.tests.backend.demo_controller import DemoService
from pyonir import init

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

def generate_py_tests(parsely: DeserializeFile):
    from pyonir.models.utils import create_file
    cases = []
    name = parsely.__class__.__name__
    # indent = " " * 4
    test_setup = textwrap.dedent(
        """        
        import pytest, os
        from pyonir.models.parser import DeserializeFile
        true = True
        false = False
        parselyFile = DeserializeFile(os.path.join(os.path.dirname(__file__),'contents', 'test.md'))\n\n
        # test cases for {name}
        {test_cases}
        """
    )
    test_case = """
    def test_{case_name}():
        obj = {value}
        assert obj == parselyFile.data.get('{case_name}')
    """

    for case_name, value in parsely.data.items():
        _case = test_case.format(case_name=case_name, value=json.dumps(value))
        cases.append(textwrap.dedent(_case))

    final_test_case = test_setup.format(test_cases="\n".join(cases), name=name)
    create_file(os.path.join(os.path.dirname(__file__), f'test_{name.lower()}.py'), final_test_case)

if __name__=='__main__':
    app_dirpath = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'libs', 'app_setup')
    App = init(os.path.join(app_dirpath,'main.py'), use_themes=False)
    file = DeserializeFile(os.path.join(os.path.dirname(__file__),'contents','test.md'))
    # generate_parsely_tests(file)
    generate_py_tests(file)

    pass