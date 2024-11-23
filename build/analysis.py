def analyse_diff_comments(data):
    for file, commits in data.items():
        for commit in commits:
            no_change_comments = []
            for i in range(len(commit["comments"])):
                if commit["comments"][i]["line"] in [item[0] for item in commit["diff"]["added"]]:
                    commit["comments"][i]["edit"] = "added"
                if commit["comments"][i]["line"] in [item[0] for item in commit["diff"]["deleted"]]:
                    if "edit" in list(commit["comments"][i].keys()):
                        commit["comments"][i]["edit"] = "modified"
                        continue
                    else:
                        commit["comments"][i]["edit"] = "deleted"
                        continue
                no_change_comments.append(i)
            # Ensure the gaps of deleted elements are artificially filled by increasing the shift
            shift = 0
            for j in no_change_comments:
                del commit["comments"][j-shift]
                shift += 1