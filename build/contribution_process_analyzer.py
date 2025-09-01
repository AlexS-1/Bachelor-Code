from heapq import merge
from math import e
from typing import Dict, List
import pandas as pd
from pyparsing import Any
from sympy import N
from build.code_quality_visualizer import get_object
from build.utils import _set_plot_style_and_plot, date_1970
from build.database_handler import get_commits, get_events_for_eventType, get_events_for_object, get_is_user_bot, get_ocel_data, get_object_type_by_type_name, get_pull_requests, get_related_objectIds_for_event, get_type_of_object
from datetime import datetime, tzinfo, timezone
from matplotlib import pyplot as plt
from itertools import combinations

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
        _set_plot_style_and_plot()
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
                    if "close" in pr_open_to_close_times[pull_request_id]:
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
        _set_plot_style_and_plot()
        
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
        _set_plot_style_and_plot()
    else:
        return pr_review_iterations
    
def pull_request_approving_reviews(pull_request_ids, collection, visualise=False):
    pr_attributes = {}
    pr_label_sets = {}
    pr_approvals = {}
    for pull_request_id in pull_request_ids:
        events = get_events_for_object(pull_request_id, collection)
        events = sorted(events, key=lambda x: datetime.fromisoformat(x["time"]))
        pr_labels = []
        approvals = 0
        for event in events:
            if "add_label" in event["type"]:
                pr_labels.append(_get_local_attribute_value(event, "label"))
            if "approve" in event["type"]:
                approvals += 1
        pr_attributes[pull_request_id] = {
            "labels": pr_labels,
            "approvals": approvals
        }
    
    if visualise:
        plt.figure(figsize=(10, 5))
        labels = [pr["labels"] for pr in pr_attributes.values()]
        approvals = [pr["approvals"] for pr in pr_attributes.values()]
        ids = list(pr_attributes.keys())
        plt.plot(ids, approvals, tick_label=list(pr_attributes.keys()))
        plt.plot(ids, [len(label_set) for label_set in labels], tick_label=list(pr_attributes.keys()), label='Labels')
        plt.hlines(sum(approvals)/len(approvals), ids[0], ids[1], color='orange', label='Average Approvals')
        plt.xlabel('Pull Request ID')
        plt.ylabel('Number of Approving Reviews')
        plt.title('Number of Approving Reviews per Pull Request')
        _set_plot_style_and_plot()
    else:
        return pr_attributes
        
def plot_pr_issue_label_distribution(collection: str, top_n: int = 10, include_empty: bool = False, figsize=(8, 6)):
    """
    Plot distribution of the most common issue_label values in pull requests for a collection.
    Handles issue_label stored as str, comma/semicolon-separated str, list[str], or list[dict{name}].
    Returns the counts Series.
    Args:
        collection (str): The collection name.
        top_n (int): The number for specifying how many labels to include.
        include_empty (bool): Whether to exclude counts for PRs without labels.
        figsize (tuple): The figure size for the plot.
    Returns:
        pd.Series: The counts of issue labels.
    """
    pull_requests = get_pull_requests(collection) or []
    label_list = []
    for pr in pull_requests:
        labels = _get_local_attribute_value(pr, "issue_label")
        if labels is None:
            print(f"ERROR: No issue_label found for PR {pr['_id']}")
            continue
        parsed_labels = _parse_labels(labels, include_empty)
        label_list.extend(parsed_labels)

    if len(label_list) == 0:
        print("WARNING: No issue_labels were found.")
        return pd.Series(dtype=int)

    counts = pd.Series(label_list).value_counts()
    top_labels = counts.head(top_n)[::-1]  # reverse for horizontal bar plot (largest on top)

    plt.figure(figsize=figsize)
    plt.barh(top_labels.index, top_labels.to_numpy(dtype=int), color="#fad7ac")
    plt.xlabel("Count")
    plt.title(f"Top {min(top_n, len(counts))} Issue Labels in Pull Requests ({collection})", color="black")
    for index, value in enumerate(top_labels.values):
        plt.text(value, index, f" {value}", va="center")
    plt.tight_layout()
    _set_plot_style_and_plot()

    return counts

