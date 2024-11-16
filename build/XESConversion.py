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
    dt1 = datetime.datetime(2022, 10, 8, 17, 0, 0)
    dt2 = datetime.datetime(2023, 10, 8, 17, 59, 0)

    # Traverse through the commits in the repository
    # Only save commits, that contain at least one file of the format {language_file_extension}
    for commit in Repository(repo_url, 
    only_modifications_with_file_types=[f".{language_file_extension}"],
    since=dt1,
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
                    "diff": modified_file.diff
                }
                diff_added = {}
                diff_deleted = {}
                diff_modified = {}
                for line in modified_file.diff_parsed["added"]:
                    if line[1].find(comment_symbol) != -1:
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

def save_to_json(commits_data, filename):
    # Save the processed commit data to a JSON file
    with open(filename, 'w') as json_file:
        json.dump(commits_data, json_file, indent=4)

def create_xes_log(data):
    # Create a new EventLog object
    log = EventLog()

    # Iterate over each commit entry in the data
    for file in data:
        # For each file affected in the commit, create a trace
        for file_data in commit_data['files']:
            # Check if a trace for this file already exists, if not, create one
            trace_name = file_data['filename']
            trace = next((t for t in log if t.attributes.get("concept:name") == trace_name), None)
            
            if trace is None:
                trace = Trace()
                trace.attributes["concept:name"] = trace_name
                log.append(trace)

            # Create an event for the current commit affecting this file
            event = Event()
            event["concept:name"] = file_data['activity']
            event["time:timestamp"] = commit_data['timestamp']
            event["org:resource"] = commit_data['author']

            # Add custom attributes for the event
            event["additions"] = file_data['additions']
            event["deletions"] = file_data['deletions']
            event["change_type"] = file_data['change_type']
            event["commit_message"] = file_data['commit_message']
            #event["effect_keywords"] = ', '.join(file_data['effect_keywords'])
            event["diff"] = file_data["diff"]

            # Append the event to the trace
            trace.append(event)

    return log

def save_xes_log(log, filename):
    # Export the log to an XES file
    xes_exporter.apply(log, filename)

if __name__ == "__main__":
    repo_url = "https://github.com/numpy/numpy"  # Example repository URL
    # commits_data = analyze_commits(repo_url, "#", "py")
    # save_to_json(commits_data, "Data/commits_data.json")
    # print("Commit data has been saved to commits_data.json")
    # Load the previously saved commit data JSON file
    with open("Data/commits_data.json", "r") as json_file:
       commits_data = json.load(json_file)

    # Create the XES log from the commit data
    xes_log = create_xes_log(commits_data)

    # Save the XES log to a file
    save_xes_log(xes_log, "Data/commits_data.xes")
    print("XES log has been saved to commits_data.xes")
