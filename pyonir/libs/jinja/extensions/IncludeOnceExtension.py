from jinja2 import nodes
from jinja2.ext import Extension

import csscompressor
from css_html_js_minify import js_minify


class IncludeOnceExtension(Extension):
    tags = {"include_once", "render_compressed"}

    def parse(self, parser):
        token = next(parser.stream)
        lineno = token.lineno
        ctx_ref = nodes.ContextReference()

        if token.value == "include_once":
            # 1. Parse the mandatory first expression (template_name)
            template_arg = parser.parse_expression()

            # Default compile = False
            compile_arg = nodes.Const(False)

            # 2. Parse optional keyword arguments (e.g., compile=True)
            while parser.stream.current.type != "block_end":
                if parser.stream.skip_if("comma"):
                    continue

                if parser.stream.current.type == "name":
                    param_name = parser.stream.current.value
                    if param_name == "compile":
                        parser.stream.expect("name")  # consume 'compile'
                        parser.stream.expect("assign")  # consume '='
                        compile_arg = parser.parse_expression()
                    else:
                        # Skip or handle unknown keyword arguments safely
                        parser.stream.expect("name")
                        parser.stream.expect("assign")
                        parser.parse_expression()

            call_node = self.call_method(
                "_collect_file",
                [template_arg, compile_arg, ctx_ref],
                lineno=lineno,
            )
            return nodes.Output([call_node], lineno=lineno)

        elif token.value == "render_compressed":
            # Parse mandatory extension string (e.g., 'css' or 'js')
            ext_arg = parser.parse_expression()

            call_node = self.call_method(
                "_render_compressed_bucket",
                [ext_arg, ctx_ref],
                lineno=lineno,
            )
            return nodes.Output([call_node], lineno=lineno)

    @staticmethod
    def _get_extension(filename):
        """Extracts and normalizes file extension"""
        return filename.split('.').pop().lower()

    @staticmethod
    def _get_storage(context):
        """Request-scoped storage container."""
        req = context.get("request")
        container = req if req is not None else context

        if not hasattr(container, "_included_once_files"):
            container._included_once_files = set()

        return container

    @staticmethod
    def _get_bucket(storage, ext):
        """Dynamically gets or creates the bucket list using getattr/setattr."""
        attr_name = f"_collected_{ext}_content"
        if not hasattr(storage, attr_name):
            setattr(storage, attr_name, [])
        return getattr(storage, attr_name)

    @staticmethod
    def _minify_content(content, ext):
        """Minifies content based on file extension if minifiers are available."""
        try:
            if ext == "css" and csscompressor:
                return csscompressor.compress(content)
            elif ext == "js" and js_minify:
                return js_minify(content)
        except Exception as e:
            pass
        return content

    def _collect_file(self, template_name, compile_asset, context):
        storage = self._get_storage(context)

        # 1. Deduplicate globally across all calls
        if template_name in storage._included_once_files:
            return ""

        storage._included_once_files.add(template_name)

        # 2. Render fragment content
        template = self.environment.get_template(template_name)
        raw_content = template.render(context.get_all())
        ext = self._get_extension(template_name)

        # 3. Store or output based on `compile` parameter
        if compile_asset:
            bucket = self._get_bucket(storage, ext)
            bucket.append(raw_content)
            return ""
        else:
            # Inline mode: compress immediately and wrap in appropriate tags
            return self._minify_content(raw_content, ext)

    def _render_compressed_bucket(self, ext, context):
        storage = self._get_storage(context)
        ext = ext.lower().lstrip(".")
        bucket = self._get_bucket(storage, ext)

        if not bucket:
            return ""

        combined = "\n".join(bucket)
        minified = self._minify_content(combined, ext)

        # Output wrapped HTML tag based on extension
        if ext == "css":
            return f"<style>{minified}</style>"
        elif ext == "js":
            return f"<script>{minified}</script>"
        return minified
