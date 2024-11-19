from pydriller import Repository
import json
import pm4py
from datetime import datetime
from pm4py.objects.log.obj import EventLog, Trace, Event
from pm4py.objects.log.exporter.xes import exporter as xes_exporter

def analyze_commits(repo_url, language_file_extension, dt1, dt2, single_comment_symbol, multi_comment_symbols=[]):
    files_data = {}
    # Traverse through the commits in the repository
    # Only save commits, that contain at least one file of the format {language_file_extension}
    for commit in Repository(repo_url, 
    only_modifications_with_file_types=[f".{language_file_extension}"],
    since=dt1,
    to=dt2).traverse_commits():
        if len(multi_comment_symbols) >= 2:
            multi_comments_enabled = True
        else:
            multi_comments_enabled = False
        # Analyze each file modified in the commit
        for modified_file in commit.modified_files:
            # only store file data for Rust files
            if modified_file.filename not in files_data:
                files_data[modified_file.filename] = []
            if len(modified_file.filename.split(".")) == 2 and modified_file.filename.split(".")[1] == language_file_extension:
                file_data = {
                    "commit": commit.hash,
                    "timestamp": commit.committer_date.isoformat(),
                    "author": commit.author.name,
                    "commit_message": commit.msg,
                    "additions": modified_file.added_lines,
                    "deletions": modified_file.deleted_lines,
                    "change_type": modified_file.change_type.name,
                    "diff": modified_file.diff_parsed
                }
                diff_added = {}
                diff_deleted = {}
                diff_modified = {}
                following_multi_comment = False
                # For added diff ispect lines filter out comments
                for line in modified_file.diff_parsed["added"]:
                    if line[1].find(single_comment_symbol) != -1 or following_multi_comment:
                        diff_added[line[0]] = line[1]
                    if multi_comments_enabled and line[1].find(multi_comment_symbols[0]) != -1:
                        diff_added[line[0]] = line[1]
                        following_multi_comment = True
                    if multi_comments_enabled and line[1].find(multi_comment_symbols[1]) != -1:
                        diff_added[line[0]] = line[1]
                        following_multi_comment = False
                file_data["comment_added_diff"] = diff_added
                # For deleted diff ispect lines filter out comments
                for line in modified_file.diff_parsed["deleted"]:
                    if line[1].find(single_comment_symbol) != -1 or following_multi_comment:
                        diff_deleted[line[0]] = line[1]
                        if line[0] in diff_added.keys():
                            diff_modified[line[0]] = line[1]
                    if multi_comments_enabled and line[1].find(multi_comment_symbols[0]) != -1:
                        diff_added[line[0]] = line[1]
                        following_multi_comment = True
                        if line[0] in diff_added.keys():
                            diff_modified[line[0]] = line[1]
                    if multi_comments_enabled and line[1].find(multi_comment_symbols[1]) != -1:
                        diff_added[line[0]] = line[1]
                        if line[0] in diff_added.keys():
                            diff_modified[line[0]] = line[1]
                file_data["comment_deleted_diff"] = diff_deleted
                file_data["comment_modified_diff"] = diff_modified
                # Generate keywords based on the commit message and type of changes
                # file_data["keywords"] = extract_keywords(commit.msg, modified_file)
                # Extract type of commit from commit message
                # file_data["activity"] = extract_activity(commit.msg)
                if len(diff_added) + len(diff_deleted) != 0:
                    files_data[modified_file.filename].append(file_data)
    return files_data

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
    if "bug" in commit.msg.lower() or "fix" in commit.msg.lower():
        activity = "Bug Fix"
    elif "feature" in commit.msg.lower() or "add" in commit.msg.lower():
        activity = "Feature Development"
    elif "refactor" in commit.msg.lower():
        activity = "Refactoring"
    else:
        activity = "Other"
    return activity

