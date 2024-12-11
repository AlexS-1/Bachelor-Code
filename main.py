import json
import shutil
from datetime import datetime, timedelta

from build.analysis import (analyse_diff_comments, average_comment_update_time,
                            blockify_code_data, classify_content,
                            set_metadata_for_block)
from build.comment_lister import get_comment_data
from build.extraction import (blockify_diff, classify_content,
                              extract_later_modified_comments, filter_comments_by_time, order_commits_data)
from build.pydriller import get_commits_data, get_parent_commit
from build.utils import clone_ropositoriy, save_to_json


def main():
    # Convert repo URL to path by cloning repo to temporary dictionary
    repo_url = "https://github.com/AlexS-1/Bachelor-Code"
    
    # Setting different timeperiod
    start_time = datetime.today().replace(tzinfo=None, microsecond=0) - timedelta(days=365)
    end_time = datetime.today().replace(microsecond=0)

    # Select from the supported file types for comment extraction
    file_types = [".c", ".c", ".cc", ".cp", ".cpp", ".cx", ".cxx", ".c+", ".c++", ".h", ".hh", ".hxx", ".h+", ".h++", ".hp", ".hpp", ".java", ".js", ".cs", ".py", ".php", ".rb"]

    # Get and store the code data usingy PyDriller
    repo_path = clone_ropositoriy(repo_url)
    commits_data = get_commits_data(repo_path, start_time, end_time, file_types)
    code_data = order_commits_data(commits_data)
    save_to_json(code_data, "Data/code_data.json")
    # Get and store the comment data using CommentLister
    add_comments_to_code(code_data, repo_path, start_time, end_time)
    save_to_json(code_data, "Data/code_data_with_comments.json")

    # Extract code changes and comment changes from code_data
    with open("Data/code_data_with_comments.json", "r") as json_file:
        code_data = json.load(json_file)
    analyse_diff_comments(code_data)
    blockify_code_data(code_data, old=False)
    blockify_code_data(code_data, old=True)
    set_metadata_for_block(code_data)
    blockify_diff(code_data, "added")
    blockify_diff(code_data, "deleted")
    save_to_json(code_data, "Data/blockified_code_data_with_comments.json")

    # TODO Find best point in time to remove tmp repo
    shutil.rmtree(repo_path)
    
    # Extract blocks with either outdated or updated comments
    comment_data = extract_later_modified_comments(code_data)
    for block in comment_data:
        for line, data in block["comment_lines"].items():
            data["type"] += classify_content(block["code_lines"][line])
            data["type"] = list(dict.fromkeys(data["type"]))
    save_to_json(comment_data, "Exports/comment_data.json")
    print("Average duration:", average_comment_update_time(comment_data))

def add_comments_to_code(code_data, repo_path, start_time, end_time):
    # Add comments to the code data using CommentLister
    for file, commits in code_data.items():
        previous_commit = get_parent_commit(commits[0]["commit"], file, repo_path)
        if previous_commit is None:
            raise Exception("Failed to get parent commit")
        for commit in commits:
            tag = "-target=" + commit["commit"]
            output = get_comment_data(repo_path, tag)
            output_old = get_comment_data(repo_path, "-target=" + previous_commit)
            # Parse output as JSON
            try:
                comment_data = json.loads(output)
                comment_data_old = json.loads(output_old)
            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse CommentLister output: {e}")
            # Filter comments by time
            commit_hash, filtered_comments = filter_comments_by_time(comment_data, start_time, end_time)
            commit_hash_old, filtered_comments_old = filter_comments_by_time(comment_data_old, start_time, end_time)
            if commit["commit"] == commit_hash and file in filtered_comments.keys():
                commit["comments"] = filtered_comments[file]
            else:
                print("No comments in this Commit", commit["commit"], "for investigate file", file)
                commit["comments"] = {}
            if previous_commit == commit_hash_old and file in filtered_comments_old.keys():
                commit["comments_old"] = filtered_comments_old[file]
            else:
                print("No comments in this commit's parents", commit["commit"], "for investigate file", file)
                commit["comments_old"] = {}
            previous_commit = commit["commit"]

if __name__ == "__main__":
    main()