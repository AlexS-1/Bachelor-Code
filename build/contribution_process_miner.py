from ast import Dict
from os import read
from pdb import pm
import re
from git import Optional
import pandas as pd
import pm4py
from build.code_quality_visualizer import get_attribute_value
from build.database_handler import get_events_for_object, get_filtered_objects, get_is_user_bot, get_object, get_related_objectIds, get_related_objectIds_for_event
from build.utils import date_1970, rename_field
from build.database_handler import get_commits, get_event, get_ocel_data, get_object_type_by_type_name, get_type_of_object
from datetime import datetime
from pandas._typing import Timezone
import xml.etree.ElementTree as ET
from typing import Any, Iterable, cast
import typing

from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.log.obj import EventLog, EventStream
from pm4py.objects.log.exporter.xes import exporter as xes_exporter
from pm4py.objects.log.importer.xes import importer as xes_importer
from pm4py.algo.discovery.inductive import algorithm as inductive_miner
from pm4py.algo.discovery.dfg import algorithm as dfg_discovery
from pm4py.algo.filtering.log.timestamp.timestamp_filter import filter_traces_intersecting as filter_log
from pm4py.visualization.petri_net import visualizer as pn_visualizer
from pm4py.visualization.process_tree import visualizer as pt_visualizer
from pm4py.visualization.dfg import visualizer as dfg_visualizer
from pm4py import convert_to_petri_net
import pm4py

def filter_ocel_by_object_attributes(ocel, collection, criteria):
    filtered_OCEL = emptyOCEL()
    filtered_OCEL["eventTypes"] = ocel["eventTypes"]
    filtered_OCEL["objectTypes"] = ocel["objectTypes"]
    ocel_objects = {object["id"]: object for object in ocel.get("objects")}

    objectIds = set()

    objects = get_filtered_objects(criteria, collection)

    for object in objects:
        object_id = object["_id"]
        objectIds.add(object_id)
        events = get_events_for_object(object_id, collection)
        for event in events:
            object_ids = _get_local_related_objectIds_for(event)
            objectIds.update(object_ids)
            filtered_OCEL["events"].append(rename_field(event, "_id", "id"))
    for object_id in objectIds:
        object = ocel_objects.get(object_id)
        if object:
            filtered_OCEL["objects"].append(object)
            secondary_objectIds = _get_local_related_objectIds_for(object)
            for secondary_objectId in secondary_objectIds:
                if secondary_objectId not in objectIds:
                    secondary_object = ocel_objects.get(secondary_objectId)
                    if secondary_object:
                        filtered_OCEL["objects"].append(secondary_object)
                    else:
                        print(f"ERROR: Could not find secondary object: {secondary_objectId}")
        else:
            print(f"ERROR: Could not find object: {object_id}")
    return filtered_OCEL

def filter_ocel_by_timeframe(ocel, start_datetime, end_datetime):
    filtered_OCEL = emptyOCEL()
    filtered_OCEL["eventTypes"] = ocel["eventTypes"]
    filtered_OCEL["objectTypes"] = ocel["objectTypes"]
    objectIds = set()
    ocel_objects = {object["id"]: object for  object in ocel["objects"]}
    for event in ocel["events"]:
        if start_datetime < datetime.fromisoformat(event["time"]) < end_datetime:
            filtered_OCEL["events"].append(event)
            objects = _get_local_related_objectIds_for(event)
            objectIds.update(objects)
    for object_id in objectIds:
        object = ocel_objects.get(object_id)
        if object:
            filtered_OCEL["objects"].append(object)
            secondary_objectIds = _get_local_related_objectIds_for(object)
            for secondary_objectId in secondary_objectIds:
                if secondary_objectId not in objectIds:
                    secondary_object = ocel_objects.get(secondary_objectId)
                    if secondary_object:
                        filtered_OCEL["objects"].append(secondary_object)
                    else:
                        print(f"ERROR: Could not find secondary object: {secondary_objectId}")
        else:
            print(f"ERROR: Could not find object: {object_id}")
    return filtered_OCEL

def _get_local_related_objectIds_for(data) -> list[str]:
    """
    Get the local related objectIds for a specific event.
    """
    object_Ids = []
    for relationship in data["relationships"]:
        object_Ids.append(relationship["objectId"])
    return object_Ids

