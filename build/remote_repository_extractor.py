from datetime import timedelta
from gc import collect
import time
from numpy import extract
import requests
import os

from build.database_handler import date_1970, datetime, insert_event, insert_pull, insert_user

token = os.getenv("GITHUB_TOKEN")  # Import GitHub token from environment variables
anonymous_user_counter = {}

def get_and_insert_remote_data(repo_url, repo_path, from_date, to_date):
    repo = get_repo_information(repo_url)
    collection = repo_url.split("/")[-1]
    get_closed_pulls(repo["utility_information"]["pulls_url"], from_date, to_date, collection)
    
def get_api_response(url, retries=0):
    headers = {"Authorization": f"token {token}"}
    response = requests.get(url, headers=headers)
    if response.ok:
        return response.json()
    elif response.status_code == 403 or response.status_code == 429 and retries < 5:
        if int(response.headers.get("x-ratelimit-remaining", 0)) == 0:
            retry_after = int(response.headers.get("x-ratelimit-reset", 60)) - int(time.time())
            retry_time = datetime.now() + timedelta(seconds=retry_after)
            print(f"Secondary rate limit exceeded. Retrying after {retry_after} seconds at {retry_time.strftime('%H:%M:%S')}.")
            retries += 1
        else:
            retry_after = int(response.headers.get("retry-after", 60))
            retry_time = datetime.now() + timedelta(seconds=retry_after)
            print(f"Secondary rate limit exceeded. Retrying after {retry_after} seconds at {retry_time.strftime('%H:%M:%S')}.")
            retries += 1
        time.sleep(retry_after^retries)
        return get_api_response(url, retries)
    else: 
        raise Exception(response.raise_for_status())

def get_repo_information(repo_url):
    repo_response = get_api_response(repo_url)
    repo_information = {
        "name": repo_response["full_name"],
        "has-pull_requests": get_related_pulls(repo_response["pulls_url"][:-9]),
        "has-commits": get_related_commits(repo_response["commits_url"][:-6]),
        "timestamp": repo_response["updated_at"],
        "utility_information": {
            "forks_url": repo_response["forks_url"],
            "forks_count": repo_response["forks"],
            "pulls_url": repo_response["pulls_url"][:-9],
            "issues_url": repo_response["issues_url"][:-9],
            "commits_url": repo_response["commits_url"][:-6],
            #TODO Check if it was modified and how to get data (e.g. rename of repository)
            "created_at": repo_response["created_at"], 
        }
    }
    return repo_information

def get_closed_pulls(pulls_url, from_date, to_date, collection):
    # TODO Check pulls for date range with link headers in pagination
    pages = 5
    for page in range(1, pages + 1):
        pull_response = get_api_response(pulls_url + "?state=closed&page=" + str(page))
        for pull in pull_response:
            pull_content = {
                "is-merged-with":  pull["merge_commit_sha"],
                "number": str(pull["number"]),
                "is-authored-by": get_name_by_username(pull["user"]["login"], collection, pull["author_association"]),
                "title": pull["title"],
                "description": pull["body"],
                "merged_at_timestamp": pull["merged_at"],
                "created_at_timestamp": pull["created_at"],
                "closed_at_timestamp": pull["closed_at"],
                "has-participant": 
                    [get_name_by_username(pull["user"]["login"], collection)] + 
                    [get_name_by_username(user["login"], collection) for user in pull["requested_reviewers"] + pull["requested_teams"] + pull["assignees"]],
                "is-reviewed-by": [get_name_by_username(user["login"], collection) for user in pull["requested_reviewers"] + pull["requested_teams"]], 
                "formalises": get_related_commits(pull["commits_url"]),
                "aggregates": get_related_files(pull["url"] + "/files"),
                # FIXME Extract correct state
                "state": pull["state"],
            } 
            insert_pull(pull_content, collection)
            extract_events_from_pull(pull_response, collection)

