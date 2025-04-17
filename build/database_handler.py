import pymongo

from build.utils import generic_to_python_type, rename_field

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["mydatabase"]
ocdb = myclient["ocel"]

### Insert functions
def insert_commit(data):
    commit_type = get_type("commit")
    try: 
        verify_objectType(data, commit_type)
        data_to_insert = {k: v for k, v in data.items() if k != "commit_sha"}
    except ValueError as e:
        raise ValueError(f"Data does not match the commit type: {e}")
    insert_object(data["commit_sha"], "commit", data_to_insert)

def insert_repo(data):
    repository_type = get_type("repository")
    try:
        verify_objectType(data, repository_type)
        data_to_insert = {k: v for k, v in data.items() if k != "utility_information" or k != "name"}
    except ValueError as e:
        raise ValueError(f"Data does not match the repository type: {e}")
    insert_object(data["name"], "repository", data_to_insert)

def insert_pull(data):
    pull_request_type = get_type("pull_request")
    try:
        verify_objectType(data, pull_request_type)
        data_to_insert = {k: v for k, v in data.items() if k != "number"}
    except ValueError as e: 
        raise ValueError(f"Data does not match the pull request type: {e}")
    insert_object(data["number"], "pull_request", data_to_insert)

def insert_issue(data):
    issue_type = get_type("issue")
    try:
        verify_objectType(data, issue_type)
        data_to_insert = {k: v for k, v in data.items() if k != "number"}
    except ValueError as e:
        raise ValueError(f"Data does not match the issue type: {e}")
    insert_object(data["number"], "issue", data_to_insert)

def insert_comment(data):
    comment_type = get_type("comment")
    try:
        verify_objectType(data, comment_type)
        data_to_insert = data
    except ValueError as e:
        raise ValueError(f"Data does not match the comment type: {e}")
    insert_object(data["comment-authored-by"] + "/" + str(data["timestamp"]), "comment", data_to_insert)

def insert_review(data):
    review_type = get_type("review")
    try:
        verify_objectType(data, review_type)
        data_to_insert = data
    except ValueError as e:
        raise ValueError(f"Data does not match the review type: {e}")
    insert_object(data["review-authored-by"] + "/" + str(data["timestamp"]), "review", data_to_insert)

def insert_test_run(data):
    test_run_type = get_type("test_run")
    try:
        verify_objectType(data, test_run_type)
        data_to_insert = {k: v for k, v in data.items() if k != "id"}
    except ValueError as e:
        raise ValueError(f"Data does not match the test run type: {e}")
    insert_object(data["id"], "test_run", data_to_insert)

def insert_file(data):
    file_type = get_type("file")
    try:
        verify_objectType(data, file_type)
        data_to_insert = data
    except ValueError as e:
        raise ValueError("Data does not match the file change type: {e}")
    insert_object("/".join([data["file-changed_by"], data["filename"], data["file_change_timestamp"]]), "file", data_to_insert)

def insert_user(data):
    user_type = get_type("user")
    try:
        verify_objectType(data, user_type)
        data_to_insert = data
    except ValueError as e:
        raise ValueError(f"Data does not match the user type: {e}")
    insert_object(data["name"], "user", data_to_insert)

def insert_method(data):
    pass
    # TODO Implement method insertion

### Generic insert functions
def insert_eventType(name, attributes):
    ocdb["eventTypes"].replace_one({"_id": name}, {"attributes": attributes}, True)

def insert_objectType(name, attributes):
    ocdb["objectTypes"].replace_one({"_id": name}, {"attributes": attributes}, True)

def insert_event(id, event_type: str, time, attributes=[], relationships=[]):
    ocdb["events"].replace_one({"_id": id}, {"type": event_type, "time": time, "attributes": attributes, "relationships": relationships}, True)

