from datetime import datetime
from pydoc import doc
from matplotlib import pyplot as plt, ticker
import numpy as np
from build.code_quality_analyzer import get_file_metrics_at
from build.contribution_process_miner import get_commits
from build.database_handler import get_events_for_eventType, get_files, get_object, get_related_objects
import random
from build.database_handler import get_attribute_value_at_time, get_object, get_related_objects
import matplotlib.dates as mdates
from matplotlib.dates import date2num as date2num

def plot_repo_code_quality_fast(collection): #TODO Unify with get_repository_code_quality and split_code_quality_per_guideline_change
    """
    Plot the code quality metrics for each commit of a repository in the database
    Args:
        repo_name (str): The name of the repository of which the metrics are to be plotted.
    """
    # Set up the used variables
    commits = get_commits(collection)
    commit_dates = []

    metrics = {}
    # Prepare the data for plotting
    for commit in commits:
        commit_date = commit["attributes"][0]["time"]
        pylint_score = commit["relationships"][0]["objectId"]
        maintainability_index = commit["relationships"][1]["objectId"]
        guideline_version = commit["attributes"][3]["value"]
        metrics[commit_date] = {
            "maintainability_index": maintainability_index,
            "pylint_score": pylint_score,
            "guideline_version": guideline_version
        }

    plt.figure(figsize=(12, 6))
    datetimes = [datetime.fromisoformat(ts) for ts in sorted(metrics.keys())]
    commit_dates = np.array(datetimes)
    for metric in ["maintainability_index", "pylint_score", "guideline_version"]:
        # Set lables
        if len(metric.split("_")) > 1:
            metric_label = metric.replace("_", " ").title()
        else:
            metric_label = metric.upper()

        # Plot depending on label
        if metric_label == "Guideline Version":
            guideline_changes = sorted(list(set([metrics[date]["guideline_version"] for date in sorted(metrics.keys())])))[1:]
            for change in guideline_changes:
                if not isinstance(change, datetime):
                    dt_change = datetime.fromisoformat(change)
                else:
                    dt_change = change

                plt.axvline(float(mdates.date2num(dt_change)), color='black', linestyle='--', alpha=0.7)
        else:
            values = np.array([float(metrics[date][metric]) for date in sorted(metrics.keys())])
            plt.plot(commit_dates, values, label=metric_label, linestyle="-")

    plt.title(f"Code Quality Metrics Over Time for {collection}")
    plt.rcParams['axes.spines.top'] = False
    plt.rcParams['axes.spines.right'] = False

    plt.xlabel("Commit Date")
    ax = plt.gca()
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

    plt.ylabel("Code Quality Score")
    plt.ylim(0, 1)

    plt.legend()
    plt.rcParams['figure.facecolor'] = 'white'
    plt.rcParams['axes.facecolor'] = 'white'
    plt.rcParams['axes.edgecolor'] = 'black'
    plt.rcParams['axes.labelcolor'] = 'black'
    plt.rcParams['xtick.color'] = 'black'
    plt.rcParams['ytick.color'] = 'black'
    plt.rcParams['legend.edgecolor'] = 'black'
    plt.rcParams['legend.facecolor'] = 'black'
    plt.show()

def plot_file_code_quality(file_id, collection):
    """
    Plot the code quality metrics for a specific file in the repository
    Args:
        repo_name (str): The name of the repository of the file file belongs to
        file_id (str): The ID of the file to plot the code quality metrics for
    """
    file = get_object(file_id, collection)
    if not file:
        print(f"File with ID {file_id} not found in collection {collection}.")
        return
    metrics = {}

    for attribute in file["attributes"]:
        if attribute["name"] == "pylint_score":
            pylint_score = attribute["value"]
            metrics[attribute["time"]] = {"pylint_score": pylint_score}
    
    commit_dates = sorted(metrics.keys())
    # maintainability_indices = [metrics[date]["mi"] for date in commit_dates]
    pylint_scores = [metrics[date]["pylint_score"] for date in commit_dates]

    filtered_metrics = {dt: m for dt, m in metrics.items() if "pylint_score" in m}
    commit_dates = sorted(filtered_metrics.keys())
    pylint_scores = [filtered_metrics[date]["pylint_score"] for date in commit_dates]

    plt.figure(figsize=(12, 6))
    # plt.plot(commit_dates, maintainability_indices, label="Maintainability Index", color="blue", marker="o", linestyle="-")

    plt.plot(commit_dates, pylint_scores, label="Pylint Score", color="red", marker="x", linestyle="-")
    plt.xlabel("Commit Date")
    plt.ylabel("Code Quality Score")
    plt.title(f"Code Quality Metrics Over Time for {file['_id']}") # type: ignore
    plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(nbins=10, prune='both'))
    plt.rcParams['axes.spines.top'] = False
    plt.rcParams['axes.spines.right'] = False
    plt.ylim(0, 1)
    plt.legend()

def split_code_quality_per_guideline_change(collection, limit_commits=None):
    """
    Split the code quality metrics per contribution guideline change
    Args:
        collection (str): The name of the collection to split the code quality metrics for.
    """
    # Get all commits and their contribution guideline versions
    commits = get_commits(collection)
    guideline_versions = {}
    for commit in commits[:limit_commits]:
        if "contribution_guideline_version" in commit.get("attributes")[3]["name"]:
            guideline_versions[commit["attributes"][0]["time"]] = commit["attributes"][3]["value"]
    code_quality = get_repository_code_quality(collection)
    times = list(code_quality.keys())
    mis = [v["mi"] for v in code_quality.values()]
    pylints = [v["pylint_score"] for v in code_quality.values()]
    plt.figure(figsize=(14, 7))
    plt.plot(times, mis, label="Maintainability Index", color="blue", marker="o")
    plt.plot(times, pylints, label="Pylint Score", color="red", marker="x")

    # Add vertical lines for guideline changes #TODO make sure vertical lines are shown
    for change_time, version in guideline_versions.items():
        plt.axvline(x=change_time, color='green', linestyle='--', alpha=0.7)
        # plt.text(change_time, plt.ylim()[1]*0.95, f'Version {version}', rotation=90, color='green', va='top', ha='right', fontsize=8)

    plt.xlabel("Commit Date")
    plt.ylabel("Code Quality Score")
    plt.title(f"Repository Code Quality Over Time with Guideline Changes")
    plt.legend()
    plt.xticks(rotation=90)
    plt.tight_layout()
    plt.show()

def get_repository_code_quality(collection, limit_commits=None):
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
    for commit in commits[:limit_commits]:
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