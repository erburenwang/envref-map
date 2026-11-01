"""Text, Markdown, and versioned JSON renderers."""

from __future__ import annotations

import json
import re

from envref_map.model import EnvReport


def _safe_path(path: str) -> str:
    return path.replace("\r", r"\r").replace("\n", r"\n")


def _code_span(value: str) -> str:
    longest_run = max((len(match.group(0)) for match in re.finditer(r"`+", value)), default=0)
    delimiter = "`" * (longest_run + 1)
    return f"{delimiter}{value}{delimiter}"


def _json_payload(report: EnvReport) -> dict[str, object]:
    return {
        "schema_version": report.schema_version,
        "scanned_files": report.scanned_files,
        "template_paths": list(report.template_paths),
        "keys": [
            {
                "name": item.name,
                "status": item.status,
                "references": [{"path": ref.path, "line": ref.line} for ref in item.references],
                "template_paths": list(item.template_paths),
            }
            for item in report.keys
        ],
        "unused_template_keys": [
            {"name": item.name, "template_paths": list(item.template_paths)}
            for item in report.unused_template_keys
        ],
        "dynamic_accesses": [
            {"path": item.path, "line": item.line, "language": item.language}
            for item in report.dynamic_accesses
        ],
        "diagnostics": [
            {"path": item.path, "line": item.line, "code": item.code}
            for item in report.diagnostics
        ],
    }


def _items(lines: list[str], values: list[str], *, markdown: bool) -> None:
    if values:
        lines.extend(values)
    else:
        lines.append("- None" if markdown else "  (none)")


def _render_text(report: EnvReport) -> str:
    lines = ["EnvRef Map", f"Scanned files: {report.scanned_files}", "Templates:"]
    _items(lines, [f"  {_safe_path(path)}" for path in report.template_paths], markdown=False)

    for status, title in (("documented", "Documented keys"), ("missing", "Missing keys")):
        lines.append(f"{title}:")
        items = []
        for result in report.keys:
            if result.status != status:
                continue
            locations = ", ".join(f"{_safe_path(ref.path)}:{ref.line}" for ref in result.references)
            templates = ", ".join(_safe_path(path) for path in result.template_paths)
            suffix = f" (templates: {templates})" if templates else ""
            items.append(f"  {result.name} — {locations}{suffix}")
        _items(lines, items, markdown=False)

    lines.append("Unused template keys:")
    _items(lines, [
        f"  {item.name} — {', '.join(_safe_path(path) for path in item.template_paths)}"
        for item in report.unused_template_keys
    ], markdown=False)
    lines.append("Dynamic accesses:")
    _items(lines, [
        f"  {item.language} — {_safe_path(item.path)}:{item.line}"
        for item in report.dynamic_accesses
    ], markdown=False)
    lines.append("Diagnostics:")
    _items(lines, [
        f"  {item.code} — {_safe_path(item.path)}:{item.line}"
        for item in report.diagnostics
    ], markdown=False)
    return "\n".join(lines) + "\n"


def _render_markdown(report: EnvReport) -> str:
    lines = ["# EnvRef Map", "", f"- Scanned files: `{report.scanned_files}`", "", "## Templates"]
    _items(lines, [f"- {_code_span(_safe_path(path))}" for path in report.template_paths], markdown=True)

    for status, title in (("documented", "Documented keys"), ("missing", "Missing keys")):
        lines.extend(["", f"## {title}"])
        items = []
        for result in report.keys:
            if result.status != status:
                continue
            locations = ", ".join(_code_span(_safe_path(f"{ref.path}:{ref.line}")) for ref in result.references)
            templates = ", ".join(_code_span(_safe_path(path)) for path in result.template_paths)
            suffix = f" (templates: {templates})" if templates else ""
            items.append(f"- {_code_span(result.name)} — {locations}{suffix}")
        _items(lines, items, markdown=True)

    lines.extend(["", "## Unused template keys"])
    _items(lines, [
        f"- {_code_span(item.name)} — {', '.join(_code_span(_safe_path(path)) for path in item.template_paths)}"
        for item in report.unused_template_keys
    ], markdown=True)
    lines.extend(["", "## Dynamic accesses"])
    _items(lines, [
        f"- {item.language} — {_code_span(_safe_path(f'{item.path}:{item.line}'))}"
        for item in report.dynamic_accesses
    ], markdown=True)
    lines.extend(["", "## Diagnostics"])
    _items(lines, [
        f"- {item.code} — {_code_span(_safe_path(f'{item.path}:{item.line}'))}"
        for item in report.diagnostics
    ], markdown=True)
    return "\n".join(lines) + "\n"


def render_report(report: EnvReport, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(_json_payload(report), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if output_format == "text":
        return _render_text(report)
    if output_format == "markdown":
        return _render_markdown(report)
    raise ValueError("output format must be text, markdown, or json")
