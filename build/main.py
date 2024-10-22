
import matplotlib.pyplot as plt
# from pydriller import Repository
# import numpy as np
# import requests
# import json
# from flask import Response
# 
# commits_monthly = list()
# curr_month = 0
# curr_year = 0
# i = 0
# month_del = 0
# month_add = 0
# month_commits = 0
# filecounter = 0
# 
# 
# for commit in Repository('https://github.com/dani-garcia/vaultwarden').traverse_commits():
# #for commit in Repository('~/Developer/Ecogenium/Atava').traverse_commits():
#     if (commit.committer_date.month != curr_month):
#         label = str(curr_month) + "-" + str(curr_year)
#         commits_monthly.append([label, filecounter, month_commits, month_add, month_del])
#         curr_month = commit.committer_date.month
#         curr_year = commit.committer_date.year
#         i += 1
#         filecounter = 0
#         month_del = 0
#         month_add = 0
#         month_commits = 0
# 
#     month_commits += 1
#     for file in commit.modified_files:
#         month_add += file.added_lines
#         month_del += file.deleted_lines
#         filecounter += 1
#     
# commits = []
# additions = []
# deletions = []
# files = []
# loc = []
# issues = []
# 
# for i in range(0, len(commits_monthly)):
#     commits.append(commits_monthly[i][1])
#     files.append(commits_monthly[i][2])
#     additions.append(commits_monthly[i][3])
#     deletions.append(commits_monthly[i][4])
#     if (i == 0):
#         loc.append(additions[i] - deletions[i])
#     else: 
#         loc.append(loc[i-1] + additions[i] - deletions[i])
# 
# api_url = "https://api.github.com/repos/dani-garcia/vaultwarden/issues"
# for i in range (1, 50):
#     params = {
#         "state": "all",
#         "direction": "asc",
#         "per_page": 100,
#         "page" : i
#     }
#     response = requests.get(api_url, params=params)
#     issues_response = response.json()
#     for issue in issues_response:
#         issue_data = []
#         issue_data.append(issue['number'])
#         issue_data.append(issue['created_at'])
#         issue_data.append(issue['closed_at'])
#         issues.append(issue_data)
# 
# m = 0
# issues_monthly = [0]
# for i in range(len(issues)):
#     if (issues[i][1][2:5] != issues[i+1][1][2:5]):
#         m += 1
#         issues_monthly.append(0)
#     issues_monthly[m] += 1
# 
# fig, ax1 = plt.subplots()
# ax1.plot(additions, color='g', label='Additions')
# ax1.plot(deletions, color='r', label='Deletions')
# ax1.plot(loc, color='0', label='LOC')
# ax1.tick_params(axis='y', labelcolor='0.5')
# 
# ax2 = ax1.twinx()
# ax2.plot(commits, color='y', label='Commits')
# ax2.plot(files, color='b', label='Files')
# ax2.plot(issues_monthly, color='0.3', label='Created Issues')
# ax2.tick_params(axis='y', labelcolor='0.8')
# 
# fig.tight_layout()
# ax1.legend()
# ax2.legend()
# plt.savefig("GitVisualisation.pdf", format="pdf")
# plt.show()
# 
import matplotlib.pyplot as plt
from pydriller import Repository
import requests

def analyze_commit_data(repo_url):
    # Initialize tracking variables
    monthly_commit_data = []
    current_month = 0
    current_year = 0
    monthly_additions = 0
    monthly_deletions = 0
    monthly_commit_count = 0
    modified_file_count = 0

    # Traverse through all commits in the repository
    for commit in Repository(repo_url).traverse_commits():
        # If we encounter a new month, save the previous month's data
        if commit.committer_date.month != current_month:
            label = f"{current_month}-{current_year}"
            monthly_commit_data.append([label, monthly_commit_count, modified_file_count, monthly_additions, monthly_deletions])
            # Reset counters for the new month
            current_month = commit.committer_date.month
            current_year = commit.committer_date.year
            monthly_additions = 0
            monthly_deletions = 0
            monthly_commit_count = 0
            modified_file_count = 0

        # Update current month's data
        monthly_commit_count += 1
        for file in commit.modified_files:
            monthly_additions += file.added_lines
            monthly_deletions += file.deleted_lines
            modified_file_count += 1

    return monthly_commit_data

