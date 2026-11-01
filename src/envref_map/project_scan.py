"""Offline project traversal and language scanner dispatch."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from envref_map.analysis import analyze_scan
from envref_map.model import DynamicAccess, EnvReport, ScanDiagnostic, SourceReference, TemplateDefinition
from envref_map.scanner_javascript import scan_javascript
from envref_map.scanner_python import scan_python
from envref_map.scanner_shell import scan_shell
from envref_map.templates import (
    IGNORED_DIRS,
    BinaryTemplateError,
    discover_template_paths,
    is_unsafe_env_name,
    parse_template,
)


_SOURCE_EXTENSIONS = frozenset({
    ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".sh", ".bash",
})
_JAVASCRIPT_EXTENSIONS = frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"})
_SHELL_EXTENSIONS = frozenset({".sh", ".bash"})


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return "<root>"


def scan_project(root: Path, custom_templates: Sequence[Path] = ()) -> EnvReport:
    root_resolved = Path(root).resolve()
    if not root_resolved.is_dir():
        raise ValueError("project root must be a directory")

    selected_templates = discover_template_paths(root_resolved, custom_templates)
    template_paths = tuple(sorted(_relative(path, root_resolved) for path in selected_templates))
    template_definitions: list[TemplateDefinition] = []
    references: list[SourceReference] = []
    dynamic_accesses: list[DynamicAccess] = []
    diagnostics: list[ScanDiagnostic] = []

    for path in selected_templates:
        relative = _relative(path, root_resolved)
        try:
            template_definitions.extend(parse_template(path, root_resolved))
        except BinaryTemplateError:
            diagnostics.append(ScanDiagnostic(relative, 1, "template_binary_file"))
        except UnicodeError:
            diagnostics.append(ScanDiagnostic(relative, 1, "template_encoding_error"))
        except OSError:
            diagnostics.append(ScanDiagnostic(relative, 1, "template_read_error"))

    source_paths: list[Path] = []

    def on_walk_error(error: OSError) -> None:
        path = Path(os.fsdecode(error.filename)) if error.filename else root_resolved
        diagnostics.append(ScanDiagnostic(_relative(path, root_resolved), 1, "directory_read_error"))

    for current, directories, files in os.walk(root_resolved, topdown=True, followlinks=False, onerror=on_walk_error):
        current_path = Path(current)
        directories[:] = sorted(
            name for name in directories
            if name not in IGNORED_DIRS and not (current_path / name).is_symlink()
        )
        for name in files:
            path = current_path / name
            if (
                path.is_symlink()
                or is_unsafe_env_name(name)
                or path.suffix.lower() not in _SOURCE_EXTENSIONS
            ):
                continue
            source_paths.append(path)

    source_paths.sort(key=lambda path: _relative(path, root_resolved))
    scanned_files = len(source_paths)

    for path in source_paths:
        relative = _relative(path, root_resolved)
        try:
            source = path.read_text(encoding="utf-8-sig")
        except UnicodeError:
            diagnostics.append(ScanDiagnostic(relative, 1, "source_encoding_error"))
            continue
        except OSError:
            diagnostics.append(ScanDiagnostic(relative, 1, "source_read_error"))
            continue

        if "\x00" in source:
            diagnostics.append(ScanDiagnostic(relative, 1, "source_binary_file"))
            continue

        suffix = path.suffix.lower()
        if suffix == ".py":
            chunk = scan_python(source, relative)
        elif suffix in _JAVASCRIPT_EXTENSIONS:
            chunk = scan_javascript(source, relative)
        else:
            chunk = scan_shell(source, relative)
        references.extend(chunk.references)
        dynamic_accesses.extend(chunk.dynamic_accesses)
        diagnostics.extend(chunk.diagnostics)

    report = analyze_scan(scanned_files, references, template_definitions, dynamic_accesses, diagnostics)
    # Keep empty and unreadable template files visible without synthetic key records.
    return replace(report, template_paths=template_paths)
