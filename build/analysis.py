import os
import re
import subprocess
import spacy
import ast
import networkx as nx

from turtle import st
from pm4py.algo.discovery.ocel.ocdfg import algorithm as ocel_algorithm
from pm4py.visualization.ocel.ocdfg import visualizer as ocel_visualizer
from pm4py.read import read_ocel2_json as read_el
from pm4py.vis import save_vis_ocdfg as write_el
from sklearn import svm
from graphviz import Digraph
from numpy import log, sin, sqrt
from pylint.lint import Run

from build.utils import write_to_file

# Load the spaCy model
# nlp = spacy.load("en_core_web_md")

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

# def analyse_message(message):
#     # Process the message with spaCy
#     message_doc = nlp(message)

#     # Calculate similarity with corrective examples
#     corrective_similarity = max(message_doc.similarity(nlp(example)) for example in corrective_examples)

#     # Calculate similarity with adaptive examples
#     adaptive_similarity = max(message_doc.similarity(nlp(example)) for example in adaptive_examples)

#     # Classify based on the highest similarity score
#     if corrective_similarity > adaptive_similarity:
#         return "Corrective"
#     else:
#         return "Adaptive"

def analyse_ocel(ocel_path, export_path):
    # Exemplary implementation of analysis script
    # Load OCEL data and apply the OCEL algorithm
    # The result is saved as a numpy array and a PNG image
    ocel  = read_el(ocel_path)
    ocdfg = ocel_algorithm.classic.apply(ocel)
    write_el(ocdfg, export_path)

# Call Graph generation

def visit_functions(node, functions=None, current_function=None):
    """Recursively visit function definitions and return them as a list"""
    if functions is None:
        functions = []
    
    if isinstance(node, ast.FunctionDef):
        functions.append(node)
        current_function = node
    
    for child in ast.iter_child_nodes(node):
        visit_functions(child, functions, current_function)
    
    return functions

def generate_ast_graph(file_content):
    """Parses the file content, extracts AST, and creates a call graph."""
    tree = ast.parse(file_content)
    graphs = []
    function_definitions = visit_functions(tree)
    for function in function_definitions:
        graph = Digraph(strict=True)
        graphs.append(check_ast(function, graph))
    return graphs

def visualize_call_graph(graph, filename="call_graph"):
    """Visualizes a call graph using Graphviz."""
    graph.render(filename, format="svg", cleanup=True)

def get_filename_for_graph(folder, file, sha, graph: Digraph, revision = "new"):
    return f"{folder}/{sha[:7]}-{file.split('/')[-1].replace(".", "-")}-{graph.body[0].split('"')[1].split('- ')[1]}-{revision}"

def visualise_diff_graph(graph_old, graph_new, filename="diff_graph"):
    """Visualizes the differences between two call graphs."""
    dot = Digraph()
    
    for node in nodes(graph_new):
        if node not in nodes(graph_old):
            dot.body.append(node)
        else:
            dot.node(node, shape="ellipse")
    
    for caller, callee in edges(graph_new):
        if (caller, callee) not in edges(graph_old):
            dot.edge(caller, callee, color="green")
        else:
            dot.edge(caller, callee)
    
    for node in nodes(graph_old):
        if node not in nodes(graph_new):
            dot.node(node, shape="ellipse", color="red")
    
    for caller, callee in edges(graph_old):
        if (caller, callee) not in edges(graph_new):
            dot.edge(caller, callee, color="red")
    
    dot.render(filename, format="svg", cleanup=True)

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
    if code_metric == "loc":
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
    if code_metric == "pylint":
        path = "temp.py"
        write_to_file(path, source_code)
        options = [
            path, 
            "--output-format=json:somefile.json"
        ]
        results = Run(options, exit=False)
        os.remove(path)
        os.remove("somefile.json")
        return results.linter.stats.global_note


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