def _get_local_attribute(data, attribute_name: str) -> Optional[Any]:
    """
    Get the local attribute value for a specific event.
    """
    for attribute in data.get("attributes", []):
        if attribute.get("name") == attribute_name:
            return attribute["value"]
    return None

def _actor_from_event(event) -> Optional[str]:
    for rel in event.get("relationships", []):
        # your log uses qualifiers like "authored-by", "merged-by", "commented-by"
        if "by" in rel.get("qualifier", ""):
            return rel.get("objectId")
    return None

def get_open_pr_event_id(pr_id: str, collection: str) -> Optional[str]:
    """
    Get the event ID for the opening of a pull request.
    """
    events = get_events_for_object(pr_id, collection)
    for event in events:
        if event.get("type") == "open_pull_request":
            return event.get("_id")
    return None

def is_bot_user(actor_id: str, collection: str) -> bool:
    user = get_object(actor_id, collection)
    if not user:
        return False
    # check attributes list for is_bot-like flag
    for a in user.get("attributes", []) or []:
        name = str(a.get("name", "")).lower()
        if name == "is-bot" and a.get("value") == "True":
            return True
    return False

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
        related_object_ids = get_related_objectIds_for_event(event_id, "by", collection, True)
        bot = get_is_user_bot(related_object_ids[0], collection)
        # rank = get_attribute_value(related_object_ids[0], "rank" , collection)
        row = {
            "case:concept:name": object_id,
            "event_id": event_id,
            "concept:name": event.get("type"),
            "time:timestamp": event.get("time") + "Z",
            "is_bot": bot,
            **{k: v for k, v in event.items() if k not in ["id", "type", "time"]}
        }
        rows.append(row)
    
    # Build DataFrame and sort by case_id and timestamp
    df = pd.DataFrame(rows)
    export_path = f"Exports/{collection}-{object_type}-flattened.xes"
    if df is not None and rows != []:
        df["time:timestamp"] = pd.to_datetime(df["time:timestamp"], utc=True)
        df = df.sort_values(["case:concept:name", "time:timestamp"])
        event_log = log_converter.apply(df, variant=log_converter.Variants.TO_EVENT_LOG)
        xes_exporter.apply(event_log, export_path)
        return correct_XES_headers(export_path)

    print("ERROR flattening OCEL for export at: ", export_path)
    return None

def correct_XES_headers(export_path):
    # Correct XES Header for later processing using ProM
    ET.register_namespace('', "http://www.xes-standard.org/")
    tree = ET.parse(export_path)
    root = tree.getroot()
    root.set("xes.version","1.0")
    root.set("xes.features","")
    tree.write(export_path, encoding="utf-8", xml_declaration=False)
    # Now strip any leftover xmlns="..." the serializer may have kept
    with open(export_path, "r", encoding="utf-8") as f:
        txt = f.read()
    txt = re.sub(r'\s+xmlns="[^"]+"', "", txt, count=1)
    with open(export_path, "w", encoding="utf-8") as f:
        f.write(txt)
    return export_path


def visualise_xes_as(variant, import_path, collection):
    event_log = xes_importer.apply(import_path)

    if variant != "dfg":
        # Discover a process tree
        process_tree = inductive_miner.apply(event_log)
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

def divide_event_log_at(split_date: datetime, event_log_path: str):
    """
    Splits the XES log at a given date.
    
    Parameters
    -------------------
    date
        Date to split the log at
    event_log_path
        Event log to split

    Returns
    ------------------
    export_path_before
        Path to event log before the date
    export_path_after
        Path to event log after the date
    """

    raw_log = xes_importer.apply(event_log_path)
    event_log: EventLog = cast(EventLog, log_converter.apply(raw_log, variant=log_converter.Variants.TO_EVENT_LOG))


    start_date = datetime.min.replace(tzinfo=None)
    split_date = split_date.replace(tzinfo=None)
    end_date = datetime.today().replace(tzinfo=None)

    before = filter_log(event_log, start_date, split_date)
    after = filter_log(event_log, split_date, end_date)

    export_path_before = f"{event_log_path.split('.')[0]}-before.xes"
    export_path_after = f"{event_log_path.split('.')[0]}-after.xes"

    xes_exporter.apply(before, export_path_before)
    xes_exporter.apply(after, export_path_after)

    return export_path_before, export_path_after