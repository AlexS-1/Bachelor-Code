import ast
from datetime import datetime
import hashlib
import re
import subprocess
from numpy import insert, size
from pydriller import Repository
from typing import Dict, List, Optional, Set


from build.database_handler import get_attribute_change_times, get_attribute_value_at_time, get_object, insert_commit, insert_event, insert_file, insert_file_metrics, update_attribute
from build.code_quality_analyzer import get_cyclomatic_complexity, get_halstead_metrics, get_line_metrics, get_pylint_score, get_maintainability_index
from build.utils import date_1970, date_formatter, list_to_dict

def _create_commit(commit_sha, author, message, repository, branches, commit_timestamp, description=None, file_changes=None, parents=None):
    return {
        "commit_sha": commit_sha,
        "message": message,
        "description": str(description),
        "to": str([repository + ":" + branch for branch in branches]),
        "is-authored-by": author,
        "commit_timestamp": commit_timestamp,
        "aggregates": str(file_changes),
        "is-child-of": str(parents),
    }

def _create_file_metrics(name, filename, file_change_timestamp, commit_sha, method_count, cyclomatic_complexity, theta_1, theta_2, N_1, N_2, loc, lloc, sloc, cloc, dloc, blank_lines, pylint_score):
    return {
        "file_change_timestamp": file_change_timestamp,
        "method_count": method_count,
        "cc": cyclomatic_complexity,
        "theta_1": theta_1,
        "theta_2": theta_2,
        "N_1": N_1,
        "N_2": N_2,
        "loc": loc,
        "lloc": lloc,
        "sloc": sloc,
        "cloc": cloc,
        "dloc": dloc,
        "blank_lines": blank_lines,
        "pylint_score": pylint_score
    }

def _create_file(name, filename, file_change_timestamp, commit_sha, size_bytes, file_purpose, file_metrics=None):
    return {
        "file-changed_by": name,
        "filename": filename,
        "file_change_timestamp": file_change_timestamp,
        "part-of-commit": commit_sha,
        "size_bytes": size_bytes,
        "file_purpose": file_purpose,
        "has-file-metrics": file_metrics is not None
    }

def _get_snapshot_code_quality(repo_path, from_date, file_types, collection, partial=True):
    repository_code_metrics: Dict[str, List[float]] = {}  # filename: [maintainability_index, pylint_score]
    for commit in Repository(repo_path, 
                             since=from_date).traverse_commits():

        # Get the initial commit to reset the repository to its original state
        initial_commit = subprocess.run(
            ['git', 'rev-parse', 'HEAD'], 
            cwd=repo_path, 
            stdout=subprocess.PIPE, 
            text=True).stdout.strip()
        
        # Move HEAD to the commit, from which we want to analze the code quality
        if partial:
            # Get the code metrics for only Python files:
            print(f"Checking out commit {commit.hash} from original commit {initial_commit}")
            subprocess.run(['git', 'checkout', commit.hash], cwd=repo_path, check=True)
            result = subprocess.run(
                ["git", "ls-files", "*.py", "**/*.py"],
                cwd=repo_path,
                stdout=subprocess.PIPE,
                text=True,
                check=True
            )
            py_files = result.stdout.strip().split('\n')
            for file in py_files:
                try:
                    with open(f"{repo_path}/{file}", 'r') as f:
                        source_code = f.read()
                except Exception as e:
                    print(f"Error reading file {file}: {e}")
                    source_code = ""
                mi = get_maintainability_index(source_code)/100 # TODO Implement own calculation of maintainability index
                pl = get_pylint_score(source_code)/10
                repository_code_metrics[file] = [mi, pl]
        else:
            # Get inital values for all files in the repository and add them to the OCEL
            all_files = subprocess.run(
                ["git", "ls-files"],
                cwd=repo_path,
                stdout=subprocess.PIPE,
                text=True,
                check=True
            )
            for file in all_files.stdout.strip().split('\n'):
                try:
                    with open(f"{repo_path}/{file}", 'r') as f:
                        source = f.read()
                except Exception as e:
                    print(f"ERROR: Reading file {file}: {e}")
                    source = ""
                file_purpose = _check_file_purpose(file, source, file_types)
                file_object = _create_file(
                    "Repository Owner", 
                    file,
                    str(date_1970()), 
                    commit.hash,
                    size(source),
                    file_purpose,
                    "m_" + str(file) if file_purpose == "source" else None
                )
                insert_file(file_object, collection)

                if file_purpose == "source":
                    source_code_metrics = _extract_source_code_metrics(source)
                    repository_code_metrics[file] = source_code_metrics[0:2]
                    ps, cc, hm, lm = source_code_metrics[1:6]
                    file_metrics = _create_file_metrics(
                        commit.committer.name, 
                        file,
                        str(date_1970()), 
                        commit.hash,
                        -1, # FIXME Check with prior suggestion of cc_visit
                        cc,
                        hm.total.h1,
                        hm.total.h2,
                        hm.total.N1,
                        hm.total.N2,
                        lm.loc,
                        lm.lloc,
                        lm.sloc,
                        lm.comments,
                        lm.multi,
                        lm.blank,
                        ps)
                    insert_file_metrics(file_metrics, collection)

                if file_purpose == "documentation":
                    word_count = len(source.split())
                    diff_new = {i: line for i, line in enumerate(source.split("\n"), 1)}
                    
                    
                    # diff_new = list_to_dict(modified_file.diff_parsed["added"])
                    # for line, content in diff_new.items():
                    #     for keyword in set(keyword_topic.keys()):
                    #         if keyword.lower() in content.split():
                    #             print(f"LOG: Found line \"{content}\" for \"{keyword}\" in \"{modified_file.new_path}\"")
                    #             contribution_guidelines[modified_file.new_path] = {
                    #                 line: content,
                    #                 keyword.lower(): keyword_topic[keyword]
                    #             }

        # Move HEAD back to the initial commit
        subprocess.run(['git', 'checkout', initial_commit], cwd=repo_path, check=True)
        print(f"Back to the real analysis")
        break
    return repository_code_metrics

