from datetime import datetime
from pydoc import doc
from matplotlib import pyplot as plt
import numpy as np
from build.code_quality_analyzer import calculate_maintainability_index, get_file_metrics_at
from build.contribution_process_miner import get_commits
from build.database_handler import get_attribute_time, get_attribute_value, get_events_for_eventType, get_files, get_object, get_related_objectIds
import matplotlib.dates as mdates
from matplotlib.dates import date2num as date2num

def plot_repo_code_quality_fast(collection, year=None): #TODO Unify with get_repository_code_quality and split_code_quality_per_guideline_change
    """
    Plot the code quality metrics for each commit of a repository in the database
    Args:
        repo_name (str): The name of the repository of which the metrics are to be plotted.
        year (str, optional): The year for which the metrics are to be plotted. If None, all years are included.
    """
    # Set up the used variables
    commits = get_commits(collection)
    commit_dates = []

    metrics = {}
    # Prepare the data for plotting
    for commit in commits:
        # TODO Fix as not intended use of function 
        commit_date = get_attribute_time(commit["_id"], "message", collection)
        guideline_version = get_attribute_value(commit["_id"], "guideline_version", collection)
        pylint_score = None
        maintainability_index = None

        pylint_score = get_related_objectIds(commit["_id"], "commit_pylint", collection)[0]
        maintainability_index = get_related_objectIds(commit["_id"], "commit_mi", collection)[0]

        if year and year in commit_date:
            metrics[commit_date] = {
                "maintainability_index": maintainability_index,
                "pylint_score": pylint_score,
                "guideline_version": guideline_version
            }
        elif not year:
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
            labelled = False
            for change in guideline_changes:
                if not isinstance(change, datetime):
                    dt_change = datetime.fromisoformat(change)
                else:
                    dt_change = change
                if not labelled:
                    plt.axvline(float(mdates.date2num(dt_change)), color='black', linestyle='--', label="Contribution Guideline Changes" , alpha=0.7)
                    labelled = True
                else:
                    plt.axvline(float(mdates.date2num(dt_change)), color='black', linestyle='--', alpha=0.7)

        else:
            if metric != "maintainability_index":
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

    _set_plot_style_and_plot()

def plot_file_code_quality(file_id, collection, metric_names=[]):
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
    
    # Setup the metrics dictionary
    metrics = {}
    input_metrics = []
    if "mi" in metric_names:
        input_metrics = (["cc", "theta_1", "theta_2", "N_1", "N_2", "sloc"] + metric_names) # TODO Fix error where MI is in wrong order
    else: 
        input_metrics = metric_names
    default_metric_structure = {}
    for metric in input_metrics:
        default_metric_structure[metric] = None

    previous_time = None
    previous_complete_time = None
    for attribute in file["attributes"]:
        if attribute["name"] not in input_metrics:
            continue
        time = attribute["time"]
        name = attribute["name"]
        value = attribute["value"]

        if time not in list(metrics.keys()):
            metrics[time] = default_metric_structure.copy()
            if previous_time is not None and previous_time != time:
                previous_complete_time = list(metrics.keys())[-3] if len(metrics) > 2 else None
                for metric, metric_value in metrics[previous_time].items():
                    if metric_value is None and metric != "mi":
                        metrics[previous_time][metric] = metrics[previous_complete_time][metric]
                    elif metric == "mi":
                        if all(metrics[previous_time][m] is not None for m in input_metrics if m != "mi"):
                            metrics[previous_time][metric] = calculate_maintainability_index(
                                metrics[previous_time]["N_1"],
                                metrics[previous_time]["N_2"],
                                metrics[previous_time]["theta_1"],
                                metrics[previous_time]["theta_2"],
                                metrics[previous_time]["cc"],
                                metrics[previous_time]["sloc"]
                            )/100
                        else: 
                            print(f"ERROR: Not all required metrics for MI calculation are available at {previous_time}.")
        metrics[time][name] = int(value) if name != "pylint_score" else float(value)
        previous_time = time

    # After going through all changed attributes, ensure that the last time point has also all metrics filled (Not accounted for in loop)
    for metric, metric_value in metrics[previous_time].items():
        if metric_value is None:
            metrics[previous_time][metric] = metrics[previous_complete_time][metric]

    # Plotting the metrics
    plt.figure(figsize=(12, 6))
    datetimes = [datetime.fromisoformat(ts) for ts in sorted(metrics.keys())]
    commit_dates = np.array(datetimes)
    for metric in metric_names:
        values = np.array([float(metrics[date][metric]) for date in sorted(metrics.keys())])
        if len(metric.split("_")) > 1:
            metric_label = metric.replace("_", " ").title()
        else:
            metric_label = metric.upper()
        plt.plot(commit_dates, values, label=metric_label, marker="o", linestyle="-")

    plt.title(f"Code Quality Metrics Over Time for {file['_id']}")

    plt.xlabel("Commit Date")
    ax = plt.gca()
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

    plt.ylabel("Code Quality Score")
    if "mi" in metric_names or "pylint_score" in metric_names:
        plt.ylim(0, 1)
    else:
        plt.ylim(0, max([max(metrics[date][metric] for date in metrics) for metric in metric_names]) * 1.1)
    _set_plot_style_and_plot()

def get_repository_code_quality(collection, limit_commits=None):
    """
    Get a time series of averaged code quality metrics (maintainability index and pylint score) over all files at each commit date.

    Args:
        collection (str): The name of the collection (i.e., repository) to get the metrics from.

    Returns:
        dict: A dictionary mapping each commit date (datetime) to the averaged code quality metrics at that point in time.
    """
    # TODO Compare and contrast with fast version above
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
        files = get_related_objectIds(commit["_id"], "aggregates", collection)
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

def _set_plot_style_and_plot():
    plt.rcParams['figure.facecolor'] = 'white'
    plt.rcParams['axes.facecolor'] = 'white'
    plt.rcParams['axes.edgecolor'] = 'black'
    plt.rcParams['axes.labelcolor'] = 'black'
    plt.rcParams['xtick.color'] = 'black'
    plt.rcParams['ytick.color'] = 'black'
    plt.rcParams['legend.edgecolor'] = 'black'
    plt.rcParams['legend.facecolor'] = 'black'
    plt.rcParams['axes.spines.top'] = False
    plt.rcParams['axes.spines.right'] = False
    plt.legend()
    plt.show()