#!/usr/bin/env python3

import argparse
import csv
import sys
from pathlib import Path


REQUIRED_FIELDS = (
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

STRING_FIELDS = {"workload_name"}
INT_FIELDS = {"num_transactions"}


class CompareError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare Python and C++ replay summary.csv outputs."
    )
    parser.add_argument("--python-output", required=True, type=Path)
    parser.add_argument("--cpp-output", required=True, type=Path)
    parser.add_argument(
        "--tolerance",
        default=0.001,
        type=float,
        help="Allowed absolute difference for floating-point metrics.",
    )
    return parser.parse_args()


def summary_path(output_dir):
    return output_dir / "summary.csv"


def read_summary(path):
    if not path.exists():
        raise CompareError(f"summary.csv not found: {path}")

    with path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        rows = list(reader)

    if not fieldnames:
        raise CompareError(f"summary.csv has no header: {path}")
    if not rows:
        raise CompareError(f"summary.csv has no rows: {path}")

    missing = [field for field in REQUIRED_FIELDS if field not in fieldnames]
    if missing:
        raise CompareError(
            f"summary.csv missing required fields in {path}: "
            + ", ".join(missing)
        )

    return fieldnames, rows


def parse_int(value, workload, field, side):
    try:
        return int(str(value).strip())
    except ValueError as error:
        raise CompareError(
            f"{workload} {field}: {side} value is not an integer: {value!r}"
        ) from error


def parse_float(value, workload, field, side):
    try:
        return float(str(value).strip())
    except ValueError as error:
        raise CompareError(
            f"{workload} {field}: {side} value is not a float: {value!r}"
        ) from error


def compare_summaries(python_output, cpp_output, tolerance):
    python_path = summary_path(python_output)
    cpp_path = summary_path(cpp_output)
    python_fields, python_rows = read_summary(python_path)
    cpp_fields, cpp_rows = read_summary(cpp_path)

    if python_fields != cpp_fields:
        raise CompareError(
            "summary.csv field mismatch:\n"
            f"  python: {', '.join(python_fields)}\n"
            f"  cpp:    {', '.join(cpp_fields)}"
        )

    if len(python_rows) != len(cpp_rows):
        raise CompareError(
            "summary.csv row count mismatch: "
            f"python={len(python_rows)} cpp={len(cpp_rows)}"
        )

    for index, (python_row, cpp_row) in enumerate(
        zip(python_rows, cpp_rows), start=2
    ):
        python_workload = python_row.get("workload_name", "")
        cpp_workload = cpp_row.get("workload_name", "")
        if python_workload != cpp_workload:
            raise CompareError(
                "workload_name mismatch "
                f"at summary.csv row {index}: "
                f"python={python_workload!r} cpp={cpp_workload!r}"
            )

        workload = python_workload or f"row {index}"
        for field in REQUIRED_FIELDS:
            python_value = python_row.get(field, "")
            cpp_value = cpp_row.get(field, "")

            if field in STRING_FIELDS:
                if python_value != cpp_value:
                    raise CompareError(
                        f"{workload} {field} mismatch: "
                        f"python={python_value!r} cpp={cpp_value!r}"
                    )
                continue

            if field in INT_FIELDS:
                python_int = parse_int(python_value, workload, field, "Python")
                cpp_int = parse_int(cpp_value, workload, field, "C++")
                if python_int != cpp_int:
                    raise CompareError(
                        f"{workload} {field} mismatch: "
                        f"python={python_value!r} cpp={cpp_value!r}"
                    )
                continue

            python_float = parse_float(python_value, workload, field, "Python")
            cpp_float = parse_float(cpp_value, workload, field, "C++")
            if abs(python_float - cpp_float) > tolerance:
                raise CompareError(
                    f"{workload} {field} mismatch: "
                    f"python={python_value!r} cpp={cpp_value!r} "
                    f"tolerance={tolerance}"
                )


def main():
    args = parse_args()
    if args.tolerance < 0:
        raise CompareError("--tolerance must be non-negative")

    compare_summaries(args.python_output, args.cpp_output, args.tolerance)
    print("[compare] Python vs C++ replay summary equivalence PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CompareError as error:
        print(f"[compare] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
