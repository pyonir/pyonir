from jinja2 import nodes
from jinja2.ext import Extension
from jinja2.nodes import ContextReference
try:
    from css_html_js_minify import html_minify, js_minify, css_minify
except:
    # help("modules")
    pass


def init():
    return BlockPushExtension


class BlockPushExtension(Extension):
    """Defines custom blocks to gather template fragments and output them in specific areas in the jinja template"""
    tags = {'pull', 'yield'}

    def __init__(self, environment):
        super(BlockPushExtension, self).__init__(environment)
        self.callstring = ""
        environment.extend(
            block_pull_cache={},
            block_string=None
        )
        # print(environment.block_string)

    def parse(self, parser):
        """Parse tokens """
        tag = parser.stream.__next__()
        ctx_ref = ContextReference()

        if tag.value == "pull":
            args = [ctx_ref, parser.parse_expression(), nodes.Const(tag.lineno)]
            body = parser.parse_statements(['name:endpull'], drop_needle=True)
            callback = self.call_method('compiled', args)
        else:
            body = []
            # self.callstring = parser.parse_expression().value
            self.environment.block_string = parser.parse_expression().value
            # self.environment.block_string.add('foo',parser.parse_expression().value)
            callback = self.call_method('scope', [ctx_ref])

        return nodes.CallBlock(callback, [], [], body).set_lineno(tag.lineno)

    def scope(self, context, caller):
        if self.environment.block_string and self.environment.block_pull_cache.get(self.environment.block_string):
            # print('\n\n', len(self.environment.block_pull_cache.get(self.environment.block_string)))
            return "".join(self.environment.block_pull_cache[self.environment.block_string])
        return "" 

    def compiled(self, context, tagname, linenum, caller):
        # print(self.cls.block_pull)
        tagname = "{}".format(tagname, linenum)
        if not self.environment.block_pull_cache.get(tagname, False):
            self.environment.block_pull_cache[tagname] = []
        self.environment.block_pull_cache[tagname].append(
            caller().strip()
        )
        return "<!-- moved {} from line {} -->".format(tagname, linenum)
