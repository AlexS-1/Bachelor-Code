import datetime
import json
from multiprocessing import process
import os
import subprocess

from jsonschema import validate
from numpy import std

def diff_to_dict(diff):
    return {
        diff[0]: diff[1]
    }   

def clone_ropositoriy(repo_url, temp_dir="/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/tmp"):
    repo_name = os.path.basename(repo_url).replace(".git", "")
    clone_path = os.path.join(temp_dir, repo_name)
    subprocess.run(['git', 'clone', repo_url, clone_path], check=True)
    return clone_path

def array_to_string(array):
    return "[" + ", ".join(map(str, array)) + "]"

def generic_to_python_type(python_type):
    if (python_type == "string"):
        return str
    elif (python_type == "int"):
        return int
    elif (python_type == "time"):
        return datetime.datetime
    elif (python_type == "boolean"):
        return bool
    else:
        return None
    
def date_formatter(date):
    return date.strftime('%Y-%m-%dT%H:%M:%SZ')

def date_1970():
    return datetime.datetime(1970, 1, 1, 0, 0, 0, 0)

def validate_json(data_file_path, schema_file_path):
    with open(data_file_path, 'r') as data_file:
        data = json.load(data_file)
    with open(schema_file_path, 'r') as schema_file:
        schema = json.load(schema_file)
    return validate(data, schema)

def rename_field(document, old_field, new_field):
    if old_field in document:
        document[new_field] = document.pop(old_field)
    return document

def write_json(path, data):
    with open(path, "w") as data_file:
        json.dump(data, data_file, indent=4)

def delete_json(path):
    os.remove(path)

def write_to_file(path: str, data: str):
    with open(path, "w") as file:
        file.write(data)

def read_from_file(path: str):
    with open(path, "r") as file:
        return json.load(file)