def get_and_insert_local_data(repo_path: str, from_date: datetime, to_date: datetime, file_types: list, do_snapshot: bool = True):
    """
    Extract the file level change for a given repository and certain source code files
    Args:
        repo_path (str): The file path to the repository
        from_date (datetime): The start date for the analysis
        to_date (datetime): The end date for the analysis
        file_types (list): The file types to include in the analysis
        do_snapshot (bool): Whether to take a snapshot of the code quality
    """
    collection = repo_path.split("/")[-1]
    repository_code_metrics = _get_snapshot_code_quality(repo_path, from_date, file_types, collection, partial = True) if do_snapshot else {}

    print(f"LOG: Finsehd snapshotting, now extracting local data from {repo_path} between {from_date} and {to_date}")
    print(repository_code_metrics)

    for commit in Repository(repo_path, 
                             since=from_date, 
                             to=to_date,
                             #only_modifications_with_file_types=file_types NOTE Remove for final version 
                            ).traverse_commits():
        commit_timestamp = date_formatter(commit.committer_date)
        file_metrics = {
            "maintainability_index": [],
            "pylint_score": []
        }
        filenames = []

        # Update the repository code metrics for current commit
        for modified_file in commit.modified_files:
            file_action = {}
            file_actor = {}
            if modified_file.change_type.name == "DELETE" and commit.committer.name:
                if modified_file.old_path and any(modified_file.old_path.endswith(extension) for extension in file_types):
                    repository_code_metrics.pop(modified_file.old_path, None)
                file_action = {"removed_file": modified_file.old_path}
                file_actor = {"removed_by": commit.committer.name}
            else:
                if modified_file.change_type.name == "ADD" and modified_file.new_path and commit.committer.name:
                    file_action = {"added_file": modified_file.new_path}
                    file_actor = {"added_by": commit.committer.name}
                elif modified_file.change_type.name == "RENAME" and modified_file.old_path and modified_file.new_path and commit.committer.name:
                    update_attribute(modified_file.old_path, "filename", modified_file.new_path, commit_timestamp, collection, update_id = True)
                    if any(modified_file.old_path.endswith(extension) for extension in file_types):
                        repository_code_metrics.pop(modified_file.old_path, None)
                    file_action = {"renamed_file": modified_file.new_path}
                    file_actor = {"renamed_by": commit.committer.name}
                elif modified_file.new_path and commit.committer.name: # modified_file.change_type.name == "MODIFIED"
                    file_action = {"modified_file": modified_file.new_path}
                    file_actor = {"modified_by": commit.committer.name}
                else:
                    print(f"WARNING Unknown change type {modified_file.change_type.name} in commit {commit.hash}")

                # For every change to a file including adding a file, create/update object
                if modified_file.new_path and modified_file.source_code:
                    file_purpose = _check_file_purpose(modified_file.new_path, modified_file.source_code, file_types)
                else:
                    file_purpose = "unknown"
                file = _create_file(
                    commit.committer.name, 
                    modified_file.new_path,
                    commit_timestamp, 
                    commit.hash,
                    size(modified_file.source_code) if modified_file.source_code else 0,
                    file_purpose,
                    "m_" + str(modified_file.new_path) if file_purpose == "source" else None
                )
                insert_file(file, collection)

                if not extract_source_code_events(modified_file, commit, file_purpose, collection):
                    insert_event(
                        f"CF_{commit_timestamp}", 
                        "change_file", 
                        commit_timestamp, 
                        collection, 
                        [], 
                        [{"qualifier": list(file_action.keys())[0], "objectId": list(file_action.values())[0]},
                         {"qualifier": list(file_actor.keys())[0], "objectId": list(file_actor.values())[0]}])

                # For every source file additionally update metrics
                if file_purpose == "source" and modified_file.new_path and modified_file.source_code:
                    source_code_metrics = _extract_source_code_metrics(modified_file.source_code)
                    repository_code_metrics[modified_file.new_path] = source_code_metrics[0:2]
                    ps, cc, hm, lm = source_code_metrics[1:6]
                    file_object_metrics = _create_file_metrics(
                        commit.committer.name, 
                        modified_file.new_path,
                        commit_timestamp, 
                        commit.hash,
                        len(modified_file.methods),
                        cc,
                        hm.total.h1,
                        hm.total.h2,
                        hm.total.N1,
                        hm.total.N2,
                        lm.loc,
                        lm.lloc,
                        lm.sloc,
                        lm.comments,
                        lm.multi,
                        lm.blank,
                        ps)
                    insert_file_metrics(file_object_metrics, collection)

                # For every documentation document check wether it is a contribution relevant document
                if file_purpose == "documentation" and modified_file.new_path and modified_file.source_code:
                    word_count = len(modified_file.source_code.split())
                    diff_new = list_to_dict(modified_file.diff_parsed["added"])

            # Append the filename according to the performed action to the list of filenames
            _, objectId = file_action.popitem()
            filenames.append(objectId)

        # After going through all file changes add the commit information
        commit_object = _create_commit(
            commit.hash, 
            commit.author.name, 
            commit.msg.split("\n\n", 1)[0], 
            commit.project_name, 
            commit.branches, 
            commit_timestamp,
            "" if len(commit.msg.split("\n\n")) < 2 else commit.msg.split("\n\n", 1)[1], 
            filenames, 
            commit.parents)
        
        # Calculate the overall code quality scores for the files in the repository i.e., in ´repository_code_metrics´
        for _,v in repository_code_metrics.items():
            file_metrics["maintainability_index"].append(v[0])
            file_metrics["pylint_score"].append(v[1])
        commit_mi = sum(file_metrics["maintainability_index"])/len(file_metrics["maintainability_index"]) if file_metrics["maintainability_index"] else 0
        commit_pylint = sum(file_metrics["pylint_score"])/len(file_metrics["pylint_score"]) if file_metrics["pylint_score"] else 0
        commit_object["repository_maintainability_index"] = commit_mi
        commit_object["repository_pylint_score"] = commit_pylint
        insert_commit(commit_object, collection)
    return

