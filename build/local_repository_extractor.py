from datetime import datetime
import hashlib
import re
import subprocess
from venv import create
from colorama import init
from numpy import insert, size
from pydriller import Repository
from requests import get
from typing import Dict, List

from tomlkit import date

from build.database_handler import get_attribute_change_times, get_attribute_value_at_time, get_object, insert_commit, insert_event, insert_file, insert_file_metrics, update_attribute
from build.code_quality_analyzer import get_cyclomatic_complexity, get_halstead_metrics, get_line_metrics, get_pylint_score, get_maintainability_index
from build.utils import date_1970, date_formatter, list_to_dict

def _create_commit(commit_sha, author, message, repository, branches, commit_timestamp, contribution_guideline_version, description=None, file_changes=None, parents=None):
    return {
        "commit_sha": commit_sha,
        "message": message,
        "description": str(description),
        "to": str([repository + ":" + branch for branch in branches]),
        "is-authored-by": author,
        "commit_timestamp": commit_timestamp,
        "aggregates": str(file_changes),
        "is-child-of": str(parents),
        "contribution_guideline_version": contribution_guideline_version
    }

def _create_file_metrics(name, filename, file_change_timestamp, commit_sha, method_count, cyclomatic_complexity, theta_1, theta_2, N_1, N_2, loc, lloc, sloc, cloc, dloc, blank_lines, pylint_score):
    return {
        "file-changed_by": name,
        "filename": filename,
        "file_change_timestamp": file_change_timestamp,
        "part-of-commit": commit_sha,
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

def _create_file(name, filename, file_change_timestamp, commit_sha, size_bytes, file_purpose):
    return {
        "file-changed_by": name,
        "filename": filename,
        "file_change_timestamp": file_change_timestamp,
        "part-of-commit": commit_sha,
        "size_bytes": size_bytes,
        "file_purpose": file_purpose,
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
                    date_1970(), 
                    commit.hash,
                    size(source),
                    file_purpose
                )
                insert_file(file_object, collection)

                if file_purpose == "source":
                    source_code_metrics = _extract_source_code_metrics(source)
                    repository_code_metrics[file] = source_code_metrics[0:2]
                    ps, cc, hm, lm = source_code_metrics[1:6]
                    file_metrics = _create_file_metrics(
                        commit.committer.name, 
                        file,
                        date_1970, 
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
                    candidates = _extract_guideline_rule_candidates_combined(
                        file,
                        diff_new,
                        guideline_id=f"g_{date_1970}"
                    )
                    for rule in candidates:
                        insert_event(f"GR_{rule['rule_id']}_{date}",
                                    "guideline_rule_candidate",
                                    date_1970(),
                                    collection,
                                    [rule],
                                    [])
                    
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

def get_and_insert_local_data(repo_path: str, from_date: datetime, to_date: datetime, file_types: list, do_snapshot: bool = False):
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
    repository_code_metrics = _get_snapshot_code_quality(repo_path, from_date, file_types, collection) if do_snapshot else {}
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
        contribution_guidelines = {}

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
                insert_event(
                    f"CF_{commit_timestamp}", 
                    "change_file", 
                    commit_timestamp, 
                    collection, 
                    [], 
                    [{"qualifier": file_action, "objectId": file_actor}])

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
                    file_purpose
                )
                insert_file(file, collection)

                # For every source file additionally update metrics
                if file_purpose == "source" and modified_file.new_path and modified_file.source_code:
                    source_code_metrics = _extract_source_code_metrics(modified_file.source_code)
                    repository_code_metrics[modified_file.new_path] = source_code_metrics[0:2]
                    ps, cc, hm, lm = source_code_metrics[1:6]
                    file_metrics = _create_file_metrics(
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
                    insert_file_metrics(file_metrics, collection)

                # For every documentation document check wether it is a contribution relevant document
                if file_purpose == "documentation" and modified_file.new_path and modified_file.source_code:
                    word_count = len(modified_file.source_code.split())
                    diff_new = list_to_dict(modified_file.diff_parsed["added"])
                    candidates = _extract_guideline_rule_candidates_combined(
                        modified_file.new_path,
                        diff_new,
                        guideline_id=f"g_{commit_timestamp}"
                    )
                    for rule in candidates:
                        insert_event(f"GR_{rule['rule_id']}_{commit_timestamp}",
                                    "guideline_rule_candidate",
                                    commit_timestamp,
                                    collection,
                                    [{"attributes": rule}],
                                    [])
                    
                    # diff_new = list_to_dict(modified_file.diff_parsed["added"])
                    # for line, content in diff_new.items():
                    #     for keyword in set(keyword_topic.keys()):
                    #         if keyword.lower() in content.split():
                    #             print(f"LOG: Found line \"{content}\" for \"{keyword}\" in \"{modified_file.new_path}\"")
                    #             contribution_guidelines[modified_file.new_path] = {
                    #                 line: content,
                    #                 keyword.lower(): keyword_topic[keyword]
                    #             }

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
            # contribution_guideline_version,
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

NORMATIVE_RE = re.compile(r'\b(must|should|shall|required|require|needs? to|has to|at least|minimum|no more than|within|before|after|days?|hours?)\b', re.I)

PATTERNS = {
    "min_approvals": re.compile(r'(?:at least|minimum of)\s+(\d+)\s+(?:approvals?|reviewers?)', re.I),
    "max_open_days": re.compile(r'(?:close|closed|stale).{0,30}(?:after|within)\s+(\d+)\s+day', re.I),
    "max_loc_changed": re.compile(r'(?:no more than|less than|under|max(?:imum)? of)\s+(\d+)\s+(?:lines?|loc)', re.I),
    "require_issue_link": re.compile(r'(?:must|should).{0,40}(?:reference|link).{0,15}(?:issue|#\d+)', re.I),
    "require_tests": re.compile(r'(?:must|should).{0,40}tests?', re.I),
    "require_lint_pass": re.compile(r'(?:must|should).{0,40}(?:lint|style).{0,10}(?:pass|clean)', re.I),
}

TOPIC_ORDER = [
    ("Pull Request Acceptance Criteria", re.compile(r'(approv|review|approval|minimum.*review)', re.I)),
    ("Contribution Workflow", re.compile(r'(pull request|merge|rebase|branch|workflow)', re.I)),
    ("Continuous Integration Tools", re.compile(r'(ci|pipeline|test|coverage|lint|bot|build|check)', re.I)),
    ("Traceability", re.compile(r'(issue|#\d+|closes\s+#|references?)', re.I)),
    ("Project Orientation", re.compile(r'(owner|maintain|contact|governance|license|cla)', re.I)),
    ("Size Constraints", re.compile(r'(lines changed|loc|lines?)', re.I)),
]

COUNT_MAP = {
    "a":1,"an":1,"one":1,"two":2,"three":3,"four":4,"five":5
}

RX_MIN_APPROVALS = re.compile(r'\brequire(?:s)?\s*\+1\s+by\s+(?P<count>a|an|one|two|three|four|five|\d+)\s+core\s+contributor(?:s)?', re.I)

RX_LAZY_CONSENSUS = re.compile(r'no\s*-1\s+by\s+a\s+core\s+contributor', re.I)

def extract_min_approvals(sentence):
    m = RX_MIN_APPROVALS.search(sentence)
    if not m:
        return None
    raw = m.group('count').lower()
    approvals = COUNT_MAP.get(raw, int(raw))
    lazy = bool(RX_LAZY_CONSENSUS.search(sentence))
    return {"constraint_type":"min_approvals",
            "operator":">=",
            "parameter_value":approvals,
            "lazy_consensus":lazy}

def split_sentences(text: str):
    # Lightweight sentence splitter
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', text.strip())
    return [p.strip() for p in parts if p.strip()]

def topic_for(sentence: str) -> str:
    for name, rx in TOPIC_ORDER:
        if rx.search(sentence):
            return name
    return "Other"

def detect_rule(sentence: str):
    # Specialized phrase (+1 by X core contributors) first
    specialized = extract_min_approvals(sentence)
    if specialized:
        specialized["confidence_heuristic"] = 0.95
        return specialized
    for ctype, rx in PATTERNS.items():
        m = rx.search(sentence)
        if m:
            val = m.group(1) if m.groups() else None
            operator = ">=" if ctype == "min_approvals" else \
                       "<=" if ctype in ("max_open_days", "max_loc_changed") else "presence"
            return {
                "constraint_type": ctype,
                "operator": operator,
                "parameter_value": val,
                "confidence_heuristic": 0.9
            }
    return {
        "constraint_type": "unclassified",
        "operator": "",
        "parameter_value": "",
        "confidence_heuristic": 0.3
    }

def _candidate_sentences(added_lines: Dict[int, str]):
    # Merge contiguous lines into blocks to avoid fragmenting sentences
    sorted_lines = sorted(added_lines.items())
    block = []
    prev = None
    for ln, txt in sorted_lines:
        if prev is None or ln == prev + 1:
            block.append((ln, txt))
        else:
            yield from _emit_block(block)
            block = [(ln, txt)]
        prev = ln
    if block:
        yield from _emit_block(block)

def _emit_block(block):
    text = " ".join(t for _, t in block)
    for sent in split_sentences(text):
        norm = sent.lower()
        if NORMATIVE_RE.search(norm) or any(p.search(norm) for p in PATTERNS.values()):
            lines = [ln for ln, _ in block]
            yield {
                "sentence": sent,
                "line_start": lines[0],
                "line_end": lines[-1],
            }

def _extract_guideline_rule_candidates(file_path: str, added_lines: Dict[int, str], guideline_id: str):
    seen = set()
    results = []
    for cand in _candidate_sentences(added_lines):
        s = cand["sentence"]
        h = hashlib.sha1(s.encode()).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        topic = topic_for(s)
        rule_meta = detect_rule(s)
        importance = "MUST" if re.search(r'\bmust|shall|required|has to|needs to\b', s, re.I) else \
                     "SHOULD" if re.search(r'\bshould\b', s, re.I) else "UNSPECIFIED"
        results.append({
            "rule_id": f"R_{h[:10]}",
            "guideline_id": guideline_id,
            "source_text": s,
            "topic": topic,
            "importance": importance,
            **rule_meta,
            "effective_from": guideline_id[2:],
            "status": "active",
            "subject_type": "pull_request" if "pull request" in s.lower() else "",
            "detection_method": "sentence_heuristic",
        })
    return results

def _extract_guideline_rule_candidates_combined(file_path: str, added_lines: Dict[int, str], guideline_id: str):
    """Combine heuristic sentence-based extraction with keyword-topic signals.

    1. Run sentence heuristic extractor (normative + regex patterns).
    2. Add any new-line keyword hits not already covered by heuristic sentences.
    """
    heuristic_rules = _extract_guideline_rule_candidates(file_path, added_lines, guideline_id)
    covered_texts = {r["source_text"].lower() for r in heuristic_rules}
    keyword_rules = []
    for ln, text in added_lines.items():
        lowered = text.lower().strip()
        if not lowered:
            continue
        matched_topics = [topic for kw, topic in _keyword_topic.items() if kw.lower() in lowered]
        if matched_topics:
            # Skip if heuristic already captured (substring or exact)
            if any(lowered in ht or ht in lowered for ht in covered_texts):
                continue
            topic = matched_topics[0]
            h = hashlib.sha1(text.encode()).hexdigest()
            keyword_rules.append({
                "rule_id": f"RKW_{h[:10]}",
                "guideline_id": guideline_id,
                "source_text": text.strip(),
                "topic": topic,
                "importance": "UNSPECIFIED",
                "constraint_type": "keyword_signal",
                "operator": "",
                "parameter_value": "",
                "confidence_heuristic": 0.6,
                "effective_from": guideline_id[2:],
                "status": "active",
                "subject_type": "pull_request" if "pull request" in lowered else "",
                "detection_method": "keyword",
            })
    return heuristic_rules + keyword_rules

_keyword_topic = {
                    "review": "Pull Request Acceptance Criteria",
                    "pull request": "Contribution Workflow",
                    "continuous integration": "Continuous Integration Tools",
                    "CI/CD": "Continuous Integration Tools",
                    "test": "Continuous Integration Tools",
                    "workflow": "Contribution Workflow",
                    "owner": "Project Orientation",
                    "protection": "Contribution Workflow",
                    "requirement": "Pull Request Acceptance Criteria",
                    "CLA": "Project Orientation",
                    "submit": "Contribution Workflow",
                    "approv": "Pull Request Acceptance Criteria",
                    "bot": "Continuous Integration Tools",
                    "check": "Continuous Integration Tools",
                    "link": "Traceability",
                    "how to": "Project Orientation",
                    "knowledge": "Project Orientation",
                    "CI": "Continuous Integration Tools",
                    "MUST": "Pull Request Acceptance Criteria",
                    "SHOULD": "Pull Request Acceptance Criteria",
                    "REQUIRED": "Pull Request Acceptance Criteria",
                    "MINIMUM": "Pull Request Acceptance Criteria",
                    "DAYS": "Pull Request Acceptance Criteria",
                    "APPROVAL": "Pull Request Acceptance Criteria",
                    "REVIEW": "Pull Request Acceptance Criteria",
                    "TEST": "Continuous Integration Tools",
                    "LINT": "Continuous Integration Tools",
                    "ISSUE": "Traceability"
                }
