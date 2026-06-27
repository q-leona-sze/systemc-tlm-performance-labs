#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


SCHEMA_VERSION = "scenario-r1.0"
DEFAULT_INPUT = "examples/scenarios/sample_architecture_scenarios.csv"
DEFAULT_OUTPUT = "docs/generated/scenario_decision_benchmark.md"

DECISION_FAMILIES = (
    "fabric_decision",
    "bandwidth_wall_decision",
    "noc_qos_boundary_decision",
    "mixed_decision",
)

REQUIRED_COLUMNS = (
    "scenario",
    "description",
    "workload",
    "bottleneck_family",
    "recommendation_family",
    "candidate_actions",
    "primary_metric",
    "secondary_metric",
    "latency_sensitivity",
    "throughput_sensitivity",
    "fairness_sensitivity",
    "ordering_sensitivity",
    "implementation_risk",
    "evidence_project",
    "industry_mapping",
    "expected_decision_family",
    "expected_recommended_action",
)

UNSUPPORTED_CLAIMS = (
    "Not supported: Apple Silicon simulation.",
    "Not supported: NVIDIA GPU simulation.",
    "Not supported: Arm CHI compliance.",
    "Not supported: AXI compliance.",
    "Not supported: ACE compliance.",
    "Not supported: real hardware profiling.",
    "Not supported: automatic hardware optimization.",
    "Not supported: real design-space exploration.",
    "Not supported: real NoC behavior.",
    "Not supported: real cache coherency.",
    "Not supported: cycle-accurate modeling.",
    "Not supported: silicon validation.",
    "Not supported: production signoff.",
)


@dataclass(frozen=True)
class ScenarioDecision:
    scenario: str
    description: str
    workload: str
    bottleneck_family: str
    recommendation_family: str
    decision_family: str
    recommended_action: str
    secondary_recommendation: str
    evidence_project: str
    industry_mapping: str
    confidence: str
    risk_if_wrong: str
    what_to_measure_next: str
    scoring_notes: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a deterministic scenario decision benchmark over bounded "
            "architecture scenario CSV inputs."
        )
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help="Input architecture scenario CSV. Relative paths are resolved from repo root.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Output benchmark markdown. Relative paths are resolved from repo root.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable schema, self-check, generated markdown, and claim-boundary validation.",
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
        errors.append("strict mode requires at least 6 scenario rows")
    return errors


def validate_output_path(output_path: Path) -> List[str]:
    errors: List[str] = []
    if output_path.exists() and output_path.is_dir():
        errors.append(f"output path is a directory: {output_path}")
        return errors
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("a", encoding="utf-8"):
            pass
    except OSError as exc:
        errors.append(f"output markdown is not writable: {output_path}: {exc}")
    return errors


def split_actions(raw_actions: str) -> List[str]:
    return [part.strip() for part in raw_actions.split(";") if part.strip()]


def row_text(row: Dict[str, str]) -> str:
    return " ".join(
        row.get(field, "")
        for field in ("scenario", "description", "workload", "primary_metric", "secondary_metric")
    ).lower()


def decision_family_for(bottleneck_family: str) -> str:
    mapping = {
        "shared_fabric_pressure": "fabric_decision",
        "throughput_bandwidth_wall": "bandwidth_wall_decision",
        "noc_qos_coherency_boundary": "noc_qos_boundary_decision",
        "mixed_or_uncertain": "mixed_decision",
    }
    return mapping.get(bottleneck_family, "mixed_decision")


def add_score(
    scores: Dict[str, int],
    reasons: Dict[str, List[str]],
    action: str,
    points: int,
    reason: str,
) -> None:
    if action not in scores:
        return
    scores[action] += points
    reasons[action].append(f"{action}+{points}: {reason}")


def score_fabric_actions(
    row: Dict[str, str], scores: Dict[str, int], reasons: Dict[str, List[str]]
) -> None:
    latency = row.get("latency_sensitivity", "").strip()
    throughput = row.get("throughput_sensitivity", "").strip()
    fairness = row.get("fairness_sensitivity", "").strip()
    risk = row.get("implementation_risk", "").strip()

    if latency == "high":
        add_score(
            scores,
            reasons,
            "protect_latency_initiator",
            12,
            "high latency sensitivity favors protecting latency-sensitive initiators",
        )
    if fairness == "high":
        add_score(
            scores,
            reasons,
            "throttle_bulk_dma",
            9,
            "high fairness sensitivity favors throttling bulk DMA-like pressure",
        )
        add_score(
            scores,
            reasons,
            "fairness_guard",
            9,
            "high fairness sensitivity favors an explicit fairness guard",
        )
    if throughput == "high" and latency != "high":
        add_score(
            scores,
            reasons,
            "increase_fabric_capacity",
            8,
            "high throughput sensitivity without high latency sensitivity can justify capacity",
        )
    if risk == "high":
        add_score(
            scores,
            reasons,
            "schedule_high_pressure_initiators",
            10,
            "high implementation risk favors scheduling before structural change",
        )


