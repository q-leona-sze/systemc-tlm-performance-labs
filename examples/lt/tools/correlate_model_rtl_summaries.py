#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = Path("examples/lt/results/project_h_verilator_rtl_golden_model")
SUMMARY_FIELDS = (
    "workload",
    "total_requests",
    "accepted_requests",
    "rejected_requests",
    "avg_latency_cycles",
    "p50_latency_cycles",
    "p95_latency_cycles",
    "p99_latency_cycles",
    "max_latency_cycles",
    "avg_latency_ns",
    "p50_latency_ns",
    "p95_latency_ns",
    "p99_latency_ns",
    "max_latency_ns",
    "throughput_txn_per_cycle",
    "throughput_txn_per_us",
    "bank_conflict_ratio_pct",
)
CORRELATION_FIELDS = (
    "workload",
    "metric",
    "unit",
    "model_value",
    "rtl_value",
    "abs_error",
    "rel_error_pct",
    "tolerance_pct",
    "status",
)
ERROR_BUDGET_FIELDS = (
    "metric",
    "unit",
    "tolerance_pct",
    "rule",
)


class CorrelationError(Exception):
    pass


ERROR_BUDGET = {
    "total_requests": ("requests", 0.0, "exact integer match"),
    "accepted_requests": ("requests", 0.0, "exact integer match"),
    "rejected_requests": ("requests", 0.0, "exact integer match"),
    "avg_latency_cycles": ("cycles", 0.001, "floating match with tiny tolerance"),
    "p50_latency_cycles": ("cycles", 0.001, "floating match with tiny tolerance"),
    "p95_latency_cycles": ("cycles", 0.001, "floating match with tiny tolerance"),
    "p99_latency_cycles": ("cycles", 0.001, "floating match with tiny tolerance"),
    "max_latency_cycles": ("cycles", 0.001, "floating match with tiny tolerance"),
    "avg_latency_ns": ("ns", 0.001, "floating match with tiny tolerance"),
    "p50_latency_ns": ("ns", 0.001, "floating match with tiny tolerance"),
    "p95_latency_ns": ("ns", 0.001, "floating match with tiny tolerance"),
    "p99_latency_ns": ("ns", 0.001, "floating match with tiny tolerance"),
    "max_latency_ns": ("ns", 0.001, "floating match with tiny tolerance"),
    "throughput_txn_per_cycle": ("txn/cycle", 0.1, "relative error must be <= 0.1%"),
    "throughput_txn_per_us": ("txn/us", 0.1, "relative error must be <= 0.1%"),
    "bank_conflict_ratio_pct": (
        "pct",
        0.001,
        "Project H definition: accepted requests with latency_cycles > service_latency_cycles divided by accepted_requests",
    ),
}
EXACT_METRICS = {"total_requests", "accepted_requests", "rejected_requests"}
TINY_FLOAT_METRICS = {
    "avg_latency_cycles",
    "p50_latency_cycles",
    "p95_latency_cycles",
    "p99_latency_cycles",
    "max_latency_cycles",
    "avg_latency_ns",
    "p50_latency_ns",
    "p95_latency_ns",
    "p99_latency_ns",
    "max_latency_ns",
    "bank_conflict_ratio_pct",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Correlate Project H H-aligned model summary against RTL summary."
    )
    parser.add_argument(
        "--model-summary",
        default=DEFAULT_OUTPUT_DIR / "model_summary_aligned.csv",
        type=Path,
        help="H-aligned model summary.csv.",
    )
    parser.add_argument(
        "--rtl-summary",
        default=DEFAULT_OUTPUT_DIR / "rtl_summary.csv",
        type=Path,
        help="Verilator RTL summary.csv.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        type=Path,
        help="Output directory for correlation CSV, error budget, and report.",
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


def read_summary(path, label):
    path = repo_path(path)
    if not path.exists():
        raise CorrelationError(f"{label} not found: {display_path(path)}")
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        rows = list(reader)
    if not fieldnames:
        raise CorrelationError(f"{label} has no header: {display_path(path)}")
    if not rows:
        raise CorrelationError(f"{label} is empty: {display_path(path)}")
    missing = [field for field in SUMMARY_FIELDS if field not in fieldnames]
    if missing:
        raise CorrelationError(
            f"{label} missing fields in {display_path(path)}: "
            + ", ".join(missing)
        )
    by_workload = {}
    for row in rows:
        workload = row.get("workload", "")
        if not workload:
            raise CorrelationError(f"{label} contains row with empty workload")
        if workload in by_workload:
            raise CorrelationError(f"{label} has duplicate workload: {workload}")
        by_workload[workload] = row
    return by_workload


def parse_float(value, workload, metric, side):
    try:
        return float(str(value).strip())
    except ValueError as error:
        raise CorrelationError(
            f"{workload} {metric}: {side} value is not numeric: {value!r}"
        ) from error


def format_number(value):
    return f"{value:.3f}"


def status_for_metric(metric, abs_error, rel_error_pct, rtl_value):
    tolerance_pct = ERROR_BUDGET[metric][1]
    if metric in EXACT_METRICS:
        return "pass" if abs_error == 0.0 else "fail"
    if metric in TINY_FLOAT_METRICS:
        return "pass" if abs_error <= 0.001 else "fail"
    if rtl_value == 0.0:
        return "pass" if abs_error == 0.0 else "warning"
    return "pass" if rel_error_pct <= tolerance_pct else "fail"


def build_correlation_rows(model_rows, rtl_rows):
    model_workloads = set(model_rows)
    rtl_workloads = set(rtl_rows)
    if model_workloads != rtl_workloads:
        missing_in_model = sorted(rtl_workloads - model_workloads)
        missing_in_rtl = sorted(model_workloads - rtl_workloads)
        raise CorrelationError(
            "workload mismatch: "
            f"missing_in_model={missing_in_model} missing_in_rtl={missing_in_rtl}"
        )

    rows = []
    for workload in sorted(model_workloads):
        model = model_rows[workload]
        rtl = rtl_rows[workload]
        for metric, (unit, tolerance_pct, _) in ERROR_BUDGET.items():
            model_value = parse_float(model.get(metric, ""), workload, metric, "model")
            rtl_value = parse_float(rtl.get(metric, ""), workload, metric, "rtl")
            abs_error = abs(model_value - rtl_value)
            if rtl_value == 0.0:
                rel_error_pct = "NA"
                rel_for_status = 0.0
            else:
                rel_for_status = abs_error / abs(rtl_value) * 100.0
                rel_error_pct = format_number(rel_for_status)
            rows.append(
                {
                    "workload": workload,
                    "metric": metric,
                    "unit": unit,
                    "model_value": format_number(model_value),
                    "rtl_value": format_number(rtl_value),
                    "abs_error": format_number(abs_error),
                    "rel_error_pct": rel_error_pct,
                    "tolerance_pct": format_number(tolerance_pct),
                    "status": status_for_metric(
                        metric,
                        abs_error,
                        rel_for_status,
                        rtl_value,
                    ),
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


def write_report(output_dir, correlation_rows, source_info):
    report_path = output_dir / "correlation_report.md"
    failed = [row for row in correlation_rows if row["status"] == "fail"]
    warnings = [row for row in correlation_rows if row["status"] == "warning"]
    status = "pass" if not failed else "fail"

    lines = [
        "# Project H：Verilator RTL Golden Model Correlation Report",
        "",
        "## Current",
        "",
        "Project H 当前建立的是 local banked memory controller 的 bounded RTL golden reference。"
        "它用 deterministic normalized trace 驱动 Verilator RTL，并把同一 workload 下的 "
        "H-aligned C++ model summary 与 RTL summary 做 quantitative correlation。",
        "",
        "## Inputs",
        "",
        f"- model summary: `{source_info['model_summary']}`",
        f"- RTL summary: `{source_info['rtl_summary']}`",
        "",
        "## Error Budget",
        "",
    ]
    budget_rows = [
        {
            "metric": metric,
            "unit": unit,
            "tolerance_pct": format_number(tolerance_pct),
            "rule": rule,
        }
        for metric, (unit, tolerance_pct, rule) in ERROR_BUDGET.items()
    ]
    lines.extend(markdown_table(ERROR_BUDGET_FIELDS, budget_rows))
    lines.extend(
        [
            "",
            "## Correlation Summary",
            "",
            f"- Overall status: `{status}`",
            f"- Failed rows: `{len(failed)}`",
            f"- Warning rows: `{len(warnings)}`",
            "",
        ]
    )
    lines.extend(markdown_table(CORRELATION_FIELDS, correlation_rows))
    lines.extend(
        [
            "",
            "## Scope Boundary",
            "",
            "- Current: local banked memory controller micro-model vs local Verilator RTL reference。",
            "- Supported: deterministic trace replay、accepted/rejected request count、latency percentile、throughput、bank conflict ratio 和 explicit error budget。",
            "- Not Supported: full SoC、AXI / CHI、gem5-Verilator live co-simulation、silicon validation、production signoff、full-system cycle accuracy。",
            "- Future Work: 引入更丰富的 reference manifest、更多 workload coverage、CI profile 和后续 profiler/counter reference interface。",
            "",
            "## Claim Boundary",
            "",
            "完成本报告后，只能说：在当前 bounded workload、metric definition 和 error budget 下，"
            "H-aligned C++ model summary 与 local Verilator RTL reference summary 已完成 quantitative comparison。",
            "",
            "不能说：silicon validated、production signoff、full-system cycle accurate、full SoC validated，"
            "也不能说达到 NVIDIA / Apple / ARM production-level validation。",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main():
    args = parse_args()
    model_summary = repo_path(args.model_summary)
    rtl_summary = repo_path(args.rtl_summary)
    output_dir = repo_path(args.output_dir)

    model_rows = read_summary(model_summary, "model_summary_aligned.csv")
    rtl_rows = read_summary(rtl_summary, "rtl_summary.csv")
    correlation_rows = build_correlation_rows(model_rows, rtl_rows)

    budget_rows = [
        {
            "metric": metric,
            "unit": unit,
            "tolerance_pct": format_number(tolerance_pct),
            "rule": rule,
        }
        for metric, (unit, tolerance_pct, rule) in ERROR_BUDGET.items()
    ]

    correlation_path = output_dir / "model_vs_rtl_correlation.csv"
    budget_path = output_dir / "error_budget.csv"
    write_csv(correlation_path, CORRELATION_FIELDS, correlation_rows)
    write_csv(budget_path, ERROR_BUDGET_FIELDS, budget_rows)
    report_path = write_report(
        output_dir,
        correlation_rows,
        {
            "model_summary": display_path(model_summary),
            "rtl_summary": display_path(rtl_summary),
        },
    )

    failed = [row for row in correlation_rows if row["status"] == "fail"]
    print("[project-h] outputs")
    print(f"  - correlation: {display_path(correlation_path)}")
    print(f"  - error_budget: {display_path(budget_path)}")
    print(f"  - report: {display_path(report_path)}")
    if failed:
        raise CorrelationError(
            f"model-vs-RTL correlation has {len(failed)} failed row(s)"
        )
    print("[project-h] Project H model-vs-RTL correlation PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CorrelationError as error:
        print(f"[project-h] ERROR: {error}")
        raise SystemExit(1)
