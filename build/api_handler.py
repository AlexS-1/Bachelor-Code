import os
import time
from httpx import get
import requests
import test

from build.database_handler import insert_comment, insert_event, insert_issue, insert_repo, insert_pull, insert_review, insert_test_run, insert_user

token = os.getenv("GITHUB_TOKEN")  # Import GitHub token from environment variables
owner = "srbhr"
repo_name = "Resume-Matcher"
url = f"https://api.github.com/repos/{owner}/{repo_name}"
headers = {"Authorization": f"token {token}"}
anonymous_user_counter = {}

def get_api_response(url, retries=0):
    response = requests.get(url, headers=headers)
    if response.ok:
        return response.json()
    elif response.status_code == 403 or response.status_code == 429 and retries < 5:
        if int(response.headers.get("x-ratelimit-remaining", 0)) == 0:
            retry_after = int(response.headers.get("x-ratelimit-reset", 60)) - int(time.time())
            print(f"Primary rate limit exceeded. Retrying after {retry_after} seconds.")
            retries += 1
        else:
            retry_after = int(response.headers.get("retry-after", 60))
            print(f"Secondary rate limit exceeded. Retrying after {retry_after} seconds.")
            retries += 1
        time.sleep(retry_after^retries)
        return get_api_response(url, retries)
    else: 
        print(  response.raise_for_status())

def get_repo_information(repo_url=url):
    repo_response = get_api_response(repo_url)
    repo_information = {
        "name": repo_response["full_name"],
        "has-pull_requests": get_related_pulls(repo_response["pulls_url"][:-9]),
        "has-commits": get_related_commits(repo_response["commits_url"][:-6]),
        "has-branches": get_related_branches(repo_response["branches_url"][:-9]),
        "has-issues": get_related_issues(repo_response["issues_url"][:-9]),
        "timestamp": repo_response["updated_at"],
        "utility_information": {
            "forks_url": repo_response["forks_url"],
            "forks_count": repo_response["forks"],
            "pulls_url": repo_response["pulls_url"][:-9],
            "issues_url": repo_response["issues_url"][:-9],
            "commits_url": repo_response["commits_url"][:-6],
            "created_at": repo_response["created_at"], #TODO Check if it was modified and how to get data (e.g. rename of repository)
        }
    }
    insert_repo(repo_information)
    return repo_information

def get_closed_pulls(pulls_url, pages = 1):
    pulls = {}
    for page in range(1, pages + 1):
        pull_response = get_api_response(pulls_url + "?state=closed&page=" + str(page))
        extract_events_from_pull(pull_response)
        for pull in pull_response:
            comments = get_related_comments(pull["comments_url"])
            pull_content = {
                "merge_commit_sha":  pull["merge_commit_sha"],
                "number": str(pull["number"]),
                "author": get_name_by_username(pull["user"]["login"], pull["author_association"]),
                "title": pull["title"],
                "description": pull["body"],
                "merged_at_timestamp": pull["merged_at"],
                "created_at_timestamp": pull["created_at"],
                "closed_at_timestamp": pull["closed_at"],
                # "head_branches_url": pull["head"]["label"].split(":")[0]+"/Resume-Matcher" if not pull["head"]["repo"]["branches_url"][:-9] else pull["head"]["repo"]["branches_url"][:-9],
                # "base_branches_url": pull["base"]["repo"]["branches_url"][:-9],
                "branch_to_pull_from": pull["head"]["ref"],
                "origin_branch": pull["base"]["ref"],
                # "closing_issues": 0, # TODO Fix to parse description and crawl github.com or otherwise retrieve respective field -> GH Archive maybe
                "participants": 
                    [get_name_by_username(pull["user"]["login"])] + 
                    [get_name_by_username(user["login"]) for user in pull["requested_reviewers"] + pull["requested_teams"] + pull["assignees"]] + 
                    [comment.split("/")[0] for comment in comments],
                "reviewers": [get_name_by_username(user["login"]) for user in pull["requested_reviewers"] + pull["requested_teams"]], 
                "assignees": [get_name_by_username(user["login"]) for user in pull["assignees"]],
                "comments": comments,
                "commits": get_related_commits(pull["commits_url"]),
                "file_changes": get_related_files(pull["url"] + "/files"),
                "test_runs": get_related_ci_cd(pull["url"].split("pulls")[0] + "commits/" + pull["head"]["sha"]),
                "state": "merged" if pull["merged_at"] else "closed",
            }
            insert_pull(pull_content)
            pulls[pull["number"]] = pull_content
    return pulls

