
import pytest, os
from pyonir.models.parser import DeserializeFile
true = True
false = False
parselyFile = DeserializeFile(os.path.join(os.path.dirname(__file__),'contents', 'test.md'))


# test cases for DeserializeFile

def test_url():
    obj = "/"
    assert obj == parselyFile.data.get('url')


def test_slug():
    obj = ""
    assert obj == parselyFile.data.get('slug')


def test_inline_list_of_scalrs_types():
    obj = [1, true, "hello", 3.14, 1, true, "hello", 3.14]
    assert obj == parselyFile.data.get('inline_list_of_scalrs_types')


def test_single_item_list():
    obj = ["just one thing here"]
    assert obj == parselyFile.data.get('single_item_list')


def test_string_phonenumber():
    obj = "(111) 123-3456"
    assert obj == parselyFile.data.get('string_phonenumber')


def test_string_types():
    obj = "1, true, hello, 3.14"
    assert obj == parselyFile.data.get('string_types')


def test_basic():
    obj = "scalar value"
    assert obj == parselyFile.data.get('basic')


def test_dict_value():
    obj = {"my_key": "my_value", "another_key": "another_value"}
    assert obj == parselyFile.data.get('dict_value')


def test_list_value():
    obj = ["one", "two", "three"]
    assert obj == parselyFile.data.get('list_value')


def test_dynamic_list_blocks():
    obj = [{"ages": [1, true, "hello", 3.14, {"dict_key": "dict_value"}]}, {"this": {"age": 3, "key": "some value"}}]
    assert obj == parselyFile.data.get('dynamic_list_blocks')


def test_inline_list_of_maps():
    obj = [{"one": 1}, {"two": true}, {"three": "hello"}]
    assert obj == parselyFile.data.get('inline_list_of_maps')


def test_inline_dict_value():
    obj = "my_lnkey: my_lnvalue, another_lnkey: another_lnvalue"
    assert obj == parselyFile.data.get('inline_dict_value')


def test_multiline_block():
    obj = "What is this here? Content types enable you to organize and manage content in a consistent way for specific kinds of pages.\nthere is no such thing as a Python JSON object. JSON is a language independent file \nformat that finds its roots in JavaScript, and is supported by many languages. end of mulitiline block.\n"
    assert obj == parselyFile.data.get('multiline_block')


def test_js():
    obj = "if ('serviceWorker' in navigator) {\n  window.addEventListener('load', function() {\n    navigator.serviceWorker.register('/public/pwa/js/service-worker.js');\n  });\n}\n"
    assert obj == parselyFile.data.get('js')


def test_content():
    obj = "What is this here? Content types enable you to organize and manage content in a consistent way for specific kinds of pages.\nthere is no such thing as a Python JSON object. JSON is a language independent file \nformat that finds its roots in JavaScript, and is supported by many languages. If your YAML\n"
    assert obj == parselyFile.data.get('content')


def test_html():
    obj = "<app-screen>\n    <footer>\n        <span subtitle>Hello</span>\n        <img src=\"/public/some-image.jpg\" alt=\"find dibs logo\">\n        <button type=\"submit\">Join Pyonir</button>\n    </footer>\n</app-screen>\n"
    assert obj == parselyFile.data.get('html')

