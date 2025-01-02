def limit(iterList, limit=6):
	l = list()
	for i, itm in enumerate(iterList):
		if limit >= i:
			l.append(itm)
		else:
			break
	return l