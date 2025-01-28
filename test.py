import os
import sys
from venv import create
from httpx import get
import requests
import csv
import pymongo

# Add the build directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'build'))
from build.utils import save_to_json

# Configuration
token = os.getenv("GITHUB_TOKEN")  # Import GitHub token from environment variables
owner = "srbhr"
repo_name = "Resume-Matcher"
url = f"https://api.github.com/repos/{owner}/{repo_name}"
headers = {"Authorization": f"token {token}"}

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["mydatabase"]
print(myclient.list_database_names())
########################################################################################

# # Message lines
# message_lines = pull_request["body"].split("\n")

# classification = []

# # Print the comments
# for line in message_lines:
#     if line.find("] Bug Fix") != -1 and line[:-2].find("x") != -1:
#         classification.append("Corrective")
#     if line.find("] Feature Enhancement") != -1 and line.find("x") != -1:
#         classification.append("Adaptive")
#     if line.find("] Code Refactoring") != -1 and line.find("x") != -1:
#         classification.append("Perfective")
#     if line.find("] Documentation Update") != -1 and line.find("x") != -1:
#         classification.append("Preventive")

# print(pull_request["title"], ": ", classification[0])

########################################################################################

def get_api_response(url):
    response = requests.get(url, headers=headers)
    save_to_json(response.json(), "Data/response.json")
    return response.json()

def get_repo_information(repo_url):
    repo_response = get_api_response(repo_url)
    repo_information = {
        "forks_url": repo_response["forks_url"],
        "forks_count": repo_response["forks"],
        "pulls_url": repo_response["pulls_url"][:-9],
        "issues_url": repo_response["issues_url"][:-9],
        "commits_url": repo_response["commits_url"][:-6],
        "created_at": repo_response["created_at"],
    }
    mydb["repos"].insert_one(repo_information)
    return repo_information

def get_closed_pulls(pulls_url):
    pull_response = get_api_response(pulls_url + "?state=closed")
    pulls = {}
    for pull in pull_response[:25]:
        pull_content = {
            "title": pull["title"],
            "created_at": pull["created_at"],
            "merged_at": pull["merged_at"],
            "user": pull["user"]["login"],
            "merge_commit_sha":  pull["merge_commit_sha"],
            "commits_url": pull["commits_url"],
            "head_branches_url": pull["head"]["repo"]["branches_url"][:-9],
            "from_branch": pull["head"]["label"].split(":")[1],  
        }
        pulls[pull["number"]] = pull_content
    mydb["pulls"].insert_many(pulls.values())
    return pulls

def get_forks(forks_url, count):
    forks_data = {}
    for page in range(1, count//100 + 1):
        forks_response = get_api_response(forks_url + "?sort=newest&per_page=100&page=" + str(page))
        for fork in forks_response:
            forks_data[fork["full_name"].split("/")[0]] = fork["created_at"]
    mydb["forks"].insert_many(forks_data.values())
    return forks_data

########################################################################################

activities = []
repo = get_repo_information(url)
pulls = get_closed_pulls(repo["pulls_url"])
for pull, content in pulls.items():
    if content["merged_at"] is not None:
        activities.append({
            "Commit Main Repositoriy": content["merge_commit_sha"], 
            "Action": "Create Pull Request", 
            "Message": content["title"], 
            "Author": content["user"], 
            "Timestamp": content["created_at"], 
            "Comment": ""})
        pull_item = get_api_response(repo["pulls_url"] + "/" + str(pull))
        activities.append({
            "Commit Main Repositoriy": pull_item["merge_commit_sha"], 
            "Action": "Merge Pull Request", 
            "Message": "Merge " + pull_item["title"], 
            "Author": pull_item["merged_by"]["login"], 
            "Timestamp": pull_item["merged_at"], 
            "Comment": ""})
        pull_commits_url = pull_item["commits_url"]
        if pull_item["comments"] > 0:
            comments = get_api_response(pull_item["comments_url"])
            for comment in comments:
                activities.append({
                    "Commit Main Repositoriy": pull_item["merge_commit_sha"], 
                    "Action": "Comment Pull Request", 
                    "Message": comment["body"], 
                    "Author": comment["user"]["login"], 
                    "Timestamp": comment["created_at"], 
                    "Comment": ""})
        commits = get_api_response(pull_commits_url)
        for commit in commits:
            activities.append({
                "Commit Main Repositoriy": commit["sha"], 
                "Action": "Commit to Fork", 
                "Message": commit["commit"]["message"], 
                "Author": commit["author"]["login"], 
                "Timestamp": commit["commit"]["author"]["date"], 
                "Comment": ""})
        # commit_info = get_api_response(content["head_branches_url"] + "/" + content["from_branch"])
        # if commit_info["commit"]["sha"] == get_api_response(content["commits_url"])[0]["sha"]:
        #     activities.append({
        #         "Commit Main Repositoriy": content["merge_commit_sha"], 
        #         "Action": "Commit to Forked Repository", 
        #         "Message": "Commit " + commit_info["commit"]["message"], 
        #         "Author": content["user"], 
        #         "Timestamp": commit_info["commit"]["author"]["date"], 
        #         "Comment": ""})
        forks_data = get_forks(repo["forks_url"], repo["forks_count"])
        for forker, created_at in forks_data.items():
            if forker == content["user"]:
                activities.append({
                    "Commit Main Repositoriy": content["merge_commit_sha"],
                    "Action": "Fork Repository", 
                    "Message": "Fork " + repo_name, 
                    "Author": content["user"], 
                    "Timestamp": created_at, 
                    "Comment": ""})

with open("Exports/event_log.csv", "w", newline="") as csvfile:
    fieldnames = ["Commit Main Repositoriy", "Action", "Message", "Author", "Timestamp", "Comment"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(activities)