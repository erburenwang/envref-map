"""Token-aware scanner for common JavaScript and TypeScript env access."""

from __future__ import annotations

import re
from dataclasses import dataclass

from envref_map.model import DynamicAccess, ScanChunk, SourceReference


_ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_IDENTIFIER_START = re.compile(r"[A-Za-z_$]")
_IDENTIFIER_PART = re.compile(r"[A-Za-z0-9_$]")
_REGEX_PREFIX_KEYWORDS = frozenset({
    "await", "case", "delete", "do", "else", "in", "instanceof", "new",
    "of", "return", "throw", "typeof", "void", "yield",
})
_CONTROL_PAREN_KEYWORDS = frozenset({"catch", "for", "if", "switch", "while", "with"})


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    value: str
    line: int


class _Tokenizer:
    def __init__(self, source: str) -> None:
        self.source = source
        self.length = len(source)
        self.tokens: list[_Token] = []

    def _quoted(self, start: int, line: int, quote: str) -> tuple[int, int]:
        source = self.source
        index = start + 1
        current_line = line
        value: list[str] = []
        valid = True
        while index < self.length:
            char = source[index]
            if char == quote:
                self.tokens.append(_Token("string" if valid else "invalid", "".join(value), line))
                return index + 1, current_line
            if char in "\r\n":
                # Unescaped line breaks make single- and double-quoted strings invalid.
                self.tokens.append(_Token("invalid", "".join(value), line))
                return index, current_line
            if char == "\\":
                index += 1
                if index >= self.length:
                    break
                escaped = source[index]
                if escaped == "\n":
                    current_line += 1
                    index += 1
                    continue
                if escaped == "\r":
                    current_line += 1
                    index += 1
                    if index < self.length and source[index] == "\n":
                        index += 1
                    continue
                simple = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
                if escaped in simple:
                    value.append(simple[escaped])
                    index += 1
                    continue
                if escaped in "\\'\"`$":
                    value.append(escaped)
                    index += 1
                    continue
                if escaped == "x" and index + 2 < self.length:
                    digits = source[index + 1:index + 3]
                    if all(char in "0123456789abcdefABCDEF" for char in digits):
                        value.append(chr(int(digits, 16)))
                        index += 3
                        continue
                if escaped == "u" and index + 4 < self.length:
                    digits = source[index + 1:index + 5]
                    if all(char in "0123456789abcdefABCDEF" for char in digits):
                        value.append(chr(int(digits, 16)))
                        index += 5
                        continue
                # Do not guess the meaning of a string with an unsupported escape.
                valid = False
                value.append(escaped)
                index += 1
                continue
            value.append(char)
            index += 1
        self.tokens.append(_Token("invalid", "".join(value), line))
        return self.length, current_line

    def _regex_can_start(self) -> bool:
        if not self.tokens:
            return True
        previous = self.tokens[-1]
        if previous.kind == "identifier" and previous.value in _REGEX_PREFIX_KEYWORDS:
            return True
        if previous.kind == "punct" and previous.value == ")" and self._closes_control_condition():
            return True
        return previous.kind == "punct" and previous.value in {
            "(", "[", "{", ",", ";", ":", "=", "!", "?", "=>", "&&", "||", "??",
        }

    def _closes_control_condition(self) -> bool:
        depth = 0
        for index in range(len(self.tokens) - 1, -1, -1):
            token = self.tokens[index]
            if token.value == ")":
                depth += 1
            elif token.value == "(":
                depth -= 1
                if depth == 0:
                    return (
                        index > 0
                        and self.tokens[index - 1].kind == "identifier"
                        and self.tokens[index - 1].value in _CONTROL_PAREN_KEYWORDS
                    )
        return False

    def _regex(self, start: int, line: int) -> tuple[int, int]:
        source = self.source
        index = start + 1
        current_line = line
        in_character_class = False
        while index < self.length:
            char = source[index]
            if char in "\r\n":
                return start + 1, line
            if char == "\\":
                index += 2
                continue
            if char == "[":
                in_character_class = True
            elif char == "]":
                in_character_class = False
            elif char == "/" and not in_character_class:
                index += 1
                while index < self.length and source[index].isalpha():
                    index += 1
                return index, current_line
            index += 1
        return start + 1, line

    def _template(self, start: int, line: int) -> tuple[int, int]:
        source = self.source
        index = start + 1
        current_line = line
        while index < self.length:
            char = source[index]
            if char == "\\":
                index += 1
                if index < self.length and source[index] == "\n":
                    current_line += 1
                elif index < self.length and source[index] == "\r":
                    current_line += 1
                    if index + 1 < self.length and source[index + 1] == "\n":
                        index += 1
                index += 1
                continue
            if char == "`":
                return index + 1, current_line
            if char == "$" and index + 1 < self.length and source[index + 1] == "{":
                self.tokens.append(_Token("boundary", "${", current_line))
                index, current_line = self._code(index + 2, current_line, stop_at_brace=True)
                self.tokens.append(_Token("boundary", "}", current_line))
                continue
            if char == "\n":
                current_line += 1
            index += 1
        return self.length, current_line

    def _code(self, start: int, line: int, *, stop_at_brace: bool = False) -> tuple[int, int]:
        source = self.source
        index = start
        current_line = line
        brace_depth = 0
        while index < self.length:
            char = source[index]
            if char.isspace():
                if char == "\n":
                    current_line += 1
                index += 1
                continue
            if source.startswith("//", index):
                newline = source.find("\n", index + 2)
                if newline < 0:
                    return self.length, current_line
                index = newline
                continue
            if source.startswith("/*", index):
                end = source.find("*/", index + 2)
                if end < 0:
                    current_line += source[index:].count("\n")
                    return self.length, current_line
                current_line += source[index:end + 2].count("\n")
                index = end + 2
                continue
            if stop_at_brace and char == "}":
                if brace_depth == 0:
                    return index + 1, current_line
                brace_depth -= 1
                self.tokens.append(_Token("punct", char, current_line))
                index += 1
                continue
            if char == "{":
                if stop_at_brace:
                    brace_depth += 1
                self.tokens.append(_Token("punct", char, current_line))
                index += 1
                continue
            if char in "'\"":
                index, current_line = self._quoted(index, current_line, char)
                continue
            if char == "`":
                index, current_line = self._template(index, current_line)
                continue
            if char == "<" and self._jsx_can_start(index):
                index, current_line = self._jsx(index, current_line)
                continue
            if char == "/" and index + 1 < self.length and self._regex_can_start():
                next_index, next_line = self._regex(index, current_line)
                if next_index > index + 1:
                    index, current_line = next_index, next_line
                    continue
            if _IDENTIFIER_START.fullmatch(char):
                begin = index
                index += 1
                while index < self.length and _IDENTIFIER_PART.fullmatch(source[index]):
                    index += 1
                self.tokens.append(_Token("identifier", source[begin:index], current_line))
                continue
            operator = next((item for item in ("=>", "&&", "||", "??", "?.") if source.startswith(item, index)), None)
            if operator is not None:
                self.tokens.append(_Token("punct", operator, current_line))
                index += len(operator)
                continue
            self.tokens.append(_Token("punct", char, current_line))
            index += 1
        return index, current_line

    def _jsx_tag_info(self, start: int) -> tuple[str, bool] | None:
        if start >= self.length or self.source[start] != "<":
            return None
        index = start + 1
        closing = index < self.length and self.source[index] == "/"
        if closing:
            index += 1
        if index < self.length and self.source[index] == ">":
            return "", closing
        if index >= self.length or not _IDENTIFIER_START.fullmatch(self.source[index]):
            return None
        begin = index
        index += 1
        while index < self.length and (
            _IDENTIFIER_PART.fullmatch(self.source[index]) or self.source[index] in ".:-"
        ):
            index += 1
        return self.source[begin:index], closing

    def _jsx_tag_end(self, start: int) -> int | None:
        index = start + 1
        quote: str | None = None
        brace_depth = 0
        while index < self.length:
            char = self.source[index]
            if quote is not None:
                if char == "\\":
                    index += 2
                    continue
                if char == quote:
                    quote = None
            elif char in "'\"":
                quote = char
            elif char == "{":
                brace_depth += 1
            elif char == "}" and brace_depth:
                brace_depth -= 1
            elif char == ">" and brace_depth == 0:
                return index + 1
            index += 1
        return None

    def _jsx_can_start(self, start: int) -> bool:
        info = self._jsx_tag_info(start)
        if info is None or info[1]:
            return False
        if self.tokens:
            previous = self.tokens[-1]
            expression_prefix = previous.kind == "punct" and previous.value in {
                "=", "(", "[", ",", ":", "?", "=>", "&&", "||", "??",
            }
            keyword_prefix = previous.kind == "identifier" and previous.value in {
                "await", "default", "return", "yield",
            }
            if not expression_prefix and not keyword_prefix:
                return False
        end = self._jsx_tag_end(start)
        if end is None:
            return False
        if self.source[start:end - 1].rstrip().endswith("/"):
            return True
        closing_pattern = r"</\s*>" if not info[0] else r"</" + re.escape(info[0]) + r"\s*>"
        closing = re.search(closing_pattern, self.source[end:])
        return closing is not None

    def _consume_jsx_tag(self, start: int, line: int) -> tuple[int, int, str, bool, bool] | None:
        info = self._jsx_tag_info(start)
        if info is None:
            return None
        name, closing = info
        source = self.source
        index = start + 1
        current_line = line
        quote: str | None = None
        self_closing = False
        if closing:
            index += 1
        while index < self.length:
            char = source[index]
            if quote is not None:
                if char == "\\" and index + 1 < self.length:
                    if source[index + 1] == "\n":
                        current_line += 1
                    index += 2
                    continue
                if char == quote:
                    quote = None
                elif char == "\n":
                    current_line += 1
                index += 1
                continue
            if char in "'\"":
                quote = char
                index += 1
                continue
            if not closing and char == "{":
                self.tokens.append(_Token("boundary", "{", current_line))
                index, current_line = self._code(index + 1, current_line, stop_at_brace=True)
                self.tokens.append(_Token("boundary", "}", current_line))
                continue
            if source.startswith("/>", index):
                self_closing = True
                return index + 2, current_line, name, closing, self_closing
            if char == ">":
                return index + 1, current_line, name, closing, self_closing
            if char == "\n":
                current_line += 1
            index += 1
        return self.length, current_line, name, closing, self_closing

    def _jsx(self, start: int, line: int) -> tuple[int, int]:
        index = start
        current_line = line
        depth = 0
        started = False
        source = self.source
        while index < self.length:
            if source[index] == "<":
                tag = self._consume_jsx_tag(index, current_line)
                if tag is not None:
                    index, current_line, _name, closing, self_closing = tag
                    if closing:
                        depth -= 1
                        if depth <= 0:
                            return index, current_line
                    elif not self_closing:
                        depth += 1
                    elif not started and depth == 0:
                        return index, current_line
                    started = True
                    continue
            if source[index] == "{" and depth > 0:
                self.tokens.append(_Token("boundary", "{", current_line))
                index, current_line = self._code(index + 1, current_line, stop_at_brace=True)
                self.tokens.append(_Token("boundary", "}", current_line))
                continue
            if source[index] == "\n":
                current_line += 1
            index += 1
        return index, current_line

    def tokenize(self) -> tuple[_Token, ...]:
        self._code(0, 1)
        return tuple(self.tokens)


