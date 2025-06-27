from datetime import datetime
from os import path
import pymongo

from build.utils import date_1970, generic_to_python_type, rename_field, write_json, write_to_file

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
ocdb = myclient["OCEL"]

### Insert object-type functions
def insert_commit(data):
    commit_type = get_type("commit")
    try: 
        verify_objectType(data, commit_type)
        data_to_insert = {k: v for k, v in data.items() if k != "commit_sha"}
    except ValueError as e:
        raise ValueError(f"Data does not match the commit type: {e}")
    insert_object(data["commit_sha"], "commit", data_to_insert)

def insert_pull(data):
    pull_request_type = get_type("pull_request")
    try:
        verify_objectType(data, pull_request_type)
        data_to_insert = {k: v for k, v in data.items() if k != "number"}
    except ValueError as e: 
        raise ValueError(f"Data does not match the pull request type: {e}")
    insert_object(data["number"], "pull_request", data_to_insert)

def insert_file(data):
    file_type = get_type("file")
    try:
        verify_objectType(data, file_type)
        data_to_insert = data
    except ValueError as e:
        raise ValueError("Data does not match the file change type: {e}")
    insert_object(data["filename"], "file", data_to_insert)

def insert_user(data):
    user_type = get_type("user")
    try:
        verify_objectType(data, user_type)
        data_to_insert = data
    except ValueError as e:
        raise ValueError(f"Data does not match the user type: {e}")
    insert_object(data["name"], "user", data_to_insert)

### TODO Make inserting events and objects consistent

### Generic insert functions
def insert_eventType(name, attributes):
    ocdb["eventTypes"].replace_one({"_id": name}, {"attributes": attributes}, True)

def insert_objectType(name, attributes):
    ocdb["objectTypes"].replace_one({"_id": name}, {"attributes": attributes}, True)

def insert_event(id, event_type: str, time, attributes=[], relationships=[]):
    ocdb["events"].replace_one({"_id": id}, {"type": event_type, "time": time, "attributes": attributes, "relationships": relationships}, True)

def insert_object(id, object_type: str, data: dict):
    attribute_keys = [attribute_key["name"] for attribute_key in list(get_type(object_type)["attributes"])] # type: ignore
    timestamp_keys = [key for key in list(data.keys()) if key.find("timestamp") != -1]
    relationship_keys = list(set(data.keys()) - set(attribute_keys) - set(timestamp_keys))
    attributes = []
    relationships = []

    # Check if the object already exists
    existing_object = ocdb["objects"].find_one({"_id": id})

    if not attribute_keys and not relationship_keys:
        # Replace object, as no times/relationships to update
        ocdb["objects"].replace_one({"_id": id}, {"type": object_type}, True)
        return

    if not existing_object:
        existing_attributes = []
        # If the object does not exist, create it
        if relationship_keys:
            for key in relationship_keys:
                if type(data[key]) == list:
                    for item in data[key]:
                        relationships.append({"objectId": str(item), "qualifier": key})
                elif type(data[key]) != list:
                    relationships.append({"objectId": str(data[key]), "qualifier": key})
            if not attribute_keys:
                ocdb["objects"].replace_one({"_id": id}, {"type": object_type, "relationships": relationships}, True)
                return
        if attribute_keys:
            for key in attribute_keys:
                attributes.append({
                    "name": key,
                    "value": str(data[key]),
                    "time": str(date_1970()) if not timestamp_keys else data[timestamp_keys[0]]
                })
            if not relationship_keys:
                ocdb["objects"].replace_one({"_id": id}, {"type": object_type, "attributes": attributes}, True)
                return
    else:
        # If the object exists, update it
        existing_attributes = existing_object.get("attributes", [])
        for key in attribute_keys:
            new_value = str(data[key])
            new_time = data[timestamp_keys[0]] if timestamp_keys else ""
            # Check if the attribute already exists with the same name and timestamp
            attribute_found = False
            for attribute_object in existing_attributes:
                if attribute_object["name"] == key:
                    if attribute_object["time"] == new_time:
                        # If an attribute with the same name and timestamp exists, skip adding it
                        attribute_found = True
                        break
                    elif attribute_object["value"] == new_value:
                        # If the value is the same but the timestamp is different, skip adding it
                        attribute_found = True
                        break
            if not attribute_found:
                # Add the new attribute only if it doesn't already exist with the same name and timestamp
                attributes.append({
                    "name": key,
                    "value": new_value,
                    "time": new_time
                })

        # Merge relationships if they exist
        if relationship_keys:
            for key in relationship_keys:
                if type(data[key]) == list:
                    for item in data[key]:
                        relationships.append({"objectId": str(item), "qualifier": key})
                elif type(data[key]) != list:
                    relationships.append({"objectId": str(data[key]), "qualifier": key})

    try:
        # Update the object in the database
        ocdb["objects"].replace_one(
            {"_id": id}, 
            {"type": object_type, "attributes": existing_attributes + attributes, "relationships": relationships}, 
            True
        )
    except (pymongo.errors.DocumentTooLarge, pymongo.errors.InvalidDocument) as e: # type: ignore
        print(e)


