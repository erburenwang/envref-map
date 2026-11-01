from __future__ import annotations

import unittest

from envref_map.scanner_javascript import scan_javascript


class JavaScriptScannerTests(unittest.TestCase):
    def test_detects_process_and_import_meta_accesses(self) -> None:
        chunk = scan_javascript(
            "const a = process.env.API_KEY;\n"
            'const b = process.env["DATABASE_URL"];\n'
            "const c = import.meta.env.VITE_ENDPOINT;\n"
            "const d = import.meta.env['MODE'];\n",
            "src/app.ts",
        )

        self.assertEqual(
            [(item.key, item.path, item.line) for item in chunk.references],
            [
                ("API_KEY", "src/app.ts", 1),
                ("DATABASE_URL", "src/app.ts", 2),
                ("VITE_ENDPOINT", "src/app.ts", 3),
                ("MODE", "src/app.ts", 4),
            ],
        )
        self.assertEqual(chunk.dynamic_accesses, ())

    def test_ignores_comments_and_ordinary_strings(self) -> None:
        chunk = scan_javascript(
            "// process.env.LINE_COMMENT\n"
            "/* process.env.BLOCK_COMMENT */\n"
            'const a = "process.env.DOUBLE_STRING";\n'
            "const b = 'process.env.SINGLE_STRING';\n"
            "const pattern = /process\\.env\\.REGEX/;\n"
            "const text = `process.env.TEMPLATE_TEXT`;\n"
            "const good = process.env.REAL_KEY;\n",
            "app.js",
        )

        self.assertEqual([(item.key, item.line) for item in chunk.references], [("REAL_KEY", 7)])
        self.assertEqual(chunk.dynamic_accesses, ())

    def test_reports_computed_environment_key_as_dynamic(self) -> None:
        chunk = scan_javascript(
            "const name = getName();\n"
            "const a = process.env[name];\n"
            "const b = import.meta.env[getName()];\n",
            "app.js",
        )

        self.assertEqual(chunk.references, ())
        self.assertEqual(
            [(item.path, item.line, item.language) for item in chunk.dynamic_accesses],
            [("app.js", 2, "javascript"), ("app.js", 3, "javascript")],
        )

    def test_preserves_source_line_numbers(self) -> None:
        chunk = scan_javascript(
            "const first = process.env\n"
            "  .FIRST_KEY;\n"
            'const second = import.meta.env[\n'
            '  "SECOND_KEY"\n'
            "];\n",
            "app.tsx",
        )

        self.assertEqual([(item.key, item.line) for item in chunk.references], [("FIRST_KEY", 2), ("SECOND_KEY", 4)])

    def test_scans_template_expressions_but_not_template_text(self) -> None:
        chunk = scan_javascript(
            "const text = `process.env.NOT_CODE`;\n"
            "const message = `value: ${process.env.ACTIVE_KEY}`;\n",
            "app.js",
        )

        self.assertEqual([(item.key, item.line) for item in chunk.references], [("ACTIVE_KEY", 2)])

    def test_interpolated_bracket_keys_remain_dynamic_without_invented_names(self) -> None:
        chunk = scan_javascript(
            'const a = process.env[`PREFIX_${"SUFFIX"}`];\n'
            'const b = process.env[`${"PREFIX_"}${"OTHER"}`];\n'
            'const c = `${process.env.REAL_KEY}`;\n',
            "app.js",
        )

        self.assertEqual([(item.key, item.line) for item in chunk.references], [("REAL_KEY", 3)])
        self.assertEqual(
            [(item.path, item.line, item.language) for item in chunk.dynamic_accesses],
            [("app.js", 1, "javascript"), ("app.js", 2, "javascript")],
        )

    def test_ignores_regex_and_jsx_text_but_scans_jsx_expressions(self) -> None:
        chunk = scan_javascript(
            "const logical = flag && /process.env.LOGICAL_FAKE/.test(text);\n"
            "if (ready) /process.env.CONTROL_FAKE/.test(text);\n"
            "const view = <p>process.env.JSX_FAKE</p>;\n"
            "const active = <p>{process.env.JSX_REAL}</p>;\n"
            "const withProp = <p value={process.env.JSX_ATTR_REAL} />;\n"
            "const fragment = <>process.env.FRAGMENT_FAKE{process.env.FRAGMENT_REAL}</>;\n"
            "export default <Panel>process.env.DEFAULT_FAKE</Panel>;\n",
            "app.tsx",
        )

        self.assertEqual(
            [(item.key, item.line) for item in chunk.references],
            [("JSX_REAL", 4), ("JSX_ATTR_REAL", 5), ("FRAGMENT_REAL", 6)],
        )


if __name__ == "__main__":
    unittest.main()
