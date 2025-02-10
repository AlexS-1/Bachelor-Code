from isort import file
from numpy import insert
import pymongo
from ulid import T

from build.utils import generic_to_python_type

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["mydatabase"]
ocdb = myclient["ocel"]

### Insert functions # TODO Unify insert functions as lots of similar functionality
def insert_commit(data):
    commit_type = get_type("commit")
    try: 
        verify_type(data, commit_type)
        data_to_insert = {k: v for k, v in data.items() if k != "commit_sha"}
    except ValueError as e:
        raise ValueError(f"Data does not match the commit type: {e}")
    insert_object(data["commit_sha"], "commit", data_to_insert)

def insert_repo(data):
    repository_type = get_type("repository")
    try:
        verify_type(data, repository_type)
        data_to_insert = {k: v for k, v in data.items() if k != "utility_information"}
    except ValueError as e:
        raise ValueError(f"Data does not match the repository type: {e}")
    insert_object(data["owner"] + "/" + data["name"], "repository", data_to_insert) # TODO Double check correct format of repo id

def insert_pull(data):
    pull_request_type = get_type("pull_request")
    try:
        verify_type(data, pull_request_type)
        data_to_insert = {k: v for k, v in data.items() if k != "number"}
    except ValueError as e: 
        raise ValueError(f"Data does not match the pull request type: {e}")
    insert_object(data["number"], "pull_request", data_to_insert)

def insert_issue(data):
    issue_type = get_type("issue") 
    try:
        verify_type(data, issue_type)
        data_to_insert = {k: v for k, v in data.items() if k != "number"} 
    except ValueError as e:
        raise ValueError(f"Data does not match the issue type {e}")
    insert_object(data["number"], "issue", data_to_insert)

def insert_comment(data):
    comment_type = get_type("comment")
    try:
        verify_type(data, comment_type)
        data_to_insert = data
    except ValueError as e:
        raise ValueError(f"Data does not match the comment type: {e}")
    insert_object(data["author"] + "/" + str(data["timestamp"]), "comment", data_to_insert)

def insert_review(data):
    review_type = get_type("review")
    try:
        verify_type(data, review_type)
        data_to_insert = data
    except ValueError as e:
        raise ValueError(f"Data does not match the review type: {e}")
    insert_object(data["author"] + "/" + str(data["timestamp"]), "review", data_to_insert)

def insert_test_run(data):
    test_run_type = get_type("test_run")
    try:
        verify_type(data, test_run_type)
        data_to_insert = data
    except ValueError as e:
        raise ValueError(f"Data does not match the test run type: {e}")
    insert_object(data["pull_request"] + "/" + str(data["timestamp"]), "test_run", data_to_insert)

def insert_file_change(data):
    file_change_type = get_type("file_change")
    try:
        verify_type(data, file_change_type)
        data_to_insert = data
    except ValueError as e:
        raise ValueError("Data does not match the file change type: {e}")
    insert_object("/".join([data["changed_by"], data["filename"], str(data["file_change_timestamp"])]), "file_change", data_to_insert)

def insert_user(data):
    user_type = get_type("user")
    try:
        verify_type(data, user_type)
        data_to_insert = {k: v for k, v in data.items() if k != "name"}
    except ValueError as e:
        raise ValueError(f"Data does not match the user type: {e}")
    insert_object(data["name"], "user", data_to_insert)

### Generic insert functions
def insert_eventType(name, attributes):
    ocdb["eventTypes"].replace_one({"_id": name}, {"attributes": attributes}, True)

def insert_objectType(name, attributes):
    ocdb["objectTypes"].replace_one({"_id": name}, {"attributes": attributes}, True)

def insert_event(id, type, time, attributes, relationships=[]):
    ocdb["events"].replace_one({"_id": id}, {"type": type, "time": time, "attributes": attributes, "relationships": relationships}, True)

def insert_object(id, type, attributes=[], relationships=[]):
    if not attributes and not relationships:
        ocdb["objects"].replace_one({"_id": id}, {"type": type}, True)
    elif not relationships:
        ocdb["objects"].replace_one({"_id": id}, {"type": type, "attributes": attributes}, True)
    elif not attributes:
        ocdb["objects"].replace_one({"_id": id}, {"type": type, "relationships": relationships}, True)
    else:
        ocdb["objects"].replace_one({"_id": id}, {"type": type, "attributes": attributes}, True)

### Get functions
def get_commits():
    return ocdb["objects"].find({"type": "commit"})

def get_type(name):
    return ocdb["objectTypes"].find_one({"_id": name})

