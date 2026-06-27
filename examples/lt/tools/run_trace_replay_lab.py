#!/usr/bin/env python3

import argparse
import csv
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TRACES = (
    Path("examples/lt/traces/sample_sequential_trace.csv"),
    Path("examples/lt/traces/sample_stride_trace.csv"),
)
DEFAULT_OUTPUT_DIR = Path("examples/lt/results/trace_replay_lab")

REQUIRED_FIELDS = (
    "workload_name",
    "txn_id",
    "timestamp_ns",
    "initiator_id",
    "command",
    "address",
    "size_bytes",
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
TRACE_FIELDS = (
    "workload_name",
    "txn_id",
    "timestamp_ns",
    "initiator_id",
    "command",
    "address",
    "size_bytes",
    "target_id",
    "decoded_port",
    "masked_address",
    "data_length",
    "data",
    "start_time_ns",
    "delay_ns",
    "end_time_ns",
    "response_status",
    "request_time_ns",
    "bus_grant_time_ns",
    "queue_delay_ns",
    "target_service_delay_ns",
    "total_delay_ns",
    "target_busy_until_ns",
    "bank_id",
    "bank_conflict",
    "bank_conflict_delay_ns",
    "source_trace",
)

MVP_INITIATOR_ID = "101"
MVP_COMMAND = "READ"
MVP_SIZE_BYTES = 4
TARGET_SERVICE_DELAY_NS = 100.0
BANK_CONFLICT_DELAY_NS = 20.0
DANGEROUS_CLEAN_PATHS = {
    REPO_ROOT.resolve(),
    (REPO_ROOT / "examples").resolve(),
    (REPO_ROOT / "examples" / "lt").resolve(),
    (REPO_ROOT / "examples" / "lt" / "results").resolve(),
}


class TraceReplayError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the Project B normalized trace replay MVP."
    )
    parser.add_argument(
        "--trace",
        action="append",
        default=[],
        type=Path,
        help=(
            "Normalized trace CSV. Can be repeated. Defaults to the two MVP "
            "sample traces."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        type=Path,
        help=(
            "Output directory. Defaults to "
            "examples/lt/results/trace_replay_lab."
        ),
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate input trace schema and MVP constraints without replay.",
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


def parse_number(value, field, row_number):
    text = str(value).strip()
    if not text:
        raise TraceReplayError(f"row {row_number}: {field} is empty")
    try:
        return float(text)
    except ValueError as error:
        raise TraceReplayError(
            f"row {row_number}: {field} is not numeric: {value}"
        ) from error


def parse_int_value(value, field, row_number):
    text = str(value).strip()
    if not text:
        raise TraceReplayError(f"row {row_number}: {field} is empty")
    try:
        return int(text, 0)
    except ValueError as error:
        raise TraceReplayError(
            f"row {row_number}: {field} is not an integer: {value}"
        ) from error


def sort_key(row):
    txn_id = row["txn_id"]
    try:
        txn_key = (0, int(txn_id, 0))
    except ValueError:
        txn_key = (1, txn_id)
    return (row["timestamp_ns_value"], txn_key)


def load_trace(trace_path):
    trace_path = repo_path(trace_path)
    if not trace_path.exists():
        raise TraceReplayError(f"trace not found: {display_path(trace_path)}")

    with trace_path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames or []
        missing = [field for field in REQUIRED_FIELDS if field not in fieldnames]
        if missing:
            raise TraceReplayError(
                f"{display_path(trace_path)} missing fields: "
                + ", ".join(missing)
            )

        rows = []
        for row_number, row in enumerate(reader, start=2):
            normalized = {field: (row.get(field) or "").strip() for field in REQUIRED_FIELDS}
            normalized["_row_number"] = row_number
            normalized["_source_trace"] = display_path(trace_path)

            workload_name = normalized["workload_name"]
            if not workload_name:
                raise TraceReplayError(f"row {row_number}: workload_name is empty")

            if not normalized["txn_id"]:
                raise TraceReplayError(f"row {row_number}: txn_id is empty")

            timestamp_ns = parse_number(
                normalized["timestamp_ns"], "timestamp_ns", row_number
            )
            if timestamp_ns < 0:
                raise TraceReplayError(f"row {row_number}: timestamp_ns is negative")
            normalized["timestamp_ns_value"] = timestamp_ns

            if normalized["initiator_id"] != MVP_INITIATOR_ID:
                raise TraceReplayError(
                    f"row {row_number}: MVP only supports initiator_id={MVP_INITIATOR_ID}"
                )

            command = normalized["command"].upper()
            if command != MVP_COMMAND:
                raise TraceReplayError(
                    f"row {row_number}: MVP only supports command={MVP_COMMAND}"
                )
            normalized["command"] = command

            address = parse_int_value(normalized["address"], "address", row_number)
            if address < 0:
                raise TraceReplayError(f"row {row_number}: address is negative")
            normalized["address_value"] = address

            size_bytes = parse_int_value(
                normalized["size_bytes"], "size_bytes", row_number
            )
            if size_bytes != MVP_SIZE_BYTES:
                raise TraceReplayError(
                    f"row {row_number}: MVP only supports size_bytes={MVP_SIZE_BYTES}"
                )
            normalized["size_bytes_value"] = size_bytes

            decoded_port = address >> 28
            if decoded_port not in (0, 1):
                raise TraceReplayError(
                    f"row {row_number}: address decodes outside LT MVP targets"
                )
            normalized["decoded_port"] = decoded_port
            normalized["target_id"] = 201 + decoded_port
            normalized["masked_address"] = address & 0x0FFFFFFF

            rows.append(normalized)

    if not rows:
        raise TraceReplayError(f"{display_path(trace_path)} has no transactions")

    workload_names = {row["workload_name"] for row in rows}
    if len(workload_names) != 1:
        raise TraceReplayError(
            f"{display_path(trace_path)} must contain exactly one workload_name"
        )

    txn_ids = set()
    for row in rows:
        key = row["txn_id"]
        if key in txn_ids:
            raise TraceReplayError(
                f"{display_path(trace_path)} has duplicate txn_id: {key}"
            )
        txn_ids.add(key)

    return sorted(rows, key=sort_key)


def format_number(value):
    return f"{value:.3f}"


def format_time(value):
    return f"{value:.3f}"


def format_hex(value, width=16):
    return f"0x{value:0{width}X}"


def bank_id_for_address(masked_address):
    return int((masked_address // MVP_SIZE_BYTES) % 4)


def replay_rows(input_rows):
    last_bank_by_target = {}
    output_rows = []

    for row in input_rows:
        decoded_port = row["decoded_port"]
        masked_address = row["masked_address"]
        bank_id = bank_id_for_address(masked_address)
        bank_conflict = last_bank_by_target.get(decoded_port) == bank_id
        last_bank_by_target[decoded_port] = bank_id

        bank_delay = BANK_CONFLICT_DELAY_NS if bank_conflict else 0.0
        start_time_ns = row["timestamp_ns_value"]
        queue_delay_ns = 0.0
        target_service_delay_ns = TARGET_SERVICE_DELAY_NS
        total_delay_ns = queue_delay_ns + target_service_delay_ns + bank_delay
        end_time_ns = start_time_ns + total_delay_ns

        output_rows.append(
            {
                "workload_name": row["workload_name"],
                "txn_id": row["txn_id"],
                "timestamp_ns": format_time(row["timestamp_ns_value"]),
                "initiator_id": row["initiator_id"],
                "command": row["command"],
                "address": format_hex(row["address_value"]),
                "size_bytes": str(row["size_bytes_value"]),
                "target_id": str(row["target_id"]),
                "decoded_port": str(decoded_port),
                "masked_address": format_hex(masked_address),
                "data_length": str(row["size_bytes_value"]),
                "data": "0x00000000",
                "start_time_ns": format_time(start_time_ns),
                "delay_ns": format_time(total_delay_ns),
                "end_time_ns": format_time(end_time_ns),
                "response_status": "TLM_OK_RESPONSE",
                "request_time_ns": format_time(start_time_ns),
                "bus_grant_time_ns": format_time(start_time_ns),
                "queue_delay_ns": format_time(queue_delay_ns),
                "target_service_delay_ns": format_time(target_service_delay_ns),
                "total_delay_ns": format_time(total_delay_ns),
                "target_busy_until_ns": format_time(end_time_ns),
                "bank_id": str(bank_id),
                "bank_conflict": "1" if bank_conflict else "0",
                "bank_conflict_delay_ns": format_time(bank_delay),
                "source_trace": row["_source_trace"],
            }
        )

    return output_rows


def average(values):
    return sum(values) / len(values) if values else 0.0


def percentile(values, percentile_value):
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = int(round((percentile_value / 100.0) * (len(ordered) - 1)))
    rank = max(0, min(rank, len(ordered) - 1))
    return ordered[rank]


def metric_float(row, field):
    return float(row[field])


def summary_for_workload(rows):
    if not rows:
        raise TraceReplayError("cannot summarize empty replay output")

    workload_name = rows[0]["workload_name"]
    if {row["workload_name"] for row in rows} != {workload_name}:
        raise TraceReplayError("summary input contains mixed workloads")

    latencies = [metric_float(row, "total_delay_ns") for row in rows]
    starts = [metric_float(row, "start_time_ns") for row in rows]
    ends = [metric_float(row, "end_time_ns") for row in rows]
    bank_conflicts = sum(1 for row in rows if row["bank_conflict"] == "1")
    num_transactions = len(rows)
    replay_window_ns = max(ends) - min(starts)
    throughput = 0.0
    if replay_window_ns > 0.0:
        throughput = num_transactions / (replay_window_ns / 1000.0)

    return {
        "workload_name": workload_name,
        "num_transactions": str(num_transactions),
        "avg_latency_ns": format_number(average(latencies)),
        "p50_latency_ns": format_number(percentile(latencies, 50)),
        "p95_latency_ns": format_number(percentile(latencies, 95)),
        "p99_latency_ns": format_number(percentile(latencies, 99)),
        "max_latency_ns": format_number(max(latencies)),
        "bank_conflict_ratio_pct": format_number(
            100.0 * bank_conflicts / num_transactions
        ),
        "throughput_txn_per_us": format_number(throughput),
    }


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


def delta(row, baseline, field):
    return float(row[field]) - float(baseline[field])


def write_trace_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=TRACE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_comparison(path, summary_rows):
    first = summary_rows[0] if summary_rows else None
    second = summary_rows[1] if len(summary_rows) > 1 else None
    first_name = first["workload_name"] if first else "first_workload"
    second_name = second["workload_name"] if second else "second_workload"

    lines = [
        "# Project B Normalized Trace Replay MVP Comparison",
        "",
        "Generated from `summary.csv` by `run_trace_replay_lab.py`.",
        "",
        "This MVP replays normalized memory traces through the LT performance "
        "lab's minimal latency and bank-conflict abstraction. The replay step "
        "does not run gem5; gem5-derived inputs are consumed only as files. "
        "This is not gem5-SystemC live co-simulation.",
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
    lines.extend(["", f"## {first_name} vs {second_name}", ""])

    if first is None or second is None:
        lines.append(
            "At least two workload summaries are required for delta comparison; "
            "deltas unavailable."
        )
    else:
        lines.extend(
            markdown_table(
                (
                    "metric",
                    first_name,
                    second_name,
                    "delta_second_minus_first",
                ),
                (
                    (
                        "avg_latency_ns",
                        first["avg_latency_ns"],
                        second["avg_latency_ns"],
                        format_number(delta(second, first, "avg_latency_ns")),
                    ),
                    (
                        "p99_latency_ns",
                        first["p99_latency_ns"],
                        second["p99_latency_ns"],
                        format_number(delta(second, first, "p99_latency_ns")),
                    ),
                    (
                        "bank_conflict_ratio_pct",
                        first["bank_conflict_ratio_pct"],
                        second["bank_conflict_ratio_pct"],
                        format_number(
                            delta(second, first, "bank_conflict_ratio_pct")
                        ),
                    ),
                    (
                        "throughput_txn_per_us",
                        first["throughput_txn_per_us"],
                        second["throughput_txn_per_us"],
                        format_number(
                            delta(second, first, "throughput_txn_per_us")
                        ),
                    ),
                ),
            )
        )

        lines.extend(
            [
                "",
                "## Engineering Interpretation",
                "",
                f"- This comparison reports `{second_name}` minus "
                f"`{first_name}` using the first two traces in command-line "
                "order.",
                "- Workload names are labels from the normalized traces; the "
                "replay tool does not require specific names.",
                "- `timestamp_ns` is a normalized issue-time and ordering hint; "
                "it is not gem5 timing and not cycle timing.",
                "- This report is a trace replay MVP, not a cache, DRAM, AXI, "
                "CHI, NoC, GPU, or gem5 co-simulation result.",
            ]
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def remove_output_dir(path):
    if not path.exists():
        return
    resolved = path.resolve()
    if resolved in DANGEROUS_CLEAN_PATHS:
        raise TraceReplayError(f"refusing to remove broad output path: {path}")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def validate_summary_rows(rows):
    if not rows:
        raise TraceReplayError("summary must contain at least one workload")

    for row in rows:
        if int(row["num_transactions"]) <= 0:
            raise TraceReplayError(f"{row['workload_name']} has no transactions")
        p50 = float(row["p50_latency_ns"])
        p95 = float(row["p95_latency_ns"])
        p99 = float(row["p99_latency_ns"])
        max_latency = float(row["max_latency_ns"])
        if not (p50 <= p95 <= p99 <= max_latency):
            raise TraceReplayError(
                f"{row['workload_name']} percentile ordering failed"
            )
        bank_ratio = float(row["bank_conflict_ratio_pct"])
        if not 0.0 <= bank_ratio <= 100.0:
            raise TraceReplayError(
                f"{row['workload_name']} bank_conflict_ratio_pct out of range"
            )
        if float(row["throughput_txn_per_us"]) < 0.0:
            raise TraceReplayError(
                f"{row['workload_name']} throughput_txn_per_us is negative"
            )


def main():
    args = parse_args()
    trace_paths = args.trace or list(DEFAULT_TRACES)

    loaded_traces = []
    for trace_path in trace_paths:
        rows = load_trace(trace_path)
        loaded_traces.append((repo_path(trace_path), rows))
        print(
            "[validate] OK "
            f"{display_path(repo_path(trace_path))}: "
            f"workload={rows[0]['workload_name']} rows={len(rows)}"
        )

    if args.validate_only:
        print("[validate] Project B normalized trace schema PASS")
        return 0

    if len(loaded_traces) < 2:
        raise TraceReplayError("MVP replay expects at least two trace inputs")

    output_dir = repo_path(args.output_dir)
    remove_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_output_rows = []
    summary_rows = []
    for _, input_rows in loaded_traces:
        output_rows = replay_rows(input_rows)
        all_output_rows.extend(output_rows)
        summary_rows.append(summary_for_workload(output_rows))

    validate_summary_rows(summary_rows)

    trace_output = output_dir / "trace.csv"
    summary_output = output_dir / "summary.csv"
    comparison_output = output_dir / "comparison.md"
    write_trace_csv(trace_output, all_output_rows)
    write_summary_csv(summary_output, summary_rows)
    write_comparison(comparison_output, summary_rows)

    print("[replay] outputs")
    print(f"  - trace: {display_path(trace_output)}")
    print(f"  - summary: {display_path(summary_output)}")
    print(f"  - comparison: {display_path(comparison_output)}")
    print("[replay] Project B normalized trace replay PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TraceReplayError as error:
        print(f"[replay] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
