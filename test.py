from pydriller import Repository
import json
from build.utils import save_to_json, list_to_dict
from datetime import datetime

def get_source_code_from_tag(repo_path, tag_name, dt1, dt2):
    """
    Extracts the source code of a specific commit tagged in the repository.

    :param repo_path: Path to the local Git repository.
    :param tag_name: The name of the tag to fetch.
    :return: A dictionary containing file paths and their contents at the given commit.
    """
    source_code = []

    for commit in Repository(repo_path, since=dt1, to=dt2).traverse_commits():
        print(f"Processing commit: {commit.hash} tagged as {tag_name}")
        for modified_file in commit.modified_files:
            # Save the file path and its source code
            if modified_file.source_code:
                if modified_file.filename.find(".py") != -1 and modified_file.filename.find(".pyc") == -1:
                    comit = {
                        commit.hash + "---" + modified_file.filename: list_to_dict(modified_file.source_code.split("\n"))
                    }
                    source_code.append(comit)

    return source_code

# Example usage
repo_path = "https://github.com/AlexS-1/Bachelor-Code"
tag_name = "a1ad5c2cb35d621f2b187166af65a2b2ee3ea45e"
dt1 = datetime(2024,11,21)
dt2 = datetime(2024,11,22)
source_code = get_source_code_from_tag(repo_path, tag_name, dt1, dt2)
save_to_json(source_code, "Tests/exports.json")
