"""Small immutable records shared by the scanners and report layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TemplateDefinition:
    key: str
    path: str
    line: int


@dataclass(frozen=True, slots=True)
class SourceReference:
    key: str
    path: str
    line: int


@dataclass(frozen=True, slots=True)
class DynamicAccess:
    path: str
    line: int
    language: str


@dataclass(frozen=True, slots=True)
class ScanDiagnostic:
    path: str
    line: int
    code: str


@dataclass(frozen=True, slots=True)
class ScanChunk:
    references: tuple[SourceReference, ...] = ()
    dynamic_accesses: tuple[DynamicAccess, ...] = ()
    diagnostics: tuple[ScanDiagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class KeyResult:
    name: str
    status: str
    references: tuple[SourceReference, ...]
    template_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UnusedTemplateKey:
    name: str
    template_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EnvReport:
    schema_version: int
    scanned_files: int
    template_paths: tuple[str, ...]
    keys: tuple[KeyResult, ...]
    unused_template_keys: tuple[UnusedTemplateKey, ...]
    dynamic_accesses: tuple[DynamicAccess, ...]
    diagnostics: tuple[ScanDiagnostic, ...]
