#!/usr/bin/env python3

import argparse
import csv
import sys
from collections import defaultdict
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
NA_VALUE = "NA"

COUNTER_SAMPLE_FIELDS = (
    "schema_version",
    "capture_id",
    "sample_id",
    "data_class",
    "source_type",
    "workload",
    "region_id",
    "counter_name",
    "counter_vendor_name",
    "counter_category",
    "counter_definition",
    "raw_value",
    "raw_unit",
    "aggregation",
    "sampling_mode",
    "window_start_ns",
    "window_end_ns",
    "normalization_basis",
    "normalization_denominator",
    "notes",
)

SOURCE_METADATA_FIELDS = (
    "schema_version",
    "capture_id",
    "data_class",
    "is_real_capture",
    "source_type",
    "tool_name",
    "tool_version",
    "platform_vendor",
    "platform_model",
    "os_name",
    "os_version",
    "cpu_model",
    "gpu_model",
    "fpga_board",
    "silicon_stepping",
    "workload",
    "binary_sha256",
    "input_dataset",
    "region_id",
    "region_start_marker",
    "region_end_marker",
    "capture_timestamp_utc",
    "permission_notes",
    "multiplexing_notes",
    "overflow_notes",
    "calibration_notes",
    "limitations",
)

NORMALIZED_SUMMARY_FIELDS = (
    "schema_version",
    "capture_id",
    "data_class",
    "source_type",
    "workload",
    "region_id",
    "counter_name",
    "counter_category",
    "raw_total",
    "raw_unit",
    "normalized_value",
    "normalized_unit",
    "normalization_basis",
    "sample_count",
    "window_ns",
    "quality_status",
    "claim_status",
    "notes",
)

VALIDATED_METADATA_FIELDS = SOURCE_METADATA_FIELDS + (
    "quality_status",
    "claim_status",
)

CORRELATION_READY_FIELDS = (
    "workload",
    "region_id",
    "model_metric_candidate",
    "counter_name",
    "counter_value",
    "counter_unit",
    "capture_id",
    "source_type",
    "data_class",
    "alignment_status",
    "claim_status",
    "correlation_status",
    "notes",
)

DATA_CLASSES = {
    "sample_synthetic",
    "real_capture",
}

SOURCE_TYPES = {
    "sample_synthetic",
    "linux_perf",
    "arm_pmu",
    "apple_instruments",
    "apple_powermetrics",
    "nvidia_nsight",
    "fpga_counter",
    "silicon_profiler",
    "emulator_counter",
}

NORMALIZATION_UNITS = {
    "none": None,
    "per_request": "request",
    "per_cycle": "cycle",
    "per_us": "us",
}

REAL_CAPTURE_REQUIRED_METADATA = (
    "tool_name",
    "tool_version",
    "platform_vendor",
    "platform_model",
    "workload",
    "region_id",
    "region_start_marker",
    "region_end_marker",
)

METRIC_CANDIDATES = {
    "cycles": "region_elapsed_cycles_candidate",
    "instructions": "instruction_count_candidate",
    "memory_accesses": "memory_access_count_candidate",
    "read_bytes": "read_bandwidth_or_bytes_candidate",
    "write_bytes": "write_bandwidth_or_bytes_candidate",
    "stall_cycles_sample": "stall_cycle_candidate",
}


