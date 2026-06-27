#!/usr/bin/env python3

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_CLAIM_MATRIX = Path("examples/lt/validation_packet/project_j_claim_matrix.csv")
DEFAULT_EVIDENCE_TABLE = Path("examples/lt/validation_packet/project_j_evidence_table.csv")
DEFAULT_UNSUPPORTED_CLAIMS = Path(
    "examples/lt/validation_packet/project_j_unsupported_claims.csv"
)
DEFAULT_OUTPUT_DIR = Path("examples/lt/results/project_j_accuracy_validation_packet")

CLAIM_FIELDS = [
    "claim_id",
    "project",
    "validation_level",
    "claim",
    "workload_scope",
    "region_scope",
    "metric_scope",
    "reference_source",
    "evidence_source",
    "error_budget",
    "observed_error",
    "status",
    "valid_wording",
    "invalid_wording",
    "limitation",
    "next_step",
]

EVIDENCE_FIELDS = [
    "evidence_id",
    "project",
    "evidence_type",
    "path",
    "exists_required",
    "generated_or_static",
    "claim_supported",
    "reference_source",
    "metric_or_artifact",
    "quality_status",
    "limitation",
]

UNSUPPORTED_FIELDS = [
    "unsupported_claim",
    "why_unsupported",
    "current_evidence_gap",
    "required_future_evidence",
    "allowed_alternative_wording",
]

SUMMARY_FIELDS = ["summary_type", "name", "count", "notes"]
INVENTORY_FIELDS = EVIDENCE_FIELDS + ["actual_exists", "resolved_quality_status"]

VALIDATION_LEVELS = {
    "Level 0 Internal consistency",
    "Level 1 Trend correlation",
    "Level 2 Quantitative correlation",
    "Level 3 Golden reference validation",
    "Level 4 Production signoff",
    "Unsupported",
    "Future",
}

CLAIM_STATUSES = {
    "pass",
    "partial",
    "future",
    "unsupported",
    "not_applicable",
}

DANGEROUS_PHRASES = [
    "silicon validated",
    "production signoff",
    "full-system cycle accurate",
    "hardware-counter validated",
    "apple/nvidia/arm production-level validation",
    "full soc validated",
]

INTERVIEW_SAFE_WORDING = (
    "I built a compact architecture performance modeling lab with an explicit "
    "validation ladder: internal replay consistency, gem5 trend correlation, "
    "local Verilator RTL reference correlation, and a sample-only "
    "profiler/counter interface for future real captures. The project is "
    "careful about claim boundaries: every accuracy statement is tied to a "
    "reference source, metric definition, workload region, and error budget."
)