def insert_object(id, object_type: str, data: dict):
    attribute_keys = [attribute_key["name"] for attribute_key in list(get_type(object_type)["attributes"])]
    timestamp_keys = [key for key in list(data.keys()) if key.find("timestamp") != -1]
    relationship_keys = list(set(data.keys()) - set(attribute_keys) - set(timestamp_keys))
    attributes = []
    relationships = []
    if not attribute_keys and not relationship_keys:
        ocdb["objects"].replace_one({"_id": id}, {"type": object_type}, True)
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
            attributes.append({"name": key, "value": str(data[key]), "time": data[timestamp_keys[0]] if data[timestamp_keys[0]] else "" + str(data[timestamp_keys[1]])})
        if not relationship_keys:
            ocdb["objects"].replace_one({"_id": id}, {"type": object_type, "attributes": attributes}, True)
            return
    try:
        ocdb["objects"].replace_one({"_id": id}, {"type": object_type, "attributes": attributes, "relationships": relationships}, True)
    except (pymongo.errors.DocumentTooLarge, pymongo.errors.InvalidDocument) as e:
        print(e)


### Get functions
def get_commits():
    return ocdb["objects"].find({"type": "commit"})

def get_type(name: str) -> dict:
    return ocdb["objectTypes"].find_one({"_id": name})

def get_ocel_data():
    data = {
        "objectTypes": [rename_field(doc, "_id", "name") for doc in ocdb["objectTypes"].find()],
        "eventTypes": [rename_field(doc, "_id", "name") for doc in ocdb["eventTypes"].find()],
        "objects": [rename_field(doc, "_id", "id") for doc in ocdb["objects"].find()],
        "events": [rename_field(doc, "_id", "id") for doc in ocdb["events"].find()]
    }
    return data

### Initialisation functions
def initialise_database():
    initialise_objectTypes()
    initialise_eventTypes()

