from datetime import datetime, timedelta
import tokenize
from io import StringIO
import re

def analyse_diff_comments(data):
    for file, commits in data.items():
        for commit in commits:
            no_change_comments = []
            for line in list(commit["comments"].keys()):
                if line in list(commit["diff"]["added"].keys()):
                    commit["comments"][line]["edit"] = "added"
                continue
                if line in list(commit["diff"]["deleted"].keys()):
                    if "edit" in list(commit["comments"][line].keys()):
                        commit["comments"][line]["edit"] = "modified"
                        continue
                    else:
                        commit["comments"][line]["edit"] = "deleted"
                        continue
                no_change_comments.append(int(line))
            # Ensure the gaps of deleted elements are artificially filled by increasing the shift
            shift = 0
            for i in no_change_comments:
                del commit["comments"][i-shift]
                shift += 1

def blockify_code_data(data):
    for file, commits in data.items():
        for commit in commits:
            blocks = []
            current_block = {}
            for line_number, content in commit["source_code"].items():
                if line_number in list(commit["comments"].keys()):
                    if current_block != {} and list(current_block["code_lines"].keys())[-1] not in list(commit["comments"].keys()):
                        blocks.append(current_block)
                        current_block = {}
                    current_block.setdefault("code_lines", {})[line_number] = content
                    current_block.setdefault("comment_lines", {})[line_number] = commit["comments"][line_number]
                else:
                    current_block.setdefault("code_lines", {})[line_number] = content
            if current_block != {}:
                blocks.append(current_block)
            commit["source_code"] = blocks

def blockify_diff(data, type):
    for file, commits in data.items():
        for commit in commits:
            blocks = []
            current_block = {}
            for line_number, content in commit["diff"][type].items():
                if line_number in list(commit["comments"].keys()):
                    if (current_block != {} and list(current_block.keys())[-1] not in list(commit["comments"].keys())) or current_block != {} and int(line_number) != int(list(current_block.keys())[-1]) + 1:
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
        last_modified = {}
        for commit in commits:
            # print("Starting to analyse commit: ", commit["commit"])
            commit_time = datetime.fromisoformat(commit["timestamp"])
            # Track modified lines
            for line in list(commit["diff"]["added"].keys()):
                last_modified[line] = commit_time
            # Compare with comments
            for line in list(commit["comments"].keys()):
                comment_time = datetime.fromisoformat(commit["timestamp"])
                last_modified_lines = list(last_modified.keys())
                # TODO investigate why line is null
                if line != "null" and line in last_modified_lines:
                    for block in commit["diff"]["added-block"]:
                        # Where there are comment changes and no source code changes in block
                        if not only_code_in_block(block): # and block[line["line"]]["comment_index"] != -1:
                            if comment_time > last_modified[line]:
                                comment = commit["comments"][line]["comment"]
                                comment_type = commit["comments"][line]["type"]
                                for comit in commits:
                                    if datetime.fromisoformat(comit["timestamp"]) == comment_time:
                                        for block in commit["source_code"]:
                                            if line in list(block["code_lines"].keys()):
                                                content = block["code_lines"][line]
                                        break
                                if len(analysis_results) == 0 or (len(analysis_results) > 0 and analysis_results[-1]["comment"] != comment):  
                                    analysis_results.append({
                                        "file": file,
                                        "line": line,
                                        "content": content,
                                        "comment": comment,
                                        "type": comment_type,
                                        "comment_time": str(comment_time),
                                        "last_code_change_time": str(last_modified[line])
                                    })
    del commit["comments"]
    return analysis_results

def only_code_in_block(block):
    try:
        block["comment_lines"]
        return True
    except KeyError:
        return False

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

def classify_content(line):
    comment_types = []
    if line.find("#") != -1 and line.split("#")[0].strip() != "":
        comment_types.append("inline")
    if is_potential_code(line.strip().lstrip("#").strip()) and is_potential_code(line.strip().lstrip("\"\"\"").strip()):
        comment_types.append("commented-out")
    return comment_types