def get_code_metrics(commit_hash, commit_data, repo_path):
    cc_old, message_count_old = analyse_source_code(commit_data["source_old"], "cc")
    cc_new, message_count_new = analyse_source_code(commit_data["source_new"], "cc")
    print(f"HALSTEAD: Changed from {analyse_source_code(commit_data["source_old"], 'helstead')[1:5]} to {analyse_source_code(commit_data["source_new"], 'helstead')[1:5]}")
    print(f"CYCLOMATIC COMPLEXITY: The average cyclomatic complexity per method changed from {cc_old/message_count_old} to {cc_new/message_count_new}")
    print(f"MCCABE'S WEIGHTED METHOD COUNT: The McCabe's weighted method count changed from {cc_old} to {cc_new}")
    print(f"HALSTEAD'S COMPLEXITY MEASURES: The Halstead's complexity measures e.g. for Effort changed from {analyse_source_code(commit_data["source_old"], 'helstead')[10].split(":")[-1]} to {analyse_source_code(commit_data["source_new"], 'helstead')[10].split(":")[-1]}")
    loc = int(analyse_source_code(commit_data["source_old"], 'docuementation_LOC')[4].split(":")[1])
    loc_new = int(analyse_source_code(commit_data["source_new"], 'docuementation_LOC')[4].split(":")[1])
    print(f"LINES OF COMMENT: The lines of comment changed from {loc} to {loc_new}")
    print(f"DOCUMENTATION RATIO: The documentation ratio changed from {int(analyse_source_code(commit_data["source_old"], 'docuementation_LOC')[6].split(":")[1])/int(analyse_source_code(commit_data["source_old"], 'docuementation_LOC')[1].split(":")[1])} to {int(analyse_source_code(commit_data["source_new"], 'docuementation_LOC')[6].split(":")[1])/int(analyse_source_code(commit_data["source_new"], 'docuementation_LOC')[1].split(":")[1])}")
    print(f"COMMENT LINES OF CODE: The comment lines of code changed from {analyse_source_code(commit_data["source_old"], 'docuementation_LOC')[4].split(":")[1]} to {analyse_source_code(commit_data["source_new"], 'docuementation_LOC')[4].split(":")[1]}")
    print(f"METHOD COUNT: The method count changed from {message_count_old} to {message_count_new}")
    print(f"CALL GRAPH: The call graphs are as follows and the differences are visualized in the diff graph")
    sloc_old = len([line for line in commit_data["source_old"].split("\n")])
    sloc_new = len([line for line in commit_data["source_new"].split("\n")])
    print(f"MAINTAINABIKITY INDEX: The maintainability index changed from {max(0,(171 - 5.2 * log(float(analyse_source_code(commit_data["source_old"], 'helstead')[8].split(":")[-1])) - 0.23 * (cc_old) - 16.2 * log(sloc_old) + 50* sin(sqrt(2.4 * (loc)/(loc_new))))*100 / 171)} to {max(0,(171 - 5.2 * log(float(analyse_source_code(commit_data["source_new"], 'helstead')[8].split(":")[-1])) - 0.23 * (cc_new) - 16.2 * log(sloc_new)+50*sin(sqrt(2.4 * (loc)/(loc_new))))*100 / 171)}") if loc_new != 0 else 0
    print(f"CODE QUALITY: The code quality changed from {analyse_source_code(commit_data["source_old"], 'pylint')[-3].split("at ")[-1].split(" ")[0]} to {analyse_source_code(commit_data["source_new"], 'pylint')[-3].split("at ")[-1].split(" ")[0]}")
    graphs_old = generate_ast_graph(commit_data["source_old"])
    graphs_new = generate_ast_graph(commit_data["source_new"])
    for graph_old in graphs_old:
        name_old = get_filename_for_graph("Exports", commit_data["filename_new"], commit_hash, graph_old, "old")
        visualize_call_graph(graph_old, name_old)
    for graph_new in graphs_new:
        name_new = get_filename_for_graph("Exports", commit_data["filename_old"], commit_hash, graph_new, "new")
        visualize_call_graph(graph_new, name_new)

