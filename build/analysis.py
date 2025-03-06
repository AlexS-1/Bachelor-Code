import os
import subprocess
import spacy
import ast

from pm4py.algo.discovery.ocel.ocdfg import algorithm as ocel_algorithm
from pm4py.visualization.ocel.ocdfg import visualizer as ocel_visualizer
from pm4py.read import read_ocel2_json as read_el
from pm4py.vis import save_vis_ocdfg as write_el
from sklearn import svm
import networkx as nx
from graphviz import Digraph

from build.utils import write_to_file

# Load the spaCy model
nlp = spacy.load("en_core_web_md")

# Define example sentences for each category
corrective_examples = [
    "Fix bug in the code",
    "Resolve issue with the application",
    "Correct error in the function"
]

adaptive_examples = [
    "Add new feature to the application",
    "Enhance the performance of the system",
    "Adapt the code to new requirements"
]

def analyse_message(message):
    # Process the message with spaCy
    message_doc = nlp(message)

    # Calculate similarity with corrective examples
    corrective_similarity = max(message_doc.similarity(nlp(example)) for example in corrective_examples)

    # Calculate similarity with adaptive examples
    adaptive_similarity = max(message_doc.similarity(nlp(example)) for example in adaptive_examples)

    # Classify based on the highest similarity score
    if corrective_similarity > adaptive_similarity:
        return "Corrective"
    else:
        return "Adaptive"

def analyse_ocel(ocel_path, export_path):
    # Exemplary implementation of analysis script
    # Load OCEL data and apply the OCEL algorithm
    # The result is saved as a numpy array and a PNG image
    ocel  = read_el(ocel_path)
    ocdfg = ocel_algorithm.classic.apply(ocel)
    write_el(ocdfg, export_path)

def visit_functions(node, graph, current_function=None):
    """Recursively visit function definitions and calls to build the call graph."""
    if isinstance(node, ast.FunctionDef):
        current_function = node.name
        graph.add_node(current_function, type="function")
    
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        callee = node.func.id
        if current_function:
            graph.add_edge(current_function, callee)
    
    for child in ast.iter_child_nodes(node):
        visit_functions(child, graph, current_function)

def generate_ast_graph(file_content):
    """Parses the file content, extracts AST, and creates a call graph."""
    tree = ast.parse(file_content)
    graph = nx.DiGraph()
    visit_functions(tree, graph)
    return graph

def visualize_call_graph(graph, filename="call_graph"):
    """Visualizes a call graph using Graphviz."""
    dot = Digraph()
    
    for node in graph.nodes():
        dot.node(node, shape="ellipse")

    for caller, callee in graph.edges():
        dot.edge(caller, callee)

    dot.render(filename, format="pdf", view=True, cleanup=True)

def visualise_diff_graph(graph_old, graph_new, filename="diff_graph"):
    """Visualizes the differences between two call graphs."""
    dot = Digraph()
    
    for node in graph_new.nodes():
        if node not in graph_old.nodes():
            dot.node(node, shape="ellipse", color="green")
        else:
            dot.node(node, shape="ellipse")
    
    for caller, callee in graph_new.edges():
        if (caller, callee) not in graph_old.edges():
            dot.edge(caller, callee, color="green")
        else:
            dot.edge(caller, callee)
    
    for node in graph_old.nodes():
        if node not in graph_new.nodes():
            dot.node(node, shape="ellipse", color="red")
    
    for caller, callee in graph_old.edges():
        if (caller, callee) not in graph_new.edges():
            dot.edge(caller, callee, color="red")
    
    dot.render(filename, format="pdf", view=True, cleanup=True)

def analyse_source_code(source_code: str, code_metric: str):
    """Analyse the source code and return the code metric."""
    if code_metric == "cc":
        path = "temp.py"
        write_to_file(path, source_code)
        res = get_cyclomatic_complexity(path)
        os.remove(path)
        return res
    if code_metric == "cg":
        pass
    if code_metric == "helstead":
        path = "temp.py"
        write_to_file(path, source_code)
        result = subprocess.run(
            ['radon', 'hal', path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        os.remove(path)
        return result.stdout.split("\n")
    if code_metric == "docuementation_LOC":
        path = "temp.py"
        write_to_file(path, source_code)
        result = subprocess.run(
            ['radon', 'raw', path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        os.remove(path)
        return result.stdout.split("\n")


def get_cyclomatic_complexity(file_path: str):
    """Get the cyclomatic complexity of a Python file using flake8."""
    result = subprocess.run(
        ['flake8', '--max-complexity', '0', file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Parse the output to extract the cyclomatic complexity
    complexity = 0
    message_count = 0
    for line in result.stdout.split('\n'):
        # Only view lines that violate the max complexity i.e. with code 'C901'
        if 'C901' in line:
            kind = line.split("'")[1]
            # Only count complexity of methods as in PyDriller metric
            if ' ' not in kind:
                parts = line.split()
                # Add up the complexities of all methods in the file
                complexity += int(parts[-1].strip("()"))
                message_count += 1
    
    return complexity, message_count

