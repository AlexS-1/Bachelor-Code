from pydriller import Repository
import json
import pm4py
from pm4py.objects.log.obj import EventLog, Trace, Event
from pm4py.objects.log.exporter.xes import exporter as xes_exporter

def analyze_commits(repo_url):
    # This will hold the data for each file and its changes across commits
    commits_data = []

    # Traverse through the commits in the repository
    for commit in Repository(repo_url).traverse_commits():
        commit_data = {
            "timestamp": commit.committer_date.isoformat(),
            "author": commit.author.name,
            "files": []
        }

        # Analyze each file modified in the commit
        for modified_file in commit.modified_files:
            file_data = {
                "filename": modified_file.filename,
                "additions": modified_file.added_lines,
                "deletions": modified_file.deleted_lines,
                "change_type": modified_file.change_type.name,
                "commit_message": commit.msg
            }

            # Use commit message keywords to determine activity type
            if "bug" in commit.msg.lower() or "fix" in commit.msg.lower():
                file_data["activity"] = "Bug Fix"
            elif "feature" in commit.msg.lower() or "add" in commit.msg.lower():
                file_data["activity"] = "Feature Development"
            elif "refactor" in commit.msg.lower():
                file_data["activity"] = "Refactoring"
            else:
                file_data["activity"] = "Other"

            # Generate effect/meaning keywords based on the commit message and type of changes
            file_data["effect_keywords"] = extract_keywords(commit.msg, modified_file)

            commit_data["files"].append(file_data)

        # Store the processed commit data
        commits_data.append(commit_data)

    return commits_data

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

def save_to_json(commits_data, filename):
    # Save the processed commit data to a JSON file
    with open(filename, 'w') as json_file:
        json.dump(commits_data, json_file, indent=4)



def create_xes_log(commits_data):
    # Create a new EventLog object
    log = EventLog()

    # Iterate over each commit entry in the data
    for commit_data in commits_data:
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
            event["effect_keywords"] = ', '.join(file_data['effect_keywords'])

            # Append the event to the trace
            trace.append(event)

    return log

def save_xes_log(log, filename):
    # Export the log to an XES file
    xes_exporter.apply(log, filename)

if __name__ == "__main__":
    repo_url = "https://github.com/dani-garcia/vaultwarden"  # Example repository URL
    commits_data = analyze_commits(repo_url)
    save_to_json(commits_data, "commits_data.json")
    print("Commit data has been saved to commits_data.json")
     # Load the previously saved commit data JSON file
    with open("commits_data.json", "r") as json_file:
        commits_data = json.load(json_file)

    # Create the XES log from the commit data
    xes_log = create_xes_log(commits_data)

    # Save the XES log to a file
    save_xes_log(xes_log, "commits_data.xes")

    print("XES log has been saved to commits_data.xes")
