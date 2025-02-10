from heapq import merge
import json
from datetime import datetime
from numpy import add
from pydriller import Repository

from build.database_handler import insert_commit, insert_file_change, insert_repo
from build.api_handler import get_name_by_username
from build.utils import array_to_string, diff_to_dict

_repo_path = "/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/tmp/Toy-Example"

def create_commit(commit_sha, author, title, repository, branch, commit_timestamp, message=None, file_changes=None, parents=None):
    return {
        "commit_sha": commit_sha,
        "author": author,
        "title": title,
        "repository": repository,
        "branch": branch,
        "commit_timestamp": commit_timestamp,
        "message": message,
        "file_changes": file_changes,
        "parents": parents
    }

def create_file_change(name, filename, file_change_timestamp, additions, deletions, language_popularity=None, typed=False):
    return {
        "changed_by": name,
        "filename": filename,
        "language_popularity": language_popularity,
        "typed": typed,
        "file_change_timestamp": file_change_timestamp,
        "additions": additions,
        "deletions": deletions
    }

def get_and_insert_commits_data(repo_path, from_date, to_date, file_types): 
    commits_data = {}
    for commit in Repository(   repo_path, 
                                since=from_date, 
                                to=to_date).traverse_commits():
        file_changes = []
        for file in commit.modified_files:
            file_changes.append("/".join([commit.committer.name, file.new_path if file.new_path != None else file.old_path, str(commit.committer_date)]))
            insert_file_change(create_file_change(commit.committer.name, file.new_path if file.new_path != None else file.old_path, commit.committer_date, array_to_string([str(diff_to_dict(line)) for line in file.diff_parsed["added"]]), array_to_string([str(diff_to_dict(line)) for line in file.diff_parsed["deleted"]])))
        commit = create_commit(commit.hash, commit.author.name, commit.msg.split("\n\n", 1)[0], commit.project_name, commit.committer_date.timestamp(), commit.merge, "" if len(commit.msg.split("\n\n")) < 2 else commit.msg.split("\n\n", 1)[1], file_changes, array_to_string(commit.parents))
        insert_commit(commit)
    return commits_data