def score_bandwidth_wall_actions(
    row: Dict[str, str], scores: Dict[str, int], reasons: Dict[str, List[str]]
) -> None:
    text = row_text(row)
    latency = row.get("latency_sensitivity", "").strip()
    primary_metric = row.get("primary_metric", "").strip()

    if "bursty" in text or "tail" in text:
        add_score(
            scores,
            reasons,
            "shape_bursty_traffic",
            14,
            "bursty or tail-latency wording favors burst shaping",
        )
    if primary_metric == "throughput" or "memory wall" in text or "bandwidth wall" in text:
        add_score(
            scores,
            reasons,
            "throttle_outstanding_after_knee",
            11,
            "throughput memory-wall signal favors throttling after the knee point",
        )
    if latency == "high":
        add_score(
            scores,
            reasons,
            "shape_bursty_traffic",
            4,
            "high latency sensitivity avoids blindly increasing outstanding depth",
        )
        add_score(
            scores,
            reasons,
            "throttle_outstanding_after_knee",
            3,
            "high latency sensitivity favors controlled outstanding pressure",
        )
        add_score(
            scores,
            reasons,
            "increase_outstanding_depth",
            -5,
            "high latency sensitivity penalizes blind outstanding-depth increase",
        )
    add_score(
        scores,
        reasons,
        "bandwidth_aware_batching",
        3,
        "bandwidth-aware batching is a secondary mitigation when present",
    )


def score_noc_boundary_actions(
    row: Dict[str, str], scores: Dict[str, int], reasons: Dict[str, List[str]]
) -> None:
    text = row_text(row)
    fairness = row.get("fairness_sensitivity", "").strip()
    ordering = row.get("ordering_sensitivity", "").strip()

    if ordering == "high":
        add_score(
            scores,
            reasons,
            "reduce_boundary_crossing",
            12,
            "high ordering sensitivity favors reducing boundary crossings",
        )
    if "write-heavy" in text or "read-tail" in text or "write interference" in text:
        add_score(
            scores,
            reasons,
            "protect_read_latency_from_bulk_write",
            14,
            "write-heavy read-tail interference favors read-latency protection",
        )
    if fairness == "high":
        add_score(
            scores,
            reasons,
            "qos_partition",
            9,
            "high fairness sensitivity favors QoS partitioning",
        )
    if "hotspot" in text or "route hotspot" in text:
        add_score(
            scores,
            reasons,
            "route_isolation",
            10,
            "route hotspot wording favors route isolation",
        )


def score_mixed_actions(
    scores: Dict[str, int], reasons: Dict[str, List[str]]
) -> None:
    add_score(
        scores,
        reasons,
        "run_targeted_evidence_checks",
        12,
        "mixed evidence should start with targeted AT-6/AT-7/AT-8 checks",
    )
    add_score(
        scores,
        reasons,
        "collect_more_workload_symptoms",
        8,
        "mixed evidence benefits from more workload symptoms",
    )
    add_score(
        scores,
        reasons,
        "split_scenario_by_bottleneck_family",
        7,
        "mixed evidence benefits from splitting by bottleneck family",
    )
    add_score(
        scores,
        reasons,
        "avoid_single_family_overfit",
        6,
        "mixed evidence should avoid overfitting one family",
    )


def score_actions(row: Dict[str, str]) -> Tuple[str, str, str]:
    candidate_actions = split_actions(row.get("candidate_actions", ""))
    scores = {action: 0 for action in candidate_actions}
    reasons: Dict[str, List[str]] = {action: [] for action in candidate_actions}
    bottleneck_family = row.get("bottleneck_family", "").strip()

    if bottleneck_family == "shared_fabric_pressure":
        score_fabric_actions(row, scores, reasons)
    elif bottleneck_family == "throughput_bandwidth_wall":
        score_bandwidth_wall_actions(row, scores, reasons)
    elif bottleneck_family == "noc_qos_coherency_boundary":
        score_noc_boundary_actions(row, scores, reasons)
    else:
        score_mixed_actions(scores, reasons)

    if not scores:
        return "", "", "no candidate actions provided"

    ordered = sorted(scores.items(), key=lambda item: (-item[1], candidate_actions.index(item[0])))
    recommended_action = ordered[0][0]
    secondary = ordered[1][0] if len(ordered) > 1 and ordered[1][1] > 0 else ""
    note_parts = []
    for action, score in ordered:
        action_reasons = "; ".join(reasons[action]) or "no rule matched"
        note_parts.append(f"{action}={score} ({action_reasons})")
    return recommended_action, secondary, " | ".join(note_parts)


