import re
from git import Optional
import pandas as pd
from build.code_quality_visualizer import get_attribute_value
from build.database_handler import get_events_for_object, get_filtered_objects, get_is_user_bot, get_object, get_related_objectIds_for_event
from build.utils import rename_field
from build.database_handler import get_type_of_object
from datetime import datetime
from pandas._typing import Timezone
import xml.etree.ElementTree as ET
from typing import Any, cast

from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.log.obj import EventLog
from pm4py.objects.log.exporter.xes import exporter as xes_exporter

def filter_ocel_by_object_attributes(ocel, collection, criteria):
    filtered_OCEL = emptyOCEL()
    filtered_OCEL["eventTypes"] = ocel["eventTypes"]
    filtered_OCEL["objectTypes"] = ocel["objectTypes"]
    ocel_objects = {obj["id"]: obj for obj in ocel.get("objects")}

    objectIds = set()
    event_ids_seen: set[str] = set()
    object_ids_seen: set[str] = set()

    objects = get_filtered_objects(criteria, collection)

    for obj in objects:
        object_id = obj["_id"]
        objectIds.add(object_id)
        object_ids_seen.add(object_id)
        events = get_events_for_object(object_id, collection) or []
        for event in events:
            # Track related objects
            for oid in _get_local_related_objectIds_for(event):
                objectIds.add(oid)
                object_ids_seen.add(oid)
            # Deduplicate events by id in O(1)
            eid = event.get("_id")
            if eid and eid not in event_ids_seen:
                filtered_OCEL["events"].append(rename_field(event, "_id", "id"))
                event_ids_seen.add(eid)

    for object_id in objectIds:
        obj = ocel_objects.get(object_id)
        if not obj:
            print(f"ERROR: Could not find object: {object_id}")
            continue

        filtered_OCEL["objects"].append(obj)
        secondary_objectIds = _get_local_related_objectIds_for(obj)
        for secondary_objectId in secondary_objectIds:
            if secondary_objectId in object_ids_seen:
                continue
            sec_obj = ocel_objects.get(secondary_objectId)
            if not sec_obj:
                print(f"ERROR: Could not find secondary object: {secondary_objectId}")
                continue

            filtered_OCEL["objects"].append(sec_obj)
            object_ids_seen.add(secondary_objectId)

            filtered_events = get_events_for_object(secondary_objectId, collection) or []
            for event in filtered_events:
                eid = event.get("_id")
                if eid and eid not in event_ids_seen:
                    filtered_OCEL["events"].append(rename_field(event, "_id", "id"))
                    event_ids_seen.add(eid)
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
        bot = get_is_user_bot(related_object_ids[0], collection) if len(related_object_ids) > 0 else False
        issue_labels = str(get_attribute_value(object_id, "issue_label", collection)).lower()
        if "good first issue" in issue_labels:
            issue_label = "Good First Issue"
        elif "documentation" in issue_labels:
            issue_label = "Documentation"
        elif "build" in issue_labels or "CI" in issue_labels:
            issue_label = "CI"
        elif "enhancement" in issue_labels:
            issue_label = "enhancement"
        else:
            issue_label = "MISC"
        
        if "easy" in issue_labels or "good first issue" in issue_labels:
            difficulty = "Easy"
        elif "medium" in issue_labels:
            difficulty = "Medium"
        elif "hard" in issue_labels or "difficult" in issue_labels:
            difficulty = "Hard"
        else:
            difficulty = "MISC"
        # rank = get_attribute_value(related_object_ids[0], "rank" , collection)
        row = {
            "case:concept:name": object_id,
            "case:issue_label": issue_label,
            "case:difficulty": difficulty,
            "event_id": event_id,
            "concept:name": event.get("type"),
            "time:timestamp": event.get("time") + "Z",
            "is_bot": bot,
            # **{k: v for k, v in event.items() if k not in ["id", "type", "time"]}
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
    root.set("xes.version","2.0")
    root.set("xes.features","")
    tree.write(export_path, encoding="utf-8", xml_declaration=False)
    # Now strip any leftover xmlns="..." the serializer may have kept
    with open(export_path, "r", encoding="utf-8") as f:
        txt = f.read()
    txt = re.sub(r'\s+xmlns="[^"]+"', "", txt, count=1)
    with open(export_path, "w", encoding="utf-8") as f:
        f.write(txt)
    return export_path