### Get functions
def get_commits():
    return ocdb["objects"].find({"type": "commit"})

def get_type(name: str):
    return ocdb["objectTypes"].find_one({"_id": name})

def get_events_for_type(type: str):
    return ocdb["events"].find({"type": type})

def get_object(id: str):
    """
    Get an object from the database by its ID.
    Args:
        id (str): The ID of the object to retrieve.
    Returns:
        dict: The object data if found, otherwise None.
    """
    return ocdb["objects"].find({"_id": id})

def get_event(id: str):
    """
    Get an event from the database by its ID.
    Args:
        id (str): The ID of the event to retrieve.
    Returns:
        dict: The event data if found, otherwise None.
    """
    return ocdb["events"].find({"_id": id})
    

def get_ocel_data():
    data = {
        "objectTypes": [rename_field(doc, "_id", "name") for doc in ocdb["ocel:objectTypes"].find()],
        "eventTypes": [rename_field(doc, "_id", "name") for doc in ocdb["ocel:eventTypes"].find()],
        "objects": [rename_field(doc, "_id", "id") for doc in ocdb["ocel:objects"].find()],
        "events": [rename_field(doc, "_id", "id") for doc in ocdb["ocel:events"].find()]
    }
    # Return data as JSON
    path = "Exports/OCEL-Data.json"
    
    write_to_file(path, str(data))
    return path

### Initialisation functions
def initialise_database():
    initialise_objectTypes()
    initialise_eventTypes()

def initialise_objectTypes():
    user_type = {
        "name": "user",
        "attributes": [
            {"name": "username", "type": "string"},
            {"name": "rank", "type": "string"}, # TODO Find way to model rank
            {"name": "is-bot", "type": "boolean"}
        ]
    }
    insert_objectType(user_type["name"], user_type["attributes"])
    
    commit_type = {
        "name": "commit",
        "attributes": [
            # {"name": "commit_sha", "type": "string"}, Removed as it is used as id
            {"name": "message", "type": "string"},
            {"name": "description", "type": "string"},
            {"name": "to", "type": "string"},
        ]
    }
    insert_objectType(commit_type["name"], commit_type["attributes"])
    pull_request_type = {
        "name": "pull_request",
        "attributes": [
            {"name": "title", "type": "string"},
            {"name": "description", "type": "string"},
            {"name": "state", "type": "string"},
        ]
    }
    insert_objectType(pull_request_type["name"], pull_request_type["attributes"])
    file_type = {
        "name": "file",
        "attributes": [
            {"name": "filename", "type": "string"}, # TODO Decide on use, then add to diagramm
            {"name": "method_count", "type": "int"},
            {"name": "theta_1", "type": "int"},
            {"name": "theta_2", "type": "int"},
            {"name": "N_1", "type": "int"},
            {"name": "N_2", "type": "int"},
            {"name": "loc", "type": "int"},
            {"name": "lloc", "type": "int"},
            {"name": "sloc", "type": "int"},
            {"name": "cloc", "type": "int"},
            {"name": "dloc", "type": "int"},
            {"name": "blank_lines", "type": "int"},
            {"name": "pylint_score", "type": "float"}
        ]
    }
    insert_objectType(file_type["name"], file_type["attributes"])

