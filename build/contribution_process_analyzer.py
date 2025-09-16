from collections import defaultdict
from tkinter import font
from typing import Dict
import numpy as np
import pandas as pd
from pyparsing import Any
from build.code_quality_visualizer import get_object
from build.contribution_process_miner import _actor_from_event, get_open_pr_event_id, is_bot_user
from build.utils import _set_plot_style_and_plot
from build.database_handler import get_attribute_value, get_event, get_events, get_events_for_object, get_is_user_bot, get_pull_requests, get_type_of_object, get_objects
from datetime import datetime
from matplotlib import legend, pyplot as plt
from itertools import combinations
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

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
    # Plot PR open times as a histogram
        plt.hist([data["duration"] for data in pr_open_to_close_times.values() if "duration" in data], bins=30, edgecolor='black')
        plt.xlabel('Open Time (hours)')
        plt.ylabel('Frequency')
        plt.title('Distribution of Pull Request Open Times')
    # Plot PR open times as a boxplot
        # durations = [data["duration"] for data in pr_open_to_close_times.values() if "duration" in data]
        # plt.boxplot(durations, vert=False)
        # plt.xlabel('Open Time (hours)')
        # plt.title('Boxplot of Pull Request Open Times')
    # Plot PR open times as a timeline
        # def plot_pr_timeline(pr_open_to_close_times):
        #     # Prepare list of (open, close, pr_id)
        #     pr_intervals = []
        #     for pr_id, data in pr_open_to_close_times.items():
        #         if "open" in data and "merge" in data:
        #             pr_intervals.append((data["open"], data["merge"], pr_id, "merge"))
        #         elif "open" in data and "close" in data:
        #             pr_intervals.append((data["open"], data["close"], pr_id, "close"))
        #     # Sort by open time
        #     pr_intervals.sort(key=lambda x: x[0])

        #     # Assign stack levels to avoid overlap
        #     levels = []
        #     for open_time, close_time, _, type in pr_intervals:
        #         # Find the lowest available level
        #         for i, last_close in enumerate(levels):
        #             if open_time > last_close:
        #                 levels[i] = close_time
        #                 break
        #         else:
        #             levels.append(close_time)
        #             i = len(levels) - 1
        #         # Store the level index
        #         yield (open_time, close_time, i, type)
        # intervals = list(plot_pr_timeline(pr_open_to_close_times))
        # plt.figure(figsize=(12, 0.5 * (max([lvl for _, _, lvl, _ in intervals]) + 2)))
        # for open_time, close_time, level, type in intervals:
        #     plt.hlines(level, open_time, close_time, color='tab:blue', linewidth=2)
        #     plt.plot(open_time, level, 'o', color='green')  # Open marker
        #     if type == "merge":
        #         plt.plot(close_time, level, 'o', color='green')   # Close marker
        #     else:
        #         plt.plot(close_time, level, 'x', color='red')
        #     plt.plot()
        # plt.xlabel("Time")
        # plt.ylabel("Concurrent PRs")
        # plt.title("Pull Request Overlaps Timeline")
        # plt.yticks(range(max([lvl for _, _, lvl, _ in intervals]) + 1))
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
    _pr_label_sets = {}
    _pr_approvals = {}
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

