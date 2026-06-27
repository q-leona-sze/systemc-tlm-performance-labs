#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


SCHEMA_VERSION = "memo-r1.0"
SCENARIO_SCHEMA_VERSION = "scenario-r1.0"
RECOMMENDATION_SCHEMA_VERSION = "recommendation-r1.0"
CLASSIFIER_SCHEMA_VERSION = "classifier-r1.0"

DEFAULT_REQUESTS = "examples/decision_memos/sample_decision_memo_requests.csv"
DEFAULT_SCENARIO_REPORT = "docs/generated/scenario_decision_benchmark.md"
DEFAULT_RECOMMENDATION_REPORT = "docs/generated/architecture_recommendations.md"
DEFAULT_CLASSIFICATION_REPORT = "docs/generated/workload_bottleneck_classification.md"
DEFAULT_OUTPUT = "docs/generated/architecture_decision_memos.md"

REQUIRED_COLUMNS = (
    "memo_id",
    "scenario",
    "workload",
    "decision_family",
    "recommended_action",
    "evidence_project",
    "industry_mapping",
    "memo_type",
    "audience",
    "decision_context",
    "expected_primary_decision",
    "expected_memo_type",
)

MEMO_TYPES = (
    "fabric_memo",
    "bandwidth_wall_memo",
    "noc_qos_boundary_memo",
    "mixed_evidence_memo",
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
class ScenarioEvidence:
    scenario: str
    workload: str
    decision_family: str
    recommended_action: str
    evidence_project: str
    industry_mapping: str
    confidence: str
    risk_if_wrong: str
    what_to_measure_next: str


@dataclass(frozen=True)
class RecommendationEvidence:
    workload: str
    predicted_family: str
    recommendation_family: str
    evidence_project: str
    industry_mapping: str
    primary: str
    secondary: str
    risk_if_ignored: str
    confidence: str
    measure_next: str


@dataclass(frozen=True)
class ClassificationEvidence:
    workload: str
    predicted_family: str
    confidence: str
    evidence_mapping: str
    recommendation: str
    reason: str


@dataclass(frozen=True)
class MemoRequest:
    memo_id: str
    scenario: str
    workload: str
    decision_family: str
    recommended_action: str
    evidence_project: str
    industry_mapping: str
    memo_type: str
    audience: str
    decision_context: str
    expected_primary_decision: str
    expected_memo_type: str


@dataclass(frozen=True)
class MemoRule:
    memo_type: str
    decision: str
    evidence_project: str
    industry_mapping: str
    problem: str
    secondary: str
    risk_if_ignored: str
    measure_next: str
    confidence: str


@dataclass(frozen=True)
class DecisionMemo:
    request: MemoRequest
    decision: str
    primary_recommendation: str
    secondary_considerations: str
    problem: str
    risk_if_ignored: str
    risk_if_wrong: str
    measure_next: str
    confidence: str
    evidence_chain: str
    scenario_evidence: ScenarioEvidence
    recommendation_evidence: RecommendationEvidence
    classification_evidence: ClassificationEvidence


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate bounded deterministic architecture decision memos from "
            "scenario, recommendation, classification, and memo-request inputs."
        )
    )
    parser.add_argument(
        "--requests",
        default=DEFAULT_REQUESTS,
        help="Input decision memo request CSV. Relative paths are resolved from repo root.",
    )
    parser.add_argument(
        "--scenario-report",
        default=DEFAULT_SCENARIO_REPORT,
        help="Project AA scenario decision benchmark markdown.",
    )
    parser.add_argument(
        "--recommendation-report",
        default=DEFAULT_RECOMMENDATION_REPORT,
        help="Project Z architecture recommendation markdown.",
    )
    parser.add_argument(
        "--classification-report",
        default=DEFAULT_CLASSIFICATION_REPORT,
        help="Project Y workload bottleneck classification markdown.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Output architecture decision memo markdown.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable input, output, report, self-check, and claim-boundary validation.",
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


def split_markdown_row(line: str) -> List[str]:
    line = line.strip()
    if not line.startswith("|") or not line.endswith("|"):
        return []
    return [cell.strip().replace("\\|", "|") for cell in line.strip("|").split("|")]


def table_after_heading(text: str, heading: str) -> Tuple[List[str], List[str]]:
    lines = text.splitlines()
    table_start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            table_start = index
            break
    if table_start is None:
        return [], [f"report missing heading: {heading}"]

    table_lines: List[str] = []
    for line in lines[table_start + 1 :]:
        if line.startswith("## "):
            break
        if line.strip().startswith("|"):
            table_lines.append(line)
    if len(table_lines) < 3:
        return [], [f"report table under {heading} has no data rows"]
    return table_lines, []


def parse_markdown_table(
    text: str,
    heading: str,
    required_headers: Sequence[str],
    key_header: str,
) -> Tuple[Dict[str, Dict[str, str]], List[str]]:
    table_lines, errors = table_after_heading(text, heading)
    if errors:
        return {}, errors

    headers = split_markdown_row(table_lines[0])
    header_index = {header: index for index, header in enumerate(headers)}
    missing_headers = [
        header for header in required_headers if header not in header_index
    ]
    if missing_headers:
        return {}, [
            f"{heading} missing required column(s): {', '.join(missing_headers)}"
        ]

    rows: Dict[str, Dict[str, str]] = {}
    for line in table_lines[2:]:
        cells = split_markdown_row(line)
        if len(cells) != len(headers):
            errors.append(f"{heading} row has unexpected shape: {line}")
            continue
        row = {header: cells[index] for header, index in header_index.items()}
        key = row.get(key_header, "").strip()
        if key:
            rows[key] = row
    return rows, errors


def validate_existing_inputs(
    request_path: Path,
    scenario_path: Path,
    recommendation_path: Path,
    classification_path: Path,
) -> List[str]:
    errors: List[str] = []
    for label, path in (
        ("requests CSV", request_path),
        ("scenario report", scenario_path),
        ("recommendation report", recommendation_path),
        ("classification report", classification_path),
    ):
        if not path.exists():
            errors.append(f"{label} does not exist: {path}")
        elif path.is_dir():
            errors.append(f"{label} is a directory: {path}")
    return errors


def validate_request_schema(
    request_path: Path, headers: Sequence[str], rows: Sequence[Dict[str, str]], strict: bool
) -> List[str]:
    errors: List[str] = []
    if not request_path.exists():
        errors.append(f"requests CSV does not exist: {request_path}")
        return errors
    missing = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing:
        errors.append(f"requests CSV missing required column(s): {', '.join(missing)}")
    if strict and len(rows) < 6:
        errors.append("strict mode requires at least 6 memo requests")
    return errors


def validate_output_path(output_path: Path) -> List[str]:
    errors: List[str] = []
    if output_path.exists() and output_path.is_dir():
        errors.append(f"output markdown is a directory: {output_path}")
        return errors
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("a", encoding="utf-8"):
            pass
    except OSError as exc:
        errors.append(f"output markdown is not writable: {output_path}: {exc}")
    return errors


def validate_report_text(path: Path, text: str, schema: str, label: str) -> List[str]:
    errors: List[str] = []
    if f"schema_version={schema}" not in text:
        errors.append(f"{label} missing schema_version={schema}")
    if "claim_boundary=PASS" not in text:
        errors.append(f"{label} missing claim_boundary=PASS")
    return errors


def parse_scenario_report(text: str) -> Tuple[Dict[str, ScenarioEvidence], List[str]]:
    rows, errors = parse_markdown_table(
        text,
        "## Scenario Decision Table",
        (
            "scenario",
            "workload",
            "decision_family",
            "recommended_action",
            "evidence_project",
            "industry_mapping",
            "confidence",
            "risk_if_wrong",
            "what_to_measure_next",
        ),
        "scenario",
    )
    evidence = {
        key: ScenarioEvidence(
            scenario=row["scenario"],
            workload=row["workload"],
            decision_family=row["decision_family"],
            recommended_action=row["recommended_action"],
            evidence_project=row["evidence_project"],
            industry_mapping=row["industry_mapping"],
            confidence=row["confidence"],
            risk_if_wrong=row["risk_if_wrong"],
            what_to_measure_next=row["what_to_measure_next"],
        )
        for key, row in rows.items()
    }
    return evidence, errors


def parse_recommendation_report(
    text: str,
) -> Tuple[Dict[str, RecommendationEvidence], List[str]]:
    rows, errors = parse_markdown_table(
        text,
        "## Workload Recommendation Table",
        (
            "workload",
            "predicted bottleneck family",
            "recommendation family",
            "evidence project",
            "industry-inspired mapping",
            "primary recommendation",
            "secondary recommendation",
            "risk if ignored",
            "confidence",
            "what to measure next",
        ),
        "workload",
    )
    evidence = {
        key: RecommendationEvidence(
            workload=row["workload"],
            predicted_family=row["predicted bottleneck family"],
            recommendation_family=row["recommendation family"],
            evidence_project=row["evidence project"],
            industry_mapping=row["industry-inspired mapping"],
            primary=row["primary recommendation"],
            secondary=row["secondary recommendation"],
            risk_if_ignored=row["risk if ignored"],
            confidence=row["confidence"],
            measure_next=row["what to measure next"],
        )
        for key, row in rows.items()
    }
    return evidence, errors


def parse_classification_report(
    text: str,
) -> Tuple[Dict[str, ClassificationEvidence], List[str]]:
    rows, errors = parse_markdown_table(
        text,
        "## Workload Classification Table",
        (
            "workload",
            "predicted_family",
            "confidence",
            "evidence mapping",
            "recommendation",
            "reason",
        ),
        "workload",
    )
    evidence = {
        key: ClassificationEvidence(
            workload=row["workload"],
            predicted_family=row["predicted_family"],
            confidence=row["confidence"],
            evidence_mapping=row["evidence mapping"],
            recommendation=row["recommendation"],
            reason=row["reason"],
        )
        for key, row in rows.items()
    }
    return evidence, errors


def request_from_row(row: Dict[str, str], row_index: int) -> Tuple[MemoRequest, List[str]]:
    errors: List[str] = []
    values = {column: row.get(column, "").strip() for column in REQUIRED_COLUMNS}
    for column, value in values.items():
        if not value:
            errors.append(f"row {row_index}: missing value for {column}")
    request = MemoRequest(**values)
    if request.memo_type and request.memo_type not in MEMO_TYPES:
        errors.append(f"{request.memo_id}: unknown memo_type={request.memo_type}")
    return request, errors


def memo_rules() -> Dict[str, MemoRule]:
    return {
        "fabric_memo": MemoRule(
            memo_type="fabric_memo",
            decision="protect_latency_initiator",
            evidence_project="AT-6",
            industry_mapping="Apple-like",
            problem=(
                "Shared-fabric pressure can expose latency-sensitive initiator "
                "traffic to queue growth, unfair bandwidth share, and starvation risk."
            ),
            secondary=(
                "Use bounded priority, bandwidth partitioning, bulk-traffic caps, "
                "and starvation checks before arguing for more fabric capacity."
            ),
            risk_if_ignored=(
                "shared-fabric pressure can turn concurrent initiator traffic "
                "into queue growth and latency outliers"
            ),
            measure_next=(
                "queue peak, initiator-level latency, starvation, fabric utilization, "
                "and traffic mix"
            ),
            confidence="high when AT-6-style fabric symptoms and Project AA agree",
        ),
        "bandwidth_wall_memo": MemoRule(
            memo_type="bandwidth_wall_memo",
            decision="throttle_outstanding_after_knee",
            evidence_project="AT-7",
            industry_mapping="NVIDIA-like",
            problem=(
                "A throughput-oriented workload can hit a bandwidth knee where "
                "additional outstanding pressure grows queues faster than useful throughput."
            ),
            secondary=(
                "Shape bursty traffic, identify the saturation knee, and compare "
                "throughput gain against p99 latency and queue growth."
            ),
            risk_if_ignored=(
                "increasing pressure past the bandwidth knee may grow queues "
                "without proportional throughput gains"
            ),
            measure_next=(
                "throughput saturation knee, outstanding depth, queue peak, "
                "p99 latency, and burstiness"
            ),
            confidence="high when AT-7-style bandwidth-wall symptoms and Project AA agree",
        ),
        "noc_qos_boundary_memo": MemoRule(
            memo_type="noc_qos_boundary_memo",
            decision="protect_read_latency_from_bulk_write",
            evidence_project="AT-8",
            industry_mapping="Arm-like",
            problem=(
                "Boundary crossing, ordering-sensitive traffic, and write-heavy "
                "interference can create tail latency even when average throughput looks acceptable."
            ),
            secondary=(
                "Reduce boundary crossings, protect read latency from bulk writes, "
                "partition QoS-like pressure, and watch starvation events."
            ),
            risk_if_ignored=(
                "boundary-crossing, ordering-sensitive, or write-heavy pressure "
                "can create tail latency and starvation symptoms"
            ),
            measure_next=(
                "boundary crossing rate, ordering events, read/write interference, "
                "QoS pressure, and starvation events"
            ),
            confidence="high when AT-8-style boundary/QoS symptoms and Project AA agree",
        ),
        "mixed_evidence_memo": MemoRule(
            memo_type="mixed_evidence_memo",
            decision="run_targeted_evidence_checks",
            evidence_project="AT-6+AT-7+AT-8",
            industry_mapping="Mixed",
            problem=(
                "Mixed symptoms make it risky to choose one mitigation family "
                "before separating fabric, bandwidth-wall, and boundary/QoS evidence."
            ),
            secondary=(
                "Split the scenario into targeted evidence checks, then choose "
                "the narrowest action that survives the evidence review."
            ),
            risk_if_ignored=(
                "overfitting one bottleneck family can lead to wrong mitigation "
                "and hidden regressions"
            ),
            measure_next=(
                "split the scenario into fabric, bandwidth-wall, and boundary/QoS "
                "symptoms; rerun targeted reasoning stack"
            ),
            confidence="medium until targeted AT-6/AT-7/AT-8 checks separate symptoms",
        ),
    }


def generate_memos(
    request_rows: Sequence[Dict[str, str]],
    scenario_evidence: Dict[str, ScenarioEvidence],
    recommendation_evidence: Dict[str, RecommendationEvidence],
    classification_evidence: Dict[str, ClassificationEvidence],
    strict: bool,
) -> Tuple[List[DecisionMemo], List[str]]:
    errors: List[str] = []
    memos: List[DecisionMemo] = []
    rules = memo_rules()

    for row_index, row in enumerate(request_rows, start=2):
        request, request_errors = request_from_row(row, row_index)
        errors.extend(request_errors)
        if request_errors:
            continue

        if strict and request.expected_primary_decision != request.recommended_action:
            errors.append(
                f"{request.memo_id}: expected_primary_decision="
                f"{request.expected_primary_decision}, got {request.recommended_action}"
            )
        if strict and request.expected_memo_type != request.memo_type:
            errors.append(
                f"{request.memo_id}: expected_memo_type={request.expected_memo_type}, "
                f"got {request.memo_type}"
            )

        rule = rules[request.memo_type]
        scenario = scenario_evidence.get(request.scenario)
        recommendation = recommendation_evidence.get(request.workload)
        classification = classification_evidence.get(request.workload)
        if scenario is None:
            errors.append(f"{request.memo_id}: missing Project AA scenario row")
            continue
        if recommendation is None:
            errors.append(f"{request.memo_id}: missing Project Z recommendation row")
            continue
        if classification is None:
            errors.append(f"{request.memo_id}: missing Project Y classification row")
            continue
        if strict and scenario.recommended_action != request.recommended_action:
            errors.append(
                f"{request.memo_id}: Project AA action={scenario.recommended_action}, "
                f"request action={request.recommended_action}"
            )
        if strict and scenario.decision_family != request.decision_family:
            errors.append(
                f"{request.memo_id}: Project AA decision_family="
                f"{scenario.decision_family}, request={request.decision_family}"
            )

        selected_evidence = request.evidence_project or rule.evidence_project
        selected_mapping = request.industry_mapping or rule.industry_mapping
        evidence_chain = (
            f"{selected_evidence} evidence -> Project X industry mapping "
            f"({selected_mapping}) -> Project Y bottleneck classification "
            f"({classification.predicted_family}) -> Project Z recommendation "
            f"({recommendation.recommendation_family}) -> Project AA scenario "
            f"decision ({scenario.recommended_action}) -> Project AB memo "
            f"({request.memo_type})"
        )

        memos.append(
            DecisionMemo(
                request=request,
                decision=request.recommended_action,
                primary_recommendation=request.recommended_action,
                secondary_considerations=rule.secondary,
                problem=rule.problem,
                risk_if_ignored=rule.risk_if_ignored,
                risk_if_wrong=scenario.risk_if_wrong,
                measure_next=rule.measure_next,
                confidence=scenario.confidence or rule.confidence,
                evidence_chain=evidence_chain,
                scenario_evidence=scenario,
                recommendation_evidence=recommendation,
                classification_evidence=classification,
            )
        )

    return memos, errors


def render_memo(item: DecisionMemo) -> List[str]:
    request = item.request
    chain_statement = (
        "AT-6/AT-7/AT-8 evidence -> Project X industry mapping -> "
        "Project Y bottleneck classification -> Project Z recommendation -> "
        "Project AA scenario decision -> Project AB memo."
    )
    return [
        f"## Memo: {request.memo_id}",
        "",
        f"- Memo ID: `{request.memo_id}`",
        f"- Scenario: `{request.scenario}`",
        f"- Workload: `{request.workload}`",
        f"- Audience: `{request.audience}`",
        f"- Memo Type: `{request.memo_type}`",
        f"- Decision Family: `{request.decision_family}`",
        "",
        "### Executive Summary",
        "",
        (
            f"For `{request.scenario}`, the bounded architecture decision is "
            f"`{item.decision}`. The memo turns Project AA scenario output into "
            f"an architecture review memo while preserving the Project X/Y/Z/AA "
            f"evidence chain and claim boundary."
        ),
        "",
        "### Problem",
        "",
        f"{request.decision_context} {item.problem}",
        "",
        "### Decision",
        "",
        f"- Decision: `{item.decision}`",
        f"- Evidence project: `{request.evidence_project}`",
        f"- Industry-inspired mapping: `{request.industry_mapping}`",
        "",
        "### Evidence Chain",
        "",
        f"- Required chain: {chain_statement}",
        f"- Selected chain: {item.evidence_chain}.",
        (
            f"- Project Y classification: `{request.workload}` -> "
            f"`{item.classification_evidence.predicted_family}` "
            f"({item.classification_evidence.reason})."
        ),
        (
            f"- Project Z recommendation: "
            f"`{item.recommendation_evidence.recommendation_family}`; "
            f"primary evidence-backed action: "
            f"{item.recommendation_evidence.primary}."
        ),
        (
            f"- Project AA scenario decision: `{request.scenario}` -> "
            f"`{item.scenario_evidence.recommended_action}` with "
            f"`{item.scenario_evidence.confidence}` confidence."
        ),
        "",
        "### Primary Recommendation",
        "",
        f"- `{item.primary_recommendation}`",
        "",
        "### Secondary Considerations",
        "",
        f"- {item.secondary_considerations}",
        f"- Project Z secondary recommendation: {item.recommendation_evidence.secondary}.",
        "",
        "### Risk if Ignored",
        "",
        f"- {item.risk_if_ignored}.",
        "",
        "### Risk if Wrong",
        "",
        f"- {item.risk_if_wrong}.",
        "",
        "### What to Measure Next",
        "",
        f"- {item.measure_next}.",
        f"- Project AA next measurement hook: {item.scenario_evidence.what_to_measure_next}.",
        "",
        "### Confidence",
        "",
        (
            f"- {item.confidence}. Classification confidence is "
            f"`{item.classification_evidence.confidence}` and recommendation "
            f"confidence is `{item.recommendation_evidence.confidence}`."
        ),
        "",
        "### Claim Boundary",
        "",
        (
            "- This memo is a bounded rule-based architecture decision memo. "
            "It supports architecture review storytelling and evidence-chain "
            "communication, not automatic hardware design or signoff."
        ),
        "",
    ]


def render_markdown(
    root: Path,
    request_path: Path,
    scenario_path: Path,
    recommendation_path: Path,
    classification_path: Path,
    memos: Sequence[DecisionMemo],
) -> str:
    lines = [
        "# Architecture Decision Memos",
        "",
        f"schema_version={SCHEMA_VERSION}",
        "",
        "## Purpose",
        "",
        (
            "This generated report is Project AB: Architecture Decision Memo "
            "Generator. It turns scenario-level decisions into bounded "
            "architecture review memos for portfolio and interview storytelling."
        ),
        "",
        "## Source Inputs",
        "",
        f"- Memo requests: `{display_path(root, request_path)}`",
        f"- Project AA scenario report: `{display_path(root, scenario_path)}`",
        f"- Project Z recommendation report: `{display_path(root, recommendation_path)}`",
        f"- Project Y classification report: `{display_path(root, classification_path)}`",
        "",
        "## Memo Index",
        "",
        "| memo_id | scenario | workload | memo_type | audience | decision | evidence_project | industry_mapping | confidence |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for item in memos:
        request = item.request
        lines.append(
            "| "
            + " | ".join(
                escape_cell(value)
                for value in (
                    request.memo_id,
                    request.scenario,
                    request.workload,
                    request.memo_type,
                    request.audience,
                    item.decision,
                    request.evidence_project,
                    request.industry_mapping,
                    item.confidence,
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Memo Type Rules",
            "",
            "| memo_type | default evidence project | default mapping | deterministic rule intent |",
            "| --- | --- | --- | --- |",
        ]
    )
    for rule in memo_rules().values():
        lines.append(
            "| "
            + " | ".join(
                escape_cell(value)
                for value in (
                    rule.memo_type,
                    rule.evidence_project,
                    rule.industry_mapping,
                    f"Decision defaults to {rule.decision}; measure {rule.measure_next}.",
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Complete Memos",
            "",
        ]
    )
    for item in memos:
        lines.extend(render_memo(item))

    lines.extend(
        [
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
                "- Project AB is implemented as a lightweight deterministic "
                f"architecture decision memo generator with `schema_version={SCHEMA_VERSION}`."
            ),
            "",
            "Supported:",
            "",
            (
                "- It supports bounded rule-based architecture reasoning, "
                "architecture review memo writing, evidence-chain explanation, "
                "portfolio discussion, and interview storytelling."
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
                "- Future versions may add more deterministic memo templates or "
                "request fields only when the upstream evidence chain supports them."
            ),
            "",
            "claim_boundary=PASS",
            "",
        ]
    )
    return "\n".join(lines)


def validate_generated(document: str, memos: Sequence[DecisionMemo]) -> List[str]:
    required_fragments = [
        f"schema_version={SCHEMA_VERSION}",
        "## Memo Index",
        "Executive Summary",
        "Decision",
        "Evidence Chain",
        "Risk if Ignored",
        "What to Measure Next",
        "## Unsupported Claims",
        "## Claim Boundary",
        "claim_boundary=PASS",
    ]
    errors = [
        f"generated markdown missing required fragment: {fragment}"
        for fragment in required_fragments
        if fragment not in document
    ]
    for item in memos:
        if item.request.memo_id not in document:
            errors.append(f"generated markdown missing memo_id={item.request.memo_id}")
        if item.request.expected_primary_decision != item.decision:
            errors.append(
                f"{item.request.memo_id}: expected_primary_decision="
                f"{item.request.expected_primary_decision}, got {item.decision}"
            )
        if item.request.expected_memo_type != item.request.memo_type:
            errors.append(
                f"{item.request.memo_id}: expected_memo_type="
                f"{item.request.expected_memo_type}, got {item.request.memo_type}"
            )
    return errors


def print_errors(errors: Sequence[str]) -> None:
    for error in errors:
        print(f"[memo-r1] ERROR {error}", file=sys.stderr)


def main() -> int:
    args = parse_args()
    root = repo_root()
    request_path = resolve_path(root, args.requests)
    scenario_path = resolve_path(root, args.scenario_report)
    recommendation_path = resolve_path(root, args.recommendation_report)
    classification_path = resolve_path(root, args.classification_report)
    output_path = resolve_path(root, args.output)

    errors = validate_existing_inputs(
        request_path, scenario_path, recommendation_path, classification_path
    )
    if args.strict:
        errors.extend(validate_output_path(output_path))
    if errors:
        print_errors(errors)
        print("Architecture Decision Memo Generator FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    headers, request_rows = read_csv_rows(request_path)
    errors = validate_request_schema(request_path, headers, request_rows, args.strict)
    if errors:
        print_errors(errors)
        print("Architecture Decision Memo Generator FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    scenario_text = scenario_path.read_text(encoding="utf-8")
    recommendation_text = recommendation_path.read_text(encoding="utf-8")
    classification_text = classification_path.read_text(encoding="utf-8")

    if args.strict:
        errors.extend(
            validate_report_text(
                scenario_path,
                scenario_text,
                SCENARIO_SCHEMA_VERSION,
                "scenario report",
            )
        )
        errors.extend(
            validate_report_text(
                recommendation_path,
                recommendation_text,
                RECOMMENDATION_SCHEMA_VERSION,
                "recommendation report",
            )
        )
        errors.extend(
            validate_report_text(
                classification_path,
                classification_text,
                CLASSIFIER_SCHEMA_VERSION,
                "classification report",
            )
        )
    if errors:
        print_errors(errors)
        print("Architecture Decision Memo Generator FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    scenario_evidence, scenario_errors = parse_scenario_report(scenario_text)
    recommendation_evidence, recommendation_errors = parse_recommendation_report(
        recommendation_text
    )
    classification_evidence, classification_errors = parse_classification_report(
        classification_text
    )
    errors.extend(scenario_errors)
    errors.extend(recommendation_errors)
    errors.extend(classification_errors)
    if errors:
        print_errors(errors)
        print("Architecture Decision Memo Generator FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    memos, memo_errors = generate_memos(
        request_rows,
        scenario_evidence,
        recommendation_evidence,
        classification_evidence,
        args.strict,
    )
    if memo_errors:
        print_errors(memo_errors)
        print("Architecture Decision Memo Generator FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    document = render_markdown(
        root,
        request_path,
        scenario_path,
        recommendation_path,
        classification_path,
        memos,
    )
    if args.strict:
        generated_errors = validate_generated(document, memos)
        if generated_errors:
            print_errors(generated_errors)
            print("Architecture Decision Memo Generator FAIL")
            print(f"schema_version={SCHEMA_VERSION}")
            return 1

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(document, encoding="utf-8")
    except OSError as exc:
        print_errors([f"cannot write output markdown {output_path}: {exc}"])
        print("Architecture Decision Memo Generator FAIL")
        print(f"schema_version={SCHEMA_VERSION}")
        return 1

    print("Architecture Decision Memo Generator PASS")
    print(f"memos={len(memos)}")
    print(
        "memo_types="
        "fabric_memo,"
        "bandwidth_wall_memo,"
        "noc_qos_boundary_memo,"
        "mixed_evidence_memo"
    )
    print("claim_boundary=PASS")
    print(f"schema_version={SCHEMA_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
