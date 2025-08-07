import pandas as pd
import pm4py
from build.utils import date_1970
from build.database_handler import get_commits, get_ocel_data, get_object_type, get_type_of_object
from datetime import datetime, tzinfo, timezone

from pandas._typing import Timezone

from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.log.exporter.xes import exporter as xes_exporter
from pm4py.objects.log.importer.xes import importer as xes_importer
from pm4py.algo.discovery.inductive import algorithm as inductive_miner
from pm4py.algo.discovery.dfg import algorithm as dfg_discovery
from pm4py.visualization.petri_net import visualizer as pn_visualizer
from pm4py.visualization.process_tree import visualizer as pt_visualizer
from pm4py.visualization.dfg import visualizer as dfg_visualizer
from pm4py import convert_to_petri_net

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

def flatten_ocel2(ocel, object_type, collection):
    """
    Flattens the object-centric event log to a traditional event log with the choice of an object type.
    In the flattened log, the objects of a given object type are the cases, and each case
    contains the set of events related to the object.

    Parameters
    -------------------
    ocel
        Object-centric event log
    object_type
        Object type
    collection
        Name of the repository to search for
   
    Returns
    ------------------
    xes
        Flattened log in the form of a xes-type encoded JSON
    """
    event_map = {ev["id"]: ev for ev in ocel["events"]}
    
    # For each relation, if object_type matches, collect (object_id, event_id)
    case_event_pairs = []
    for event in ocel["events"]:
        for row in event["relationships"]:
            object_id = row["objectId"]
            event_id = event["id"]
            if get_type_of_object(object_id, collection) == object_type:
                case_event_pairs.append((object_id, event_id))

    # For each (object_id, event_id), build a row with case_id, activity, timestamp, event_id, etc.
    rows = []
    for object_id, event_id in case_event_pairs:
        event = event_map[event_id]
        row = {
            "case:concept:name": object_id,
            "event_id": event_id,
            "concept:name": event.get("type"),
            "time:timestamp": event.get("time") + "Z",
            **{k: v for k, v in event.items() if k not in ["id", "type", "time"]}
        }
        rows.append(row)
    
    # Build DataFrame and sort by case_id and timestamp
    df = pd.DataFrame(rows)
    print(df.columns)
    if df is not None:
        df["time:timestamp"] = pd.to_datetime(df["time:timestamp"], utc=True)
        df = df.sort_values(["case:concept:name", "time:timestamp"])
    return df

def visualise_xes_as(variant, event_log, collection):

    #flat_log = dataframe_utils.convert_timestamp_columns_in_df(flat_log)
    event_log = log_converter.apply(event_log, variant=log_converter.Variants.TO_EVENT_LOG)

    xes_exporter.apply(event_log, f"{collection}-PR-flattened.xes")

    event_log = xes_importer.apply(f"{collection}-PR-flattened.xes")

    if variant != "dfg":
        # Discover a process tree
        process_tree = inductive_miner.apply(event_log) # type: ignore
        if variant == "petri_net":
            net1, im1, fm1 = convert_to_petri_net(process_tree)
            gviz = pn_visualizer.apply(net1, im1, fm1)
            pn_visualizer.view(gviz) 
        else:
            gviz = pt_visualizer.apply(process_tree)
            pt_visualizer.view(gviz)
    else:
        dfg = dfg_discovery.apply(event_log)
        gviz = dfg_visualizer.apply(dfg)
        dfg_visualizer.view(gviz)

def divide_event_log_at(split_date: datetime, event_log: pd.DataFrame):
    """
    Splits the XES log at a given date.
    
    Parameters
    -------------------
    date
        Date to split the log at
    event_log
        Event log to split

    Returns
    ------------------
    traces_before
        Event log before the date
    traces_after
        Event log after the date
    """
    split_date = pd.to_datetime(split_date)
    event_log["time:timestamp"] = pd.to_datetime(event_log["time:timestamp"], utc=True)
    traces_before = []
    traces_after = []

    split_date = pd.to_datetime(split_date).tz_localize(None)
    event_log["time:timestamp"] = pd.to_datetime(event_log["time:timestamp"], utc=True)

    for _, trace_events in event_log.groupby("case:concept:name"):
        if (trace_events["time:timestamp"] < split_date).any():
            traces_before.append(trace_events)
        else:
            traces_after.append(trace_events)

    # Concatenate the traces back into DataFrames
    df_before = pd.concat(traces_before) if traces_before else pd.DataFrame(columns=event_log.columns)
    df_after = pd.concat(traces_after) if traces_after else pd.DataFrame(columns=event_log.columns)
    if traces_before == [] or traces_after == []:
        print("ERROR splitting log: split-date is not in range of event_log")
    return df_before, df_after