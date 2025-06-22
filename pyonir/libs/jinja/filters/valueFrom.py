def valueFrom(rowObj, path=""):
    from pyonir.utilities import get_attr
    return get_attr(rowObj, path)