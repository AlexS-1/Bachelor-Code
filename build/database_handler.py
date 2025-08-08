from datetime import datetime
from os import path
from flask.cli import F
import pymongo

from build.utils import date_1970, generic_to_python_type, rename_field, write_json, write_to_file

myclient = pymongo.MongoClient("mongodb://localhost:27017/")

### Insert object-type functions
def insert_commit(data, collection):
    commit_type = get_object_type_by_type_name("commit", collection)
    try: 
        verify_objectType(data, commit_type)
        data_to_insert = {k: v for k, v in data.items() if k != "commit_sha"}
    except ValueError as e:
        raise ValueError(f"Data does not match the commit type: {e}")
    insert_object(data["commit_sha"], "commit", data_to_insert, collection)

def insert_pull(data, collection):
    pull_request_type = get_object_type_by_type_name("pull_request", collection)
    try:
        verify_objectType(data, pull_request_type)
        data_to_insert = {k: v for k, v in data.items() if k != "number"}
    except ValueError as e: 
        raise ValueError(f"Data does not match the pull request type: {e}")
    insert_object(data["number"], "pull_request", data_to_insert, collection)

def insert_file(data, collection):
    file_type = get_object_type_by_type_name("file", collection)
    try:
        verify_objectType(data, file_type)
        data_to_insert = data
    except ValueError as e:
        raise ValueError("Data does not match the file change type: {e}")
    insert_object(data["filename"], "file", data_to_insert, collection)

def insert_user(data, collection):
    user_type = get_object_type_by_type_name("user", collection)
    try:
        verify_objectType(data, user_type)
        data_to_insert = data
    except ValueError as e:
        raise ValueError(f"Data does not match the user type: {e}")
    insert_object(data["name"], "user", data_to_insert, collection)

### TODO Make inserting events and objects consistent

### Generic insert functions
def insert_eventType(name, attributes, collection):
    ocdb = myclient[f"{collection}"]
    ocdb["eventTypes"].replace_one({"_id": name}, {"attributes": attributes}, True)

def insert_objectType(name, attributes, collection):
    ocdb = myclient[f"{collection}"]
    ocdb["objectTypes"].replace_one({"_id": name}, {"attributes": attributes}, True)

def insert_event(id, event_type: str, time, collection, attributes=[], relationships=[]):
    ocdb = myclient[f"{collection}"]
    ocdb["events"].replace_one({"_id": id}, {"type": event_type, "time": time, "attributes": attributes, "relationships": relationships}, True)

def insert_object(id, object_type: str, data: dict, collection: str):
    ocdb = myclient[f"{collection}"]
    attribute_keys = [attribute_key["name"] for attribute_key in list(get_object_type_by_type_name(object_type, collection)["attributes"])] # type: ignore
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

def insert_ocel_object(object, collection: str):
    """
    Insert an object into the OCEL database.
    Args:
        object (dict): The object to insert, must contain 'id', 'type', 'attributes', and 'relationships'.
        collection (str): The collection to insert the object into.
    """
    ocdb = myclient[f"{collection}"]
    ocdb["objects"].replace_one({"_id": object["id"]}, {k: v for k, v in object.items() if k != "id"}, True)

def insert_ocel_event(event, collection: str):
    """
    Insert an event into the OCEL database.
    Args:
        event (dict): The event to insert, must contain 'id', 'type', 'attributes', and 'relationships'.
        collection (str): The collection to insert the event into.
    """
    ocdb = myclient[f"{collection}"]
    ocdb["events"].replace_one({"_id": event["id"]}, {k: v for k, v in event.items() if k != "id"}, True)


### Get functions
def get_commits(collection: str):
    ocdb = myclient[f"{collection}"]
    return ocdb["objects"].find({"type": "commit"})

def get_files(collection: str):
    ocdb = myclient[f"{collection}"]
    return ocdb["objects"].find({"type": "file"})

def get_pull_requests(collection: str):
    ocdb = myclient[f"{collection}"]
    return ocdb["objects"].find({"type": "pull_request"})

def get_object_type_by_type_name(type: str, collection: str):
    ocdb = myclient[f"{collection}"]
    object = ocdb["objectTypes"].find_one({"_id": type})
    return object

