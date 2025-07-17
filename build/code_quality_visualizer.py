from datetime import datetime
from pydoc import doc
from matplotlib import pyplot as plt
import numpy as np
from build.code_quality_analyzer import get_file_metrics_at
from build.contribution_process_miner import get_commits
from build.database_handler import get_events_for_type, get_files, get_object, get_related_objects

def plot_commit_code_quality(repo_name):
    """
    Plot the code quality metrics for each commit of a repository in the database
    Args:
        repo_name (str): The name of the repository of which the metrics are to be plotted.
    """
    # Set up the used variables
    commits = get_events_for_type("commit", repo_name)
    commit_dates = []
    maintainability_indices = []
    commit_pylints = []

    # Prepare the data for plotting
    date_str = "2020-06-02T19:45:54.000+00:00"
    date_obj_1 = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    dt = np.array([date_obj_1])
    for commit in commits:
        commit_date = commit["time"]
        commit_dates.append(datetime.fromisoformat(commit_date))
        maintainability_index = commit["attributes"][0]
        maintainability_indices.append(maintainability_index)
        pylint_score = commit["attributes"][1]
        commit_pylints.append(pylint_score)
    plt.figure(figsize=(12, 6))
    plt.plot(dt,[0], label="Initial Code Quality", color="black", marker="o", linestyle="--")
    plt.plot(commit_dates, maintainability_indices, label="Maintainability Index", color="blue", marker="o", linestyle="-")
    plt.plot(commit_dates, commit_pylints, label="Pylint Score", color="red", marker="x", linestyle="-")
    plt.xlabel("Commit Date")
    plt.ylabel("Code Quality Score")
    plt.title(f"Code Quality Metrics Over Time for {repo_name}")
    plt.rcParams['axes.spines.top'] = False
    plt.rcParams['axes.spines.right'] = False
    plt.ylim(0, 1.1)
    plt.legend()
    plt.xticks(rotation=90)
    plt.savefig(f"Exports/{repo_name}_code_quality.png")

# def plot_file_code_quality(file_id):
#     """
#     Plot the code quality metrics for a specific file in the repository
#     Args:
#         repo_name (str): The name of the repository of the file file belongs to
#         file_id (str): The ID of the file to plot the code quality metrics for
#     """
#     file = get_object(file_id)
#     mis = {}
#     pylint_scores = {}
#     for attribute in file["attributes"]: # type: ignore
#         if attribute["name"] == "loc":
#             mis[datetime.fromisoformat(attribute["time"]).replace(tzinfo=None)] = int(attribute["value"])
#     commit_dates = sorted(mis.keys())
#     maintainability_indices = [mis[date] for date in commit_dates]
#     plt.figure(figsize=(12, 6))
#     plt.plot(commit_dates, maintainability_indices, label="Maintainability Index", color="blue", marker="o", linestyle="-")
#     plt.xlabel("Commit Date")
#     plt.ylabel("Code Quality Score")
#     plt.title(f"Code Quality Metrics Over Time for {file['_id']}") # type: ignore
#     plt.xticks(rotation=90)
#     plt.rcParams['axes.spines.top'] = False
#     plt.rcParams['axes.spines.right'] = False
#     plt.ylim(0, 400)
#     plt.legend()
#     plt.savefig(f"Exports/{file['_id']}_code_quality.png") # type: ignore

def split_code_quality_per_guideline_change(collection):
    """
    Split the code quality metrics per contribution guideline change
    Args:
        collection (str): The name of the collection to split the code quality metrics for.
    """
    # Get all commits and their contribution guideline versions
    commits = get_commits(collection)
    guideline_versions = {}
    for commit in commits:
        if "contribution_guideline_version" in commit.get("attributes")[3]["name"]:
            guideline_versions[commit["attributes"][0]["time"]] = commit["attributes"][3]["contribution_guideline_version"]
    code_quality = get_repository_code_quality(collection)
    times = list(code_quality.keys())
    mis = [v["mi"] for v in code_quality.values()]
    pylints = [v["pylint_score"] for v in code_quality.values()]
    plt.figure(figsize=(14, 7))
    plt.plot(times, mis, label="Maintainability Index", color="blue", marker="o")
    plt.plot(times, pylints, label="Pylint Score", color="red", marker="x")

    # Add vertical lines for guideline changes
    for change_time, version in guideline_versions:
        plt.axvline(x=change_time, color='green', linestyle='--', alpha=0.7)
        plt.text(change_time, plt.ylim()[1]*0.95, f'Version {version}', rotation=90, color='green', va='top', ha='right', fontsize=8)

    plt.xlabel("Commit Date")
    plt.ylabel("Code Quality Score")
    plt.title(f"Repository Code Quality Over Time with Guideline Changes")
    plt.legend()
    plt.xticks(rotation=90)
    plt.tight_layout()
    plt.show()

def get_repository_code_quality(collection):
    """
    Get a time series of averaged code quality metrics (maintainability index and pylint score) over all files at each commit date.

    Args:
        collection (str): The name of the collection (i.e., repository) to get the metrics from.

    Returns:
        dict: A dictionary mapping each commit date (datetime) to the averaged code quality metrics at that point in time.
    """
    files = get_files(collection)
    commits = get_commits(collection)
    file_metrics = {}
    if commits:
        initial_commit_time = datetime.fromisoformat(commits[0].get("attributes")[0]["time"])
    else:
        raise ValueError("No commits found in the collection.")
        
    for file in files:
        mi, pylint = get_file_metrics_at(file["_id"], initial_commit_time.isoformat(), collection)
        file_metrics[file["_id"]] = {
            "mi": mi,
            "pylint_score": pylint
        }
    code_quality = {}
    # Average over all pylint_scores
    pylint_scores = [v["pylint_score"] for v in file_metrics.values()]
    pylint_average = sum(pylint_scores) / len(pylint_scores) if pylint_scores else 0
    mi_scores = [v["mi"] for v in file_metrics.values()]
    mi_average = sum(mi_scores) / len(mi_scores) if mi_scores else 0
    code_quality[initial_commit_time] = {
        "mi": mi_average,
        "pylint_score": pylint_average
    }
    for commit in commits:
        commit_time = datetime.fromisoformat(commit["attributes"][0]["time"])
        files = get_related_objects(commit["_id"], "aggregates", collection)
        for changed_file in files:
            if changed_file.split(".")[-1] not in ["py"]: 
                continue
            else:
                mi, pl = get_file_metrics_at(changed_file, commit["attributes"][0]["time"], collection)
                file_metrics[changed_file] = {
                    "mi": mi,
                    "pylint_score": pl
                }
        pylint_scores = [v["pylint_score"] for v in file_metrics.values()]
        pylint_average = sum(pylint_scores) / len(pylint_scores) if pylint_scores else 0
        mi_scores = [v["mi"] for v in file_metrics.values()]
        mi_average = sum(mi_scores) / len(mi_scores) if mi_scores else 0
        code_quality[commit_time] = {
            "mi": mi_average,
            "pylint_score": pylint_average
        }
    return code_quality