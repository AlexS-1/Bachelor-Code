from datetime import datetime, timedelta
import pandas as pd

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

def process_csv_and_create_event_log(input_csv, output_csv):
    # Step 1: Read the CSV file
    data = pd.read_csv(input_csv)
    
    # Step 2: Sort the data by method name and filename
    data_sorted = data.sort_values(by=["Method Name", "Filename"])

    # Step 3: Calculate differences and generate events
    event_log = []
    
    for i in range(len(data_sorted) - 1):
        current_row = data_sorted.iloc[i]
        next_row = data_sorted.iloc[i + 1]

        # Check if the method and file are the same
        if current_row["Method Name"] == next_row["Method Name"] and current_row["Filename"] == next_row["Filename"]:
            # Compare fields to determine the type of change
            if current_row["Code Lines"] != next_row["Code Lines"]:
                event_type = "Method Modified"
            else:
                continue
        else:
            event_type = "Method Added"

        # Append the event to the log
        event_log.append({
            "Case ID": current_row["Method Name"],
            "Activity": event_type,
            "Timestamp": current_row["Timestamp"],
            "Filename": current_row["Filename"],
            "Details": f"Change from {current_row['Code Line Count']} to {next_row['Code Line Count']} LOC"
        })

    # Step 4: Convert event log to a DataFrame
    event_log_df = pd.DataFrame(event_log)

    # Step 5: Save the event log to a CSV file
    event_log_df.to_csv(output_csv, index=False)


  