def check_ast(node, graph, parent=None):
    if isinstance(node, ast.Module):
        for child in ast.iter_child_nodes(node):
            return check_ast(child, graph)
    if isinstance(node, ast.FunctionDef):
        graph.node(f"Start▷- {node.name}", fixedsize = "True", label = "▷", shape = "circle", fontsize = "8", height = "0.5")
        parent = f"Start▷- {node.name}"

        parallel = check_sub_tree_parallelism(node)
        children = []
        for i in range(len(parallel.values())):
            if i == 0:
                if len(parallel.values()) > 1:
                    if list(parallel.values())[i+1] == True:
                        # open + and add as child of that
                        graph.node(f"Start+- {str(node)}", fixedsize = "True", label = "+", shape = "diamond", width = "0.5", height = "0.5")
                        graph.edge(str(parent), f"Start+- {str(node)}")
                        parent = f"Start+- {str(node)}"
                        children.append(check_ast(node.body[i], graph, parent))
                    if list(parallel.values())[i+1] == False:
                        # add as child of start and set parent to new node
                        sub_tree_parent = parent
                        parent = check_ast(node.body[i], graph, sub_tree_parent)
            else:
                if list(parallel.values())[i] == True:
                    if list(parallel.values())[i-1] == True:
                        # add as child of previous + or create new one
                        if "Start+-" in str(parent):
                            children.append(check_ast(node.body[i], graph, parent))
                        else:
                            graph.node(f"Start+- {str(node)}", fixedsize = "True", label = "+", shape = "diamond", width = "0.5", height = "0.5")
                            graph.edge(str(parent), f"Start+- {str(node)}")
                            parent = f"Start+- {str(node)}"
                            children.append(check_ast(node.body[i], graph, parent))
                    if list(parallel.values())[i-1] == False:
                        # close + and add as child of that
                        graph.node(f"End+- {str(node)}", fixedsize = "True", label = "+", shape = "diamond", width = "0.5", height = "0.5")
                        children.append(check_ast(node.body[i], graph, parent))
                        for child in children:
                            graph.edge(str(child), f"End+- {str(node)}")
                        children = []
                        parent = f"End+- {str(node)}"
                if list(parallel.values())[i] == False:
                    if list(parallel.values())[i-1] == False:
                        # add as child of previous
                        sub_tree_parent = parent
                        parent = check_ast(node.body[i], graph, sub_tree_parent)
                    if list(parallel.values())[i-1] == True:
                        if children != []:
                            # close + and add as child of that
                            graph.node(f"End+- {str(node)}", fixedsize = "True", label = "+", shape = "diamond", width = "0.5", height = "0.5")
                            for child in children:
                                graph.edge(str(child), f"End+- {str(node)}")
                            children = []
                            parent = f"End+- {str(node)}"
                            sub_tree_parent = parent
                            parent = check_ast(node.body[i], graph, sub_tree_parent)
                        else:
                            if list(parallel.values())[i+1] == True:
                                # open + and add as child of that
                                graph.node(f"Start+- {str(node)}", fixedsize = "True", label = "+", shape = "diamond", width = "0.5", height = "0.5")
                                graph.edge(str(parent), f"Start+- {str(node)}")
                                parent = f"Start+- {str(node)}"
                                children.append(check_ast(node.body[i], graph, parent))
                            if list(parallel.values())[i+1] == False:
                                # add as child of start and set parent to new node
                                sub_tree_parent = parent
                                parent = check_ast(node.body[i], graph, sub_tree_parent)

        graph.node("End⃞", fixedsize = "True", label = "⃞", shape = "circle", fontsize = "8", height = "0.5")
        for child in children:
            graph.edge(str(child), str("End⃞"))
        else: 
            graph.edge(str(parent), str("End⃞"))
        return graph
    if isinstance(node, ast.If):
        sub_tree_children = [] # Calls in the test node
        if node.test:
            calls = get_calls(node.test)
            for call in calls:
                sub_tree_children.append(check_ast(call, graph, parent))
        if node.orelse != []:
            # Exclusive
            graph.node(f"Start×- {str(node)}", fixedsize = "True", label = "×", shape = "diamond", width = "0.5", height = "0.5")
            if sub_tree_children != []:
                for child in sub_tree_children:
                    graph.edge(str(child), f"Start×- {str(node)}")
            else:
                graph.edge(str(parent), f"Start×- {str(node)}")
            parent = f"Start×- {str(node)}"
            children = []
            for child in node.body:
                children.append(check_ast(child, graph, parent))
            for child in node.orelse:
                children.append(check_ast(child, graph, parent))
            graph.node(f"End×- {str(node)}", fixedsize = "True", label = "×", shape = "diamond", width = "0.5", height = "0.5")
            if len(children) > 1:
                color = "red"
            else:
                color = "black"
            for child in children:
                if isinstance(child, ast.Call) or True or "End×-" in str(child):
                    graph.edge(str(child), f"End×- {str(node)}", color = color)
                parent = f"End×- {str(node)}"
            return parent
        else:
            # Inclusive
            graph.node(f"Start○- {str(node)}", fixedsize = "True", label = "○", shape = "diamond", width = "0.5", height = "0.5")
            if sub_tree_children != []:
                for child in sub_tree_children:
                    graph.edge(str(child), f"Start○- {str(node)}")
            else:
                graph.edge(str(parent), f"Start○- {str(node)}")
            parent = f"Start○- {str(node)}"
            children = []
            for child in node.body:
                children.append(check_ast(child, graph, parent))
            for child in node.orelse:
                children.append(check_ast(child, graph, parent))
            graph.node(f"End○- {str(node)}", fixedsize = "True", label = "○", shape = "diamond", width = "0.5", height = "0.5")
            if len(children) > 1:
                color = "red"
            else:
                color = "black"
            for child in children:
                if isinstance(child, ast.Call) or True or "End○-" in str(child):
                    graph.edge(str(child), f"End○- {str(node)}", color = color)
                parent = f"End○- {str(node)}"
            return parent
    if isinstance(node, ast.For):
        graph.node(f"Starf- {str(node)}", fixedsize = "True", label = "⟲", shape = "diamond", width = "0.5", height = "0.5")
        graph.edge(str(parent), f"Starf- {str(node)}")
        parent = f"Starf- {str(node)}"
        children = []
        for child in node.body:
            children.append(check_ast(child, graph, parent))
        for child in node.orelse:
            children.append(check_ast(child, graph, parent))
        graph.node(f"Endf-{str(node)}", fixedsize = "True", label = "⟲", shape = "diamond", width = "0.5", height = "0.5")
        for child in children:
            graph.edge(str(child), f"Endf-{str(node)}")
        parent = f"Endf-{str(node)}"
        return parent
    if isinstance(node, ast.Call):
        # Parallel
        graph.node(str(node), label = get_func_name(node.func))
        graph.edge(str(parent), str(node))
        parent = node
        for child in ast.iter_child_nodes(node):
            return check_ast(child, graph, parent)
    if isinstance(node, ast.Assign):
        calls = get_calls(node.value)
        for call in calls:
            return check_ast(call, graph, parent)
        else:
            if parent:
                return parent
    else:
        for child in ast.iter_child_nodes(node):
            return check_ast(child, graph, parent)
        else:
            if parent:
                return parent

