from __future__ import annotations

import json
import unittest

from envref_map.model import (
    DynamicAccess,
    EnvReport,
    KeyResult,
    ScanDiagnostic,
    SourceReference,
    UnusedTemplateKey,
)
from envref_map.report import render_report


def sample_report() -> EnvReport:
    return EnvReport(
        schema_version=1,
        scanned_files=3,
        template_paths=(".env.example",),
        keys=(
            KeyResult("DATABASE_URL", "documented", (SourceReference("DATABASE_URL", "src/db.py", 8),), (".env.example",)),
            KeyResult("MISSING_TOKEN", "missing", (SourceReference("MISSING_TOKEN", "src/auth.ts", 4),), ()),
        ),
        unused_template_keys=(UnusedTemplateKey("UNUSED_FLAG", (".env.example",)),),
        dynamic_accesses=(DynamicAccess("src/config.js", 12, "javascript"),),
        diagnostics=(ScanDiagnostic("broken.py", 3, "python_syntax_error"),),
    )


class ReportTests(unittest.TestCase):
    def test_json_is_versioned_and_deterministic(self) -> None:
        report = sample_report()

        first = render_report(report, "json")
        second = render_report(report, "json")
        payload = json.loads(first)

        self.assertEqual(first, second)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["keys"][0]["name"], "DATABASE_URL")
        self.assertEqual(payload["keys"][1]["status"], "missing")
        self.assertEqual(payload["dynamic_accesses"][0]["language"], "javascript")

    def test_text_and_markdown_include_scan_results(self) -> None:
        report = sample_report()

        text = render_report(report, "text")
        markdown = render_report(report, "markdown")

        self.assertIn("MISSING_TOKEN", text)
        self.assertIn("src/auth.ts:4", text)
        self.assertIn("Unused template keys", text)
        self.assertIn("## Missing keys", markdown)
        self.assertIn("MISSING_TOKEN", markdown)
        self.assertIn("src/config.js:12", markdown)

    def test_rejects_unknown_format(self) -> None:
        with self.assertRaises(ValueError):
            render_report(sample_report(), "xml")

    def test_markdown_uses_code_span_delimiters_longer_than_path_backtick_runs(self) -> None:
        report = EnvReport(
            schema_version=1,
            scanned_files=1,
            template_paths=(),
            keys=(
                KeyResult(
                    "TOKEN",
                    "missing",
                    (SourceReference("TOKEN", "src/a``b.ts", 7),),
                    (),
                ),
            ),
            unused_template_keys=(),
            dynamic_accesses=(),
            diagnostics=(),
        )

        markdown = render_report(report, "markdown")

        self.assertIn("```src/a``b.ts:7```", markdown)


if __name__ == "__main__":
    unittest.main()
