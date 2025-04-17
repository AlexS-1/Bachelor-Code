import os
from datetime import datetime, timedelta

from build.analysis import analyse_source_code, generate_ast_graph, get_filename_for_graph, visualise_diff_graph, visualize_call_graph
from build.api_handler import get_repo_information, get_closed_pulls
from build.pydriller import get_and_insert_commits_data, get_and_store_commits_data, get_initial_commit_hash, get_pydriller_metric
from build.utils import clone_ropositoriy, read_from_file, write_json
from build.database_handler import initialise_database


def main():
    # Convert repo URL to path by cloning repo to temporary dictionary
    repo_url = "https://github.com/srbhr/Resume-Matcher"
    api_url = repo_url.replace("github.com", "api.github.com/repos")

    # Setting different timeperiod
    start_time = datetime.today().replace(
        tzinfo=None,
        microsecond=0) - timedelta(days=100)
    end_time = datetime.today().replace(microsecond=0)

    # Select from the supported file types for comment extraction
    file_types = [
        ".c", ".c", ".cc", ".cp", ".cpp", ".cx", ".cxx", ".c+", ".c++",
        ".h", ".hh", ".hxx", ".h+", ".h++", ".hp", ".hpp",
        ".java", ".js", ".cs", ".py", ".php", ".rb"]

    initialise_database()

    # Get & store code data usingy PyDriller before deleting cloned repository
    if not os.path.exists(f"../tmp/{repo_url.split('/')[-1]}"):        
        repo_path = clone_ropositoriy(repo_url)
    else:
        repo_path = os.path.abspath(f"../tmp/{repo_url.split('/')[-1]}")
    get_and_insert_commits_data(repo_path, start_time, end_time, file_types)
    commits = get_and_store_commits_data(repo_path, start_time, end_time, file_types)
    
    write_json("Data/commits.json", commits)

    repo_info = get_repo_information(api_url)
    pulls = get_closed_pulls(repo_info["utility_information"]["pulls_url"], 1)

    # TODO Delete the repo after all analysis has been performed (only for production)
    # shutil.rmtree(repo_path)

if __name__ == "__main__":
    main()
