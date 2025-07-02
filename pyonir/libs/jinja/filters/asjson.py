

def asjson(input, escaped = False):
    """converts input parameter into a json string. pyonir json_serial is used to convert non supported data types"""
    from pyonir.utilities import json_serial
    import json, html
    d = json.dumps(input, default=json_serial)
    if escaped: return html.escape(d)
    return d
    # return d.replace('<script>','<\/script>').replace('</script>','<\/script>')
