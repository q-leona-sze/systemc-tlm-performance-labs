#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


SCHEMA_VERSION = "classifier-r1.0"
DEFAULT_INPUT = "examples/workloads/sample_workload_symptoms.csv"
DEFAULT_OUTPUT = "docs/generated/workload_bottleneck_classification.md"

FAMILIES = (
    "shared_fabric_pressure",
    "throughput_bandwidth_wall",
    "noc_qos_coherency_boundary",
    "mixed_or_uncertain",
)

REQUIRED_COLUMNS = (
    "workload",
    "description",
    "concurrent_initiators",
    "memory_utilization_ratio",
    "queue_peak",
    "p99_latency_ns",
    "throughput_req_per_us",
    "avg_outstanding",
    "burstiness_score",
    "boundary_crossing_rate",
    "ordering_events",
    "read_write_interference_score",
    "qos_class_pressure",
    "starvation_events",
    "expected_family",
)

NUMERIC_COLUMNS = (
    "concurrent_initiators",
    "memory_utilization_ratio",
    "queue_peak",
    "p99_latency_ns",
    "throughput_req_per_us",
    "avg_outstanding",
    "burstiness_score",
    "boundary_crossing_rate",
    "ordering_events",
    "read_write_interference_score",
    "qos_class_pressure",
    "starvation_events",
)

UNSUPPORTED_CLAIMS = (
    "Not supported: Apple Silicon simulation.",
    "Not supported: NVIDIA GPU simulation.",
    "Not supported: Arm CHI compliance.",
    "Not supported: AXI compliance.",
    "Not supported: ACE compliance.",
    "Not supported: real hardware profiling.",
    "Not supported: real NoC behavior.",
    "Not supported: real cache coherency.",
    "Not supported: cycle-accurate modeling.",
    "Not supported: silicon validation.",
    "Not supported: production signoff.",
)


@dataclass(frozen=True)
class Classification:
    workload: str
    description: str
    expected_family: str
    predicted_family: str
    scores: Dict[str, int]
    confidence: str
    evidence_mapping: str
    recommendation: str
    reason: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Classify workload symptoms into bounded architecture bottleneck "
            "families. This is a deterministic rule-based tool, not ML."
        )
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help="Input workload symptom CSV. Relative paths are resolved from repo root.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Output markdown file. Relative paths are resolved from repo root.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable schema, self-check, output, and claim-boundary validation.",
    )
    return parser.parse_args()


