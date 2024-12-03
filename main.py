# Import modules
from build.pydriller import get_commits_data
from build.comment_lister import run_comment_lister, filter_comments_by_time
from build.utils import save_to_json
from build.analysis import analyse_diff_comments, blockify_comments, blockify_comments2, extract_later_modified_comments, clean, average_comment_update_time, classify_comments
from build.xes_conversion import convert_json_to_xes

# Import packages
import os
import json
import subprocess
import shutil
from datetime import datetime, timezone

def main():
    # # Convert repo URL to path by cloning repo
    # repo_url = "https://github.com/AlexS-1/Bachelor-Code"

    # repo_name = os.path.basename(repo_url).replace(".git", "")
    # temp_dir = "/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/tmp"
    # clone_path = os.path.join(temp_dir, repo_name)

    # subprocess.run(['git', 'clone', repo_url, clone_path], check=True)

    # # # Paths
    # repo_path = clone_path
    # jar_path = "/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/CommentLister/target/CommentLister.jar"
    
    # # # Setting different timeperiod
    # start_time = datetime.today().replace(year = datetime.today().year - 1, tzinfo=None, microsecond=0)
    # end_time = datetime.today().replace(microsecond=0)

    # file_types = [".c", ".c", ".cc", ".cp", ".cpp", ".cx", ".cxx", ".c+", ".c++", ".h", ".hh", ".hxx", ".h+", ".h++", ".hp", ".hpp", ".java", ".js", ".cs", ".py", ".php", ".rb"]

    # commits_data = get_commits_data(repo_path, start_time, end_time, file_types)
    # save_to_json(commits_data, "Data/commits_data.json")
    
    # with open ("Data/commits_data.json", "r") as json_file:
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
    #             print("mismatch in commit and comment data or no comments in this commit for investigatet file")
    #             print("file could have been deleted")
    #             commit["comments"] = {}
    # # Save filtered comments on your system
    # save_to_json(commits_data, "Data/filtered_commits_data.json")
    # shutil.rmtree(clone_path)
    with open("Data/filtered_commits_data.json", "r") as json_file:
        data = json.load(json_file)
    # analyse_diff_comments(data)
    blockify_comments(data)
    save_to_json(data, "Exports/blockified_comments_data.json")
    with open("Exports/blockified_comments_data.json", "r") as json_file:
        data = json.load(json_file)
    blockify_comments2(data)
    save_to_json(data, "Exports/blockified_comments2_data.json")
    with open("Exports/blockified_comments2_data.json", "r") as json_file:
        data = json.load(json_file)
    d = extract_later_modified_comments(data)
    save_to_json(d, "Exports/analysis_results.json")
    with open("Exports/analysis_results.json", "r") as json_file:
        data = json.load(json_file)
    d = clean(data)
    save_to_json(d, "Exports/clean_analysis_results.json")
    with open("Exports/clean_analysis_results.json", "r") as json_file:
        data = json.load(json_file)
    d = classify_comments(data)
    save_to_json(d, "Exports/clean_analysis_results2.json")
    print("Average duration:", average_comment_update_time(d))
    convert_json_to_xes(d, 'Exports/output.xes')

if __name__ == "__main__":
    main()