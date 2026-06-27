#!/usr/bin/env python3

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]

BUILDER = Path("examples/lt/tools/build_accuracy_validation_packet.py")
DEFAULT_CLAIM_MATRIX = Path("examples/lt/validation_packet/project_j_claim_matrix.csv")
DEFAULT_EVIDENCE_TABLE = Path("examples/lt/validation_packet/project_j_evidence_table.csv")
DEFAULT_UNSUPPORTED_CLAIMS = Path(
    "examples/lt/validation_packet/project_j_unsupported_claims.csv"
)
DEFAULT_OUTPUT_DIR = Path("examples/lt/results/project_j_accuracy_validation_packet")


class DemoError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run Project J accuracy validation packet demo."
    )
    parser.add_argument("--claim-matrix", default=DEFAULT_CLAIM_MATRIX, type=Path)
    parser.add_argument("--evidence-table", default=DEFAULT_EVIDENCE_TABLE, type=Path)
    parser.add_argument(
        "--unsupported-claims",
        default=DEFAULT_UNSUPPORTED_CLAIMS,
        type=Path,
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, type=Path)
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


def require_output(path, label):
    path = repo_path(path)
    if not path.exists():
        raise DemoError(f"{label} not found: {display_path(path)}")
    if not path.is_file():
        raise DemoError(f"{label} is not a file: {display_path(path)}")
    return path


def run_builder(args):
    command = [
        sys.executable,
        repo_path(BUILDER),
        "--claim-matrix",
        repo_path(args.claim_matrix),
        "--evidence-table",
        repo_path(args.evidence_table),
        "--unsupported-claims",
        repo_path(args.unsupported_claims),
        "--output-dir",
        repo_path(args.output_dir),
    ]
    print("[demo-project-j] run: " + " ".join(str(part) for part in command))
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
            "build_accuracy_validation_packet.py failed with exit code "
            f"{result.returncode}"
        )


def main():
    args = parse_args()
    output_dir = repo_path(args.output_dir)

    run_builder(args)

    summary_path = require_output(
        output_dir / "validation_packet_summary.csv",
        "validation_packet_summary.csv",
    )
    report_path = require_output(
        output_dir / "validation_packet_report.md",
        "validation_packet_report.md",
    )
    inventory_path = require_output(
        output_dir / "evidence_inventory.csv",
        "evidence_inventory.csv",
    )
    unsupported_report_path = require_output(
        output_dir / "unsupported_claims_report.md",
        "unsupported_claims_report.md",
    )

    print("[demo-project-j] outputs")
    print(f"  - summary: {display_path(summary_path)}")
    print(f"  - report: {display_path(report_path)}")
    print(f"  - evidence inventory: {display_path(inventory_path)}")
    print(f"  - unsupported claims report: {display_path(unsupported_report_path)}")
    print("Project J Accuracy Validation Report PASS")
    print(
        "scope: evidence packet only; no silicon validation, no production "
        "signoff, no full-system cycle accuracy claim."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DemoError as error:
        print(f"[project-j] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