def extract_events_from_pull(pull_response, collection):
    for pull in pull_response:
        # Check PR events

        for event in get_api_response(pull["issue_url"] + "/timeline"):
            if event["event"] not in ["committed", "reviewed"]:
                timestamp = event["created_at"]
                actor = {"objectId": get_name_by_username(event["actor"]["login"], collection), "qualifier": "authored-by"}
            else:
                # TODO Check OCEL for those attributes
                timestamp = date_1970()
                actor = "Cincinnatus"
            # Handle specific events from OCEL-Diagrams.drawio
            if event["event"] == "committed":
                # TOOD Define timestamp correctly: timestamp = event["author"]["date"]
                committer = {"objectId": event["committer"]["name"], "qualifier": "authored-by"}
                commit = {"objectId": event["sha"], "qualifier": "sha"}
                insert_event(
                    f"{event['node_id']}",
                    "commit",
                    event["committer"]["date"], 
                    collection, 
                    [],
                    [committer, commit, {"objectId": str(pull['number']), "qualifier": "committed-to-pull_request"}]
                )
            elif event["event"] == "closed":
                insert_event(
                    f"{event['node_id']}",
                    "close_pull_request",
                    timestamp,
                    collection,
                    [],
                    [actor, {"objectId": str(pull['number']), "qualifier": "closed-on-pull_request"}]
                )
            elif event["event"] == "reopened":
                actor = {"objectId": get_name_by_username(event["actor"]["login"], collection), "qualifier": "reopened-by"}
                insert_event(
                    f"{event['node_id']}",
                    "reopen_pull_request",
                    timestamp,
                    collection,
                    [],
                    [actor, {"objectId": str(pull['number']), "qualifier": "reopened-pull-request"}]
                )
            elif event["event"] == "merged":
                insert_event(
                    f"{event['node_id']}",
                    "merge_pull_request",
                    timestamp,
                    collection,
                    [],
                    [actor, {"objectId": str(pull['number']), "qualifier": "merged-on-pull_request"}]
                )
            elif event["event"] == "review_requested":
                requested_reviewer = {"objectId": get_name_by_username(event["requested_reviewer"]["login"], collection), "qualifier": "for"}
                review_requester = {"objectId": get_name_by_username(event["review_requester"]["login"], collection), "qualifier": "by"}
                insert_event(
                    f"{event['node_id']}",
                    "add_review_request",
                    timestamp,
                    collection, 
                    [],
                    [requested_reviewer, review_requester, {"objectId": str(pull['number']), "qualifier": "in-pull-request"}]
                )
            elif event["event"] == "review_request_removed":
                requested_reviewer = {"objectId": get_name_by_username(event["requested_reviewer"]["login"], collection), "qualifier": "for"}
                review_requester = {"objectId": get_name_by_username(event["review_requester"]["login"], collection), "qualifier": "by"}
                insert_event(
                    f"{event['node_id']}",
                    "remove_review_request",
                    timestamp,
                    collection,
                    [],
                    [requested_reviewer, review_requester, {"objectId": str(pull['number']), "qualifier": "in-pull-request"}]
                )
            elif event["event"] == "commented":
                user_relation = {"objectId": get_name_by_username(event["actor"]["login"], collection), "qualifier": "commented-by"}
                insert_event(
                    f"{event['node_id']}",
                    "comment_pull_request",
                    timestamp,
                    collection,
                    [{"name": "comment", "value": f"{event["body"]}"}],
                    [user_relation, {"objectId": str(pull['number']), "qualifier": "on-pull-request"}]
                )
            elif event["event"] == "ready-for-review":
                insert_event(
                    f"{event['node_id']}",
                    "mark_ready_for_review",
                    timestamp,
                    collection,
                    [],
                    [actor, {"objectId": str(pull['number']), "qualifier": "in-pull-request"}]
                )
            elif event["event"] == "renamed":
                insert_event(
                    f"{event['node_id']}",
                    "rename_pull_request",
                    timestamp,
                    collection,
                    [{"name": "renamed-to", "value": event["rename"]["to"]}],
                    [{"objectId": get_name_by_username(event["actor"]["login"], collection, collection), "qualifier": "change-issued-by"}, {"objectId": str(pull['number']), "qualifier": "for-pull-request"}]
                )
            elif event["event"] == "labeled":
                label = {"name": "label", "value": event["label"]["name"]}
                insert_event(
                    f"{event['node_id']}",
                    "add_label",
                    timestamp,
                    collection,
                    [label],
                    [actor, {"objectId": str(pull['number']), "qualifier": "labeled-on-pull_request"}]
                )
            elif event["event"] == "unlabeled":
                label = {"name": "label", "value": event["label"]["name"]}
                insert_event(
                    f"{event['node_id']}",
                    "remove_label",
                    timestamp,
                    collection,
                    [label],
                    [actor, {"objectId": str(pull['number']), "qualifier": "unlabeled-on-pull_request"}]
                )
            elif event["event"] == "reviewed":
                if event["state"] == "approved":
                    review_type = "approve_review"
                    user_relation = {"objectId": get_name_by_username(event["user"]["login"], collection), "qualifier": "approved-by"}
                elif event["state"] == "changes_requested":
                    review_type = "suggest_changes_as_review"
                    user_relation = {"objectId": get_name_by_username(event["user"]["login"], collection), "qualifier": "requested-by"}
                elif event["state"] == "review_dismissed":
                    review_type = "dismiss_review"
                    user_relation = {"objectId": get_name_by_username(event["user"]["login"], collection), "qualifier": "dismissed-by"}
                else:
                    review_type = "comment_review"
                    user_relation = {"objectId": get_name_by_username(event["user"]["login"], collection), "qualifier": "commented-by"}
                timestamp = event["submitted_at"]
                insert_event(
                    f"{event['id']}",
                    review_type,
                    timestamp,
                    collection,
                    [],
                    [user_relation, {"objectId": str(pull['number']), "qualifier": "for-pull-request"}]
                )
        # Assumption: Creation of pull request is when pull request was opened, i.e. pull requests are opened not as draft
        insert_event(
            f"open_pull_{pull['number']}",
            "open_pull_request",
            pull["created_at"],
            collection,
            [],
            [{"objectId": get_name_by_username(pull["user"]["login"], collection), "qualifier": "opened-by"}, {"objectId": str(pull['number']), "qualifier": "for-pull_request"}]
        )
        # TODO 1. Change file event