def plot_pr_secondary_issue_label_distribution(collection: str, label: str, top_n: int = 10, include_single_secondary: bool = False, figsize=(8, 6)):
    """
    For PRs whose issue_label contains 'good first issue', compute distribution of
    the other labels present on those PRs. Returns a pandas Series (counts).
    Args:
        collection (str): The collection name.
        label (str): The specific label to analyze.
        top_n (int): The number for specifying how many labels to include.
        include_single_secondary (bool): Whether to include counts for PRs where only the specified label is present
        figsize (tuple): The figure size for the plot.
    Returns:
        pd.Series: The counts of issue labels.
    """
    pull_requests = get_pull_requests(collection) or []
    counts = {}
    label = label.lower()
    for pr in pull_requests:
        if not _pr_has_label(pr, label):
            continue
        labels_string = _get_local_attribute_value(pr, "issue_label")
        if labels_string is None:
            print(f"ERROR: No issue_label found for PR {pr['_id']}")
            continue
        labels = _parse_labels(labels_string, False)
        if labels == [label] and include_single_secondary:
            counts[f"<Only {label}>"] = counts.get("<Only {label}>", 0) + 1
        for lbl in labels:
            if label in str(lbl).lower():
                continue
            counts[lbl] = counts.get(lbl, 0) + 1

    if not counts:
        print(f"WARNING: No labels found on PRs with label: {label} in collection: {collection}")
        return pd.Series(dtype=int)

    series = pd.Series(counts).sort_values(ascending=False)
    top_labels = series.head(top_n)[::-1]

    plt.figure(figsize=(6, 6))
    plt.barh(top_labels.index, top_labels.to_numpy(dtype=int), color="#fad7ac")
    plt.xlabel("Count")
    plt.title(f"Top {min(top_n, len(series))} other labels on 'good first issue' PRs ({collection})")
    for index, value in enumerate(top_labels.to_numpy(dtype=int)):
        plt.text(value, index, f" {int(value)}", va="center")
    plt.tight_layout()
    _set_plot_style_and_plot()

    return series

def pull_request_approving_reviews_grouped(pull_request_ids,
                                           collection,
                                           visualise=False,
                                           min_prs_per_group=1):
    """
    Group PRs by every non-empty combination (subset) of their labels.

    For a PR with labels {A,B,C} it contributes to:
      {A}, {B}, {C}, {A,B}, {A,C}, {B,C}, {A,B,C}

    Args:
        pull_request_ids (list[str])
        collection (str)
        visualise (bool): show bar chart of average approvals per label group
        min_prs_per_group (int): filter out sparse groups

    """
    pr_label_sets = {}
    pr_approvals = {}
    for pull_request_id in pull_request_ids:
        events = get_events_for_object(pull_request_id, collection)
        events = sorted(events, key=lambda x: datetime.fromisoformat(x["time"]))
        labels = set()
        approvals = 0
        for event in events:
            etype = event["type"]
            if "add_label" in etype:
                labels.add(_get_local_attribute_value(event, "label"))
            if "approve" in etype:
                approvals += 1
        if labels:
            pr_label_sets[pull_request_id] = labels
            pr_approvals[pull_request_id] = approvals

    # Step 2: build power-set groups (exclude empty)
    group_data = {}

    def all_non_empty_subsets(labels_set):
        labels_list = sorted(labels_set)
        for r in range(1, len(labels_list) + 1):
            for comb in combinations(labels_list, r):
                yield comb

    for pr_id, labels in pr_label_sets.items():
        approvals = pr_approvals.get(pr_id, 0)
        for subset in all_non_empty_subsets(labels):
            if subset not in group_data:
                group_data[subset] = {"prs": [], "approvals": []}
            group_data[subset]["prs"].append(pr_id)
            group_data[subset]["approvals"].append(approvals)

    # Step 3: compute aggregates & filter
    filtered = {}
    for group_key, payload in group_data.items():
        n = len(payload["prs"])
        payload_with_av = {**payload, "avg_approvals": sum(payload["approvals"]) / n if n >= min_prs_per_group else 0.0, "n_prs": n}
        filtered[group_key] = payload_with_av

    # Step 4: visualisation
    if visualise and filtered:
        # Prepare plotting order: larger groups first then by avg approvals
        order = sorted(filtered.items(),
                       key=lambda kv: (len(kv[0]), kv[1]["avg_approvals"]),
                       reverse=True)
        labels_txt = [" | ".join(k) for k, _ in order]
        avgs = [v["avg_approvals"] for _, v in order]

        # Color mapping: base color per single label; combos take color of first label
        base_palette = plt.get_cmap("tab20")
        single_labels = sorted({lab for g in filtered.keys() if len(g) == 1 for lab in g})
        color_map = {lab: base_palette(i % 20) for i, lab in enumerate(single_labels)}

        colors = []
        for g, _ in order:
            primary = g[0]
            colors.append(color_map.get(primary, "#808080"))

        plt.figure(figsize=(min(18, 0.6 * len(order) + 4), 6))
        bars = plt.bar(range(len(order)), avgs, color=colors)

        # Annotate n
        for i, (_, payload) in enumerate(order):
            plt.text(i, avgs[i] + 0.02, f"n={payload['n_prs']}", ha="center", va="bottom", fontsize=8, rotation=90)

        plt.xticks(range(len(order)), labels_txt, rotation=90)
        plt.ylabel("Average Approvals")
        plt.title("Average Approvals per Label Combination (power-set groups)")

        # Legend (single labels)
        
        plt.legend(single_labels, title="Primary Label", bbox_to_anchor=(1.02, 1), loc="upper left")
        plt.tight_layout()
        _set_plot_style_and_plot()
    else: 
        result = {"groups": filtered}
        return result
    