def _extract_source_code_metrics(source):
    if source is None:
        source = ""
        print(f"File has no source code")

    # Gather code quality data per file
    mi = get_maintainability_index(source)/100
    ps = get_pylint_score(source)/10
    lm = get_line_metrics(source)
    hm = get_halstead_metrics(source)
    cc = get_cyclomatic_complexity(source)

    return [mi, ps, cc, hm, lm]

def _check_file_purpose(path: str, source: str, file_types: list):
    if path:
        path_parts = path.split("/")
        for path_part in reversed(path_parts):
            if any(path_part.endswith(extension) for extension in file_types):
                return "source"
            elif "requirement" in path_part or "dep" in path_part:
                return "dependency"
            elif any(path_part.endswith(extension) for extension in [".txt", ".md", ".rst"]) or "doc" in path_part:
                return "documentation"
            elif "test" in path_part:
                return "test"
            elif "example" in path_part:
                return "example"
            elif any(path_part.endswith(extension) for extension in [".yaml", ".yml", ".cfg"]) or "conf" in path_part:
                return "configuration"
            elif "git" in path_part:
                return "git"
        if len(path_parts) == 1:
            return "information"
        print(f"WARNING: Found no file purpose for {path}")
    return "misc"

def extract_source_code_events(modified_file, commit, file_purpose, collection):
    """
    Extracts source code events from a modified file and inserts them into the database.
    Args:
        modified_file: The modified file object from PyDriller.
        file_purpose: The purpose of the file (e.g., "source", "documentation").
        collection: The database collection to insert events into.
    Return:
        bool: True if events were inserted, False otherwise.
    """
    # Extract source code events from the modified file
    if modified_file.new_path and modified_file.source_code and modified_file.diff_parsed:
        time = date_formatter(commit.committer_date)
        actor = commit.author.name
        commit_hash = commit.hash
        change_type = modified_file.change_type.name

        if file_purpose == "source":
            source_code_events = _extract_source_code_events(modified_file.new_path, modified_file.source_code_before, modified_file.source_code, modified_file.diff_parsed)
        else:
            source_code_events = [_extract_non_source_code_events(file_purpose, change_type, modified_file.source_code, modified_file.source_code_before)]

        inserted_event = False
        if source_code_events == None:
            return inserted_event

        for event in source_code_events:
            if event is None:
                continue
            insert_event(
                f"{event["acronym"]}_{commit_hash}",
                event["type"],
                time,
                collection,
                event["attributes"],
                [{"qualifier": "file-modified-by", "objectId": actor}, 
                 {"qualifier": "in-file", "objectId": modified_file.new_path}]
            )
            inserted_event = True
        return inserted_event

