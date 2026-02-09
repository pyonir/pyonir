
from pyonir.core.parser import DeserializeFile
true = True
false = False


# test cases for DeserializeFile
def test_nested_blocks(mock_file: DeserializeFile):
    data = mock_file.data
    pass

def test_url(mock_file: DeserializeFile):
    obj = "/"
    assert obj == mock_file.data.get('url')


def test_slug(mock_file: DeserializeFile):
    obj = ""
    assert obj == mock_file.data.get('slug')


def test_inline_list_of_scalrs_types(mock_file: DeserializeFile):
    obj = [1, true, "hello", 3.14, 1, true, "hello", 3.14]
    assert obj == mock_file.data.get('inline_list_of_scalrs_types')


def test_single_item_list(mock_file: DeserializeFile):
    obj = ["just one thing here"]
    assert obj == mock_file.data.get('single_item_list')


def test_string_phonenumber(mock_file: DeserializeFile):
    obj = "(111) 123-3456"
    assert obj == mock_file.data.get('string_phonenumber')


def test_string_types(mock_file: DeserializeFile):
    obj = "1, true, hello, 3.14"
    assert obj == mock_file.data.get('string_types')


def test_basic(mock_file: DeserializeFile):
    obj = "scalar value"
    assert obj == mock_file.data.get('basic')


def test_dict_value(mock_file: DeserializeFile):
    obj = {"my_key": "my_value", "another_key": "another_value"}
    assert obj == mock_file.data.get('dict_value')


def test_list_value(mock_file: DeserializeFile):
    obj = ["one", "two", "three"]
    assert obj == mock_file.data.get('list_value')


def test_dynamic_list_blocks(mock_file: DeserializeFile):
    obj = [{"ages": [1, true, "hello", 3.14, {"dict_key": "dict_value"}]}, {"this": {"age": 3, "key": "some value"}}]
    assert obj == mock_file.data.get('dynamic_list_blocks')


def test_inline_list_of_maps(mock_file: DeserializeFile):
    obj = [{"one": 1}, {"two": true}, {"three": "hello"}]
    assert obj == mock_file.data.get('inline_list_of_maps')


def test_inline_dict_value(mock_file: DeserializeFile):
    obj = "my_lnkey: my_lnvalue, another_lnkey: another_lnvalue"
    assert obj == mock_file.data.get('inline_dict_value')


def test_multiline_block(mock_file: DeserializeFile):
    obj = "What is this here? Content types enable you to organize and manage content in a consistent way for specific kinds of pages.\nthere is no such thing as a Python JSON object. JSON is a language independent file \nformat that finds its roots in JavaScript, and is supported by many languages. end of mulitiline block.\n"
    assert obj == mock_file.data.get('multiline_block')


def test_js(mock_file: DeserializeFile):
    obj = "if ('serviceWorker' in navigator) {\n  window.addEventListener('load', function() {\n    navigator.serviceWorker.register('/public/pwa/js/service-worker.js');\n  });\n}\n"
    assert obj == mock_file.data.get('js')


def test_content(mock_file: DeserializeFile):
    obj = "What is this here? Content types enable you to organize and manage content in a consistent way for specific kinds of pages.\nthere is no such thing as a Python JSON object. JSON is a language independent file \nformat that finds its roots in JavaScript, and is supported by many languages. If your YAML\n"
    assert obj == mock_file.data.get('content')


def test_html(mock_file: DeserializeFile):
    obj = "<app-screen>\n    <footer>\n        <span subtitle>Hello</span>\n        <img src=\"/public/some-image.jpg\" alt=\"find dibs logo\">\n        <button type=\"submit\">Join Pyonir</button>\n    </footer>\n</app-screen>\n"
    assert obj == mock_file.data.get('html')

