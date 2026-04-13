

def asjson(input, escaped = False, with_props = None):
    """converts input parameter into a json string. pyonir json_serial is used to convert non supported data types"""
    from pyonir.core.utils import json_serial
    import json, html
    d = json.dumps(input, default=lambda o: json_serial(o, with_props=with_props))
    if escaped: return html.escape(d)
    return d