def get_type_of_object(object_id: str, collection: str):
    ocdb = myclient[f"{collection}"]
    object = ocdb["objects"].find_one({"_id": object_id})
    if object:
        return object.get("type")
    print(f"ERROR: No object found for id: {object_id}")
    return None

def get_events_for_eventType(type: str, collection: str):
    ocdb = myclient[f"{collection}"]
    return ocdb["events"].find({"type": type})

def get_events_for_object(object_id: str, collection: str):
    """
    Get all events related to a specific object by its ID.
    Args:
        object_id (str): The ID of the object to get events for.
        collection (str): The collection to search in.
    Returns:
        list: A list of events related to the specified object.
    """
    ocdb = myclient[f"{collection}"]
    return ocdb["events"].find({"relationships.objectId": object_id})

def get_object(object_id: str, collection: str):
    """
    Get an object from the database by its ID.
    Args:
        id (str): The ID of the object to retrieve.
        collection (str): The collection to get the objec from.
    Returns:
        dict: The object data if found, otherwise None.
    """
    ocdb = myclient[f"{collection}"]
    return ocdb["objects"].find_one({"_id": object_id})

def get_event(event_id: str, collection: str):
    """
    Get an event from the database by its ID.
    Args:
        id (str): The ID of the event to retrieve.
        collection (str): The collection to get the objec from
    Returns:
        dict: The event data if found, otherwise None.
    """
    ocdb = myclient[f"{collection}"]
    return ocdb["events"].find({"_id": event_id}) 

def get_ocel_data(collection: str):
    ocdb = myclient[f"{collection}"]
    data = {
        "objectTypes": [rename_field(doc, "_id", "name") for doc in ocdb["objectTypes"].find()],
        "eventTypes": [rename_field(doc, "_id", "name") for doc in ocdb["eventTypes"].find()],
        "objects": [rename_field(doc, "_id", "id") for doc in ocdb["objects"].find()],
        "events": [rename_field(doc, "_id", "id") for doc in ocdb["events"].find()]
    }
    # Return data as JSON
    path = f"Exports/{collection}-OCEL.json"
    
    write_json(path, data)
    return path

def get_user_by_username(username: str, collection: str):
    """
    Get a user from the database by their username.
    Args:
        username (str): The username of the user to retrieve.
        collection (str): The collection to search in.
    Returns:
        dict: The user data if found, otherwise None.
    """
    ocdb = myclient[f"{collection}"]
    return ocdb["objects"].find_one({"type": "user", "attributes.0.value": username})

def get_attribute_value_at_time(id, attribute_name, time, collection):
    """
    Get the value of an attribute at a specific time.
    Args:
        id (str): The ID of the object to get the attribute value for.
        attribute_name (str): The name of the attribute to get the value for.
        time (datetime): The time to get the attribute value at.
    Returns:
        str: The value of the attribute at the specified time, or None if not found.
    """
    file = get_object(id, collection)
    time = datetime.fromisoformat(time).replace(tzinfo=None)
    attributes = {}
    if file is None:
        return None
    for attribute in file["attributes"]:
        attr_time = datetime.fromisoformat(attribute["time"]).replace(tzinfo=None)
        if attribute["name"] == attribute_name and attr_time <= time:
            # Convert string to designated attribute_type
            object_type = get_object_type_by_type_name(file["type"], collection)
            if object_type is not None:
                attribute_type = next((attr["type"] for attr in object_type["attributes"] if attr["name"] == attribute_name), None)
                if attribute_type == "int":
                    attributes[attr_time] = int(attribute["value"])
                if attribute_type == "float":
                    attributes[attr_time] = float(attribute["value"])
                if attribute_type == "boolean":
                    attributes[attr_time] = True if attribute["value"] == "True" else False
        else:
            print("ERROR: No suitable object type for requested id")
    return attributes.get(max(attributes.keys(), default=None), None) if attributes else None


    return None

