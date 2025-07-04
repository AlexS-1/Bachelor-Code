from build.utils import date_1970
from build.database_handler import get_commits, get_ocel_data
from datetime import datetime

def split_OCEL_at_guideline_changes(ocel, collection):
    # Update the current contribution guideline while going through the commits
    ocels = []
    prev_contribution_guideline_version = date_1970()
    for commit in get_commits(collection):
        if commit["attributes"][3]["value"] != prev_contribution_guideline_version:
            prev_contribution_guideline_version = commit["attributes"][3]["value"]
            split_datetime = datetime.fromisoformat(commit["attributes"][3]["value"])
            split_ocel, to_split_ocel = split_ocel_at(ocel, split_datetime)
            ocels.append(split_ocel)
            ocel = to_split_ocel
    return ocels

def split_ocel_at(ocel, split_datetime):
    ocel_before_split_datetime = emptyOCEL()
    ocel_after_split_datetime = emptyOCEL()
    for event in ocel["events"]:
        if event["time"] < split_datetime:
            ocel_before_split_datetime["events"].append(event)
        else:
            ocel_after_split_datetime["events"].append(event)
    ocel_before_split_datetime["objects"] = ocel["objects"]
    ocel_after_split_datetime["objects"] = ocel["objects"]
    
    ocel_before_split_datetime["objectTypes"] = ocel["objectTypes"]
    ocel_after_split_datetime["objectTypes"] = ocel["objectTypes"]
    
    ocel_before_split_datetime["eventTypes"] = ocel["eventTypes"]
    ocel_after_split_datetime["eventTypes"] = ocel["eventTypes"]
    return ocel_before_split_datetime, ocel_after_split_datetime

def emptyOCEL():
    return {
        "objectTypes": [],
        "eventTypes": [],
        "objects": [],
        "events": []
    }