import subprocess
import json
import os
import shutil
from datetime import datetime, timezone
from build.analysis import classify_comments, classify_content

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
    filtered_comments = {}
    commit_time = datetime.fromisoformat(commit_data["CommitTime"]).replace(tzinfo=None)
    if start_time <= commit_time <= end_time:
        for filename, contents in commit_data["Files"].items():
            filtered_comments[filename] = {}
            error = False
            i = 0
            while not error:
                try:
                    type = classify_comments(contents[str(i)]["Text"])
                    split_comment_lines = contents[str(i)]["Text"].split("\n")
                    # print("Have to split comments:", split_comment_lines)
                    if len(split_comment_lines) > 1:
                        initial_line = contents[str(i)]["Line"]
                        j = 0
                        for comment in split_comment_lines:
                            # Assumption: All multi line comments are formatted in one block, i.e. vertically in one collum
                            comment_data = {
                                "comment": comment,
                                "char_position_in_line": contents[str(i)]["CharPositionInLine"],
                                "type": type + classify_content(comment)
                            }
                            filtered_comments[filename][initial_line + j] = comment_data
                            j += 1
                    else:
                        comment_data = {
                            "comment": contents[str(i)]["Text"],
                            "char_position_in_line": contents[str(i)]["CharPositionInLine"],
                            "type": type
                        }
                        filtered_comments[filename][contents[str(i)]["Line"]] = comment_data
                except KeyError as e:
                    error = True
                if not error:
                    i += 1
    else:
        print("Comments not in specified date range")
    return commit_data["ObjectId"], filtered_comments