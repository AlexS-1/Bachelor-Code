from pydriller import Repository
from pydriller.metrics.process.code_churn import CodeChurn
from pydriller.metrics.process.commits_count import CommitsCount
import os

from build.database_handler import insert_commit, insert_file
from build.utils import array_to_string, date_formatter, diff_to_dict
from build.analysis import analyse_source_code

def create_commit(commit_sha, author, message, repository, branches, commit_timestamp, description=None, file_changes=None, parents=None):
    return {
        "commit_sha": commit_sha,
        "message": message,
        "description": description,
        "to": [repository + ":" + branch for branch in branches],
        "is-authored-by": author,
        "commit_timestamp": commit_timestamp,
        "aggregates": file_changes,
        "is-child-of": parents
    }

# TODO Add code quality metrics
def create_file(name, filename, file_change_timestamp, commit_sha, method_count, theta_1, theta_2, N_1, N_2, loc, lloc, sloc, cloc, dloc,blank_lines, pylint_score, language_popularity=None, typed=False):
    return {
        "file-changed_by": name,
        "filename": filename,
        "file_change_timestamp": file_change_timestamp,
        "part-of-commit": commit_sha,
        "method_count": method_count,
        "theta_1": theta_1,
        "theta_2": theta_2,
        "N_1": N_1,
        "N_2": N_2,
        "loc": loc,
        "lloc": lloc,
        "sloc": sloc,
        "cloc": cloc,
        "dloc": dloc,
        "blank_lines": blank_lines,
        "pylint_score": pylint_score
    }

def get_and_insert_commits_data(repo_path, from_date, to_date, file_types): 
    commits_data = {}
    for commit in Repository(   repo_path, 
                                since=from_date, 
                                to=to_date).traverse_commits():
        file_changes = []
        commit_timestamp = date_formatter(commit.committer_date)
        for file in commit.modified_files:
            # Generate ID for the file object, to be referenced from the commit object
            file_changes.append(file.new_path if file.new_path != None else file.old_path)
            if file.new_path != None and file.new_path.endswith(".py"):
            # Gather code quality data
                _, method_count = analyse_source_code(file.source_code, "cc")
                theta_1, theta_2, N_1, N_2 = [int(i.split(": ")[-1]) for i in analyse_source_code(file.source_code, "helstead")[1:5]]
                loc, lloc, sloc, _, cloc, dloc, blank_lines = [int(i.split(" ")[-1]) for i in analyse_source_code(file.source_code, "loc")[1:8]]
                pylint_score = float(analyse_source_code(file.source_code, "pylint"))
            else:
                method_count, theta_1, theta_2, N_1, N_2 = -1, -1, -1, -1, -1
                loc, lloc, sloc, cloc, dloc, blank_lines = -1, -1, -1, -1, -1, -1
                pylint_score = -1
            # TODO Add code quality metrics
            file = create_file(
                commit.committer.name, 
                file.new_path if file.new_path != None else file.old_path, 
                commit_timestamp, 
                commit.hash,
                array_to_string([str(diff_to_dict(line)) for line in file.diff_parsed["added"]]), 
                array_to_string([str(diff_to_dict(line)) for line in file.diff_parsed["deleted"]]),
                method_count,
                theta_1,
                theta_2,
                N_1,
                N_2,
                loc,
                lloc,
                sloc,
                cloc,
                dloc,
                blank_lines,
                pylint_score)
            insert_file(file)
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
    return commits_data

def get_and_store_commits_data(repo_path, from_date, to_date, file_types):
    commits_data = {}
    commits = Repository(repo_path,
                         since=from_date,
                         to=to_date,
                         only_modifications_with_file_types=".py").traverse_commits()
    for commit in commits:
        for file in commit.modified_files:
            if file.new_path != None and file.new_path.endswith(".py"):
                commit_data = {
                    "filename_old": file.old_path,
                    "source_old": file.source_code_before,
                    "filename_new": file.new_path,
                    "source_new": file.source_code,
                    "additions": file.added_lines,
                    "deletions": file.deleted_lines,
                    "cyclomatic_complexity_new": file.complexity
                    }
                commits_data[commit.hash] = commit_data
    return commits_data

def get_pydriller_metric(repo_path, from_commit, to_commit, path, metric):
    if metric == "code_churn":
        metric = CodeChurn(path_to_repo=repo_path,
                           from_commit=from_commit,
                           to_commit=to_commit)
    if metric == "commit_count":
        metric = CommitsCount(path_to_repo=repo_path,
                              from_commit=from_commit,
                              to_commit=to_commit)
    return  metric.count()[path]

def get_initial_commit_hash(repo_path):
    for commit in Repository(repo_path).traverse_commits():
        return commit.hash