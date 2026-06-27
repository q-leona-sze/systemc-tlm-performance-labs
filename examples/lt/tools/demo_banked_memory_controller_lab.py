#!/usr/bin/env python3

import argparse
import csv
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CPP_SOURCE_DIR = Path("examples/lt/banked_memory_controller_cpp")
CPP_BUILD_DIR = Path("build/examples/lt/banked_memory_controller_cpp")
DEFAULT_BINARY = CPP_BUILD_DIR / "banked_memory_controller"
DEFAULT_INPUT_DIR = Path("build/examples/lt/project_e_banked_memory_controller_inputs")
DEFAULT_OUTPUT_DIR = Path("examples/lt/results/project_e_banked_memory_controller")
REQUIRED_SUMMARY_FIELDS = (
    "workload",
    "bank_count",
    "queue_depth",
    "transactions",
    "avg_latency_ns",
    "p95_latency_ns",
    "p99_latency_ns",
    "max_latency_ns",
    "throughput_txn_per_us",
    "avg_queue_occupancy",
    "max_queue_occupancy",
    "bank_utilization_pct",
    "row_hit_ratio_pct",
    "stalled_or_rejected_transactions",
)
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
        description="Run the Project E banked memory controller queueing model demo."
    )
    parser.add_argument(
        "--binary",
        default=DEFAULT_BINARY,
        type=Path,
        help="C++ model binary. Defaults to build/examples/lt/banked_memory_controller_cpp/banked_memory_controller.",
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        type=Path,
        help="Generated normalized trace input directory under build/.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        type=Path,
        help="Project E output directory.",
    )
    parser.add_argument("--bank-count", default=4, type=int)
    parser.add_argument("--queue-depth", default=16, type=int)
    parser.add_argument("--address-mapping", default="word_interleave")
    parser.add_argument("--base-service-latency-ns", default=20.0, type=float)
    parser.add_argument("--row-hit-latency-ns", default=8.0, type=float)
    parser.add_argument("--row-miss-latency-ns", default=40.0, type=float)
    parser.add_argument("--row-size-bytes", default=64, type=int)
    parser.add_argument("--interleave-bytes", default=4, type=int)
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
        raise DemoError(f"refusing to remove broad path: {display_path(path)}")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def run_command(command):
    print("[demo-project-e] run: " + " ".join(str(part) for part in command))
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
            "C++ model binary not found: "
            f"{display_path(binary)}\n"
            "Build it with:\n"
            "  cmake -S examples/lt/banked_memory_controller_cpp -B build/examples/lt/banked_memory_controller_cpp\n"
            "  cmake --build build/examples/lt/banked_memory_controller_cpp"
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
        raise DemoError(f"C++ model binary not found after build: {display_path(binary)}")
    return binary


def format_hex(value):
    return f"0x{value:08X}"


def write_workload_trace(path, workload, count, timestamp_step_ns, address_fn, command_fn):
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
                    "timestamp_ns": f"{index * timestamp_step_ns:.3f}",
                    "initiator_id": "101",
                    "command": command_fn(index),
                    "address": format_hex(address_fn(index)),
                    "size_bytes": 4,
                }
            )


