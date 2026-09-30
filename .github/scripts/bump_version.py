#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

VALID_BUMPS = {"feature", "minor", "major"}


def parse_version(value: str) -> tuple[Decimal, str | None]:
    value = value.strip()
    match = re.fullmatch(
        r"(?P<number>\d+(?:\.\d+)?)(?:-(?P<label>[A-Za-z0-9.-]+))?", value
    )
    if not match:
        raise ValueError(f"Invalid version format: {value!r}")

    number = Decimal(match.group("number"))
    label = match.group("label")
    return number, label


def format_version(
    value: Decimal, label: str | None, *, force_decimal: bool = False
) -> str:
    value_text = format(value.normalize(), "f")
    if force_decimal and "." not in value_text:
        value_text = f"{value_text}.0"
    elif "." in value_text and not force_decimal:
        value_text = value_text.rstrip("0").rstrip(".")
    if value_text == "-0":
        value_text = "0"
    if label:
        return f"{value_text}-{label}"
    return value_text


def bump_version(version: str, bump: str) -> str:
    if bump not in VALID_BUMPS:
        raise ValueError(
            f"Unsupported bump type: {bump!r}. Use one of: {sorted(VALID_BUMPS)}"
        )

    current_value, label = parse_version(version)
    if bump == "feature":
        next_value = current_value + Decimal("0.1")
    elif bump == "minor":
        next_value = current_value + Decimal("0.01")
    else:
        next_value = Decimal(int(current_value) + 1)

    return format_version(next_value, label, force_decimal=(bump == "major"))


def update_manifest_files(version: str) -> None:
    root = Path(__file__).resolve().parents[2]
    pyproject_path = root / "apps" / "backend" / "pyproject.toml"
    web_package_path = root / "apps" / "web" / "package.json"
    readme_path = root / "README.md"

    if pyproject_path.exists():
        text = pyproject_path.read_text(encoding="utf-8")
        pyproject_path.write_text(
            text.replace(
                'version = "0.1.0-alpha"',
                f'version = "{version.replace("-alpha", ".0-alpha")}"',
            ),
            encoding="utf-8",
        )

    if web_package_path.exists():
        text = web_package_path.read_text(encoding="utf-8")
        web_package_path.write_text(
            text.replace(
                '"version": "0.1.0-alpha"',
                f'"version": "{version.replace("-alpha", ".0-alpha")}"',
            ),
            encoding="utf-8",
        )

    if readme_path.exists():
        text = readme_path.read_text(encoding="utf-8")
        readme_path.write_text(
            text.replace("Current version: v0.1-alpha", f"Current version: v{version}"),
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bump the project version based on a PR label."
    )
    parser.add_argument(
        "--bump", choices=sorted(VALID_BUMPS), required=True, help="Version bump type"
    )
    parser.add_argument(
        "--version-file", default="VERSION", help="Path to the version file"
    )
    args = parser.parse_args()

    version_file = Path(args.version_file)
    if not version_file.exists():
        raise FileNotFoundError(f"Version file not found: {version_file}")

    current_version = version_file.read_text(encoding="utf-8").strip()
    next_version = bump_version(current_version, args.bump)
    version_file.write_text(f"{next_version}\n", encoding="utf-8")

    # Keep package manifests and the visible README in sync.
    update_manifest_files(next_version)
    print(next_version)


if __name__ == "__main__":
    try:
        main()
    except (InvalidOperation, ValueError) as exc:
        raise SystemExit(str(exc))
