#!/usr/bin/env python3

import argparse
import csv
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CORRELATION_TOOL = Path("examples/lt/tools/gem5_stats_correlation.py")
DEFAULT_OUTPUT_DIR = Path("examples/lt/results/project_f_gem5_stats_correlation")
DEFAULT_SEQUENTIAL_STATS = Path(
    "examples/lt/results/gem5_se_trace_extraction/sequential/stats.txt"
)
DEFAULT_STRIDE_STATS = Path(
    "examples/lt/results/gem5_se_trace_extraction/stride/stats.txt"
)
DEFAULT_PROJECT_E_SUMMARY = Path(
    "examples/lt/results/project_e_banked_memory_controller/summary.csv"
)
DANGEROUS_CLEAN_PATHS = {
    REPO_ROOT.resolve(),
    (REPO_ROOT / "examples").resolve(),
    (REPO_ROOT / "examples" / "lt").resolve(),
    (REPO_ROOT / "examples" / "lt" / "results").resolve(),
}


class DemoError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the Project F gem5 stats trend-correlation report demo."
    )
    parser.add_argument(
        "--sequential-stats",
        default=DEFAULT_SEQUENTIAL_STATS,
        type=Path,
        help="gem5 SE stats.txt for the sequential workload.",
    )
    parser.add_argument(
        "--stride-stats",
        default=DEFAULT_STRIDE_STATS,
        type=Path,
        help="gem5 SE stats.txt for the stride workload.",
    )
    parser.add_argument(
        "--replay-summary",
        type=Path,
        help="Optional explicit replay summary.csv.",
    )
    parser.add_argument(
        "--project-e-summary",
        default=DEFAULT_PROJECT_E_SUMMARY,
        type=Path,
        help="Project E summary.csv used for queueing-model columns.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        type=Path,
        help="Project F output directory.",
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


def remove_path(path):
    path = repo_path(path)
    if not path.exists():
        return
    resolved = path.resolve()
    if resolved in DANGEROUS_CLEAN_PATHS:
        raise DemoError(f"refusing to remove broad output path: {display_path(path)}")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def run_command(command):
    print(
        "[demo-project-f] run: " + " ".join(str(part) for part in command),
        flush=True,
    )
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
    if result.returncode != 0:
        message = [
            f"command failed with exit code {result.returncode}:",
            " ".join(str(part) for part in command),
        ]
        if result.stderr:
            message.extend(("", "stderr:", result.stderr.strip()))
        raise DemoError("\n".join(message))
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)


def read_summary(summary_path):
    summary_path = repo_path(summary_path)
    if not summary_path.exists():
        raise DemoError(f"correlation_summary.csv not found: {display_path(summary_path)}")
    with summary_path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))
    if not rows:
        raise DemoError(f"correlation_summary.csv is empty: {display_path(summary_path)}")
    return rows


def row_by_workload(rows, workload):
    for row in rows:
        if row.get("workload") == workload:
            return row
    raise DemoError(f"correlation_summary.csv missing workload: {workload}")


def main():
    args = parse_args()
    output_dir = repo_path(args.output_dir)
    remove_path(output_dir)

    command = [
        sys.executable,
        CORRELATION_TOOL,
        "--sequential-stats",
        args.sequential_stats,
        "--stride-stats",
        args.stride_stats,
        "--project-e-summary",
        args.project_e_summary,
        "--output-dir",
        args.output_dir,
    ]
    if args.replay_summary:
        command.extend(("--replay-summary", args.replay_summary))
    run_command(command)

    summary_path = output_dir / "correlation_summary.csv"
    report_path = output_dir / "correlation_report.md"
    rows = read_summary(summary_path)
    sequential = row_by_workload(rows, "sequential")
    stride = row_by_workload(rows, "stride")

    print("[demo-project-f] outputs")
    print(f"  - summary: {display_path(summary_path)}")
    print(f"  - report: {display_path(report_path)}")
    print("[demo-project-f] trend snapshot")
    print(
        "  - replay avg latency: "
        f"sequential={sequential.get('replay_avg_latency_ns', '')} ns, "
        f"stride={stride.get('replay_avg_latency_ns', '')} ns"
    )
    print(
        "  - replay bank conflict: "
        f"sequential={sequential.get('bank_conflict_ratio_pct', '')}%, "
        f"stride={stride.get('bank_conflict_ratio_pct', '')}%"
    )
    print(
        "  - Project E queue occupancy: "
        f"sequential={sequential.get('project_e_avg_queue_occupancy', '')}, "
        f"stride={stride.get('project_e_avg_queue_occupancy', '')}"
    )
    print("[demo-project-f] Project F Gem5 Stats Trend Correlation MVP PASS")
    print(
        "[demo-project-f] scope: qualitative trend report only; no live "
        "gem5-SystemC co-simulation, no cycle-accuracy claim, no RTL/silicon/profiler "
        "correlation claim; timestamp_ns remains normalized issue-time."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DemoError as error:
        print(f"[demo-project-f] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