def _extract_non_source_code_events(file_purpose, change_type, source_code, source_code_old):
    if file_purpose == "documentation":
        if change_type == "ADDED":
            return _create_event_properties("DAD", "documentation_added", [])
        elif change_type == "MODIFIED":
            return _create_event_properties("DMD", "documentation_modified", [])
        elif change_type == "DELETED":
            return _create_event_properties("DDD", "documentation_deleted", [])
    elif file_purpose == "dependency":
        if change_type == "ADDED" or source_code and source_code_old and len(source_code.split("\n")) < len(source_code_old.split("\n")):
            return _create_event_properties("DEA", "dependency_added", [])
        elif change_type == "MODIFIED" and source_code and source_code_old  and len(source_code.split("\n")) == len(source_code_old.split("\n")):
            return _create_event_properties("DEM", "dependency_modified", [])
        elif change_type == "DELETED" or source_code and source_code_old and len(source_code.split("\n")) > len(source_code_old.split("\n")):
            return _create_event_properties("DED", "dependency_deleted", [])
        else:
            print(f"WARNING: Unknown change type: {change_type} for dependency file with purpose: {file_purpose}")
    elif file_purpose == "configuration" or file_purpose == "git":
        return _create_event_properties("CON", "configuration_modified", [])
    elif file_purpose == "example":
        return _create_event_properties("EMO", "example_modified", [])
    elif file_purpose == "test":
        return _create_event_properties("TMO", "test_modified", [])
    else:
        return None

