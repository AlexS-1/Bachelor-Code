import json
from datetime import datetime

from httpx import get
from pydriller import Repository

from build.extraction import diff_to_dict
from build.utils import list_to_dict

def get_commits_data(repo_path, from_date, to_date, file_types): 
    files_data = {}
    for commit in Repository(   repo_path, 
                                since=from_date, 
                                to=to_date, 
                                histogram_diff=True,
                                only_modifications_with_file_types=file_types).traverse_commits():
        for file in commit.modified_files:
            if file.new_path not in files_data and len(file.filename.split(".")) == 2 and "." + file.filename.split(".")[1] in file_types and file.change_type.name == 'MODIFY':
                files_data[file.new_path] = []
            if len(file.filename.split(".")) == 2 and "." + file.filename.split(".")[1] in file_types and file.change_type.name == 'MODIFY':
                if file.source_code:
                    source = list_to_dict(file.source_code.split("\n"))
                else:
                    source = {}
                if file.source_code_before:
                    source_old = list_to_dict(file.source_code_before.split("\n"))
                else:
                    source_old = {}
                file_data = {
                    "commit": commit.hash,
                    "timestamp": commit.committer_date.isoformat(),
                    "author": commit.author.name,
                    "commit_msg": commit.msg,
                    "filename": file.new_path,
                    "diff": diff_to_dict(file.diff_parsed),
                    "source_code": source,
                    "source_code_old": source_old
                }
                if len(file.diff_parsed) != 0:
                    files_data[file.new_path].append(file_data)
    return files_data