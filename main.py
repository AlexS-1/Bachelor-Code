# Import modules
from build.pydriller import get_commits_data, order_commits_data
from build.comment_lister import run_comment_lister, filter_comments_by_time
from build.utils import save_to_json
from build.analysis import analyse_diff_comments, blockify_code_data, blockify_diff, extract_later_modified_comments, average_comment_update_time, classify_comments, classify_content
from build.xes_conversion import convert_json_to_xes

# Import packages
import os
import json
import subprocess
import shutil
from datetime import datetime, timezone, timedelta

def main():
    # # Convert repo URL to path by cloning repo
    # repo_url = "https://github.com/AlexS-1/Bachelor-Code"

    # repo_name = os.path.basename(repo_url).replace(".git", "")
    # temp_dir = "/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/tmp"
    # clone_path = os.path.join(temp_dir, repo_name)

    # subprocess.run(['git', 'clone', repo_url, clone_path], check=True)

    # # Paths
    # repo_path = clone_path
    # jar_path = "/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/CommentLister/target/CommentLister.jar"
    
    # # Setting different timeperiod
    # start_time = datetime.today().replace(tzinfo=None, microsecond=0) - timedelta(14)
    # end_time = datetime.today().replace(microsecond=0)

    # file_types = [".c", ".c", ".cc", ".cp", ".cpp", ".cx", ".cxx", ".c+", ".c++", ".h", ".hh", ".hxx", ".h+", ".h++", ".hp", ".hpp", ".java", ".js", ".cs", ".py", ".php", ".rb"]

    # commits_data = get_commits_data(repo_path, start_time, end_time, file_types)
    # ordered_commits = order_commits_data(commits_data)
    # save_to_json(ordered_commits, "Data/code_data.json")
    
    # with open ("Data/code_data.json", "r") as json_file:
    #     commits_data = json.load(json_file)

    # for file, commits in commits_data.items():
    #     for commit in commits:
    #         tag = "-target=" + commit["commit"]
    #         output = run_comment_lister(repo_path, jar_path, tag)
    #         # Parse output as JSON
    #         try:
    #             comment_data = json.loads(output)
    #         except json.JSONDecodeError as e:
    #             print(f"Failed to parse CommentLister output: {e}")
    #             return
    #         # Filter comments by time
    #         commit_hash, filtered_comments = filter_comments_by_time(comment_data, start_time, end_time)
    #         if commit["commit"] == commit_hash and file in filtered_comments.keys():
    #             commit["comments"] = filtered_comments[file]
    #         else:
    #             print("mismatch in commit and comment data")
    #             print("No comments in this Commit", commit["commit"], "for investigate file", file)
    #             commit["comments"] = {}
    # # Save filtered comments on your system
    # save_to_json(commits_data, "Data/code_data_with_comments.json")
    # shutil.rmtree(clone_path)

    with open("Data/code_data_with_comments.json", "r") as json_file:
        code_data = json.load(json_file)
    blockify_code_data(code_data)
    blockify_diff(code_data, "added")
    blockify_diff(code_data, "deleted")
    analyse_diff_comments(code_data)
    save_to_json(code_data, "Data/blockified_code_data_with_comments.json")
    with open("Data/blockified_code_data_with_comments.json", "r") as json_file:
        code_data = json.load(json_file)
    save_to_json(code_data, "Data/blockified_code_data_with_comments.json")
    comment_data = extract_later_modified_comments(code_data)
    for item in comment_data:
        item["type"] += classify_content(item["content"])
        item["type"] = list(dict.fromkeys(item["type"]))
    save_to_json(comment_data, "Exports/comment_data.json")
    print("Average duration:", average_comment_update_time(comment_data))

if __name__ == "__main__":
    main()