class CounterNormalizationError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Normalize Project I profiler/counter sample CSVs into schema-smoke "
            "summary and correlation-ready outputs."
        )
    )
    parser.add_argument(
        "--counter-samples",
        default=DEFAULT_COUNTER_SAMPLES,
        type=Path,
        help="Profiler/counter sample CSV input.",
    )
    parser.add_argument(
        "--source-metadata",
        default=DEFAULT_SOURCE_METADATA,
        type=Path,
        help="Profiler/counter source metadata CSV input.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        type=Path,
        help="Output directory for Project I normalized artifacts.",
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


def read_csv(path, required_fields, label):
    path = repo_path(path)
    if not path.exists():
        raise CounterNormalizationError(
            f"{label} not found: {display_path(path)}"
        )
    if not path.is_file():
        raise CounterNormalizationError(
            f"{label} is not a file: {display_path(path)}"
        )
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        rows = list(reader)
    if not fieldnames:
        raise CounterNormalizationError(
            f"{label} has no header: {display_path(path)}"
        )
    missing = [field for field in required_fields if field not in fieldnames]
    if missing:
        raise CounterNormalizationError(
            f"{label} missing required field(s): {', '.join(missing)}"
        )
    if not rows:
        raise CounterNormalizationError(
            f"{label} has no rows: {display_path(path)}"
        )
    return rows


def parse_float(value, field, context):
    try:
        return float(str(value).strip())
    except ValueError as error:
        raise CounterNormalizationError(
            f"{context}: {field} is not numeric: {value!r}"
        ) from error


def parse_bool(value, field, context):
    value = str(value).strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise CounterNormalizationError(
        f"{context}: {field} must be true or false, got {value!r}"
    )


def is_missing(value):
    value = str(value).strip()
    return value == "" or value.upper() == NA_VALUE


def format_number(value):
    if value == NA_VALUE:
        return NA_VALUE
    text = f"{float(value):.6f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def claim_status_for_data_class(data_class):
    if data_class == "sample_synthetic":
        return "sample_only_not_evidence"
    return "real_capture_not_evaluated"


def validate_sample_row(row, row_number):
    context = f"counter sample row {row_number}"
    data_class = row["data_class"].strip()
    source_type = row["source_type"].strip()
    if data_class not in DATA_CLASSES:
        raise CounterNormalizationError(
            f"{context}: unsupported data_class {data_class!r}"
        )
    if source_type not in SOURCE_TYPES:
        raise CounterNormalizationError(
            f"{context}: unsupported source_type {source_type!r}"
        )
    if data_class == "sample_synthetic" and source_type != "sample_synthetic":
        raise CounterNormalizationError(
            f"{context}: sample_synthetic must use source_type=sample_synthetic"
        )
    if data_class == "sample_synthetic" and "sample_only_not_evidence" not in row[
        "notes"
    ]:
        raise CounterNormalizationError(
            f"{context}: sample_synthetic notes must include sample_only_not_evidence"
        )
    basis = row["normalization_basis"].strip()
    if basis not in NORMALIZATION_UNITS:
        raise CounterNormalizationError(
            f"{context}: unsupported normalization_basis {basis!r}"
        )
    parse_float(row["raw_value"], "raw_value", context)
    parse_float(row["window_start_ns"], "window_start_ns", context)
    parse_float(row["window_end_ns"], "window_end_ns", context)


def validate_metadata_rows(rows):
    metadata_by_capture = {}
    validated = []
    for index, row in enumerate(rows, start=2):
        context = f"source metadata row {index}"
        capture_id = row["capture_id"].strip()
        if not capture_id:
            raise CounterNormalizationError(f"{context}: empty capture_id")
        if capture_id in metadata_by_capture:
            raise CounterNormalizationError(
                f"{context}: duplicate capture_id {capture_id!r}"
            )

        data_class = row["data_class"].strip()
        source_type = row["source_type"].strip()
        if data_class not in DATA_CLASSES:
            raise CounterNormalizationError(
                f"{context}: unsupported data_class {data_class!r}"
            )
        if source_type not in SOURCE_TYPES:
            raise CounterNormalizationError(
                f"{context}: unsupported source_type {source_type!r}"
            )
        is_real_capture = parse_bool(row["is_real_capture"], "is_real_capture", context)
        if data_class == "sample_synthetic":
            if is_real_capture:
                raise CounterNormalizationError(
                    f"{context}: sample_synthetic metadata must use is_real_capture=false"
                )
            if source_type != "sample_synthetic":
                raise CounterNormalizationError(
                    f"{context}: sample_synthetic metadata must use source_type=sample_synthetic"
                )
        if data_class == "real_capture":
            if not is_real_capture:
                raise CounterNormalizationError(
                    f"{context}: real_capture metadata must use is_real_capture=true"
                )
            missing = [
                field for field in REAL_CAPTURE_REQUIRED_METADATA if is_missing(row[field])
            ]
            if missing:
                raise CounterNormalizationError(
                    f"{context}: real_capture metadata missing field(s): "
                    + ", ".join(missing)
                )

        claim_status = claim_status_for_data_class(data_class)
        quality_status = "pass"
        if data_class == "sample_synthetic" and "sample-only" not in row[
            "limitations"
        ]:
            quality_status = "warning"
        validated_row = dict(row)
        validated_row["quality_status"] = quality_status
        validated_row["claim_status"] = claim_status
        metadata_by_capture[capture_id] = validated_row
        validated.append(validated_row)
    return metadata_by_capture, validated


def validate_and_join_samples(rows, metadata_by_capture):
    validated = []
    for index, row in enumerate(rows, start=2):
        validate_sample_row(row, index)
        capture_id = row["capture_id"].strip()
        if capture_id not in metadata_by_capture:
            raise CounterNormalizationError(
                f"counter sample row {index}: capture_id not found in metadata: "
                f"{capture_id!r}"
            )
        metadata = metadata_by_capture[capture_id]
        data_class = row["data_class"].strip()
        if metadata["data_class"].strip() != data_class:
            raise CounterNormalizationError(
                f"counter sample row {index}: data_class does not match metadata "
                f"for capture_id {capture_id!r}"
            )
        sample_is_real = data_class == "real_capture"
        metadata_is_real = parse_bool(
            metadata["is_real_capture"],
            "is_real_capture",
            f"metadata for {capture_id}",
        )
        if sample_is_real != metadata_is_real:
            raise CounterNormalizationError(
                f"counter sample row {index}: is_real_capture does not match data_class "
                f"for capture_id {capture_id!r}"
            )
        if metadata["workload"].strip() != row["workload"].strip():
            raise CounterNormalizationError(
                f"counter sample row {index}: workload does not match metadata "
                f"for capture_id {capture_id!r}"
            )
        if metadata["region_id"].strip() != row["region_id"].strip():
            raise CounterNormalizationError(
                f"counter sample row {index}: region_id does not match metadata "
                f"for capture_id {capture_id!r}"
            )
        validated.append(row)
    return validated


def denominator_for_row(row):
    basis = row["normalization_basis"].strip()
    if basis == "none":
        return 1.0, False
    try:
        denominator = float(str(row["normalization_denominator"]).strip())
    except ValueError:
        return 0.0, True
    return denominator, denominator <= 0.0


def build_normalized_summary(sample_rows):
    groups = {}
    denominator_invalid = defaultdict(bool)
    denominator_totals = defaultdict(float)
    window_start = {}
    window_end = {}
    notes_by_group = defaultdict(list)

    for row in sample_rows:
        key = (
            row["schema_version"].strip(),
            row["capture_id"].strip(),
            row["data_class"].strip(),
            row["source_type"].strip(),
            row["workload"].strip(),
            row["region_id"].strip(),
            row["counter_name"].strip(),
            row["counter_category"].strip(),
            row["raw_unit"].strip(),
            row["normalization_basis"].strip(),
        )
        raw_value = parse_float(row["raw_value"], "raw_value", row["sample_id"])
        start_ns = parse_float(row["window_start_ns"], "window_start_ns", row["sample_id"])
        end_ns = parse_float(row["window_end_ns"], "window_end_ns", row["sample_id"])
        denominator, invalid = denominator_for_row(row)

        if key not in groups:
            groups[key] = {
                "raw_total": 0.0,
                "sample_count": 0,
            }
            window_start[key] = start_ns
            window_end[key] = end_ns
        groups[key]["raw_total"] += raw_value
        groups[key]["sample_count"] += 1
        window_start[key] = min(window_start[key], start_ns)
        window_end[key] = max(window_end[key], end_ns)
        denominator_totals[key] += denominator
        denominator_invalid[key] = denominator_invalid[key] or invalid
        if row["notes"] not in notes_by_group[key]:
            notes_by_group[key].append(row["notes"])

    output_rows = []
    for key in sorted(groups):
        (
            schema_version,
            capture_id,
            data_class,
            source_type,
            workload,
            region_id,
            counter_name,
            counter_category,
            raw_unit,
            normalization_basis,
        ) = key
        raw_total = groups[key]["raw_total"]
        quality_status = "pass"
        if denominator_invalid[key]:
            normalized_value = NA_VALUE
            normalized_unit = NA_VALUE
            quality_status = "warning"
        elif normalization_basis == "none":
            normalized_value = raw_total
            normalized_unit = raw_unit
        else:
            normalized_value = raw_total / denominator_totals[key]
            normalized_unit = f"{raw_unit}/{NORMALIZATION_UNITS[normalization_basis]}"

        output_rows.append(
            {
                "schema_version": schema_version,
                "capture_id": capture_id,
                "data_class": data_class,
                "source_type": source_type,
                "workload": workload,
                "region_id": region_id,
                "counter_name": counter_name,
                "counter_category": counter_category,
                "raw_total": format_number(raw_total),
                "raw_unit": raw_unit,
                "normalized_value": format_number(normalized_value),
                "normalized_unit": normalized_unit,
                "normalization_basis": normalization_basis,
                "sample_count": str(groups[key]["sample_count"]),
                "window_ns": format_number(window_end[key] - window_start[key]),
                "quality_status": quality_status,
                "claim_status": claim_status_for_data_class(data_class),
                "notes": "; ".join(notes_by_group[key]),
            }
        )
    return output_rows


def build_correlation_ready_rows(summary_rows):
    rows = []
    for row in summary_rows:
        data_class = row["data_class"]
        claim_status = row["claim_status"]
        if data_class == "sample_synthetic":
            alignment_status = "sample_schema_only"
            correlation_status = "sample_only_not_evidence"
        else:
            alignment_status = "requires_workload_region_metric_alignment"
            correlation_status = "not_evaluated"
        rows.append(
            {
                "workload": row["workload"],
                "region_id": row["region_id"],
                "model_metric_candidate": METRIC_CANDIDATES.get(
                    row["counter_name"],
                    "requires_manual_metric_mapping",
                ),
                "counter_name": row["counter_name"],
                "counter_value": row["normalized_value"],
                "counter_unit": row["normalized_unit"],
                "capture_id": row["capture_id"],
                "source_type": row["source_type"],
                "data_class": data_class,
                "alignment_status": alignment_status,
                "claim_status": claim_status,
                "correlation_status": correlation_status,
                "notes": row["notes"],
            }
        )
    return rows


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def markdown_cell(value):
    return str(value).replace("\n", " ").replace("|", "\\|")


def markdown_table(headers, rows):
    lines = [
        "| " + " | ".join(markdown_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(markdown_cell(row.get(header, "")) for header in headers)
            + " |"
        )
    return lines


def write_claim_boundary_report(output_dir, summary_rows, metadata_rows, source_info):
    report_path = output_dir / "counter_claim_boundary_report.md"
    sample_rows = [row for row in summary_rows if row["data_class"] == "sample_synthetic"]
    real_rows = [row for row in summary_rows if row["data_class"] == "real_capture"]
    warning_rows = [row for row in summary_rows if row["quality_status"] == "warning"]
    status = "pass" if not warning_rows else "warning"

    lines = [
        "# Project I: Profiler / Counter Correlation Interface Report",
        "",
        "## Current Scope",
        "",
        "Project I only validates schema, ingest, normalization, and report formatting "
        "on sample synthetic data.",
        "",
        "This report is generated from CSV files and does not represent a real "
        "profiler, hardware counter, FPGA, or silicon capture.",
        "",
        "## Inputs",
        "",
        f"- Counter samples: `{source_info['counter_samples']}`",
        f"- Source metadata: `{source_info['source_metadata']}`",
        "",
        "## Output Summary",
        "",
        f"- Overall status: `{status}`",
        f"- Normalized counter rows: `{len(summary_rows)}`",
        f"- Sample synthetic rows: `{len(sample_rows)}`",
        f"- Real capture rows: `{len(real_rows)}`",
        f"- Warning rows: `{len(warning_rows)}`",
        f"- Metadata captures: `{len(metadata_rows)}`",
        "",
        "## Supported Claims",
        "",
        "- The Project I CSV schema can represent counter samples and source metadata.",
        "- The ingest tool can validate required columns, data-class/source-type rules, "
        "metadata joins, and basic normalization rules.",
        "- The generated tables are correlation-ready interface artifacts for a future "
        "Project J report.",
        "",
        "## Unsupported Claims",
        "",
        "- Project I does not validate hardware counter accuracy.",
        "- Project I does not provide silicon validation.",
        "- Project I does not provide production signoff.",
        "- Project I does not prove full-system cycle accuracy.",
        "- Project I does not claim real Linux perf, ARM PMU, Apple Instruments, Apple "
        "powermetrics, NVIDIA Nsight, FPGA counter, or silicon profiler integration.",
        "",
        "## Sample Data Policy",
        "",
        "- Current sample rows use `data_class=sample_synthetic` and "
        "`source_type=sample_synthetic`.",
        "- Sample data is not real hardware evidence.",
        "- Every sample-derived row must carry `claim_status=sample_only_not_evidence`.",
        "- Sample data may be used for parser smoke tests, schema stability checks, "
        "normalization checks, and report formatting only.",
        "",
        "## Future Real Capture Requirements",
        "",
        "Real Linux perf / ARM PMU / Apple Instruments / NVIDIA Nsight / FPGA / "
        "silicon capture must be added later with metadata, workload region alignment, "
        "metric definition alignment, and explicit error budget.",
        "",
        "Required future evidence includes tool version, platform identity, workload "
        "identity, binary or source hash where possible, region markers, counter "
        "definitions, sampling mode, multiplexing/overflow notes, measurement noise "
        "notes, and Project J error-budget rules.",
        "",
        "## Relationship to Project G/H/J",
        "",
        "- Project G defines the accuracy ladder and claim boundary vocabulary.",
        "- Project H provides a bounded local Verilator RTL reference path.",
        "- Project I defines the profiler/counter ingestion interface for future real "
        "captures.",
        "- Project J should consume real reference data and model outputs to produce "
        "observed-error reports with pass/fail/warning/invalid/not_applicable status.",
        "",
        "## Normalized Counter Preview",
        "",
    ]
    preview_fields = (
        "workload",
        "counter_name",
        "normalized_value",
        "normalized_unit",
        "quality_status",
        "claim_status",
    )
    lines.extend(markdown_table(preview_fields, summary_rows[:12]))
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main():
    args = parse_args()
    counter_samples_path = repo_path(args.counter_samples)
    source_metadata_path = repo_path(args.source_metadata)
    output_dir = repo_path(args.output_dir)

    sample_rows = read_csv(
        counter_samples_path,
        COUNTER_SAMPLE_FIELDS,
        "counter samples CSV",
    )
    metadata_rows = read_csv(
        source_metadata_path,
        SOURCE_METADATA_FIELDS,
        "source metadata CSV",
    )
    metadata_by_capture, validated_metadata_rows = validate_metadata_rows(
        metadata_rows
    )
    validated_sample_rows = validate_and_join_samples(sample_rows, metadata_by_capture)
    normalized_rows = build_normalized_summary(validated_sample_rows)
    correlation_ready_rows = build_correlation_ready_rows(normalized_rows)

    normalized_path = output_dir / "normalized_counter_summary.csv"
    metadata_path = output_dir / "counter_source_metadata.csv"
    correlation_path = output_dir / "counter_correlation_ready.csv"

    write_csv(normalized_path, NORMALIZED_SUMMARY_FIELDS, normalized_rows)
    write_csv(metadata_path, VALIDATED_METADATA_FIELDS, validated_metadata_rows)
    write_csv(
        correlation_path,
        CORRELATION_READY_FIELDS,
        correlation_ready_rows,
    )
    report_path = write_claim_boundary_report(
        output_dir,
        normalized_rows,
        validated_metadata_rows,
        {
            "counter_samples": display_path(counter_samples_path),
            "source_metadata": display_path(source_metadata_path),
        },
    )

    print("[project-i] outputs")
    print(f"  - normalized summary: {display_path(normalized_path)}")
    print(f"  - source metadata: {display_path(metadata_path)}")
    print(f"  - correlation-ready table: {display_path(correlation_path)}")
    print(f"  - claim-boundary report: {display_path(report_path)}")
    print(
        "[project-i] scope: sample-only schema smoke test; no real profiler "
        "capture; no hardware-counter validation; no silicon validation; "
        "no production signoff."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CounterNormalizationError as error:
        print(f"[project-i] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
