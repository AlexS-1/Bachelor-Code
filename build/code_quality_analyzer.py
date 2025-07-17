from datetime import datetime
import math
import os
import subprocess
from matplotlib.pylab import f
from radon.metrics import mi_visit, h_visit
from radon.raw import analyze
from radon.complexity import cc_visit
from pylint.reporters.base_reporter import BaseReporter
import re
from pylint.lint import Run
import os

from sympy import Q
from tomlkit import date

from build.database_handler import get_attribute_times, get_attribute_value_at_time, get_object
class ScoreOnlyReporter(BaseReporter):
    def __init__(self, output = None) -> None:
        super().__init__(output)
        self.name = "score-only"
    
    def handle_message(self, msg):
        pass

    def writeln(self, string = ""):
        pass

    def display_reports(self, layout):
        pass

    def _display(self, layout):
        pass

    def on_close(self, stats, previous_stats): 
        pass

def get_maintainability_index(source_code, filepath='temp_code.py'):
    """
    Calculate the maintainability index of a given source code file.
    Args:
        source_code (str): The source code to analyze.
        filepath (str): The path to the file to save the source code temporarily.
    Returns:
        int: The maintainability index of the source code.
    """
    try:
        return mi_visit(source_code, True)
    except Exception as e:
        filename = filepath.split('/')[-1]
        with open(filename, "w") as f:
            f.write(source_code)
        result = subprocess.run(
            ['python2', '-m' 'radon', "mi", "-s", filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        maintainability_output = result.stdout
        match_mi = re.search(r"\((\d+)\)", maintainability_output)
        if match_mi:
            os.remove(filename)
            return float(match_mi.group(1))  
        else:
            print(f"Error calculating maintainability index for file at {filepath}: {result.stderr}")
            return 0
        
def calculate_maintainability_index(loc): #N1, N2, h1, h2, complexity, loc):
    # N = N1 + N2
    # h = h1 + h2
    # volume = N * math.log2(h) if h > 0 else 0
    # mi = 171 - 5.2 * math.log(volume) - 0.23 * complexity - 16.2 * math.log(loc)
    # mi = max(0, mi/ 171)
    
    # FIXME Temporary overwrite for maintainability index
    if loc is None or loc <= 0:
        print(f"LOC is None or <= 0, cannot calculate maintainability index, setting to 0")
        return 0
    try:
        mi = 171 - 5.2 * math.log(45 * loc - 428) - 0.23 * (0.22 * loc - 1.9)  - 16.2 * math.log(loc)
    except:
        print(f"Error calculating maintainability index for loc=")
        mi = 0
    mi = max(0, mi/ 171)
    return mi

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
    filename = filepath.split("/")[-1]
    with open(filename, 'w') as f:
        f.write(source_code)
    try:
        result = subprocess.run(
            ['python', '-m', 'pylint', filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
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
    except Exception as e:
        print(f"Error calculating pylint score for file at {filepath}: {e}")
        return 0

class Python2LineMetics:
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
    try:
        return analyze(source_code)
    except Exception as e:
        filename = filepath.split("/")[-1]
        with open(filename, 'w') as f:
            f.write(source_code)
        result = subprocess.run(
            ['python2', '-m' 'radon', "raw", filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
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
    """
    Calculate the Halstead metrics of a given source code file.
    Args:
        source_code (str): The source code to analyze.
        filepath (str): The path to the file to save the source code temporarily.
    Returns:
        dict: A dictionary containing the Halstead metrics.
    """
    try:
        return h_visit(source_code)
    except Exception as e:
        filename = filepath.split("/")[-1]
        with open(filename, 'w') as f:
            f.write(source_code)
        result = subprocess.run(
            ['python2', '-m' 'radon', "raw", filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
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
    """
    Calculate the Cyclomatic Complexity of a given source code file.
    Args:
        source_code (str): The source code to analyze.
        filepath (str): The path to the file to save the source code temporarily.
    Returns:
        int: The Cyclomatic Complexity of the source code.
    """
    try:
        return cc_visit(source_code)
    except Exception as e:
        filename = filepath.split("/")[-1]
        with open(filename, "w") as f:
            f.write(source_code)
        result = subprocess.run(
            ['python2', '-m' 'radon', "cc", "-s", filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        cc_output = result.stdout
        match_cc = re.search(r"\((\d+)\)", cc_output)
        if match_cc:
            os.remove(filename)
            return int(match_cc.group(1))
        else:
            raise Exception(f"File at {filepath} does not compile: {result.stderr}")

def calculate_maintainability_indeces(id, collection):
    """
    Get the maintainability indeces for a given object in the collection.
    Args:
        id (str): The ID of the object to analyze.
        collection (str): The name of the collection to query.
    Returns:
        float: The maintainability index of the file 
    """
    origin = get_object(id, collection)
    if origin is None:
        print(f"Object with id {id} not found in collection {collection}")
        return None
    code_quality_metrics = dict()
    if origin["type"] == "file":
        times = get_attribute_times(id, collection)
        for time in times:
            h1 = get_attribute_value_at_time(id, "theta_1", time, collection) 
            h2 = get_attribute_value_at_time(id, "theta_2", time, collection)
            N1 = get_attribute_value_at_time(id, "N_1", time, collection)
            N2 = get_attribute_value_at_time(id, "N_2", time, collection)
            cyclomatic_complexity = get_attribute_value_at_time(id, "cyclomatic_complexity", time, collection)
            loc = get_attribute_value_at_time(id, "loc", time, collection)
            mi = calculate_maintainability_index(loc) #N1, N2, h1, h2, cyclomatic_complexity, loc)
            pl = get_attribute_value_at_time(id, "pylint_score", time, collection)
            code_quality_metrics[time] = {
                "maintainability_index": mi,
                "pylint_score": pl,
            }
    if origin["type"] == "commit":
        commit_time = datetime.fromisoformat(origin["attributes"][0]["time"])
        before_commit = commit_time.replace((commit_time.second - 1) % 60)
        for time in [before_commit, commit_time]:

            h1 = get_attribute_value_at_time(id, "h1", time, collection) 
            h2 = get_attribute_value_at_time(id, "h2", time, collection)
            N1 = get_attribute_value_at_time(id, "N1", time, collection)
            N2 = get_attribute_value_at_time(id, "N2", time, collection)
            cyclomatic_complexity = get_attribute_value_at_time(id, "cyclomatic_complexity", time, collection)
            loc = get_attribute_value_at_time(id, "loc", time, collection)
            mi = calculate_maintainability_index(loc) # N1, N2, h1, h2, cyclomatic_complexity, loc)
            pl = get_attribute_value_at_time(id, "pylint_score", time, collection)
            code_quality_metrics[time] = {
                "maintainability_index": mi,
                "pylint_score": pl,
            }
    return code_quality_metrics

def get_file_metrics_at(file_id, commit_date, collection):
    h1 = get_attribute_value_at_time(file_id, "theta_1", commit_date, collection) or 0
    h2 = get_attribute_value_at_time(file_id, "theta_2", commit_date, collection) or 0
    N1 = get_attribute_value_at_time(file_id, "N_1", commit_date, collection) or 0
    N2 = get_attribute_value_at_time(file_id, "N_2", commit_date, collection) or 0
    cyclomatic_complexity = get_attribute_value_at_time(file_id, "cyclomatic_complexity", commit_date, collection) or 0
    loc = get_attribute_value_at_time(file_id, "loc", commit_date, collection) or 0
    mi = calculate_maintainability_index(loc) or 0 #N1, N2, h1, h2, cyclomatic_complexity, loc) 
    pl = get_attribute_value_at_time(file_id, "pylint_score", commit_date, collection) or 0
    return mi, pl
