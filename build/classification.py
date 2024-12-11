def classify_comments(lines):
        line_types = []
        # Check for commented-out code (basic heuristic: looks like valid Python code)
        if is_potential_code(lines.lstrip("#").strip()) and is_potential_code(lines.lstrip("\"\"\"").strip()):
            line_types.append("commented-out")
        # Check for block comments (multi-line consecutive)
        if lines.find("\n") != -1:
            line_types.append("block")
        # Check if text has docstring format with """" somewhere
        if lines.find("\"\"\"") != -1:
            line_types.append("docstring")
        if len(line_types) == 0:
            line_types.append("normal")
        return line_types

def is_potential_code(text):
    try:
        compile(text, "<string>", "exec")
        return True
    except SyntaxError:
        return False

def classify_content(line):
    comment_types = []
    if (line.find("#") != -1 and line.split("#")[0].strip() != "") or line.find(";") != -1 and line.split(";")[0].strip() != "":
        comment_types.append("inline")
    if is_potential_code(line.strip().lstrip("#").strip()) and is_potential_code(line.strip().lstrip("\"\"\"").strip()):
        comment_types.append("commented-out")
    return comment_types