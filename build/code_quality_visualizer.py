from datetime import datetime
from matplotlib import pyplot as plt
import numpy as np
from build.database_handler import get_events_for_type

def plot_commit_code_quality(repo_name):
    """
    Plot the code quality metrics for each commit of a repository in the database
    Args:
        repo_name (str): The name of the repository of which the metrics are to be plotted.
    """
    # Set up the used variables
    commits = get_events_for_type("commit")
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
    plt.show()