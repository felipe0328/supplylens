import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "apps" / "backend"
COVERAGE_THRESHOLD = 100.0


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary_directory:
        coverage_report = Path(temporary_directory) / "coverage.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-m",
                "not integration",
                "--cov=supplylens",
                "--cov-report=term-missing",
                f"--cov-fail-under={COVERAGE_THRESHOLD}",
                f"--cov-report=json:{coverage_report}",
            ],
            cwd=BACKEND_ROOT,
            check=False,
        )

        if result.returncode != 0:
            return result.returncode

        coverage = json.loads(coverage_report.read_text(encoding="utf-8"))
        percentage = coverage["totals"]["percent_covered"]
        print(
            f"Backend coverage: {percentage:.1f}% (target: {COVERAGE_THRESHOLD:.0f}%)."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
