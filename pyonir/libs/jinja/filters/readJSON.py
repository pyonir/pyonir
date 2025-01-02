import os, json

def readJSON(abs_path_to_json_file):
	jsondata = {}
	if not abs_path_to_json_file.endswith(".json"): return f"{abs_path_to_json_file} is not a valid json file"
	try:
		with open(abs_path_to_json_file) as json_file:
			jsondata = json.load(json_file)
	except Exception as e:
		jsondata = f"{type(e).__name__} error occurred when attempting to convert {abs_path_to_json_file}: {e}"
	return jsondata
