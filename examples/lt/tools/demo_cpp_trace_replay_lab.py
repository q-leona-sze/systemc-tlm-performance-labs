#!/usr/bin/env python3

import argparse
import csv
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CPP_SOURCE_DIR = Path("examples/lt/replay_cpp")
CPP_BUILD_DIR = Path("build/examples/lt/replay_cpp")
DEFAULT_BINARY = CPP_BUILD_DIR / "replay_cpp"
DEFAULT_OUTPUT_DIR = Path("examples/lt/results/cpp_trace_replay_lab")
DEFAULT_PYTHON_OUTPUT_DIR = Path("examples/lt/results/cpp_trace_replay_lab_python")
PYTHON_REPLAY = Path("examples/lt/tools/run_trace_replay_lab.py")
COMPARE_TOOL = Path("examples/lt/tools/compare_python_cpp_replay_outputs.py")
DEFAULT_TRACES = (
    Path("examples/lt/traces/sample_sequential_trace.csv"),
    Path("examples/lt/traces/sample_stride_trace.csv"),
    Path("examples/lt/traces/gem5_sequential_trace.csv"),
    Path("examples/lt/traces/gem5_stride_trace.csv"),
)
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
        description="Run the Project D standalone C++ trace replay MVP demo."
    )
    parser.add_argument(
        "--binary",
        default=DEFAULT_BINARY,
        type=Path,
        help="C++ replay binary. Defaults to build/examples/lt/replay_cpp/replay_cpp.",
    )
    parser.add_argument(
        "--trace",
        action="append",
        default=[],
        type=Path,
        help="Normalized trace CSV. Can be repeated. Defaults to Project B and C MVP traces.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        type=Path,
        help="C++ output directory.",
    )
    parser.add_argument(
        "--python-output-dir",
        default=DEFAULT_PYTHON_OUTPUT_DIR,
        type=Path,
        help="Python baseline output directory.",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Do not build the C++ binary automatically.",
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
    print("[demo-cpp] run: " + " ".join(str(part) for part in command))
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


def ensure_binary(binary, no_build):
    binary = repo_path(binary)
    if binary.exists():
        return binary

    if no_build:
        raise DemoError(
            "C++ replay binary not found: "
            f"{display_path(binary)}\n"
            "Build it with:\n"
            "  cmake -S examples/lt/replay_cpp -B build/examples/lt/replay_cpp\n"
            "  cmake --build build/examples/lt/replay_cpp"
        )

    run_command(
        [
            "cmake",
            "-S",
            str(CPP_SOURCE_DIR),
            "-B",
            str(CPP_BUILD_DIR),
        ]
    )
    run_command(["cmake", "--build", str(CPP_BUILD_DIR)])
    if not binary.exists():
        raise DemoError(f"C++ replay binary not found after build: {display_path(binary)}")
    return binary


def trace_args(traces):
    args = []
    for trace in traces:
        args.extend(("--trace", str(trace)))
    return args


def read_summary(summary_path):
    summary_path = repo_path(summary_path)
    if not summary_path.exists():
        raise DemoError(f"summary.csv not found: {display_path(summary_path)}")

    with summary_path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        rows = list(reader)

    if fieldnames != SUMMARY_FIELDS:
        raise DemoError(
            "summary.csv field order mismatch:\n"
            f"  expected: {', '.join(SUMMARY_FIELDS)}\n"
            f"  got:      {', '.join(fieldnames)}"
        )
    if not rows:
        raise DemoError("summary.csv is empty")
    return rows


def markdown_cell(value):
    return str(value).replace("\n", " ").replace("|", "\\|")


def markdown_table(headers, rows):
    lines = [
        "| " + " | ".join(markdown_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(markdown_cell(value) for value in row) + " |")
    return lines


def write_comparison(output_dir, summary_rows):
    output_dir = repo_path(output_dir)
    comparison_path = output_dir / "comparison.md"
    lines = [
        "# Project D C++ Trace Replay MVP Comparison",
        "",
        "Generated by `demo_cpp_trace_replay_lab.py` from the C++ `summary.csv`.",
        "",
        "This report covers standalone C++ normalized trace replay. It does not "
        "connect to the SystemC kernel, does not run gem5 live co-simulation, "
        "and does not claim cycle accuracy, cache, DRAM, AXI, CHI, or NoC "
        "protocol modeling.",
        "",
        "## Replay Cases",
        "",
    ]
    lines.extend(
        markdown_table(
            SUMMARY_FIELDS,
            (tuple(row[field] for field in SUMMARY_FIELDS) for row in summary_rows),
        )
    )
    lines.extend(
        [
            "",
            "## Engineering Interpretation",
            "",
            "- C++ owns normalized trace parsing, MVP latency modeling, minimal "
            "bank-conflict accounting, and summary metric generation.",
            "- Python remains orchestration and reporting glue for the MVP.",
            "- The first validation target is Python vs C++ metric equivalence, "
            "not increased model fidelity.",
            "",
        ]
    )
    comparison_path.write_text("\n".join(lines), encoding="utf-8")
    return comparison_path


def main():
    args = parse_args()
    traces = args.trace or list(DEFAULT_TRACES)
    for trace in traces:
        if not repo_path(trace).exists():
            raise DemoError(f"trace not found: {display_path(repo_path(trace))}")

    binary = ensure_binary(args.binary, args.no_build)
    cpp_output_dir = repo_path(args.output_dir)
    python_output_dir = repo_path(args.python_output_dir)
    remove_path(cpp_output_dir)
    remove_path(python_output_dir)

    run_command(
        [
            binary,
            *trace_args(traces),
            "--output-dir",
            str(cpp_output_dir),
        ]
    )
    run_command(
        [
            sys.executable,
            PYTHON_REPLAY,
            *trace_args(traces),
            "--output-dir",
            str(python_output_dir),
        ]
    )
    run_command(
        [
            sys.executable,
            COMPARE_TOOL,
            "--python-output",
            str(python_output_dir),
            "--cpp-output",
            str(cpp_output_dir),
        ]
    )

    summary_rows = read_summary(cpp_output_dir / "summary.csv")
    comparison_path = write_comparison(cpp_output_dir, summary_rows)

    print("[demo-cpp] outputs")
    print(f"  - binary: {display_path(binary)}")
    print(f"  - c++ trace: {display_path(cpp_output_dir / 'trace.csv')}")
    print(f"  - c++ summary: {display_path(cpp_output_dir / 'summary.csv')}")
    print(f"  - comparison: {display_path(comparison_path)}")
    print(f"  - python baseline: {display_path(python_output_dir)}")
    print("[demo-cpp] Project D Standalone C++ Trace Replay MVP PASS")
    print(
        "[demo-cpp] scope: standalone C++ replay engine; no SystemC kernel, "
        "no gem5 live co-simulation, no cycle-accuracy claim."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DemoError as error:
        print(f"[demo-cpp] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
