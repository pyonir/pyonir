import timeit
import json
import yaml
import toml
from pyonir.models.parser import DeserializeFile, serializer

data = {
    "name": "MyApp",
    "version": "1.0.0",
    "config": {
        "host": "localhost",
        "port": 8000,
        "debug": True,
        "database": {
            "url": "postgresql://localhost/db",
            "pool_size": 10
        }
    }
}

# PARSELY
data_str = DeserializeFile.loads(data)
parsely_time = timeit.timeit(lambda: DeserializeFile.load(data_str), number=10000)

# JSON
json_str = json.dumps(data)
json_time = timeit.timeit(lambda: json.loads(json_str), number=10000)

# # YAML
# yaml_str = yaml.dump(data)
# yaml_time = timeit.timeit(lambda: yaml.safe_load(yaml_str), number=10000)
#
# # TOML
# toml_str = toml.dumps(data)
# toml_time = timeit.timeit(lambda: toml.loads(toml_str), number=10000)

print(f"JSON:  {json_time:.4f}s")  # ~0.05s
print(f"PARSELY:  {parsely_time:.4f}s")  # ~0.30s
# print(f"TOML:  {toml_time:.4f}s")  # ~0.15s
# print(f"YAML:  {yaml_time:.4f}s")  # ~0.50s
