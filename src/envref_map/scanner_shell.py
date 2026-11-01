"""Line-aware scanner for common shell variable expansions."""

from __future__ import annotations

import re

from envref_map.model import DynamicAccess, ScanChunk, SourceReference


_VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_BRACE_MODIFIERS = (":-", ":?", ":+", ":=")


def _command_substitution_end(source: str, start: int) -> int | None:
    index = start + 2
    depth = 1
    quote: str | None = None
    while index < len(source):
        char = source[index]
        if quote == "'":
            if char == "'":
                quote = None
            index += 1
            continue
        if quote == '"':
            if char == "\\" and index + 1 < len(source):
                index += 2
                continue
            if char == '"':
                quote = None
                index += 1
                continue
            if source.startswith("$(", index):
                depth += 1
                index += 2
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return index
            index += 1
            continue
        if char == "\\" and index + 1 < len(source):
            index += 2
            continue
        if char == "'":
            quote = "'"
        elif char == '"':
            quote = '"'
        elif source.startswith("$(", index):
            depth += 1
            index += 2
            continue
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        elif char == "#" and (index == 0 or source[index - 1].isspace()):
            newline = source.find("\n", index + 1)
            if newline < 0:
                return None
            index = newline
        index += 1
    return None


def _quoted_heredoc_end(source: str, start: int) -> int | None:
    if not source.startswith("<<", start) or source.startswith("<<<", start):
        return None
    index = start + 2
    strip_tabs = index < len(source) and source[index] == "-"
    if strip_tabs:
        index += 1
    while index < len(source) and source[index] in " \t":
        index += 1
    if index >= len(source) or source[index] not in "'\"":
        return None
    quote = source[index]
    index += 1
    delimiter_start = index
    while index < len(source):
        if source[index] == "\\" and quote == '"' and index + 1 < len(source):
            index += 2
            continue
        if source[index] == quote:
            break
        index += 1
    if index >= len(source):
        return None
    delimiter = source[delimiter_start:index]
    command_newline = source.find("\n", index + 1)
    if command_newline < 0:
        return len(source)
    body_start = command_newline + 1
    line_start = body_start
    while line_start <= len(source):
        line_end = source.find("\n", line_start)
        if line_end < 0:
            line_end = len(source)
            next_line = len(source)
        else:
            next_line = line_end + 1
        line_text = source[line_start:line_end].removesuffix("\r")
        compared = line_text.lstrip("\t") if strip_tabs else line_text
        if compared == delimiter:
            return next_line
        if line_end == len(source):
            break
        line_start = next_line
    return len(source)


def scan_shell(source: str, path: str) -> ScanChunk:
    return _scan_shell(source, path, line_offset=0)


def _scan_shell(source: str, path: str, *, line_offset: int) -> ScanChunk:
    references: list[SourceReference] = []
    dynamic_accesses: list[DynamicAccess] = []
    index = 0
    line = line_offset + 1
    quote: str | None = None

    while index < len(source):
        char = source[index]

        if quote == "'":
            if char == "'":
                quote = None
            elif char == "\n":
                line += 1
            index += 1
            continue

        if quote != "'" and source.startswith("$(", index):
            end = _command_substitution_end(source, index)
            if end is not None:
                nested = _scan_shell(source[index + 2:end], path, line_offset=line - 1)
                references.extend(nested.references)
                dynamic_accesses.extend(nested.dynamic_accesses)
                consumed = source[index:end + 1]
                line += consumed.count("\n")
                index = end + 1
                continue

        if quote is None and source.startswith("<<", index):
            end = _quoted_heredoc_end(source, index)
            if end is not None:
                line += source[index:end].count("\n")
                index = end
                continue

        if quote == '"':
            if char == "\\" and index + 1 < len(source):
                escaped = source[index + 1]
                if escaped in '$`"\\':
                    index += 2
                    continue
                if escaped == "\n":
                    line += 1
                    index += 2
                    continue
            if char == '"':
                quote = None
                index += 1
                continue
            if char == "\n":
                line += 1
                index += 1
                continue
        else:
            if char == "\\" and index + 1 < len(source):
                if source[index + 1] == "\n":
                    line += 1
                index += 2
                continue
            if char == "'":
                quote = "'"
                index += 1
                continue
            if char == '"':
                quote = '"'
                index += 1
                continue
            if char == "#" and (
                index == 0
                or source[index - 1].isspace()
                or source[index - 1] in ";|&("
            ):
                newline = source.find("\n", index + 1)
                if newline < 0:
                    break
                index = newline
                continue
            if char == "\n":
                line += 1
                index += 1
                continue

        if char != "$" or index + 1 >= len(source):
            index += 1
            continue

        if source[index + 1] == "$":
            # `$$` is one special-parameter expansion; a following name or
            # braced word is literal text, not a second environment lookup.
            index += 2
            continue

        if source[index + 1] == "{":
            expansion_line = line
            key_start = index + 2
            if key_start < len(source) and source[key_start] == "!":
                dynamic_accesses.append(DynamicAccess(path, expansion_line, "shell"))
                index += 2
                continue

            match = _VARIABLE_NAME.match(source, key_start)
            if match is None:
                dynamic_accesses.append(DynamicAccess(path, expansion_line, "shell"))
                index += 2
                continue

            key = match.group(0)
            end = match.end()
            if source.startswith("}", end) or any(source.startswith(modifier, end) for modifier in _BRACE_MODIFIERS):
                references.append(SourceReference(key, path, expansion_line))
            else:
                dynamic_accesses.append(DynamicAccess(path, expansion_line, "shell"))
            index = end
            continue

        match = _VARIABLE_NAME.match(source, index + 1)
        if match is not None:
            references.append(SourceReference(match.group(0), path, line))
            index = match.end()
            continue

        index += 1

    return ScanChunk(tuple(references), tuple(dynamic_accesses))
