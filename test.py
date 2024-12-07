from pydriller import Repository
import json
from build.pydriller import get_commits_data
from build.comment_lister import run_comment_lister, filter_comments_by_time
from build.utils import save_to_json
from build.analysis import analyse_diff_comments, blockify_diff, extract_later_modified_comments, clean, average_comment_update_time, classify_comments, classify_content
from build.xes_conversion import convert_json_to_xes
from datetime import datetime, timezone
import os
import subprocess
import shutil

def get_source_code_from_tag(repo_path, tag_name, dt1, dt2):
    """
    DOCSTRIING: Extracts the source code of a specific commit tagged in the repository.

    :param repo_path: Path to the local Git repository.
    :param tag_name: The name of the tag to fetch.
    :return: A dictionary containing file paths and their contents at the given commit.
    END DOCSTRING
    """
    source_code = []

    for commit in Repository(repo_path, since=dt1, to=dt2).traverse_commits():
        print(f"Processing commit: {commit.hash} tagged as {tag_name}")
        for modified_file in commit.modified_files:
            # NORMAL Save the file path and its source code
            if modified_file.source_code:
                # BLOCK: Multiple lines
                # of comment
                if modified_file.filename.find(".py") != -1 and modified_file.filename.find(".pyc") == -1:
                    comit = {
                        commit.hash + "---" + modified_file.filename: list_to_dict(modified_file.source_code.split("\n")) #INLINE: identify each block of data
                    }
                    source_code.append(comit)
                    # print(commit) #COMMENTED-OUT
    return source_code  

# Example usage
repo_url = "https://github.com/AlexS-1/Bachelor-Code"
tag_name = "a1ad5c2cb35d621f2b187166af65a2b2ee3ea45e"
start_time = datetime(2024,12,3)
end_time = datetime.today()
repo_name = os.path.basename(repo_url).replace(".git", "")
temp_dir = "/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/tmp"
clone_path = os.path.join(temp_dir, repo_name)

subprocess.run(['git', 'clone', repo_url, clone_path], check=True)

# # Paths
repo_path = clone_path
jar_path = "/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/CommentLister/target/CommentLister.jar"
file_types = [".c", ".c", ".cc", ".cp", ".cpp", ".cx", ".cxx", ".c+", ".c++", ".h", ".hh", ".hxx", ".h+", ".h++", ".hp", ".hpp", ".java", ".js", ".cs", ".py", ".php", ".rb"]

commits_data = get_commits_data(repo_path, start_time, datetime.today(), file_types)
save_to_json(commits_data, "Toy-Example/commits_data.json")
with open ("Toy-Example/commits_data.json", "r") as json_file: 
        commits_data = json.load(json_file)

for file, commits in commits_data.items():
    for commit in commits:
        tag = "-target=" + commit["commit"]
        output = run_comment_lister(repo_path, jar_path, tag)
        # Parse output as JSON
        try:
            comment_data = json.loads(output)
            if file.find("pydriller") != -1:
                save_to_json(commit["source_code"], f"Toy-Example/{commit["commit"]}_code.json")
                save_to_json(comment_data, f"Toy-Example/{commit["commit"]}_comments.json")
                if commit["commit"] == "e20d03792161ba1b90725e6912b40275f06bf2da": break
        except json.JSONDecodeError as e:
            print(f"Failed to parse CommentLister output: {e}")
            break
        # Filter comments by time
        commit_hash, filtered_comments = filter_comments_by_time(comment_data, start_time, end_time)
        if commit["commit"] == commit_hash and file in filtered_comments.keys():
            commit["comments"] = filtered_comments[file]
        else:
            print("mismatch in commit and comment data or no comments in this commit for investigatet file")
            print("file could have been deleted")
            commit["comments"] = {}
shutil.rmtree(clone_path)
# # Save filtered comments on your system
# save_to_json(commits_data, "Toy-Example/filtered_commits_data.json")
# shutil.rmtree(clone_path)
# with open("Toy-Example/filtered_commits_data.json", "r") as json_file:
#     data = json.load(json_file)
# # analyse_diff_comments(data)
# blockify_comments(data)
# save_to_json(data, "Toy-Example/blockified_comments_data.json")
# with open("Toy-Example/blockified_comments_data.json", "r") as json_file:
#     data = json.load(json_file)
# add_content_to_blocks(data)
# save_to_json(data, "Toy-Example/blockified_comments2_data.json")
# with open("Toy-Example/blockified_comments2_data.json", "r") as json_file:
#     data = json.load(json_file)
# d = extract_later_modified_comments(data)
# save_to_json(d, "Toy-Example/analysis_results.json")
# with open("Toy-Example/analysis_results.json", "r") as json_file:
#     data = json.load(json_file)
# d = clean(data)
# save_to_json(d, "Toy-Example/clean_analysis_results.json")
# with open("Toy-Example/clean_analysis_results.json", "r") as json_file:
#     data = json.load(json_file)
# d = classify_content(data)
# save_to_json(d, "Toy-Example/clean_analysis_results2.json")
# print("Average duration:", average_comment_update_time(d))
# convert_json_to_xes(d, 'Toy-Example/output.xes')