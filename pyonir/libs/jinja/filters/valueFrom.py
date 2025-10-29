def valueFrom(rowObj, path=""):
    from pyonir.core.utils import get_attr
    return get_attr(rowObj, path)