def _extract_source_code_events(
    file_path: str,
    source_before: Optional[str],
    source_after: Optional[str],
    diff_parsed: Optional[Dict],
) -> List[Dict]:
    """
    Applies detectors in precedence order (first match wins for interpretation):
      1) MAD, MRE, MDE
      2) PAD, PMO, PDE
      3) DAD, DMO, DPM, DDE
      4) CMO
      5) CAD, COM, COD
      6) SAD, SMO, SDE
    """
    events: List[Dict] = []
    # 1
    events.extend(detect_method_add_delete_rename(file_path, source_before, source_after))
    # 2
    events.extend(detect_parameter_changes(file_path, source_before, source_after))
    # 3
    events.extend(detect_docstring_changes(file_path, source_before, source_after))
    # 4
    events.extend(detect_comment_only_changes(file_path, source_before, source_after, diff_parsed))
    # 5
    events.extend(detect_condition_changes(file_path, source_before, source_after))
    # 6
    events.extend(detect_statement_changes_fallback(diff_parsed))
    # de-duplicate by (acronym, qname, span)
    return events


def _create_event_properties(acronym, event_type, attributes):
    return {
        "acronym": acronym,
        "type": event_type,
        "attributes": attributes
    }


def _normalize_source_for_hash(text: str) -> str:
    if not text:
        return ""
    text_without_line_comments = re.sub(r"(?m)^\s*#.*$", "", text)
    return re.sub(r"\s+", " ", text_without_line_comments).strip()


def _hash_source_span(text: str, start_line: int, end_line: int) -> str:
    lines = text.splitlines()
    snippet = "\n".join(lines[start_line - 1:end_line]) if lines else ""
    return hashlib.sha1(_normalize_source_for_hash(snippet).encode()).hexdigest()


def _collect_conditions(node: ast.AST) -> Set[str]:
    conditions: Set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, (ast.If, ast.While, ast.Assert)):
            test = getattr(n, "test", None)
            if test is not None:
                try:
                    conditions.add(ast.unparse(test))  # Python 3.9+
                except Exception:
                    conditions.add(ast.dump(test, include_attributes=False))
        elif isinstance(n, ast.comprehension) and n.ifs:
            for t in n.ifs:
                try:
                    conditions.add(ast.unparse(t))
                except Exception:
                    conditions.add(ast.dump(t, include_attributes=False))
    return conditions


def _comment_lines_in_span(source_text: str, start_line: int, end_line: int) -> Set[int]:
    out: Set[int] = set()
    for i, line in enumerate(source_text.splitlines(), 1):
        if start_line <= i <= end_line and re.match(r"^\s*#", line):
            out.add(i)
    return out


def _entity_index(source_text: str, module_qualname: str) -> Dict[str, Dict]:
    """
    Builds an index of module/class/function/method entities with:
    qname, kind, lineno, end_lineno, params, annotations, docstring, body_hash, conditions, comment_lines.
    """
    if not source_text:
        return {}

    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return {}

    index: Dict[str, Dict] = {}
    lines = source_text.splitlines()

    # Module entity
    module_doc = ast.get_docstring(tree)
    module_entry = {
        "qname": module_qualname,
        "kind": "module",
        "lineno": 1,
        "end_lineno": len(lines) or 1,
        "params": [],
        "annotations": [],
        "docstring": module_doc,
        "body_hash": hashlib.sha1(_normalize_source_for_hash(source_text).encode()).hexdigest(),
        "conditions": _collect_conditions(tree),
        "comment_lines": _comment_lines_in_span(source_text, 1, len(lines) or 1),
    }
    index[module_qualname] = module_entry

    def add_function(qname_prefix: str, func: ast.AST, kind: str):
        params = []
        annotations = []
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for a in func.args.args:
                params.append(a.arg)
                annotation = getattr(a, "annotation", None)
                if annotation is not None:
                    try:
                        annotations.append(ast.unparse(annotation))
                    except Exception:
                        annotations.append("")
                else:
                    annotations.append("")
        end_ln = getattr(func, "end_lineno", getattr(func, "lineno", 1))
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            doc = ast.get_docstring(func)
        else:
            doc = None
        index[qname_prefix] = {
            "qname": qname_prefix,
            "kind": kind,
            "lineno": getattr(func, "lineno", 1),
            "end_lineno": end_ln,
            "params": params,
            "annotations": annotations,
            "docstring": doc,
            "body_hash": _hash_source_span(source_text, getattr(func, "lineno", 1), end_ln),
            "conditions": _collect_conditions(func),
            "comment_lines": _comment_lines_in_span(source_text, getattr(func, "lineno", 1), end_ln),
        }

    # Top-level functions
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add_function(f"{module_qualname}.{node.name}", node, "function")

    # Classes and methods
    def visit_class(node: ast.ClassDef, parent_qname: str):
        add_function(f"{parent_qname}.{node.name}", node, "class")
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                add_function(f"{parent_qname}.{node.name}.{child.name}", child, "method")
            if isinstance(child, ast.ClassDef):
                visit_class(child, f"{parent_qname}.{node.name}")

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            visit_class(node, module_qualname)

    return index


