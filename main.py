import shutil
from datetime import datetime, timedelta

from build.api_handler import (
    get_issues, get_repo_information,
    get_closed_pulls, get_anonymous_user_counter)
from build.pydriller import get_and_insert_commits_data
from build.utils import clone_ropositoriy, validate_json, write_json
from build.database_handler import get_ocel_data, initialise_database


def main():
    # Convert repo URL to path by cloning repo to temporary dictionary
    repo_url = "https://github.com/srbhr/Resume-Matcher"
    api_url = repo_url.replace("github.com", "api.github.com/repos")

    # Setting different timeperiod
    start_time = datetime.today().replace(
        tzinfo=None,
        microsecond=0) - timedelta(days=365)
    end_time = datetime.today().replace(microsecond=0)

    # Select from the supported file types for comment extraction
    file_types = [
        ".c", ".c", ".cc", ".cp", ".cpp", ".cx", ".cxx", ".c+", ".c++",
        ".h", ".hh", ".hxx", ".h+", ".h++", ".hp", ".hpp",
        ".java", ".js", ".cs", ".py", ".php", ".rb"]

    initialise_database()

    # Get & store code data usingy PyDriller before deleting cloned repository
    repo_path = clone_ropositoriy(repo_url)
    get_and_insert_commits_data(repo_path, start_time, end_time, file_types)
    shutil.rmtree(repo_path)

    repo_info = get_repo_information(api_url)
    get_closed_pulls(repo_info["utility_information"]["pulls_url"], 9)
    get_issues(repo_info["utility_information"]["issues_url"], 4)
    count = get_anonymous_user_counter()
    print(len(list(count.keys())))

    # Validate the JSON data to OCEL format
    write_json("Exports/OCEL-Data.jsonocel", get_ocel_data())
    validate_json("Exports/OCEL-Data.jsonocel", "Data/OCEL-Schema.json")


if __name__ == "__main__":
    main()
