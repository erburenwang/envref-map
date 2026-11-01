# EnvRef Map Design

**Status:** Implemented; public release pending  
**Proposed repository/package:** `envref-map`  
**Command:** `envref-map`

## Intent

EnvRef Map helps developers see which environment-variable names their source code reads and whether those names are represented in safe example templates such as `.env.example`, `.env.sample`, and `.env.template`. It addresses a common deployment failure: code starts requiring a new variable while setup documentation stays stale.

The user chose an offline, multi-language pattern-scanning direction. Existing projects already cover work handoffs, Git branch cleanup, Git change review, and issue-report drafting; this project adds a source-level configuration map. The name `EnvMirror` is already used on GitHub, so `envref-map` is the proposed distinct name.

## Goals

- Scan common static environment-variable references in Python, JavaScript, TypeScript, and shell source files.
- Report each detected key with source paths and line numbers.
- Compare the detected keys with recognized example-template files and report missing and unused keys.
- Produce readable text, Markdown, and stable versioned JSON output.
- Offer a CI-friendly strict mode that exits nonzero when references are missing from templates.
- Work offline with Python 3.11+ and no runtime dependencies.
- Keep scans read-only and deterministic.

## Non-goals

- Read real secret-bearing files such as `.env`, `.env.local`, or `.env.production`, including when they are explicitly passed as templates.
- Print, persist, validate, or infer variable values, defaults, secret contents, or value formats.
- Resolve dynamic key construction, evaluate code, or claim complete language parsing.
- Generate or edit templates automatically.
- Fetch dependencies, access networks, modify the inspected repository, or integrate with an AI service.
- Support every language or configuration library in the first release.

## Anti-goals

- Do not label a key safe, required, or correctly configured just because its name appears in a template.
- Do not fail a scan because a dynamic lookup cannot be resolved; explain that such lookups are outside static coverage.
- Do not silently treat source patterns as a complete inventory of runtime configuration.

## Approaches considered

1. **Python-only AST scanner.** This gives stronger syntax-aware results with a small standard-library implementation, but excludes common JavaScript, TypeScript, and shell projects.
2. **Conservative language-specific pattern scanners.** This covers Python, JavaScript, TypeScript, and shell while keeping installation lightweight. Python can use the standard-library AST for common access forms; the other scanners can use token-aware patterns. Dynamic access remains explicitly incomplete. **Chosen by the user** because it provides useful breadth without a parser dependency.
3. **Tree-sitter parsers.** This offers broader syntax-aware scanning and a path to more languages, but adds runtime dependencies, packaging work, and cross-platform complexity before the core use case is validated.

## Proposed behavior

### Inputs and discovery

- `envref-map scan` scans the current directory; `--root PATH` selects another project root.
- Scan `.py`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx`, `.sh`, and `.bash` files.
- Skip `.git`, `node_modules`, virtual environments, common build outputs, and symlinked directories.
- Recognize example templates by exact basename: `.env.example`, `.env.sample`, and `.env.template`. Allow repeatable `--template PATH` for a differently named example file.
- Resolve relative custom template paths from `--root`; require every resolved path, including symlink targets, to remain inside the selected root. A custom template basename must end in `.example`, `.sample`, or `.template`. Always reject `.env` and other `.env.*` names except the three recognized safe example basenames, even when explicitly passed.
- For the first release, compare references within the selected root against the union of selected templates. For monorepos with separate service environments, users can run once per service root; service-specific scope inference is deferred.
- Ignore comments and ordinary string literals where practical. Tests will pin the supported syntax and known edge cases.
- Report only root-relative paths. Tests will cover unsafe template names, paths outside the root, and symlinks that escape the root.

### Static reference patterns

- Python: `os.getenv("KEY")`, `os.environ.get("KEY")`, and `os.environ["KEY"]` with literal keys.
- JavaScript/TypeScript: `process.env.KEY`, `process.env["KEY"]`, `import.meta.env.KEY`, and literal bracket access.
- Shell: `$KEY` and `${KEY}`, including common parameter modifiers such as `:-` and `:?`.
- Non-literal lookups such as `process.env[name]` are not attributed to a key. Where reliably recognizable, they appear in a separate dynamic-access note with a source location.
- Template parsing reads only the key portion of assignment lines, discards values immediately, and emits no value text.

### Results and exit behavior

- Text and Markdown reports group keys by status and show source references as `path:line`.
- JSON schema version 1 contains scanned-file counts, template paths, referenced key names, source locations, template presence, unused template keys, and dynamic-access notes.
- Names and paths are sorted for deterministic output.
- Normal mode returns 0 when a report is produced. `--strict` returns 1 when any referenced key is absent from all selected templates. Invalid arguments return 2; unreadable source or template files return 1 with a concise path-based diagnostic.
- Reports never include assignment values, source-line contents, or absolute paths.

## Constraints and safety

- Python 3.11+; standard library only at runtime.
- No network access and no subprocess execution.
- Ignore real `.env*` files by default; only exact example basenames are eligible as templates.
- Read text files with a documented encoding policy, skip binary data, and avoid following symlinks.
- Preserve Unicode paths and deterministic ordering across Windows, macOS, and Linux.
- CI should run unit tests, compile checks, package installation, and CLI smoke checks on Python 3.11 and 3.13 across Ubuntu, Windows, and macOS.

## Builder-check disposition

The independent builder review asked whether a custom template could point outside the selected root or at a real `.env` file. **My call:** resolve and contain every template under the root, reject real `.env*` basenames even when explicitly supplied, and require custom templates to use an `.example`, `.sample`, or `.template` suffix. This keeps the custom-template feature while preserving the no-secret-file boundary.

## Calls left to the builder

- Exact token-aware handling of comments, quoted keys, and multiline syntax, provided tests demonstrate the documented patterns.
- Internal module boundaries and error-message wording.
- A conservative default exclusion list for generated and vendored directories.

The builder may not broaden language or configuration coverage, read real `.env` files, or weaken the no-value-output promise without revising this design.
