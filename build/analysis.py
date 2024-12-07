from datetime import datetime, timedelta
import tokenize
from io import StringIO
import re

def analyse_diff_comments(data):
    for file, commits in data.items():
        for commit in commits:
            no_change_comments = []
            for i in range(len(commit["comments"])):
                if commit["comments"][i]["line"] in list(commit["diff"]["added"].keys()):
                    commit["comments"][i]["edit"] = "added"
                continue
                if commit["comments"][i]["line"] in list(commit["diff"]["deleted"].keys()):
                    if "edit" in list(commit["comments"][i].keys()):
                        commit["comments"][i]["edit"] = "modified"
                        continue
                    else:
                        commit["comments"][i]["edit"] = "deleted"
                        continue
                no_change_comments.append(i)
            # Ensure the gaps of deleted elements are artificially filled by increasing the shift
            shift = 0
            for j in no_change_comments:
                del commit["comments"][j-shift]
                shift += 1
    print("Finished")

def check_inline_comments(data):
    return

def blockify_comments2(data):
    for file, commits in data.items():
        for commit in commits:
            block_diff = []
            for block in commit["diff"]["block_diff"]:
                block_dict = {}
                for line in block:
                    comment_index = -1
                    for item in commit["comments"]:
                        if int(line) == item["line"]:
                            comment_index = item["char_position_in_line"]
                            break
                    line_info = {
                        "content": commit["diff"]["added"][str(line)],
                        "comment_index": comment_index
                    }
                    block_dict[line] = line_info
                block_diff.append(block_dict)
            commit["diff"]["block_diff"] = block_diff

def blockify_comments(data):
    for file, commits in data.items():
        for commit in commits:
            blocks = []
            current_block = []
            for line in list(commit["diff"]["added"].keys()):
                if int(line) in get_comment_lines(commit["comments"]):
                    if current_block and current_block[-1] not in get_comment_lines(commit["comments"]):
                        blocks.append(current_block)
                        current_block = []
                    current_block.append(int(line))
                else:
                    if current_block and int(line) != current_block[-1] + 1:
                        blocks.append(current_block)
                        current_block = []
                    current_block.append(int(line))
            if current_block:
                blocks.append(current_block)
            commit["diff"]["block_diff"] = blocks

def get_comment_lines(comments):
    comment_lines = []
    for comment in comments:
        comment_lines.append(comment["line"])
    return comment_lines

def get_diff_lines(diff):
    diff_lines = []
    for line in diff:
        diff_lines.append(line[0])
    return diff_lines

def extract_later_modified_comments(data): 
    analysis_results = []
    for file, commits in data.items():
        # Store last modified timestamps for each line
        last_modified = {}
        for commit in commits:
            # print("Starting to analyse commit: ", commit["commit"])
            commit_time = datetime.fromisoformat(commit["timestamp"])
            # Track modified lines
            for line in list(commit["diff"]["added"].keys()):
                last_modified[line] = commit_time
            # Compare with comments
            for line in commit["comments"]:
                comment_time = datetime.fromisoformat(commit["timestamp"])
                last_modified_lines = list(last_modified.keys())
                # TODO investigate why line is null
                if line != "null" and str(line["line"]) in last_modified_lines:
                    for block in commit["diff"]["block_diff"]:
                        # Where there are comment changes and no source code changes in block
                        if not is_code_in_block(block): # and block[line["line"]]["comment_index"] != -1:
                            if comment_time > last_modified[str(line["line"])]:
                                for item in commit["comments"]:
                                    if line["line"] == item["line"]:
                                        comment = item["comment"]
                                        type = item["type"]
                                        break
                                for commit2 in commits:
                                    if datetime.fromisoformat(commit2["timestamp"]) == comment_time:
                                        content = commit2["source_code"][str(line["line"])]
                                        break
                                    else:
                                        content = "PROBLEM"
                                analysis_results.append({
                                    "file": file,
                                    "line": line["line"],
                                    "content": content,
                                    "comment": comment,
                                    "type": type,
                                    "comment_time": str(comment_time),
                                    "last_code_change_time": str(last_modified[str(line["line"])])
                                })
    return analysis_results

def is_code_in_block(block):
    for line in list(block.keys()):
        if block[line]["comment_index"] == -1:
            return True 

def clean(data):
    clean_data = []
    for i in range(len(data)):
        item = {
            "file": data[i]["file"],
            "line": data[i]["line"],
            "content": data[i]["content"], # Cheeky inline comment
            "comment": data[i]["comment"], # Cheeky 2 inline comment
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

def average_comment_update_time(data):
    datetime_pairs = []
    if data == None: return
    for file in data:
        start = datetime.fromisoformat(file["last_code_change_time"])
        end = datetime.fromisoformat(file["comment_time"])
        datetime_pairs.append((start, end))
    durations = [end - start for start, end in datetime_pairs]
    total_duration = sum(durations, timedelta(0))
    average_duration = total_duration / len(durations)
    return average_duration

def classify_comments(lines):
        line_types = []
        # Check for commented-out code (basic heuristic: looks like valid Python code)
        if is_potential_code(lines.lstrip("#").strip()) and is_potential_code(lines.lstrip("\"\"\"").strip()):
            line_types.append("commented-out")
        # Check for block comments (multi-line consecutive)
        if lines.find("\n") != -1:
            line_types.append("block")
        # Check if text has docstring format with """" somewhere
        if lines.find("\"\"\"") != -1:
            line_types.append("docstring")
        if len(line_types) == 0:
            line_types.append("normal")
        return line_types

def is_potential_code(text):
    try:
        compile(text, "<string>", "exec")
        return True
    except SyntaxError:
        return False

def classify_content(data):
    for item in data:
        if "normal" or "block" in item["type"]:
            line = item["content"]
            if line.find("#") != -1 and line.split("#")[0].strip() != "":
                item["type"] = ["inline"]
    return data