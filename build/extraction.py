from datetime import datetime
from fileinput import filename
from operator import concat

from isort import file
from numpy import block

from build.classification import classify_comments, classify_content


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

def split_comments_to_lines(code_data, raw_comment_data):
    processed_comments = {}
    for filename, contents in raw_comment_data["Files"].items():
        processed_comments[filename] = {}
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
                            "type": list(dict.fromkeys(type + classify_content(comment) + classify_content(code_data[initial_line + j])))
                        }
                        processed_comments[filename][initial_line + j] = comment_data
                        j += 1
                else:
                    comment_data = {
                        "comment": contents[str(i)]["Text"],
                         "type": list(dict.fromkeys(type + classify_content(contents[str(i)]["Text"]) + classify_content(code_data[contents[str(i)]["Line"]])))
                    }
                    processed_comments[filename][contents[str(i)]["Line"]] = comment_data
            except KeyError as e:
                error = True
            if not error:
                i += 1
    return raw_comment_data["ObjectId"], processed_comments

def blockify_code_data_v1_to_3(data, version):
    comments = "comments"
    source_code = "source_code"
    for _, commits in data.items():
        for commit in commits:
            blocks = []
            current_block = {}
            for line_number, content in commit[source_code].items():
                if content.find("def ") != -1 and current_block != {}:
                    if version == "v1":
                        current_block["code_linesv1"] = "".join(current_block["code_linesv2"])
                        current_block.pop("code_linesv2")
                    blocks.append(current_block)
                    current_block = {}
                if version == "v1" or version == "v2":
                    if current_block == {}:
                        current_block.setdefault("code_linesv2", []).append(content)
                    else: 
                        current_block["code_linesv2"].append(content)
                if version == "v3":
                    current_block.setdefault("code_linesv3", {})[line_number] = content
                if version == "v4":
                    if line_number in commit["diff"]["added"].keys():
                        current_block.setdefault("code_linesv4", {})[line_number] = concat("++", content)
                    if line_number in commit["diff"]["deleted"].keys():
                        if "code_linesv4" in  list(current_block.keys()) and line_number in current_block["code_linesv4"]:
                            current_block["code_linesv4"][line_number] += concat("\\\n--", commit["diff"]["deleted"][line_number])
                        else:
                            current_block.setdefault("code_linesv4", {})[line_number] = concat("--", commit["diff"]["deleted"][line_number])
                    elif line_number not in commit["diff"]["added"].keys():
                        current_block.setdefault("code_linesv4", {})[line_number] = concat("  ", content)
                if line_number in list(commit[comments].keys()):
                    current_block.setdefault("comment_lines", {})[line_number] = commit[comments][line_number]
            if current_block != {}:
                if version == "v1":
                        current_block["code_linesv1"] = "".join(current_block["code_linesv2"])
                        current_block.pop("code_linesv2")
                blocks.append(current_block)
            commit[source_code] = blocks

def blockify_code_data(data, version):
    comments = "comments"
    source_code = "source_code_old"
    for _, commits in data.items():
        for commit in commits:
            blocks = []
            current_block = {"code_linesv4": []}
            shift_map = []
            i = 1
            i_del = 1
            i_add = 1
            # Calculate where to insert diff added and deleted lines
            while int(i_del) < len(list(commit["source_code_old"].keys())) and int(i_add) < len(list(commit["source_code"].keys())):
                i_del = str(i + sum(a for a, _ in shift_map))
                i_add = str(i + sum(b for _, b in shift_map))
                if i_del in commit["diff"]["deleted"].keys() and i_add not in commit["diff"]["added"].keys():
                    shift_map.append((1, 0))
                    text = i_del + " " + i_add + "--" + commit["diff"]["deleted"][i_del]
                elif i_del not in commit["diff"]["deleted"].keys() and i_add in commit["diff"]["added"].keys():
                    shift_map.append((0, 1))
                    text = i_del + " " + i_add + "++" + commit["diff"]["added"][i_add]
                elif i_del in commit["diff"]["deleted"].keys() and i_add in commit["diff"]["added"].keys():
                    shift_map.append((1, 1))
                    text = i_del + " " + i_add + "--" + commit["diff"]["deleted"][i_del] + "++" + commit["diff"]["added"][i_add]
                else:
                    shift_map.append((0, 0))
                    text = i_del + " " + i_add + "  " + commit[source_code][str(i_del)]
                    i += 1
                # TODO Add proper check if i was not increased although lines still had to be added
                if text.find("def ") != -1 and current_block != {"code_linesv4": []}:
                    if "++" in "".join(current_block["code_linesv4"]) or "--" in "".join(current_block["code_linesv4"]):
                        blocks.append(current_block)
                    current_block = {"code_linesv4": []}

                current_block["code_linesv4"].append(text)
                if i_add in commit[comments].keys():
                    if shift_map[-1] == (0, 1):
                        commit["comments"][i_add]["edit"] = "added"
                        current_block.setdefault("comment_lines", {})[i_add] = commit[comments][i_add]
                    elif shift_map[-1] == (1, 1):
                        commit["comments"][i_add]["edit"] = "modifiedd"
                        current_block.setdefault("comment_lines", {})[i_add] = commit[comments][i_add]
                    else:
                        commit["comments"][i_add]["edit"] = "unedited"
                    current_block.setdefault("comment_lines", {})[i_add] = commit[comments][i_add]

            if current_block != {"code_linesv4": []}:
                if "++" in "".join(current_block["code_linesv4"]) or "--" in "".join(current_block["code_linesv4"]):
                    blocks.append(current_block)
            commit["source_code_blocks"] = blocks
            del commit["comments"]
            del commit["diff"]
            del commit["source_code"]
            del commit["source_code_old"]

def make_table(data, version):
    table = []
    for filename, commits in data.items():
        for commit in commits:
            for block in commit["source_code_blocks"]:
                if block["code_linesv4"][0].find("def ") != -1:
                    method_name = block["code_linesv4"][0].split("def ")[1].split("(")[0]
                else:
                    method_name = "Not a Method"
                try:
                    comments_blocks = block["comment_lines"]
                    comment_lines, comments = list(comments_blocks.keys()), list(comments_blocks["comment"])
                except KeyError:
                    comments = ""
                    comment_lines = 0
                line = [method_name, commit["commit"], commit["author"], commit["timestamp"], filename, block["code_linesv4"], comments, len(block["code_linesv4"]), comment_lines]
                table.append(line)
    return table

def is_equal(d1,d2):
    d1_k = list(d1.keys())
    for i in d1_k:
        if d1[i] != d2[i]:
            return False
    return True