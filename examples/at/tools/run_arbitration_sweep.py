#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional


POLICIES = ["fifo", "priority_101", "priority_102"]

SUMMARY_METRIC_FIELDS = [
    "total_transactions",
    "complete_transactions",
    "incomplete_transactions",
    "total_phase_events",
    "sanity_failure_count",
    "avg_request_accept_latency_ns",
    "avg_response_latency_ns",
    "avg_total_transaction_latency_ns",
    "max_total_transaction_latency_ns",
]

SUMMARY_FIELDS = [
    "policy",
    "status",
    *SUMMARY_METRIC_FIELDS,
    "error",
]

TIMELINE_FIELDS = [
    "txn_id",
    "command",
    "begin_req_ns",
    "end_req_ns",
    "begin_resp_ns",
    "end_resp_ns",
    "request_accept_latency_ns",
    "response_latency_ns",
    "total_transaction_latency_ns",
    "response_status",
    "sanity_status",
    "sanity_issues",
]


@dataclass
class CaseResult:
    policy: str
    status: str = "FAIL"
    metrics: Dict[str, str] = field(default_factory=dict)
    timeline: List[Dict[str, str]] = field(default_factory=list)
    error: str = ""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_repo_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return repo_root() / candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the examples/at arbitration policy sweep."
    )
    parser.add_argument(
        "--binary",
        default="./build/examples/at/at",
        help="AT executable path. Relative paths are resolved from the repo root.",
    )
    parser.add_argument(
        "--output-dir",
        default="examples/at/results/arbitration_sweep",
        help="Sweep output directory. Relative paths are resolved from the repo root.",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue running later policies after a case fails.",
    )
    parser.add_argument(
        "--policy",
        action="append",
        choices=POLICIES,
        help="Policy to run. May be repeated. Default: fifo, priority_101, priority_102.",
    )
    return parser.parse_args()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def remove_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def clear_case_outputs(case_dir: Path) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "summary_metrics.csv",
        "timeline.csv",
        "phase_trace.csv",
        "at.stdout.txt",
        "at.stderr.txt",
        "analysis.stdout.txt",
        "analysis.stderr.txt",
    ]:
        remove_if_exists(case_dir / name)


def read_single_row_csv(path: Path, required_fields: List[str]) -> Dict[str, str]:
    with path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames or []
        for field in required_fields:
            if field not in fieldnames:
                raise ValueError(f"{path}: missing field {field}")

        rows = list(reader)
        if not rows:
            raise ValueError(f"{path}: missing data row")

        return {field: rows[0].get(field, "") for field in required_fields}


def read_timeline_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames or []
        for field in TIMELINE_FIELDS:
            if field not in fieldnames:
                raise ValueError(f"{path}: missing field {field}")
        return [{field: row.get(field, "") for field in TIMELINE_FIELDS} for row in reader]


