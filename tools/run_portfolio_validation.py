#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


SCHEMA_VERSION = "p0.5"


@dataclass(frozen=True)
class CsvOutputCheck:
    path: Path
    min_rows: int
    claim_boundary: Optional[str]
    schema_version: Optional[str]
    required_columns: Tuple[str, ...] = ()
    min_unique_values: Optional[Dict[str, int]] = None
    required_values: Optional[Dict[str, Tuple[str, ...]]] = None


@dataclass(frozen=True)
class TextOutputCheck:
    path: Path
    required_fragments: Tuple[str, ...]
    case_sensitive: bool = False


@dataclass(frozen=True)
class ProjectCheck:
    name: str
    command: List[str]
    pass_markers: List[str]
    project_labels: List[str]
    stage: str = "stage1"
    build_command: Optional[List[str]] = None
    csv_outputs: Tuple[CsvOutputCheck, ...] = ()
    text_outputs: Tuple[TextOutputCheck, ...] = ()
    executable_candidates: Tuple[Path, ...] = ()
    executable_args: Tuple[str, ...] = ()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Project P portfolio evidence validation harness."
    )
    parser.add_argument(
        "--at-build-dir",
        default="build-at",
        help=(
            "Existing AT CMake build directory. The harness uses named target "
            "builds and does not configure it."
        ),
    )
    parser.add_argument(
        "--skip-lt",
        action="store_true",
        help="Skip Project K/L LT validation.",
    )
    parser.add_argument(
        "--skip-at",
        action="store_true",
        help="Skip Project AT-1/AT-2/AT-3/AT-4/AT-5/AT-6/AT-7/AT-8 validation.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print validation commands without running demos or checking PASS markers.",
    )
    return parser.parse_args()


