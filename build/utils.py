import datetime
import os
import subprocess

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