def confidence_from_notes(scoring_notes: str, decision_family: str) -> str:
    score_values: List[int] = []
    for part in scoring_notes.split(" | "):
        if "=" not in part:
            continue
        raw_score = part.split("=", 1)[1].split(" ", 1)[0]
        try:
            score_values.append(int(raw_score))
        except ValueError:
            continue
    ordered = sorted(score_values, reverse=True)
    if decision_family == "mixed_decision":
        return "medium"
    if not ordered:
        return "low"
    gap = ordered[0] - ordered[1] if len(ordered) > 1 else ordered[0]
    if gap >= 5:
        return "high"
    if gap >= 2:
        return "medium"
    return "low"


def risk_if_wrong(row: Dict[str, str], action: str) -> str:
    action_risks = {
        "protect_latency_initiator": (
            "latency-sensitive traffic can still lose tail behavior if bulk pressure "
            "or starvation is the real dominant symptom"
        ),
        "throttle_bulk_dma": (
            "bulk throughput may be capped without reducing the actual latency path"
        ),
        "fairness_guard": (
            "fairness can improve while absolute fabric capacity remains saturated"
        ),
        "increase_fabric_capacity": (
            "capacity can hide symptoms without fixing scheduling or starvation risk"
        ),
        "schedule_high_pressure_initiators": (
            "scheduling can reduce overlap but may leave peak throughput underused"
        ),
        "throttle_outstanding_after_knee": (
            "too little throttling leaves queue buildup; too much throttling cuts useful throughput"
        ),
        "shape_bursty_traffic": (
            "burst shaping can reduce tails but may underfill the bandwidth path"
        ),
        "bandwidth_aware_batching": (
            "batching can improve bandwidth efficiency while delaying latency-sensitive work"
        ),
        "increase_outstanding_depth": (
            "additional outstanding depth can become queue delay after saturation"
        ),
        "protect_read_latency_from_bulk_write": (
            "read protection can help tails but may not fix boundary serialization"
        ),
        "reduce_boundary_crossing": (
            "boundary reduction can help ordering pressure but may not solve route hotspots"
        ),
        "qos_partition": (
            "QoS partitioning can isolate classes while total route capacity remains limited"
        ),
        "route_isolation": (
            "route isolation can reduce hotspots while increasing path imbalance elsewhere"
        ),
        "run_targeted_evidence_checks": (
            "without targeted checks, a single-family action can overfit mixed symptoms"
        ),
        "collect_more_workload_symptoms": (
            "collecting symptoms delays action but reduces misclassification risk"
        ),
        "split_scenario_by_bottleneck_family": (
            "splitting can clarify evidence but may miss cross-family interactions"
        ),
        "avoid_single_family_overfit": (
            "avoiding overfit is safer but can defer an obvious local mitigation"
        ),
    }
    return action_risks.get(
        action,
        f"wrong action can overfit {row.get('bottleneck_family', 'unknown')} symptoms",
    )


def measure_next(row: Dict[str, str], action: str) -> str:
    bottleneck_family = row.get("bottleneck_family", "").strip()
    if bottleneck_family == "shared_fabric_pressure":
        return (
            "per-initiator p95/p99 latency, bandwidth share, fabric queue peak, "
            "and starvation events"
        )
    if bottleneck_family == "throughput_bandwidth_wall":
        return (
            "throughput knee point, memory utilization, queue peak, average "
            "outstanding depth, and tail latency"
        )
    if bottleneck_family == "noc_qos_coherency_boundary":
        return (
            "boundary crossings, ordering events, read/write interference, QoS "
            "class pressure, route utilization, and starvation events"
        )
    return (
        "phase-split workload symptoms plus targeted AT-6, AT-7, and AT-8 "
        "evidence checks before choosing one action"
    )


