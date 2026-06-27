#!/usr/bin/env python3

import argparse
import csv
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MARKER = "PROJECT_C_MEM"
NORMALIZED_FIELDS = (
    "workload_name",
    "txn_id",
    "timestamp_ns",
    "initiator_id",
    "command",
    "address",
    "size_bytes",
    "pc",
    "symbol",
    "source",
)
SAMPLE_PATTERNS = ("sequential", "stride")


class ConvertError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Convert Project C gem5 SE workload markers into the Project B "
            "normalized memory trace CSV schema."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        help=(
            "gem5 SE simout or text file containing PROJECT_C_MEM markers. "
            "Required unless --sample-pattern is used."
        ),
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--workload-name",
        help="Override workload_name in the normalized CSV.",
    )
    parser.add_argument("--initiator-id", default="101")
    parser.add_argument("--timestamp-step-ns", default=100.0, type=float)
    parser.add_argument("--size-bytes", default=4, type=int)
    parser.add_argument("--command-filter", default="READ")
    parser.add_argument(
        "--address-normalize",
        default="zero_based",
        choices=("zero_based", "none"),
    )
    parser.add_argument(
        "--source",
        default="gem5_se_simout",
        help="Value for the normalized source column.",
    )
    parser.add_argument(
        "--sample-pattern",
        choices=SAMPLE_PATTERNS,
        help=(
            "Generate an expected-format sample trace without reading gem5 "
            "output. This is not a real gem5 trace."
        ),
    )
    parser.add_argument("--sample-count", default=64, type=int)
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


def parse_int(text, field, context):
    try:
        return int(str(text), 0)
    except ValueError as error:
        raise ConvertError(f"{context}: invalid {field}: {text}") from error


def parse_marker_line(line, line_number):
    tokens = line.strip().split()
    if not tokens or tokens[0] != MARKER:
        return None

    fields = {}
    for token in tokens[1:]:
        if "=" not in token:
            raise ConvertError(
                f"line {line_number}: malformed marker token: {token}"
            )
        key, value = token.split("=", 1)
        fields[key] = value

    for field in ("workload", "seq", "command", "address", "size"):
        if field not in fields:
            raise ConvertError(f"line {line_number}: missing marker field {field}")

    return {
        "workload": fields["workload"],
        "seq": parse_int(fields["seq"], "seq", f"line {line_number}"),
        "command": fields["command"].upper(),
        "address": parse_int(fields["address"], "address", f"line {line_number}"),
        "size": parse_int(fields["size"], "size", f"line {line_number}"),
        "pc": fields.get("pc", "0x0"),
        "symbol": fields.get("symbol", fields["workload"]),
    }


def load_marker_events(input_path):
    input_path = repo_path(input_path)
    if not input_path.exists():
        raise ConvertError(f"input not found: {display_path(input_path)}")

    events = []
    with input_path.open(encoding="utf-8", errors="replace") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            event = parse_marker_line(line, line_number)
            if event is not None:
                events.append(event)

    if not events:
        raise ConvertError(
            f"no {MARKER} markers found in {display_path(input_path)}"
        )
    return events


def sample_events(pattern, count, size_bytes):
    if count <= 0:
        raise ConvertError("--sample-count must be positive")
    if size_bytes <= 0:
        raise ConvertError("--size-bytes must be positive")

    if pattern == "sequential":
        workload = "sequential_scan"
        stride_bytes = size_bytes
    elif pattern == "stride":
        workload = "stride_scan"
        stride_bytes = 16
    else:
        raise ConvertError(f"unsupported sample pattern: {pattern}")

    return [
        {
            "workload": workload,
            "seq": index + 1,
            "command": "READ",
            "address": index * stride_bytes,
            "size": size_bytes,
            "pc": "0x0",
            "symbol": workload,
        }
        for index in range(count)
    ]


def format_time(value):
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.3f}"


def format_hex(value):
    return f"0x{value:08X}"


def normalize_events(events, args):
    command_filter = args.command_filter.upper()
    filtered = [
        event for event in events if event["command"].upper() == command_filter
    ]
    if not filtered:
        raise ConvertError(f"no events matched command filter {command_filter}")

    bad_sizes = [event for event in filtered if event["size"] != args.size_bytes]
    if bad_sizes:
        raise ConvertError(
            f"event size mismatch: expected {args.size_bytes}, "
            f"got {bad_sizes[0]['size']}"
        )

    base_address = min(event["address"] for event in filtered)
    workload_name = args.workload_name or filtered[0]["workload"]
    rows = []
    for index, event in enumerate(filtered):
        address = event["address"]
        if args.address_normalize == "zero_based":
            address -= base_address
        if address < 0:
            raise ConvertError("normalized address became negative")

        rows.append(
            {
                "workload_name": workload_name,
                "txn_id": str(index + 1),
                "timestamp_ns": format_time(index * args.timestamp_step_ns),
                "initiator_id": str(args.initiator_id),
                "command": command_filter,
                "address": format_hex(address),
                "size_bytes": str(args.size_bytes),
                "pc": event.get("pc", "0x0"),
                "symbol": event.get("symbol", workload_name),
                "source": args.source,
            }
        )

    return rows


def write_normalized_csv(output_path, rows):
    output_path = repo_path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=NORMALIZED_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def main():
    args = parse_args()
    if args.sample_pattern:
        if args.input is not None:
            raise ConvertError("--input cannot be used with --sample-pattern")
        args.source = "sample_expected_format_not_real_gem5"
        events = sample_events(args.sample_pattern, args.sample_count, args.size_bytes)
        print(
            "[convert] WARNING: generated sample expected-format trace; "
            "this is not real gem5 output."
        )
    else:
        if args.input is None:
            raise ConvertError("--input is required unless --sample-pattern is used")
        events = load_marker_events(args.input)

    rows = normalize_events(events, args)
    output_path = write_normalized_csv(args.output, rows)
    print(
        "[convert] normalized trace "
        f"{display_path(output_path)} rows={len(rows)} source={rows[0]['source']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConvertError as error:
        print(f"[convert] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