def initialise_objectTypes():
    # issue_type = {
    #     "name": "issue", 
    #     "attributes": [ 
    #         {"name": "title", "type": "string"}, 
    #         {"name": "description", "type": "string"}, 
    #         {"name": "type", "type": "string"} # TODO Decide on use e.g. from standard naming conventions, always used labels, NLP techniques on content or combination thereof
    #     ]
    #     # Relationships listed for later use when creating objects (with relationships)
    #     # "relationships": [
    #     #     {"objectId": "author", "qualifier": "authored-by"},
    #     #     {"objectId": "assignees", "qualifier": "assigned-to"},
    #     #     {"objectId": "comments", "qualifier": "has"},
    #     #     {"objectId": "repository", "qualifier": "comprises"}, 
    #     #     {"objectId": "pull_requests", "qualifier": "is-related-to"},
    #     # ]
    # }
    # insert_objectType(issue_type["name"], issue_type["attributes"])
    # repository_type = {
    #     "name": "repository",
    #     "attributes": [
    #         {"name": "name", "type": "string"}
    #     ]
    #     # Relationships listed for later use when creating objects (with relationships)
    #     # "relationships": [,
    #     #     {"objectId": "branches", "qualifier": "has"},
    #     #     {"objectId": "owner", "qualifier": "owned-by"},
    #     #     {"objectId": "commit", "qualifier": "includes"},
    #     #     {"objectId": "pull_requests", "qualifier": "string"},
    #     # ]
    # }
    # insert_objectType(repository_type["name"], repository_type["attributes"])
    user_type = {
        "name": "user",
        "attributes": [
            {"name": "username", "type": "string"},
            {"name": "rank", "type": "string"}, # TODO Find way to model rank
            {"name": "type", "type": "string"}
        ]
    }
    insert_objectType(user_type["name"], user_type["attributes"])
    # comment_type = {
    #     "name": "comment",
    #     "attributes": [
    #         {"name": "message", "type": "string"}
    #     ]
    #     # Relationships listed for later use when creating objects (with relationships)
    #     # "relationships": [
    #     #     {"objectId": "user", "qualifier": "commented-by"}
    #     # ]
    # }
    # insert_objectType(comment_type["name"], comment_type["attributes"])
    commit_type = {
        "name": "commit",
        "attributes": [
            # {"name": "commit_sha", "type": "string"}, Removed as it is used as id
            {"name": "message", "type": "string"},
            {"name": "description", "type": "string"},
            {"name": "to", "type": "string"},
        ]
        # Relationships listed for later use when creating objects (with relationships)
        # "relationships": [
        #     {"objectId": "user", "qualifier": "authored-by"},
        #     {"objectId": "user", "qualifier": "co-authored-by"},
        #     {"objectId": "file_change", "qualifier": "aggregates"},
        #     {"objectId": "repository", "qualifier": "commit-to"},
        #     {"objectId": "commit", "qualifier": "is-child-of"}, # TODO Discuss if this is necessary, can have relationship with multiple parents
        # ]
    }
    insert_objectType(commit_type["name"], commit_type["attributes"])
    pull_request_type = {
        "name": "pull_request",
        "attributes": [
            {"name": "title", "type": "string"},
            {"name": "description", "type": "string"},
            {"name": "state", "type": "string"},
        ]
        # Relationships listed for later use when creating objects (with relationships)
        # "relationships": [
        #     {"objectId": "user", "qualifier": "authored-by"},
        #     {"objectId": "file_change", "qualifier": "aggregates"},
        #     {"objectId": "commit", "qualifier": "formalises"},
        #     {"objectId": "user", "qualifier": "has-participant"},
        #     {"objectId": "user", "qualifier": "is-reviewd-by"},
        #     {"objectId": "comment", "qualifier": "has"},
        #     {"objectId": "test_run", "qualifier": "has"},
        #     {"objectId": "issue", "qualifier": "is-related-to"},
        #     {"objectId": "pull_request", "qualifier": "is-related-to"},
        #     {"objectId": "issue", "qualifier": "would-close"}, # TODO Define according to analysis goal
        #     {"objectId": "repository", "qualifier": "is-used-as-policy-in}
        #     {"objectId": "repository", "type": "head-branch-to-pull-from"},
        #     {"objectId": "repository", "type": "base-branch-to-pull-to"},
        # ]
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
        # Relationships listed for later use when creating objects (with relationships)
        # "relationships": [
        #     {"objectId": "commit", "qualifier": "part-of"},
        #     {"objectId": "user", "qualifier": "changed-by"},
        # ]
    }
    insert_objectType(file_type["name"], file_type["attributes"])
    method_tpye = {
        "name": "method",
        "attributes": [
            {"name": "cyclomatic_complexity", "type": "int"},
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
        # Relationships listed for later use when creating objects (with relationships)
        # "relationships": [
        #     {"objectId": "method", "qualifier": "calls-method"},
        #]
    }
    insert_objectType(method_tpye["name"], method_tpye["attributes"])
    label_type = {
        "name": "label",
        "attributes": [
        ]
    }
    insert_objectType(label_type["name"], label_type["attributes"])
    # review_type = {
    #     "name": "review",
    #     "attributes": [
    #         {"name": "referenced_code_line", "type": "string"},
    #         {"name": "approved", "type": "boolean"},
    #     ]
    #     # Relationships listed for later use when creating objects (with relationships)
    #     # "relationships": [
    #     #     {"objectId": "user", "qualifier": "authored-by"},
    #     #     {"objectId": "comment", "qualifier": "has"},
    #     #     {"objectId": "pull_request", "qualifier": "part-of"},
    #     # ]

    # }
    # insert_objectType(review_type["name"], review_type["attributes"])
    # test_run_type = {
    #     "name": "test_run",
    #     "attributes": [
    #         {"name": "name", "type": "string"},
    #         {"name": "passed", "type": "boolean"},
    #     ]
    #     # Relationships listed for later use when creating objects (with relationships)
    #     # "relationships": [
    #     #     {"objectId": "pull_request", "qualifier": "part-of"},
    #     # ]
    # }
    # insert_objectType(test_run_type["name"], test_run_type["attributes"])

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