def pull_request_bot_ratio(pull_request_ids, collection, visualise=False):
    """
    Compute bot vs total event counts for the given PRs.
    Returns both per-event-type totals and bot-only counts, plus debug stats.
    """
    event_by_bot = {}
    event_not_by_bot = {}
    event_by_type = {}
    totals = {
        "events_processed": 0,
        "events_with_actor": 0,
        "bot_events": 0,
        "non_bot_events": 0,
        "unmatched_actor": [],
        "user_lookup_failed": 0,
    }

    for pull_request_id in pull_request_ids:
        if int(pull_request_id) < 30000:
            events = get_events_for_object(pull_request_id, collection)
            events = sorted(events, key=lambda x: datetime.fromisoformat(x["time"]))

            for event in events:
                etype = event["type"]
                event_by_type[etype] = event_by_type.get(etype, 0) + 1
                totals["events_processed"] += 1

                actor_id, origin = _extract_event_actor(event, collection)
                if actor_id:
                    totals["events_with_actor"] += 1
                    is_bot = get_is_user_bot(actor_id, collection)
                    if is_bot == True:
                        totals["bot_events"] += 1
                        event_by_bot[etype] = event_by_bot.get(etype, 0) + 1
                    elif is_bot == False:
                        totals["non_bot_events"] += 1
                        event_not_by_bot[etype] = event_not_by_bot.get(etype, 0) + 1
                    else:
                        totals["unmatched_actor"].append(actor_id)
                else:
                    totals["user_lookup_failed"] += 1

    # Log summary
    total_events = totals["events_processed"]
    matched = totals["events_with_actor"]
    print(f"LOG: Processed {total_events} events across {len(pull_request_ids)} PRs.")
    print(f"LOG: Actor matched for {matched} events ({(matched/total_events*100 if total_events else 0):.1f}%).")
    print(f"LOG: Bot events: {totals['bot_events']} ({(totals['bot_events']/total_events*100 if total_events else 0):.1f}%).")

    if visualise:
        print("WARNING: Visualisation not implemented yet")
    else:
        return {
            "by_bot": event_by_bot,
            "not_by_bot": event_not_by_bot,
            "totals": event_by_type,
            "totals": totals
        }

# Helper methods for local use

def _extract_event_actor(event, collection):
    prefer = ["by", "author", "committer", "merged_by", "closed_by", "requested_by", "reviewer", "assignee", "user", "actor"]
    rels = event.get("relationships", [])
    # exact or substring match
    for pref in prefer:
        for rel in rels:
            qual = rel.get("qualifier", "")
            if qual == pref or pref in qual:
                oid = rel.get("objectId")
                if oid and get_type_of_object(oid, collection) == "user":
                    return oid, "relationship"

    return None, "none"

def _parse_labels(labels_string: str, include_empty: bool) -> list[str]:
    """Get the labels as list for a given string or list input."""
    output = []
    if labels_string is None:
        return output
    if isinstance(labels_string, str):
        labels_string = labels_string.replace(";", ",")
        labels_string = labels_string.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
        parts = [label.strip() for label in labels_string.split(",") if label.strip() != "" or include_empty]
        return parts
    if isinstance(labels_string, list):
        for label in labels_string:
            if isinstance(label, str):
                output.append(label.strip())
        return output
    return output

def _get_local_attribute_value(object, attribute_name):
    for a in object.get("attributes", []):
        if a.get("name") == attribute_name:
            return str(a.get("value"))
        
def _pr_has_label(pull_request: Dict[str, Any], label: str) -> bool:
    labels_string = _get_local_attribute_value(pull_request, "issue_label")
    if labels_string is None:
        return False
    return label in labels_string.lower()
        