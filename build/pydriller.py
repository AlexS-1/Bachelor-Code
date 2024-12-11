import json
from datetime import date, datetime

from httpx import get
from dateutil.relativedelta import relativedelta
from pydriller import Repository

from build.comment_lister import get_comment_data
from build.extraction import diff_to_dict, filter_comments_by_time
from build.utils import list_to_dict

_repo_path = "/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/tmp/Bachelor-Code"

def get_commits_data(repo_path, from_date, to_date, file_types): 
    files_data = {}
    for commit in Repository(   repo_path, 
                                since=from_date, 
                                to=to_date, 
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
                    "filename": file.new_path,
                    "diff": diff_to_dict(file.diff_parsed),
                    "source_code": source,
                    "source_code_old": source_old
                }
                if len(file.diff_parsed) != 0:
                    files_data[file.new_path].append(file_data)
    return files_data

def get_parent_commit(commit_hash, file, repo_path=_repo_path):
    for commit in Repository(repo_path).traverse_commits():
        if commit.hash == commit_hash:
            parent = None
            while file not in get_files_in_commit(repo_path, commit.parents[0]):
                parent = get_parent_commit(commit.parents[0], file, repo_path)
                if parent is not None:
                    return parent
            return commit.parents[0]
    return None

def get_files_in_commit(repo_path, commit_hash):
    files = []
    for commit in Repository(repo_path, single=commit_hash).traverse_commits():
        for file in commit.modified_files:
            if file.new_path not in files:
                files.append(file.new_path)
    return files

def get_commit_data(commit_hash, filename, repo_path=_repo_path, old=False):
    for commit in Repository(repo_path, single=commit_hash).traverse_commits():
        for file in commit.modified_files:
            if file.new_path == filename:
                if old:
                    if file.change_type.name == 'ADD':
                        source_code_old = {}
                        comments = "comments_old"
                    else:
                        source_code_old = list_to_dict(file.source_code_before.split("\n"))
                        comments = "comments"
                    data = {
                    "commit": commit.hash,
                    "timestamp": commit.committer_date.isoformat(),
                    "author": commit.author.name,
                    "filename":file.new_path,
                    "source_code_old": source_code_old
                    }
                else:
                    data = {
                    "commit": commit.hash,
                    "timestamp": commit.committer_date.isoformat(),
                    "author": commit.author.name,
                    "filename":file.new_path,
                    "source_code": list_to_dict(file.source_code.split("\n"))
                    }
                output = get_comment_data(repo_path, "-target=" + commit.hash)
                try:
                    comment_data = json.loads(output)
                except json.JSONDecodeError as e:
                    raise Exception(f"Failed to parse CommentLister output: {e}")
                # Filter comments by time
                commit_hash, filtered_comments = filter_comments_by_time(comment_data, datetime.fromisoformat(commit.committer_date.isoformat()).replace(tzinfo=None), datetime.fromisoformat(commit.committer_date.isoformat()).replace(tzinfo=None))
                if data["commit"] == commit_hash and file.new_path in filtered_comments.keys():
                    data[comments] = filtered_comments[file.new_path]
                else:
                    print("No comments in this Commit", data["commit"], "for investigate file", file.new_path)
                    data[comments] = {}
                return {file.new_path: [data]}
    return None