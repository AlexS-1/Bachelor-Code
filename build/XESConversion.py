from pydriller import Repository
import json
import pm4py
import datetime
from pm4py.objects.log.obj import EventLog, Trace, Event
from pm4py.objects.log.exporter.xes import exporter as xes_exporter

def analyze_commits(repo_url, comment_symbol, language_file_extension):
    # This will hold the data for each file and its changes across commits
    files_data = {}

    # Analysis range
    # dt1 = datetime.datetime(2022, 10, 8, 17, 0, 0)
    dt2 = datetime.datetime(2020, 10, 8, 17, 59, 0)

    # Traverse through the commits in the repository
    # Only save commits, that contain at least one file of the format {language_file_extension}
    for commit in Repository(repo_url, 
    only_modifications_with_file_types=[f".{language_file_extension}"],
    # since=dt1,
    to=dt2).traverse_commits():
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
                for line in modified_file.diff_parsed["added"]:
                    if line[1].find(comment_symbol) != -1:
                        print(int(line[0]))
                        diff_added[line[0]] = line[1]
                file_data["comment_added_diff"] = diff_added
                for line in modified_file.diff_parsed["deleted"]:
                    if line[1].find(comment_symbol) != -1:
                        diff_deleted[line[0]] = line[1]
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
    # This function can use NLP techniques or simple keyword extraction
    # Here, a simplified approach is used: basic keywords based on the commit message
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

def analyze_diff(commits_data, type):
    for file, commits in commits_data.items():
        if len(file) > 0:
            for commit in commits:
                diff_edited = []
                for i in range(len(commit["diff"][type])):
                    if commit["diff"][type][i][1].find("// ") == -1:
                        if len(diff_edited) > 0:
                            # In case of no comment add lines to existing dict if line number directly follows
                            if commit["diff"][type][i][0] == diff_edited[-1]["line_numbers"][-1] + 1:
                                diff_edited[-1]["line_numbers"].append(commit["diff"][type][i][0])
                                diff_edited[-1]["lines"].append(commit["diff"][type][i][1])
                            else:
                                # or create new one
                                diff_edited.append({
                                    "line_numbers": [commit["diff"][type][i][0]],
                                    "comments": [],
                                    "lines": [commit["diff"][type][i][1]]})
                    else:
                        if len(diff_edited) > 0:
                            # In case of comment add them to existing dict if they directly follow
                            if commit["diff"][type][i][0] == diff_edited[-1]["line_numbers"][-1] + 1:
                                diff_edited[-1]["line_numbers"].append(commit["diff"][type][i][0])
                                diff_edited[-1]["comments"].append(commit["diff"][type][i][1])
                        else:
                            # or create new one
                            diff_edited.append({
                                "line_numbers": [commit["diff"][type][i][0]],
                                "comments": [commit["diff"][type][i][1]],
                                "lines": []})
                commit["diff"][type] = diff_edited
    return commits_data

def save_to_json(commits_data, path):
    # Save the processed commit data to a JSON file
    with open(path, 'w') as json_file:
        json.dump(commits_data, json_file, indent=4)
    print("Commit data has been saved to ", path)

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
    print("XES log has been saved to ", path)

if __name__ == "__main__":
    repo_url = "https://github.com/espressif/arduino-esp32"  # Example repository URL
    commits_data = analyze_commits(repo_url, "// ", "cpp")
    save_to_json(commits_data, "Data/commits_data.json")
    # save_to_xes(commits_data, "Data/commits_data.xes")
    with open("Data/commits_data.json", "r") as json_file:
       commits_data = json.load(json_file)
    analyzed_data = analyze_diff(commits_data, "added")
    save_to_json(analyzed_data, "Exports/analyzed_data.json")
    analyzed_data = analyze_diff(commits_data, "deleted")
    save_to_json(analyzed_data, "Exports/analyzed_data.json")


