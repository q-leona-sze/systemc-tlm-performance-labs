#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


SCHEMA_VERSION = "industry-r1.0"
DEFAULT_OUTPUT = "docs/generated/industry_evidence_matrix.md"


@dataclass(frozen=True)
class ProjectSpec:
    label: str
    result_dir: Path
    mapping: str
    problem_type: str
    key_metric_columns: Tuple[str, ...]
    bottleneck_case: str
    bottleneck_columns: Tuple[str, ...]
    recommendation_style: str
    unsupported_claims: Tuple[str, ...]
    required_comparison_fragments: Tuple[str, ...]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the industry-inspired evidence matrix for Project X."
        )
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Output markdown path. Relative paths are resolved from repo root.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if required artifacts or generated claim-boundary text is missing.",
    )
    return parser.parse_args()


def specs() -> List[ProjectSpec]:
    return [
        ProjectSpec(
            label="AT-6",
            result_dir=Path(
                "examples/at/results/project_at6_heterogeneous_soc_fabric"
            ),
            mapping="Apple-like heterogeneous SoC shared fabric pressure",
            problem_type=(
                "heterogeneous initiators sharing one bounded memory fabric "
                "under latency-sensitive and throughput-oriented pressure"
            ),
            key_metric_columns=(
                "p99_latency_ns",
                "fabric_queue_peak",
                "starvation_events",
                "cpu_p99_latency_ns",
                "npu_bandwidth_share",
                "dma_bandwidth_share",
                "isp_p99_latency_ns",
            ),
            bottleneck_case="mixed_stress",
            bottleneck_columns=(
                "p99_latency_ns",
                "fabric_queue_peak",
                "starvation_events",
                "dma_bandwidth_share",
            ),
            recommendation_style=(
                "compare latency priority and bandwidth cap policies before "
                "claiming latency-flow protection"
            ),
            unsupported_claims=(
                "Not supported: Apple Silicon simulation",
                "Not supported: real unified memory controller",
                "Not supported: real NoC behavior",
                "Not supported: cycle-accurate modeling",
                "Not supported: silicon validation",
                "Not supported: production signoff",
            ),
            required_comparison_fragments=(
                "bounded AT-level synthetic",
                "Claim Boundary",
                (
                    "It does not claim Apple Silicon simulation, real NoC "
                    "behavior, cycle-accurate modeling, silicon validation, "
                    "or production signoff."
                ),
            ),
        ),
        ProjectSpec(
            label="AT-7",
            result_dir=Path(
                "examples/at/results/"
                "project_at7_gpu_like_throughput_saturation"
            ),
            mapping="NVIDIA-like throughput engine bandwidth wall",
            problem_type=(
                "throughput engine outstanding-depth sensitivity, latency "
                "hiding approximation, bandwidth saturation, and queue buildup"
            ),
            key_metric_columns=(
                "throughput_req_per_us",
                "effective_bandwidth_bytes_per_ns",
                "memory_utilization_ratio",
                "queue_peak",
                "avg_outstanding",
                "stall_ratio",
                "saturation_flag",
                "knee_point_hint",
            ),
            bottleneck_case="bandwidth_saturation",
            bottleneck_columns=(
                "throughput_req_per_us",
                "memory_utilization_ratio",
                "p99_latency_ns",
                "queue_peak",
                "stall_ratio",
                "knee_point_hint",
            ),
            recommendation_style=(
                "stop increasing outstanding depth after the knee; throttle "
                "injection when p95/p99 latency or queue peak is the risk"
            ),
            unsupported_claims=(
                "Not supported: NVIDIA GPU simulation",
                "Not supported: CUDA execution modeling",
                "Not supported: SM scheduler behavior",
                "Not supported: real HBM controller",
                "Not supported: Tensor Core behavior",
                "Not supported: TMEM behavior",
                "Not supported: cycle-accurate modeling",
                "Not supported: silicon validation",
                "Not supported: production signoff",
            ),
            required_comparison_fragments=(
                "bounded AT-level synthetic",
                "Claim Boundary",
                (
                    "It does not claim NVIDIA GPU simulation, real GPU "
                    "behavior, CUDA execution modeling, real HBM-controller "
                    "behavior, cycle-accurate modeling, silicon validation, "
                    "or production signoff."
                ),
            ),
        ),
        ProjectSpec(
            label="AT-8",
            result_dir=Path(
                "examples/at/results/"
                "project_at8_amba_noc_qos_coherency_boundary"
            ),
            mapping=(
                "Arm-like AMBA-inspired NoC QoS and "
                "coherency-boundary pressure"
            ),
            problem_type=(
                "QoS class protection, route contention, boundary crossing, "
                "ordering delay, and read/write interference"
            ),
            key_metric_columns=(
                "p99_latency_ns",
                "route_queue_peak",
                "shared_route_utilization",
                "boundary_route_utilization",
                "ordering_delay_ns",
                "coherency_boundary_events",
                "starvation_events",
                "collapse_score",
            ),
            bottleneck_case="mixed_qos_collapse",
            bottleneck_columns=(
                "p99_latency_ns",
                "route_queue_peak",
                "boundary_route_utilization",
                "ordering_delay_ns",
                "coherency_boundary_events",
                "starvation_events",
                "collapse_score",
            ),
            recommendation_style=(
                "switch from priority tuning to route capacity, partitioning, "
                "or traffic shaping when collapse score is high"
            ),
            unsupported_claims=(
                "Not supported: Arm CHI compliance",
                "Not supported: AXI compliance",
                "Not supported: ACE compliance",
                "Not supported: real AMBA protocol behavior",
                "Not supported: real NoC behavior",
                "Not supported: real cache coherency",
                "Not supported: cycle-accurate modeling",
                "Not supported: silicon validation",
                "Not supported: production signoff",
            ),
            required_comparison_fragments=(
                "bounded AT-level synthetic",
                "Claim Boundary",
                (
                    "It does not claim Arm CHI compliance, AXI compliance, "
                    "ACE compliance, real AMBA protocol behavior, real NoC "
                    "behavior, real cache coherency, cycle-accurate modeling, "
                    "silicon validation, or production signoff."
                ),
            ),
        ),
    ]