def generate_decisions(
    rows: Sequence[Dict[str, str]], strict: bool
) -> Tuple[List[ScenarioDecision], List[str]]:
    decisions: List[ScenarioDecision] = []
    errors: List[str] = []
    for index, row in enumerate(rows, start=1):
        scenario = row.get("scenario", "").strip()
        if not scenario:
            errors.append(f"row {index}: missing scenario")
            continue

        decision_family = decision_family_for(row.get("bottleneck_family", "").strip())
        recommended_action, secondary, scoring_notes = score_actions(row)
        if not recommended_action:
            errors.append(f"{scenario}: no recommended action selected")
            continue

        if strict:
            expected_family = row.get("expected_decision_family", "").strip()
            expected_action = row.get("expected_recommended_action", "").strip()
            if expected_family and expected_family != decision_family:
                errors.append(
                    f"{scenario}: expected_decision_family={expected_family}, "
                    f"got {decision_family}"
                )
            if expected_action and expected_action != recommended_action:
                errors.append(
                    f"{scenario}: expected_recommended_action={expected_action}, "
                    f"got {recommended_action}"
                )

        decisions.append(
            ScenarioDecision(
                scenario=scenario,
                description=row.get("description", "").strip(),
                workload=row.get("workload", "").strip(),
                bottleneck_family=row.get("bottleneck_family", "").strip(),
                recommendation_family=row.get("recommendation_family", "").strip(),
                decision_family=decision_family,
                recommended_action=recommended_action,
                secondary_recommendation=secondary,
                evidence_project=row.get("evidence_project", "").strip(),
                industry_mapping=row.get("industry_mapping", "").strip(),
                confidence=confidence_from_notes(scoring_notes, decision_family),
                risk_if_wrong=risk_if_wrong(row, recommended_action),
                what_to_measure_next=measure_next(row, recommended_action),
                scoring_notes=scoring_notes,
            )
        )
    return decisions, errors


