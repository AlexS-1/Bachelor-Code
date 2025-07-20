import json
import os
from datetime import datetime, timedelta

from build.utils import clone_ropositoriy
from build.local_repository_extractor import get_and_insert_local_data
from build.remote_repository_extractor import get_and_insert_remote_data
from build.database_handler import initialise_database, get_ocel_data
from build.code_quality_visualizer import plot_commit_code_quality
from build.contribution_process_miner import divide_event_log_at, split_OCEL_at_guideline_changes, flatten_ocel2, visualise_xes_as

def main():
    # =============================================
    # Set-Up
    # =============================================
    # Convert repo URL to path by cloning repo to temporary dictionary
    repo_url = "https://github.com/matplotlib/matplotlib"
    api_url = repo_url.replace("github.com", "api.github.com/repos")
    collection = repo_url.split("/")[-1]

    # Setting different timeperiod
    from_date = datetime.today() - timedelta(days=1*31)
    to_date = datetime.today()

    # Select supported file types your code quality analyser
    file_types = [".py"]

    if not os.path.exists(f"../tmp/{collection}"):
        repo_path = clone_ropositoriy(repo_url)
    else:
        repo_path = os.path.abspath(f"../tmp/{collection}")

    if not os.path.exists(repo_path):
        raise Exception(f"Repository at {repo_path} does not exist")
    
    initialise_database(repo_path)

    # =============================================
    # RQ1: Creation of OCEL
    # =============================================
    
    # # Go through all commits in the given time period
    # get_and_insert_local_data(repo_path, from_date, to_date, file_types, False)

    # # TODO Implement checking if remote and lcoal user ids match
    # get_and_insert_remote_data(api_url, from_date, to_date, file_types)

    path = get_ocel_data(collection)
    with open(path) as f:
        ocel = json.load(f)

    # =============================================
    # RQ2: Code Quality Analysis and Visualisation
    # =============================================

    # plot_commit_code_quality(collection)

    # =============================================
    # RQ3: Process Discovery of Guidelines
    # =============================================

    flat_dataframe = flatten_ocel2(ocel, object_type="pull_request", collection=collection)
    visualise_xes_as("petri_net", flat_dataframe)

    before_log, after_log = divide_event_log_at(datetime(2025, 7, 7, 15, 0).replace(tzinfo=None), flat_dataframe)
    visualise_xes_as("petri_net", before_log)
    visualise_xes_as("petri_net", after_log)

if __name__ == "__main__":
    main()