def plot_pr_secondary_issue_label_distribution(collection: str, label: str, top_n: int = 10, include_single_secondary: bool = False, figsize=(4, 6)):
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

    plt.figure(figsize=figsize)
    plt.barh(top_labels.index, top_labels.to_numpy(dtype=int), color="#fad7ac")
    plt.xticks(fontsize=18)
    plt.gca().xaxis.set_major_locator(mticker.MaxNLocator(nbins=6, prune='both'))
    plt.yticks(fontsize=18)
    plt.xlabel("Count", fontsize=18)
    # plt.title(f"Top {min(top_n, len(series))} Other Labels on Pull Requests Labelled {label} ({collection})")
    for index, value in enumerate(top_labels.to_numpy(dtype=int)):
        plt.text(value, index, f" {int(value)}", va="center", fontsize=18)
    plt.tight_layout()
    plt.savefig(f"thesis-writing/thesis-main/figures/{collection}-gfi-labels.pdf")
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
        order = sorted(
            filtered.items(),
            key=lambda kv: (len(kv[0]), kv[1]["avg_approvals"]),
            reverse=True,
        )
        labels_txt = [" | ".join(k) for k, _ in order]
        avgs = [v["avg_approvals"] for _, v in order]

        # Color mapping: base color per single label; combos take color of first label
        base_palette = plt.get_cmap("tab20")
        single_labels = sorted({lab for g in filtered.keys() if len(g) == 1 for lab in g})
        color_map = {lab: base_palette(i % 20) for i, lab in enumerate(single_labels)}
        colors = [color_map.get(g[0], "#808080") for g, _ in order]

        plt.figure(figsize=(min(18, 0.6 * len(order) + 4), 6))
        _bars = plt.bar(range(len(order)), avgs, color=colors)

        # Annotate n
        for i, (_, payload) in enumerate(order):
            plt.text(
                i,
                avgs[i] + 0.02,
                f"n={payload['n_prs']}",
                ha="center",
                va="bottom",
                fontsize=8,
                rotation=90,
            )

        plt.xticks(range(len(order)), labels_txt, rotation=90)
        plt.ylabel("Average Approvals")
        plt.title("Average Approvals per Label Combination (power-set groups)")
        plt.legend(single_labels, title="Primary Label", bbox_to_anchor=(1.02, 1), loc="upper left")
        plt.tight_layout()
        _set_plot_style_and_plot()
        return {"groups": filtered}

    return {"groups": filtered}
    
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

                actor_id = _extract_event_actor(event)
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
            "by_type": event_by_type,
            "summary": totals
        }

