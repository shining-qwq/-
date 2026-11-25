from repo_evolution.ast_metrics import analyze_source


def test_nested_async_and_branch_definitions():
    source = b'''class Example:
    async def outer(self, flag):
        def inner():
            return 1
        if flag:
            return inner()
        return 0
'''
    result = analyze_source("example.py", source)
    assert result["parse_error"] == ""
    assert result["physical_lines"] == 7
    assert result["functions"] == 2
    assert result["classes"] == 1
    assert result["branch_nodes"] == 1
    assert result["function_lines"] == 8
    assert result["max_function_lines"] == 6


def test_declared_encoding_and_parse_failures():
    result = analyze_source("latin.py", b"# coding: latin-1\nname = 'caf\xe9'\n")
    assert result["parse_error"] == ""
    assert result["physical_lines"] == 2
    bad = analyze_source("bad.py", b"def broken(:\n")
    assert bad["parse_error"].startswith("SyntaxError:")
    assert bad["functions"] is None
    assert bad["physical_lines"] == 1
    assert analyze_source("encoding.py", b"# coding: unknown-codec\nx = 1\n")["parse_error"]


def test_match_and_boolean_short_circuit_policy():
    source = b"match x:\n    case 1:\n        pass\n    case _:\n        pass\nresult = a and b\n"
    assert analyze_source("match.py", source)["branch_nodes"] == 2