def generate_demo_inputs(input_dir):
    input_dir = repo_path(input_dir)
    remove_path(input_dir)
    input_dir.mkdir(parents=True, exist_ok=True)

    traces = []
    cases = (
        (
            "sequential_scan",
            96,
            64.0,
            lambda index: index * 4,
            lambda index: "WRITE" if index % 24 == 23 else "READ",
        ),
        (
            "stride_scan",
            96,
            32.0,
            lambda index: index * 16,
            lambda index: "WRITE" if index % 16 == 15 else "READ",
        ),
        (
            "hot_bank_stress",
            96,
            8.0,
            lambda index: index * 64,
            lambda index: "WRITE" if index % 8 == 7 else "READ",
        ),
    )
    for workload, count, timestamp_step, address_fn, command_fn in cases:
        trace_path = input_dir / f"{workload}.csv"
        write_workload_trace(
            trace_path,
            workload,
            count,
            timestamp_step,
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


def read_summary(summary_path):
    summary_path = repo_path(summary_path)
    if not summary_path.exists():
        raise DemoError(f"summary.csv not found: {display_path(summary_path)}")

    with summary_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        rows = list(reader)

    missing = [field for field in REQUIRED_SUMMARY_FIELDS if field not in fieldnames]
    if missing:
        raise DemoError("summary.csv missing fields: " + ", ".join(missing))
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


def row_by_workload(summary_rows, workload):
    for row in summary_rows:
        if row["workload"] == workload:
            return row
    raise DemoError(f"summary.csv missing workload: {workload}")


def write_comparison(output_dir, summary_rows, args):
    output_dir = repo_path(output_dir)
    comparison_path = output_dir / "comparison.md"
    headers = (
        "workload",
        "transactions",
        "accepted_transactions",
        "avg_latency_ns",
        "p95_latency_ns",
        "p99_latency_ns",
        "max_latency_ns",
        "avg_queue_occupancy",
        "max_queue_occupancy",
        "bank_utilization_pct",
        "row_hit_ratio_pct",
        "stalled_or_rejected_transactions",
    )
    sequential = row_by_workload(summary_rows, "sequential_scan")
    stride = row_by_workload(summary_rows, "stride_scan")
    hot = row_by_workload(summary_rows, "hot_bank_stress")

    lines = [
        "# Project E Banked Memory Controller Queueing Model Comparison",
        "",
        "Generated by `demo_banked_memory_controller_lab.py` from the C++ "
        "`banked_memory_controller` `summary.csv`.",
        "",
        "## Scope Boundary",
        "",
        "- Current: standalone C++ banked memory controller + queueing abstraction.",
        "- Supported: `bank_count`、`queue_depth`、per-bank `busy_until_ns`、"
        "address-to-bank mapping、row-buffer hit/miss、queue occupancy、tail "
        "latency、bank utilization、throughput 和 rejected transaction 统计。",
        "- Not Supported: SystemC kernel integration、gem5 live co-simulation、"
        "JEDEC DRAM timing、AXI / CHI / NoC protocol、cycle accuracy。",
        "- Future Work: 把同一抽象接到后续 AT/LT 对比或更丰富的 trace producer，"
        "但需要保持 `trace -> metrics -> summary.csv -> comparison.md` 链路可回归。",
        "",
        "## Model Knobs",
        "",
        f"- `bank_count = {args.bank_count}`",
        f"- `queue_depth = {args.queue_depth}`，按 bank 统计 outstanding requests，"
        "包含正在服务的 request。",
        f"- `address_mapping = {args.address_mapping}`",
        f"- `base_service_latency_ns = {args.base_service_latency_ns:.3f}`",
        f"- `row_hit_latency_ns = {args.row_hit_latency_ns:.3f}`",
        f"- `row_miss_latency_ns = {args.row_miss_latency_ns:.3f}`",
        f"- `row_size_bytes = {args.row_size_bytes}`",
        "",
        "## Summary",
        "",
    ]
    lines.extend(
        markdown_table(
            headers,
            (tuple(row.get(field, "") for field in headers) for row in summary_rows),
        )
    )
    lines.extend(
        [
            "",
            "## Engineering Interpretation",
            "",
            "- `sequential_scan` 的 latency tail 较稳：连续 4-byte access 在 "
            "`word_interleave` mapping 下轮转到多个 bank，并且同一 row 会被短时间复用，"
            f"本次 p99 latency 为 `{sequential['p99_latency_ns']} ns`，"
            f"max queue occupancy 为 `{sequential['max_queue_occupancy']}`。",
            "- `stride_scan` 用 16-byte stride 让更多 transaction 压到相同 bank，"
            "同时 row boundary 变化会引入 row miss；因此它展示的是 bank pressure 和 "
            "row-buffer behavior 对 tail latency 的趋势影响，"
            f"本次 p99 latency 为 `{stride['p99_latency_ns']} ns`。",
            "- `hot_bank_stress` 把请求集中到一个 hot bank，并用跨 row 地址制造持续 "
            "row miss。它会快速抬高 queue occupancy、p99/max latency，并在 queue full "
            "时产生 rejected transaction；"
            f"本次 p99 latency 为 `{hot['p99_latency_ns']} ns`，"
            f"max latency 为 `{hot['max_latency_ns']} ns`，"
            f"stalled/rejected 为 `{hot['stalled_or_rejected_transactions']}`。",
            "- 这个模型证明的是 trend-level memory subsystem behavior：bank mapping、"
            "queue depth 和 row locality 如何改变吞吐、tail latency 和 reject 风险。"
            "它不是 cycle-accurate DRAM，也不声称 AXI、CHI 或 NoC protocol compliance。",
            "",
        ]
    )
    comparison_path.write_text("\n".join(lines), encoding="utf-8")
    return comparison_path


def main():
    args = parse_args()
    if args.bank_count <= 0 or args.queue_depth <= 0:
        raise DemoError("--bank-count and --queue-depth must be positive")

    binary = ensure_binary(args.binary, args.no_build)
    output_dir = repo_path(args.output_dir)
    remove_path(output_dir)
    traces = generate_demo_inputs(args.input_dir)

    run_command(
        [
            binary,
            *trace_args(traces),
            "--output-dir",
            str(output_dir),
            "--bank-count",
            str(args.bank_count),
            "--queue-depth",
            str(args.queue_depth),
            "--address-mapping",
            args.address_mapping,
            "--base-service-latency-ns",
            str(args.base_service_latency_ns),
            "--row-hit-latency-ns",
            str(args.row_hit_latency_ns),
            "--row-miss-latency-ns",
            str(args.row_miss_latency_ns),
            "--row-size-bytes",
            str(args.row_size_bytes),
            "--interleave-bytes",
            str(args.interleave_bytes),
        ]
    )

    summary_rows = read_summary(output_dir / "summary.csv")
    comparison_path = write_comparison(output_dir, summary_rows, args)

    print("[demo-project-e] outputs")
    print(f"  - binary: {display_path(binary)}")
    print(f"  - generated inputs: {display_path(repo_path(args.input_dir))}")
    print(f"  - trace: {display_path(output_dir / 'trace.csv')}")
    print(f"  - summary: {display_path(output_dir / 'summary.csv')}")
    print(f"  - comparison: {display_path(comparison_path)}")
    print("[demo-project-e] Project E Banked Memory Controller Queueing MVP PASS")
    print(
        "[demo-project-e] scope: standalone C++ model; no SystemC kernel, "
        "no gem5 live co-simulation, no JEDEC DRAM timing, no AXI/CHI/NoC, "
        "no cycle-accuracy claim."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DemoError as error:
        print(f"[demo-project-e] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
