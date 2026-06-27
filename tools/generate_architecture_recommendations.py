#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


SCHEMA_VERSION = "recommendation-r1.0"
CLASSIFIER_SCHEMA_VERSION = "classifier-r1.0"
DEFAULT_INPUT = "examples/workloads/sample_workload_symptoms.csv"
DEFAULT_CLASSIFICATION = "docs/generated/workload_bottleneck_classification.md"
DEFAULT_OUTPUT = "docs/generated/architecture_recommendations.md"

FAMILIES = (
    "shared_fabric_pressure",
    "throughput_bandwidth_wall",
    "noc_qos_coherency_boundary",
    "mixed_or_uncertain",
)

RECOMMENDATION_FAMILIES = (
    "fabric_mitigation",
    "bandwidth_wall_mitigation",
    "noc_qos_boundary_mitigation",
    "mixed_evidence_required",
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

UNSUPPORTED_CLAIMS = (
    "Not supported: Apple Silicon simulation.",
    "Not supported: NVIDIA GPU simulation.",
    "Not supported: Arm CHI compliance.",
    "Not supported: AXI compliance.",
    "Not supported: ACE compliance.",
    "Not supported: real hardware profiling.",
    "Not supported: automatic hardware optimization.",
    "Not supported: real NoC behavior.",
    "Not supported: real cache coherency.",
    "Not supported: cycle-accurate modeling.",
    "Not supported: silicon validation.",
    "Not supported: production signoff.",
)


@dataclass(frozen=True)
class ClassificationRow:
    workload: str
    predicted_family: str
    expected_family: str
    classifier_confidence: str
    scores: Dict[str, int]
    classifier_reason: str


@dataclass(frozen=True)
class RecommendationRule:
    family: str
    recommendation_family: str
    evidence_project: str
    industry_mapping: str
    primary: str
    secondary: str
    risk_if_ignored: str
    measure_next: str
    rule_summary: str


@dataclass(frozen=True)
class Recommendation:
    workload: str
    description: str
    predicted_family: str
    recommendation_family: str
    evidence_project: str
    industry_mapping: str
    primary: str
    secondary: str
    risk_if_ignored: str
    confidence: str
    measure_next: str
    evidence_notes: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate bounded architecture recommendations from Project Y "
            "workload bottleneck families."
        )
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help="Input workload symptom CSV. Relative paths are resolved from repo root.",
    )
    parser.add_argument(
        "--classification",
        default=DEFAULT_CLASSIFICATION,
        help="Project Y classifier markdown. Relative paths are resolved from repo root.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Output recommendation markdown. Relative paths are resolved from repo root.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable input, generated markdown, and claim-boundary validation.",
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
        errors.append("strict mode requires at least 6 workload rows")
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


def split_markdown_row(line: str) -> List[str]:
    line = line.strip()
    if not line.startswith("|") or not line.endswith("|"):
        return []
    cells = line.strip("|").split("|")
    return [cell.strip().replace("\\|", "|") for cell in cells]


def parse_scores(raw_scores: str) -> Dict[str, int]:
    score_map = {
        "shared": "shared_fabric_pressure",
        "throughput": "throughput_bandwidth_wall",
        "noc": "noc_qos_coherency_boundary",
    }
    scores = {family: 0 for family in score_map.values()}
    for part in raw_scores.split(";"):
        if "=" not in part:
            continue
        raw_key, raw_value = part.split("=", 1)
        key = raw_key.strip()
        family = score_map.get(key)
        if family is None:
            continue
        try:
            scores[family] = int(float(raw_value.strip()))
        except ValueError:
            scores[family] = 0
    return scores


def parse_classification_markdown(path: Path) -> Tuple[Dict[str, ClassificationRow], List[str]]:
    errors: List[str] = []
    text = path.read_text(encoding="utf-8")
    if f"schema_version={CLASSIFIER_SCHEMA_VERSION}" not in text:
        errors.append(
            f"classification markdown missing schema_version={CLASSIFIER_SCHEMA_VERSION}"
        )

    lines = text.splitlines()
    table_start = None
    for index, line in enumerate(lines):
        if line.strip() == "## Workload Classification Table":
            table_start = index
            break
    if table_start is None:
        return {}, errors + ["classification markdown missing workload table"]

    table_lines: List[str] = []
    for line in lines[table_start + 1 :]:
        if line.startswith("## "):
            break
        if line.strip().startswith("|"):
            table_lines.append(line)

    if len(table_lines) < 3:
        return {}, errors + ["classification workload table has no data rows"]

    headers = split_markdown_row(table_lines[0])
    header_index = {header: index for index, header in enumerate(headers)}
    required_headers = (
        "workload",
        "predicted_family",
        "expected_family",
        "confidence",
        "scores",
        "reason",
    )
    missing_headers = [
        header for header in required_headers if header not in header_index
    ]
    if missing_headers:
        return {}, errors + [
            "classification workload table missing column(s): "
            + ", ".join(missing_headers)
        ]

    classifications: Dict[str, ClassificationRow] = {}
    for line in table_lines[2:]:
        cells = split_markdown_row(line)
        if len(cells) != len(headers):
            errors.append(f"classification table row has unexpected shape: {line}")
            continue
        workload = cells[header_index["workload"]]
        predicted = cells[header_index["predicted_family"]]
        if predicted not in FAMILIES:
            errors.append(
                f"{workload}: unknown predicted_family in classification: {predicted}"
            )
        classifications[workload] = ClassificationRow(
            workload=workload,
            predicted_family=predicted,
            expected_family=cells[header_index["expected_family"]],
            classifier_confidence=cells[header_index["confidence"]],
            scores=parse_scores(cells[header_index["scores"]]),
            classifier_reason=cells[header_index["reason"]],
        )
    return classifications, errors


def rules() -> Dict[str, RecommendationRule]:
    return {
        "shared_fabric_pressure": RecommendationRule(
            family="shared_fabric_pressure",
            recommendation_family="fabric_mitigation",
            evidence_project="AT-6",
            industry_mapping="Apple-like heterogeneous SoC shared fabric pressure",
            primary=(
                "protect latency-sensitive initiators with bounded priority or "
                "bandwidth partitioning"
            ),
            secondary=(
                "cap bulk/DMA-like traffic; schedule high-pressure initiators; "
                "increase shared fabric capacity only if queue pressure persists"
            ),
            risk_if_ignored=(
                "tail latency, starvation risk, and unfair bandwidth share can "
                "grow under mixed initiator pressure"
            ),
            measure_next=(
                "fabric queue peak, per-initiator p95/p99 latency, bandwidth "
                "share, and starvation events"
            ),
            rule_summary=(
                "Map shared-fabric symptoms to latency-flow protection, "
                "bandwidth caps, scheduling separation, and starvation checks."
            ),
        ),
        "throughput_bandwidth_wall": RecommendationRule(
            family="throughput_bandwidth_wall",
            recommendation_family="bandwidth_wall_mitigation",
            evidence_project="AT-7",
            industry_mapping="NVIDIA-like throughput engine bandwidth wall",
            primary=(
                "stop increasing outstanding depth after the knee point and tune "
                "occupancy/outstanding limits"
            ),
            secondary=(
                "shape burstiness, prefer bandwidth-aware batching, and use a "
                "throttled profile when tail latency is a risk"
            ),
            risk_if_ignored=(
                "extra outstanding pressure can become queue delay and p99 "
                "tail growth without useful throughput gain"
            ),
            measure_next=(
                "memory utilization ratio, queue peak, average outstanding "
                "depth, stall ratio, and throughput"
            ),
            rule_summary=(
                "Map bandwidth-wall symptoms to outstanding-depth control, "
                "burst shaping, and knee-point validation."
            ),
        ),
        "noc_qos_coherency_boundary": RecommendationRule(
            family="noc_qos_coherency_boundary",
            recommendation_family="noc_qos_boundary_mitigation",
            evidence_project="AT-8",
            industry_mapping=(
                "Arm-like AMBA-inspired NoC QoS and coherency-boundary pressure"
            ),
            primary=(
                "isolate boundary-crossing traffic and reduce ordering-sensitive "
                "serialization"
            ),
            secondary=(
                "protect read latency from write-heavy bulk traffic, partition "
                "QoS/VC-like resources, and avoid route hotspot mapping"
            ),
            risk_if_ignored=(
                "route and boundary queues can dominate tail latency, while QoS "
                "priority collapses under hotspot pressure"
            ),
            measure_next=(
                "boundary crossing rate, ordering events, read/write "
                "interference, QoS class pressure, and starvation events"
            ),
            rule_summary=(
                "Map boundary/QoS symptoms to traffic isolation, serialization "
                "reduction, QoS partitioning, and hotspot avoidance."
            ),
        ),
        "mixed_or_uncertain": RecommendationRule(
            family="mixed_or_uncertain",
            recommendation_family="mixed_evidence_required",
            evidence_project="AT-6/AT-7/AT-8",
            industry_mapping=(
                "Mixed Apple-like / NVIDIA-like / Arm-like evidence family"
            ),
            primary=(
                "do not overfit one bottleneck family; run targeted AT-6/AT-7/"
                "AT-8 evidence checks"
            ),
            secondary=(
                "collect additional workload symptoms and separate shared-"
                "fabric, bandwidth-wall, and boundary/QoS phases"
            ),
            risk_if_ignored=(
                "a single mitigation can improve one symptom while hiding or "
                "worsening another bottleneck family"
            ),
            measure_next=(
                "phase-split symptoms plus targeted AT-6, AT-7, and AT-8 "
                "metrics before choosing an architecture action"
            ),
            rule_summary=(
                "Map mixed symptoms to additional evidence collection before "
                "choosing a primary mitigation."
            ),
        ),
    }


def recommendation_confidence(item: ClassificationRow) -> str:
    if item.predicted_family == "mixed_or_uncertain":
        return "low"

    ordered_scores = sorted(item.scores.values(), reverse=True)
    top_gap = ordered_scores[0] - ordered_scores[1] if len(ordered_scores) > 1 else 0
    if top_gap >= 4 or item.expected_family == item.predicted_family:
        return "high"
    if top_gap >= 2:
        return "medium"
    return "low"


def symptom_notes(row: Dict[str, str], classification: ClassificationRow) -> str:
    fields = (
        "concurrent_initiators",
        "memory_utilization_ratio",
        "queue_peak",
        "p99_latency_ns",
        "throughput_req_per_us",
        "avg_outstanding",
        "boundary_crossing_rate",
        "ordering_events",
        "read_write_interference_score",
        "qos_class_pressure",
        "starvation_events",
    )
    metrics = "; ".join(f"{field}={row.get(field, '')}" for field in fields)
    return f"{classification.classifier_reason}; {metrics}"


def generate_recommendations(
    rows: Sequence[Dict[str, str]],
    classifications: Dict[str, ClassificationRow],
) -> Tuple[List[Recommendation], List[str]]:
    errors: List[str] = []
    rule_map = rules()
    recommendations: List[Recommendation] = []
    for row in rows:
        workload = row.get("workload", "").strip()
        if not workload:
            errors.append("workload row missing workload name")
            continue
        classification = classifications.get(workload)
        if classification is None:
            errors.append(f"{workload}: missing Project Y classification row")
            continue
        rule = rule_map.get(classification.predicted_family)
        if rule is None:
            errors.append(
                f"{workload}: no recommendation rule for "
                f"{classification.predicted_family}"
            )
            continue
        recommendations.append(
            Recommendation(
                workload=workload,
                description=row.get("description", "").strip(),
                predicted_family=classification.predicted_family,
                recommendation_family=rule.recommendation_family,
                evidence_project=rule.evidence_project,
                industry_mapping=rule.industry_mapping,
                primary=rule.primary,
                secondary=rule.secondary,
                risk_if_ignored=rule.risk_if_ignored,
                confidence=recommendation_confidence(classification),
                measure_next=rule.measure_next,
                evidence_notes=symptom_notes(row, classification),
            )
        )
    return recommendations, errors


def render_markdown(
    root: Path,
    input_path: Path,
    classification_path: Path,
    recommendations: Sequence[Recommendation],
) -> str:
    lines = [
        "# Architecture Recommendations",
        "",
        f"schema_version={SCHEMA_VERSION}",
        f"input_file={display_path(root, input_path)}",
        f"classification_file={display_path(root, classification_path)}",
        "",
        "## Purpose",
        "",
        (
            "This generated report is the Project Z architecture "
            "recommendation layer over Project Y bottleneck families. It is a "
            "bounded rule-based recommendation engine and architecture "
            "reasoning layer. It is not an optimizer, not machine learning, "
            "not a profiler, and not a hardware design synthesis tool."
        ),
        "",
        "## Source Inputs",
        "",
        f"- Workload symptoms: `{display_path(root, input_path)}`",
        f"- Project Y classification: `{display_path(root, classification_path)}`",
        (
            "- Project Z consumes the same workload symptom source and uses "
            "Project Y family definitions."
        ),
        "",
        "## Workload Recommendation Table",
        "",
        "| workload | predicted bottleneck family | recommendation family | evidence project | industry-inspired mapping | primary recommendation | secondary recommendation | risk if ignored | confidence | what to measure next |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for item in recommendations:
        lines.append(
            "| "
            + " | ".join(
                escape_cell(value)
                for value in (
                    item.workload,
                    item.predicted_family,
                    item.recommendation_family,
                    item.evidence_project,
                    item.industry_mapping,
                    item.primary,
                    item.secondary,
                    item.risk_if_ignored,
                    item.confidence,
                    item.measure_next,
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Recommendation Rule Summary",
            "",
            "| predicted bottleneck family | recommendation family | deterministic rule |",
            "| --- | --- | --- |",
        ]
    )
    for rule in rules().values():
        lines.append(
            "| "
            + " | ".join(
                escape_cell(value)
                for value in (
                    rule.family,
                    rule.recommendation_family,
                    rule.rule_summary,
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Evidence Mapping",
            "",
            "| recommendation family | evidence project | industry-inspired mapping | evidence-backed action |",
            "| --- | --- | --- | --- |",
        ]
    )
    for rule in rules().values():
        lines.append(
            "| "
            + " | ".join(
                escape_cell(value)
                for value in (
                    rule.recommendation_family,
                    rule.evidence_project,
                    rule.industry_mapping,
                    rule.primary,
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Validation / Confidence Notes",
            "",
            (
                "- High confidence means Project Y family evidence is dominant "
                "or the expected family agrees with the predicted family."
            ),
            (
                "- Medium confidence means the symptoms are mixed but still "
                "support a dominant recommendation family."
            ),
            (
                "- Low confidence means Project Y returned "
                "`mixed_or_uncertain` or the top symptoms conflict."
            ),
            "",
            "| workload | confidence | evidence notes |",
            "| --- | --- | --- |",
        ]
    )
    for item in recommendations:
        lines.append(
            "| "
            + " | ".join(
                escape_cell(value)
                for value in (item.workload, item.confidence, item.evidence_notes)
            )
            + " |"
        )

    lines.extend(
        [
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
                "- Project Z is implemented as a lightweight deterministic "
                "architecture recommendation engine over Project Y workload "
                "families."
            ),
            "",
            "Supported:",
            "",
            (
                "- It supports bounded architecture reasoning, recommendation "
                "families, evidence-backed action discussion, and portfolio / "
                "interview explanation."
            ),
            "",
            "Not Supported:",
            "",
            (
                "- It does not claim Apple Silicon simulation, NVIDIA GPU "
                "simulation, Arm CHI compliance, AXI compliance, ACE "
                "compliance, real hardware profiling, automatic hardware "
                "optimization, real NoC behavior, real cache coherency, "
                "cycle-accurate modeling, silicon validation, or production "
                "signoff."
            ),
            "",
            "Future Work:",
            "",
            (
                "- Future versions may add more deterministic rules or more "
                "workload symptoms while preserving the same claim boundary."
            ),
            "",
            "claim_boundary=PASS",
            "",
        ]
    )
    return "\n".join(lines)


def validate_generated(
    document: str, recommendations: Sequence[Recommendation]
) -> List[str]:
    required_fragments = [
        f"schema_version={SCHEMA_VERSION}",
        "## Workload Recommendation Table",
        "## Recommendation Rule Summary",
        "## Evidence Mapping",
        "## Validation / Confidence Notes",
        "## Unsupported Claims",
        "## Claim Boundary",
        "claim_boundary=PASS",
    ]
    errors = [
        f"generated markdown missing required fragment: {fragment}"
        for fragment in required_fragments
        if fragment not in document
    ]
    for item in recommendations:
        if (
            item.workload not in document
            or item.recommendation_family not in document
            or item.primary not in document
        ):
            errors.append(
                f"generated markdown missing recommendation for {item.workload}"
            )
    return errors


def print_errors(errors: Sequence[str]) -> None:
    for error in errors:
        print(f"[recommendation-r1] ERROR {error}", file=sys.stderr)


def main() -> int:
    args = parse_args()
    root = repo_root()
    input_path = resolve_path(root, args.input)
    classification_path = resolve_path(root, args.classification)
    output_path = resolve_path(root, args.output)

    if not input_path.exists():
        print_errors([f"input CSV does not exist: {input_path}"])
        print("Architecture Recommendation Engine FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1
    if not classification_path.exists():
        print_errors([f"classification markdown does not exist: {classification_path}"])
        print("Architecture Recommendation Engine FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    headers, rows = read_csv_rows(input_path)
    errors = validate_input_schema(input_path, headers, rows, args.strict)
    if args.strict:
        errors.extend(validate_output_path(output_path))
    if errors:
        print_errors(errors)
        print("Architecture Recommendation Engine FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    classifications, parse_errors = parse_classification_markdown(classification_path)
    if parse_errors:
        print_errors(parse_errors)
        print("Architecture Recommendation Engine FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    recommendations, recommendation_errors = generate_recommendations(
        rows, classifications
    )
    if recommendation_errors:
        print_errors(recommendation_errors)
        print("Architecture Recommendation Engine FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    document = render_markdown(root, input_path, classification_path, recommendations)
    if args.strict:
        generated_errors = validate_generated(document, recommendations)
        if generated_errors:
            print_errors(generated_errors)
            print("Architecture Recommendation Engine FAIL")
            print(f"schema_version={SCHEMA_VERSION}")
            return 1

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(document, encoding="utf-8")
    except OSError as exc:
        print_errors([f"cannot write output markdown {output_path}: {exc}"])
        print("Architecture Recommendation Engine FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    print("Architecture Recommendation Engine PASS")
    print(f"workloads={len(recommendations)}")
    print(
        "recommendation_families="
        "fabric_mitigation,"
        "bandwidth_wall_mitigation,"
        "noc_qos_boundary_mitigation,"
        "mixed_evidence_required"
    )
    print("claim_boundary=PASS")
    print(f"schema_version={SCHEMA_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