# ========== Activity detectors (explain emitted acronyms) ==========

def detect_method_add_delete_rename(
    file_path: str,
    source_before: Optional[str],
    source_after: Optional[str],
) -> List[Dict]:
    """
    Emits:
      - MAD (Method Added): method in 'after' but not in 'before'
      - MDE (Method Deleted): method in 'before' but not in 'after'
      - MRE (Method Renamed): match deleted and added by body similarity, name changed
    Precedence: detect MRE and remove corresponding MAD/MDE pairs.
    """
    events: List[Dict] = []
    before_index = _entity_index(source_before or "", file_path) if source_before is not None else {}
    after_index = _entity_index(source_after or "", file_path) if source_after is not None else {}

    before_methods = {k: v for k, v in before_index.items() if v["kind"] in ("function", "method")}
    after_methods = {k: v for k, v in after_index.items() if v["kind"] in ("function", "method")}

    before_names = set(before_methods.keys())
    after_names = set(after_methods.keys())

    added = after_names - before_names
    deleted = before_names - after_names

    # MAD
    for name in sorted(added):
        entry = after_methods[name]
        events.append({"acronym": "MAD", "type": "method_added", "qname": name, "span": (entry["lineno"], entry["end_lineno"]), "attributes": []})

    # MDE
    for name in sorted(deleted):
        entry = before_methods[name]
        events.append({"acronym": "MDE", "type": "method_deleted", "qname": name, "span": (entry["lineno"], entry["end_lineno"]), "attributes": []})

    # MRE (pair by body hash/ratio)
    added_entries = [after_methods[n] for n in added]
    deleted_entries = [before_methods[n] for n in deleted]
    matched_added: Set[str] = set()
    matched_deleted: Set[str] = set()

    def find_best_match(deleted_entry: Dict) -> Optional[Dict]:
        # exact hash first
        for cand in added_entries:
            if deleted_entry["body_hash"] and deleted_entry["body_hash"] == cand["body_hash"]:
                return cand
        # fallback: hash string similarity (very cheap)
        best = None
        best_score = 0.0
        for cand in added_entries:
            score = 1.0 if cand["body_hash"] == deleted_entry["body_hash"] else 0.0
            if score > best_score:
                best = cand
                best_score = score
        return best if best_score >= 1.0 else None

    for d in deleted_entries:
        c = find_best_match(d)
        if c:
            events.append({
                "acronym": "MRE",
                "type": "method_renamed",
                "qname": f"{d['qname']} -> {c['qname']}",
                "span": (c["lineno"], c["end_lineno"]),
                "attributes": [{"name": "old_name", "value": d["qname"]}, {"name": "new_name", "value": c["qname"]}],
            })
            matched_added.add(c["qname"])
            matched_deleted.add(d["qname"])

    # remove MAD/MDE that are part of MRE
    filtered: List[Dict] = []
    for ev in events:
        if ev["acronym"] == "MAD" and ev["qname"] in matched_added:
            continue
        if ev["acronym"] == "MDE" and ev["qname"] in matched_deleted:
            continue
        filtered.append(ev)
    return filtered


