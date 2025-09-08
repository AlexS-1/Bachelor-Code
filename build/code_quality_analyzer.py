"""Static analysis helpers for computing code quality metrics.

Public API (imported by other modules):
    - get_maintainability_index
    - calculate_maintainability_index
    - calculate_maintainability_index_like_radon
    - get_pylint_score
    - get_line_metrics
    - get_halstead_metrics
    - get_cyclomatic_complexity
    - get_file_metrics_at

Other helper classes mimic Radon's legacy Python2 fallback structures.
"""

import math
import os
import re
import subprocess
from pylint.lint import Run
from pylint.reporters.base_reporter import BaseReporter
from radon.complexity import cc_visit
from radon.metrics import mi_visit
from radon.metrics import mi_compute as mi
from radon.metrics import h_visit
from radon.raw import analyze

from build.database_handler import get_attribute_value_at_time
class ScoreOnlyReporter(BaseReporter):
    """Minimal Pylint reporter returning only the global score (used as fallback)."""

    def __init__(self, output=None) -> None:  # pragma: no cover (simple wiring)
        super().__init__(output)
        self.name = "score-only"

    def handle_message(self, msg):  # pragma: no cover
        pass

    def writeln(self, string = ""):
        pass

    def display_reports(self, layout):  # pragma: no cover
        pass

    def _display(self, layout):  # pragma: no cover
        pass

    def on_close(self, stats, previous_stats):  # pragma: no cover
        pass

