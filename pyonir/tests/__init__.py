import os, unittest, json, textwrap
from pyonir.parser import Parsely
from pyonir.parser import Parsely
from pyonir import init

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
    App = init(__file__)
    file = Parsely(os.path.join(os.path.dirname(__file__),'test.md'), App.app_ctx)
    # generate_tests(file)
    print(file.data)
    pass