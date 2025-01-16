from datetime import datetime, timedelta
from numpy import add, sort
import pandas as pd

def analyse_blocks(data):
    for _, commits in data.items():
        for commit in commits:
            for block in commit["source_code_blocks"]:
                activities = []
                old_parameters = []
                new_parameters = []
                old_method_name = ""
                new_method_name = ""
                if "def " in block["code_linesv4"][0]:
                    if "--" in block["code_linesv4"][0]:
                        old_part = block["code_linesv4"][0].split("--")[1]
                        old_method_name = block["code_linesv4"][0].split("def ")[1].split("(")[0]
                        old_parameters = block["code_linesv4"][0].split("(")[1].split(")")[0].split(",")
                        if "++" in block["code_linesv4"][0]:
                            new_part = block["code_linesv4"][0].split("++")[1]
                            if "def " in new_part:
                                new_method_name = new_part.split("def ")[1].split("(")[0]
                                new_parameters = new_part.split("(")[1].split(")")[0].split(", ")
                                for parameter in new_parameters:
                                    if "=" in parameter:
                                        new_parameters[new_parameters.index(parameter)] = parameter.split("=")[0]
                            old_part = block["code_linesv4"][0].split("--")[1].split("++")[0]
                            if "def " in old_part:
                                old_method_name = old_part.split("def ")[1].split("(")[0]
                                old_parameters = old_part.split("(")[1].split(")")[0].split(", ")
                                for parameter in old_parameters:
                                    if "=" in parameter:
                                        old_parameters[old_parameters.index(parameter)] = parameter.split("=")[0]
                    if new_method_name != old_method_name and len (old_method_name) > 0 and len(new_method_name) > 0 and len(old_parameters) == len(new_parameters):
                        activities.append("Method Renamed")
                    if len(old_parameters) < len(new_parameters):
                        activities.append("Method Parameter Added")
                    elif len(old_parameters) > len(new_parameters):
                        activities.append("Method Parameter Deleted")
                    elif (sort(old_parameters) == sort(new_parameters)).all() and old_parameters != new_parameters:
                        activities.append("Method Parameter Order Changed")
                    elif old_parameters != new_parameters:
                        activities.append("Method Parameter Renamed")
                    
                    deletions = []
                    additions = []
                    for line in block["code_linesv4"][1:]:
                        if "--" in line:
                            deletions.append(True)
                        if "++" in line:
                            additions.append(True)
                    
                    if len(deletions) == len(block["code_linesv4"][1:]) and not True in additions:
                        activities.append("Method Deleted")
                    elif len(additions) == len(block["code_linesv4"][1:]) and not True in deletions:
                        activities.append("Method Created")

                elif "import " in block["code_linesv4"][0]:
                    for line in block["code_linesv4"]:
                        if "--" in block["code_linesv4"][0]:
                            old_import = block["code_linesv4"][0].split("--")[1]
                            if "++" in block["code_linesv4"][0]:
                                new_import = block["code_linesv4"][0].split("++")[1]
                                if new_import != old_import:
                                    activities.append("Import Changed")
                
                else: 
                    if "comment_lines" in list(block.keys()):
                        added = False
                        modified = False
                        for _, comment_data in block["comment_lines"].items():
                            if comment_data["edit"] == "modified":
                                modified = True
                            elif comment_data["edit"] == "added":
                                added = True
                        if added:
                            activities.append("Comment Added")
                        if modified:
                            activities.append("Comment Modified")
                        # TODO Check if comment was deleted
                        
                block["activities"] = activities

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

def process_csv_and_create_event_log(input_csv, output_csv):
    # Step 1: Read the CSV file
    data = pd.read_csv(input_csv)
    
    # Step 2: Sort the data by method name and filename
    data_sorted = data.sort_values(by=["Method Name", "Filename"])

    # Step 3: Calculate differences and generate events
    event_log = []
    
    for i in range(len(data_sorted)):
        current_row = data_sorted.iloc[i]

        if len(current_row["Activities"][1:-1].split(", ")) > 1:
            for activity in current_row["Activities"][1:-1].split(", "):
                event_log.append({
                    "Case ID": current_row["Method Name"],
                    "Activity": activity,
                    "Timestamp": current_row["Timestamp"],
                    "Filename": current_row["Filename"],
                    "Author": current_row["Author"],
                })
        else:
            # Append the event to the log
            event_log.append({
                "Case ID": current_row["Method Name"],
                "Activity": current_row["Activities"][1:-1],
                "Timestamp": current_row["Timestamp"],
                "Filename": current_row["Filename"],
                "Author": current_row["Author"],
            })

    # Step 4: Convert event log to a DataFrame
    event_log_df = pd.DataFrame(event_log)

    # Step 5: Save the event log to a CSV file
    event_log_df.to_csv(output_csv, index=False)  