def get_maintainability_index(source_code: str, filepath: str = "temp_code.py"):
    """Return Radon's maintainability index for a source string.

    Falls back to invoking a subprocess (compat path) if direct analysis fails.
    Returns 0 on failure.
    """
    try:
        return mi_visit(source_code, True)
    except (SyntaxError, ValueError):
        filename = filepath.split('/')[-1]
        with open(filename, "w", encoding="utf-8") as f:
            f.write(source_code)
        result = subprocess.run(
            ["python2", "-m", "radon", "mi", "-s", filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        maintainability_output = result.stdout
        match_mi = re.search(r"\((\d+)\)", maintainability_output)
        if match_mi:
            os.remove(filename)
            return float(match_mi.group(1))
        print(f"ERROR: MI fallback failed for {filepath}: {result.stderr}")
        return 0
        
def calculate_maintainability_index(N1, N2, h1, h2, complexity, loc):
    """Compute classic MI variant (scaled 0..100)."""
    N = N1 + N2
    h = h1 + h2
    volume = N * math.log2(h) if h > 0 else 0
    try:
        raw_mi = 171 - 5.2 * math.log(volume) - 0.23 * complexity - 16.2 * math.log(loc)
    except (ValueError, ZeroDivisionError):
        print(
            f"ERROR: MI calc inputs invalid N1={N1} N2={N2} h1={h1} h2={h2} complexity={complexity} loc={loc}"
        )
        raw_mi = 0.0
    return min(max(0.0, raw_mi * 100 / 171.0), 100.0)

def calculate_maintainability_index_like_radon(N1, N2, h1, h2, complexity, sloc, comments):
    """Compute Radon-like MI using Radon's `mi_compute` helper."""
    N = N1 + N2
    h = h1 + h2 if h1 + h2 > 0 else 1
    halstead_volume = N * math.log2(h) if h > 0 else 0
    return mi(halstead_volume, complexity, sloc, comments)

# def get_pylint_score(source_code, filepath='temp_code.py'):
#     """
#     Calculate the pylint score of a given source code file.
#     Args:
#         source_code (str): The source code to analyze.
#         filepath (str): The path to the file to save the source code temporarily.
#     Returns:
#         float: The pylint score of the source code.
#     """
#     filename = filepath.split("/")[-1]
#     with open(filename, 'w') as f:
#         f.write(source_code)
#     try:
#         pylint_results = Run([filename], ScoreOnlyReporter(), exit=True)
#         os.remove(filename)
#         return pylint_results.linter.stats.global_note
#     except:
#         print(f"Error calculating pylint score for file at {filepath}")
#         return 0
    
def get_pylint_score(source_code, filepath='temp_code.py') -> float:
    """Run Pylint for a piece of code and extract its numeric score (0..10)."""
    filename = filepath.split("/")[-1]
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(source_code)
    try:
        result = subprocess.run(
            ['python', '-m', 'pylint', filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
                text=True,
                check=False
        )
        match = re.search(r"rated at ([\d\.]+)/10", result.stdout)
        if match:
            os.remove(filename)
            print(f"{match.group(1)}")
            return float(match.group(1))
        else:
            pylint_results = Run([filename], ScoreOnlyReporter(), exit =False)
            os.remove(filename)
            return float(pylint_results.linter.stats.global_note)
    except (RuntimeError, OSError) as exc:
        print(f"ERROR: Pylint score failed for {filepath}: {exc}")
    return 0

class Python2LineMetics:
    """Fallback container when Radon direct call fails (legacy format)."""
    def __init__(self, loc, lloc, sloc, comments, single_comments, multi, blank):
        self.loc = loc
        self.lloc = lloc
        self.sloc = sloc
        self.comments = comments
        self.single_comments = single_comments
        self.multi = multi
        self.blank = blank

    def __repr__(self):
        return f"""
        LOC: {self.loc}, 
        LLOC: {self.lloc}, 
        SLOC: {self.sloc}, 
        Comments: {self.comments}, 
        Single Comments: {self.single_comments}, 
        Multi: {self.multi}, 
        Blank: {self.blank}"""

def get_line_metrics(source_code, filepath='temp_code.py'):
    """Return raw line metrics (LOC, LLOC, etc.) via Radon or subprocess fallback."""
    try:
        return analyze(source_code)
    except (SyntaxError, ValueError):
        filename = filepath.split("/")[-1]
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(source_code)
        result = subprocess.run(
            ['python2', '-m', 'radon', 'raw', filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
    line_metrics_output = result.stdout
    loc = re.search(r"LOC:\s*(\d+)", line_metrics_output)
    lloc = re.search(r"LLOC:\s*(\d+)", line_metrics_output)
    sloc = re.search(r"SLOC:\s*(\d+)", line_metrics_output)
    comments = re.search(r"Comments:\s*(\d+)", line_metrics_output)
    single_comments = re.search(r"Single comments:\s*(\d+)", line_metrics_output)
    multi = re.search(r"Multi:\s*(\d+)", line_metrics_output)
    blank = re.search(r"Blank:\s*(\d+)", line_metrics_output)
    if loc and lloc and sloc and comments and single_comments and multi and blank:
        os.remove(filename)
        return Python2LineMetics(
            loc=int(loc.group(1)),
            lloc=int(lloc.group(1)),
            sloc=int(sloc.group(1)),
            comments=int(comments.group(1)),
            single_comments=int(single_comments.group(1)),
            multi=int(multi.group(1)),
            blank=int(blank.group(1))
        )
    else:
        print(f"Error calculating maintainability index for {filepath}: {result.stderr}")
        return Python2LineMetics(
            loc=0,
            lloc=0,
            sloc=0,
            comments=0,
            single_comments=0,
            multi=0,
            blank=0
        )
        
class Python2HelsteadTotal:
    def __init__(self, h1, h2, N1, N2):
        self.h1 = h1
        self.h2 = h2
        self.N1 = N1
        self.N2 = N2

class Python2HelsteadReport:
    def __init__(self, h1, h2, N1, N2):
        self.total = Python2HelsteadTotal(h1, h2, N1, N2)

    def __repr__(self):
        return f"""
        HelsteadReport(total: 
        h1={self.total.h1}, 
        h2={self.total.h2}, 
        N1={self.total.N1}, 
        N2={self.total.N2})"""

def get_halstead_metrics(source_code, filepath='temp_code.py'):
    """Return Halstead metrics (h_visit) or legacy fallback structure."""
    try:
        return h_visit(source_code)
    except (SyntaxError, ValueError):
        filename = filepath.split("/")[-1]
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(source_code)
        result = subprocess.run(
            ['python2', '-m', 'radon', 'raw', filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
    line_metrics_output = result.stdout
    theta_1 = re.search(r"h1:\s*(\d+)", line_metrics_output)
    theta_2 = re.search(r"h1:\s*(\d+)", line_metrics_output)
    N1 = re.search(r"N1:\s*(\d+)", line_metrics_output)
    N2 = re.search(r"N2:\s*(\d+)", line_metrics_output)
    if theta_1 and theta_2 and N1 and N2:
        os.remove(filename)
        return Python2HelsteadReport(
            h1=int(theta_1.group(1)),
            h2=int(theta_2.group(1)),
            N1=int(N1.group(1)),
            N2=int(N2.group(1))
        )
    else:
        print(f"File at {filepath} does not compile: {result.stderr}")
        return Python2HelsteadReport(
            h1=0,
            h2=0,
            N1=0,
            N2=0
        )
        
def get_cyclomatic_complexity(source_code, filepath='temp_code.py'):
    """Sum cyclomatic complexity of all blocks in source (fallback to subprocess)."""
    try:
        res = cc_visit(source_code)
        return sum(r.complexity for r in res)
    except (SyntaxError, ValueError):
        filename = filepath.split("/")[-1]
        with open(filename, "w", encoding='utf-8') as f:
            f.write(source_code)
        result = subprocess.run(
            ['python2', '-m', 'radon', 'cc', '-s', filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
    cc_output = result.stdout
    match_cc = re.search(r"\((\d+)\)", cc_output)
    if match_cc:
        os.remove(filename)
        return int(match_cc.group(1))
    else:
        print(f"File at {filepath} does not compile: {result.stderr}")
        return 0

def get_file_metrics_at(file_id, commit_date, collection):
    """Return (maintainability_index, pylint_score) for a file at a commit timestamp."""
    h1 = get_attribute_value_at_time(file_id, "theta_1", commit_date, collection) or 0
    h2 = get_attribute_value_at_time(file_id, "theta_2", commit_date, collection) or 0
    n_1 = get_attribute_value_at_time(file_id, "N_1", commit_date, collection) or 0
    n_2 = get_attribute_value_at_time(file_id, "N_2", commit_date, collection) or 0
    cc = get_attribute_value_at_time(file_id, "cyclomatic_complexity", commit_date, collection) or 0
    loc = get_attribute_value_at_time(file_id, "loc", commit_date, collection) or 0
    m_index = calculate_maintainability_index(n_1, n_2, h1, h2, cc, loc) or 0
    pl = get_attribute_value_at_time(file_id, "pylint_score", commit_date, collection) or 0
    return m_index, pl
