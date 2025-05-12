from pydriller import Repository

from build.database_handler import insert_commit, insert_file
from build.code_quality_analyzer import get_pylint_score, get_maintainability_index
from build.utils import date_formatter

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

def create_file(name, filename, file_change_timestamp, commit_sha, method_count, theta_1, theta_2, N_1, N_2, loc, lloc, sloc, cloc, dloc,blank_lines, pylint_score):
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

def get_and_insert_local_data(repo_path, from_date, to_date, file_types): 
    # FIXME Split in extract and insert methods in two modules
    count = 0
    for commit in Repository(repo_path, 
                             since=from_date, 
                             to=to_date,
                             only_modifications_with_file_types=file_types).traverse_commits():
        files_modified_in_commit = []
        commit_timestamp = date_formatter(commit.committer_date)
        code_quality_graph = []
        # TODO For testing limit analysis to 100 commits
        if count == 100:
            break

        # Gather code quality data per file
        for file in commit.modified_files:
            if file.new_path != None and [file.new_path.endswith(extension) == True for extension in file_types]:
                files_modified_in_commit.append(file.new_path)
                try:
                    # TODO Implement own calculation of other metrics
                    method_count, theta_1, theta_2, N_1, N_2 = 0, 0, 0, 0, 0
                    loc, lloc, sloc, cloc, dloc = 0, 0, 0, 0, 0
                    pylint_score = get_pylint_score(file.source_code, file.new_path)
                    blank_lines = get_maintainability_index(file.source_code, file.new_path)
                except:
                    pylint_score = 0
                    blank_lines = 0
            else:
                # TODO Handle case when file is not of specified file type i.e., when guideleines could have changed
                method_count, theta_1, theta_2, N_1, N_2 = -1, -1, -1, -1, -1
                loc, lloc, sloc, cloc, dloc, blank_lines = -1, -1, -1, -1, -1, -1
            file = create_file(
                commit.committer.name, 
                file.new_path if file.new_path != None else file.old_path,
                commit_timestamp, 
                commit.hash,
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
            files_modified_in_commit, 
            commit.parents)
        insert_commit(commit_object)
        count += 1