def analyze_issues_data(repo_url, max_pages):
    issues_data = []
    api_url = f"https://api.github.com/repos/{repo_url}/issues"

    # Fetch issues data from GitHub using pagination
    for page in range(1, max_pages + 1):
        params = {
            "state": "all",
            "direction": "asc",
            "per_page": 100,
            "page": page
        }
        response = requests.get(api_url, params=params)
        if response.status_code != 200:
            print(f"Failed to fetch issues data. Status code: {response.status_code}")
            break

        issues_response = response.json()
        # Stop if no more issues are returned
        if not issues_response:
            break

        # Extract necessary issue data
        for issue in issues_response:
            issues_data.append([issue['number'], issue['created_at'], issue['closed_at']])

    return issues_data

def count_issues_monthly(issues_data):
    issues_per_month = [0,0,0,0]
    current_month = issues_data[0][1][5:7] if issues_data else None
    monthly_issue_count = 0

    # Count issues per month
    for i in range(len(issues_data) - 1):
        issue_month = issues_data[i][1][5:7]
        next_issue_month = issues_data[i + 1][1][5:7]
        if issue_month != next_issue_month:
            issues_per_month.append(monthly_issue_count)
            print("mic: ", monthly_issue_count, issues_data[i][1][2:7])
            monthly_issue_count = 0
            current_month = next_issue_month
        monthly_issue_count += 1

    # Add the last month's count
    issues_per_month.append(monthly_issue_count)
    return issues_per_month

def calculate_loc(monthly_commit_data):
    # Calculate lines of code (LOC) changes over time
    loc_over_time = []
    total_loc = 0

    for month_data in monthly_commit_data:
        additions = month_data[3]
        deletions = month_data[4]
        total_loc += additions - deletions
        loc_over_time.append(total_loc)

    return loc_over_time

def plot_data(monthly_commit_data, loc_over_time, issues_per_month):
    # Extract data for plotting
    monthly_labels = [data[0] for data in monthly_commit_data]
    monthly_commits = [data[1] for data in monthly_commit_data]
    modified_files = [data[2] for data in monthly_commit_data]
    monthly_additions = [data[3] for data in monthly_commit_data]
    monthly_deletions = [data[4] for data in monthly_commit_data]

    for i in range(len(monthly_labels)):
        label = monthly_labels[i].split('-')
        if (len(label[0]) == 1):
            label[0] = "0" + label[0]
        label[1] = label[1][2:]
        monthly_labels[i] = label[1] + "-" + label[0]

    # Plotting
    fig, ax1 = plt.subplots()

    # Plot lines for additions, deletions, and LOC
    ax1.plot(monthly_labels, monthly_additions, color='g', label='Additions')
    ax1.plot(monthly_labels, monthly_deletions, color='r', label='Deletions')
    ax1.plot(monthly_labels, loc_over_time, color='k', label='LOC')
    ax1.tick_params(axis='y', labelcolor='black')

    # Secondary Y-axis for commits, modified files, and issues
    ax2 = ax1.twinx()
    ax2.plot(monthly_labels, monthly_commits, color='y', label='Commits')
    ax2.plot(monthly_labels, modified_files, color='b', label='Modified Files')
    ax2.plot(monthly_labels[:len(issues_per_month)], issues_per_month, color='grey', label='Created Issues')
    ax2.tick_params(axis='y', labelcolor='grey')

    # Finalize and show the plot
    fig.tight_layout()
    ax1.legend(loc='upper left')
    ax2.legend(loc='upper right')
    plt.xticks(rotation=45)
    plt.title("Repository Analysis")
    plt.savefig("GitVisualisation.pdf", format="pdf")
    plt.show()

def main():
    repo_url = 'dani-garcia/vaultwarden'
    monthly_commit_data = analyze_commit_data(f'https://github.com/{repo_url}')
    issues_data = analyze_issues_data(repo_url, 50)
    issues_per_month = count_issues_monthly(issues_data)
    loc_over_time = calculate_loc(monthly_commit_data)
    plot_data(monthly_commit_data, loc_over_time, issues_per_month)

if __name__ == "__main__":
    main()