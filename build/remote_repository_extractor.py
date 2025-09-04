from datetime import timedelta
import re
import time
import requests
import os

from build.database_handler import date_1970, datetime, get_user_by_username, insert_event, insert_pull, insert_user, update_attribute

token = os.getenv("GITHUB_TOKEN")  # Import GitHub token from environment variables

def get_and_insert_remote_data(repo_url, repo_path, start_date, end_date):
    repo = get_repo_information(repo_url)
    collection = repo_url.split("/")[-1]
    get_closed_pulls(repo["utility_information"]["pulls_url"], collection, start_date, end_date)
    
def get_api_response(url, retries=0, headers = False):
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

def get_api_response_with_headers(url):
    headers = {"Authorization": f"token {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json(), response.headers

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
            "created_at": repo_response["created_at"], 
        }
    }
    return repo_information

def _parse_link_last_page(headers) -> int:
    link = headers.get("Link", "")
    m = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link or "")
    return int(m.group(1)) if m else 1

def get_closed_pulls(pulls_url, collection, start_date, end_date):
    # Find the first pull request after the start page and the corresponding page
    last_pull_requests, headers = get_api_response_with_headers(pulls_url+"?state=closed&per_page=100")
    last_pull_request_number = int(last_pull_requests[0]["number"])
    page_max = _parse_link_last_page(headers)
    low, high = 1, max(1, page_max)
    while low < high:
        current_page = (low + high) // 2
        pull_response = get_api_response(pulls_url + "?state=closed&per_page=100&direction=asc&page=" + str(current_page))
        last_created = datetime.fromisoformat(pull_response[1]["created_at"]).replace(tzinfo=None)
        if last_created < start_date:
            low = current_page + 1
        else:
            high = current_page

    start_page = low
    pages = page_max - low
    print(f"LOG: Found {last_pull_request_number} closed pull requests in {pages} pages, starting at page {start_page}.")
    for page in range(start_page, page_max + 1):
        pull_response = get_api_response(pulls_url + "?state=closed&per_page=100&direction=asc&page=" + str(page))
        for pull in pull_response:
            created_at = datetime.fromisoformat(pull["created_at"]).replace(tzinfo=None)
            if created_at > end_date:
                break
            if created_at < start_date:
                continue
            pull_content = {
                "is-merged-with":  pull["merge_commit_sha"],
                "number": str(pull["number"]),
                "is-authored-by": get_name_by_username(pull["user"]["login"], collection, pull["author_association"]),
                "title": pull["title"],
                "description": pull["body"] if pull["body"] else "",
                "merged_at_timestamp": pull["merged_at"],
                "created_at_timestamp": pull["created_at"],
                "closed_at_timestamp": pull["closed_at"],
                "has-participant": 
                    [get_name_by_username(pull["user"]["login"], collection)] + 
                    [get_name_by_username(user["login"], collection) for user in pull["requested_reviewers"] + pull["assignees"]],
                "is-reviewed-by": [get_name_by_username(user["login"], collection) for user in pull["requested_reviewers"]], 
                "formalises": get_related_commits(pull["commits_url"]),
                "aggregates": get_related_files(pull["url"] + "/files"),
                "state": "open",
                "issue_label": extract_label_from_related_issues(pull["_links"]["self"]["href"], pull["body"]) if pull["body"] else ""
            }
            insert_pull(pull_content, collection)
        extract_events_from_pull(pull_response, collection, start_date, end_date)

def extract_label_from_related_issues(pull_url: str, pull_body: str) -> str:
    """
    Extract issue references from PR text.
    Matches:
      - "#123" (up to 5 digits, not ollowed by a dot)
      - https://github.com/<owner>/<repo>/issues/123
      - https://api.github.com/repos/<owner>/<repo>/issues/123
    Returns a sorted list like ["#12", "#203"].
    """
    if not pull_body:
        return ""

    # Try to get owner/repo from the API/web issue URL to restrict matches to same repo
    owner = repo = ""
    match = re.match(r"https?://(?:api\.github\.com/repos|github\.com)/([^/]+)/([^/]+)/", pull_url or "")
    if match:
        owner, repo = match.group(1).lower(), match.group(2).lower()

    refs: set[str] = set()

    # Intra-repo shorthand references: require whitespace or opening bracket before '#'
    # Constraints:
    #   - allow only up to 5 digits
    #   - do NOT match if a dot follows the digits (e.g., "#12345.67")
    # Matches: " #123", "(#123", "[#123"
    for m in re.finditer(r"(?:(?<=\s)|(?<=\()|(?<=\[))#(\d{1,5})(?!\.)\b", pull_body):
        refs.add(f"{m.group(1)}")

    # Web URLs to issues in the same repo
    for m in re.finditer(r"https?://github\.com/([^/\s]+)/([^/\s]+)/issues/(\d+)", pull_body):
        if not owner or (m.group(1).lower() == owner and m.group(2).lower() == repo):
            refs.add(f"{m.group(3)}")

    # API URLs to issues in the same repo
    for m in re.finditer(r"https?://api\.github\.com/repos/([^/\s]+)/([^/\s]+)/issues/(\d+)", pull_body):
        if not owner or (m.group(1).lower() == owner and m.group(2).lower() == repo):
            refs.add(f"{m.group(3)}")
    labels = set()
    for ref in refs:
        try:
            response = get_api_response(f"https://api.github.com/repos/{owner}/{repo}/issues/{ref}")
        except requests.exceptions.HTTPError as e:
            try: 
                response = get_api_response(f"https://api.github.com/repos/{owner}/{repo}/discussions/{ref}")
            except requests.exceptions.HTTPError as e:
                response = None
        if response and "labels" in response:
            labels.update(label["name"] for label in response["labels"])
        if "good first issue" in labels:
            print(f"LOG: Found label: 'good first issue' for referenced issue #{ref} in PR#{pull_url.split('/')[-1]}")
    print("LOG: labels:", labels)
    return str(labels)

