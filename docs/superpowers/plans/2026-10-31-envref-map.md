# EnvRef Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publicly release an offline CLI that maps static environment-variable references to safe example templates.

**Architecture:** A root walker discovers supported source and template files. Language-specific scanners return key references, dynamic-access notes, and diagnostics; analysis compares these with template keys; renderers produce text, Markdown, or versioned JSON. The CLI owns argument parsing and exit codes.

**Tech Stack:** Python 3.11+, standard library only, `unittest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-31-envref-map-design.md`

## Global Constraints

- Requires Python 3.11+ and has no runtime dependencies.
- The scan is offline, read-only, deterministic, and starts from `envref-map scan`.
- Scan `.py`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx`, `.sh`, and `.bash` source files.
- Never read `.env` or real `.env.*` files; recognize only `.env.example`, `.env.sample`, and `.env.template` automatically.
- Explicit custom templates must be root-contained after resolution and end in `.example`, `.sample`, or `.template`.
- Output includes key names and root-relative paths; it excludes values, source-line contents, and absolute paths.
- Dynamic key construction is outside static coverage and must not be guessed.
- Text, Markdown, and JSON are supported; JSON uses schema version 1.
- Normal report mode returns 0; `--strict` returns 1 for missing template keys; operational scan errors return 1; invalid arguments return 2.
- CI targets Ubuntu, Windows, and macOS with Python 3.11 and 3.13.
- In local PowerShell test runs, set `$env:PYTHONPATH = 'src'`; CI sets `PYTHONPATH=src`.

## Review Focus

- A custom path or symlink escapes the root, or names a real `.env` file: reject it before reading; test in Task 1.
- Duplicate keys appear in several templates or definitions: merge locations deterministically without exposing values; test in Task 1 and Task 5.
- Environment-looking text occurs in comments or ordinary strings: ignore it; test in Tasks 2–4.
- A lookup uses a computed key: report a dynamic-access note without inventing a key; test in Tasks 2–4.
- Unicode and unusual relative paths are reported: preserve them and stable ordering in JSON; test in Task 5.

---

## File Structure

- `src/envref_map/model.py`: immutable records shared by scanners, analysis, and renderers.
- `src/envref_map/templates.py`: safe template discovery, path validation, and key-only parsing.
- `src/envref_map/scanner_python.py`: Python AST-based static references.
- `src/envref_map/scanner_javascript.py`: token-aware JavaScript/TypeScript patterns.
- `src/envref_map/scanner_shell.py`: shell expansion patterns with comment/quote handling.
- `src/envref_map/project_scan.py`: root traversal and scanner dispatch.
- `src/envref_map/analysis.py`: missing and unused key calculation.
- `src/envref_map/report.py`: deterministic text, Markdown, and JSON rendering.
- `src/envref_map/cli.py`, `src/envref_map/__main__.py`: CLI and module entry point.
- `tests/test_templates.py`, `tests/test_scan_python.py`, `tests/test_scan_javascript.py`, `tests/test_scan_shell.py`, `tests/test_project_scan.py`, `tests/test_report.py`, `tests/test_cli.py`: focused and end-to-end behavior.

## Tasks

### Task 1: Data model and safe template reader

**Files:**
- Create: `src/envref_map/__init__.py`, `src/envref_map/model.py`, `src/envref_map/templates.py`
- Create: `tests/test_templates.py`

**Interfaces:**
- Produces `TemplateDefinition(key: str, path: str, line: int)`.
- Produces `SourceReference(key: str, path: str, line: int)`, `DynamicAccess(path: str, line: int, language: str)`, `ScanDiagnostic(path: str, line: int, code: str)`, and `ScanChunk(references: tuple[SourceReference, ...], dynamic_accesses: tuple[DynamicAccess, ...], diagnostics: tuple[ScanDiagnostic, ...])`.
- Produces `KeyResult(name: str, status: str, references: tuple[SourceReference, ...], template_paths: tuple[str, ...])`, `UnusedTemplateKey(name: str, template_paths: tuple[str, ...])`, and `EnvReport(schema_version: int, scanned_files: int, template_paths: tuple[str, ...], keys: tuple[KeyResult, ...], unused_template_keys: tuple[UnusedTemplateKey, ...], dynamic_accesses: tuple[DynamicAccess, ...], diagnostics: tuple[ScanDiagnostic, ...])`.
- Produces `discover_template_paths(root: Path, custom_paths: Sequence[Path] = ()) -> tuple[Path, ...]` and `parse_template(path: Path, root: Path) -> tuple[TemplateDefinition, ...]`.

- [x] Create a minimal package/test skeleton and initialize Git on branch `main`.
- [x] Write `test_discovers_safe_templates_recursively`, `test_parses_export_and_plain_assignments_without_values`, `test_rejects_real_env_names_even_when_explicit`, `test_rejects_template_outside_root`, and `test_rejects_symlink_escape_when_supported`.
- [x] Run `python -m unittest discover -s tests -p test_templates.py -v`; confirm the new tests fail for the missing interfaces or behavior.
- [x] Implement safe discovery and parsing. Resolve explicit paths against the selected root, reject resolved escapes and unsafe `.env*` names, retain duplicate key locations, and discard assignment values after extracting the key.
- [x] Run the focused template tests; require all pass and verify serialized records contain no value fields.
- [x] Commit with `feat: add safe environment template reader`.

### Task 2: Python reference scanner

**Files:**
- Create: `src/envref_map/scanner_python.py`
- Create: `tests/test_scan_python.py`

**Interfaces:**
- Consumes `ScanChunk` and reference records from Task 1.
- Produces `scan_python(source: str, path: str) -> ScanChunk`.

- [x] Write `test_detects_getenv_environ_get_and_subscript`, `test_ignores_comments_and_unrelated_strings`, `test_reports_nonliteral_lookup_as_dynamic`, and `test_reports_python_syntax_error_without_source_text`.
- [x] Run `python -m unittest discover -s tests -p test_scan_python.py -v`; confirm the tests fail before implementation.
- [x] Implement recognition of literal `os.getenv("KEY")`, `os.environ.get("KEY")`, and `os.environ["KEY"]` references using Python's standard-library AST; mark non-literal arguments/subscripts as dynamic accesses.
- [x] Run the focused Python scanner tests; require exact keys and line numbers and no matches from comments or ordinary strings.
- [x] Commit with `feat: scan Python environment references`.

### Task 3: JavaScript and TypeScript reference scanner

**Files:**
- Create: `src/envref_map/scanner_javascript.py`
- Create: `tests/test_scan_javascript.py`

**Interfaces:**
- Produces `scan_javascript(source: str, path: str) -> ScanChunk`.

- [x] Write `test_detects_process_and_import_meta_accesses`, `test_ignores_comments_and_ordinary_strings`, `test_reports_computed_environment_key_as_dynamic`, and `test_preserves_source_line_numbers`.
- [x] Run `python -m unittest discover -s tests -p test_scan_javascript.py -v`; confirm failure before implementation.
- [x] Implement token-aware recognition of `process.env.KEY`, `process.env["KEY"]`, `import.meta.env.KEY`, and literal bracket access; ignore comment/string contents and report computed bracket access as dynamic.
- [x] Run the focused JavaScript/TypeScript scanner tests; require exact key names, lines, and dynamic notes.
- [x] Commit with `feat: scan JavaScript environment references`.

### Task 4: Shell reference scanner

**Files:**
- Create: `src/envref_map/scanner_shell.py`
- Create: `tests/test_scan_shell.py`

**Interfaces:**
- Produces `scan_shell(source: str, path: str) -> ScanChunk`.

- [x] Write `test_detects_dollar_and_braced_expansions`, `test_supports_default_and_required_modifiers`, `test_ignores_single_quotes_and_comments`, and `test_reports_indirect_expansion_as_dynamic`.
- [x] Run `python -m unittest discover -s tests -p test_scan_shell.py -v`; confirm failure before implementation.
- [x] Implement line-aware expansion scanning for `$KEY` and `${KEY}`, including `:-` and `:?`; respect single quotes, double quotes, escapes, and shell comments.
- [x] Run the focused shell scanner tests; require exact references and no single-quoted/comment matches.
- [x] Commit with `feat: scan shell environment references`.

### Task 5: Project traversal, comparison, and reports

**Files:**
- Create: `src/envref_map/project_scan.py`, `src/envref_map/analysis.py`, `src/envref_map/report.py`
- Create: `tests/test_project_scan.py`, `tests/test_report.py`

**Interfaces:**
- Produces `scan_project(root: Path, custom_templates: Sequence[Path] = ()) -> EnvReport`.
- Produces `analyze_scan(scanned_files: int, references: Sequence[SourceReference], templates: Sequence[TemplateDefinition], dynamic_accesses: Sequence[DynamicAccess], diagnostics: Sequence[ScanDiagnostic]) -> EnvReport`.
- Produces `render_report(report: EnvReport, output_format: str) -> str`; valid formats are `text`, `markdown`, and `json`.
- `EnvReport` contains `schema_version`, `scanned_files`, `template_paths`, `keys`, `unused_template_keys`, `dynamic_accesses`, and `diagnostics`. Each key result contains its name, `documented` or `missing` status, all source references, and template paths.

- [x] Write `test_dispatches_supported_extensions_and_skips_build_dirs`, `test_skips_symlinked_source_outside_root_when_supported`, `test_ignores_real_env_files_without_opening_them`, `test_duplicate_template_keys_merge_all_paths`, `test_missing_key_contains_all_source_locations`, `test_unused_keys_are_reported`, `test_unicode_paths_and_json_are_deterministic`, and `test_reports_relative_paths_without_values_or_absolute_root`.
- [x] Run the focused project-scan and report tests; confirm failure before implementation.
- [x] Implement deterministic traversal of supported extensions, skip ignored directories and symlinks, dispatch to the language scanners, compare keys against the union of safe templates, and render schema version 1.
- [x] Run `python -m unittest discover -s tests -p test_project_scan.py -v` and `python -m unittest discover -s tests -p test_report.py -v`; require all pass.
- [x] Commit with `feat: map source references to environment templates`.

### Task 6: CLI and end-to-end behavior

**Files:**
- Create: `src/envref_map/cli.py`, `src/envref_map/__main__.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Produces `main(argv: Sequence[str] | None = None) -> int`.
- Command syntax: `envref-map scan [--root PATH] [--template PATH ...] [--format text|markdown|json] [--strict]`.

