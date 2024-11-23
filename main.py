# Import modules
from build.pydriller import get_commits_data
from build.comment_lister import run_comment_lister, filter_comments_by_time
from build.utils import save_to_json
from build.analysis import analyse_diff_comments

# Import packages
import os
import json
import subprocess
import shutil
from datetime import datetime, timezone

def main():
    # Convert repo URL to path by cloning repo
    repo_url = "https://github.com/AlexS-1/Bachelor-Code.git"

    repo_name = os.path.basename(repo_url).replace(".git", "")
    temp_dir = "/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/tmp"
    clone_path = os.path.join(temp_dir, repo_name)

    subprocess.run(['git', 'clone', repo_url, clone_path], check=True)

    # # Paths
    repo_path = clone_path
    jar_path = "/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/CommentLister/target/CommentLister.jar"
    
    # # Setting different timeperiod
    start_time = datetime.today().replace(year = datetime.today().year - 1, tzinfo=None, microsecond=0)
    end_time = datetime.today().replace(microsecond=0)

    file_types = [".c", ".c", ".cc", ".cp", ".cpp", ".cx", ".cxx", ".c+", ".c++", ".h", ".hh", ".hxx", ".h+", ".h++", ".hp", ".hpp", ".java", ".js", ".cs", ".py", ".php", ".rb"]

    commits_data = get_commits_data(repo_path, start_time, end_time, file_types)
    save_to_json(commits_data, "Data/commits_data.json")
    
    with open ("Data/commits_data.json", "r") as json_file:
        commits_data = json.load(json_file)

    for file, commits in commits_data.items():
        for commit in commits:
            tag = "-target=" + commit["commit"]
            output = run_comment_lister(repo_path, jar_path, tag)
            # Parse output as JSON
            try:
                comment_data = json.loads(output)
            except json.JSONDecodeError as e:
                print(f"Failed to parse CommentLister output: {e}")
                return
            # Filter comments by time
            filtered_comments = filter_comments_by_time(comment_data, start_time, end_time)
            commit["comments"] = filtered_comments
    # Save filtered comments on your system
    save_to_json(commits_data, "Data/filtered_commits_data.json")
    shutil.rmtree(clone_path)
    with open("Data/filtered_commits_data.json", "r") as json_file:
        data = json.load(json_file)
    analyse_diff_comments(data)
    save_to_json(data, "Exports/filtered_comments_data.json")

if __name__ == "__main__":
    main()