def get_pull_data(number: int, owner: str, repo_name: str) -> dict:
    return get_api_response(f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{number}")

def get_related_commits(commits_url):
    commit_response = get_api_response(commits_url) 
    commits = []
    for commit in commit_response:
        commits.append(commit["sha"])
    return commits

def get_related_files(files_url):
    file_response = get_api_response(files_url)
    files = []
    for file in file_response:
        files.append(file["filename"])
    return files

def get_related_pulls(pulls_url):
    pull_response = get_api_response(pulls_url)
    pulls = []
    for pull in pull_response:
        pulls.append(str(pull["number"]))
    return pulls

def get_anonymous_user_counter():
    global anonymous_user_counter
    return anonymous_user_counter

def get_name_by_username(username, collection, author_association = "NONE"):
    global anonymous_user_counter
    user_response = {
        "name": None,
        "login": username,
        "type": "Bot",
        "updated_at": date_1970(),
    }
    if username != "Copilot":
        user_response = get_api_response(f"https://api.github.com/users/{username}")
        if user_response["name"] is None and user_response["type"] == "User":
            anonymous_user_counter[username] = anonymous_user_counter.get(username, 0) + 1
    user = {
        "name": user_response["name"] if user_response["name"] else username, 
        "username": user_response["login"] if user_response["login"] else username, 
        "rank": author_association,
        "is-bot": False if user_response["type"] == "User" else True, 
        "created_at_timestamp": user_response["updated_at"] if user_response["updated_at"] else date_1970(),
    }
    insert_user(user, collection)
    return user["name"]