def initialise_eventTypes():
    # File viewpoint
    commit_event = {
        "name": "commit",
        "attributes": []
    }
    insert_eventType(commit_event["name"], commit_event["attributes"])
    change_file_event = {
        "name": "change_file",
        "attributes": []
    }
    # Pull request viewpoint
    insert_eventType(change_file_event["name"], change_file_event["attributes"])
    reopen_pull_request_event = {
        "name": "rereopen_pull_request",
        "attributes": []
    }
    insert_eventType(reopen_pull_request_event["name"], reopen_pull_request_event["attributes"])
    add_label_event = {
        "name": "add_label",
        "attributes": []
    }
    insert_eventType(add_label_event["name"], add_label_event["attributes"])
    remove_label_event = {
        "name": "remove_label",
        "attributes": []
    }
    insert_eventType(remove_label_event["name"], remove_label_event["attributes"])
    open_pull_request_event = {
        "name": "open_pull_request",
        "attributes": []
    }
    insert_eventType(open_pull_request_event["name"], open_pull_request_event["attributes"])
    close_pull_request_event = {
        "name": "close_pull_request",
        "attributes": []
    }
    insert_eventType(close_pull_request_event["name"], close_pull_request_event["attributes"])
    merge_pull_request_event = {
        "name": "merge_pull_request",
        "attributes": []
    }
    insert_eventType(merge_pull_request_event["name"], merge_pull_request_event["attributes"])
    rename_pull_request_event = {
        "name": "rename_pull_request",
        "attributes": []
    }
    insert_eventType(rename_pull_request_event["name"], rename_pull_request_event["attributes"])
    comment_pull_request_event = {
        "name": "comment_pull_request",
        "attributes": []
    }
    insert_eventType(comment_pull_request_event["name"], comment_pull_request_event["attributes"])
    # Review viewpoint
    mark_ready_for_review_event = {
        "name": "mark_ready_for_review",
        "attributes": []
    }
    insert_eventType(mark_ready_for_review_event["name"], mark_ready_for_review_event["attributes"])
    add_review_request_event = {
        "name": "add_review_request",
        "attributes": []
    }
    insert_eventType(add_review_request_event["name"], add_review_request_event["attributes"])
    remove_review_request_event = {
        "name": "remove_review_request",
        "attributes": []
    }
    insert_eventType(remove_review_request_event["name"], remove_review_request_event["attributes"])
    comment_review_event = {
        "name": "comment_review",
        "attributes": []
    }
    insert_eventType(comment_review_event["name"], comment_review_event["attributes"])
    suggest_changes_as_review_event = {
        "name": "suggest_changes_as_review",
        "attributes": []
    }
    insert_eventType(suggest_changes_as_review_event["name"], suggest_changes_as_review_event["attributes"])
    approve_review_event = {
        "name": "approve_review",
        "attributes": []
    }
    insert_eventType(approve_review_event["name"], approve_review_event["attributes"])
    dismiss_review_event = {
        "name": "dismiss_review",
        "attributes": []
    }
    insert_eventType(dismiss_review_event["name"], dismiss_review_event["attributes"])

def verify_objectType(data, obj_type):
    for attribute in obj_type["attributes"]:
        if attribute["name"] not in list(data.keys()): 
            if type(data[attribute["name"]]) and generic_to_python_type(attribute["type"] is type(data[attribute["name"]])):
                raise ValueError(f"Attribute {attribute["name"]} not in {list(data.keys())} or {generic_to_python_type(attribute["type"])} is not of type {type(data[attribute["name"]])})")
            else: 
                raise ValueError(f"Attribute {attribute["name"]} not in {list(data.keys())})")