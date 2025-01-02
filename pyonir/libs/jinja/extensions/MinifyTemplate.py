from jinja2 import nodes
from jinja2.ext import Extension


def init():
    return MinifyTemplate

class MinifyTemplate(Extension):

    tags = {'minify'}
    def __init__(self, environment):
        super(MinifyTemplate, self).__init__(environment)

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        body = parser.parse_statements(['name:endminify'], drop_needle=True)
        return nodes.CallBlock(self.call_method('_minify'), [], [], body).set_lineno(lineno)

    @staticmethod
    def _minify(caller):
        return caller().strip()
        # try:
        #     return html_minify(caller())
        # except:
        #     return caller().strip()
        # return minify(
        #     caller(),
        #     remove_comments=True,
        #     reduce_boolean_attributes=True,
        #     remove_optional_attribute_quotes=False )
