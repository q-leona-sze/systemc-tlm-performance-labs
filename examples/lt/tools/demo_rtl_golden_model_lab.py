#!/usr/bin/env python3

import argparse
import csv
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RTL_SOURCE_DIR = Path("examples/lt/rtl_banked_memory_controller")
RTL_BUILD_DIR = Path("build/examples/lt/rtl_banked_memory_controller")
DEFAULT_BINARY = RTL_BUILD_DIR / "rtl_banked_memory_controller"
DEFAULT_INPUT_DIR = Path("build/examples/lt/project_h_rtl_golden_model_inputs")
DEFAULT_OUTPUT_DIR = Path("examples/lt/results/project_h_verilator_rtl_golden_model")
CORRELATION_TOOL = Path("examples/lt/tools/correlate_model_rtl_summaries.py")
DANGEROUS_CLEAN_PATHS = {
    REPO_ROOT.resolve(),
    (REPO_ROOT / "build").resolve(),
    (REPO_ROOT / "examples").resolve(),
    (REPO_ROOT / "examples" / "lt").resolve(),
    (REPO_ROOT / "examples" / "lt" / "results").resolve(),
}


class DemoError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run Project H Verilator RTL golden model MVP."
    )
    parser.add_argument(
        "--binary",
        default=DEFAULT_BINARY,
        type=Path,
        help="Built Project H RTL simulator binary.",
    )
    parser.add_argument(
        "--trace",
        action="append",
        type=Path,
        help="Input normalized trace CSV. If omitted, deterministic demo traces are generated under build/.",
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        type=Path,
        help="Generated demo input trace directory.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        type=Path,
        help="Project H output directory.",
    )
    parser.add_argument("--cycle-time-ns", default=1.0, type=float)
    parser.add_argument("--bank-count", default=4, type=int)
    parser.add_argument("--interleave-bytes", default=64, type=int)
    parser.add_argument("--service-latency-cycles", default=10, type=int)
    parser.add_argument("--queue-depth", default=8, type=int)
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Do not build the Verilator simulator automatically.",
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
        raise DemoError(f"refusing to remove broad path: {display_path(path)}")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def run_command(command):
    print("[demo-project-h] run: " + " ".join(str(part) for part in command))
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


def require_verilator():
    if shutil.which("verilator") is None:
        raise DemoError(
            "verilator not found. Install Verilator or run on the Ubuntu validation environment."
        )


def ensure_binary(args):
    binary = repo_path(args.binary)
    if binary.exists():
        return binary

    if args.no_build:
        raise DemoError(
            "Project H RTL simulator binary not found: "
            f"{display_path(binary)}\n"
            "Build it with:\n"
            "  cmake -S examples/lt/rtl_banked_memory_controller -B build/examples/lt/rtl_banked_memory_controller\n"
            "  cmake --build build/examples/lt/rtl_banked_memory_controller"
        )

    run_command(
        [
            "cmake",
            "-S",
            str(RTL_SOURCE_DIR),
            "-B",
            str(RTL_BUILD_DIR),
            f"-DPROJECT_H_BANK_COUNT={args.bank_count}",
            f"-DPROJECT_H_INTERLEAVE_BYTES={args.interleave_bytes}",
            f"-DPROJECT_H_SERVICE_LATENCY_CYCLES={args.service_latency_cycles}",
            f"-DPROJECT_H_QUEUE_DEPTH={args.queue_depth}",
        ]
    )
    run_command(["cmake", "--build", str(RTL_BUILD_DIR)])
    if not binary.exists():
        raise DemoError(
            f"Project H RTL simulator binary not found after build: {display_path(binary)}"
        )
    return binary


def format_hex(value):
    return f"0x{value:016X}"


def write_workload_trace(
    path,
    workload,
    count,
    issue_step_cycles,
    cycle_time_ns,
    address_fn,
    command_fn,
):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=(
                "workload_name",
                "txn_id",
                "timestamp_ns",
                "initiator_id",
                "command",
                "address",
                "size_bytes",
            ),
        )
        writer.writeheader()
        for index in range(count):
            writer.writerow(
                {
                    "workload_name": workload,
                    "txn_id": index + 1,
                    "timestamp_ns": f"{index * issue_step_cycles * cycle_time_ns:.9f}",
                    "initiator_id": "101",
                    "command": command_fn(index),
                    "address": format_hex(address_fn(index)),
                    "size_bytes": 4,
                }
            )


