import subprocess
from venv import create
from colorama import init
from numpy import insert
from pydriller import Repository
from requests import get

from build.database_handler import get_attribute_times, get_attribute_value_at_time, get_object, insert_commit, insert_event, insert_file, update_attribute
from build.code_quality_analyzer import get_cyclomatic_complexity, get_halstead_metrics, get_line_metrics, get_pylint_score, get_maintainability_index
from build.utils import date_1970, date_formatter

def create_commit(commit_sha, author, message, repository, branches, commit_timestamp, contribution_guideline_version, description=None, file_changes=None, parents=None):
    return {
        "commit_sha": commit_sha,
        "message": message,
        "description": description,
        "to": [repository + ":" + branch for branch in branches],
        "is-authored-by": author,
        "commit_timestamp": commit_timestamp,
        "aggregates": file_changes,
        "is-child-of": parents,

        "contribution_guideline_version": contribution_guideline_version
    }

def create_file(name, filename, file_change_timestamp, commit_sha, method_count, cyclomatic_complexity, theta_1, theta_2, N_1, N_2, loc, lloc, sloc, cloc, dloc, blank_lines, pylint_score):
    return {
        "file-changed_by": name,
        "filename": filename,
        "file_change_timestamp": file_change_timestamp,
        "part-of-commit": commit_sha,
        "method_count": method_count,
        "cc": cyclomatic_complexity,
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

def get_snapshot_code_quality(repo_path, from_date, file_types):
    repository_code_metrics = {}
    # FIXME Split in extract and insert methods in two modules
    for commit in Repository(repo_path, 
                             since=from_date, 
                             only_modifications_with_file_types=file_types).traverse_commits():
        
        # Get the initial commit to reset the repository to its original state
        initial_commit = subprocess.run(
            ['git', 'rev-parse', 'HEAD'], 
            cwd=repo_path, 
            stdout=subprocess.PIPE, 
            text=True).stdout.strip()
        
        # Move HEAD to the commit, from which we want to analze the code quality
        # and get the code metrics for all Python files
        print(f"Checking out commit {commit.hash} from original commit {initial_commit}")
        subprocess.run(['git', 'checkout', commit.hash], cwd=repo_path, check=True)
        result = subprocess.run(
            ["git", "ls-files", "*.py", "**/*.py"],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            text=True,
            check=True
        )
        py_files = result.stdout.strip().split('\n')
        # TODO Check if simply passing the path is faster
        for file in py_files:
            try:
                with open(f"{repo_path}/{file}", 'r') as f:
                    source_code = f.read()
            except Exception as e:
                print(f"Error reading file {file}: {e}")
                source_code = ""
            # TODO Implement own calculation of other metrics
            mi = get_maintainability_index(source_code)/100
            pl = get_pylint_score(source_code)/10
            repository_code_metrics[file] = [mi, pl]

        # Move HEAD back to the initial commit
        subprocess.run(['git', 'checkout', initial_commit], cwd=repo_path, check=True)
        print(f"Back to the real analysis")
        break
    return repository_code_metrics

def get_and_insert_local_data(repo_path, from_date, to_date, file_types, snapshot=False):
    # FIXME Split in extract and insert methods in two modules
    collection = repo_path.split("/")[-1]
    contribution_guideline_version = date_1970()
    repository_code_metrics = get_snapshot_code_quality(repo_path, from_date, file_types) if snapshot else {}
    for commit in Repository(repo_path, 
                             since=from_date, 
                             to=to_date,
                             only_modifications_with_file_types=file_types).traverse_commits():
        commit_timestamp = date_formatter(commit.committer_date)
        
        # TODO test if replaying with MongoDB is faster
        file_mis = []
        file_pylints = []

        # Update the repository code metrics for current commit and skip irrelevant commits
        for modified_file in commit.modified_files:
            if modified_file.change_type.name == "ADD" and modified_file.new_path and modified_file.new_path.endswith(".py"):
                repository_code_metrics[modified_file.new_path] = [0, 0]
            elif modified_file.change_type.name == "DELETE" and modified_file.old_path and modified_file.old_path.endswith(".py"):
                # TODO Decide how to handle deleted files
                repository_code_metrics.pop(modified_file.old_path, None)
                continue
            elif modified_file.change_type.name == "RENAME":
                update_attribute(modified_file.old_path, "filename", modified_file.new_path, commit_timestamp, collection)
                if modified_file.old_path and modified_file.old_path.endswith(".py"):
                    repository_code_metrics.pop(modified_file.old_path, None)
                if modified_file.new_path and modified_file.new_path.endswith(".py"):
                    repository_code_metrics[modified_file.new_path] = [0, 0]
                if modified_file.source_code and modified_file.source_code_before:
                    print(f"RENAME: File LOC changed from {len(modified_file.source_code_before.split("\n"))} to {len(modified_file.source_code.split("\n"))}")
            elif modified_file.change_type.name == "MODIFY" and modified_file.new_path and modified_file.new_path.endswith(".py"):
                repository_code_metrics[modified_file.new_path] = [0, 0]
            elif modified_file.change_type.name == "MODIFY" and modified_file.new_path and not modified_file.new_path.endswith(".py"):
                print("Potentially change in documentation")
                # TODO Decide how to do NLP here
                # TODO Check if this is the right way to handle contribution guidelines
                # import spacy
                # nlp = spacy.load("en_core_web_sm")
                # doc = nlp(str(modified_file.source_code))
                if "pull" in modified_file.new_path or "contribut" in modified_file.new_path or "document" in modified_file.new_path:
                    print(f"Contribution guideline found in {modified_file.new_path}")
                    keyword_list = ["reviewer",
                            "approval",
                            "pull request",
                            "continuous integration",
                            "CI/CD",
                            "test",
                            "workflow",
                            "code owner",
                            "branch protection",
                            "requirement"]
                    # if any(keyword in modified_file.diff_parsed["diff"] for keyword in keyword_list):
                    #     print(f"Contribution guideline found in {modified_file.new_path} with keywords {keyword_list}")
                    contribution_guideline_version = commit_timestamp
            else:
                continue
            
            # Skip irrevant files in relevant commits
            if modified_file.new_path is None or modified_file.new_path.endswith(".py") == False:
                # TODO Check if there are cases where code_metrics is stil set to [0, 0]
                continue
            
            # Prevent wrong code quality measurements for empty files
            # TODO Optimize by not analyzing files that are renamed
            if modified_file.source_code is None:
                source = ""
                print(f"File {modified_file.new_path} has no source code")
            else:
                source = modified_file.source_code

            # Gather code quality data per file
            mi = get_maintainability_index(source)/100
            pl = get_pylint_score(source)/10
            lm = get_line_metrics(source)
            hm = get_halstead_metrics(source)
            cc = get_cyclomatic_complexity(source)

            # TODO Implement as reading from MongoDB
            repository_code_metrics[modified_file.new_path] = [mi, pl]

            #####################################################
            # TODO Split here for insertion and MongoDB control #
            #####################################################

            file = create_file(
                commit.committer.name, 
                modified_file.new_path,
                commit_timestamp, 
                commit.hash,
                -1, # TODO Check how method count works len(hm.methods), e.g. len(cc_visit) by modifying get_cyclomatic_complexity
                cc,
                hm.total.h1,
                hm.total.h2,
                hm.total.N1,
                hm.total.N2,
                lm.loc,
                lm.lloc,
                lm.sloc,
                lm.comments,
                lm.multi,
                lm.blank,
                pl)
            insert_file(file, collection)
        filenames = [f.new_path for f in commit.modified_files if f.new_path]
        commit_object = create_commit(
            commit.hash, 
            commit.author.name, 
            commit.msg.split("\n\n", 1)[0], 
            commit.project_name, 
            commit.branches, 
            commit_timestamp, 
            contribution_guideline_version,
            "" if len(commit.msg.split("\n\n")) < 2 else commit.msg.split("\n\n", 1)[1], 
            filenames, 
            commit.parents)
        for _,v in repository_code_metrics.items():
            file_mis.append(v[0])
            file_pylints.append(v[1])
        commit_mi = sum(file_mis)/len(file_mis) if file_mis else 0
        commit_pylint = sum(file_pylints)/len(file_pylints) if file_pylints else 0
        commit_object["commit_mi"] = commit_mi
        commit_object["commit_pylint"] = commit_pylint
        insert_commit(commit_object, collection)
    return