def generate_author_distribution_for_issue_labels(collection, analysis_labels, plot: bool = True):
    """
    Create a DataFrame with author-type distributions per category.
    Args:
        collection (str): The collection to analyse the PRs in
        analysis_labels (list(str)): The issue labels to group the author distribtuions by
        plot (bool): Wether or not to plot the results (default = True)
    Returns:
        pd.DataFrame: Indexed by category with columns ['new','bot','experienced','total']
    """

    # expected percentages as decimals (new, bot, experienced)
    _percents = {
        "Documentation": (0.40, 0.20, 0.40),
        "Good First Issue": (0.80, 0.10, 0.10),
        "Good First Review": (0.15, 0.05, 0.80),
        r"Average \ {Good First Issue, Good First Review}": (0.075, 0.075, 0.85),
        "PRs Average": (0.09, 0.09, 0.82),
    }

    # Collect author distribution per pull request
    rows = []
    actors_per_pr = {}
    pull_requests = get_pull_requests(collection)
    for pr in pull_requests:
        issue_labels = get_attribute_value(pr["_id"], "issue_label", collection)
        open_event_id = get_open_pr_event_id(pr["_id"], collection)
        opener = ""
        opener_bot = False
        if open_event_id:
            event = get_event(open_event_id, collection)
            if event:
                opener = _actor_from_event(event) or ""
                opener_bot = is_bot_user(opener, collection) or False
        res_labels = []
        for label in analysis_labels:
            if label in issue_labels:
                res_labels.append(label)
        
        actors_per_pr[pr["_id"]] = {
            "opener": opener,
            "is_bot": opener_bot,
            "labels": res_labels,
        }

    # Group author distribution by issue_labels
    results = {}
    already_contributed = set()
    for _, values in actors_per_pr.items():
        categories = ["Average"]
        if values["labels"] == []:
            categories.append("Other")
        else: 
            categories.extend(values["labels"])
        for category in categories:
            n_new, n_bot, n_other = results.setdefault(category, (0, 0, 0))
            if values["opener"] not in already_contributed:
                n_new += 1
            elif values["is_bot"]:
                n_bot += 1
            else:
                n_other += 1
            results[category] = (n_new, n_bot, n_other)
        already_contributed.add(values["opener"])
    
    # Add categories to DataFrame
    for category in ["Average", "Other"] + analysis_labels:
        n_new, n_bot, n_other = results.get(category, (0, 0, 0))
        rows.append({"category": category, "new": n_new, "bot": n_bot, "experienced": n_other, "total": sum(results.get(category, (0, 0, 0)))})
    df = pd.DataFrame(rows).set_index("category")[["new", "bot", "experienced", "total"]]

    # Plot results if specified
    if plot:
        props = df[["new", "bot", "experienced"]].div(df["total"], axis=0)
        colors = {"new": "#4C72B0", "bot": "#DD8452", "experienced": "#55A868"}
        y = np.arange(len(df))
        height = 0.6


        plt.figure(figsize=(10, max(4, len(df) * 0.7)))
        plt.title(f"Distribution of Pull Request Authors by Related Issue labels ({collection})")
        left = np.zeros(len(df))
        for col in ["new", "bot", "experienced"]:
            vals = np.array(props[col].values)
            plt.barh(y, vals, left=left, height=height, color=colors[col], label=col.title())
            # annotate percentage if wide enough
            for i, (l, v) in enumerate(zip(left, vals)):
                if v > 0.04:
                    plt.text(l + v/2, i, f"{int(round(v*100))}%", ha="center", va="center", color="white", fontsize=9)
            left += vals

        # annotate absolute totals on right
        for i, tot in enumerate(df["total"].values):
            plt.text(1.02, i, f"n={tot}", va="center", fontsize=9)

        plt.xlim(0, 1.15)
        plt.xlabel("Proportion of Author Types Normalized to 1")
        ax = plt.gca()
        ax.set_xticks([])
        ax.set_xticklabels([])
        label_list = df.index.astype(str).tolist()  # make Sequence[str] for type checker
        plt.yticks(y, label_list)
        plt.gca().invert_yaxis()
        plt.tight_layout()
        plt.legend(loc="lower center", bbox_to_anchor=(-0.3, -0.15), ncol=1)
        _set_plot_style_and_plot()

    return df

