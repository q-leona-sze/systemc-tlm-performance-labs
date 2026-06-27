#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


SCHEMA_VERSION = "p0.5"
DEFAULT_OUTPUT = "docs/generated/portfolio_evidence_summary.md"


@dataclass(frozen=True)
class CsvSpec:
    title: str
    path: Path
    preferred_columns: Sequence[str]
    reproduce_hint: str
    context_lines: Sequence[str] = ()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the Project P portfolio evidence summary from CSV outputs."
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Output markdown path. Relative paths are resolved from repo root.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero if any required CSV has not been generated yet.",
    )
    return parser.parse_args()


def normalize_field(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


FIELD_ALIASES: Dict[str, Sequence[str]] = {
    "throughput": (
        "throughput_txn_per_us",
        "aggregate_throughput_txn_per_us",
    ),
    "bank_conflict_ratio": (
        "bank_conflict_ratio_pct",
        "bank_conflict_ratio",
        "bank_conflict_proxy",
    ),
    "dominant_bottleneck": (
        "dominant_bottleneck",
        "primary_bottleneck",
    ),
    "p99_latency_ns": (
        "p99_latency_ns",
        "max_p99_total_latency_ns",
        "max_p99_response_latency_ns",
    ),
}


def candidates_for(preferred: str) -> List[str]:
    aliases = FIELD_ALIASES.get(preferred, ())
    return [preferred, *aliases]


def find_column(headers: Sequence[str], preferred: str) -> str:
    normalized_headers = {normalize_field(header): header for header in headers}
    for candidate in candidates_for(preferred):
        normalized_candidate = normalize_field(candidate)
        if normalized_candidate in normalized_headers:
            return normalized_headers[normalized_candidate]

    for candidate in candidates_for(preferred):
        normalized_candidate = normalize_field(candidate)
        for header in headers:
            normalized_header = normalize_field(header)
            if (
                normalized_candidate
                and (
                    normalized_candidate in normalized_header
                    or normalized_header in normalized_candidate
                )
            ):
                return header

    return ""


def select_columns(headers: Sequence[str], preferred: Sequence[str]) -> List[str]:
    selected: List[str] = []
    for preferred_column in preferred:
        column = find_column(headers, preferred_column)
        if column and column not in selected:
            selected.append(column)

    for header in headers:
        if len(selected) >= 10:
            break
        if header not in selected:
            selected.append(header)

    return selected[:10]


def read_csv_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return headers, rows


def escape_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def markdown_table(headers: Sequence[str], rows: Sequence[Dict[str, str]]) -> str:
    if not headers:
        return "_Generated CSV exists but has no header._"
    if not rows:
        return "_Generated CSV exists but contains no data rows._"

    lines = [
        "| " + " | ".join(escape_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(escape_cell(row.get(header, "")) for header in headers)
            + " |"
        )
    return "\n".join(lines)


def specs() -> List[CsvSpec]:
    return [
        CsvSpec(
            title="2. Project K: LT Bottleneck Summary",
            path=Path(
                "examples/lt/results/project_k_workload_bottleneck/"
                "project_k_workload_bottleneck_summary.csv"
            ),
            preferred_columns=(
                "workload",
                "pattern_class",
                "avg_latency_ns",
                "p95_latency_ns",
                "p99_latency_ns",
                "throughput",
                "bank_conflict_ratio",
                "dominant_bottleneck",
                "claim_boundary",
            ),
            reproduce_hint="python3 examples/lt/tools/demo_project_k_workload_bottleneck_lab.py",
        ),
        CsvSpec(
            title="3. Project L: Recommendation Summary",
            path=Path(
                "examples/lt/results/project_l_memory_architecture_recommendation/"
                "project_l_recommendations.csv"
            ),
            preferred_columns=(
                "workload",
                "primary_bottleneck",
                "confidence",
                "recommended_action",
                "recommendation_priority",
                "evidence_summary",
                "claim_boundary",
            ),
            reproduce_hint="python3 examples/lt/tools/demo_project_k_workload_bottleneck_lab.py",
        ),
        CsvSpec(
            title="4. Project AT-1: Transaction Timing Summary",
            path=Path(
                "examples/at/results/project_at1_four_phase_memory_timing/"
                "project_at1_summary.csv"
            ),
            preferred_columns=(
                "case_name",
                "num_transactions",
                "avg_request_accept_latency_ns",
                "p95_request_accept_latency_ns",
                "avg_target_service_latency_ns",
                "avg_response_latency_ns",
                "avg_initiator_blocked_ns",
                "backpressure_events",
                "claim_boundary",
            ),
            reproduce_hint=(
                "python3 examples/at/tools/demo_project_at1_four_phase_memory_timing.py "
                "--build-dir build-at"
            ),
        ),
        CsvSpec(
            title="5. Project AT-2: Arbitration / Contention Summary",
            path=Path(
                "examples/at/results/project_at2_multi_initiator_arbitration/"
                "project_at2_policy_summary.csv"
            ),
            preferred_columns=(
                "case_name",
                "policy",
                "total_transactions",
                "total_backpressure_events",
                "aggregate_throughput_txn_per_us",
                "max_p99_response_latency_ns",
                "fairness_index",
                "worst_initiator",
                "claim_boundary",
            ),
            reproduce_hint=(
                "python3 examples/at/tools/demo_project_at2_multi_initiator_arbitration.py "
                "--build-dir build-at"
            ),
        ),
        CsvSpec(
            title="6. Project AT-3: QoS / SLA Summary",
            path=Path(
                "examples/at/results/project_at3_qos_sensitivity_sla/"
                "project_at3_policy_sweep.csv"
            ),
            preferred_columns=(
                "case_name",
                "weight_vector",
                "queue_depth",
                "service_latency_ns",
                "total_sla_violations",
                "max_sla_violation_rate",
                "max_p99_total_latency_ns",
                "fairness_index",
                "worst_initiator",
                "claim_boundary",
            ),
            reproduce_hint=(
                "python3 examples/at/tools/demo_project_at3_qos_sensitivity_sla.py "
                "--build-dir build-at"
            ),
        ),
        CsvSpec(
            title="7. Project AT-3: Architecture Recommendations",
            path=Path(
                "examples/at/results/project_at3_qos_sensitivity_sla/"
                "project_at3_recommendations.csv"
            ),
            preferred_columns=(
                "case_name",
                "primary_bottleneck",
                "recommended_action",
                "recommendation_priority",
                "evidence_summary",
                "protected_initiator",
                "worst_initiator",
                "claim_boundary",
            ),
            reproduce_hint=(
                "python3 examples/at/tools/demo_project_at3_qos_sensitivity_sla.py "
                "--build-dir build-at"
            ),
        ),
        CsvSpec(
            title="8. Project AT-4: Cache-like Shared Resource and MSHR Pressure Lab",
            path=Path(
                "examples/at/results/project_at4_cache_mshr_pressure/"
                "project_at4_policy_sweep.csv"
            ),
            preferred_columns=(
                "case_name",
                "hit_rate",
                "miss_rate",
                "mshr_capacity",
                "mshr_full_events",
                "interference_score",
                "pollution_proxy",
                "p95_total_latency_ns",
                "p99_total_latency_ns",
                "claim_boundary",
            ),
            reproduce_hint=(
                "python3 examples/at/tools/demo_at4_cache_mshr_pressure.py "
                "--at-build-dir build-at"
            ),
            context_lines=(
                "Project AT-4 covers 7 cases and 3 initiators: `cpu0`, `dma0`, and `accel0`.",
                (
                    "It highlights locality / hit-miss trend, MSHR-like outstanding miss "
                    "pressure, shared interference / pollution proxy, tail latency p95/p99, "
                    "and diminishing return when memory service dominates."
                ),
                (
                    "claim boundary: PASS means bounded AT-level architecture exploration only; "
                    "it is not real cache coherence, a real L1-L2-L3 hierarchy, cycle accuracy, "
                    "or silicon validation."
                ),
            ),
        ),
        CsvSpec(
            title="9. Project AT-4: Architecture Recommendations",
            path=Path(
                "examples/at/results/project_at4_cache_mshr_pressure/"
                "project_at4_recommendations.csv"
            ),
            preferred_columns=(
                "case_name",
                "primary_bottleneck",
                "recommended_action",
                "recommendation_priority",
                "evidence_summary",
                "locality_signal",
                "mshr_pressure_signal",
                "interference_signal",
                "pollution_signal",
                "claim_boundary",
            ),
            reproduce_hint=(
                "python3 examples/at/tools/demo_at4_cache_mshr_pressure.py "
                "--at-build-dir build-at"
            ),
        ),
        CsvSpec(
            title="10. Project AT-5: Backpressure / QoS Collapse Summary",
            path=Path(
                "examples/at/results/project_at5_backpressure_qos_collapse/"
                "project_at5_policy_sweep.csv"
            ),
            preferred_columns=(
                "case_name",
                "policy",
                "cpu_rt_p95_ns",
                "cpu_rt_sla_violation_ratio",
                "system_throughput_txn_per_us",
                "service_utilization",
                "queue_full_events",
                "backpressure_stall_ns",
                "collapse_score",
                "claim_boundary",
            ),
            reproduce_hint=(
                "python3 -B examples/at/tools/demo_at5_backpressure_qos_collapse.py "
                "--at-build-dir build-at"
            ),
            context_lines=(
                (
                    "Project AT-5 covers bounded queues and downstream saturation: "
                    "`cpu_rt`, `dma_bulk`, and `accel_burst` contend for a shared "
                    "downstream service under 5 synthetic QoS policies."
                ),
                (
                    "It highlights backpressure propagation and QoS collapse: "
                    "QoS alone can redistribute contention but cannot create "
                    "downstream service capacity."
                ),
                (
                    "PASS marker: `Project AT-5 Memory System Backpressure and "
                    "QoS Collapse Lab PASS`; claim boundary remains bounded "
                    "AT-level trend comparison only."
                ),
            ),
        ),
        CsvSpec(
            title="11. Project AT-5: Architecture Recommendations",
            path=Path(
                "examples/at/results/project_at5_backpressure_qos_collapse/"
                "project_at5_recommendations.csv"
            ),
            preferred_columns=(
                "case_name",
                "primary_bottleneck",
                "confidence",
                "recommended_action",
                "recommendation_priority",
                "qos_policy_best",
                "service_saturation_signal",
                "backpressure_signal",
                "sla_signal",
                "claim_boundary",
            ),
            reproduce_hint=(
                "python3 -B examples/at/tools/demo_at5_backpressure_qos_collapse.py "
                "--at-build-dir build-at"
            ),
            context_lines=(
                (
                    "Project AT-5 recommendations separate QoS policy choices from "
                    "capacity actions such as reducing memory service latency or "
                    "increasing bounded queue capacity."
                ),
            ),
        ),
        CsvSpec(
            title="12. Project AT-6: Heterogeneous SoC Shared Memory Fabric Summary",
            path=Path(
                "examples/at/results/project_at6_heterogeneous_soc_fabric/"
                "summary.csv"
            ),
            preferred_columns=(
                "case",
                "total_transactions",
                "p95_latency_ns",
                "p99_latency_ns",
                "fabric_queue_peak",
                "starvation_events",
                "cpu_p99_latency_ns",
                "npu_throughput_txn_per_us",
                "npu_bandwidth_share",
                "dma_bandwidth_share",
            ),
            reproduce_hint=(
                "./build-at/project_at6_heterogeneous_soc_fabric --no-trace"
            ),
            context_lines=(
                (
                    "Project AT-6 is the first Stage 2 lab in the portfolio "
                    "evidence harness."
                ),
                (
                    "It covers a bounded AT-level synthetic heterogeneous SoC "
                    "problem type: CPU-like, NPU-like, DMA-like, and ISP-like "
                    "traffic sharing one memory fabric."
                ),
                (
                    "claim boundary: PASS means bounded AT-level synthetic "
                    "architecture exploration only; it is not Apple Silicon "
                    "simulation, real NoC behavior, cycle-accurate modeling, "
                    "silicon validation, or production signoff."
                ),
            ),
        ),
        CsvSpec(
            title="13. Project AT-7: GPU-like Throughput Engine and Memory Saturation Summary",
            path=Path(
                "examples/at/results/"
                "project_at7_gpu_like_throughput_saturation/"
                "summary.csv"
            ),
            preferred_columns=(
                "case",
                "num_lanes",
                "requests_per_lane",
                "total_requests",
                "avg_latency_ns",
                "p95_latency_ns",
                "p99_latency_ns",
                "throughput_req_per_us",
                "effective_bandwidth_bytes_per_ns",
                "memory_utilization_ratio",
            ),
            reproduce_hint="./build-at/project_at7_gpu_like_throughput_saturation",
            context_lines=(
                (
                    "Project name: Project AT-7, GPU-like Throughput Engine "
                    "and Memory Saturation Lab."
                ),
                (
                    "Result files: "
                    "`examples/at/results/project_at7_gpu_like_throughput_saturation/summary.csv` "
                    "and "
                    "`examples/at/results/project_at7_gpu_like_throughput_saturation/comparison.md`."
                ),
                (
                    "Cases: `low_occupancy`, `balanced_occupancy`, "
                    "`high_occupancy`, `bandwidth_saturation`, "
                    "`bursty_stress`, and `throttled_occupancy`."
                ),
                (
                    "Key metrics: latency percentiles, throughput, effective "
                    "bandwidth, memory utilization, queue delay, outstanding "
                    "depth, stall ratio, hidden latency, exposed stall, "
                    "saturation flag, and knee-point hint."
                ),
                (
                    "Key observations: useful throughput improves from low to "
                    "balanced occupancy, high pressure approaches the knee, "
                    "bandwidth saturation mostly adds queue delay, burstiness "
                    "raises tail risk, and throttling gives a bounded safer "
                    "latency reference."
                ),
                (
                    "claim boundary: PASS means bounded AT-level synthetic "
                    "GPU-like throughput and memory saturation exploration "
                    "only; it does not claim NVIDIA GPU simulation, real GPU "
                    "behavior, CUDA execution modeling, real HBM-controller "
                    "behavior, cycle-accurate modeling, silicon validation, "
                    "or production signoff."
                ),
                "schema_version=at7.0",
            ),
        ),
        CsvSpec(
            title="14. Project AT-8: AMBA-inspired NoC QoS and Coherency Boundary Summary",
            path=Path(
                "examples/at/results/"
                "project_at8_amba_noc_qos_coherency_boundary/"
                "summary.csv"
            ),
            preferred_columns=(
                "case",
                "total_transactions",
                "avg_latency_ns",
                "p95_latency_ns",
                "p99_latency_ns",
                "throughput_txn_per_us",
                "route_queue_peak",
                "shared_route_utilization",
                "boundary_route_utilization",
                "collapse_score",
            ),
            reproduce_hint="./build-at/project_at8_amba_noc_qos_coherency_boundary",
            context_lines=(
                (
                    "Project name: Project AT-8, AMBA-inspired NoC QoS "
                    "and Coherency Boundary Lab."
                ),
                (
                    "Result files: "
                    "`examples/at/results/project_at8_amba_noc_qos_coherency_boundary/summary.csv` "
                    "and "
                    "`examples/at/results/project_at8_amba_noc_qos_coherency_boundary/comparison.md`."
                ),
                (
                    "Cases: `baseline_qos_rr`, `latency_qos_priority`, "
                    "`bulk_dma_pressure`, `boundary_crossing_stress`, "
                    "`route_hotspot`, and `mixed_qos_collapse`."
                ),
                (
                    "Key metrics: latency percentiles, throughput, route "
                    "queue peak, local/shared/boundary route utilization, "
                    "route delay, ordering delay, boundary penalty, "
                    "coherency-boundary events, read/write p95 latency, "
                    "QoS-class p99 latency, starvation events, protection "
                    "score, collapse score, and recommendation."
                ),
                (
                    "Key observations: QoS priority protects latency_high "
                    "traffic only within route-capacity bounds; bulk DMA "
                    "pressure raises read/write tail latency; boundary "
                    "crossing stress exposes ordering and serialization cost; "
                    "route hotspots can dominate QoS intent; mixed pressure "
                    "collapses into capacity or partitioning recommendations."
                ),
                (
                    "claim boundary: PASS means bounded AT-level synthetic "
                    "AMBA-inspired NoC QoS and coherency-boundary exploration "
                    "only; it does not claim Arm CHI compliance, AXI "
                    "compliance, ACE compliance, real AMBA protocol behavior, "
                    "real NoC behavior, real cache coherency, cycle-accurate "
                    "modeling, silicon validation, or production signoff."
                ),
                "schema_version=at8.0",
            ),
        ),
    ]


def section_for_spec(root: Path, spec: CsvSpec) -> Tuple[str, bool]:
    full_path = root / spec.path
    lines = [f"## {spec.title}", ""]

    if not full_path.exists():
        lines.extend(
            [
                "**Status:** Not generated yet.",
                "",
                f"Run `{spec.reproduce_hint}` to generate `{spec.path}`.",
                "",
            ]
        )
        return "\n".join(lines), True

    for context_line in spec.context_lines:
        lines.append(f"- {context_line}")
    if spec.context_lines:
        lines.append("")

    headers, rows = read_csv_rows(full_path)
    selected = select_columns(headers, spec.preferred_columns)
    lines.extend(
        [
            f"Source: `{spec.path}`",
            "",
            markdown_table(selected, rows),
            "",
        ]
    )
    return "\n".join(lines), False


def render_document(root: Path) -> Tuple[str, List[Path]]:
    lines = [
        "# Portfolio Evidence Summary",
        "",
        "由可复现 demo 输出生成。",
        "",
        f"- schema_version: `{SCHEMA_VERSION}`",
        "- claim_boundary: `PASS`",
        "- stage1_projects: `AT-1,AT-2,AT-3,AT-4,AT-5,K,L`",
        "- stage2_projects: `AT-6,AT-7,AT-8`",
        "- projects: `AT-1,AT-2,AT-3,AT-4,AT-5,K,L,AT-6,AT-7,AT-8`",
        "- portfolio_pass: `Portfolio Evidence Pack PASS`",
        "- portfolio_claim_boundary: `claim_boundary=PASS`",
        f"- portfolio_schema_version: `schema_version={SCHEMA_VERSION}`",
        "",
        "## 1. Validation Scope",
        "",
        "- Stage 1 projects: AT-1, AT-2, AT-3, AT-4, AT-5, K, L",
        "- Stage 2 projects: AT-6, AT-7, AT-8",
        "- Project K/L: LT bottleneck and recommendation",
        "- Project AT-1: four-phase transaction timing",
        "- Project AT-2: multi-initiator arbitration and contention",
        "- Project AT-3: QoS-like sensitivity and SLA violation analysis",
        "- Project AT-4: cache-like shared-resource and MSHR pressure analysis",
        "- Project AT-5: memory-system backpressure and QoS collapse analysis",
        "- Project AT-6: heterogeneous SoC shared-memory fabric pressure analysis",
        "- Project AT-7: GPU-like throughput engine and memory saturation analysis",
        "- Project AT-8: AMBA-inspired NoC QoS and coherency-boundary analysis",
        "",
    ]

    missing: List[Path] = []
    for spec in specs():
        section, is_missing = section_for_spec(root, spec)
        lines.append(section)
        if is_missing:
            missing.append(spec.path)

    lines.extend(
        [
            "## 15. What This Evidence Pack Supports",
            "",
            "- workload bottleneck reasoning",
            "- evidence-driven memory architecture recommendation",
            "- transaction phase timing analysis",
            "- arbitration, fairness, and tail-latency tradeoff discussion",
            "- QoS-like sensitivity discussion",
            "- SLA violation and recommendation discussion",
            "- locality, hit/miss trend, MSHR-like pressure, and shared-resource interference discussion",
            "- bounded queues, downstream saturation, backpressure propagation, and QoS collapse discussion",
            "- heterogeneous SoC shared-memory fabric pressure and bandwidth partitioning discussion",
            "- GPU-like throughput pressure, latency hiding approximation, and bandwidth saturation discussion",
            "- AMBA-inspired NoC QoS, route contention, coherency-boundary pressure, and bounded recommendation discussion",
            "- reproducible portfolio validation",
            "",
            "## 16. Claim Boundary",
            "",
            (
                "This evidence pack supports bounded architecture modeling discussion only. "
                "It does not claim Arm CHI compliance, AXI compliance, ACE compliance, "
                "real AMBA protocol behavior, real NoC behavior, real cache coherency, "
                "cycle-accurate modeling, Apple Silicon simulation, NVIDIA GPU simulation, "
                "real GPU behavior, CUDA execution modeling, real HBM-controller behavior, "
                "silicon validation, production signoff, real DRAM timing, or real workload "
                "performance."
            ),
            "",
        ]
    )
    return "\n".join(lines), missing


def resolve_output(root: Path, output: str) -> Path:
    output_path = Path(output)
    return output_path if output_path.is_absolute() else root / output_path


def main() -> int:
    args = parse_args()
    root = repo_root()
    output = resolve_output(root, args.output)
    document, missing = render_document(root)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    print(f"[project-p] wrote {output.relative_to(root)}")

    if missing:
        print("[project-p] missing CSV input(s):")
        for path in missing:
            print(f"  - {path}")
        return 1 if args.strict else 0

    print("[project-p] all required CSV inputs found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
