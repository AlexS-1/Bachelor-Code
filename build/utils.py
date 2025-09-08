"""Utility helper functions used across the code base.

Public helpers expose generic transformations (e.g. list_to_dict, clone_repository)
while private helpers (prefixed with an underscore) are meant for local use only.
"""

import datetime
import json
import os
import subprocess

from jsonschema import validate
from matplotlib import pyplot as plt

def list_to_dict(diff: list):
    """Convert a list of two-item iterables into a dictionary.

    Args:
        diff (list): A list where each element is an indexable with at least two items.
    Returns:
        dict: Mapping of first -> second element of every list item.
    """
    return {item[0]: item[1] for item in diff}

def clone_repository(
    repo_url: str,
    temp_dir: str = "/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/tmp"):
    """Clone a git repository locally.

    Args:
        repo_url (str): Remote repository URL.
        temp_dir (str): Base directory to clone into.
    Returns:
        str: Absolute path to the cloned repository.
    """
    repo_name = os.path.basename(repo_url).replace(".git", "")
    clone_path = os.path.join(temp_dir, repo_name)
    subprocess.run(["git", "clone", repo_url, clone_path], check=True)
    return clone_path

def array_to_string(array) -> str:
    """Return a human readable string representation of a list."""
    return "[" + ", ".join(map(str, array)) + "]"

def string_to_array(s: str) -> list[str]:
    """Parse a bracket / comma separated string to a normalized list of tokens."""
    s = s.strip("[]")
    if not s:
        return []
    return [item.strip().lower() for item in s.split(",")]

def generic_to_python_type(python_type):
    """Map a generic schema type string to a Python type object."""
    if python_type == "string":
        return str
    if python_type == "int":
        return int
    if python_type == "time":
        return datetime.datetime
    if python_type == "boolean":
        return bool
    return None

def date_formatter(date: datetime.datetime) -> str:
    """Format a datetime object to an ISO-like UTC string (no offset)."""
    return date.strftime("%Y-%m-%dT%H:%M:%SZ")

def date_1970() -> str:
    """Return the canonical epoch start timestamp string."""
    return date_formatter(datetime.datetime(1970, 1, 1))

def validate_json(data_file_path: str, schema_file_path: str):
    """Validate a JSON document against a JSONSchema file.

    Returns whatever jsonschema.validate returns (None on success, raises on failure).
    """
    with open(data_file_path, "r", encoding="utf-8") as data_file:
        data = json.load(data_file)
    with open(schema_file_path, "r", encoding="utf-8") as schema_file:
        schema = json.load(schema_file)
    return validate(data, schema)

def rename_field(document: dict, old_field: str, new_field: str):
    """Rename a key in a dict if present and return the mutated dict."""
    if old_field in document:
        document[new_field] = document.pop(old_field)
    return document

def write_json(path: str, data):
    """Write JSON serialisable data to a file path with indentation."""
    with open(path, "w", encoding="utf-8") as data_file:
        json.dump(data, data_file, indent=4)

def delete_json(path: str):
    """Delete a JSON file (wrapper for os.remove)."""
    os.remove(path)

def write_to_file(path: str, data: str):
    """Write raw string data to a file."""
    with open(path, "w", encoding="utf-8") as file:
        file.write(data)

def read_from_file(path: str):
    """Read and JSON-decode file contents."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)

def _set_plot_style_and_plot():
    """Apply a consistent light style to matplotlib then display the figure."""
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"
    plt.rcParams["axes.edgecolor"] = "black"
    plt.rcParams["axes.labelcolor"] = "black"
    plt.rcParams["xtick.color"] = "black"
    plt.rcParams["ytick.color"] = "black"
    plt.rcParams["legend.edgecolor"] = "black"
    plt.rcParams["legend.facecolor"] = "#A2A2A2"
    plt.rcParams["axes.titlecolor"] = "black"
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["text.color"] = "black"
    plt.rcParams["axes.spines.right"] = False
    plt.show()
