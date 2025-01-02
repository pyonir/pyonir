def valueFrom(rowObj, path=""):
    targetObj = None
    for key in path.split('.'):
        try:
            if targetObj:
                targetObj = targetObj[key]
            else:
                targetObj = rowObj[key]
            pass
        except Exception as error:
            raise error
    return targetObj