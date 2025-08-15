import unittest, os
true = True
class ParselyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pyonir.parser import Parsely
        from pyonir import init
        App = init(__file__, serve_frontend=False)
        cls.parselyFile = Parsely(os.path.join(os.path.dirname(__file__),'contents', 'test.md'), App.app_ctx)

    def test_basic(self):
        self.assertEqual("scalar value", self.parselyFile.data.get('basic'))

    def test_dict_value(self):
        self.assertEqual({"my_key": "my_value", "another_key": "another_value"}, self.parselyFile.data.get('dict_value'))

    def test_list_value(self):
        self.assertEqual(["one", "two", "three"], self.parselyFile.data.get('list_value'))

    def test_dynamic_list_blocks(self):
        self.assertEqual([{"ages": [1, true, "hello", 3.14, {"dict_key": "dict_value"}]}, {"this": {"age": 3, "key": "some value"}}], self.parselyFile.data.get('dynamic_list_blocks'))

    def test_inline_list_of_scalrs_types(self):
        self.assertEqual([1, true, "hello", 3.14], self.parselyFile.data.get('inline_list_of_scalrs_types'))

    def test_inline_list_of_maps(self):
        self.assertEqual([{"one": 1}, {"two": true}, {"three": "hello"}], self.parselyFile.data.get('inline_list_of_maps'))

    def test_inline_dict_value(self):
        self.assertEqual({"my_lnkey": "my_lnvalue", "another_lnkey": "another_lnvalue"}, self.parselyFile.data.get('inline_dict_value'))

    def test_multiline_block(self):
        self.assertEqual("What is this here? Content types enable you to organize and manage content in a consistent way for specific kinds of pages.\nthere is no such thing as a Python JSON object. JSON is a language independent file \nformat that finds its roots in JavaScript, and is supported by many languages. end of mulitiline block.\n", self.parselyFile.data.get('multiline_block'))

    def test_js(self):
        self.assertEqual("if ('serviceWorker' in navigator) {\n  window.addEventListener('load', function() {\n    navigator.serviceWorker.register('/public/pwa/js/service-worker.js');\n  });\n}\n", self.parselyFile.data.get('js'))

    def test_content(self):
        self.assertEqual("What is this here? Content types enable you to organize and manage content in a consistent way for specific kinds of pages.\nthere is no such thing as a Python JSON object. JSON is a language independent file \nformat that finds its roots in JavaScript, and is supported by many languages. If your YAML\n", self.parselyFile.data.get('content'))

    def test_html(self):
        self.assertEqual("<app-screen>\n    <footer>\n        <span subtitle>Hello</span>\n        <img src=\"/public/some-image.jpg\" alt=\"find dibs logo\">\n        <button type=\"submit\">Join Pyonir</button>\n    </footer>\n</app-screen>\n", self.parselyFile.data.get('html'))