def detect_parameter_changes(file_path: str, source_before: Optional[str], source_after: Optional[str]) -> List[Dict]:
    """
    Emits (for methods present in both versions):
      - PAD (Parameter Added): number of parameters increased
      - PDE (Parameter Deleted): number of parameters decreased
      - PMO (Parameter Modified): count unchanged but names/type/order changed
    """
    events: List[Dict] = []
    before_index = _entity_index(source_before or "", file_path) if source_before is not None else {}
    after_index = _entity_index(source_after or "", file_path) if source_after is not None else {}

    before_methods = {k: v for k, v in before_index.items() if v["kind"] in ("function", "method")}
    after_methods = {k: v for k, v in after_index.items() if v["kind"] in ("function", "method")}

    common = set(before_methods.keys()) & set(after_methods.keys())
    for name in sorted(common):
        b = before_methods[name]
        a = after_methods[name]
        nb, na = len(b["params"]), len(a["params"])
        if na > nb:
            events.append({"acronym": "PAD", "type": "parameter_added", "qname": name, "span": (a["lineno"], a["end_lineno"]),
                           "attributes": [{"name": "before", "value": str(b["params"])}, {"name": "after", "value": str(a["params"])}]})
        elif na < nb:
            events.append({"acronym": "PDE", "type": "parameter_deleted", "qname": name, "span": (a["lineno"], a["end_lineno"]),
                           "attributes": [{"name": "before", "value": str(b["params"])}, {"name": "after", "value": str(a["params"])}]})
        elif nb == na and b["params"] != a["params"]:
            events.append({"acronym": "PMO", "type": "parameter_modified", "qname": name, "span": (a["lineno"], a["end_lineno"]),
                           "attributes": [{"name": "before", "value": str(b["params"])}, {"name": "after", "value": str(a["params"])}]})
    return events


def _parse_doc_params(docstring_text: Optional[str]) -> Set[str]:
    if not docstring_text:
        return set()
    names = set()
    for line in docstring_text.splitlines():
        m1 = re.match(r"^\s*:param\s+([A-Za-z_][A-Za-z0-9_]*)", line)
        m2 = re.match(r"^\s*@param\s+([A-Za-z_][A-Za-z0-9_]*)", line)
        if m1:
            names.add(m1.group(1))
        if m2:
            names.add(m2.group(1))
    return names


def detect_docstring_changes(file_path: str, source_before: Optional[str], source_after: Optional[str]) -> List[Dict]:
    """
    Emits (for module/class/function/method):
      - DAD (Documentation Added): docstring appears
      - DMO (Documentation Modified): docstring changed (params unchanged)
      - DPM (Documentation Parameters Modified): docstring changed and parameter names changed
      - DDE (Documentation Deleted): docstring removed
    """
    events: List[Dict] = []
    before_index = _entity_index(source_before or "", file_path) if source_before is not None else {}
    after_index = _entity_index(source_after or "", file_path) if source_after is not None else {}

    keys = set(before_index.keys()) | set(after_index.keys())
    for name in sorted(keys):
        b = before_index.get(name)
        a = after_index.get(name)
        bdoc = b["docstring"] if b else None
        adoc = a["docstring"] if a else None
        bln, ben = (b["lineno"], b["end_lineno"]) if b else (1, 1)
        aln, aen = (a["lineno"], a["end_lineno"]) if a else (1, 1)

        if bdoc is None and adoc:
            events.append({"acronym": "DAD", "type": "docstring_added", "qname": name, "span": (aln, aen), "attributes": []})
        elif bdoc and adoc and bdoc != adoc:
            bparams = _parse_doc_params(bdoc)
            aparams = _parse_doc_params(adoc)
            if bparams != aparams:
                events.append({"acronym": "DPM", "type": "docstring_parameters_modified", "qname": name, "span": (aln, aen),
                               "attributes": [{"name": "before_params", "value": sorted(bparams)},
                                              {"name": "after_params", "value": sorted(aparams)}]})
            else:
                events.append({"acronym": "DMO", "type": "docstring_modified", "qname": name, "span": (aln, aen), "attributes": []})
        elif bdoc and adoc is None:
            events.append({"acronym": "DDE", "type": "docstring_deleted", "qname": name, "span": (bln, ben), "attributes": []})
    return events


