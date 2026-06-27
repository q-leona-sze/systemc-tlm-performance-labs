#!/usr/bin/env python3

import csv
import shlex
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = Path("examples/lt/results/trace_replay_lab")
RUNNER = Path("examples/lt/tools/run_trace_replay_lab.py")
SUMMARY_FIELDS = (
    "workload_name",
    "num_transactions",
    "avg_latency_ns",
    "p50_latency_ns",
    "p95_latency_ns",
    "p99_latency_ns",
    "max_latency_ns",
    "bank_conflict_ratio_pct",
    "throughput_txn_per_us",
)
EXPECTED_WORKLOADS = ("sample_sequential", "sample_stride")


class DemoError(Exception):
    pass


def repo_path(path):
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def display_path(path):
    path = Path(path)
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def run_command(command):
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as error:
        raise DemoError(
            f"failed to run command: {shlex.join(command)}\n"
            f"{error.__class__.__name__}: {error}"
        ) from error

    if result.stdout:
        print(result.stdout, end="")
    if result.returncode != 0:
        message = [
            f"command failed with exit code {result.returncode}:",
            shlex.join(command),
        ]
        if result.stderr:
            message.extend(("", "stderr:", result.stderr.strip()))
        raise DemoError("\n".join(message))


def read_summary(summary_path):
    if not summary_path.exists():
        raise DemoError(f"summary.csv not found: {display_path(summary_path)}")

    with summary_path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        if fieldnames != SUMMARY_FIELDS:
            raise DemoError(
                "summary.csv field order mismatch: " + ", ".join(fieldnames)
            )
        rows = list(reader)

    workloads = tuple(row.get("workload_name") for row in rows)
    if workloads != EXPECTED_WORKLOADS:
        raise DemoError(
            "summary.csv workload order mismatch: " + ", ".join(workloads)
        )

    for row in rows:
        for field in SUMMARY_FIELDS[1:]:
            if row.get(field) in (None, ""):
                raise DemoError(
                    f"summary.csv field {field} is empty for "
                    f"{row.get('workload_name')}"
                )
            try:
                float(row[field])
            except ValueError as error:
                raise DemoError(
                    f"summary.csv field {field} is not numeric for "
                    f"{row.get('workload_name')}"
                ) from error

    return rows


def read_trace(trace_path):
    if not trace_path.exists():
        raise DemoError(f"trace.csv not found: {display_path(trace_path)}")

    with trace_path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames or []
        for field in ("workload_name", "txn_id"):
            if field not in fieldnames:
                raise DemoError(f"trace.csv missing required field: {field}")
        rows = list(reader)

    if not rows:
        raise DemoError("trace.csv is empty")
    return rows


def metric(row, field):
    try:
        return float(row.get(field, ""))
    except ValueError:
        return None


def format_metric(value, suffix=""):
    if value is None:
        return "NA"
    return f"{value:.3f}{suffix}"


def print_conclusions(summary_rows):
    by_workload = {row["workload_name"]: row for row in summary_rows}
    sequential = by_workload["sample_sequential"]
    stride = by_workload["sample_stride"]
    seq_bank = metric(sequential, "bank_conflict_ratio_pct")
    stride_bank = metric(stride, "bank_conflict_ratio_pct")
    bank_delta = None
    if seq_bank is not None and stride_bank is not None:
        bank_delta = stride_bank - seq_bank

    print("[demo] Project B MVP conclusions")
    for workload in EXPECTED_WORKLOADS:
        row = by_workload[workload]
        print(
            "  - "
            f"{workload}: "
            f"transactions={row['num_transactions']}, "
            f"avg_latency={format_metric(metric(row, 'avg_latency_ns'), ' ns')}, "
            f"p99_latency={format_metric(metric(row, 'p99_latency_ns'), ' ns')}, "
            f"bank_conflict={format_metric(metric(row, 'bank_conflict_ratio_pct'), '%')}, "
            f"throughput={format_metric(metric(row, 'throughput_txn_per_us'), ' txn/us')}"
        )
    print(
        "  - stride bank conflict delta vs sequential: "
        f"{format_metric(bank_delta, ' pct')}"
    )


def main():
    output_dir = repo_path(DEFAULT_OUTPUT_DIR)
    run_command([sys.executable, str(repo_path(RUNNER)), "--output-dir", str(output_dir)])

    trace_path = output_dir / "trace.csv"
    summary_path = output_dir / "summary.csv"
    comparison_path = output_dir / "comparison.md"
    for path in (trace_path, summary_path, comparison_path):
        if not path.exists():
            raise DemoError(f"expected output missing: {display_path(path)}")

    trace_rows = read_trace(trace_path)
    summary_rows = read_summary(summary_path)

    print("[demo] outputs")
    print(f"  - trace: {display_path(trace_path)} ({len(trace_rows)} rows)")
    print(f"  - summary: {display_path(summary_path)}")
    print(f"  - comparison: {display_path(comparison_path)}")
    print_conclusions(summary_rows)
    print("[demo] Project B Normalized Trace Replay MVP PASS")
    print(
        "[demo] scope: normalized trace replay only; no gem5 dependency, "
        "no gem5-SystemC live co-simulation, no cycle-accuracy claim."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DemoError as error:
        print(f"[demo] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