def extract_events_from_pull(pull_response, collection, start_date, end_date):
    for pull in pull_response:
        # Check PR events
        created_at = datetime.fromisoformat(pull["created_at"]).replace(tzinfo=None)
        if created_at > end_date:
            break
        if created_at < start_date:
            continue
        
        # Assumption: Creation of pull request is when pull request was opened, i.e. pull requests are opened not as draft
        insert_event(
            f"open_pull_{pull['number']}",
            "open_pull_request",
            pull["created_at"],
            collection,
            [],
            [{"objectId": get_name_by_username(pull["user"]["login"], collection), "qualifier": "opened-by"}, {"objectId": str(pull['number']), "qualifier": "for-pull_request"}]
        )
        for event in get_api_response(pull["issue_url"] + "/timeline"):
            if not event:
                print("ERROR: No event found for pull request", pull["number"])
                continue
            if event["event"] not in ["committed", "reviewed", "line-commented", "mentioned", "subscribed"]:
                try:
                    timestamp = event["created_at"]
                except:
                    print(f"ERROR: Unable to get timestamp for event: {event['node_id']} with event type: {event['event']} in #PR: {pull['number']}")
                    continue
                try: 
                    actor = {"objectId": get_name_by_username(event["actor"]["login"], collection), "qualifier": "authored-by"}
                except: 
                    print(f"ERROR: Unable to get actor for event: {event['node_id']} with event type: {event['event']} in #PR: {pull['number']}")
                finally:
                    actor = {"objectId": "Cincinnatus", "qualifier": "authored-by"}
            else:
                timestamp = date_1970()
                actor = {"objectId": "Cincinnatus", "qualifier": "authored-by"}
            # Handle specific events from OCEL-Diagrams.drawio
            if event["event"] == "committed":
                # TODO Define timestamp correctly: timestamp = event["author"]["date"]
                committer = {"objectId": event["committer"]["name"], "qualifier": "authored-by"}
                commit = {"objectId": event["sha"], "qualifier": "sha"}
                insert_event(
                    f"{event['node_id']}",
                    "commit_event",
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
                update_attribute(str(pull['number']), "state", "closed", timestamp, collection)
            elif event["event"] == "reopened":
                try:
                    actor = [{"objectId": get_name_by_username(event["actor"]["login"], collection), "qualifier": "reopened-by"}]
                except: 
                    actor = []
                insert_event(
                    f"{event['node_id']}",
                    "reopen_pull_request",
                    timestamp,
                    collection,
                    [],
                    actor.append({"objectId": str(pull['number']), "qualifier": "reopened-pull-request"})
                )
                update_attribute(str(pull['number']), "state", "open", timestamp, collection)
            elif event["event"] == "merged":
                insert_event(
                    f"{event['node_id']}",
                    "merge_pull_request",
                    timestamp,
                    collection,
                    [],
                    [actor, {"objectId": str(pull['number']), "qualifier": "merged-on-pull_request"}]
                )
                update_attribute(str(pull['number']), "state", "merged", timestamp, collection)
            elif event["event"] == "review_requested":
                try:
                    requested_reviewer = [{"objectId": get_name_by_username(event["requested_reviewer"]["login"], collection), "qualifier": "for"}]
                except:
                    requested_reviewer = [{"objectId": event["requested_team"]["name"], "qualifier": "for"}]
                try:
                    requested_reviewer.append({"objectId": get_name_by_username(event["review_requester"]["login"], collection), "qualifier": "by"})
                except:
                    pass
                insert_event(
                    f"{event['node_id']}",
                    "add_review_request",
                    timestamp,
                    collection, 
                    [],
                    [requested_reviewer.append({"objectId": str(pull['number']), "qualifier": "in-pull-request"})]
                )
            elif event["event"] == "review_request_removed":
                try:
                    requested_reviewer = {"objectId": get_name_by_username(event["requested_reviewer"]["login"], collection), "qualifier": "for"}
                except:
                    requested_reviewer = {"objectId": event["requested_team"]["name"], "qualifier": "for"}
                try:
                    review_requester = {"objectId": get_name_by_username(event["review_requester"]["login"], collection), "qualifier": "by"}
                except:
                    review_requester = {"objectId": event["requested_team"]["name"], "qualifier": "by"}
                insert_event(
                    f"{event['node_id']}",
                    "remove_review_request",
                    timestamp,
                    collection,
                    [],
                    [review_requester, requested_reviewer, {"objectId": str(pull['number']), "qualifier": "in-pull-request"}]
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
                if "#" in event["body"] or "https://" in event["body"]:
                    issue_references = extract_label_from_related_issues(pull["url"], event["body"])
                    if issue_references:
                        update_attribute(pull['number'], "issue_label", issue_references, timestamp, collection)
            elif event["event"] == "line-commented":
                for comment in event["comments"]:
                    try:
                        user = {"objectId": get_name_by_username(comment["user"]["login"], collection)}
                    except:
                        print(f"ERROR: Could not retrieve user during extraction of event: {event['node_id']} in #PR: {pull['number']}")
                        continue
                    insert_event(
                        f"LC_{comment['id']}",
                        "comment_pull_request",
                        comment["created_at"],
                        collection,
                        [{"name": "comment", "value": comment["body"]}],
                        [{"objectId": user["objectId"], "qualifier": "commented-by"}, {"objectId": str(pull['number']), "qualifier": "in-pull-request"}, {"objectId": comment["commit_id"], "qualifier": "for-commit"}, {"objectId": comment["path"], "qualifier": "for-file"}]
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
                try:
                    actor = [{"objectId": get_name_by_username(event["actor"]["login"], collection), "qualifier": "change-issued-by"}]
                except:
                    actor = []
                insert_event(
                    f"{event['node_id']}",
                    "rename_pull_request",
                    timestamp,
                    collection,
                    [{"name": "renamed-to", "value": event["rename"]["to"]}],
                    actor.append({"objectId": str(pull['number']), "qualifier": "for-pull-request"})
                )
                update_attribute(str(pull['number']), "title", event["rename"]["from"], timestamp, collection) #FIXME
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
                # update_attribute(pull['number'], "issue_label", event["label"]["name"], timestamp, collection) #TODO Decide for separate PR label?
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
                comment = []
                try:
                    user = {"objectId": get_name_by_username(event["user"]["login"], collection)}
                except:
                    print(f"ERROR: Could not retrieve user during extraction of event: {event['node_id']} in #PR: {pull['number']}")
                    continue
                if event["state"] == "approved":
                    review_type = "approve_review"
                    user_relation = {"objectId": user["objectId"], "qualifier": "approved-by"}
                elif event["state"] == "changes_requested":
                    review_type = "suggest_changes_as_review"
                    user_relation = {"objectId": user["objectId"], "qualifier": "requested-by"}
                elif event["state"] == "review_dismissed":
                    review_type = "dismiss_review"
                    user_relation = {"objectId": user["objectId"], "qualifier": "dismissed-by"}
                else:
                    review_type = "comment_review"
                    comment = [{"name": "comment", "value": event["body"]}]
                    user_relation = {"objectId": user["objectId"], "qualifier": "commented-by"}
                timestamp = event["submitted_at"]
                insert_event(
                    f"{event['id']}",
                    review_type,
                    timestamp,
                    collection,
                    comment,
                    [user_relation, {"objectId": str(pull['number']), "qualifier": "for-pull-request"}]
                )


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

def get_name_by_username(username, collection, author_association = "NONE"):
    # TODO Implement checking if remote and local user ids match
    user_response = {
        "name": None,
        "login": username,
        "type": "Bot",
        "updated_at": date_1970(),
    }
    # Check if user is already in database, than save API calls
    user_object = get_user_by_username(username, collection)
    if user_object:
        return user_object["_id"]
    else:
        if username != "Copilot":
            user_response = get_api_response(f"https://api.github.com/users/{username}")
        user = {
            "name": user_response["name"] if user_response["name"] else username,
            "username": user_response["login"] if user_response["login"] else username,
            "rank": author_association,
            "is-bot": False if user_response["type"] == "User" else True, 
            "created_at_timestamp": user_response["updated_at"] if user_response["updated_at"] else date_1970(),
        }
        insert_user(user, collection)
        return user["name"]