def repo_inventory_stats(collections: list[str] | None = None, return_dataframe: bool = True):
    """
    Compute repository inventory stats for one or more collections.

    For each collection (repository), return:
      - total_objects: total number of OCEL objects
      - total_events: total number of OCEL events
      - objects_per_type: dict mapping object type -> count

    Args:
        collections (list[str] | None): Repository collections to inspect. If None,
            defaults to the three investigated repositories ["scikit-learn", "matplotlib", "edx-platform"].
        return_dataframe (bool): If True, also return a tidy DataFrame with columns
            [total_objects, total_events, obj_<type>...].

    Returns:
        dict | dict[str, Any]:
            If return_dataframe=True: {"stats": <per-repo dict>, "table": pandas.DataFrame}
            Else: <per-repo dict> only.
    """
    repos = collections or ["scikit-learn", "matplotlib", "edx-platform"]
    results: dict[str, dict] = {}

    for col in repos:
        type_counts: dict[str, int] = defaultdict(int)

        # Count objects and break down by type
        total_objects = 0
        try:
            objs_cursor = get_objects(col) or []
            for obj in objs_cursor:
                total_objects += 1
                otype = obj.get("type", "unknown")
                type_counts[otype] = type_counts.get(otype, 0) + 1
        except:
            total_objects = 0

        # Count events
        total_events = 0
        try:
            ev_cursor = get_events(col) or []
            for _ in ev_cursor:
                total_events += 1
        except:
            total_events = 0

        results[col] = {
            "total_objects": total_objects,
            "total_events": total_events,
            "objects_per_type": dict(sorted(type_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        }

    if return_dataframe:
        rows = []
        # Build a wide table with one row per repo and columns per object type
        for col, stats in results.items():
            row = {
                "collection": col,
                "total_objects": stats["total_objects"],
                "total_events": stats["total_events"],
            }
            for otype, count in stats["objects_per_type"].items():
                row[f"obj_{otype}"] = count
            rows.append(row)

        table = pd.DataFrame(rows).set_index("collection").sort_index()
        return {"stats": results, "table": table}

    return results

_bot_ids = {
    "matplotlib": [
        "lumberbot-app[bot]",
        "codecov[bot]",
        "github-actions[bot]",
        "Matplotlib Developers",
        "dependabot[bot]",
        "Codecov",
        "ALL",
        "pre-commit-ci[bot]",
        "csc510-team5",
        "AppVeyor Systems Inc.",
        "github-advanced-security[bot]",
        "Dependabot",
        "Copilot"
    ],
    "scikit-learn": [
        "scikit-learn-bot",
        "Copilot",
        "github-actions[bot]",
        "Open Source Maintainers on GitHub [moved]",
        "dependabot[bot]",
        "codecov[bot]",
        "github-advanced-security[bot]",
        "Dependabot",
        "Women in Machine Learning & Data Science",
        "scikit-learn",
        "azure-pipelines[bot]",
        "github-merge-queue[bot]",
        "beartype",
        "azure-pipelines",
        "Article",
        "mergify[bot]",
        "neurodata"
    ],
    "edx-platform": [
        "github-actions[bot]",
        "dependabot[bot]",
        "Dependabot",
        "Open edX",
        "Incresco",
        "Copilot"
    ]
}

def plot_bot_activity(
        collection, 
        freq="M", 
        ma_window=3, 
        start_date=datetime(2020, 1, 1), 
        end_date=datetime(2025, 12, 31), 
        yscale: str = "linear", 
        eps: float = 1e-2, 
        ylim: tuple | None = None, 
        ylabel: bool = True,
        figsize=(6, 4),
        plot_legend=False):
    """
    Stacked area of bot vs non-bot events with moving average smoothing.
    No percentage axis; bot proportion visible via relative area.

    Args:
        collection: repository/collection name
        freq: resample frequency (e.g., "M", "W", "D", "Q")
        ma_window: moving average window
        start_date, end_date: time window
        yscale: "linear" (default) or "log"
        eps: small positive value to replace zeros when using log scale
        ylim: optional (ymin, ymax)
    """
    start_date = pd.to_datetime(start_date, utc=True)
    end_date = pd.to_datetime(end_date, utc=True)
    bot_ids = _bot_ids[collection]
    events = get_events(collection)
    
    rows = []
    for ev in events:
        ts = datetime.fromisoformat(ev.get("time"))
        if not (start_date <= ts <= end_date):
            continue
        is_bot = 0
        for rel in ev.get("relationships", []) or []:
            if "by" in (rel.get("qualifier") or ""):
                if rel.get("objectId") in bot_ids:
                    is_bot = 1
                break
        rows.append({"time": ts, "is_bot": is_bot})

    if not rows:
        print("No events in interval.")
        return pd.DataFrame()

    df = (pd.DataFrame(rows)
            .sort_values("time")
            .set_index("time"))

    agg = pd.DataFrame({
        "events": df["is_bot"].resample(freq).count(),
        "bot_events": df["is_bot"].resample(freq).sum()
    }).loc[start_date:end_date]

    agg["non_bot"] = agg["events"] - agg["bot_events"]

    ma = agg[["bot_events","non_bot","events"]].rolling(ma_window, min_periods=1).mean()
    ma = ma.rename(columns={
        "bot_events":"bot_events_ma",
        "non_bot":"non_bot_ma",
        "events":"events_ma"
    })

    plot_df = pd.concat([agg, ma], axis=1)

    x = plot_df.index
    bot_smoothed = plot_df["bot_events_ma"]
    non_bot_smoothed = plot_df["non_bot_ma"]

    # Clip zeros for log scale to avoid -inf
    if yscale == "log":
        bot_smoothed = bot_smoothed.clip(lower=eps)
        non_bot_smoothed = non_bot_smoothed.clip(lower=eps)
        raw_bot = agg["bot_events"].clip(lower=eps)
        raw_total = plot_df["events"].clip(lower=eps)
    else:
        raw_bot = agg["bot_events"]
        raw_total = plot_df["events"]

    _, ax = plt.subplots(figsize=figsize)
    plt.rcParams.update({'font.size': 20})
    ax.stackplot(
        x,
        raw_bot,
        raw_total - raw_bot,
        colors=["#45372c", "#bac8d3"],
        labels=["Bot", "Non-Bot"],
        alpha=0.95
    )
    frequency = freq.replace("ME", "Month").replace("D", "Day").replace("W", "Week").replace("Q", "Quarter")

    # ...existing code...
    ax.set_xlim(start_date, end_date)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # Get the first year from the data
    first_year = plot_df.index.year.min()
    # Set the ticks to start from the second year
    ax.set_xticks([mdates.date2num(datetime(year, 1, 1)) for year in range(first_year + 1, datetime.now().year + 1)])
    if ylabel:
        ax.set_ylabel(f"Events per {frequency}")

    if plot_legend:
        ax.legend(loc="upper right")

    # Apply scale and limits
    ax.set_yscale(yscale)
    if ylim:
        ax.set_ylim(*ylim)
    elif yscale == "linear":
        ax.set_ylim(0, 4500)

    plt.tight_layout()
    plt.savefig(f"thesis-writing/thesis-main/figures/{collection}-bot-percentage.pdf", format="pdf", bbox_inches="tight")
    _set_plot_style_and_plot()
    return plot_df

def list_bot_events_per_type(collection: str, event_type: str, fast=True):
    """
    Print and return approve_review events where the actor is a bot.
    Returns a list of dicts (and a pandas DataFrame if pandas is available).
    """
    events = get_events(collection)
    rows = []
    count_scanned = 0
    for ev in events:
        if ev.get("type") != event_type:
            continue
        actor = _extract_event_actor(ev)
        if actor in _bot_ids[collection]:
            if fast:
                count_scanned += 1
            else:
                rows.append({
                    "event_id": ev.get("_id"),
                    "time": ev.get("time"),
                    "actor": actor,
                    "repo": collection,
                })

    # Pretty print and optional DataFrame
    if not fast:
        df = pd.DataFrame(rows).sort_values("time")
        print(f"Found {len(df)} {event_type} event(s) by bots in '{collection}':")
        display(df)
        return len(df)
    else:
        return count_scanned

def plot_top_bot_event_types(top_n: int = 10, figsize=(10, 6), all_repos=False, show_title=False, just_data=False):
    """
    Plot the top N event types with highest bot activity.
    When all_repos=False (default):
                - For a single collection, show the top_n event types ranked by total count (desc),
                    then by bot percentage (desc). Bars show TOTAL counts (not percentage).

    When all_repos=True:
        - Consider the three studied repositories ["scikit-learn", "matplotlib", "edx-platform"].
        - Select the top_n event types by TOTAL count across all three repos.
                - Plot a grouped bar chart with one bar per repo for each event type,
                    where the bar height is the TOTAL count for that repo.
        - Repository colors are defined at the start of the method.
    """

    # Repository colors for multi-repo view
    repo_colors = {
        "scikit-learn": "#4C72B0",  # blue
        "matplotlib": "#55A868",    # green
        "edx-platform": "#DD8452",  # orange
    }
    repos = ["scikit-learn", "matplotlib", "edx-platform"]
    per_repo_type_counts: dict[str, dict[str, int]] = {r: defaultdict(int) for r in repos}
    per_repo_bot_counts: dict[str, dict[str, int]] = {r: defaultdict(int) for r in repos}

    # Gather counts per repo
    for repo in repos:
        events = get_events(repo) or []
        for ev in events:
            ev_type = ev.get("type")
            actor = _actor_from_event(ev)
            if actor in _bot_ids[repo]:
                per_repo_bot_counts[repo][ev_type] += 1
            per_repo_type_counts[repo][ev_type] += 1
    if just_data:
        return per_repo_bot_counts, per_repo_type_counts
    # Total across repos per event type
    global_totals: dict[str, int] = defaultdict(int)
    for repo in repos:
        for ev_type, cnt in per_repo_type_counts[repo].items():
            global_totals[ev_type] += cnt

    # Choose top_n by total count across repos (stable tie-breaker by name)
    selected_types = [
        et for et, _ in sorted(
            global_totals.items(),
            key=lambda kv: (kv[1], kv[0]),
            reverse=True
        )[:top_n]
    ]

    # Prepare grouped data: per event type, bot percentage for each repo
    x_labels = selected_types
    x = np.arange(len(x_labels))
    width = 0.33

    plt.figure(figsize=figsize)

    bars_per_repo = []
    # Slimmer bars; width relative to number of repos to keep spacing tight
    width = min(0.18, 0.7 / max(1, len(repos)))
    for i, repo in enumerate(repos):
        totals_vals = []
        share_pcts_for_ann = []
        for et in x_labels:
            bot_count = per_repo_bot_counts[repo].get(et, 0)
            total_count = per_repo_type_counts[repo].get(et, 0)
            totals_vals.append(bot_count)
            pct = (bot_count / total_count) if total_count > 0 else 0
            share_pcts_for_ann.append(pct)
        bars = plt.bar(x + (i - 1) * width, totals_vals, width=width, color=repo_colors.get(repo, "#808080"), alpha=0.9, label=repo)
        
        # annotate repo share % on each bar
        for bar, pct in zip(bars, share_pcts_for_ann):
            h = bar.get_height()
            if h > 0:
                plt.text(bar.get_x() + bar.get_width()/2, h + max(0.5, h * 0.01), f"{int(round(pct*100))}%", ha="center", va="bottom", fontsize=10, rotation=0)
        bars_per_repo.append(bars)

    plt.xticks(x, x_labels, rotation=45, ha="right")
    plt.ylabel("Event Count")
    plt.xlabel("Event Type")
    if show_title:
        plt.title(f"Top {top_n} Event Types Across Repositories (Annotated With Repository Share %)")
    plt.legend(title="Repository")
    plt.tight_layout()
    plt.savefig("thesis-writing/thesis-main/figures/bot-event-type-distribution.pdf", format="pdf", bbox_inches="tight")
    _set_plot_style_and_plot()

# Helper methods for local use

def _extract_event_actor(event):
    prefer = ["by", "merged_by", "closed_by", "requested_by"]
    rels = event.get("relationships", [])
    # exact or substring match
    for rel in rels:
        qual = rel.get("qualifier")
        if qual and any(p in qual for p in prefer):
            return rel.get("objectId")
    return None

def _parse_labels(labels_string: str, include_empty: bool) -> list[str]:
    """Get the labels as list for a given string or list input."""
    output = []
    if labels_string is None:
        return output
    if isinstance(labels_string, str):
        labels_string = labels_string.replace(";", ",")
        labels_string = labels_string.replace("[", "").replace("]", "").replace("'", "").replace('"', "").replace("{", "").replace("}", "")
        parts = [label.strip() for label in labels_string.split(",") if label.strip() != "" or include_empty]
        return parts
    if isinstance(labels_string, list):
        for label in labels_string:
            if isinstance(label, str):
                output.append(label.strip())
        return output
    return output

def _get_local_attribute_value(obj, attribute_name):
    for a in obj.get("attributes", []):
        if a.get("name") == attribute_name:
            return str(a.get("value"))
        
def _pr_has_label(pull_request: Dict[str, Any], label: str) -> bool:
    labels_string = _get_local_attribute_value(pull_request, "issue_label")
    if labels_string is None:
        return False
    return label in labels_string.lower()