from heapq import merge
import pandas as pd
from build.code_quality_visualizer import get_object
from build.utils import date_1970
from build.database_handler import get_commits, get_events_for_eventType, get_events_for_object, get_ocel_data, get_object_type, get_type_of_object
from datetime import datetime, tzinfo, timezone
from matplotlib import pyplot as plt

def pull_request_reviewer_analysis(pull_request_ids, collection, visualise=False):
    """
    First extract the pull request data for one or multiple pull requests
    then extract the reviewers from the pull request data
    and if specified visualise the number of reviewers per pull request over time.
    """
    pull_request_data = []
    for pull_request_id in pull_request_ids:
        events = get_events_for_object(pull_request_id, collection)
        reviewers = []
        bots = []
        pr_time = None
        for event in events:
            if "open" in event["type"] and pr_time is None:
                pr_time = datetime.fromisoformat(event["time"])
            elif "close" in event["type"]:
                pr_time = datetime.fromisoformat(event["time"])
            elif "review" == event["type"].split("_")[-1]:
                for related_object in event["relationships"]:
                    if "by" in related_object["qualifier"]:
                        user = get_object(related_object["objectId"], collection)
                        if user and user["type"] == "user" and user["attributes"][2]["value"] == "True":
                            bots.append(related_object["objectId"])
                        else:
                            reviewers.append(related_object["objectId"])
        pull_request_data.append({"id": pull_request_id, "time": pr_time, "reviewers": reviewers, "bots": bots})

    # Visualise the number of reviewers per pull request over time if specified
    if visualise:
        plt.figure(figsize=(10, 5))
        times = []
        counts = []
        bots = []
        for pr in pull_request_data:
            times.append(pr["time"])
            counts.append(len(pr["reviewers"]) + len(pr["bots"]))
            bots.append(len(pr["bots"]))
        # Sort by time
        sorted_pairs = sorted(zip(times, counts))
        times_sorted, counts_sorted = zip(*sorted_pairs)
        times_sorted, bots = zip(*sorted(zip(times, bots)))

        plt.plot(times_sorted, counts_sorted, marker='o', label='Reviewers per PR')
        plt.plot(times_sorted, bots, marker='x', label='Reviews by Bots per PR', color='orange')

        average = sum(counts_sorted) / len(counts_sorted) if counts_sorted else 0
        plt.axhline(y=average, color='r', linestyle='--', label='Average')
        plt.xlabel('Time')
        plt.ylabel('Number of Reviewers')
        plt.yticks(range(0, max(counts_sorted) + 2))
        plt.title('Number of Reviewers per Pull Request Over Time')
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
    else:
        return pull_request_data
    
