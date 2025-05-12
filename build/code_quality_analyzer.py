# Get the maintainability index for a given source code file
import os
import subprocess
from radon.metrics import mi_visit
from pylint.reporters.base_reporter import BaseReporter
import re
from pylint.lint import Run
import os

class ScoreOnlyReporter(BaseReporter):
    """A reporter that only returns the score of the code quality analysis."""
    def __init__(self, output = None) -> None:
        super().__init__(output)
        self.name = "score-only"
    
    def handle_message(self, msg):
        pass

    def writeln(self, string = ""):
        pass

    def display_reports(self, layout):
        pass

    def on_close(self, stats, previous_stats):
        return stats.global_note

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
            return int(match_mi.group(1))
        else:
            raise Exception(f"File at {filepath} does not compile: {result.stderr}")
        
def get_pylint_score(source_code, filepath='temp_code.py'):
    """
    Calculate the pylint score of a given source code file.
    Args:
        source_code (str): The source code to analyze.
        filepath (str): The path to the file to save the source code temporarily.
    Returns:
        float: The pylint score of the source code.
    """
    filename = filepath.split("/")[-1]
    with open(filename, 'w') as f:
        f.write(source_code)
    try:
        pylint_results = Run([filename], ScoreOnlyReporter(), exit=False)
        os.remove(filename)
        return pylint_results.linter.stats.global_note
    except Exception as e:
        print(f"Error calculating pylint score for file at {filepath}: {e}")
        return None