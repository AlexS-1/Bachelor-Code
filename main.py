import os
from datetime import datetime, timedelta

from build.analysis import analyse_source_code, generate_ast_graph, visualise_diff_graph, visualize_call_graph
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
    commits = read_from_file("Data/commits.json")
    for commit_hash, commit_data in commits.items():
        if commit_data["filename_old"] is None:
            continue
        cc_old, message_count_old = analyse_source_code(commit_data["source_old"], "cc")
        cc_new, message_count_new = analyse_source_code(commit_data["source_new"], "cc")
        initial_commit_hash = get_initial_commit_hash(repo_path)
        print(f"CYCLOMATIC COMPLEXITY: The average cyclomatic complexity per method changed from {cc_old/message_count_old} to {cc_new/message_count_new}")
        print(f"MCCABE'S WEIGHTED METHOD COUNT: The McCabe's weighted method count changed from {cc_old} to {cc_new}")
        print(f"HALSTEAD'S COMPLEXITY MEASURES: The Halstead's complexity measures e.g. for Effort changed from {analyse_source_code(commit_data["source_old"], 'helstead')[10].split(":")[-1]} to {analyse_source_code(commit_data["source_new"], 'helstead')[10].split(":")[-1]}")
        print(f"COMMIT COUNT: The commit count for this file changed from {get_pydriller_metric(repo_path, initial_commit_hash, commit_hash, commit_data["filename_new"], "commit_count") - 1} to {get_pydriller_metric(repo_path, initial_commit_hash, commit_hash, commit_data["filename_new"], "commit_count")}")
        print(f"CODE CHURN: The code churn changes from {get_pydriller_metric(repo_path, initial_commit_hash, commit_hash, commit_data["filename_new"], "code_churn") - (commit_data["additions"] - commit_data["deletions"])} to {get_pydriller_metric(repo_path, initial_commit_hash, commit_hash, commit_data["filename_new"], "code_churn")}")
        print(f"DOCUMENTATION RATIO: The documentation ratio changed from {int(analyse_source_code(commit_data["source_old"], 'docuementation_LOC')[6].split(":")[1])/int(analyse_source_code(commit_data["source_old"], 'docuementation_LOC')[1].split(":")[1])} to {int(analyse_source_code(commit_data["source_new"], 'docuementation_LOC')[6].split(":")[1])/int(analyse_source_code(commit_data["source_new"], 'docuementation_LOC')[1].split(":")[1])}")
        print(f"COMMENT LINES OF CODE: The comment lines of code changed from {analyse_source_code(commit_data["source_old"], 'docuementation_LOC')[4].split(":")[1]} to {analyse_source_code(commit_data["source_new"], 'docuementation_LOC')[4].split(":")[1]}")
        print(f"METHOD COUNT: The method count changed from {message_count_old} to {message_count_new}")
        print(f"CALL GRAPH: The call graphs are as follows and the differences are visualized in the diff graph")
        graph_new = generate_ast_graph(commit_data["source_new"])
        visualize_call_graph(graph_new, f"Exports/{commit_data["filename_new"].split("/")[-1]}-new-{commit_hash}-call_graph")
        graph_old = generate_ast_graph(commit_data["source_old"])
        visualize_call_graph(graph_old, f"Exports/{commit_data["filename_old"].split("/")[-1]}-old-{commit_hash}-call_graph")
        visualise_diff_graph(graph_old, graph_new, filename=f"Exports/{commit_data["filename_new"].split("/")[-1]}-{commit_hash}-diff_graph")

    # TODO Delete the repo after all analysis has been performed (only for production)
    # shutil.rmtree(repo_path)

if __name__ == "__main__":
    main()
