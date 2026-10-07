from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Iterable
from pathlib import Path

VALID_BUMPS = {"major", "minor", "patch"}
SEMVER_PATTERN = re.compile(
    r"(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
)


def classify_bump(title: str, labels: str | Iterable[str] | None = None) -> str:
    """Return the semantic bump requested by a pull request title and labels.

    A title may start with a ticket, as in ``[SUP-123] feat: add an endpoint``.
    The prefix after that ticket selects the bump. Titles that still use the
    older ``feat: [SUP-123] summary`` form remain valid.
    """

    if labels is None:
        label_values: list[str] = []
    elif isinstance(labels, str):
        label_values = [label.strip().lower() for label in labels.split(",")]
    else:
        label_values = [str(label).strip().lower() for label in labels]
    normalized_labels = {label for label in label_values if label}

    normalized_title = title.strip().lower()
    title_without_ticket = re.sub(r"^\[[^\]]+\]\s*", "", normalized_title)
    candidates = {normalized_title, title_without_ticket}

    def starts_with(prefix: str) -> bool:
        return any(candidate.startswith(prefix) for candidate in candidates)

    def contains(fragment: str) -> bool:
        return any(fragment in candidate for candidate in candidates)

    if "major" in normalized_labels or starts_with("major:") or contains("breaking"):
        return "major"
    if (
        "feature" in normalized_labels
        or "enhancement" in normalized_labels
        or starts_with("feat:")
        or starts_with("feature:")
        or starts_with("minor:")
        or contains("new feature")
    ):
        return "minor"
    return "patch"


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
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--bump", choices=sorted(VALID_BUMPS), help="Version bump type to apply"
    )
    action.add_argument(
        "--print-bump",
        action="store_true",
        help="Print the bump selected from PR_TITLE and PR_LABELS",
    )
    parser.add_argument(
        "--version-file", default="VERSION", help="Path to the version file"
    )
    args = parser.parse_args()

    if args.print_bump:
        print(
            classify_bump(
                os.environ.get("PR_TITLE", ""),
                os.environ.get("PR_LABELS", ""),
            )
        )
        return

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
