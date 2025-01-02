from babel.numbers import format_currency

def babelmoney(value, currency='', locale='en_US'):
	"""Converts value parameter into currency format using babel"""
	try:
		return format_currency(float(value), currency, locale=locale)
	except Exception as e:
		val_type = type(value).__name__
		return f"{value} is not valid format. must be str or int not {val_type}"
