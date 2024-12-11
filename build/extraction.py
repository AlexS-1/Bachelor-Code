from datetime import datetime
from build.analysis import classify_content
from build.classification import classify_comments


def order_commits_data(commit_data):
    ordered_commits = {}
    for commit_filename, _ in commit_data.items():
        ordered_commits[commit_filename] = []
    for commit_filename, commit_file_data in commit_data.items():
        for commit in commit_file_data:
            if ordered_commits[commit["filename"]] == []:
                ordered_commits[commit["filename"]].append(commit)
            elif ordered_commits[commit["filename"]][-1]["commit"] != commit["commit"]:
                ordered_commits[commit["filename"]].append(commit)
    return ordered_commits

def diff_to_dict(diff):
    dict_added = {}
    for line in diff["added"]:
        dict_added[line[0]] = line[1]
    diff["added"] = dict_added
    dict_deleted = {}
    for line in diff["deleted"]:
        dict_deleted[line[0]] = line[1]
    diff["deleted"] = dict_deleted
    return diff

def extract_keywords(commit_message, modified_file):
    # Determine basic keywords based on the commit message
    keywords = []
    if "performance" in commit_message.lower():
        keywords.append("performance")
    if "security" in commit_message.lower():
        keywords.append("security")
    if modified_file.added_lines > modified_file.deleted_lines:
        keywords.append("expansion")
    else:
        keywords.append("optimization")
    return keywords

def extract_activity(commit_message):
    # Use commit message keywords to determine activity type
    activity = ""
    if "bug" in commit_message.lower() or "fix" in commit_message.lower():
        activity = "Bug Fix"
    elif "feature" in commit_message.lower() or "add" in commit_message.lower():
        activity = "Feature Development"
    elif "refactor" in commit_message.lower():
        activity = "Refactoring"
    else:
        activity = "Other"
    return activity

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
                                "type": type + classify_content(comment)
                            }
                            filtered_comments[filename][initial_line + j] = comment_data
                            j += 1
                    else:
                        comment_data = {
                            "comment": contents[str(i)]["Text"],
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

def blockify_code_data(data, old=False):
    if old:
        comments = "comments_old"
        source_code = "source_code_old"
    else:
        comments = "comments"
        source_code = "source_code"
    for _, commits in data.items():
        for commit in commits:
            blocks = []
            current_block = {}
            for line_number, content in commit[source_code].items():
                if comments in list(commit.keys()) and line_number in list(commit[comments].keys()):
                    if current_block != {} and list(current_block["code_lines"].keys())[-1] not in list(commit[comments].keys()):
                        blocks.append(current_block)
                        current_block = {}
                    current_block.setdefault("code_lines", {})[line_number] = content
                    current_block.setdefault("comment_lines", {})[line_number] = commit[comments][line_number]
                else:
                    current_block.setdefault("code_lines", {})[line_number] = content
            if current_block != {}:
                blocks.append(current_block)
            commit[source_code] = blocks

def blockify_diff(data, type):
    for file, commits in data.items():
        for commit in commits:
            blocks = []
            current_block = {}
            for line_number, content in commit["diff"][type].items():
                if type == "added":
                    comments = commit["comments"]
                else:
                    comments = commit["comments_old"]
                if line_number in list(comments.keys()):
                    if (current_block != {} and list(current_block.keys())[-1] not in list(comments.keys())) or current_block != {} and int(line_number) != int(list(current_block.keys())[-1]) + 1:
                        blocks.append(current_block)
                        current_block = {}
                    current_block[line_number] = content
                else:
                    if current_block != {} and int(line_number) != int(list(current_block.keys())[-1]) + 1:
                        blocks.append(current_block)
                        current_block = {}
                    current_block[line_number] = content
            if current_block != {}:
                blocks.append(current_block)
            commit["diff"][type + "-" + "block"] = blocks

def extract_later_modified_comments(data):
    analysis_results = []
    for file, commits in data.items():
        # Store last modified timestamps for each line
        for commit in commits:
            for block in commit["source_code"]:
                if "has_no_comments" != block["metadata"]["comment_last_modified"] and datetime.fromisoformat(block["metadata"]["code_last_modified"]) < datetime.fromisoformat(block["metadata"]["comment_last_modified"]):
                    analysis_results.append(block)
    return analysis_results

def clean(data):
    clean_data = []
    for i in range(len(data)):
        item = {
            "file": data[i]["file"],
            "line": data[i]["line"],
            "content": data[i]["content"],
            "comment": data[i]["comment"],
            "type": data[i]["type"],
            "comment_time": data[i]["comment_time"],
            "last_code_change_time": data[i]["last_code_change_time"]
        }
        if len(data) > i + 1 and not is_equal(data[i], data[i+1]):
            clean_data.append(item)
    return clean_data

def is_equal(d1,d2):
    d1_k = list(d1.keys())
    d2_k = list(d2.keys())
    for i in d1_k:
        if d1[i] != d2[i]:
            return False
    return True