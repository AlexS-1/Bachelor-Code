import os
import time
import requests
import test

from build.database_handler import insert_comment, insert_issue, insert_repo, insert_pull, insert_test_run, insert_user
from build.utils import array_to_string

token = os.getenv("GITHUB_TOKEN")  # Import GitHub token from environment variables
owner = "srbhr"
repo_name = "Resume-Matcher"
url = f"https://api.github.com/repos/{owner}/{repo_name}"
headers = {"Authorization": f"token {token}"}

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
        "owner": get_name_by_username(repo_response["owner"]["login"]), #TODO Investigate if use of owner is necessary or if full name is sufficient
        "name": repo_response["name"],
        "pull_requests": get_related_pulls(repo_response["pulls_url"][:-9]),
        "commits": get_related_commits(repo_response["commits_url"][:-6]),
        "branches": get_related_branches(repo_response["branches_url"][:-9]),
        "issues": get_related_issues(repo_response["issues_url"][:-9]),
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
    insert_repo(repo_information)
    return repo_information

def get_closed_pulls(pulls_url):
    pulls = {}
    for page in range(1, 9):
        pull_response = get_api_response(pulls_url + "?state=closed&page=" + str(page))
        for pull in pull_response:
            pull_content = {
                "merge_commit_sha":  pull["merge_commit_sha"],
                "number": pull["number"],
                "author": get_name_by_username(pull["user"]["login"]),
                "title": pull["title"],
                "description": pull["body"],
                "merged_at_timestamp": pull["merged_at"],
                "created_at_timestamp": pull["created_at"],
                "closed_at_timestamp": pull["closed_at"],
                # "head_branches_url": pull["head"]["label"].split(":")[0]+"/Resume-Matcher" if not pull["head"]["repo"]["branches_url"][:-9] else pull["head"]["repo"]["branches_url"][:-9],
                # "base_branches_url": pull["base"]["repo"]["branches_url"][:-9],
                "branch_to_pull_from": pull["head"]["ref"],
                "origin_branch": pull["base"]["ref"],
                "closing_issues": 0, # TODO Fix to parse description and crawl github.com or otherwise retrieve respective field
                "participants": "", # TODO Fix to include reviewers, author and commenters
                "reviewers": pull["requested_reviewers"] + pull["requested_teams"],
                "comments": array_to_string(get_related_comments(pull["comments_url"])),
                "commits": get_related_commits(pull["commits_url"]),
                "file_changes": get_related_files(pull["url"] + "/files"),
                "test_runs": get_related_ci_cd(pull["url"].split("pulls")[0] + "commits/" + pull["head"]["sha"]),
                "state": "merged" if pull["merged_at"] else "closed",
            }
            insert_pull(pull_content)
            pulls[pull["number"]] = pull_content
    return pulls

def get_issues(issues_url):
    issues = {}
    for page in range(1, 4):
        issue_response = get_api_response(issues_url + "?page=" + str(page))
        for issue in issue_response:
            issue_content = {
                "number": issue["number"],
                "authored-by": get_name_by_username(issue["user"]["login"]),
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
        pulls.append(pull["number"])
    return pulls

def get_related_commits(commits_url):
    commit_response = get_api_response(commits_url)
    commits = []
    for commit in commit_response:
        commits.append(commit["sha"])
    return commits

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
        issues.append(issue["number"])
    return issues

def get_related_ci_cd(ci_cd_url):
    ci_cd_response = get_api_response(ci_cd_url + "/check-runs")
    ci_cd = []
    if ci_cd_response["total_count"] != 0:
        for ci_cd_run in ci_cd_response["check_runs"]:
            ci_cd.append(ci_cd_run["id"])
            test_run = {
                "id": ci_cd_run["id"],
                "timestamp": ci_cd_run["started_at"],
                "name": ci_cd_run["name"],
                "passed": ci_cd_run["conclusion"] == "success",
            }
            insert_test_run(test_run)
    return ci_cd

def get_name_by_username(username):
    user_response = get_api_response(f"https://api.github.com/users/{username}")
    if user_response["name"] is None:
        return username # TODO Refine and check overall percentage of cases
    insert_user({"name": user_response["name"], "username": user_response["login"], "email": user_response["email"], "rank": None, "bot": False if user_response["type"] == "User" else True, "created_at_timestamp": user_response["updated_at"]})
    return user_response["name"]