def get_attribute_value(id, attribute_name, collection):
    """
    Get the (first) value of an object attribute.
    Args:
        id (str): The ID of the object to get the attribute value for.
        attribute_name (str): The name of the attribute to get the value for.
        collection (str): The collection to get the object from.
    Returns:
        str: The value of the attribute, or None if not found.
    """
    file = get_object(id, collection)
    if file is None:
        return None
    for attribute in file["attributes"]:
        if attribute["name"] == attribute_name:
            return attribute["value"]
    return None

def get_related_objectIds(id, qualifier, collection):
    """
    Get the related objects of an object based on a qualifier.
    Args:
        id (str): The ID of the file to get the related objects for.
        qualifier (str): The qualifier to filter the related objects by.
    Returns:
        list: A list of related object IDs.
    """
    object = get_object(id, collection)
    related_objects = []
    if object is None:
        return related_objects
    for relation in object["relationships"]:
        if relation["qualifier"] == qualifier:
            related_objects.append(relation["objectId"])
    return related_objects 

def get_attribute_change_times(id, collection):
    """
    Get the timestamps when an attribute value changed
    Args:
        id (str): The ID of the object to get the attribute times for.
        collection (str): The collection to get the object from.
    Returns:
        list: A list of timestamps when the attribute value changed.
    """
    try:
        file = get_object(id, collection)
    except Exception as e:
        print(f"Error retrieving object with ID {id} from collection {collection}: {e}")
        return []
    
    if not file or "attributes" not in file:
        print(f"No attributes found for object with ID {id} in collection {collection}")
        return []
    
    attribute_times = set()
    for attribute in file["attributes"]:
        if "time" in attribute:
            attribute_times.add(attribute["time"])
    return list(attribute_times)

def get_attribute_time(id, attribute_name, collection):
    """
    Get the timestamp of an object attribute.
    Args:
        id (str): The ID of the object to get the attribute time for.
        attribute_name (str): The name of the attribute to get the time for.
        collection (str): The collection to get the object from.
    Returns:
        str: The timestamp of the attribute, or None if not found.
    """
    file = get_object(id, collection)
    if file is None:
        return None
    for attribute in file["attributes"]:
        if attribute["name"] == attribute_name:
            return attribute["time"]

### Update functions
def update_attribute(id, attribute_name, new_value, time, collection):
    """
    Update the value of an attribute.

    The 'attributes' field is expected to be a list of dictionaries, 
    each with keys: 'name', 'value', and 'time', e.g.:
    [
        {"name": "attribute1", "value": "some_value", "time": "2024-06-01T12:00:00"},
        ...
    ]

    Args:
        id (str): The ID of the object to update.
        attribute_name (str): The name of the attribute to update.
        new_value (str): The new value to set for the attribute.
        time (str): The time when the attribute was updated.
        collection (str): The collection to update the object in.
    """ 
    ocdb = myclient[f"{collection}"]
    ocdb["objects"].update_one(
        {"_id": id},
        {"$push": {
            "attributes": {
                "name": attribute_name,
                "time": time,
                "value": new_value
            }
        }}
    )

### Initialisation functions
def initialise_database(repo_path):
    initialise_objectTypes(repo_path)
    initialise_eventTypes(repo_path)

