"""Safe discovery and key-only parsing for environment example templates."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Sequence

from envref_map.model import TemplateDefinition


SAFE_TEMPLATE_NAMES = frozenset({".env.example", ".env.sample", ".env.template"})
IGNORED_DIRS = frozenset({
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules",
    "__pycache__", "build", "dist", "coverage", ".next", ".nuxt", "vendor", "target",
})
_ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


class BinaryTemplateError(ValueError):
    """Raised when a template contains a recognizable binary marker."""


def is_unsafe_env_name(name: str) -> bool:
    return name == ".env" or (name.startswith(".env.") and name not in SAFE_TEMPLATE_NAMES)


def _quoted_value_closes(line: str, quote: str) -> bool:
    escaped = False
    for char in line:
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == quote:
            return True
    return False


def _multiline_quote_after_assignment(line: str, assignment_end: int) -> str | None:
    value = line[assignment_end:].lstrip()
    if not value or value[0] not in {'"', "'"}:
        return None
    quote = value[0]
    return quote if not _quoted_value_closes(value[1:], quote) else None


def _root_path(root: Path) -> Path:
    resolved = Path(root).resolve()
    if not resolved.is_dir():
        raise ValueError("project root must be a directory")
    return resolved


def _validated_template(path: Path, root: Path, *, custom: bool) -> Path:
    root_resolved = _root_path(root)
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root_resolved / candidate
    if is_unsafe_env_name(candidate.name):
        raise ValueError("real .env files are not safe templates")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as error:
        raise ValueError("template path is outside the project root") from error

    name = resolved.name
    if name in SAFE_TEMPLATE_NAMES:
        pass
    elif is_unsafe_env_name(name):
        raise ValueError("real .env files are not safe templates")
    elif custom and name.endswith((".example", ".sample", ".template")):
        pass
    else:
        raise ValueError("template name must be a recognized example or end in .example, .sample, or .template")

    if not resolved.is_file():
        raise ValueError("template path does not name a file")
    return resolved


def discover_template_paths(root: Path, custom_paths: Sequence[Path] = ()) -> tuple[Path, ...]:
    root_resolved = _root_path(root)
    found: set[Path] = set()

    for current, directories, files in os.walk(root_resolved, topdown=True, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            name for name in directories
            if name not in IGNORED_DIRS and not (current_path / name).is_symlink()
        )
        for name in files:
            if name not in SAFE_TEMPLATE_NAMES:
                continue
            candidate = current_path / name
            if candidate.is_symlink() or not candidate.is_file():
                continue
            found.add(candidate.resolve())

    for custom_path in custom_paths:
        found.add(_validated_template(Path(custom_path), root_resolved, custom=True))

    return tuple(sorted(found, key=lambda item: item.as_posix()))


def parse_template(path: Path, root: Path) -> tuple[TemplateDefinition, ...]:
    root_resolved = _root_path(root)
    resolved = _validated_template(Path(path), root_resolved, custom=True)
    relative = resolved.relative_to(root_resolved).as_posix()
    definitions: list[TemplateDefinition] = []

    # Read only so keys can be extracted; assignment values are never stored.
    quote: str | None = None
    with resolved.open("r", encoding="utf-8-sig", newline=None) as stream:
        for line_number, line in enumerate(stream, start=1):
            if "\x00" in line:
                raise BinaryTemplateError
            if quote is not None:
                if _quoted_value_closes(line, quote):
                    quote = None
                continue
            match = _ASSIGNMENT.match(line)
            if match:
                definitions.append(TemplateDefinition(match.group(1), relative, line_number))
                quote = _multiline_quote_after_assignment(line, match.end())

    return tuple(definitions)