### Initialisation functions
def initialise_database():
    issue_type = {
        "name": "issue", 
        "attributes": [
            {"name": "author", "type": "string"}, 
            {"name": "title", "type": "string"}, 
            {"name": "description", "type": "string"}, 
            {"name": "number", "type": "int"}, 
            {"name": "repository", "type": "string"}, 
            {"name": "created_at_timestamp", "type": "time" }, 
            {"name": "closed_at_timestamp", "type": "time"}, 
            {"name": "type", "type": "string"},
            {"name": "assignees", "type": "string"}, 
            {"name": "comments", "type": "string"}
        ]
    }
    insert_objectType(issue_type["name"], issue_type["attributes"])
    repository_type = {
        "name": "repository",
        "attributes": [
            {"name": "owner", "type": "string"},
            {"name": "name", "type": "string"},
            {"name": "pull_requests", "type": "string"},
            {"name": "issues", "type": "string"},
            {"name": "commits", "type": "string"},
            {"name": "branches", "type": "string"}
        ]
    }
    insert_objectType(repository_type["name"], repository_type["attributes"])
    user_type = {
        "name": "user",
        "attributes": [
            {"name": "name", "type": "string"},
            {"name": "username", "type": "string"},
            {"name": "email", "type": "string"},
            {"name": "rank", "type": "string"},
            {"name": "bot", "type": "bool"}
        ]
    }
    insert_objectType(user_type["name"], user_type["attributes"])
    comment_type = {
        "name": "comment",
        "attributes": [
            {"name": "message", "type": "string"},
            {"name": "timestamp", "type": "time"},
            {"name": "author", "type": "string"}
        ]
    }
    insert_objectType(comment_type["name"], comment_type["attributes"])
    commit_type = {
        "name": "commit",
        "attributes": [
            {"name": "commit_sha", "type": "string"},
            {"name": "author", "type": "string"},
            {"name": "title", "type": "string"},
            {"name": "repository", "type": "string"},
            {"name": "branch", "type": "string"},
            {"name": "commit_timestamp", "type": "time"},
            {"name": "message", "type": "string"},
            {"name": "file_changes", "type": "string"},
            {"name": "parents", "type": "string"}
        ]
    }
    insert_objectType(commit_type["name"], commit_type["attributes"])
    pull_request_type = {
        "name": "pull_request",
        "attributes": [
            {"name": "number", "type": "int"},
            {"name": "merge_commit_sha", "type": "string"},
            {"name": "author", "type": "string"},
            {"name": "title", "type": "string"},
            {"name": "description", "type": "string"},
            {"name": "merged_at_timestamp", "type": "time"},
            {"name": "closed_at_timestamp", "type": "time"},
            {"name": "created_at_timestamp", "type": "time"},
            {"name": "branch_to_pull_from", "type": "string"},
            {"name": "origin_branch", "type": "string"},
            {"name": "closing_issues", "type": "string"},
            {"name": "participants", "type": "string"},
            {"name": "reviewers", "type": "string"},
            {"name": "comments", "type": "string"},
            {"name": "commits", "type": "string"},
            {"name": "file_changes", "type": "string"},
            {"name": "test_runs", "type": "string"}
        ]
    }
    insert_objectType(pull_request_type["name"], pull_request_type["attributes"])
    file_change_type = {
        "name": "file_change",
        "attributes": [
            {"name": "changed_by", "type": "string"},
            {"name": "filename", "type": "string"},
            {"name": "language_popularity", "type": "string"},
            {"name": "typed", "type": "bool"},
            {"name": "file_change_timestamp", "type": "time"},
            {"name": "additions", "type": "string"},
            {"name": "deletions", "type": "string"}
        ]
    }
    insert_objectType(file_change_type["name"], file_change_type["attributes"])
    review_type = {
        "name": "review",
        "attributes": [
            {"name": "author", "type": "string"},
            {"name": "timestamp", "type": "time"},
            {"name": "referenced_code", "type": "string"},
            {"name": "approved", "type": "bool"},
            {"name": "comments", "type": "string"}
        ]
    }
    insert_objectType(review_type["name"], review_type["attributes"])
    test_run_type = {
        "name": "test_run",
        "attributes": [
            {"name": "passed", "type": "string"},
            {"name": "name", "type": "string"},
            {"name": "timestamp", "type": "time"},
            {"name": "pull_request", "type": "int"}
        ]
    }
    insert_objectType(test_run_type["name"], test_run_type["attributes"])

def verify_type(data, obj_type):
    for attribute in obj_type["attributes"]:
        if attribute["name"] not in list(data.keys()): 
            if type(data[attribute["name"]]) and generic_to_python_type(attribute["type"] is type(data[attribute["name"]])):
                raise ValueError(f"Attribute {attribute["name"]} not in {list(data.keys())} or {generic_to_python_type(attribute["type"])} is not of type {type(data[attribute["name"]])})")
            else: 
                raise ValueError(f"Attribute {attribute["name"]} not in {list(data.keys())})")