def run_process(args: List[str], env: Dict[str, str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_case(policy: str, binary: Path, output_dir: Path, analyzer: Path) -> CaseResult:
    result = CaseResult(policy=policy)
    case_dir = output_dir / policy
    trace_path = repo_root() / "phase_trace.csv"

    try:
        clear_case_outputs(case_dir)
        remove_if_exists(trace_path)

        if not binary.exists():
            result.error = f"binary not found: {binary}"
            write_text(case_dir / "at.stdout.txt", "")
            write_text(case_dir / "at.stderr.txt", f"error: {result.error}\n")
            write_text(case_dir / "analysis.stdout.txt", "")
            write_text(case_dir / "analysis.stderr.txt", "analysis skipped: AT binary missing\n")
            return result

        if not os.access(binary, os.X_OK):
            result.error = f"binary is not executable: {binary}"
            write_text(case_dir / "at.stdout.txt", "")
            write_text(case_dir / "at.stderr.txt", f"error: {result.error}\n")
            write_text(case_dir / "analysis.stdout.txt", "")
            write_text(
                case_dir / "analysis.stderr.txt",
                "analysis skipped: AT binary is not executable\n",
            )
            return result

        env = os.environ.copy()
        env["AT_ARBITRATION_POLICY"] = policy

        at_run = run_process([str(binary)], env=env, cwd=repo_root())
        write_text(case_dir / "at.stdout.txt", at_run.stdout)
        write_text(case_dir / "at.stderr.txt", at_run.stderr)

        if at_run.returncode != 0:
            result.error = f"AT binary failed with exit code {at_run.returncode}"
            write_text(case_dir / "analysis.stdout.txt", "")
            write_text(case_dir / "analysis.stderr.txt", "analysis skipped: AT binary failed\n")
            if trace_path.exists():
                shutil.copy2(trace_path, case_dir / "phase_trace.csv")
            return result

        if not trace_path.exists():
            result.error = f"trace not produced: {trace_path}"
            write_text(case_dir / "analysis.stdout.txt", "")
            write_text(case_dir / "analysis.stderr.txt", f"analysis skipped: {result.error}\n")
            return result

        analysis_run = run_process(
            [
                sys.executable,
                str(analyzer),
                "--trace",
                str(trace_path),
                "--fail-on-sanity",
                "--summary-csv-output",
                str(case_dir / "summary_metrics.csv"),
                "--timeline-csv-output",
                str(case_dir / "timeline.csv"),
            ],
            env=os.environ.copy(),
            cwd=repo_root(),
        )
        write_text(case_dir / "analysis.stdout.txt", analysis_run.stdout)
        write_text(case_dir / "analysis.stderr.txt", analysis_run.stderr)
        shutil.copy2(trace_path, case_dir / "phase_trace.csv")

        if analysis_run.returncode != 0:
            result.error = f"analyzer failed with exit code {analysis_run.returncode}"
            return result

        result.metrics = read_single_row_csv(
            case_dir / "summary_metrics.csv", SUMMARY_METRIC_FIELDS
        )
        result.timeline = read_timeline_csv(case_dir / "timeline.csv")
        result.status = "OK"
        return result
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result.status = "FAIL"
        result.error = str(exc)
        write_text(case_dir / "analysis.stderr.txt", f"error: {result.error}\n")
        return result


def write_summary_csv(path: Path, results: List[CaseResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as summary_file:
        writer = csv.DictWriter(summary_file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for result in results:
            row = {
                "policy": result.policy,
                "status": result.status,
                "error": result.error,
            }
            for field in SUMMARY_METRIC_FIELDS:
                row[field] = result.metrics.get(field, "")
            writer.writerow(row)


def decimal_metric(result: Optional[CaseResult], field: str) -> Optional[Decimal]:
    if result is None or result.status != "OK":
        return None

    value = result.metrics.get(field, "")
    if value == "":
        return None

    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


def format_decimal(value: Optional[Decimal], signed: bool = False) -> str:
    if value is None:
        return "NA"
    if signed and value >= 0:
        return f"+{value:.3f}"
    return f"{value:.3f}"


def write_delta_row(
    lines: List[str], result: CaseResult, baseline: Optional[CaseResult]
) -> None:
    fields = [
        "avg_request_accept_latency_ns",
        "avg_total_transaction_latency_ns",
        "max_total_transaction_latency_ns",
    ]

    cells = [result.policy, result.status]
    for field in fields:
        value = decimal_metric(result, field)
        baseline_value = decimal_metric(baseline, field)
        delta = None if value is None or baseline_value is None else value - baseline_value
        cells.append(format_decimal(value))
        cells.append(format_decimal(delta, signed=True))

    cells.append(result.error)
    lines.append("| " + " | ".join(cells) + " |")


def baseline_status_line(baseline: Optional[CaseResult]) -> str:
    if baseline is None:
        return "Baseline status: missing; deltas unavailable."

    if baseline.status != "OK":
        error = f" Error: {baseline.error}" if baseline.error else ""
        return f"Baseline status: FAIL; deltas unavailable.{error}"

    return "Baseline status: OK."


def write_timeline_section(lines: List[str], result: CaseResult) -> None:
    lines.append(f"### {result.policy}")
    lines.append("")

    if result.status != "OK":
        error = f" Error: {result.error}" if result.error else ""
        lines.append(f"Case status: FAIL; delta unavailable.{error}")
        lines.append("")
        return

    lines.append(
        "| txn_id | command | request_accept_latency_ns | "
        "total_transaction_latency_ns | sanity_status |"
    )
    lines.append("| --- | --- | ---: | ---: | --- |")
    for row in result.timeline:
        lines.append(
            "| {txn_id} | {command} | {request_accept_latency_ns} | "
            "{total_transaction_latency_ns} | {sanity_status} |".format(**row)
        )
    lines.append("")


def policy_observation(policy: str, result: CaseResult) -> str:
    if result.status != "OK":
        return f"- {policy}: no timeline comparison because the case failed."

    latency_by_txn = {
        row["txn_id"]: row["request_accept_latency_ns"] for row in result.timeline
    }

    if policy == "priority_101":
        return (
            "- priority_101: 101001/101002 request_accept_latency_ns = "
            f"{latency_by_txn.get('101001', 'NA')}/"
            f"{latency_by_txn.get('101002', 'NA')}; "
            f"102001 = {latency_by_txn.get('102001', 'NA')}."
        )

    if policy == "priority_102":
        return (
            "- priority_102: 102001/102002 request_accept_latency_ns = "
            f"{latency_by_txn.get('102001', 'NA')}/"
            f"{latency_by_txn.get('102002', 'NA')}; "
            f"101001 = {latency_by_txn.get('101001', 'NA')}."
        )

    return (
        "- fifo: request_accept_latency_ns follows the pending-request arrival "
        f"order; 101001 = {latency_by_txn.get('101001', 'NA')}, "
        f"102001 = {latency_by_txn.get('102001', 'NA')}."
    )


def write_comparison_md(path: Path, results: List[CaseResult]) -> None:
    by_policy = {result.policy: result for result in results}
    baseline = by_policy.get("fifo")
    lines = [
        "# AT Arbitration Sweep Comparison",
        "",
        "Baseline policy: fifo",
        baseline_status_line(baseline),
        "",
        "## Run-Level Deltas vs fifo",
        "",
        "| policy | status | avg_request_accept_latency_ns | delta | "
        "avg_total_transaction_latency_ns | delta | "
        "max_total_transaction_latency_ns | delta | error |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]

    for result in results:
        write_delta_row(lines, result, baseline)

    lines.extend(["", "## Policy Observations", ""])
    for result in results:
        lines.append(policy_observation(result.policy, result))

    lines.extend(["", "## Per-Transaction Timeline", ""])
    for result in results:
        write_timeline_section(lines, result)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    policies = args.policy if args.policy else POLICIES
    binary = resolve_repo_path(args.binary)
    output_dir = resolve_repo_path(args.output_dir)
    analyzer = Path(__file__).resolve().with_name("analyze_phase_trace.py")

    results: List[CaseResult] = []

    for policy in policies:
        print(f"[sweep] running policy={policy}")
        result = run_case(policy, binary=binary, output_dir=output_dir, analyzer=analyzer)
        results.append(result)
        if result.status == "OK":
            print(f"[sweep] policy={policy} status=OK")
        else:
            print(f"[sweep] policy={policy} status=FAIL error={result.error}")
            if not args.keep_going:
                break

    write_summary_csv(output_dir / "summary.csv", results)
    write_comparison_md(output_dir / "comparison.md", results)

    print(f"[sweep] summary: {output_dir / 'summary.csv'}")
    print(f"[sweep] comparison: {output_dir / 'comparison.md'}")

    if any(result.status != "OK" for result in results):
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
