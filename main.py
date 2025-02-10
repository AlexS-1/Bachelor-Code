import json
from mimetypes import init
import shutil
from datetime import datetime, timedelta

from build.analysis import analyse_message
from build.api_handler import get_issues, get_repo_information, get_closed_pulls
from build.pydriller import get_and_insert_commits_data
from build.utils import clone_ropositoriy
from build.database_handler import get_commits, initialise_database


def main():
    # Convert repo URL to path by cloning repo to temporary dictionary
    repo_url = "https://github.com/srbhr/Resume-Matcher"
    
    # Setting different timeperiod
    start_time = datetime.today().replace(tzinfo=None, microsecond=0) - timedelta(days=365)
    end_time = datetime.today().replace(microsecond=0)

    # Select from the supported file types for comment extraction
    file_types = [".c", ".c", ".cc", ".cp", ".cpp", ".cx", ".cxx", ".c+", ".c++", ".h", ".hh", ".hxx", ".h+", ".h++", ".hp", ".hpp", ".java", ".js", ".cs", ".py", ".php", ".rb"]

    # Get and store the code data usingy PyDriller before deleting the cloned repository
    repo_path = clone_ropositoriy(repo_url)
    get_and_insert_commits_data(repo_path, start_time, end_time, file_types)
    shutil.rmtree(repo_path)

    commits = get_commits()
    repo_info = get_repo_information()
    get_closed_pulls(repo_info["utility_information"]["pulls_url"])
    get_issues(repo_info["utility_information"]["issues_url"])
    initialise_database()

if __name__ == "__main__":
    main()