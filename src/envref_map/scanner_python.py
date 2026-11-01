"""Conservative Python AST scanner for common os environment lookups."""

from __future__ import annotations

import ast

from envref_map.model import DynamicAccess, ScanChunk, ScanDiagnostic, SourceReference


def _is_os_environ(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


class _EnvironmentVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.references: list[SourceReference] = []
        self.dynamic_accesses: list[DynamicAccess] = []

    def _record(self, key_node: ast.AST | None, line: int) -> None:
        key = _literal_string(key_node) if key_node is not None else None
        if key is None:
            self.dynamic_accesses.append(DynamicAccess(self.path, line, "python"))
        else:
            self.references.append(SourceReference(key, self.path, line))

    def visit_Call(self, node: ast.Call) -> None:
        function = node.func
        is_getenv = (
            isinstance(function, ast.Attribute)
            and function.attr == "getenv"
            and isinstance(function.value, ast.Name)
            and function.value.id == "os"
        )
        is_environ_get = (
            isinstance(function, ast.Attribute)
            and function.attr == "get"
            and _is_os_environ(function.value)
        )
        if is_getenv or is_environ_get:
            key_node = node.args[0] if node.args else None
            if key_node is None:
                key_node = next((item.value for item in node.keywords if item.arg == "key"), None)
            self._record(key_node, node.lineno)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if _is_os_environ(node.value):
            self._record(node.slice, node.lineno)
        self.generic_visit(node)


def scan_python(source: str, path: str) -> ScanChunk:
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as error:
        return ScanChunk(diagnostics=(ScanDiagnostic(path, error.lineno or 1, "python_syntax_error"),))

    visitor = _EnvironmentVisitor(path)
    visitor.visit(tree)
    return ScanChunk(
        references=tuple(visitor.references),
        dynamic_accesses=tuple(visitor.dynamic_accesses),
    )
