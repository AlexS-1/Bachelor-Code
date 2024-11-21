import subprocess
import json
import os
import shutil
from datetime import datetime, timezone

def run_comment_lister(repo_path, jar_path, tag="-target=HEAD"):
    try:
        result = subprocess.run(
            ['java', '-jar', jar_path, repo_path, tag],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running CommentLister: {e.stderr}")
        return None

def filter_comments_by_time(commit_data, start_time, end_time):
    filtered_comments = []
    commit_time = datetime.fromisoformat(commit_data["CommitTime"])
    if start_time <= end_time:
        for filename, contents in commit_data["Files"].items():
            i = 0
            error = False
            while not error:
                try:
                    comment_data = {
                        "line": contents[str(i)]["Line"],
                        "comment": contents[str(i)]["Text"]
                    }
                except KeyError as e:
                    error = True
                if not error:
                    filtered_comments.append(comment_data)
                i += 1
    return filtered_comments