def pull_request_open_time_analysis(pull_request_ids, collection, visualise=False):
    """
    Extract the open time of pull requests and optionally visualise it.
    """
    pr_open_to_close_times = {}
    for pull_request_id in pull_request_ids:
        events = get_events_for_object(pull_request_id, collection)
        for event in events:
            if "open" in event["type"]:
                open_time = datetime.fromisoformat(event["time"])
                if pull_request_id in pr_open_to_close_times:
                    pr_open_to_close_times[pull_request_id]["open"] = open_time
                    close_time = pr_open_to_close_times[pull_request_id]["close"]
                    pr_open_to_close_times[pull_request_id]["duration"] = (close_time - open_time).total_seconds() / 3600
                else:
                    pr_open_to_close_times.setdefault(pull_request_id, {})["open"] = open_time
            if "close" in event["type"]:
                close_time = datetime.fromisoformat(event["time"])
                if pull_request_id in pr_open_to_close_times and "open" in pr_open_to_close_times[pull_request_id]:
                    open_time = pr_open_to_close_times[pull_request_id]["open"]
                    pr_open_to_close_times[pull_request_id]["close"] = close_time
                    pr_open_to_close_times[pull_request_id]["duration"] = (close_time - open_time).total_seconds() / 3600
                else:
                   pr_open_to_close_times.setdefault(pull_request_id, {})["close"] = close_time
            if "merge" in event["type"]:
                merge_time = datetime.fromisoformat(event["time"])
                pr_open_to_close_times.setdefault(pull_request_id, {})["merge"] = merge_time

    if visualise:
        plt.figure(figsize=(10, 5))
        """Plot PR open times as a histogram"""
        # plt.hist([data["duration"] for data in pr_open_to_close_times.values() if "duration" in data], bins=30, edgecolor='black')
        # plt.xlabel('Open Time (hours)')
        # plt.ylabel('Frequency')
        # plt.title('Distribution of Pull Request Open Times')
        """Plot PR open times as a boxplot"""
        # durations = [data["duration"] for data in pr_open_to_close_times.values() if "duration" in data]
        # plt.boxplot(durations, vert=False)
        # plt.xlabel('Open Time (hours)')
        # plt.title('Boxplot of Pull Request Open Times')
        """Plot PR open times as a timeline"""
        def plot_pr_timeline(pr_open_to_close_times):
            # Prepare list of (open, close, pr_id)
            pr_intervals = []
            for pr_id, data in pr_open_to_close_times.items():
                if "open" in data and "merge" in data:
                    pr_intervals.append((data["open"], data["merge"], pr_id, "merge"))
                elif "open" in data and "close" in data:
                    pr_intervals.append((data["open"], data["close"], pr_id, "close"))
            # Sort by open time
            pr_intervals.sort(key=lambda x: x[0])

            # Assign stack levels to avoid overlap
            levels = []
            for open_time, close_time, _, type in pr_intervals:
                # Find the lowest available level
                for i, last_close in enumerate(levels):
                    if open_time > last_close:
                        levels[i] = close_time
                        break
                else:
                    levels.append(close_time)
                    i = len(levels) - 1
                # Store the level index
                yield (open_time, close_time, i, type)
        intervals = list(plot_pr_timeline(pr_open_to_close_times))
        plt.figure(figsize=(12, 0.5 * (max([lvl for _, _, lvl, _ in intervals]) + 2)))
        for open_time, close_time, level, type in intervals:
            plt.hlines(level, open_time, close_time, color='tab:blue', linewidth=2)
            plt.plot(open_time, level, 'o', color='green')  # Open marker
            if type == "merge":
                plt.plot(close_time, level, 'o', color='green')   # Close marker
            else:
                plt.plot(close_time, level, 'x', color='red')
            plt.plot()
        plt.xlabel("Time")
        plt.ylabel("Concurrent PRs")
        plt.title("Pull Request Overlaps Timeline")
        plt.yticks(range(max([lvl for _, _, lvl, _ in intervals]) + 1))
        plt.tight_layout()
        plt.rcParams['axes.facecolor'] = 'white'
        plt.rcParams['axes.edgecolor'] = 'black'
        plt.rcParams['axes.labelcolor'] = 'black'
        plt.rcParams['xtick.color'] = 'black'
        plt.rcParams['ytick.color'] = 'black'
        plt.rcParams['legend.edgecolor'] = 'black'
        plt.rcParams['legend.facecolor'] = 'black'
        plt.rcParams['axes.spines.top'] = False
        plt.rcParams['axes.spines.right'] = False
        plt.show()
        
    else:
        return pr_open_to_close_times
    
def pull_request_review_iterations(pull_request_ids, collection, visualise=False):
    """
    Extract the number of review iterations for each pull request and optionally visualise it.
    """
    pr_review_iterations = {}
    for pull_request_id in pull_request_ids:
        events = get_events_for_object(pull_request_id, collection)
        events = sorted(events, key=lambda x: datetime.fromisoformat(x["time"]))
        review_iterations = 0
        started_iteration = False
        for event in events:
            if "commit" in event["type"]:
                started_iteration = True
            if "review" in event["type"].split("_")[-1]:
                if started_iteration:
                    review_iterations += 1
                    started_iteration = False
        pr_review_iterations[pull_request_id] = review_iterations

    if visualise:
        plt.figure(figsize=(10, 5))
        plt.bar(list(pr_review_iterations.keys()), list(pr_review_iterations.values()))
        plt.xlabel('Pull Request ID')
        plt.ylabel('Number of Review Iterations')
        plt.yticks(range(0, max(pr_review_iterations.values()) + 2))
        plt.title('Number of Review Iterations per Pull Request')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.rcParams['axes.facecolor'] = 'white'
        plt.rcParams['axes.edgecolor'] = 'black'
        plt.rcParams['axes.labelcolor'] = 'black'
        plt.rcParams['xtick.color'] = 'black'
        plt.rcParams['ytick.color'] = 'black'
        plt.rcParams['legend.edgecolor'] = 'black'
        plt.rcParams['legend.facecolor'] = 'black'
        plt.rcParams['axes.spines.top'] = False
        plt.rcParams['axes.spines.right'] = False
        plt.show()
    else:
        return pr_review_iterations