- [x] Write `test_help_lists_scan_options`, `test_all_formats_work_from_temporary_project`, `test_strict_fails_only_for_missing_template_keys`, `test_invalid_arguments_return_two`, `test_scan_errors_return_one_without_source_contents`, `test_scan_does_not_modify_project`, and `test_scan_does_not_use_network_or_subprocess`.
- [x] Run the focused CLI tests; confirm failure before implementation.
- [x] Implement argument parsing, output selection, path-based diagnostics, and exit codes exactly as specified. Normal mode returns 0 for a produced report; strict mode returns 1 for missing keys; operational scan errors return 1; invalid arguments return 2.
- [x] Run the focused CLI tests and a temporary-project end-to-end scan; require all pass.
- [x] Commit with `feat: add EnvRef Map command line interface`.

### Task 7: Packaging, documentation, CI, and public release

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.gitattributes`, `.github/workflows/ci.yml`, `README.md`, `LICENSE`, `CONTRIBUTING.md`
- Modify: `docs/superpowers/specs/2026-10-31-envref-map-design.md`, `docs/superpowers/plans/2026-10-31-envref-map.md`

- [x] Configure Python 3.11+, zero runtime dependencies, and the `envref-map` entry point in `pyproject.toml`.
- [x] Document install, CLI usage, supported syntax, privacy boundaries, dynamic-access limits, template path rules, and exit codes in English and Simplified Chinese.
- [x] Add a least-privilege GitHub Actions matrix for Ubuntu, Windows, and macOS with Python 3.11 and 3.13; run compile, unit, install, CLI help, and JSON smoke checks.
- [x] Run `python -m compileall -q src tests`, `python -m unittest discover -s tests -v`, `python -m pip install --no-deps .`, `envref-map --help`, and `envref-map scan --root . --format json`; require all checks to pass.
- [x] Review the final README and JSON output to confirm no variable values, source lines, or absolute paths are emitted.
- [x] Commit with `chore: package and document EnvRef Map`.
- [x] Close all six Important and three Minor findings from the independent final review with regression coverage, including rejecting unsafe requested template aliases.
- [x] Commit the review corrections with `fix: close final review findings`.
- [ ] Prepare the GitHub form for public repository `erburenwang/envref-map`, with the local README initialized and no duplicate remote license or ignore file. Immediately before creation, show the exact description, visibility, and options and request browser action-time confirmation.
- [ ] After the README seed commit exists, create GitHub blobs from every committed local file, create a full tree with the same paths and modes, and create a publication commit parented to the seed commit.
- [ ] Move `main` to the publication commit with the seed SHA as `expected_sha` and `force=false`; stop and inspect the branch head if the lease fails.
- [ ] Verify public visibility, remote main SHA, exact remote/local tree SHA equality, source/template files, and all six GitHub Actions jobs. Do not mark release complete while any job remains failed or unverified.

**GitHub form prepared:** description `Offline CLI that maps environment-variable references to example templates across Python, JavaScript, TypeScript, and shell.`; visibility `Public`; initialize with README `Yes`; remote `.gitignore` `None`; remote license `None` (the local README, ignore rules, and MIT license are already prepared).
