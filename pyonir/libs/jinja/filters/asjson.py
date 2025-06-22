

def asjson(input):
    """converts input parameter into a json string. pyonir json_serial is used to convert non supported data types"""
    from pyonir.utilities import json_serial
    import json
    d = json.dumps(input, default=json_serial)
    return d.replace('<script>','<\/script>').replace('</script>','<\/script>')
