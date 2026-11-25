"""Explicit structural metrics; branch count is not cyclomatic complexity."""

import ast
import io
import tokenize


BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler, ast.match_case)


def analyze_source(path: str, content: bytes) -> dict:
    base = {"path": path, "physical_lines": None, "functions": None, "classes": None,
            "branch_nodes": None, "function_lines": None, "max_function_lines": None,
            "parse_error": ""}
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(content).readline)
        source = content.decode(encoding)
        base["physical_lines"] = len(source.splitlines())
        tree = ast.parse(source, filename=path)
        nodes = list(ast.walk(tree))
        functions = [node for node in nodes if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        lengths = [node.end_lineno - node.lineno + 1 for node in functions]
        base.update(functions=len(functions), classes=sum(isinstance(node, ast.ClassDef) for node in nodes),
                    branch_nodes=sum(isinstance(node, BRANCH_NODES) for node in nodes),
                    function_lines=sum(lengths), max_function_lines=max(lengths, default=0))
    except (SyntaxError, UnicodeError, LookupError, ValueError, RecursionError) as error:
        base["parse_error"] = f"{type(error).__name__}: {error}"
    return base
