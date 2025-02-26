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

def test_code_quality(file_path):
    try:
        result = subprocess.run(
            ['python', '-m', 'flake8', file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return result.stdout.decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        return e.stdout.decode('utf-8').strip() + "\n" + e.stderr.decode('utf-8').strip()

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