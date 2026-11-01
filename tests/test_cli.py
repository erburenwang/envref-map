from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from envref_map.cli import main


class CliTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_help_lists_scan_options(self) -> None:
        result, stdout, _ = self.invoke(["scan", "--help"])

        self.assertEqual(result, 0)
        for option in ("--root", "--template", "--format", "--strict"):
            self.assertIn(option, stdout)

    def test_all_formats_work_from_temporary_project(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app.py").write_text('value = os.getenv("API_KEY")\n', encoding="utf-8")

            for output_format in ("text", "markdown", "json"):
                with self.subTest(output_format=output_format):
                    result, stdout, stderr = self.invoke([
                        "scan", "--root", str(root), "--format", output_format,
                    ])
                    self.assertEqual(result, 0, stderr)
                    if output_format == "json":
                        self.assertEqual(json.loads(stdout)["keys"][0]["name"], "API_KEY")
                    else:
                        self.assertIn("API_KEY", stdout)

    def test_strict_fails_only_for_missing_template_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app.py").write_text('value = os.getenv("PRESENT")\n', encoding="utf-8")
            (root / ".env.example").write_text("PRESENT=example\nUNUSED=example\n", encoding="utf-8")

            result, _, stderr = self.invoke(["scan", "--root", str(root), "--strict"])
            self.assertEqual(result, 0, stderr)

            (root / "missing.py").write_text('value = os.getenv("MISSING")\n', encoding="utf-8")
            result, stdout, stderr = self.invoke(["scan", "--root", str(root), "--strict"])

            self.assertEqual(result, 1)
            self.assertIn("MISSING", stdout)
            self.assertEqual(stderr, "")

    def test_invalid_arguments_return_two(self) -> None:
        result, _, stderr = self.invoke(["scan", "--format", "xml"])

        self.assertEqual(result, 2)
        self.assertIn("invalid choice", stderr)

    def test_scan_errors_return_one_without_source_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "broken.py").write_text(
                'token = os.getenv("SOURCE_SECRET")\ninvalid =\n', encoding="utf-8"
            )

            result, stdout, stderr = self.invoke(["scan", "--root", str(root), "--format", "json"])

            self.assertEqual(result, 1)
            self.assertIn("python_syntax_error", stdout)
            self.assertNotIn("SOURCE_SECRET", stdout)
            self.assertNotIn("invalid =", stdout)
            self.assertEqual(stderr, "")

    def test_operational_os_errors_do_not_disclose_absolute_paths(self) -> None:
        private_path = r"C:\private\customer-project\secret\app.js"
        with patch("envref_map.cli.scan_project", side_effect=OSError(13, "Permission denied", private_path)):
            result, _, stderr = self.invoke(["scan", "--root", "."])

        self.assertEqual(result, 1)
        self.assertNotIn(private_path, stderr)
        self.assertNotIn("customer-project", stderr)

    def test_scan_does_not_modify_project(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app.py").write_text('value = os.getenv("API_KEY")\n', encoding="utf-8")
            (root / ".env.example").write_text("API_KEY=example-value\n", encoding="utf-8")
            before = {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}

            result, _, stderr = self.invoke(["scan", "--root", str(root)])

            after = {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}
            self.assertEqual(result, 0, stderr)
            self.assertEqual(after, before)

    def test_scan_does_not_use_network_or_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app.py").write_text('value = os.getenv("API_KEY")\n', encoding="utf-8")

            with patch("subprocess.run", side_effect=AssertionError("subprocess used")), patch(
                "subprocess.check_output", side_effect=AssertionError("subprocess used")
            ), patch("urllib.request.urlopen", side_effect=AssertionError("network used")):
                result, stdout, stderr = self.invoke(["scan", "--root", str(root), "--format", "json"])

            self.assertEqual(result, 0, stderr)
            self.assertEqual(json.loads(stdout)["keys"][0]["name"], "API_KEY")


if __name__ == "__main__":
    unittest.main()
