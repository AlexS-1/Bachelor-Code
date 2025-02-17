from pydriller import Repository

from build.database_handler import insert_commit, insert_event, insert_file_change, insert_repo
from build.api_handler import get_name_by_username
from build.utils import array_to_string, date_formatter, diff_to_dict

_repo_path = "/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/tmp/Toy-Example"

def create_commit(commit_sha, author, message, repository, branches, commit_timestamp, description=None, file_changes=None, parents=None):
    return {
        "commit_sha": commit_sha,
        "message": message,
        "description": description,
        "branch": list(branches),
        "commit-authored-by": author,
        "commit-to-repository": repository,
        "commit_timestamp": commit_timestamp,
        "commit-includes-file_change": file_changes,
        "commit-has-parent": parents
    }

def create_file_change(name, filename, file_change_timestamp, commit_sha, additions, deletions, language_popularity=None, typed=False):
    return {
        "file-changed_by": name,
        "filename": filename,
        # "language_popularity": language_popularity,
        # "typed": typed,
        "file_change_timestamp": file_change_timestamp,
        "part-of-commit": commit_sha,
        "additions": additions,
        "deletions": deletions
    }

def get_and_insert_commits_data(repo_path, from_date, to_date, file_types): 
    commits_data = {}
    for commit in Repository(   repo_path, 
                                # since=from_date, 
                                to=to_date).traverse_commits():
        file_changes = []
        commit_timestamp = date_formatter(commit.committer_date)
        for file in commit.modified_files:
            file_changes.append("/".join([
                commit.committer.name, file.new_path if file.new_path != None else file.old_path, 
                commit_timestamp]))
            file_change = create_file_change(
                commit.committer.name, 
                file.new_path if file.new_path != None else file.old_path, 
                commit_timestamp, 
                commit.hash,
                array_to_string([str(diff_to_dict(line)) for line in file.diff_parsed["added"]]), 
                array_to_string([str(diff_to_dict(line)) for line in file.diff_parsed["deleted"]]))
            insert_file_change(file_change)
        commit_object = create_commit(
            commit.hash, 
            commit.author.name, 
            commit.msg.split("\n\n", 1)[0], 
            commit.project_name, 
            commit.branches, 
            commit_timestamp, 
            "" if len(commit.msg.split("\n\n")) < 2 else commit.msg.split("\n\n", 1)[1], 
            file_changes, 
            commit.parents)
        insert_commit(commit_object)
        insert_event("create-" + commit_object["commit_sha"], 
                     "commit", commit_object["commit_timestamp"], 
                     None, 
                     [{"objectId": commit_object["commit_sha"], "qualifier": "create"}, 
                      {"objectId": commit_object["commit-authored-by"], "qualifier": "authored-by"}, 
                      {"objectId": commit_object["commit-to-repository"], "qualifier": "commit-to-repo"}, 
                      {"objectId": commit_object["branch"], "qualifier": "commit-to-branch"}, 
                      {"objectId": commit_object["commit-includes-file_change"], "qualifier": "includes"}, 
                      {"objectId": commit_object["commit-has-parent"], "qualifier": "has-parents"}])
    return commits_data