def check_ast2(node, graph, parent=None):
    if isinstance(node, ast.Module):
        for child in ast.iter_child_nodes(node):
            return check_ast(child, graph)
    if isinstance(node, ast.FunctionDef):
        graph.node(f"Start▷- {node.name}", label = "▷", shape = "circle", fontsize = "8", height = "0.5")
        parent = f"Start▷- {node.name}"
        children = []
        for child in node.body:
            children.append(check_ast(child, graph, parent))
        graph.node("End⃞", label = "⃞", shape = "circle", fontsize = "8", height = "0.5")
        for child in children:
            graph.edge(str(child), str("End⃞"))
        return graph
    if isinstance(node, ast.If):
        sub_tree_children = [] # Calls in the test node
        if node.test:
            calls = get_calls(node.test)
            for call in calls:
                sub_tree_children.append(check_ast(call, graph, parent))
        if node.orelse != []:
            # Exclusive
            graph.node(f"Start+- {str(node)}", label = "+", shape = "diamond", width = "0.1", height = "0.1")
            if sub_tree_children != []:
                for child in sub_tree_children:
                    graph.edge(str(child), f"Start+- {str(node)}")
            else:
                graph.edge(str(parent), f"Start+- {str(node)}")
            parent = f"Start+- {str(node)}"
            children = []
            for child in node.body:
                children.append(check_ast(child, graph, parent))
            for child in node.orelse:
                children.append(check_ast(child, graph, parent))
            graph.node(f"End+- {str(node)}", label = "+", shape = "diamond", width = "0.1", height = "0.1")
            if len(children) > 1:
                color = "red"
            else:
                color = "black"
            for child in children:
                if isinstance(child, ast.Call) or True or "End+-" in str(child):
                    graph.edge(str(child), f"End+- {str(node)}", color = color)
                parent = f"End+- {str(node)}"
            return parent
        else:
            # Inclusive
            graph.node(f"Start○- {str(node)}", label = "○", shape = "diamond", width = "0.1", height = "0.1")
            if sub_tree_children != []:
                for child in sub_tree_children:
                    graph.edge(str(child), f"Start○- {str(node)}")
            else:
                graph.edge(str(parent), f"Start○- {str(node)}")
            parent = f"Start○- {str(node)}"
            children = []
            for child in node.body:
                children.append(check_ast(child, graph, parent))
            for child in node.orelse:
                children.append(check_ast(child, graph, parent))
            graph.node(f"End○- {str(node)}", label = "○", shape = "diamond", width = "0.1", height = "0.1")
            if len(children) > 1:
                color = "red"
            else:
                color = "black"
            for child in children:
                if isinstance(child, ast.Call) or True or "End○-" in str(child):
                    graph.edge(str(child), f"End○- {str(node)}", color = color)
                parent = f"End○- {str(node)}"
            return parent
    if isinstance(node, ast.For):
        graph.node(f"Starf- {str(node)}", label = "⟲", shape = "diamond", width = "0.1", height = "0.1")
        graph.edge(str(parent), f"Starf- {str(node)}")
        parent = f"Starf- {str(node)}"
        children = []
        for child in node.body:
            children.append(check_ast(child, graph, parent))
        for child in node.orelse:
            children.append(check_ast(child, graph, parent))
        graph.node(f"Endf-{str(node)}", label = "⟲", shape = "diamond", width = "0.1", height = "0.1")
        for child in children:
            graph.edge(str(child), f"Endf-{str(node)}")
        parent = f"Endf-{str(node)}"
        return parent
    if isinstance(node, ast.Call):
        # Parallel
        graph.node(str(node), label = get_func_name(node.func))
        graph.edge(str(parent), str(node))
        parent = node
        for child in ast.iter_child_nodes(node):
            return check_ast(child, graph, parent)
    if isinstance(node, ast.Assign):
        calls = get_calls(node.value)
        for call in calls:
            return check_ast(call, graph, parent)
        else:
            if parent:
                return parent
    else:
        for child in ast.iter_child_nodes(node):
            return check_ast(child, graph, parent)
        else:
            if parent:
                return parent