class PacketError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build Project J accuracy validation evidence packet."
    )
    parser.add_argument(
        "--claim-matrix",
        default=DEFAULT_CLAIM_MATRIX,
        type=Path,
        help="Project J static claim matrix CSV.",
    )
    parser.add_argument(
        "--evidence-table",
        default=DEFAULT_EVIDENCE_TABLE,
        type=Path,
        help="Project J static evidence table CSV.",
    )
    parser.add_argument(
        "--unsupported-claims",
        default=DEFAULT_UNSUPPORTED_CLAIMS,
        type=Path,
        help="Project J static unsupported-claims CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        type=Path,
        help="Output directory for generated Project J packet artifacts.",
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


def read_csv_required(path, expected_fields, label):
    path = repo_path(path)
    if not path.exists():
        raise PacketError(f"{label} not found: {display_path(path)}")
    if not path.is_file():
        raise PacketError(f"{label} is not a file: {display_path(path)}")

    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise PacketError(f"{label} has no header: {display_path(path)}")
        if reader.fieldnames != expected_fields:
            raise PacketError(
                f"{label} schema mismatch: expected {expected_fields}, "
                f"got {reader.fieldnames}"
            )
        rows = list(reader)

    if not rows:
        raise PacketError(f"{label} has no rows: {display_path(path)}")
    return rows


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(fields, rows):
    lines = []
    lines.append("| " + " | ".join(fields) + " |")
    lines.append("| " + " | ".join("---" for _ in fields) + " |")
    for row in rows:
        values = [str(row.get(field, "")).replace("\n", " ") for field in fields]
        lines.append("| " + " | ".join(values) + " |")
    return lines


def parse_bool(value, label):
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise PacketError(f"{label} must be true or false, got {value!r}")


def validate_claim_matrix(rows):
    for index, row in enumerate(rows, start=2):
        validation_level = row["validation_level"]
        status = row["status"]
        if validation_level not in VALIDATION_LEVELS:
            raise PacketError(
                f"claim matrix row {index}: unsupported validation_level "
                f"{validation_level!r}"
            )
        if status not in CLAIM_STATUSES:
            raise PacketError(
                f"claim matrix row {index}: unsupported status {status!r}"
            )

        for field in CLAIM_FIELDS:
            value = row[field]
            lower_value = value.lower()
            for phrase in DANGEROUS_PHRASES:
                if phrase not in lower_value:
                    continue
                allowed = field in {"invalid_wording", "limitation"}
                allowed = allowed or (field == "claim" and status == "unsupported")
                if not allowed:
                    raise PacketError(
                        "dangerous wording appears outside an unsupported, "
                        f"invalid, or limitation context: row {index}, "
                        f"field {field!r}, phrase {phrase!r}"
                    )


def validate_unsupported_claims(rows):
    for index, row in enumerate(rows, start=2):
        if not row["unsupported_claim"].strip():
            raise PacketError(f"unsupported claims row {index}: empty claim")


def build_evidence_inventory(rows):
    inventory_rows = []
    errors = []

    for index, row in enumerate(rows, start=2):
        generated_or_static = row["generated_or_static"]
        if generated_or_static not in {"static", "generated"}:
            raise PacketError(
                f"evidence table row {index}: generated_or_static must be "
                f"static or generated, got {generated_or_static!r}"
            )

        exists_required = parse_bool(
            row["exists_required"],
            f"evidence table row {index} exists_required",
        )
        evidence_path = repo_path(row["path"])
        actual_exists = evidence_path.is_file()

        if generated_or_static == "static":
            resolved_quality_status = "available" if actual_exists else "missing"
        elif actual_exists:
            resolved_quality_status = "available"
        else:
            resolved_quality_status = "not_generated"

        if exists_required and not actual_exists:
            errors.append(
                f"required static evidence missing: {display_path(evidence_path)}"
            )

        inventory_row = dict(row)
        inventory_row["actual_exists"] = str(actual_exists).lower()
        inventory_row["resolved_quality_status"] = resolved_quality_status
        inventory_rows.append(inventory_row)

    if errors:
        raise PacketError("; ".join(errors))
    return inventory_rows


def load_optional_csv(path):
    path = repo_path(path)
    if not path.exists() or not path.is_file():
        return None
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            return []
        return list(reader)


def summarize_project_h():
    correlation_path = Path(
        "examples/lt/results/project_h_verilator_rtl_golden_model/"
        "model_vs_rtl_correlation.csv"
    )
    rows = load_optional_csv(correlation_path)
    if rows is None:
        return {
            "path": str(correlation_path),
            "quality_status": "not_generated",
            "row_count": 0,
            "status_counts": {},
            "notes": "observed_error=not_available",
        }

    status_counts = Counter(row.get("status", "unknown") for row in rows)
    return {
        "path": str(correlation_path),
        "quality_status": "available",
        "row_count": len(rows),
        "status_counts": dict(status_counts),
        "notes": "uses existing Project H generated model-vs-RTL rows",
    }


def summarize_project_i():
    correlation_path = Path(
        "examples/lt/results/project_i_profiler_counter_correlation_interface/"
        "counter_correlation_ready.csv"
    )
    rows = load_optional_csv(correlation_path)
    if rows is None:
        return {
            "path": str(correlation_path),
            "quality_status": "not_generated",
            "row_count": 0,
            "data_class_counts": {},
            "claim_status_counts": {},
            "notes": "counter interface generated output not available",
        }

    data_class_counts = Counter(row.get("data_class", "unknown") for row in rows)
    claim_status_counts = Counter(row.get("claim_status", "unknown") for row in rows)
    return {
        "path": str(correlation_path),
        "quality_status": "available",
        "row_count": len(rows),
        "data_class_counts": dict(data_class_counts),
        "claim_status_counts": dict(claim_status_counts),
        "notes": "sample_synthetic rows are interface evidence only",
    }


def build_summary_rows(claim_rows, inventory_rows):
    status_counts = Counter(row["status"] for row in claim_rows)
    level_counts = Counter(row["validation_level"] for row in claim_rows)
    evidence_counts = Counter(row["resolved_quality_status"] for row in inventory_rows)

    summary_rows = []
    for status in ["pass", "partial", "future", "unsupported", "not_applicable"]:
        summary_rows.append(
            {
                "summary_type": "claim_status",
                "name": status,
                "count": status_counts.get(status, 0),
                "notes": "claim matrix status count",
            }
        )
    for level in sorted(VALIDATION_LEVELS):
        summary_rows.append(
            {
                "summary_type": "validation_level",
                "name": level,
                "count": level_counts.get(level, 0),
                "notes": "claim matrix validation-level count",
            }
        )
    for quality_status in ["available", "not_generated", "missing"]:
        summary_rows.append(
            {
                "summary_type": "evidence_quality",
                "name": quality_status,
                "count": evidence_counts.get(quality_status, 0),
                "notes": "resolved evidence inventory count",
            }
        )
    return summary_rows


def format_counter(counter_dict):
    if not counter_dict:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counter_dict.items()))


