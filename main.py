# Import modules
from build.pydriller import get_commits_data
from build.comment_lister import run_comment_lister, filter_comments_by_time

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

    # Paths
    repo_path = clone_path
    jar_path = "/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/CommentLister/target/CommentLister.jar"
    
    # Setting different timeperiod
    start_time = datetime.today().replace(year = datetime.today().year - 1, tzinfo=None, microsecond=0)
    end_time = datetime.today().replace(microsecond=0)

    commits_data = get_commits_data(repo_path, start_time, end_time)

    for file, commits in commits_data.items():
        for commit in commits:
            tag = "-target=" + commit["commit"]
            output = run_comment_lister(repo_path, jar_path, tag)
            if output is None:
                return

            # Parse output as JSON
            try:
                comment_data = json.loads(output)
            except json.JSONDecodeError as e:
                print(f"Failed to parse CommentLister output: {e}")
                return

            # Filter comments by time
            filtered_comments = filter_comments_by_time(comment_data, start_time, end_time)
            commit["comments"] = filtered_comments
            
    # Save filtered comments
    with open('Data/filtered_commits_data.json', 'w') as f:
        json.dump(commits, f, indent=4)

    
    
    shutil.rmtree(clone_path)

if __name__ == "__main__":
    main()