def get_calls(node):
    calls = []
    if isinstance(node, ast.Call):
        calls.append(node)
    for child in ast.iter_child_nodes(node):
        calls += get_calls(child)
    return calls

def nodes(graph: Digraph):
    return [line for line in graph.body if not "->" in line]

def edges(graph: Digraph):
    res = []
    for line in graph.body:
        if "->" in line:
            res.append([line.split("->")[0].strip(), line.split("->")[1].strip()])
    return res

def get_func_name(node):
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{get_func_name(node.value)}.{node.attr}"
    elif isinstance(node, ast.FunctionDef):
        return node.name
    else:
        return ""
    
def check_sub_tree_parallelism(node):
    """ Returns a dictionary of type {node: {store: [], load: []}}
        i.e. variables stored and loaded for each direct child node of the passed AST """
    variables = {}
    for child in ast.iter_child_nodes(node):
        variables[child] = get_variables(child)
    parallel = {}
    current_dependent_variables = []
    for sub_tree in list(variables.keys())[1:]:
        if "store" in variables[sub_tree].keys():
            for variable in variables[sub_tree]["store"]:
                current_dependent_variables.append(variable)
        parallel[sub_tree] = True
        if "load" in variables[sub_tree].keys():
            for variable in variables[sub_tree]["load"]:
                if variable in current_dependent_variables:
                    parallel[sub_tree] = False
                    current_dependent_variables = []
                    if "store" in variables[sub_tree].keys():
                        for variable in variables[sub_tree]["store"]:
                            current_dependent_variables.append(variable)
                    break        
    return parallel

def get_variables(node):
    variables = dict()
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                variables.setdefault("store", set()).add(target.id)
    if isinstance(node, ast.Compare):
        for expression in node.comparators:
            if isinstance(expression, ast.Name):
                variables.setdefault("load", set()).add(expression.id)
        if not isinstance(node.left, ast.Constant) and isinstance(node.left, ast.Name):
            variables.setdefault("load", set()).add(node.left.id)
    if isinstance(node, ast.Call):
        for arg in node.args:
            if isinstance(arg, ast.Name):
                variables.setdefault("load", set()).add(arg.id)
        for keyword in node.keywords:
            variables.setdefault("load", set()).add(keyword.arg)
    if isinstance(node, ast.If):
        if isinstance(node.test, ast.Name):
            variables.setdefault("load", set()).add(node.test.id)
    for child in ast.iter_child_nodes(node):
        res = get_variables(child)
        if "load" in res.keys():
            for variable in res["load"]:
                variables.setdefault("load", set()).add(variable)
        if "store" in res.keys():
            for variable in res["store"]:
                variables.setdefault("store", set()).add(variable)
    return variables