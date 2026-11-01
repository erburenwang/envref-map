from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from envref_map.project_scan import scan_project
from envref_map.report import render_report


class ProjectScanTests(unittest.TestCase):
    def test_dispatches_supported_extensions_and_skips_build_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                "app.py": 'value = os.getenv("PY_KEY")\n',
                "client.js": "const value = process.env.JS_KEY;\n",
                "client.jsx": "const value = process.env.JS_KEY;\n",
                "legacy.mjs": "const value = process.env.MJS_KEY;\n",
                "common.cjs": "const value = process.env.CJS_KEY;\n",
                "module.ts": "const value = import.meta.env.TS_MODULE_KEY;\n",
                "view.tsx": "const value = import.meta.env.TS_KEY;\n",
                "scripts/run.sh": 'echo "$SHELL_SH_KEY"\n',
                "scripts/run.bash": 'echo "$SHELL_KEY"\n',
                "dist/ignored.py": 'value = os.getenv("DIST_KEY")\n',
                "node_modules/pkg/ignored.js": "const value = process.env.NODE_KEY;\n",
                "README.md": "NOT_SOURCE=value\n",
            }
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            report = scan_project(root)

            self.assertEqual(report.scanned_files, 9)
            self.assertEqual([item.name for item in report.keys], [
                "CJS_KEY", "JS_KEY", "MJS_KEY", "PY_KEY", "SHELL_KEY", "SHELL_SH_KEY", "TS_KEY", "TS_MODULE_KEY",
            ])
            self.assertTrue(all(item.status == "missing" for item in report.keys))

    def test_skips_symlinked_source_outside_root_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "project"
            root.mkdir()
            outside = parent / "outside.py"
            outside.write_text('value = os.getenv("OUTSIDE_KEY")\n', encoding="utf-8")
            link = root / "linked.py"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"file symlinks are unavailable: {error}")

            report = scan_project(root)

            self.assertEqual(report.scanned_files, 0)
            self.assertEqual(report.keys, ())

    def test_ignores_real_env_files_without_opening_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app.py").write_text('value = os.getenv("SECRET_KEY")\n', encoding="utf-8")
            real_env_names = {
                ".env", ".env.local", ".env.production", ".env.py", ".env.sh",
                ".env.local.py", ".env.production.js",
            }
            for name in real_env_names:
                (root / name).write_text("SECRET_KEY=do-not-read\n", encoding="utf-8")
            original_open = Path.open
            opened_real_env: list[str] = []

            def guarded_open(path: Path, *args: object, **kwargs: object):
                if path.name in real_env_names:
                    opened_real_env.append(path.name)
                    raise AssertionError("real environment file was opened")
                return original_open(path, *args, **kwargs)

            with patch.object(Path, "open", guarded_open):
                report = scan_project(root)

            self.assertEqual(opened_real_env, [])
            self.assertEqual(report.scanned_files, 1)
            self.assertEqual([(item.name, item.status) for item in report.keys], [("SECRET_KEY", "missing")])

    def test_skips_nul_containing_source_and_template_with_value_free_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app.js").write_text(
                "const value = process.env.BINARY_SOURCE_KEY;\0\n", encoding="utf-8"
            )
            (root / ".env.example").write_text(
                "BINARY_TEMPLATE_KEY=\0private-value\n", encoding="utf-8"
            )

            report = scan_project(root)
            rendered = render_report(report, "json")

            self.assertEqual(report.keys, ())
            self.assertEqual(
                [(item.path, item.code) for item in report.diagnostics],
                [(".env.example", "template_binary_file"), ("app.js", "source_binary_file")],
            )
            self.assertNotIn("private-value", rendered)
            self.assertNotIn(str(root), rendered)

    def test_duplicate_template_keys_merge_all_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app.py").write_text('value = os.getenv("SHARED_KEY")\n', encoding="utf-8")
            nested = root / "service"
            nested.mkdir()
            (root / ".env.example").write_text("SHARED_KEY=first-value\n", encoding="utf-8")
            (nested / ".env.sample").write_text("SHARED_KEY=second-value\n", encoding="utf-8")

            report = scan_project(root)

            self.assertEqual(len(report.keys), 1)
            self.assertEqual(report.keys[0].status, "documented")
            self.assertEqual(report.keys[0].template_paths, (".env.example", "service/.env.sample"))

    def test_missing_key_contains_all_source_locations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "first.py").write_text('one = os.getenv("MISSING_KEY")\n', encoding="utf-8")
            (root / "second.js").write_text("const two = process.env.MISSING_KEY;\n", encoding="utf-8")

            report = scan_project(root)

            self.assertEqual(report.keys[0].status, "missing")
            self.assertEqual(
                [(item.path, item.line) for item in report.keys[0].references],
                [("first.py", 1), ("second.js", 1)],
            )

    def test_unused_keys_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app.py").write_text('value = os.getenv("USED_KEY")\n', encoding="utf-8")
            (root / ".env.example").write_text("USED_KEY=example\nUNUSED_KEY=example\n", encoding="utf-8")

            report = scan_project(root)

            self.assertEqual([(item.name, item.template_paths) for item in report.unused_template_keys], [
                ("UNUSED_KEY", (".env.example",)),
            ])

    def test_reports_empty_template_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env.example").write_text("", encoding="utf-8")

            report = scan_project(root)

            self.assertEqual(report.template_paths, (".env.example",))
            self.assertEqual(report.keys, ())

    def test_unicode_paths_and_json_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "源文件.py").write_text('value = os.getenv("UNICODE_KEY")\n', encoding="utf-8")
            nested = root / "中文目录"
            nested.mkdir()
            (nested / "页面.ts").write_text("const value = process.env.PAGE_KEY;\n", encoding="utf-8")

            report = scan_project(root)
            first = render_report(report, "json")
            second = render_report(scan_project(root), "json")

            self.assertEqual(first, second)
            self.assertIn("源文件.py", first)
            self.assertIn("中文目录/页面.ts", first)

    def test_json_preserves_sorted_space_and_backtick_paths_and_markdown_delimits_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = ["z space.py", "a`tick.js"]
            for name in names:
                source = (
                    'value = os.getenv("PATH_KEY")\n'
                    if name.endswith(".py")
                    else "const value = process.env.PATH_KEY;\n"
                )
                (root / name).write_text(source, encoding="utf-8")

            report = scan_project(root)
            payload = json.loads(render_report(report, "json"))
            markdown = render_report(report, "markdown")
            references = payload["keys"][0]["references"]

            self.assertEqual([item["path"] for item in references], ["a`tick.js", "z space.py"])
            self.assertIn("``a`tick.js:1``", markdown)
            self.assertIn("`z space.py:1`", markdown)

    def test_reports_relative_paths_without_values_or_absolute_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app.py").write_text('token = os.getenv("API_TOKEN")  # raw source line\n', encoding="utf-8")
            (root / ".env.example").write_text("API_TOKEN=example-only-secret\nUNUSED=another-secret\n", encoding="utf-8")

            report = scan_project(root)
            rendered = "\n".join([
                render_report(report, "json"),
                render_report(report, "text"),
                render_report(report, "markdown"),
            ])

            self.assertIn("app.py", rendered)
            self.assertIn(".env.example", rendered)
            self.assertNotIn(str(root), rendered)
            self.assertNotIn("example-only-secret", rendered)
            self.assertNotIn("another-secret", rendered)
            self.assertNotIn("raw source line", rendered)

if __name__ == "__main__":
    unittest.main()
