import json
import shutil
from datetime import datetime, timedelta

from build.analysis import analyse_blocks, average_comment_update_time, process_csv_and_create_event_log
from build.comment_lister import get_comment_data
from build.extraction import split_comments_to_lines, order_commits_data, make_table, blockify_code_data_v1_to_3, blockify_code_data
from build.pydriller import get_commits_data
from build.utils import clone_ropositoriy, save_to_json, save_to_csv


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
    add_comments_to_code(code_data, repo_path)
    save_to_json(code_data, "Data/code_data_with_comments.json")
    shutil.rmtree(repo_path)

    with open("Data/code_data_with_comments.json") as f:
        code_data = json.load(f)

    # Extract code changes and comment changes from code_data
    # blockify_code_data_v1_to_3(code_data, "v3")
    blockify_code_data(code_data, "v4")
    analyse_blocks(code_data)
    save_to_json(code_data, "Data/blockified_code_data_with_comments.json")
    save_to_csv(make_table(code_data, "v4"), "Exports/commit_data.csv")

    # Usage
    process_csv_and_create_event_log("Exports/commit_data.csv", "Exports/event_log.csv")

def add_comments_to_code(code_data, repo_path):
    # Add comments to the code data using CommentLister
    for file, commits in code_data.items():
        for commit in commits:
            tag = "-target=" + commit["commit"]
            output = get_comment_data(repo_path, tag)
            # Parse output as JSON
            try:
                comment_data = json.loads(output)
            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse CommentLister output: {e}")
            # Filter comments by time
            commit_hash, filtered_comments = split_comments_to_lines(commit["source_code"], comment_data)
            if commit["commit"] == commit_hash and file in filtered_comments.keys():
                commit["comments"] = filtered_comments[file]
            else:
                print("No comments in this Commit", commit["commit"], "for investigate file", file)
                commit["comments"] = {}

if __name__ == "__main__":
    main()