def resolve_output(root: Path, output: str) -> Path:
    output_path = Path(output)
    return output_path if output_path.is_absolute() else root / output_path


def read_csv_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def escape_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def format_columns(row: Dict[str, str], columns: Sequence[str]) -> str:
    parts = []
    for column in columns:
        value = row.get(column, "")
        if value:
            parts.append(f"{column}={value}")
    return "; ".join(parts) if parts else "metric columns unavailable"


def find_case(rows: Sequence[Dict[str, str]], case_name: str) -> Dict[str, str]:
    for row in rows:
        if row.get("case") == case_name:
            return row
    return {}


def validate_inputs(root: Path, all_specs: Sequence[ProjectSpec]) -> List[str]:
    errors: List[str] = []
    for spec in all_specs:
        summary = root / spec.result_dir / "summary.csv"
        comparison = root / spec.result_dir / "comparison.md"

        if not summary.exists():
            errors.append(f"{spec.label}: missing {summary.relative_to(root)}")
        if not comparison.exists():
            errors.append(f"{spec.label}: missing {comparison.relative_to(root)}")
            continue

        text = comparison.read_text(encoding="utf-8")
        missing = [
            fragment
            for fragment in spec.required_comparison_fragments
            if fragment not in text
        ]
        if missing:
            errors.append(
                f"{spec.label}: comparison.md missing claim-boundary "
                f"fragment(s): {', '.join(missing)}"
            )

    return errors


