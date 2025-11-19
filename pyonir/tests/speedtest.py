from memory_profiler import memory_usage
import json
import yaml
import toml
from pyonir.core.parser import DeserializeFile, serializer
import time

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

# JSON
json_str = json.dumps(data)

# YAML
yaml_str = yaml.dump(data)

# TOML
toml_str = toml.dumps(data)

dlines = data_str.strip().splitlines()
COUNT = 10000

# def parsely_loop():
#     for _ in range(COUNT):
#         process_lines(dlines, cursor=0, data_container={})

def toml_loop():
    for _ in range(COUNT):
        toml.load(yaml_str)

def yaml_loop():
    for _ in range(COUNT):
        yaml.safe_load(yaml_str)

def deser_loop():
    for _ in range(COUNT):
        DeserializeFile.load(data_str)

def json_loop():
    for _ in range(COUNT):
        json.loads(json_str)

def print_metrics(func):
    name = func.__name__
    start = time.time()
    mem_usage = memory_usage((func,))
    end = time.time()
    print(f"{name} execution time: {end - start:.4f} seconds")
    print(f"{name} peak memory usage: {max(mem_usage):.2f} MiB\n\n")

if __name__ == "__main__":
    print_metrics(deser_loop)
    print_metrics(json_loop)
    print_metrics(yaml_loop)
