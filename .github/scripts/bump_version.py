from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

VALID_BUMPS = {"major", "minor", "patch"}
SEMVER_PATTERN = re.compile(
    r"(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
)


def parse_version(value: str) -> tuple[int, int, int]:
    match = SEMVER_PATTERN.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Invalid semantic version: {value!r}")
    return tuple(int(match.group(part)) for part in ("major", "minor", "patch"))


def bump_version(version: str, bump: str) -> str:
    if bump not in VALID_BUMPS:
        raise ValueError(
            f"Unsupported bump type: {bump!r}. Use one of: {sorted(VALID_BUMPS)}"
        )

    major, minor, patch = parse_version(version)
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"Could not update version in {path}.")
    path.write_text(updated, encoding="utf-8")


def update_manifest_files(version: str, root: Path) -> None:
    pyproject_path = root / "apps" / "backend" / "pyproject.toml"
    web_package_path = root / "apps" / "web" / "package.json"
    readme_path = root / "README.md"

    replace_once(
        pyproject_path,
        r'^version = "[^"]+"$',
        f'version = "{version}"',
    )

    package = json.loads(web_package_path.read_text(encoding="utf-8"))
    if "version" not in package:
        raise ValueError(f"Could not update version in {web_package_path}.")
    package["version"] = version
    web_package_path.write_text(
        json.dumps(package, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    replace_once(
        readme_path,
        r"^!\[Version\]\(https://img\.shields\.io/badge/version-v[^)]+\)$",
        f"![Version](https://img.shields.io/badge/version-v{version}-8b5cf6)",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bump the project semantic version based on a PR classification."
    )
    parser.add_argument(
        "--bump", choices=sorted(VALID_BUMPS), required=True, help="Version bump type"
    )
    parser.add_argument(
        "--version-file", default="VERSION", help="Path to the version file"
    )
    args = parser.parse_args()

    version_file = Path(args.version_file).resolve()
    if not version_file.exists():
        raise FileNotFoundError(f"Version file not found: {version_file}")

    current_version = version_file.read_text(encoding="utf-8").strip()
    next_version = bump_version(current_version, args.bump)
    version_file.write_text(f"{next_version}\n", encoding="utf-8")
    update_manifest_files(next_version, version_file.parent)
    print(next_version)


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
