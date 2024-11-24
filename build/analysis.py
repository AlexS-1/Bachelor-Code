def analyse_diff_comments(data):
    for file, commits in data.items():
        for commit in commits:
            no_change_comments = []
            for i in range(len(commit["comments"])):
                for item in commit["diff"]["added"]:
                    if commit["comments"][i]["line"] == item[0] :
                        commit["comments"][i]["edit"] = "added"
                        break
                continue
                if commit["comments"][i]["line"] in [item[0] for item in commit["diff"]["deleted"]]:
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

def check_inline_comments(data):
    return

def blockify_comments(data):
    for file, commits in data.items():
        for commit in commits:
            blocks = []
            for line in commit["diff"]["added"]:
                # Add line to block, if line follows previous line of block
                if len(blocks) > 0 and blocks[-1]["lines"][-1] + 1 == line[0]:
                    break_outer = False
                    comment = ""
                    comment_position = -1
                    edit = ""
                    for item in commit["comments"]:
                        if line[0] == item["line"]:
                            comment = item["comment"]
                            comment_position = item["char_position_in_line"]
                            edit = item["edit"]
                            # Except when line is comment following source code, create new block
                            if blocks[-1]["comments"][-1] == "":
                                block = {
                                    "lines": [line[0]],
                                    "contents": [line[1]],
                                    "comments": [comment],
                                    "comment_positions": [comment_position],
                                    "edits": [edit]
                                }
                                blocks.append(block)
                                break_outer = True
                    if break_outer:   
                        continue
                    blocks[-1]["lines"].append(line[0])
                    blocks[-1]["contents"].append(line[1])
                    blocks[-1]["comments"].append(comment)
                    blocks[-1]["comment_positions"].append(comment_position)
                    blocks[-1]["edits"].append(edit)

                # Create new block, otherwise
                else:
                    comment = ""
                    comment_position = -1
                    edit = ""
                    for item in commit["comments"]:
                        if line[0] == item["line"]:
                            comment = item["comment"]
                            comment_position = item["char_position_in_line"]
                            edit = item["edit"]
                    block = {
                        "lines": [line[0]],
                        "contents": [line[1]],
                        "comments": [comment],
                        "comment_positions": [comment_position],
                        "edits": [edit]
                    }
                    blocks.append(block)
            commit["diff"]["block_diff"] = blocks

def extract_later_modified_comments(data): 
    analysis_results = []
    for file, commits in data.items():
        # Store last modified timestamps for each line
        last_modified = {}
        for commit in commits:
            # print("Starting to analyse commit: ", commit["commit"])
            commit_time = datetime.fromisoformat(commit["timestamp"])
            # Track modified lines
            for line in commit["diff"]["added"]:
                last_modified[line] = commit_time
            # Compare with comments
            for line in commit["comments"]:
                comment_time = datetime.fromisoformat(commit["timestamp"])
                last_modified_lines = list(last_modified.keys())
                if int(line) in last_modified_lines:
                    for block in commit["diff"]["block_diff"]:
                        if line in block["comments"] and len(block["lines"]) == 0:
                            if(comment_time > last_modified[int(line)]):
                                analysis_results.append({
                                    "file": file,
                                    "line": int(line),
                                    "comment": commit["comment_added_diff"][line],
                                    "comment_time": str(comment_time),
                                    "last_code_change_time": str(last_modified[int(line)])
                                })
    return analysis_results