def _access_start(tokens: tuple[_Token, ...], index: int) -> int | None:
    if index + 2 < len(tokens) and (
        tokens[index].kind == "identifier"
        and tokens[index].value == "process"
        and tokens[index + 1].value == "."
        and tokens[index + 2].kind == "identifier"
        and tokens[index + 2].value == "env"
    ):
        return index + 2
    if (
        index + 4 < len(tokens)
        and tokens[index].kind == "identifier"
        and tokens[index].value == "import"
        and tokens[index + 1].value == "."
        and tokens[index + 2].kind == "identifier"
        and tokens[index + 2].value == "meta"
        and tokens[index + 3].value == "."
        and tokens[index + 4].kind == "identifier"
        and tokens[index + 4].value == "env"
    ):
        return index + 4
    return None


def scan_javascript(source: str, path: str) -> ScanChunk:
    tokens = _Tokenizer(source).tokenize()
    references: list[SourceReference] = []
    dynamic_accesses: list[DynamicAccess] = []

    for index in range(len(tokens)):
        env_index = _access_start(tokens, index)
        if env_index is None or env_index + 1 >= len(tokens):
            continue
        following = tokens[env_index + 1]
        if following.value == "." and env_index + 2 < len(tokens):
            key_token = tokens[env_index + 2]
            if key_token.kind == "identifier" and _ENV_KEY.fullmatch(key_token.value):
                references.append(SourceReference(key_token.value, path, key_token.line))
        elif following.value == "[":
            key_token = tokens[env_index + 2] if env_index + 2 < len(tokens) else None
            closing = tokens[env_index + 3] if env_index + 3 < len(tokens) else None
            if (
                key_token is not None
                and key_token.kind == "string"
                and closing is not None
                and closing.value == "]"
                and _ENV_KEY.fullmatch(key_token.value)
            ):
                references.append(SourceReference(key_token.value, path, key_token.line))
            else:
                dynamic_accesses.append(DynamicAccess(path, following.line, "javascript"))

    return ScanChunk(tuple(references), tuple(dynamic_accesses))
