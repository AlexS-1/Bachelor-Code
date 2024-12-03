from pydriller import Repository
import json
import pm4py
from datetime import datetime
from dateutil.relativedelta import relativedelta
from build.utils import list_to_dict

def get_commits_data(repo_path, from_date, to_date, file_types):
    files_data = {}
    for commit in Repository(   repo_path, 
                                since=from_date, 
                                to=to_date, 
                                only_modifications_with_file_types=file_types).traverse_commits():
            for file in commit.modified_files:
                if file.new_path not in files_data and len(file.filename.split(".")) == 2 and "." + file.filename.split(".")[1] in file_types:
                    files_data[file.new_path] = []
                if len(file.filename.split(".")) == 2 and "." + file.filename.split(".")[1] in file_types:
                    if file.source_code:
                        source = list_to_dict(file.source_code.split("\n"))
                    else:
                        source = {}
                    file_data = {
                        "commit": commit.hash,
                        "timestamp": commit.committer_date.isoformat(),
                        "author": commit.author.name,
                        "diff": diff_to_dict(file.diff_parsed),
                        "source_code": source
                    }
                    if len(file.diff_parsed) != 0:
                        files_data[file.new_path].append(file_data)
    return files_data

def diff_to_dict(diff):
    dict_added = {}
    for line in diff["added"]:
        dict_added[line[0]] = line[1]
    diff["added"] = dict_added
    dict_deleted = {}
    for line in diff["deleted"]:
        dict_deleted[line[0]] = line[1]
    diff["deleted"] = dict_deleted
    return diff

def extract_keywords(commit_message, modified_file):
    # Determine basic keywords based on the commit message
    keywords = []
    if "performance" in commit_message.lower():
        keywords.append("performance")
    if "security" in commit_message.lower():
        keywords.append("security")
    if modified_file.added_lines > modified_file.deleted_lines:
        keywords.append("expansion")
    else:
        keywords.append("optimization")
    return keywords

def extract_activity(commit_message):
    # Use commit message keywords to determine activity type
    activity = ""
    if "bug" in commit.msg.lower() or "fix" in commit.msg.lower():
        activity = "Bug Fix"
    elif "feature" in commit.msg.lower() or "add" in commit.msg.lower():
        activity = "Feature Development"
    elif "refactor" in commit.msg.lower():
        activity = "Refactoring"
    else:
        activity = "Other"
    return activity