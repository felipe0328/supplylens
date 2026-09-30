import json
import tempfile
import unittest
from pathlib import Path

from bump_version import bump_version, parse_version, update_manifest_files


class VersionTests(unittest.TestCase):
    def test_parse_version_requires_three_numeric_components(self) -> None:
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))
        for value in ("1.2", "v1.2.3", "1.2.3-alpha"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_version(value)

    def test_bump_version_uses_semantic_versioning(self) -> None:
        self.assertEqual(bump_version("1.2.3", "major"), "2.0.0")
        self.assertEqual(bump_version("1.2.3", "minor"), "1.3.0")
        self.assertEqual(bump_version("1.2.3", "patch"), "1.2.4")

    def test_update_manifest_files_supports_repeated_bumps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend = root / "apps" / "backend"
            web = root / "apps" / "web"
            backend.mkdir(parents=True)
            web.mkdir(parents=True)
            (backend / "pyproject.toml").write_text(
                '[project]\nversion = "0.1.0"\n', encoding="utf-8"
            )
            (web / "package.json").write_text(
                '{"name": "web", "version": "0.1.0"}\n', encoding="utf-8"
            )
            (root / "README.md").write_text(
                "![Version](https://img.shields.io/badge/version-v0.1.0-8b5cf6)\n",
                encoding="utf-8",
            )

            update_manifest_files("0.2.0", root)
            update_manifest_files("0.2.1", root)

            self.assertIn(
                'version = "0.2.1"',
                (backend / "pyproject.toml").read_text(encoding="utf-8"),
            )
            package = json.loads((web / "package.json").read_text(encoding="utf-8"))
            self.assertEqual(package["version"], "0.2.1")
            self.assertIn(
                "version-v0.2.1-8b5cf6",
                (root / "README.md").read_text(encoding="utf-8"),
            )

    def test_update_manifest_files_requires_every_version_field(self) -> None:
        for missing_field in ("pyproject", "package", "readme"):
            with (
                self.subTest(missing_field=missing_field),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                backend = root / "apps" / "backend"
                web = root / "apps" / "web"
                backend.mkdir(parents=True)
                web.mkdir(parents=True)
                pyproject = '[project]\nversion = "0.1.0"\n'
                package = '{"name": "web", "version": "0.1.0"}\n'
                readme = (
                    "![Version](https://img.shields.io/badge/version-v0.1.0-8b5cf6)\n"
                )

                if missing_field == "pyproject":
                    pyproject = '[project]\nname = "supplylens"\n'
                elif missing_field == "package":
                    package = '{"name": "web"}\n'
                else:
                    readme = "# SupplyLens\n"

                (backend / "pyproject.toml").write_text(pyproject, encoding="utf-8")
                (web / "package.json").write_text(package, encoding="utf-8")
                (root / "README.md").write_text(readme, encoding="utf-8")

                with self.assertRaisesRegex(ValueError, "Could not update version"):
                    update_manifest_files("0.2.0", root)


if __name__ == "__main__":
    unittest.main()
