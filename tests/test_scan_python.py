from __future__ import annotations

import unittest

from envref_map.scanner_python import scan_python


class PythonScannerTests(unittest.TestCase):
    def test_detects_getenv_environ_get_and_subscript(self) -> None:
        chunk = scan_python(
            'a = os.getenv("API_KEY")\n'
            'b = os.environ.get("DATABASE_URL")\n'
            'c = os.environ["LOG_LEVEL"]\n',
            "app.py",
        )

        self.assertEqual(
            [(item.key, item.path, item.line) for item in chunk.references],
            [("API_KEY", "app.py", 1), ("DATABASE_URL", "app.py", 2), ("LOG_LEVEL", "app.py", 3)],
        )
        self.assertEqual(chunk.dynamic_accesses, ())
        self.assertEqual(chunk.diagnostics, ())

    def test_ignores_comments_and_unrelated_strings(self) -> None:
        chunk = scan_python(
            '# os.getenv("COMMENTED")\n'
            'message = "os.getenv(\\\'STRING\\\')"\n'
            "other = 'os.environ[\\\"ALSO_STRING\\\"]'\n"
            'value = os.getenv("GOOD")\n',
            "app.py",
        )

        self.assertEqual([(item.key, item.line) for item in chunk.references], [("GOOD", 4)])
        self.assertEqual(chunk.dynamic_accesses, ())

    def test_reports_nonliteral_lookup_as_dynamic(self) -> None:
        chunk = scan_python(
            "first = os.getenv(name)\n"
            "second = os.environ.get(key)\n"
            "third = os.environ[key]\n",
            "app.py",
        )

        self.assertEqual(chunk.references, ())
        self.assertEqual(
            [(item.path, item.line, item.language) for item in chunk.dynamic_accesses],
            [("app.py", 1, "python"), ("app.py", 2, "python"), ("app.py", 3, "python")],
        )

    def test_reports_python_syntax_error_without_source_text(self) -> None:
        chunk = scan_python('token = os.getenv("SECRET_TOKEN")\ninvalid =\n', "broken.py")

        self.assertEqual(chunk.references, ())
        self.assertEqual(chunk.dynamic_accesses, ())
        self.assertEqual([(item.path, item.line, item.code) for item in chunk.diagnostics], [
            ("broken.py", 2, "python_syntax_error"),
        ])
        self.assertNotIn("SECRET_TOKEN", repr(chunk))
        self.assertNotIn("invalid =", repr(chunk))


if __name__ == "__main__":
    unittest.main()
