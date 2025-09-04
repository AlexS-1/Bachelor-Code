import argparse
import json
import os
from datetime import datetime, timedelta

from build.code_quality_visualizer import plot_repo_code_quality_fast
from build.utils import clone_repository
from build.local_repository_extractor import get_and_insert_local_data
from build.remote_repository_extractor import get_and_insert_remote_data
from build.database_handler import initialise_database, get_ocel_data
from build.contribution_process_miner import flatten_ocel2, visualise_xes_as

def main(repo_url="https://github.com/scikit-learn/scikit-learn", **kwargs):

    # =============================================
    # Set-Up
    # =============================================

    # Convert repo URL to path by cloning repo to temporary dictionary
    api_url = repo_url.replace("github.com", "api.github.com/repos")
    collection = repo_url.split("/")[-1]

    # Setting different timeperiod
    from_date = datetime(2018,1,20).replace(tzinfo=None)  # e.g. 5 years ago
    # (datetime.today() - timedelta(days=5*365)).replace(day=1, month=1, tzinfo=None)
    to_date = datetime(2025, 8, 15).replace(tzinfo=None)  # e.g. today
    # (datetime.today() - timedelta(days=1)).replace(tzinfo=None)

    # Select supported file types your code quality analyser
    file_types = [".py"]

    if not os.path.exists(f"../tmp/{collection}"):
        tmp_path = os.path.abspath("../tmp")
        repo_path = clone_repository(repo_url, temp_dir=tmp_path)
    else:
        repo_path = os.path.abspath(f"../tmp/{collection}")

    if not os.path.exists(repo_path):
        raise Exception(f"Repository at {repo_path} does not exist")
    
    initialise_database(repo_path)

    # =========================================================
    # RQ0: Creation of OCEL
    # =========================================================
    
    # Go through all commits in the given time period
    # get_and_insert_local_data(repo_path, from_date, to_date, file_types, False)

    get_and_insert_remote_data(api_url, repo_path, from_date, to_date)

    path = get_ocel_data(collection)
    path = "Exports/scikit-learn-OCEL.json"
    with open(path) as f:
        ocel = json.load(f)

    # =========================================================
    # RQ2: Code Quality Analysis and Visualisation
    # =========================================================

    # plot_repo_code_quality_fast(collection)

    # =========================================================
    # RQ3: Contribution Guidelines Analysis and Visualisation
    # =========================================================

    # flat_event_log = flatten_ocel2(ocel, object_type="pull_request", collection=collection)
    # visualise_xes_as("petri_net", flat_event_log, collection=collection)

    # if flat_event_log:
    #     before_log, after_log = divide_event_log_at(datetime(2023, 7, 7, 0, 0, 0).replace(tzinfo=None), flat_event_log)
    #     visualise_xes_as("petri_net", before_log, collection=collection)
    #     visualise_xes_as("petri_net", after_log, collection=collection)
    # else:
    #     print("ERROR: Flattened event log is empty")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo_url",
        type=str,
        default='https://github.com/scikit-learn/scikit-learn',
        help="URL of the GitHub repository to analyze (default: https://github.com/scikit-learn/scikit-learn)"
    )
    args = parser.parse_args()
    main(repo_url=args.repo_url)