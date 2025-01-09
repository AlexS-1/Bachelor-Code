from datetime import datetime, timedelta
from tkinter import NO

from httpx import get

from build.classification import classify_comments, classify_content
from build.extraction import blockify_code_data
from build.pydriller import get_commit_data, get_parent_commit


def analyse_diff_comments(data):
    for file, commits in data.items():
        for commit in commits:
            for line in list(commit["comments"].keys()):
                if line in list(commit["diff"]["added"].keys()):
                    commit["comments"][line]["edit"] = "added"
                if line in list(commit["diff"]["deleted"].keys()):
                    if "edit" in list(commit["comments"][line].keys()):
                        commit["comments"][line]["edit"] = "modified"
                        continue
                    else:
                        commit["comments"][line]["edit"] = "deleted"
                        continue
            for line in list(commit["comments_old"].keys()):
                if line in list(commit["diff"]["added"].keys()):
                    commit["comments_old"][line]["edit"] = "added"
                if line in list(commit["diff"]["deleted"].keys()):
                    if "edit" in list(commit["comments_old"][line].keys()):
                        commit["comments_old"][line]["edit"] = "modified"
                        continue
                    else:
                        commit["comments_old"][line]["edit"] = "deleted"
                        continue

def set_metadata_for_block(data):
    for file, commits in data.items():
        previous_commit = 0
        previous_commit_old = 0
        for commit in range(len(commits)):
            for block in commits[commit]["source_code"]:
                # Analyse block if newly created
                if commit != previous_commit:
                    created, creation_timestamp = _block_created(block, commits[previous_commit]["source_code"])
                else:
                    created = True
                if created: 
                    creation_timestamp = commits[commit]["timestamp"]
                # Analyse block for code changes to previous block (block that includes the same line)
                if commit != previous_commit and creation_timestamp != commits[commit]["timestamp"]:
                    changed, change_time = _code_changed(block, commits[previous_commit]["source_code"])
                else: 
                    changed = True
                if changed or creation_timestamp == commits[commit]["timestamp"]:
                    code_last_modified = commits[commit]["timestamp"]
                else:
                    code_last_modified = change_time
                # Analyse block for comment changes to previous block (block that includes the same line)
                if "comment_lines" in list(block.keys()):
                    for line in list(list(block["comment_lines"].keys())):
                        if line in list(commits[commit]["diff"]["added"].keys()):
                            comment_last_modified = commits[commit]["timestamp"]
                            break
                        else:
                            if commit != previous_commit:
                                if _comment_changed(block, commits[previous_commit]["source_code"]) != "mismatching comments":
                                    comment_last_modified = _comment_changed(block, commits[previous_commit]["source_code"])
                                else:
                                    comment_last_modified = commits[commit]["timestamp"]
                            else:
                                comment_last_modified = commits[commit]["timestamp"]
                else: 
                    comment_last_modified = "has_no_comments"
                block["metadata"] = {
                    "file": file,
                    "commit": commits[commit]["commit"],
                    "creation_timestamp": creation_timestamp,
                    "code_last_modified": code_last_modified,
                    "comment_last_modified": comment_last_modified
                }
            if commit != 0:
                previous_commit += 1

            # Repeat process for old source_code
            for block in commits[commit]["source_code_old"]:
                blockified_source_code_old = None # Initialize variable as otherwise not reachable throughout the different if statements
                # Determine wether block was newly created
                if commit == previous_commit_old:
                    commit_hash_old = get_parent_commit(commits[commit]["commit"], file)
                    commit_data_old = get_commit_data(commit_hash_old, file, old=True)
                    if commit_data_old[file][0]["source_code_old"] == {}:
                        created = True
                        creation_timestamp = commit_data_old[file][previous_commit_old]["timestamp"]
                    else:
                        blockify_code_data(commit_data_old, old=True)
                        created, creation_timestamp = _block_created(block, commit_data_old[file][previous_commit_old]["source_code_old"])
                else:
                    blockified_source_code_old = commits[previous_commit_old]["source_code_old"]
                    created, creation_timestamp = _block_created(block, blockified_source_code_old)
                    if created: 
                        creation_timestamp = commits[previous_commit]["timestamp"]
                # Analyse block for code changes to previous block (block that includes the same line)
                if creation_timestamp != commits[previous_commit]["timestamp"] and blockified_source_code_old != None:
                    changed, change_time = _code_changed(block, blockified_source_code_old)
                    code_last_modified = change_time
                else: 
                    changed = True
                    code_last_modified = commits[previous_commit]["timestamp"]
                # Analyse block for comment changes to previous block (block that includes the same line)
                if "comment_lines" in list(block.keys()):
                    for line in list(list(block["comment_lines"].keys())):
                        if line in list(commits[previous_commit_old]["diff"]["added"].keys()):
                            comment_last_modified = commits[previous_commit_old]["timestamp"]
                            break
                        else:
                            if created:
                                comment_last_modified = commits[previous_commit_old]["timestamp"]
                            elif _comment_changed(block, blockified_source_code_old) == "mismatching comments":
                                comment_last_modified = _comment_changed(block, blockified_source_code_old)
                            else:
                                comment_last_modified = commits[previous_commit_old]["timestamp"]
                else: 
                    comment_last_modified = "has_no_comments"
                block["metadata"] = {
                    "file": file,
                    "commit": commits[commit]["commit"],
                    "creation_timestamp": creation_timestamp,
                    "code_last_modified": code_last_modified,
                    "comment_last_modified": comment_last_modified
                }
            if commit != 0:
                previous_commit_old += 1
            
            # TODO Temporaryily disabled for testing purposes
            # del commits[commit]["diff"]
            # del commits[commit]["comments"]