def generate_demo_inputs(input_dir, cycle_time_ns):
    input_dir = repo_path(input_dir)
    remove_path(input_dir)
    input_dir.mkdir(parents=True, exist_ok=True)

    cases = (
        (
            "sequential_scan",
            64,
            12,
            lambda index: index * 64,
            lambda index: "WRITE" if index % 16 == 15 else "READ",
        ),
        (
            "stride_scan",
            64,
            6,
            lambda index: index * 256,
            lambda index: "WRITE" if index % 16 == 15 else "READ",
        ),
        (
            "hot_bank_stress",
            64,
            1,
            lambda index: index * 256,
            lambda index: "WRITE" if index % 8 == 7 else "READ",
        ),
    )

    traces = []
    for workload, count, step, address_fn, command_fn in cases:
        trace_path = input_dir / f"{workload}.csv"
        write_workload_trace(
            trace_path,
            workload,
            count,
            step,
            cycle_time_ns,
            address_fn,
            command_fn,
        )
        traces.append(trace_path)
    return traces


def trace_args(traces):
    args = []
    for trace in traces:
        args.extend(("--trace", str(trace)))
    return args


def require_output(path, label):
    path = repo_path(path)
    if not path.exists():
        raise DemoError(f"{label} not found: {display_path(path)}")
    return path


def read_correlation(path):
    path = require_output(path, "model_vs_rtl_correlation.csv")
    with path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))
    if not rows:
        raise DemoError(f"model_vs_rtl_correlation.csv is empty: {display_path(path)}")
    return rows


def main():
    args = parse_args()
    if args.cycle_time_ns <= 0:
        raise DemoError("--cycle-time-ns must be positive")
    if (
        args.bank_count <= 0
        or args.interleave_bytes <= 0
        or args.service_latency_cycles <= 0
        or args.queue_depth <= 0
    ):
        raise DemoError(
            "--bank-count, --interleave-bytes, --service-latency-cycles, and --queue-depth must be positive"
        )

    require_verilator()
    binary = ensure_binary(args)
    output_dir = repo_path(args.output_dir)
    remove_path(output_dir)

    traces = (
        [repo_path(trace) for trace in args.trace]
        if args.trace
        else generate_demo_inputs(args.input_dir, args.cycle_time_ns)
    )

    run_command(
        [
            binary,
            *trace_args(traces),
            "--output-dir",
            str(output_dir),
            "--cycle-time-ns",
            str(args.cycle_time_ns),
            "--bank-count",
            str(args.bank_count),
            "--interleave-bytes",
            str(args.interleave_bytes),
            "--service-latency-cycles",
            str(args.service_latency_cycles),
            "--queue-depth",
            str(args.queue_depth),
        ]
    )

    require_output(output_dir / "rtl_trace.csv", "rtl_trace.csv")
    require_output(output_dir / "rtl_summary.csv", "rtl_summary.csv")
    require_output(output_dir / "model_summary_aligned.csv", "model_summary_aligned.csv")

    run_command(
        [
            sys.executable,
            CORRELATION_TOOL,
            "--model-summary",
            output_dir / "model_summary_aligned.csv",
            "--rtl-summary",
            output_dir / "rtl_summary.csv",
            "--output-dir",
            output_dir,
        ]
    )

    require_output(output_dir / "error_budget.csv", "error_budget.csv")
    require_output(output_dir / "correlation_report.md", "correlation_report.md")
    rows = read_correlation(output_dir / "model_vs_rtl_correlation.csv")
    failed = [row for row in rows if row.get("status") == "fail"]
    if failed:
        raise DemoError(f"model-vs-RTL correlation has {len(failed)} failed row(s)")

    print("[demo-project-h] outputs")
    print(f"  - binary: {display_path(binary)}")
    if not args.trace:
        print(f"  - generated inputs: {display_path(repo_path(args.input_dir))}")
    print(f"  - rtl_trace: {display_path(output_dir / 'rtl_trace.csv')}")
    print(f"  - rtl_summary: {display_path(output_dir / 'rtl_summary.csv')}")
    print(
        f"  - model_summary_aligned: {display_path(output_dir / 'model_summary_aligned.csv')}"
    )
    print(
        f"  - correlation: {display_path(output_dir / 'model_vs_rtl_correlation.csv')}"
    )
    print(f"  - error_budget: {display_path(output_dir / 'error_budget.csv')}")
    print(f"  - report: {display_path(output_dir / 'correlation_report.md')}")
    print("[demo-project-h] Project H Verilator RTL Golden Model MVP PASS")
    print(
        "[demo-project-h] scope: local banked memory controller RTL reference only; "
        "no full SoC, no AXI/CHI, no gem5-Verilator live co-simulation, "
        "no silicon validation, no production signoff, no full-system cycle accuracy."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DemoError as error:
        print(f"[project-h] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