def initialise_objectTypes(repo_path):
    collection = repo_path.split("/")[-1]
    user_type = {
        "name": "user",
        "attributes": [
            {"name": "username", "type": "string"},
            {"name": "rank", "type": "string"}, # TODO Find way to model rank
            {"name": "is-bot", "type": "boolean"}
        ]
    }
    insert_objectType(user_type["name"], user_type["attributes"], collection)
    
    commit_type = {
        "name": "commit",
        "attributes": [
            # {"name": "commit_sha", "type": "string"}, Removed as it is used as id
            {"name": "message", "type": "string"},
            {"name": "description", "type": "string"},
            {"name": "to", "type": "string"},
            {"name": "contribution_guideline_version", "type": "string"},
        ]
    }
    insert_objectType(commit_type["name"], commit_type["attributes"], collection)
    pull_request_type = {
        "name": "pull_request",
        "attributes": [
            {"name": "title", "type": "string"},
            {"name": "description", "type": "string"},
            {"name": "state", "type": "string"},
        ]
    }
    insert_objectType(pull_request_type["name"], pull_request_type["attributes"], collection)
    file_type = {
        "name": "file",
        "attributes": [
            {"name": "filename", "type": "string"},
            {"name": "cc", "type": "int"},
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
    insert_objectType(file_type["name"], file_type["attributes"], collection)

def initialise_eventTypes(repo_path):
    collection = repo_path.split("/")[-1]
    # File viewpoint
    commit_event = {
        "name": "commit",
        "attributes": []
    }
    insert_eventType(commit_event["name"], commit_event["attributes"], collection)
    change_file_event = {
        "name": "change_file",
        "attributes": []
    }
    # Pull request viewpoint
    insert_eventType(change_file_event["name"], change_file_event["attributes"], collection)
    reopen_pull_request_event = {
        "name": "rereopen_pull_request",
        "attributes": []
    }
    insert_eventType(reopen_pull_request_event["name"], reopen_pull_request_event["attributes"], collection)
    add_label_event = {
        "name": "add_label",
        "attributes": []
    }
    insert_eventType(add_label_event["name"], add_label_event["attributes"], collection)
    remove_label_event = {
        "name": "remove_label",
        "attributes": []
    }
    insert_eventType(remove_label_event["name"], remove_label_event["attributes"], collection)
    open_pull_request_event = {
        "name": "open_pull_request",
        "attributes": []
    }
    insert_eventType(open_pull_request_event["name"], open_pull_request_event["attributes"], collection)
    close_pull_request_event = {
        "name": "close_pull_request",
        "attributes": []
    }
    insert_eventType(close_pull_request_event["name"], close_pull_request_event["attributes"], collection)
    merge_pull_request_event = {
        "name": "merge_pull_request",
        "attributes": []
    }
    insert_eventType(merge_pull_request_event["name"], merge_pull_request_event["attributes"], collection)
    rename_pull_request_event = {
        "name": "rename_pull_request",
        "attributes": []
    }
    insert_eventType(rename_pull_request_event["name"], rename_pull_request_event["attributes"], collection)
    comment_pull_request_event = {
        "name": "comment_pull_request",
        "attributes": []
    }
    insert_eventType(comment_pull_request_event["name"], comment_pull_request_event["attributes"], collection)
    # Review viewpoint
    mark_ready_for_review_event = {
        "name": "mark_ready_for_review",
        "attributes": []
    }
    insert_eventType(mark_ready_for_review_event["name"], mark_ready_for_review_event["attributes"], collection)
    add_review_request_event = {
        "name": "add_review_request",
        "attributes": []
    }
    insert_eventType(add_review_request_event["name"], add_review_request_event["attributes"], collection)
    remove_review_request_event = {
        "name": "remove_review_request",
        "attributes": []
    }
    insert_eventType(remove_review_request_event["name"], remove_review_request_event["attributes"], collection)
    comment_review_event = {
        "name": "comment_review",
        "attributes": []
    }
    insert_eventType(comment_review_event["name"], comment_review_event["attributes"], collection)
    suggest_changes_as_review_event = {
        "name": "suggest_changes_as_review",
        "attributes": []
    }
    insert_eventType(suggest_changes_as_review_event["name"], suggest_changes_as_review_event["attributes"], collection)
    approve_review_event = {
        "name": "approve_review",
        "attributes": []
    }
    insert_eventType(approve_review_event["name"], approve_review_event["attributes"], collection)
    dismiss_review_event = {
        "name": "dismiss_review",
        "attributes": []
    }
    insert_eventType(dismiss_review_event["name"], dismiss_review_event["attributes"], collection)

def verify_objectType(data, obj_type):
    for attribute in obj_type["attributes"]:
        try:
            if attribute["name"] not in list(data.keys()): 
                if type(data[attribute["name"]]) and generic_to_python_type(attribute["type"] is type(data[attribute["name"]])):
                    raise ValueError(f"Attribute {attribute["name"]} not in {list(data.keys())} or {generic_to_python_type(attribute["type"])} is not of type {type(data[attribute["name"]])})")
                else: 
                    raise ValueError(f"Attribute {attribute["name"]} not in {list(data.keys())})")
        except Exception as e:
            raise ValueError(f"{e}: Data is {data}")