def resolve_path(root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def escape_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def read_csv_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def validate_input_schema(
    input_path: Path, headers: Sequence[str], rows: Sequence[Dict[str, str]], strict: bool
) -> List[str]:
    errors: List[str] = []
    if not input_path.exists():
        errors.append(f"input CSV does not exist: {input_path}")
        return errors
    missing = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing:
        errors.append(f"input CSV missing required column(s): {', '.join(missing)}")
    if strict and len(rows) < 6:
        errors.append("strict mode requires at least 6 sample workloads")
    return errors


def validate_output_path(output_path: Path) -> List[str]:
    errors: List[str] = []
    if output_path.exists() and output_path.is_dir():
        errors.append(f"output path is a directory: {output_path}")
        return errors
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        errors.append(f"cannot create output directory {output_path.parent}: {exc}")
    return errors


def parse_number(row: Dict[str, str], column: str, row_index: int, errors: List[str]) -> float:
    raw = row.get(column, "").strip()
    try:
        return float(raw)
    except ValueError:
        errors.append(
            f"row {row_index}: column {column} must be numeric, got {raw!r}"
        )
        return 0.0


def add_score(
    scores: Dict[str, int],
    reasons: Dict[str, List[str]],
    family: str,
    points: int,
    reason: str,
) -> None:
    scores[family] += points
    reasons[family].append(reason)


def score_row(metrics: Dict[str, float]) -> Tuple[Dict[str, int], Dict[str, List[str]]]:
    scores = {
        "shared_fabric_pressure": 0,
        "throughput_bandwidth_wall": 0,
        "noc_qos_coherency_boundary": 0,
    }
    reasons: Dict[str, List[str]] = {family: [] for family in scores}

    concurrent = metrics["concurrent_initiators"]
    memory_util = metrics["memory_utilization_ratio"]
    queue_peak = metrics["queue_peak"]
    p99_latency = metrics["p99_latency_ns"]
    throughput = metrics["throughput_req_per_us"]
    outstanding = metrics["avg_outstanding"]
    burstiness = metrics["burstiness_score"]
    boundary = metrics["boundary_crossing_rate"]
    ordering = metrics["ordering_events"]
    rw_interference = metrics["read_write_interference_score"]
    qos_pressure = metrics["qos_class_pressure"]
    starvation = metrics["starvation_events"]

    if concurrent >= 4:
        add_score(
            scores,
            reasons,
            "shared_fabric_pressure",
            3,
            "high concurrent initiators",
        )
    elif concurrent >= 3:
        add_score(
            scores,
            reasons,
            "shared_fabric_pressure",
            2,
            "moderate concurrent initiators",
        )

    if queue_peak >= 16:
        add_score(scores, reasons, "shared_fabric_pressure", 2, "high shared queue")
    elif queue_peak >= 8:
        add_score(scores, reasons, "shared_fabric_pressure", 1, "moderate queue")

    if p99_latency >= 160:
        add_score(scores, reasons, "shared_fabric_pressure", 1, "elevated p99 latency")
    if memory_util < 0.85:
        add_score(
            scores,
            reasons,
            "shared_fabric_pressure",
            1,
            "memory path is not fully saturated",
        )
    if boundary < 0.35 and ordering <= 2 and qos_pressure < 0.45:
        add_score(
            scores,
            reasons,
            "shared_fabric_pressure",
            1,
            "boundary and QoS symptoms are not dominant",
        )

    if memory_util >= 0.90:
        add_score(
            scores,
            reasons,
            "throughput_bandwidth_wall",
            3,
            "memory utilization near saturation",
        )
    elif memory_util >= 0.85:
        add_score(
            scores,
            reasons,
            "throughput_bandwidth_wall",
            2,
            "memory utilization is high",
        )

    if throughput >= 1.30:
        add_score(
            scores,
            reasons,
            "throughput_bandwidth_wall",
            2,
            "high request throughput",
        )
    elif throughput >= 1.00:
        add_score(
            scores,
            reasons,
            "throughput_bandwidth_wall",
            1,
            "moderate request throughput",
        )

    if outstanding >= 24:
        add_score(
            scores,
            reasons,
            "throughput_bandwidth_wall",
            2,
            "high outstanding depth",
        )
    elif outstanding >= 16:
        add_score(
            scores,
            reasons,
            "throughput_bandwidth_wall",
            1,
            "moderate outstanding depth",
        )

    if burstiness >= 0.75:
        add_score(scores, reasons, "throughput_bandwidth_wall", 2, "bursty injection")
    elif burstiness >= 0.55:
        add_score(
            scores,
            reasons,
            "throughput_bandwidth_wall",
            1,
            "moderate burstiness",
        )
    if queue_peak >= 16:
        add_score(scores, reasons, "throughput_bandwidth_wall", 1, "queue buildup")
    if boundary < 0.35 and ordering <= 2:
        add_score(
            scores,
            reasons,
            "throughput_bandwidth_wall",
            1,
            "boundary and ordering symptoms are not dominant",
        )
    if boundary >= 0.55 or ordering >= 4:
        scores["throughput_bandwidth_wall"] -= 1
        reasons["throughput_bandwidth_wall"].append(
            "boundary or ordering symptom conflicts with pure bandwidth wall"
        )

    if boundary >= 0.65:
        add_score(
            scores,
            reasons,
            "noc_qos_coherency_boundary",
            3,
            "high boundary crossing rate",
        )
    elif boundary >= 0.45:
        add_score(
            scores,
            reasons,
            "noc_qos_coherency_boundary",
            2,
            "moderate boundary crossing rate",
        )
    if ordering >= 4:
        add_score(
            scores,
            reasons,
            "noc_qos_coherency_boundary",
            2,
            "high ordering events",
        )
    elif ordering >= 2:
        add_score(
            scores,
            reasons,
            "noc_qos_coherency_boundary",
            1,
            "moderate ordering events",
        )
    if rw_interference >= 0.65:
        add_score(
            scores,
            reasons,
            "noc_qos_coherency_boundary",
            2,
            "high read/write interference",
        )
    elif rw_interference >= 0.45:
        add_score(
            scores,
            reasons,
            "noc_qos_coherency_boundary",
            1,
            "moderate read/write interference",
        )
    if qos_pressure >= 0.65:
        add_score(
            scores,
            reasons,
            "noc_qos_coherency_boundary",
            2,
            "high QoS class pressure",
        )
    elif qos_pressure >= 0.45:
        add_score(
            scores,
            reasons,
            "noc_qos_coherency_boundary",
            1,
            "moderate QoS class pressure",
        )
    if starvation >= 2:
        add_score(
            scores,
            reasons,
            "noc_qos_coherency_boundary",
            2,
            "starvation signal",
        )
    elif starvation >= 1:
        add_score(
            scores,
            reasons,
            "noc_qos_coherency_boundary",
            1,
            "weak starvation signal",
        )
    if queue_peak >= 16:
        add_score(
            scores,
            reasons,
            "noc_qos_coherency_boundary",
            1,
            "route or boundary queue symptom",
        )

    return scores, reasons


def choose_family(scores: Dict[str, int]) -> Tuple[str, str]:
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    top_family, top_score = ordered[0]
    second_family, second_score = ordered[1]
    high_family_count = sum(1 for score in scores.values() if score >= 5)

    if top_score < 4:
        return "mixed_or_uncertain", "low evidence across all families"
    if high_family_count >= 3:
        return "mixed_or_uncertain", "shared, throughput, and boundary symptoms are all high"
    if top_score - second_score <= 1 and second_score >= 4:
        return (
            "mixed_or_uncertain",
            f"top scores are close: {top_family}={top_score}, "
            f"{second_family}={second_score}",
        )
    return top_family, f"top score is {top_family}={top_score}"


def evidence_mapping(family: str) -> str:
    if family == "shared_fabric_pressure":
        return "AT-6 -> Apple-like heterogeneous SoC shared fabric pressure"
    if family == "throughput_bandwidth_wall":
        return "AT-7 -> NVIDIA-like throughput engine bandwidth wall"
    if family == "noc_qos_coherency_boundary":
        return "AT-8 -> Arm-like AMBA-inspired NoC QoS and coherency-boundary pressure"
    return "needs more evidence -> split workload phases or run targeted AT-6/AT-7/AT-8 checks"


def recommendation(family: str) -> str:
    if family == "shared_fabric_pressure":
        return (
            "inspect AT-6-style fabric contention, bandwidth partitioning, "
            "latency-flow protection, and starvation risk"
        )
    if family == "throughput_bandwidth_wall":
        return (
            "inspect AT-7-style memory utilization, outstanding-depth knee, "
            "queue buildup, and bandwidth-wall behavior"
        )
    if family == "noc_qos_coherency_boundary":
        return (
            "inspect AT-8-style QoS class pressure, route contention, "
            "boundary crossings, ordering delay, and read/write interference"
        )
    return (
        "collect more evidence, split the workload into phases, and compare "
        "AT-6 / AT-7 / AT-8 symptom families separately"
    )


def confidence(family: str, scores: Dict[str, int]) -> str:
    if family == "mixed_or_uncertain":
        return "low"
    ordered = sorted(scores.values(), reverse=True)
    return "high" if ordered[0] - ordered[1] >= 4 else "medium"


def classify_rows(
    rows: Sequence[Dict[str, str]]
) -> Tuple[List[Classification], List[str]]:
    errors: List[str] = []
    classifications: List[Classification] = []
    for row_index, row in enumerate(rows, start=2):
        metrics = {
            column: parse_number(row, column, row_index, errors)
            for column in NUMERIC_COLUMNS
        }
        scores, reasons = score_row(metrics)
        predicted, reason = choose_family(scores)
        family_reasons = reasons.get(predicted, [])
        if predicted == "mixed_or_uncertain":
            family_reasons = [reason]
        classifications.append(
            Classification(
                workload=row.get("workload", "").strip(),
                description=row.get("description", "").strip(),
                expected_family=row.get("expected_family", "").strip(),
                predicted_family=predicted,
                scores=scores,
                confidence=confidence(predicted, scores),
                evidence_mapping=evidence_mapping(predicted),
                recommendation=recommendation(predicted),
                reason="; ".join(family_reasons[:4]) or reason,
            )
        )
    return classifications, errors


def validate_strict_self_check(classifications: Sequence[Classification]) -> List[str]:
    errors: List[str] = []
    for item in classifications:
        if item.expected_family and item.expected_family not in FAMILIES:
            errors.append(
                f"{item.workload}: expected_family is not recognized: "
                f"{item.expected_family}"
            )
        if item.expected_family and item.expected_family != item.predicted_family:
            errors.append(
                f"{item.workload}: predicted_family={item.predicted_family} "
                f"does not match expected_family={item.expected_family}"
            )
    return errors


def score_text(scores: Dict[str, int]) -> str:
    return (
        f"shared={scores['shared_fabric_pressure']}; "
        f"throughput={scores['throughput_bandwidth_wall']}; "
        f"noc={scores['noc_qos_coherency_boundary']}"
    )


def render_markdown(
    root: Path,
    input_path: Path,
    classifications: Sequence[Classification],
) -> str:
    lines = [
        "# Workload Bottleneck Classification",
        "",
        f"schema_version={SCHEMA_VERSION}",
        f"input_file={display_path(root, input_path)}",
        "",
        "## Purpose",
        "",
        (
            "This generated report classifies sample workload symptoms into "
            "bounded architecture bottleneck families. The classifier is "
            "deterministic and rule-based; it is not machine learning and not "
            "a hardware profiler."
        ),
        "",
        "## Workload Classification Table",
        "",
        "| workload | description | predicted_family | expected_family | confidence | scores | evidence mapping | recommendation | reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for item in classifications:
        lines.append(
            "| "
            + " | ".join(
                escape_cell(value)
                for value in (
                    item.workload,
                    item.description,
                    item.predicted_family,
                    item.expected_family,
                    item.confidence,
                    score_text(item.scores),
                    item.evidence_mapping,
                    item.recommendation,
                    item.reason,
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Classification Rules Summary",
            "",
            "- `shared_fabric_pressure`: high concurrent initiators, shared queue pressure, elevated p99 latency, and no dominant boundary / ordering symptom.",
            "- `throughput_bandwidth_wall`: memory utilization near saturation, high request throughput, high outstanding depth, burstiness, and queue buildup.",
            "- `noc_qos_coherency_boundary`: high boundary crossing rate, ordering events, read/write interference, QoS class pressure, starvation, and route / boundary queue symptoms.",
            "- `mixed_or_uncertain`: low evidence, close top scores, or simultaneous shared-fabric, throughput-wall, and boundary-pressure symptoms.",
            "",
            "## Evidence Mapping",
            "",
            "| family | evidence family | interpretation |",
            "| --- | --- | --- |",
            "| shared_fabric_pressure | AT-6 -> Apple-like | heterogeneous SoC shared fabric pressure |",
            "| throughput_bandwidth_wall | AT-7 -> NVIDIA-like | throughput engine bandwidth wall |",
            "| noc_qos_coherency_boundary | AT-8 -> Arm-like | AMBA-inspired NoC QoS and coherency-boundary pressure |",
            "| mixed_or_uncertain | needs more evidence | split the workload or collect targeted symptoms before choosing a family |",
            "",
            "## Recommendations",
            "",
            "- Treat the predicted family as an architecture discussion starting point, not a final design decision.",
            "- For shared fabric pressure, compare AT-6-style bandwidth caps, latency-sensitive flow protection, and starvation risk.",
            "- For throughput bandwidth walls, compare AT-7-style outstanding-depth pressure, memory utilization, burstiness, and queue buildup.",
            "- For NoC / QoS / coherency-boundary pressure, compare AT-8-style route pressure, boundary crossings, ordering delay, and read/write interference.",
            "- For mixed or uncertain outputs, split the workload into phases and collect more targeted evidence before claiming a bottleneck family.",
            "",
            "## Unsupported Claims",
            "",
        ]
    )

    for claim in UNSUPPORTED_CLAIMS:
        lines.append(f"- {claim}")

    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "Current:",
            "",
            (
                "- This report is generated by a bounded rule-based "
                "architecture reasoning tool over sample workload symptoms."
            ),
            "",
            "Supported:",
            "",
            (
                "- It supports portfolio and interview discussion about "
                "mapping workload symptoms to evidence families."
            ),
            "",
            "Not Supported:",
            "",
            (
                "- It does not replace real profiling, vendor simulators, "
                "protocol-compliance validation, cycle-accurate modeling, "
                "silicon validation, or production signoff."
            ),
            "",
            "Future Work:",
            "",
            (
                "- Future versions may add more symptom fields or compare "
                "multiple workload phases, while remaining deterministic and "
                "claim-bounded."
            ),
            "",
            "claim_boundary=PASS",
            "",
        ]
    )
    return "\n".join(lines)


def validate_generated(
    document: str, classifications: Sequence[Classification]
) -> List[str]:
    required_fragments = [
        f"schema_version={SCHEMA_VERSION}",
        "## Workload Classification Table",
        "## Classification Rules Summary",
        "## Evidence Mapping",
        "## Unsupported Claims",
        "## Claim Boundary",
        "claim_boundary=PASS",
    ]
    errors = [
        f"generated markdown missing required fragment: {fragment}"
        for fragment in required_fragments
        if fragment not in document
    ]
    for item in classifications:
        if item.workload not in document or item.predicted_family not in document:
            errors.append(
                f"generated markdown missing classification for {item.workload}"
            )
    return errors


def print_errors(errors: Sequence[str]) -> None:
    for error in errors:
        print(f"[classifier-r1] ERROR {error}", file=sys.stderr)


def main() -> int:
    args = parse_args()
    root = repo_root()
    input_path = resolve_path(root, args.input)
    output_path = resolve_path(root, args.output)

    if not input_path.exists():
        print_errors([f"input CSV does not exist: {input_path}"])
        print("Workload Bottleneck Classifier FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    headers, rows = read_csv_rows(input_path)
    errors = validate_input_schema(input_path, headers, rows, args.strict)
    if args.strict:
        errors.extend(validate_output_path(output_path))
    if errors:
        print_errors(errors)
        print("Workload Bottleneck Classifier FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    classifications, numeric_errors = classify_rows(rows)
    if numeric_errors:
        print_errors(numeric_errors)
        print("Workload Bottleneck Classifier FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    if args.strict:
        strict_errors = validate_strict_self_check(classifications)
        if strict_errors:
            print_errors(strict_errors)
            print("Workload Bottleneck Classifier FAIL")
            print(f"schema_version={SCHEMA_VERSION}")
            return 1

    document = render_markdown(root, input_path, classifications)
    if args.strict:
        generated_errors = validate_generated(document, classifications)
        if generated_errors:
            print_errors(generated_errors)
            print("Workload Bottleneck Classifier FAIL")
            print(f"schema_version={SCHEMA_VERSION}")
            return 1

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(document, encoding="utf-8")
    except OSError as exc:
        print_errors([f"cannot write output markdown {output_path}: {exc}"])
        print("Workload Bottleneck Classifier FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    print("Workload Bottleneck Classifier PASS")
    print(f"workloads={len(classifications)}")
    print(
        "families="
        "shared_fabric_pressure,"
        "throughput_bandwidth_wall,"
        "noc_qos_coherency_boundary,"
        "mixed_or_uncertain"
    )
    print("claim_boundary=PASS")
    print(f"schema_version={SCHEMA_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