def write_packet_report(path, claim_rows, inventory_rows, h_summary, i_summary):
    supported_rows = [row for row in claim_rows if row["status"] == "pass"]
    partial_future_rows = [
        row for row in claim_rows if row["status"] in {"partial", "future"}
    ]
    unsupported_rows = [row for row in claim_rows if row["status"] == "unsupported"]

    lines = [
        "# Project J Accuracy Validation Packet",
        "",
        "## Summary",
        "",
        "Project J is an evidence packet only. It does not run Project H or Project I, "
        "and it does not fabricate missing generated results.",
        "",
        f"- Claim rows: `{len(claim_rows)}`",
        f"- Evidence rows: `{len(inventory_rows)}`",
        f"- Project H correlation: `{h_summary['quality_status']}` "
        f"({h_summary['row_count']} rows)",
        f"- Project I counter interface: `{i_summary['quality_status']}` "
        f"({i_summary['row_count']} rows)",
        "",
        "## Validation Level Summary",
        "",
    ]

    level_counter = Counter(row["validation_level"] for row in claim_rows)
    level_rows = [
        {"validation_level": level, "count": level_counter.get(level, 0)}
        for level in sorted(VALIDATION_LEVELS)
    ]
    lines.extend(markdown_table(["validation_level", "count"], level_rows))

    lines.extend(
        [
            "",
            "## Supported Claims",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            ["claim_id", "project", "validation_level", "claim", "valid_wording"],
            supported_rows,
        )
    )

    lines.extend(
        [
            "",
            "## Partial / Future Claims",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            ["claim_id", "project", "validation_level", "claim", "status", "next_step"],
            partial_future_rows,
        )
    )

    lines.extend(
        [
            "",
            "## Unsupported Claims",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            ["claim_id", "claim", "status", "limitation", "invalid_wording"],
            unsupported_rows,
        )
    )

    lines.extend(
        [
            "",
            "## Evidence Inventory",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            [
                "evidence_id",
                "project",
                "path",
                "generated_or_static",
                "actual_exists",
                "resolved_quality_status",
                "limitation",
            ],
            inventory_rows,
        )
    )

    lines.extend(
        [
            "",
            "## Project H / I Generated Evidence State",
            "",
            f"- Project H path: `{h_summary['path']}`",
            f"- Project H status counts: `{format_counter(h_summary['status_counts'])}`",
            f"- Project H notes: `{h_summary['notes']}`",
            f"- Project I path: `{i_summary['path']}`",
            f"- Project I data classes: `{format_counter(i_summary['data_class_counts'])}`",
            f"- Project I claim statuses: `{format_counter(i_summary['claim_status_counts'])}`",
            f"- Project I notes: `{i_summary['notes']}`",
            "",
            "## Claim Boundary",
            "",
            "Current evidence supports bounded implementation consistency, trend "
            "correlation, optional local RTL correlation reporting when generated "
            "Project H rows exist, and sample-only counter interface readiness.",
            "",
            "It does not support silicon validated, production signoff, "
            "full-system cycle accurate, hardware-counter validated, "
            "Apple/NVIDIA/ARM production-level validation, or full SoC validated "
            "claims.",
            "",
            "## Interview-Safe Wording",
            "",
            "```text",
            INTERVIEW_SAFE_WORDING,
            "```",
            "",
            "## Next Steps",
            "",
            "- Run Project H in a Verilator-capable environment if bounded RTL observed-error rows are needed.",
            "- Add real profiler or counter captures only with source metadata, region alignment, and metric-specific error budgets.",
            "- Keep sample_synthetic rows classified as interface evidence only.",
            "- Keep enterprise release approval outside the current public-project claim boundary.",
            "",
        ]
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_unsupported_report(path, unsupported_rows):
    lines = [
        "# Project J Unsupported Claims Report",
        "",
        "Unsupported claims are listed here so they cannot drift into supported wording.",
        "",
    ]
    lines.extend(markdown_table(UNSUPPORTED_FIELDS, unsupported_rows))
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "These entries require future evidence before they can become valid claims.",
            "Sample synthetic counter rows remain parser and schema evidence only.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    args = parse_args()

    claim_rows = read_csv_required(args.claim_matrix, CLAIM_FIELDS, "claim matrix")
    evidence_rows = read_csv_required(args.evidence_table, EVIDENCE_FIELDS, "evidence table")
    unsupported_rows = read_csv_required(
        args.unsupported_claims,
        UNSUPPORTED_FIELDS,
        "unsupported claims",
    )

    validate_claim_matrix(claim_rows)
    validate_unsupported_claims(unsupported_rows)

    inventory_rows = build_evidence_inventory(evidence_rows)
    summary_rows = build_summary_rows(claim_rows, inventory_rows)
    h_summary = summarize_project_h()
    i_summary = summarize_project_i()

    output_dir = repo_path(args.output_dir)
    summary_path = output_dir / "validation_packet_summary.csv"
    report_path = output_dir / "validation_packet_report.md"
    inventory_path = output_dir / "evidence_inventory.csv"
    unsupported_report_path = output_dir / "unsupported_claims_report.md"

    write_csv(summary_path, SUMMARY_FIELDS, summary_rows)
    write_csv(inventory_path, INVENTORY_FIELDS, inventory_rows)
    write_packet_report(report_path, claim_rows, inventory_rows, h_summary, i_summary)
    write_unsupported_report(unsupported_report_path, unsupported_rows)

    print("[project-j] outputs")
    print(f"  - summary: {display_path(summary_path)}")
    print(f"  - report: {display_path(report_path)}")
    print(f"  - evidence inventory: {display_path(inventory_path)}")
    print(f"  - unsupported claims report: {display_path(unsupported_report_path)}")
    print("[project-j] Project J accuracy validation packet PASS")
    print(
        "[project-j] scope: evidence packet only; no silicon validation, "
        "no production signoff, no full-system cycle accuracy claim."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PacketError as error:
        print(f"[project-j] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