def format_command(command: Sequence[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def cmake_build_command(build_dir: str, target: str) -> List[str]:
    return ["cmake", "--build", build_dir, "--target", target, "-j"]


def build_checks(args: argparse.Namespace) -> List[ProjectCheck]:
    python = sys.executable
    checks: List[ProjectCheck] = []

    if not args.skip_at:
        checks.extend(
            [
                ProjectCheck(
                    name="Project AT-1",
                    project_labels=["AT-1"],
                    build_command=cmake_build_command(
                        args.at_build_dir,
                        "project_at1_four_phase_memory_timing",
                    ),
                    command=[
                        python,
                        "examples/at/tools/demo_project_at1_four_phase_memory_timing.py",
                        "--build-dir",
                        args.at_build_dir,
                        "--no-build",
                    ],
                    pass_markers=[
                        "Project AT-1 Four-Phase AT Memory Transaction Timing Lab PASS",
                    ],
                ),
                ProjectCheck(
                    name="Project AT-2",
                    project_labels=["AT-2"],
                    build_command=cmake_build_command(
                        args.at_build_dir,
                        "project_at2_multi_initiator_arbitration",
                    ),
                    command=[
                        python,
                        "examples/at/tools/demo_project_at2_multi_initiator_arbitration.py",
                        "--build-dir",
                        args.at_build_dir,
                        "--no-build",
                    ],
                    pass_markers=[
                        "Project AT-2 Multi-Initiator AT Arbitration and Contention Lab PASS",
                    ],
                ),
                ProjectCheck(
                    name="Project AT-3",
                    project_labels=["AT-3"],
                    build_command=cmake_build_command(
                        args.at_build_dir,
                        "project_at3_qos_sensitivity_sla",
                    ),
                    command=[
                        python,
                        "examples/at/tools/demo_project_at3_qos_sensitivity_sla.py",
                        "--build-dir",
                        args.at_build_dir,
                        "--no-build",
                    ],
                    pass_markers=[
                        "Project AT-3 QoS Sensitivity and SLA Violation Lab PASS",
                    ],
                ),
                ProjectCheck(
                    name="Project AT-4",
                    project_labels=["AT-4"],
                    build_command=cmake_build_command(
                        args.at_build_dir,
                        "project_at4_cache_mshr_pressure",
                    ),
                    command=[
                        python,
                        "examples/at/tools/demo_at4_cache_mshr_pressure.py",
                        "--at-build-dir",
                        args.at_build_dir,
                    ],
                    pass_markers=[
                        "Project AT-4 Cache-like Shared Resource and MSHR Pressure Lab PASS",
                        "cases=7",
                        "initiators=3",
                        "claim_boundary=PASS",
                        "schema_version=at4.0",
                    ],
                    csv_outputs=(
                        CsvOutputCheck(
                            path=Path(
                                "examples/at/results/"
                                "project_at4_cache_mshr_pressure/"
                                "project_at4_summary.csv"
                            ),
                            min_rows=21,
                            claim_boundary="PASS",
                            schema_version="at4.0",
                        ),
                        CsvOutputCheck(
                            path=Path(
                                "examples/at/results/"
                                "project_at4_cache_mshr_pressure/"
                                "project_at4_policy_sweep.csv"
                            ),
                            min_rows=7,
                            claim_boundary="PASS",
                            schema_version="at4.0",
                        ),
                        CsvOutputCheck(
                            path=Path(
                                "examples/at/results/"
                                "project_at4_cache_mshr_pressure/"
                                "project_at4_recommendations.csv"
                            ),
                            min_rows=7,
                            claim_boundary="PASS",
                            schema_version="at4.0",
                        ),
                    ),
                    text_outputs=(
                        TextOutputCheck(
                            path=Path(
                                "examples/at/results/"
                                "project_at4_cache_mshr_pressure/"
                                "project_at4_report.md"
                            ),
                            required_fragments=(
                                "Claim boundary",
                                "MSHR",
                                "interference",
                                "diminishing",
                            ),
                        ),
                    ),
                ),
                ProjectCheck(
                    name="Project AT-5",
                    project_labels=["AT-5"],
                    build_command=cmake_build_command(
                        args.at_build_dir,
                        "project_at5_backpressure_qos_collapse",
                    ),
                    command=[
                        "python3",
                        "-B",
                        "examples/at/tools/demo_at5_backpressure_qos_collapse.py",
                        "--at-build-dir",
                        args.at_build_dir,
                    ],
                    pass_markers=[
                        "Project AT-5 Memory System Backpressure and QoS Collapse Lab PASS",
                        "cases=7",
                        "initiators=3",
                        "policies=5",
                        "claim_boundary=PASS",
                        "schema_version=at5.0",
                    ],
                    csv_outputs=(
                        CsvOutputCheck(
                            path=Path(
                                "examples/at/results/"
                                "project_at5_backpressure_qos_collapse/"
                                "project_at5_summary.csv"
                            ),
                            min_rows=21,
                            claim_boundary="PASS",
                            schema_version="at5.0",
                            required_columns=(
                                "case_name",
                                "initiator",
                                "policy",
                                "transactions",
                                "sla_target_ns",
                                "sla_violation_ratio",
                                "avg_total_latency_ns",
                                "p95_total_latency_ns",
                                "p99_total_latency_ns",
                                "throughput_txn_per_us",
                                "ingress_queue_capacity",
                                "downstream_queue_capacity",
                                "queue_full_events",
                                "backpressure_stall_ns",
                                "initiator_blocked_ns",
                                "memory_service_latency_ns",
                                "service_utilization",
                                "saturation_ratio",
                                "fairness_index",
                                "starvation_proxy",
                                "collapse_score",
                                "dominant_bottleneck",
                                "claim_boundary",
                                "schema_version",
                            ),
                            min_unique_values={
                                "case_name": 7,
                                "initiator": 3,
                            },
                        ),
                        CsvOutputCheck(
                            path=Path(
                                "examples/at/results/"
                                "project_at5_backpressure_qos_collapse/"
                                "project_at5_policy_sweep.csv"
                            ),
                            min_rows=35,
                            claim_boundary="PASS",
                            schema_version="at5.0",
                            required_columns=("recommended_action",),
                            min_unique_values={"policy": 5},
                        ),
                        CsvOutputCheck(
                            path=Path(
                                "examples/at/results/"
                                "project_at5_backpressure_qos_collapse/"
                                "project_at5_recommendations.csv"
                            ),
                            min_rows=7,
                            claim_boundary="PASS",
                            schema_version="at5.0",
                            required_columns=(
                                "recommended_action",
                                "primary_bottleneck",
                                "confidence",
                            ),
                        ),
                    ),
                    text_outputs=(
                        TextOutputCheck(
                            path=Path(
                                "examples/at/results/"
                                "project_at5_backpressure_qos_collapse/"
                                "project_at5_report.md"
                            ),
                            required_fragments=(
                                "Claim boundary",
                                "backpressure",
                                "saturation",
                                "collapse",
                                "QoS alone",
                            ),
                        ),
                    ),
                ),
                ProjectCheck(
                    name="Project AT-6",
                    project_labels=["AT-6"],
                    stage="stage2",
                    build_command=cmake_build_command(
                        args.at_build_dir,
                        "project_at6_heterogeneous_soc_fabric",
                    ),
                    command=[],
                    executable_candidates=(
                        Path(args.at_build_dir)
                        / "project_at6_heterogeneous_soc_fabric",
                        Path(args.at_build_dir)
                        / "examples/at/project_at6_heterogeneous_soc_fabric",
                    ),
                    executable_args=("--no-trace",),
                    pass_markers=[
                        "Project AT-6 PASS",
                        "cases=5",
                        "claim_boundary=PASS",
                        "schema_version=at6.0",
                    ],
                    csv_outputs=(
                        CsvOutputCheck(
                            path=Path(
                                "examples/at/results/"
                                "project_at6_heterogeneous_soc_fabric/"
                                "summary.csv"
                            ),
                            min_rows=5,
                            claim_boundary=None,
                            schema_version=None,
                            required_columns=(
                                "case",
                                "total_transactions",
                                "sim_time_ns",
                                "avg_latency_ns",
                                "p95_latency_ns",
                                "p99_latency_ns",
                                "fabric_queue_peak",
                                "starvation_events",
                                "cpu_p99_latency_ns",
                                "npu_throughput_txn_per_us",
                                "npu_bandwidth_share",
                                "dma_bandwidth_share",
                                "isp_p99_latency_ns",
                                "isp_sla_violation_ratio",
                            ),
                            required_values={
                                "case": (
                                    "baseline_rr",
                                    "priority_latency",
                                    "bandwidth_cap_npu",
                                    "dma_stress",
                                    "mixed_stress",
                                ),
                            },
                        ),
                    ),
                    text_outputs=(
                        TextOutputCheck(
                            path=Path(
                                "examples/at/results/"
                                "project_at6_heterogeneous_soc_fabric/"
                                "comparison.md"
                            ),
                            required_fragments=(
                                "bounded AT-level synthetic",
                                "does not claim Apple Silicon simulation",
                                "real NoC behavior",
                                "cycle-accurate modeling",
                                "silicon validation",
                                "production signoff",
                            ),
                            case_sensitive=True,
                        ),
                    ),
                ),
                ProjectCheck(
                    name="Project AT-7",
                    project_labels=["AT-7"],
                    stage="stage2",
                    build_command=cmake_build_command(
                        args.at_build_dir,
                        "project_at7_gpu_like_throughput_saturation",
                    ),
                    command=[],
                    executable_candidates=(
                        Path(args.at_build_dir)
                        / "project_at7_gpu_like_throughput_saturation",
                        Path(args.at_build_dir)
                        / "examples/at/project_at7_gpu_like_throughput_saturation",
                    ),
                    pass_markers=[
                        "Project AT-7 PASS",
                        "cases=6",
                        "claim_boundary=PASS",
                        "schema_version=at7.0",
                    ],
                    csv_outputs=(
                        CsvOutputCheck(
                            path=Path(
                                "examples/at/results/"
                                "project_at7_gpu_like_throughput_saturation/"
                                "summary.csv"
                            ),
                            min_rows=6,
                            claim_boundary=None,
                            schema_version=None,
                            required_columns=(
                                "case",
                                "num_lanes",
                                "requests_per_lane",
                                "total_requests",
                                "sim_time_ns",
                                "avg_latency_ns",
                                "p50_latency_ns",
                                "p95_latency_ns",
                                "p99_latency_ns",
                                "max_latency_ns",
                                "throughput_req_per_us",
                                "effective_bandwidth_bytes_per_ns",
                                "memory_utilization_ratio",
                                "avg_queue_delay_ns",
                                "p95_queue_delay_ns",
                                "queue_peak",
                                "avg_outstanding",
                                "peak_outstanding",
                                "stall_events",
                                "stall_ratio",
                                "hidden_latency_ns",
                                "exposed_stall_ns",
                                "saturation_flag",
                                "knee_point_hint",
                            ),
                            required_values={
                                "case": (
                                    "low_occupancy",
                                    "balanced_occupancy",
                                    "high_occupancy",
                                    "bandwidth_saturation",
                                    "bursty_stress",
                                    "throttled_occupancy",
                                ),
                            },
                        ),
                    ),
                    text_outputs=(
                        TextOutputCheck(
                            path=Path(
                                "examples/at/results/"
                                "project_at7_gpu_like_throughput_saturation/"
                                "comparison.md"
                            ),
                            required_fragments=(
                                "bounded AT-level synthetic",
                                (
                                    "It does not claim NVIDIA GPU simulation, "
                                    "real GPU behavior, CUDA execution modeling, "
                                    "real HBM-controller behavior, "
                                    "cycle-accurate modeling, silicon validation, "
                                    "or production signoff."
                                ),
                                "Claim boundary",
                                "Schema version: `at7.0`",
                            ),
                            case_sensitive=True,
                        ),
                    ),
                ),
                ProjectCheck(
                    name="Project AT-8",
                    project_labels=["AT-8"],
                    stage="stage2",
                    build_command=cmake_build_command(
                        args.at_build_dir,
                        "project_at8_amba_noc_qos_coherency_boundary",
                    ),
                    command=[],
                    executable_candidates=(
                        Path(args.at_build_dir)
                        / "project_at8_amba_noc_qos_coherency_boundary",
                        Path(args.at_build_dir)
                        / "examples/at/project_at8_amba_noc_qos_coherency_boundary",
                    ),
                    pass_markers=[
                        "Project AT-8 PASS",
                        "cases=6",
                        "claim_boundary=PASS",
                        "schema_version=at8.0",
                    ],
                    csv_outputs=(
                        CsvOutputCheck(
                            path=Path(
                                "examples/at/results/"
                                "project_at8_amba_noc_qos_coherency_boundary/"
                                "summary.csv"
                            ),
                            min_rows=6,
                            claim_boundary=None,
                            schema_version=None,
                            required_columns=(
                                "case",
                                "total_transactions",
                                "sim_time_ns",
                                "avg_latency_ns",
                                "p50_latency_ns",
                                "p95_latency_ns",
                                "p99_latency_ns",
                                "max_latency_ns",
                                "throughput_txn_per_us",
                                "route_queue_peak",
                                "local_route_utilization",
                                "shared_route_utilization",
                                "boundary_route_utilization",
                                "avg_route_delay_ns",
                                "p95_route_delay_ns",
                                "ordering_delay_ns",
                                "boundary_penalty_ns",
                                "coherency_boundary_events",
                                "ordering_serialization_events",
                                "read_avg_latency_ns",
                                "read_p95_latency_ns",
                                "write_avg_latency_ns",
                                "write_p95_latency_ns",
                                "latency_high_p99_ns",
                                "best_effort_p99_ns",
                                "bulk_low_p99_ns",
                                "starvation_events",
                                "qos_protection_score",
                                "collapse_score",
                                "recommendation",
                            ),
                            required_values={
                                "case": (
                                    "baseline_qos_rr",
                                    "latency_qos_priority",
                                    "bulk_dma_pressure",
                                    "boundary_crossing_stress",
                                    "route_hotspot",
                                    "mixed_qos_collapse",
                                ),
                            },
                        ),
                    ),
                    text_outputs=(
                        TextOutputCheck(
                            path=Path(
                                "examples/at/results/"
                                "project_at8_amba_noc_qos_coherency_boundary/"
                                "comparison.md"
                            ),
                            required_fragments=(
                                "bounded AT-level synthetic",
                                (
                                    "AMBA-inspired NoC QoS and "
                                    "coherency-boundary exploration"
                                ),
                                (
                                    "It does not claim Arm CHI compliance, "
                                    "AXI compliance, ACE compliance, "
                                    "real AMBA protocol behavior, "
                                    "real NoC behavior, real cache coherency, "
                                    "cycle-accurate modeling, silicon validation, "
                                    "or production signoff."
                                ),
                                "Claim Boundary",
                                "Schema version: `at8.0`",
                            ),
                            case_sensitive=True,
                        ),
                    ),
                ),
            ]
        )

    if not args.skip_lt:
        checks.append(
            ProjectCheck(
                name="Project K/L",
                project_labels=["K", "L"],
                command=[
                    python,
                    "examples/lt/tools/demo_project_k_workload_bottleneck_lab.py",
                    "--no-build",
                ],
                pass_markers=[
                    "Project K Workload-Aware Memory Bottleneck Characterization MVP PASS",
                    "Project L Evidence-Driven Memory Architecture Recommendation Lab PASS",
                ],
            )
        )

    return checks


def print_failure_output(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print("[stdout]")
        print(result.stdout.rstrip())
    if result.stderr:
        print("[stderr]")
        print(result.stderr.rstrip())


def run_command(
    root: Path, command: Sequence[str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=str(root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def resolve_command(root: Path, check: ProjectCheck) -> Optional[List[str]]:
    if not check.executable_candidates:
        return check.command

    for candidate in check.executable_candidates:
        full_path = root / candidate
        if full_path.exists():
            return [str(candidate), *check.executable_args]
    return None


def validate_csv_output(root: Path, check: CsvOutputCheck) -> List[str]:
    full_path = root / check.path
    errors: List[str] = []

    if not full_path.exists():
        return [f"missing file: {check.path}"]

    with full_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]

    missing_columns = [
        column for column in check.required_columns if column not in headers
    ]
    if missing_columns:
        errors.append(
            f"{check.path}: missing required column(s): "
            f"{', '.join(missing_columns)}"
        )

    if len(rows) < check.min_rows:
        errors.append(
            f"{check.path}: expected at least {check.min_rows} data rows, "
            f"found {len(rows)}"
        )

    expected_columns = (
        ("claim_boundary", check.claim_boundary),
        ("schema_version", check.schema_version),
    )
    for column, expected in expected_columns:
        if expected is None:
            continue
        bad_values = sorted(
            {
                row.get(column, "")
                for row in rows
                if row.get(column, "") != expected
            }
        )
        if bad_values:
            errors.append(
                f"{check.path}: column {column} expected {expected}, "
                f"found {bad_values}"
            )

    if check.min_unique_values:
        for column, minimum in check.min_unique_values.items():
            if column not in headers:
                errors.append(
                    f"{check.path}: missing required column for unique check: {column}"
                )
                continue
            unique_values = {row.get(column, "") for row in rows if row.get(column, "")}
            if len(unique_values) < minimum:
                errors.append(
                    f"{check.path}: expected at least {minimum} unique {column} "
                    f"values, found {len(unique_values)}"
                )

    if check.required_values:
        for column, expected_values in check.required_values.items():
            if column not in headers:
                errors.append(
                    f"{check.path}: missing required column for value check: {column}"
                )
                continue
            actual_values = {row.get(column, "") for row in rows}
            missing_values = [
                value for value in expected_values if value not in actual_values
            ]
            if missing_values:
                errors.append(
                    f"{check.path}: column {column} missing required value(s): "
                    f"{', '.join(missing_values)}"
                )

    return errors


def validate_text_output(root: Path, check: TextOutputCheck) -> List[str]:
    full_path = root / check.path
    if not full_path.exists():
        return [f"missing file: {check.path}"]

    text = full_path.read_text(encoding="utf-8")
    haystack = text if check.case_sensitive else text.lower()
    missing = []
    for fragment in check.required_fragments:
        needle = fragment if check.case_sensitive else fragment.lower()
        if needle not in haystack:
            missing.append(fragment)

    if missing:
        return [f"{check.path}: missing text fragment(s): {', '.join(missing)}"]
    return []


def validate_outputs(root: Path, check: ProjectCheck) -> List[str]:
    errors: List[str] = []
    for csv_output in check.csv_outputs:
        errors.extend(validate_csv_output(root, csv_output))
    for text_output in check.text_outputs:
        errors.extend(validate_text_output(root, text_output))
    return errors


def run_check(root: Path, check: ProjectCheck) -> bool:
    print(f"[project-p] START {check.name}")
    if check.build_command is not None:
        print(f"[project-p] BUILD {check.name}: {format_command(check.build_command)}")
        build_result = run_command(root, check.build_command)
        if build_result.returncode != 0:
            print(f"[project-p] FAIL {check.name}: build returncode={build_result.returncode}")
            print_failure_output(build_result)
            return False

    command = resolve_command(root, check)
    if command is None:
        print(f"[project-p] FAIL {check.name}: executable not found")
        for candidate in check.executable_candidates:
            print(f"  missing candidate: {candidate}")
        return False

    result = run_command(root, command)

    combined_output = result.stdout + result.stderr
    missing_markers = [
        marker for marker in check.pass_markers if marker not in combined_output
    ]

    if result.returncode != 0:
        print(f"[project-p] FAIL {check.name}: returncode={result.returncode}")
        print_failure_output(result)
        return False

    if missing_markers:
        print(f"[project-p] FAIL {check.name}: missing PASS marker(s)")
        for marker in missing_markers:
            print(f"  missing: {marker}")
        print_failure_output(result)
        return False

    output_errors = validate_outputs(root, check)
    if output_errors:
        print(f"[project-p] FAIL {check.name}: output validation failed")
        for error in output_errors:
            print(f"  {error}")
        print_failure_output(result)
        return False

    print(f"[project-p] PASS {check.name}")
    return True


def main() -> int:
    args = parse_args()
    root = repo_root()
    checks = build_checks(args)

    if not checks:
        print("[project-p] No projects selected. Use default options or remove skip flags.")
        return 2

    if args.dry_run:
        for check in checks:
            if check.build_command is not None:
                print(
                    f"[project-p] DRY-RUN {check.name}: "
                    f"{format_command(check.build_command)}"
                )
            command = check.command
            if check.executable_candidates:
                candidate_text = " | ".join(
                    str(candidate) for candidate in check.executable_candidates
                )
                command = [f"<first-existing:{candidate_text}>", *check.executable_args]
            print(f"[project-p] DRY-RUN {check.name}: {format_command(command)}")
        print("Portfolio Evidence Pack DRY-RUN")
        print(f"schema_version={SCHEMA_VERSION}")
        return 0

    stage1_labels: List[str] = []
    stage2_labels: List[str] = []
    for check in checks:
        if not run_check(root, check):
            print("Portfolio Evidence Pack FAIL")
            print(f"failed_project={check.name}")
            print(f"schema_version={SCHEMA_VERSION}")
            return 1
        if check.stage == "stage2":
            stage2_labels.extend(check.project_labels)
        else:
            stage1_labels.extend(check.project_labels)

    print("Portfolio Evidence Pack PASS")
    print(f"stage1_projects={','.join(stage1_labels)}")
    print(f"stage2_projects={','.join(stage2_labels)}")
    print(f"projects={','.join(stage1_labels + stage2_labels)}")
    print("claim_boundary=PASS")
    print(f"schema_version={SCHEMA_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
