import os
from datetime import datetime, timedelta
import shutil

from build.remote_repository_extractor import get_and_insert_remote_data
from build.local_repository_extractor import get_and_insert_local_data
from build.utils import clone_ropositoriy
from build.database_handler import initialise_database


def main():
    # Convert repo URL to path by cloning repo to temporary dictionary
    repo_url = "https://github.com/matplotlib/matplotlib"
    api_url = repo_url.replace("github.com", "api.github.com/repos")

    # Setting different timeperiod
    from_date = datetime.today() - timedelta(days=100)
    to_date = datetime.today()

    # Select supported file types your code quality analyser
    file_types = [".py"]

    initialise_database()

    if not os.path.exists(f"../tmp/{repo_url.split('/')[-1]}"):
        repo_path = clone_ropositoriy(repo_url)
    else:
        repo_path = os.path.abspath(f"../tmp/{repo_url.split('/')[-1]}")
    
    get_and_insert_local_data(repo_path, from_date, to_date, file_types)
    # TODO Implement checking if remote and lcoal user ids match
    get_and_insert_remote_data(api_url, from_date, to_date, file_types)

    shutil.rmtree(repo_path)

if __name__ == "__main__":
    main()