def render_markdown(
    root: Path, input_path: Path, decisions: Sequence[ScenarioDecision]
) -> str:
    lines = [
        "# Scenario Decision Benchmark",
        "",
        f"schema_version={SCHEMA_VERSION}",
        f"input_file={display_path(root, input_path)}",
        "",
        "## Purpose",
        "",
        (
            "This generated report is the Project AA scenario decision benchmark. "
            "It consumes architecture scenario rows, candidate actions, sensitivity "
            "constraints, and evidence mappings, then produces bounded scenario-level "
            "decision outputs."
        ),
        "",
        (
            "It is a bounded rule-based scenario decision benchmark and architecture "
            "reasoning layer. It is not an optimizer, not machine learning, not a "
            "profiler, not a real hardware design-space exploration tool, and not "
            "a signoff artifact."
        ),
        "",
        "## Source Input",
        "",
        f"- Architecture scenarios: `{display_path(root, input_path)}`",
        "- Scenario rows are deterministic sample cases for portfolio and interview discussion.",
        "",
        "## Scenario Decision Table",
        "",
        "| scenario | workload | bottleneck_family | recommendation_family | decision_family | recommended_action | evidence_project | industry_mapping | confidence | risk_if_wrong | what_to_measure_next |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for item in decisions:
        lines.append(
            "| "
            + " | ".join(
                escape_cell(value)
                for value in (
                    item.scenario,
                    item.workload,
                    item.bottleneck_family,
                    item.recommendation_family,
                    item.decision_family,
                    item.recommended_action,
                    item.evidence_project,
                    item.industry_mapping,
                    item.confidence,
                    item.risk_if_wrong,
                    item.what_to_measure_next,
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Action Scoring Notes",
            "",
            "| scenario | recommended_action | secondary_recommendation | scoring_notes |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in decisions:
        lines.append(
            "| "
            + " | ".join(
                escape_cell(value)
                for value in (
                    item.scenario,
                    item.recommended_action,
                    item.secondary_recommendation or "none",
                    item.scoring_notes,
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Scenario Decision Rule Summary",
            "",
            "| bottleneck_family | decision_family | deterministic rule summary |",
            "| --- | --- | --- |",
            (
                "| shared_fabric_pressure | fabric_decision | High latency sensitivity favors "
                "`protect_latency_initiator`; high fairness sensitivity favors "
                "`throttle_bulk_dma` or `fairness_guard`; high implementation risk "
                "favors `schedule_high_pressure_initiators`. |"
            ),
            (
                "| throughput_bandwidth_wall | bandwidth_wall_decision | Throughput memory-wall "
                "signals favor `throttle_outstanding_after_knee`; bursty or tail-latency "
                "signals favor `shape_bursty_traffic`; high latency sensitivity penalizes "
                "blind `increase_outstanding_depth`. |"
            ),
            (
                "| noc_qos_coherency_boundary | noc_qos_boundary_decision | High ordering sensitivity "
                "favors `reduce_boundary_crossing`; write-heavy read-tail interference "
                "favors `protect_read_latency_from_bulk_write`; fairness and hotspot "
                "signals favor `qos_partition` or `route_isolation`. |"
            ),
            (
                "| mixed_or_uncertain | mixed_decision | Mixed evidence favors "
                "`run_targeted_evidence_checks`, then more symptoms, phase splitting, "
                "and avoiding single-family overfit. |"
            ),
            "",
            "## Evidence Mapping",
            "",
            "| decision_family | evidence_project | industry_mapping | interpretation |",
            "| --- | --- | --- | --- |",
            (
                "| fabric_decision | AT-6 | Apple-like | Shared-fabric pressure decisions "
                "should be backed by latency, bandwidth-share, queue, and starvation evidence. |"
            ),
            (
                "| bandwidth_wall_decision | AT-7 | NVIDIA-like | Bandwidth-wall decisions "
                "should be backed by throughput knee, outstanding-depth, queue, utilization, "
                "and tail-latency evidence. |"
            ),
            (
                "| noc_qos_boundary_decision | AT-8 | Arm-like | NoC/QoS boundary decisions "
                "should be backed by route pressure, boundary crossing, ordering, QoS, "
                "read/write interference, and starvation evidence. |"
            ),
            (
                "| mixed_decision | AT-6+AT-7+AT-8 | Mixed | Mixed decisions should run targeted "
                "evidence checks before choosing a single architecture action. |"
            ),
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
                "- Project AA is implemented as a lightweight deterministic scenario "
                f"decision benchmark with `schema_version={SCHEMA_VERSION}`."
            ),
            "",
            "Supported:",
            "",
            (
                "- It supports bounded rule-based scenario decision benchmarking, "
                "scenario-level decision discussion, evidence-backed decision review, "
                "and portfolio / interview architecture reasoning."
            ),
            "",
            "Not Supported:",
            "",
            (
                "- It does not claim Apple Silicon simulation, NVIDIA GPU simulation, "
                "Arm CHI compliance, AXI compliance, ACE compliance, real hardware "
                "profiling, automatic hardware optimization, real design-space exploration, "
                "real NoC behavior, real cache coherency, cycle-accurate modeling, "
                "silicon validation, or production signoff."
            ),
            "",
            "Future Work:",
            "",
            (
                "- Future versions may add more deterministic scenario rows or scoring "
                "rules only when new evidence artifacts justify them."
            ),
            "",
            "claim_boundary=PASS",
            "",
        ]
    )
    return "\n".join(lines)


def validate_generated(
    document: str, decisions: Sequence[ScenarioDecision]
) -> List[str]:
    required_fragments = [
        f"schema_version={SCHEMA_VERSION}",
        "## Scenario Decision Table",
        "## Action Scoring Notes",
        "## Scenario Decision Rule Summary",
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
    for item in decisions:
        if item.scenario not in document or item.recommended_action not in document:
            errors.append(
                f"generated markdown missing recommended_action for {item.scenario}"
            )
    return errors


def print_errors(errors: Sequence[str]) -> None:
    for error in errors:
        print(f"[scenario-r1] ERROR {error}", file=sys.stderr)


def main() -> int:
    args = parse_args()
    root = repo_root()
    input_path = resolve_path(root, args.input)
    output_path = resolve_path(root, args.output)

    if not input_path.exists():
        print_errors([f"input CSV does not exist: {input_path}"])
        print("Scenario Decision Benchmark FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    headers, rows = read_csv_rows(input_path)
    errors = validate_input_schema(input_path, headers, rows, args.strict)
    if args.strict:
        errors.extend(validate_output_path(output_path))
    if errors:
        print_errors(errors)
        print("Scenario Decision Benchmark FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    decisions, decision_errors = generate_decisions(rows, args.strict)
    if decision_errors:
        print_errors(decision_errors)
        print("Scenario Decision Benchmark FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    document = render_markdown(root, input_path, decisions)
    if args.strict:
        generated_errors = validate_generated(document, decisions)
        if generated_errors:
            print_errors(generated_errors)
            print("Scenario Decision Benchmark FAIL")
            print(f"schema_version={SCHEMA_VERSION}")
            return 1

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(document, encoding="utf-8")
    except OSError as exc:
        print_errors([f"cannot write output markdown {output_path}: {exc}"])
        print("Scenario Decision Benchmark FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    print("Scenario Decision Benchmark PASS")
    print(f"scenarios={len(decisions)}")
    print(
        "decision_families="
        "fabric_decision,"
        "bandwidth_wall_decision,"
        "noc_qos_boundary_decision,"
        "mixed_decision"
    )
    print("claim_boundary=PASS")
    print(f"schema_version={SCHEMA_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
