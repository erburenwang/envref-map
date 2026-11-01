# Contributing

Thanks for helping improve EnvRef Map. Keep changes small, conservative, and covered by tests.

## Development setup

EnvRef Map requires Python 3.11 or newer and has no runtime dependencies.

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

Set `PYTHONPATH=src` when running the test command from a checkout if the package is not installed.

## Changes and tests

- Add a focused test before changing scanner behavior.
- Preserve the offline, read-only behavior and deterministic report ordering.
- Keep `.env` and real `.env.*` files unreadable, even when passed explicitly.
- Do not include source lines, template values, or absolute paths in output or diagnostics.
- Keep unsupported dynamic lookups out of the key inventory; use a dynamic-access note when the pattern is recognizable.
- Run the full unit suite and the CLI checks described in the README before opening a pull request.

## Pull requests

Explain the user-visible behavior, list the test commands you ran, and note any syntax the scanner intentionally does not cover. New parser dependencies require a design discussion first.