def pretty_diff(commits_data, type, single_comment_symbol, multi_comment_symbols=[]):
    following_multi_comment = False
    if len(multi_comment_symbols) >= 2:
        multi_comments_enabled = True
    else:
        multi_comments_enabled = False
    for file, commits in commits_data.items():
        if len(file) > 0:
            for commit in commits:
                diff_edited = []
                # Set current line for each analysis
                for i in range(len(commit["diff"][type])):
                    curr_line = commit["diff"][type][i][0]
                    curr_content = commit["diff"][type][i][1]
                    # In case of a starting multiline comment start adding future lines without comment symbol 
                    if curr_content.find(multi_comment_symbols[0]) != -1:
                            following_multi_comment = True
                    # In case of comment add them to existing dict if they directly follow
                    if curr_content.find(single_comment_symbol) == 0 or curr_content.find(single_comment_symbol + " ") != -1 or following_multi_comment:
                        if len(diff_edited) > 0:
                            if len(diff_edited[-1]["line_numbers"]) == 0 or curr_line == diff_edited[-1]["line_numbers"][-1] + 1:
                                diff_edited[-1]["comments"][curr_line] = curr_content
                        else:
                    # or create new one
                            diff_edited.append({
                                "line_numbers": [],
                                "comments": {curr_line: curr_content},
                                "lines": []})
                    # In case of no comment add lines to existing dict if line number directly follows
                    else:    
                        if len(diff_edited) > 0:
                            if len(diff_edited[-1]["line_numbers"]) == 0 or curr_line == diff_edited[-1]["line_numbers"][-1] + 1:
                                diff_edited[-1]["line_numbers"].append(curr_line)
                                diff_edited[-1]["lines"].append(curr_content)
                            else:
                    # Or create new one
                                diff_edited.append({
                                    "line_numbers": [curr_line],
                                    "comments": {},
                                    "lines": [curr_content]})
                    # Disable multiline comments when symbol found
                    if multi_comments_enabled and curr_content.find(multi_comment_symbols[1]) != -1:
                        following_multi_comment = False
                commit["diff"][type] = diff_edited
    return commits_data

def analyze_diffs(data):
    analysis_results = []

    for file, commits in data.items():
        # Store last modified timestamps for each line
        last_modified = {}
        for commit in commits:
            # print("Starting to analyse commit: ", commit["commit"])
            commit_time = datetime.fromisoformat(commit["timestamp"])
            # Track modified lines
            for block in commit["diff"]["added"]:
                for line in block["line_numbers"]:
                    line_number = line
                    last_modified[line_number] = commit_time
            # Compare with comments
            for line in commit["comment_added_diff"]:
                comment_time = datetime.fromisoformat(commit["timestamp"])
                last_modified_lines = list(last_modified.keys())
                if int(line) in last_modified_lines:
                    for block in commit["diff"]["added"]:
                        if line in block["comments"] and len(block["line_numbers"]) == 0:
                            if(comment_time > last_modified[int(line)]):
                                analysis_results.append({
                                    "file": file,
                                    "line": int(line),
                                    "comment": commit["comment_added_diff"][line],
                                    "comment_time": str(comment_time),
                                    "last_code_change_time": str(last_modified[int(line)])
                                })
    return analysis_results

def save_to_json(commits_data, path):
    # Save the processed commit data to a JSON file
    with open(path, 'w') as json_file:
        json.dump(commits_data, json_file, indent=4)
    print("Data has been saved to", path)

def create_xes_log(data):
    # Create a new EventLog object
    log = EventLog()

    # Iterate over each commit entry in the data
    for file, commits in data.items():
        # Create a trace for the file
        trace = Trace()
        trace.attributes["file"] = file

        for commit in commits:
            # Extract event attributes
            event = Event()
            event["timestamp"] = commit.get("timestamp")
            event["author"] = commit.get("author")
            event["change_type"] = commit.get("change_type")
            event["commit_message"] = commit.get("commit_message")
            event["additions"] = commit.get("additions")
            event["deletions"] = commit.get("deletions")
            event["diff"] = commit.get("diff")
            if commit.get("comment_added_diff"):
                event["comment_change"] = "True"
            else:
                event["comment_change"] = "False"

            # Add the event to the trace
            trace.append(event)

        # Add the trace to the log
        log.append(trace)

    return log

def save_xes_log(log, filename):
    # Export the log to an XES file
    xes_exporter.apply(log, filename)

def save_to_xes(log, path):
    # Create the XES log from the commit data
    xes_log = create_xes_log(log)

    # Save the XES log to a file
    save_xes_log(xes_log, path)
    print("XES log has been saved to", path)

if __name__ == "__main__":
    repo_url = "https://github.com/nodejs/node"  # Example repository URL
    commits_data = analyze_commits(repo_url, "js", datetime(2015,2,1), datetime(2015,8,1), "//", ["/*", "*/"])
    save_to_json(commits_data, "Data/commits_data.json")
    # save_to_xes(commits_data, "Data/commits_data.xes")
    with open("Data/commits_data.json", "r") as json_file:
       commits_data = json.load(json_file)
    analyzed_data = pretty_diff(commits_data, "added", "//", ["/*", "*/"])
    save_to_json(analyzed_data, "Exports/analyzed_data.json")
    analyzed_data = pretty_diff(commits_data, "deleted", "//", ["/*", "*/"])
    save_to_json(analyzed_data, "Exports/analyzed_data.json")
    
    # Test case
    with open("Exports/analyzed_data.json", "r") as json_file:
        data = json.load(json_file)
    analyzed_data = analyze_diffs(data)

    save_to_json(analyzed_data, "Exports/analysis_results.json")
