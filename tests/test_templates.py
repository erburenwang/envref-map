from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from envref_map.templates import discover_template_paths, parse_template


class TemplateTests(unittest.TestCase):
    def test_discovers_safe_templates_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "services" / "api"
            nested.mkdir(parents=True)
            expected = [root / ".env.example", nested / ".env.sample", root / ".env.template"]
            for path in expected:
                path.write_text("KEY=value\n", encoding="utf-8")
            for unsafe in (".env", ".env.local", ".env.production", ".env.local.example"):
                (root / unsafe).write_text("SECRET=value\n", encoding="utf-8")

            self.assertEqual(discover_template_paths(root), tuple(sorted(expected, key=lambda p: p.as_posix())))

    def test_parses_export_and_plain_assignments_without_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / ".env.example"
            path.write_text("# comment\n\nexport API_KEY=top-secret\nPLAIN = another-secret\nAPI_KEY=duplicate-secret\nnot an assignment\n", encoding="utf-8")

            definitions = parse_template(path, root)

            self.assertEqual([(item.key, item.path, item.line) for item in definitions], [
                ("API_KEY", ".env.example", 3),
                ("PLAIN", ".env.example", 4),
                ("API_KEY", ".env.example", 5),
            ])
            self.assertEqual(set(dataclasses.asdict(definitions[0])), {"key", "path", "line"})
            self.assertNotIn("top-secret", repr(definitions))
            self.assertNotIn("another-secret", repr(definitions))
            self.assertNotIn("duplicate-secret", repr(definitions))

    def test_multiline_quoted_values_are_never_reinterpreted_as_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / ".env.example"
            path.write_text(
                'PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n'
                'c2VjcmV0Cg==\n'
                'FAKE_KEY=looks-like-an-assignment\n'
                '-----END PRIVATE KEY-----"\n'
                'SAFE_KEY=example\n',
                encoding="utf-8",
            )

            definitions = parse_template(path, root)

            self.assertEqual([(item.key, item.line) for item in definitions], [
                ("PRIVATE_KEY", 1),
                ("SAFE_KEY", 5),
            ])
            serialized = repr(definitions)
            for value_fragment in ("c2VjcmV0", "FAKE_KEY", "looks-like-an-assignment"):
                self.assertNotIn(value_fragment, serialized)

    def test_escaped_quote_does_not_end_a_multiline_value_early(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / ".env.example"
            path.write_text(
                "SINGLE_QUOTED='first line \\'\n"
                "FAKE_KEY=must-not-appear\n"
                "end'\n"
                "SAFE_KEY=example\n",
                encoding="utf-8",
            )

            definitions = parse_template(path, root)

            self.assertEqual([(item.key, item.line) for item in definitions], [
                ("SINGLE_QUOTED", 1),
                ("SAFE_KEY", 4),
            ])

    def test_rejects_real_env_names_even_when_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in (".env", ".env.local", ".env.production", ".env.example.local", ".env.local.example"):
                path = root / name
                path.write_text("SECRET=do-not-read\n", encoding="utf-8")
                with self.subTest(name=name), self.assertRaises(ValueError):
                    parse_template(path, root)

    def test_rejects_unsafe_requested_env_alias_when_it_resolves_to_safe_template(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            safe = root / ".env.example"
            safe.write_text("KEY=value\n", encoding="utf-8")
            alias = root / ".env.local.example"

            original_resolve = Path.resolve

            def resolve_alias(path: Path, *args: object, **kwargs: object) -> Path:
                if path == alias:
                    return safe
                return original_resolve(path, *args, **kwargs)

            with patch.object(Path, "resolve", resolve_alias):
                with self.assertRaises(ValueError):
                    parse_template(alias, root)

    def test_rejects_template_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "project"
            root.mkdir()
            external = parent / "outside.example"
            external.write_text("KEY=value\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                parse_template(external, root)

    def test_rejects_symlink_escape_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "project"
            root.mkdir()
            external = parent / ".env.example"
            external.write_text("SECRET=do-not-read\n", encoding="utf-8")
            link = root / ".env.example"
            try:
                link.symlink_to(external)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"file symlinks are unavailable: {error}")

            with self.assertRaises(ValueError):
                parse_template(link, root)


if __name__ == "__main__":
    unittest.main()
