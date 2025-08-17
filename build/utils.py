import datetime
import json
import os
import subprocess

from jsonschema import validate
from matplotlib import pyplot as plt
from numpy import std

def list_to_dict(diff: list):
    dict = {}
    for list in diff:
        dict[list[0]] = list[1]
    return dict

def clone_repository(repo_url, temp_dir="/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/tmp"):
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
    
def date_formatter(date: datetime.datetime):
    """
    Format a datetime object to a string.
    """
    return date.strftime('%Y-%m-%dT%H:%M:%SZ')

def date_1970():
    return date_formatter(datetime.datetime(1970, 1, 1))

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
    # If data is a string, parse it; if it's already a dict, just write it
    # if isinstance(data, str):
    #     try:
    #         data = json.loads(data)
    #     except Exception:
    #         import ast
    #         data = ast.literal_eval(data)
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
    
def _set_plot_style_and_plot():
    plt.rcParams['figure.facecolor'] = 'white'
    plt.rcParams['axes.facecolor'] = 'white'
    plt.rcParams['axes.edgecolor'] = 'black'
    plt.rcParams['axes.labelcolor'] = 'black'
    plt.rcParams['xtick.color'] = 'black'
    plt.rcParams['ytick.color'] = 'black'
    plt.rcParams['legend.edgecolor'] = 'black'
    plt.rcParams['legend.facecolor'] = 'black'
    plt.rcParams['axes.spines.top'] = False
    plt.rcParams['axes.spines.right'] = False
    plt.show()