def render_matrix(root: Path, all_specs: Sequence[ProjectSpec]) -> str:
    lines = [
        "# Industry Evidence Matrix",
        "",
        f"schema_version={SCHEMA_VERSION}",
        "",
        "## Purpose",
        "",
        (
            "This matrix is the Project X industry-inspired mapping layer over "
            "existing AT-6, AT-7, and AT-8 evidence. It organizes already "
            "generated `summary.csv` and `comparison.md` artifacts for "
            "portfolio, interview, and release-pack discussion."
        ),
        "",
        "## Source Projects",
        "",
        "- AT-6: Heterogeneous SoC Shared Memory Fabric Lab",
        "- AT-7: GPU-like Throughput Engine and Memory Saturation Lab",
        "- AT-8: AMBA-inspired NoC QoS and Coherency Boundary Lab",
        "",
        "## Evidence Matrix",
        "",
        "| project | industry-inspired mapping | architecture problem type | input evidence | key metrics | observed bottleneck | recommendation style | unsupported claims |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for spec in all_specs:
        summary_path = spec.result_dir / "summary.csv"
        comparison_path = spec.result_dir / "comparison.md"
        headers, rows = read_csv_rows(root / summary_path)
        bottleneck_row = find_case(rows, spec.bottleneck_case)
        missing_columns = [
            column for column in spec.key_metric_columns if column not in headers
        ]
        key_metrics = ", ".join(spec.key_metric_columns)
        if missing_columns:
            key_metrics += f" (missing columns: {', '.join(missing_columns)})"
        observed = (
            f"{spec.bottleneck_case}: "
            f"{format_columns(bottleneck_row, spec.bottleneck_columns)}"
        )
        unsupported = "; ".join(spec.unsupported_claims)
        evidence = f"`{summary_path}`<br>`{comparison_path}`"
        lines.append(
            "| "
            + " | ".join(
                escape_cell(value)
                for value in (
                    spec.label,
                    spec.mapping,
                    spec.problem_type,
                    evidence,
                    key_metrics,
                    observed,
                    spec.recommendation_style,
                    unsupported,
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Industry-Inspired Mapping",
            "",
            (
                "- Apple-like: AT-6 maps heterogeneous initiators, shared "
                "fabric pressure, bandwidth cap behavior, latency-sensitive "
                "flow protection, and starvation risk."
            ),
            (
                "- NVIDIA-like: AT-7 maps throughput-engine pressure, "
                "outstanding-depth sensitivity, bandwidth saturation, "
                "latency-hiding approximation, burstiness, queue buildup, "
                "and the memory wall."
            ),
            (
                "- Arm-like: AT-8 maps AMBA-inspired QoS classes, route "
                "contention, coherency-boundary pressure, ordering delay, "
                "read/write interference, starvation signal, and collapse "
                "risk."
            ),
            "",
            "## Claim Boundary",
            "",
            (
                "This industry evidence matrix is an industry-inspired "
                "mapping layer over bounded synthetic architecture "
                "explorations. It does not claim any unsupported item listed "
                "below."
            ),
            "",
            "claim_boundary=PASS",
            "",
            "## Unsupported Claims",
            "",
        ]
    )

    unsupported_claims = sorted(
        {claim for spec in all_specs for claim in spec.unsupported_claims}
    )
    for claim in unsupported_claims:
        lines.append(f"- {claim}")

    lines.extend(
        [
            "",
            "## Validation",
            "",
            "Regenerate this file with:",
            "",
            "```bash",
            "python3 tools/generate_industry_evidence_matrix.py --strict",
            "```",
            "",
            "Expected PASS marker:",
            "",
            "```text",
            "Industry Evidence Matrix PASS",
            "projects=AT-6,AT-7,AT-8",
            "industry_mappings=Apple-like,NVIDIA-like,Arm-like",
            "claim_boundary=PASS",
            f"schema_version={SCHEMA_VERSION}",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def validate_generated(document: str) -> List[str]:
    required_fragments = (
        "Apple-like heterogeneous SoC shared fabric pressure",
        "NVIDIA-like throughput engine bandwidth wall",
        "Arm-like AMBA-inspired NoC QoS and coherency-boundary pressure",
        "## Claim Boundary",
        "## Unsupported Claims",
        "claim_boundary=PASS",
        f"schema_version={SCHEMA_VERSION}",
    )
    return [fragment for fragment in required_fragments if fragment not in document]


def main() -> int:
    args = parse_args()
    root = repo_root()
    output = resolve_output(root, args.output)
    all_specs = specs()

    input_errors = validate_inputs(root, all_specs)
    if input_errors and args.strict:
        for error in input_errors:
            print(f"[industry-r1] ERROR {error}", file=sys.stderr)
        print("Industry Evidence Matrix FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    document = render_matrix(root, all_specs)
    missing_generated = validate_generated(document)
    if missing_generated and args.strict:
        for fragment in missing_generated:
            print(
                f"[industry-r1] ERROR generated markdown missing: {fragment}",
                file=sys.stderr,
            )
        print("Industry Evidence Matrix FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    print(f"[industry-r1] wrote {output.relative_to(root)}")

    if input_errors:
        for error in input_errors:
            print(f"[industry-r1] WARNING {error}", file=sys.stderr)

    print("Industry Evidence Matrix PASS")
    print("projects=AT-6,AT-7,AT-8")
    print("industry_mappings=Apple-like,NVIDIA-like,Arm-like")
    print("claim_boundary=PASS")
    print(f"schema_version={SCHEMA_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
