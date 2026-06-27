#!/usr/bin/env python3

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_COUNTER_SAMPLES = Path(
    "examples/lt/counter_samples/sample_counter_samples.csv"
)
DEFAULT_SOURCE_METADATA = Path(
    "examples/lt/counter_samples/sample_counter_source_metadata.csv"
)
DEFAULT_OUTPUT_DIR = Path(
    "examples/lt/results/project_i_profiler_counter_correlation_interface"
)
NORMALIZE_TOOL = Path("examples/lt/tools/normalize_profiler_counters.py")


class DemoError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run Project I profiler/counter correlation interface smoke test."
    )
    parser.add_argument(
        "--counter-samples",
        default=DEFAULT_COUNTER_SAMPLES,
        type=Path,
        help="Sample-only counter samples CSV.",
    )
    parser.add_argument(
        "--source-metadata",
        default=DEFAULT_SOURCE_METADATA,
        type=Path,
        help="Sample-only counter source metadata CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        type=Path,
        help="Output directory for Project I generated artifacts.",
    )
    return parser.parse_args()


def repo_path(path):
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def display_path(path):
    path = Path(path)
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def require_file(path, label):
    path = repo_path(path)
    if not path.exists():
        raise DemoError(f"{label} not found: {display_path(path)}")
    if not path.is_file():
        raise DemoError(f"{label} is not a file: {display_path(path)}")
    return path


def require_output(path, label):
    path = repo_path(path)
    if not path.exists():
        raise DemoError(f"{label} not found: {display_path(path)}")
    return path


def run_command(command):
    print("[demo-project-i] run: " + " ".join(str(part) for part in command))
    result = subprocess.run(
        [str(part) for part in command],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise DemoError(
            "command failed with exit code "
            f"{result.returncode}: {' '.join(str(part) for part in command)}"
        )


def main():
    args = parse_args()
    counter_samples = require_file(args.counter_samples, "counter samples CSV")
    source_metadata = require_file(args.source_metadata, "source metadata CSV")
    output_dir = repo_path(args.output_dir)

    run_command(
        [
            sys.executable,
            NORMALIZE_TOOL,
            "--counter-samples",
            counter_samples,
            "--source-metadata",
            source_metadata,
            "--output-dir",
            output_dir,
        ]
    )

    normalized_path = require_output(
        output_dir / "normalized_counter_summary.csv",
        "normalized_counter_summary.csv",
    )
    metadata_path = require_output(
        output_dir / "counter_source_metadata.csv",
        "counter_source_metadata.csv",
    )
    correlation_path = require_output(
        output_dir / "counter_correlation_ready.csv",
        "counter_correlation_ready.csv",
    )
    report_path = require_output(
        output_dir / "counter_claim_boundary_report.md",
        "counter_claim_boundary_report.md",
    )

    print("[demo-project-i] outputs")
    print(f"  - normalized summary: {display_path(normalized_path)}")
    print(f"  - source metadata: {display_path(metadata_path)}")
    print(f"  - correlation-ready table: {display_path(correlation_path)}")
    print(f"  - claim-boundary report: {display_path(report_path)}")
    print("[demo-project-i] Project I Profiler / Counter Correlation Interface PASS")
    print(
        "[demo-project-i] scope: sample-only schema smoke test; "
        "no real profiler capture; no hardware-counter validation; "
        "no silicon validation; no production signoff."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DemoError as error:
        print(f"[project-i] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
