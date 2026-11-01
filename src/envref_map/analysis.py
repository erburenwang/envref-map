"""Deterministic comparison of source references with template keys."""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from envref_map.model import (
    DynamicAccess,
    EnvReport,
    KeyResult,
    ScanDiagnostic,
    SourceReference,
    TemplateDefinition,
    UnusedTemplateKey,
)


def analyze_scan(
    scanned_files: int,
    references: Sequence[SourceReference],
    templates: Sequence[TemplateDefinition],
    dynamic_accesses: Sequence[DynamicAccess],
    diagnostics: Sequence[ScanDiagnostic],
) -> EnvReport:
    references_by_key: dict[str, list[SourceReference]] = defaultdict(list)
    template_paths_by_key: dict[str, set[str]] = defaultdict(set)

    for reference in references:
        references_by_key[reference.key].append(reference)
    for definition in templates:
        template_paths_by_key[definition.key].add(definition.path)

    results: list[KeyResult] = []
    for name in sorted(references_by_key):
        locations = tuple(sorted(references_by_key[name], key=lambda item: (item.path, item.line, item.key)))
        template_paths = tuple(sorted(template_paths_by_key.get(name, ())))
        results.append(KeyResult(
            name=name,
            status="documented" if template_paths else "missing",
            references=locations,
            template_paths=template_paths,
        ))

    unused = tuple(
        UnusedTemplateKey(name, tuple(sorted(paths)))
        for name, paths in sorted(template_paths_by_key.items())
        if name not in references_by_key
    )
    all_template_paths = tuple(sorted({definition.path for definition in templates}))

    return EnvReport(
        schema_version=1,
        scanned_files=scanned_files,
        template_paths=all_template_paths,
        keys=tuple(results),
        unused_template_keys=unused,
        dynamic_accesses=tuple(sorted(dynamic_accesses, key=lambda item: (item.path, item.line, item.language))),
        diagnostics=tuple(sorted(diagnostics, key=lambda item: (item.path, item.line, item.code))),
    )
