def iml(value: any, expression: str) -> str:
    """converts jinja value into interactive markup for use by OptimlJS"""
    return f'<iml js="{expression}">{value}</iml>'