def extract_events_from_pull(pull_response):
    for pull in pull_response:
        for comment in get_api_response(pull["comments_url"]):
            insert_event(f"comment-pull_request-{comment["id"]}", 
                         "comment", 
                         comment["created_at"], 
                         [], 
                         [{"objectId": get_name_by_username(comment["user"]["login"]), "qualifier": "commented-by-user"},
                          {"objectId": str(pull["number"]), "qualifier": "commented-on-pull_request"}])
        for review in get_api_response(pull["review_comments_url"]):
            insert_event(f"review-pull_request-{review["id"]}", 
                         "review", 
                         review["created_at"], 
                         [], 
                         [{"objectId": get_name_by_username(review["user"]["login"]), "qualifier": "reviewed-by-user"},
                          {"objectId": str(pull["number"]), "qualifier": "reviewed-on-pull_request"}])
        for commit in get_api_response(pull["commits_url"]):
            insert_event(f"commit-pull_request-{commit["sha"]}", 
                         "commit", 
                         commit["commit"]["author"]["date"], 
                         [], 
                         [{"objectId": commit["commit"]["author"]["name"], "qualifier": "committed-by-user"},
                          {"objectId": str(pull["number"]), "qualifier": "committed-to-pull_request"}])
        if pull["closed_at"]:
            insert_event(f"close-pull_request-{pull["number"]}", 
                         "close", 
                         pull["closed_at"], 
                         [], 
                         [{"objectId": get_name_by_username(pull["user"]["login"]), "qualifier": "closed-by-user"},
                          {"objectId": str(pull["number"]), "qualifier": "closed-pull_request"}])
        if pull["merged_at"]:
            insert_event(f"merge-pull_request-{pull["number"]}", 
                         "merge", 
                         pull["merged_at"], 
                         [], 
                         [{"objectId": get_name_by_username(get_pull_data(pull["number"])["merged_by"]["login"]), "qualifier": "merged-by-user"},
                          {"objectId": str(pull["number"]), "qualifier": "merged-pull_request"}])

def get_pull_data(number: int) -> dict:
    return get_api_response(f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{number}")

def get_issues(issues_url, pages=1):
    issues = {}
    for page in range(1, pages + 1):
        issue_response = get_api_response(issues_url + "?page=" + str(page))
        for issue in issue_response:
            issue_content = {
                "number": str(issue["number"]),
                "authored-by": get_name_by_username(issue["user"]["login"], issue["author_association"]),
                "title": issue["title"],
                "description": issue["body"],
                "issue-in-repository": "/".join(issue["repository_url"].split("/")[:-2]),
                "created_at_timestamp": issue["created_at"],
                "closed_at_timestamp": issue["closed_at"],
                "type": get_issue_state_history(issue["events_url"]),
                "issue-has-comment": get_related_comments(issue["comments_url"]),
                "issue-is-assigned-to": [get_name_by_username(assignee["login"]) for assignee in issue["assignees"]],
            }
            insert_issue(issue_content)
            issues[issue["number"]] = issue_content
    return issues

def get_issue_state_history(events_url):
    events = []
    event_response = get_api_response(events_url)
    for event in event_response:
        if event["event"] == "opened":
            events.append({"opened": event["created_at"]})
        elif event["event"] == "closed":
            events.append({"closed": event["created_at"]})
        elif event["event"] == "reopened":
            events.append({"reopened": event["created_at"]})
        elif event["event"] == "merged":
            events.append({"merged": event["created_at"]})
        elif event["event"] == "referenced":
            events.append({"closed": event["created_at"]})
    return events

def get_related_comments(comments_url):
    comment_response = get_api_response(comments_url)
    comments = []
    for comment in comment_response[:5]:
        comments.append(get_name_by_username(comment["user"]["login"]) + "/" + comment["created_at"])
        comment_content = {
            "message": comment["body"],
            "timestamp": comment["created_at"],
            "comment-authored-by": get_name_by_username(comment["user"]["login"])
        }
        insert_comment(comment_content)
    return comments

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

def get_related_commits(commits_url):
    commit_response = get_api_response(commits_url)
    commits = []
    for commit in commit_response:
        commits.append(commit["sha"])
    return commits

def get_related_reviews(review_comments_url):
    review_response = get_api_response(review_comments_url)
    reviews = []
    for review in review_response:
        reviews.append(review["id"])
        review_data = {
            "id": str(review["id"]),
            "timestamp": review["updated_at"],
            "author": get_name_by_username(review["user"]["login"]),
            "part-of-pull_request": review["pull_request_url"].split("/")[-1],
            "comment": review["body"],
            "references-code": review["diff_hunk"] if review["subject_tpye"] == "line" else review["path"]
        }
        insert_review(review_data)
    return reviews

def get_related_branches(branches_url):
    branch_response = get_api_response(branches_url)
    branches = []
    for branch in branch_response:
        branches.append(branch["name"])
    return branches

def get_related_issues(issues_url):
    issue_response = get_api_response(issues_url)
    issues = []
    for issue in issue_response:
        issues.append(str(issue["number"]))
    return issues

def get_related_ci_cd(ci_cd_url):
    ci_cd_response = get_api_response(ci_cd_url + "/check-runs")
    ci_cd = []
    if ci_cd_response["total_count"] != 0:
        for ci_cd_run in ci_cd_response["check_runs"]:
            test_run = {
                "id": str(ci_cd_run["id"]),
                "timestamp": ci_cd_run["started_at"],
                "name": ci_cd_run["name"],
                "passed": ci_cd_run["conclusion"] == "success",
            }
            insert_test_run(test_run)
            ci_cd.append(test_run["id"])
    return ci_cd

def get_anonymous_user_counter():
    global anonymous_user_counter
    return anonymous_user_counter

def get_name_by_username(username, author_association = "NONE"):
    global anonymous_user_counter
    user_response = get_api_response(f"https://api.github.com/users/{username}")
    if user_response["name"] is None and user_response["type"] == "User":
        anonymous_user_counter[username] = anonymous_user_counter.get(username, 0) + 1
    user = {
        "name": user_response["name"] if user_response["name"] else username, 
        "username": user_response["login"], 
        "rank": author_association,
        "type": "user" if user_response["type"] == "User" else "bot", 
        "created_at_timestamp": user_response["updated_at"]
    }
    insert_user(user)
    return user["name"]
