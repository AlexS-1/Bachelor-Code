import collections
from ctypes import sizeof
from gc import collect
import json
import os
from datetime import datetime, timedelta
import shutil

from build.code_quality_analyzer import get_maintainability_index, get_pylint_score
from build.contribution_process_miner import split_OCEL_at_guideline_changes
from build.remote_repository_extractor import get_and_insert_remote_data
from build.local_repository_extractor import get_and_insert_local_data
from build.utils import clone_ropositoriy
from build.database_handler import get_ocel_data, initialise_database
from build.code_quality_visualizer import plot_commit_code_quality


def main():
    # Convert repo URL to path by cloning repo to temporary dictionary
    repo_url = "https://github.com/srbhr/Resume-Matcher"
    api_url = repo_url.replace("github.com", "api.github.com/repos")

    # Setting different timeperiod
    from_date = datetime.today() - timedelta(days=1*365)
    to_date = datetime.today()

    # Select supported file types your code quality analyser
    file_types = [".py"]

    if not os.path.exists(f"../tmp/{repo_url.split('/')[-1]}"):
        repo_path = clone_ropositoriy(repo_url)
    else:
        repo_path = os.path.abspath(f"../tmp/{repo_url.split('/')[-1]}")
    
    if not os.path.exists(repo_path):
        raise Exception(f"Repository at {repo_path} does not exist")
    
    initialise_database(repo_path)
    
    # Go through all commits in the given time period
    # get_and_insert_local_data(repo_path, from_date, to_date, file_types, True)

    # TODO Implement checking if remote and lcoal user ids match
    # get_and_insert_remote_data(api_url, from_date, to_date, file_types)

    # plot_commit_code_quality(repo_url.split('/')[-1])
    collection = repo_path.split("/")[-1]
    path = get_ocel_data(collection)
    with open(path) as f:
        ocel = json.load(f)
    ocels = split_OCEL_at_guideline_changes(ocel, collection)
    for ocel in ocels:
        print(len(ocel["events"]))
 
if __name__ == "__main__":
    main()