def detect_comment_only_changes(
    file_path: str, source_before: Optional[str], source_after: Optional[str], diff_parsed: Optional[Dict]
) -> List[Dict]:
    """
    Emits:
      - CMO (Comments Modified): only comment lines changed inside any entity span.
    """
    if not diff_parsed:
        return []

    events: List[Dict] = []
    before_index = _entity_index(source_before or "", file_path) if source_before is not None else {}
    after_index = _entity_index(source_after or "", file_path) if source_after is not None else {}

    added_lines = {ln for ln, _ in diff_parsed.get("added", [])}
    deleted_lines = {ln for ln, _ in diff_parsed.get("deleted", [])}

    # test against comment line sets
    for name, entry in (after_index or before_index).items():
        start_line, end_line = entry["lineno"], entry["end_lineno"]
        in_added = {l for l in added_lines if start_line <= l <= end_line}
        in_deleted = {l for l in deleted_lines if start_line <= l <= end_line}
        if (in_added and in_added.issubset(entry["comment_lines"])) or (
            in_deleted and name in before_index and in_deleted.issubset(before_index[name]["comment_lines"])
        ):
            events.append({"acronym": "CMO", "type": "comments_modified", "qname": name, "span": (start_line, end_line), "attributes": []})
    return events


def detect_condition_changes(file_path: str, source_before: Optional[str], source_after: Optional[str]) -> List[Dict]:
    """
    Emits:
      - CAD (Conditional Added): conditions appear
      - COD (Conditional Deleted): conditions removed
      - COM (Conditional Modified): both added and removed conditions
    """
    events: List[Dict] = []
    before_index = _entity_index(source_before or "", file_path) if source_before is not None else {}
    after_index = _entity_index(source_after or "", file_path) if source_after is not None else {}

    keys = set(before_index.keys()) | set(after_index.keys())
    for name in sorted(keys):
        b = before_index.get(name)
        a = after_index.get(name)
        if not b or not a:
            continue
        added_conditions = a["conditions"] - b["conditions"]
        deleted_conditions = b["conditions"] - a["conditions"]
        if added_conditions and not deleted_conditions:
            events.append({"acronym": "CAD", "type": "conditional_added", "qname": name, "span": (a["lineno"], a["end_lineno"]),
                           "attributes": [{"name": "added", "value": list(added_conditions)}]})
        elif deleted_conditions and not added_conditions:
            events.append({"acronym": "COD", "type": "conditional_deleted", "qname": name, "span": (a["lineno"], a["end_lineno"]),
                           "attributes": [{"name": "deleted", "value": list(deleted_conditions)}]})
        elif added_conditions or deleted_conditions:
            events.append({"acronym": "COM", "type": "conditional_modified", "qname": name, "span": (a["lineno"], a["end_lineno"]),
                           "attributes": [{"name": "added", "value": list(added_conditions)},
                                          {"name": "deleted", "value": list(deleted_conditions)}]})
    return events


def detect_statement_changes_fallback(diff_parsed: Optional[Dict]) -> List[Dict]:
    """
    Emits (fallback when not classified above):
      - SAD (Statement Added): only non-comment, non-docstring lines added
      - SDE (Statement Deleted): only non-comment, non-docstring lines deleted
      - SMO (Statement Modified): both added and deleted non-comment, non-docstring lines
    """
    if not diff_parsed:
        return []
    def is_non_comment_non_docstring(line_text: str) -> bool:
        if re.match(r"^\s*#", line_text):
            return False
        if re.match(r'^\s*[ru]?"""', line_text, flags=re.IGNORECASE):
            return False
        return True

    added_lines = [t for _, t in diff_parsed.get("added", []) if is_non_comment_non_docstring(t)]
    deleted_lines = [t for _, t in diff_parsed.get("deleted", []) if is_non_comment_non_docstring(t)]
    events: List[Dict] = []
    if added_lines and not deleted_lines:
        events.append({"acronym": "SAD", "type": "statement_added", "qname": "", "span": (1, 1),
                       "attributes": [{"name": "count", "value": len(added_lines)}]})
    elif deleted_lines and not added_lines:
        events.append({"acronym": "SDE", "type": "statement_deleted", "qname": "", "span": (1, 1),
                       "attributes": [{"name": "count", "value": len(deleted_lines)}]})
    elif added_lines and deleted_lines:
        events.append({"acronym": "SMO", "type": "statement_modified", "qname": "", "span": (1, 1),
                       "attributes": [{"name": "added", "value": len(added_lines)},
                                      {"name": "deleted", "value": len(deleted_lines)}]})
    return events
