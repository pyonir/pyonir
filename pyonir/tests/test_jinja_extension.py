import pytest
from unittest.mock import patch
from jinja2 import Environment, DictLoader
from pyonir.libs.jinja.extensions.IncludeOnceExtension import IncludeOnceExtension


@pytest.fixture
def jinja_env():
    """Initializes a Jinja2 environment with the custom extension and standard templates."""
    loader = DictLoader({
        "style.css": "body { color: red; }",
        "script.js": "function hello() { console.log('hello'); }",
        "doc.html": "<p>Hello World</p>",
        "unknown.txt": "Some plain text content",
        "style_dup.css": "body { color: red; }",
    })
    env = Environment(loader=loader, extensions=[IncludeOnceExtension])
    return env


def test_include_once_inline_rendering(jinja_env):
    """Verify standard include_once renders content directly (and minifies CSS/JS)."""
    template = jinja_env.from_string("{% include_once 'style.css' %}")
    rendered = template.render()
    assert "body{color:red}" in rendered or "body { color: red; }" in rendered


def test_include_once_deduplication(jinja_env):
    """Verify a template file included multiple times renders only once."""
    template = jinja_env.from_string("""
        {% include_once 'style.css' %}
        {% include_once 'style.css' %}
    """)
    rendered = template.render().strip()

    # Second inclusion should evaluate to an empty string
    assert rendered.count("body") == 1


def test_compile_true_collects_to_bucket(jinja_env):
    """Verify include_once with compile=True suppresses output and stores content in bucket."""
    template = jinja_env.from_string("""
        {% include_once 'style.css', compile=True %}
        {% render_compressed 'css' %}
    """)
    rendered = template.render().strip()
    assert rendered.startswith("<style>")
    assert "color:red" in rendered


def test_render_compressed_js_bucket(jinja_env):
    """Verify compiled JS files are wrapped in <script> tags when rendered."""
    template = jinja_env.from_string("""
        {% include_once 'script.js', compile=True %}
        {% render_compressed 'js' %}
    """)
    rendered = template.render().strip()
    assert rendered.startswith("<script>")
    assert "hello" in rendered


def test_render_compressed_empty_bucket(jinja_env):
    """Verify render_compressed returns an empty string if no files were compiled."""
    template = jinja_env.from_string("{% render_compressed 'css' %}")
    assert template.render() == ""


def test_unknown_keyword_arguments_handled_safely(jinja_env):
    """Verify parsing handles unrecognized keyword arguments gracefully."""
    template = jinja_env.from_string("{% include_once 'style.css', foo='bar', compile=False %}")
    rendered = template.render()
    assert "body" in rendered


def test_request_scoped_storage():
    """Verify request object takes precedence for storage if available in context."""
    class MockRequest:
        pass

    req = MockRequest()
    env = Environment(
        loader=DictLoader({"style.css": "body { margin: 0; }"}),
        extensions=[IncludeOnceExtension],
    )

    template = env.from_string("{% include_once 'style.css' %}")
    template.render(request=req)

    # Check that the storage attributes were attached to the MockRequest instance
    assert hasattr(req, "_included_once_files")
    assert "style.css" in req._included_once_files


def test_helper_get_extension():
    """Test standard and edge cases for extension extraction."""
    ext_func = IncludeOnceExtension._get_extension

    assert ext_func("styles.css") == "css"
    assert ext_func("APP.JS") == "js"
    assert ext_func("no_ext_file") == "no_ext_file"
    assert ext_func(".gitignore") == "gitignore"


def test_minify_content_exception_fallback():
    """Verify minification exceptions are caught and raw content is returned."""
    with patch("csscompressor.compress", side_effect=Exception("Minification error")):
        result = IncludeOnceExtension._minify_content("body { color: red; }", "css")
        assert result == "body { color: red; }"


def test_render_compressed_unknown_extension(jinja_env):
    """Verify compiled assets with non-standard extensions render without HTML wrapper tags."""
    template = jinja_env.from_string("""
        {% include_once 'unknown.txt', compile=True %}
        {% render_compressed 'txt' %}
    """)
    rendered = template.render().strip()
    assert rendered == "Some plain text content"
    assert "<style>" not in rendered
    assert "<script>" not in rendered