def _block_created(block_new, blocks_old):
    old_sourcecode = []
    for block in blocks_old:
        old_sourcecode.extend(list((block["code_lines"].keys())))
    start_line = list(block_new["code_lines"].keys())[0]
    if start_line not in old_sourcecode:
        return True, "CREATED"
    else:
        for block in blocks_old:
            if start_line in list(block["code_lines"].keys()):
                block_created = block["metadata"]["creation_timestamp"]
                return False, block_created
    raise Exception("ERROR: new block neither found in old blocks nor created")
                
def _code_changed(block_new, blocks_old):
    for block_old in blocks_old:
        for line_old in list(block_old["code_lines"].keys()):
            if line_old in list(block_new["code_lines"].keys()):
                # Check if block has comments and if so, remove them from comparison
                if "comment_lines" not in (list(block_old.keys()) or list(block_new.keys())):
                    return list(block_old["code_lines"]) != list(block_new["code_lines"]), block_old["metadata"]["code_last_modified"]
                else:
                    if "comment_lines" in list(block_old.keys()):
                        actual_code_old = [line for line in block_old["code_lines"] if line not in block_old["comment_lines"]]
                    else:
                        actual_code_old = block_old["code_lines"]
                    if "comment_lines" in list(block_new.keys()):
                        actual_code_new = [line for line in block_new["code_lines"] if line not in block_new["comment_lines"]]
                    else:
                        actual_code_new = block_new["code_lines"]
                    # Compare content of code lines and return if different, else code_changed returns False 
                    # TODO Indent less as now for first found line already return?
                    for code_line_old, code_line_new in zip(actual_code_old, actual_code_new):
                        if block_old["code_lines"][code_line_old] != block_new["code_lines"][code_line_new]:
                            return actual_code_old != actual_code_new, block_old["metadata"]["code_last_modified"]
                    return False, block_old["metadata"]["code_last_modified"]
    raise Exception("ERROR: No line from block_new found in old_blocks")

def _comment_changed(block_new, old_blocks):
    matched_comments = []
    for block in old_blocks:
        # Go through comment lines of current block and 
        if "comment_lines" in list(block.keys()):
            for _, comment_data_new in block_new["comment_lines"].items():
                for _, comment_data in block["comment_lines"].items():
                    if comment_data["comment"] == comment_data_new["comment"]:
                        matched_comments.append(block["metadata"]["comment_last_modified"])
    if len(matched_comments) == len(list(block_new["comment_lines"].keys())):
        return matched_comments[-1]
    else:
        return "mismatching comments"

def only_code_in_block(block):
    try:
        block["comment_lines"]
        return True
    except KeyError:
        return False

def average_comment_update_time(data):
    datetime_pairs = []
    if data == None: return
    for block in data:
        start = datetime.fromisoformat(block["metadata"]["code_last_modified"])
        end = datetime.fromisoformat(block["metadata"]["comment_last_modified"])
        datetime_pairs.append((start, end))
    durations = [end - start for start, end in datetime_pairs]
    total_duration = sum(durations, timedelta(0))
    if durations != []:
        average_duration = total_duration / len(durations)
        return average_duration
    else:
        return 0