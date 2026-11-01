from __future__ import annotations

import unittest

from envref_map.scanner_shell import scan_shell


class ShellScannerTests(unittest.TestCase):
    def test_detects_dollar_and_braced_expansions(self) -> None:
        chunk = scan_shell('echo "$API_KEY"\nprintf %s "${DATABASE_URL}"\n', "scripts/start.sh")

        self.assertEqual(
            [(item.key, item.path, item.line) for item in chunk.references],
            [("API_KEY", "scripts/start.sh", 1), ("DATABASE_URL", "scripts/start.sh", 2)],
        )
        self.assertEqual(chunk.dynamic_accesses, ())

    def test_supports_default_and_required_modifiers(self) -> None:
        chunk = scan_shell('echo "${PORT:-8080}"\n: "${TOKEN:?required}"\n', "run.sh")

        self.assertEqual([(item.key, item.line) for item in chunk.references], [("PORT", 1), ("TOKEN", 2)])

    def test_ignores_single_quotes_and_comments(self) -> None:
        chunk = scan_shell(
            "# $COMMENTED\n"
            "echo '$SINGLE ${SINGLE_BRACED}'\n"
            'echo "$DOUBLE" # $TRAILING_COMMENT\n'
            'echo \\$ESCAPED and "\\${DOUBLE_ESCAPED}"\n',
            "run.sh",
        )

        self.assertEqual([(item.key, item.line) for item in chunk.references], [("DOUBLE", 3)])
        self.assertEqual(chunk.dynamic_accesses, ())

    def test_reports_indirect_expansion_as_dynamic(self) -> None:
        chunk = scan_shell('echo "${!PREFIX}"\necho "${!OTHER}"\n', "run.sh")

        self.assertEqual(chunk.references, ())
        self.assertEqual(
            [(item.path, item.line, item.language) for item in chunk.dynamic_accesses],
            [("run.sh", 1, "shell"), ("run.sh", 2, "shell")],
        )

    def test_ignores_special_pid_parameter_before_literal_name(self) -> None:
        chunk = scan_shell('echo "$$NAME"\necho "$${BRACED}"\n', "run.sh")

        self.assertEqual(chunk.references, ())
        self.assertEqual(chunk.dynamic_accesses, ())

    def test_nested_command_substitution_respects_its_own_quotes(self) -> None:
        chunk = scan_shell(
            'echo "$(printf \'%s\' \'$FAKE_INSIDE_SUBSTITUTION\')" "$REAL_AFTER_SUBSTITUTION"\n',
            "run.sh",
        )

        self.assertEqual([(item.key, item.line) for item in chunk.references], [
            ("REAL_AFTER_SUBSTITUTION", 1),
        ])

    def test_quoted_heredoc_body_is_skipped_and_scanning_resumes(self) -> None:
        chunk = scan_shell(
            "cat <<'EOF'\n"
            "$FAKE_IN_HEREDOC\n"
            "EOF\n"
            'echo "$REAL_AFTER_HEREDOC"\n',
            "run.sh",
        )

        self.assertEqual([(item.key, item.line) for item in chunk.references], [
            ("REAL_AFTER_HEREDOC", 4),
        ])


if __name__ == "__main__":
    unittest.main()
