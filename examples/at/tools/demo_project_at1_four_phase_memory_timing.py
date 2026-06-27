#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import math
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, List, Optional


SCHEMA_VERSION = "at1.0"
PROJECT_DIR = Path("examples/at/results/project_at1_four_phase_memory_timing")
TRACE_FIELDS = [
    "case_name",
    "txn_id",
    "pattern",
    "addr",
    "size_bytes",
    "cmd",
    "begin_req_ns",
    "end_req_ns",
    "begin_resp_ns",
    "end_resp_ns",
    "request_accept_latency_ns",
    "target_service_latency_ns",
    "response_latency_ns",
    "initiator_blocked_ns",
    "queue_depth_on_accept",
    "backpressure",
    "status",
]
SUMMARY_FIELDS = [
    "case_name",
    "pattern",
    "num_transactions",
    "queue_depth",
    "service_latency_ns",
    "issue_gap_ns",
    "avg_request_accept_latency_ns",
    "p50_request_accept_latency_ns",
    "p95_request_accept_latency_ns",
    "avg_target_service_latency_ns",
    "avg_response_latency_ns",
    "avg_initiator_blocked_ns",
    "max_queue_depth_observed",
    "backpressure_events",
    "throughput_txn_per_us",
    "claim_boundary",
]


class DemoError(Exception):
    pass


@dataclass(frozen=True)
class CaseConfig:
    case_name: str
    pattern: str
    num_transactions: int
    queue_depth: int
    service_latency_ns: Decimal
    issue_gap_ns: Decimal


CASES = [
    CaseConfig(
        case_name="sequential_moderate_gap",
        pattern="sequential",
        num_transactions=8,
        queue_depth=4,
        service_latency_ns=Decimal("8"),
        issue_gap_ns=Decimal("12"),
    ),
    CaseConfig(
        case_name="bursty_queue_pressure",
        pattern="bursty",
        num_transactions=12,
        queue_depth=2,
        service_latency_ns=Decimal("12"),
        issue_gap_ns=Decimal("0"),
    ),
    CaseConfig(
        case_name="hotspot_backpressure",
        pattern="hotspot",
        num_transactions=12,
        queue_depth=1,
        service_latency_ns=Decimal("16"),
        issue_gap_ns=Decimal("0"),
    ),
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_repo_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return repo_root() / candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Project AT-1 four-phase AT memory transaction timing lab."
    )
    parser.add_argument(
        "--binary",
        help=(
            "Project AT-1 binary. Relative paths are resolved from repo root. "
            "Default: <build-dir>/four_phase_memory_timing/"
            "project_at1_four_phase_memory_timing."
        ),
    )
    parser.add_argument(
        "--build-dir",
        default="build/examples/at",
        help="CMake build directory used when building the AT-1 target.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_DIR),
        help="Project AT-1 output directory.",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Do not run CMake before executing cases.",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue writing summary/report artifacts after a failed case.",
    )
    return parser.parse_args()


def run_process(command: List[str], cwd: Path, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def detect_systemc_config_args() -> List[str]:
    root = repo_root()
    lib_dir = root / "build" / "systemc" / "src"
    include_dir = root / "systemc" / "src"

    has_library = lib_dir.exists() and any(lib_dir.glob("libsystemc*"))
    if has_library and include_dir.exists():
        return [
            f"-DUSER_SYSTEMC_LIB_DIR={lib_dir}",
            f"-DUSER_SYSTEMC_INCLUDE_DIR={include_dir}",
        ]

    return []


def binary_for_build_dir(build_dir: Path) -> Path:
    return build_dir / "four_phase_memory_timing" / "project_at1_four_phase_memory_timing"


def cache_home_directory(cache: Path) -> Optional[Path]:
    if not cache.exists():
        return None
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("CMAKE_HOME_DIRECTORY:INTERNAL="):
            return Path(line.split("=", 1)[1])
    return None


def fallback_build_dir() -> Path:
    return Path(tempfile.gettempdir()) / "systemc_tlm_at1_demo_build"


def usable_build_dir(build_dir: Path) -> Path:
    root = repo_root()
    cache = build_dir / "CMakeCache.txt"
    expected_source = root / "examples" / "at"
    cached_source = cache_home_directory(cache)

    if cached_source is not None and cached_source.resolve() != expected_source.resolve():
        fallback = fallback_build_dir()
        print(
            "[at1] existing build cache points to another source tree; "
            f"using fallback build dir: {fallback}"
        )
        return fallback

    return build_dir


def build_binary(build_dir: Path) -> Path:
    root = repo_root()
    build_dir = usable_build_dir(build_dir)
    cache = build_dir / "CMakeCache.txt"

    if not cache.exists():
        configure = [
            "cmake",
            "-S",
            "examples/at",
            "-B",
            str(build_dir),
            *detect_systemc_config_args(),
        ]
        result = run_process(configure, cwd=root)
        if result.returncode != 0:
            raise DemoError(
                "CMake configure failed for Project AT-1:\n"
                + result.stdout
                + result.stderr
            )

    result = run_process(
        [
            "cmake",
            "--build",
            str(build_dir),
            "--target",
            "project_at1_four_phase_memory_timing",
        ],
        cwd=root,
    )
    if result.returncode != 0:
        raise DemoError(
            "CMake build failed for Project AT-1:\n" + result.stdout + result.stderr
        )

    return binary_for_build_dir(build_dir)


def is_protected_path(path: Path) -> bool:
    root = repo_root()
    protected = {
        root,
        root / "examples",
        root / "examples" / "at",
        root / "examples" / "at" / "results",
        root / PROJECT_DIR,
        Path("/").resolve(),
        Path("/tmp").resolve(),
    }

    try:
        resolved = path.resolve()
    except FileNotFoundError:
        resolved = path.parent.resolve() / path.name

    return resolved in protected


def reset_case_dir(case_dir: Path) -> None:
    if case_dir.exists():
        if not case_dir.is_dir():
            raise DemoError(f"case output path is not a directory: {case_dir}")
        if is_protected_path(case_dir):
            raise DemoError(f"refusing to delete protected output directory: {case_dir}")
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)


def require_binary(binary: Path) -> None:
    if not binary.exists():
        raise DemoError(f"AT-1 binary not found: {binary}")
    if not os.access(binary, os.X_OK):
        raise DemoError(f"AT-1 binary is not executable: {binary}")


def run_case(binary: Path, output_dir: Path, config: CaseConfig) -> Path:
    case_dir = output_dir / "model_runs" / config.case_name
    reset_case_dir(case_dir)

    command = [
        str(binary),
        "--case-name",
        config.case_name,
        "--pattern",
        config.pattern,
        "--num-transactions",
        str(config.num_transactions),
        "--queue-depth",
        str(config.queue_depth),
        "--service-latency-ns",
        str(config.service_latency_ns),
        "--issue-gap-ns",
        str(config.issue_gap_ns),
        "--output-dir",
        str(case_dir),
    ]
    result = run_process(command, cwd=repo_root())
    (case_dir / "model.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (case_dir / "model.stderr.txt").write_text(result.stderr, encoding="utf-8")

    if result.returncode != 0:
        raise DemoError(
            f"{config.case_name}: model failed with exit code {result.returncode}; "
            f"see {case_dir / 'model.stderr.txt'}"
        )

    trace_path = case_dir / "trace.csv"
    if not trace_path.exists():
        raise DemoError(f"{config.case_name}: missing trace.csv")
    return trace_path


def parse_decimal(value: str, field: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise DemoError(f"invalid decimal field {field}: {value}") from exc
    if not parsed.is_finite():
        raise DemoError(f"invalid decimal field {field}: {value}")
    return parsed


def read_trace(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != TRACE_FIELDS:
            raise DemoError(
                f"{path}: unexpected trace header {reader.fieldnames}; "
                f"expected {TRACE_FIELDS}"
            )
        return list(reader)


def percentile(values: List[Decimal], pct: Decimal) -> Decimal:
    if not values:
        return Decimal("0")
    sorted_values = sorted(values)
    rank = int(math.ceil(float(pct * Decimal(len(sorted_values))))) - 1
    rank = max(0, min(rank, len(sorted_values) - 1))
    return sorted_values[rank]


def average(values: Iterable[Decimal]) -> Decimal:
    values = list(values)
    if not values:
        return Decimal("0")
    return sum(values, Decimal("0")) / Decimal(len(values))


def fmt(value: Decimal) -> str:
    return f"{value:.3f}"


def validate_trace(config: CaseConfig, rows: List[Dict[str, str]]) -> None:
    if len(rows) != config.num_transactions:
        raise DemoError(
            f"{config.case_name}: trace row count {len(rows)} != "
            f"num_transactions {config.num_transactions}"
        )

    for row in rows:
        if row["case_name"] != config.case_name:
            raise DemoError(f"{config.case_name}: wrong case_name in trace row")
        if row["pattern"] != config.pattern:
            raise DemoError(f"{config.case_name}: wrong pattern in trace row")
        if row["status"] != "OK":
            raise DemoError(f"{config.case_name}: non-OK transaction status")

        begin_req = parse_decimal(row["begin_req_ns"], "begin_req_ns")
        end_req = parse_decimal(row["end_req_ns"], "end_req_ns")
        begin_resp = parse_decimal(row["begin_resp_ns"], "begin_resp_ns")
        end_resp = parse_decimal(row["end_resp_ns"], "end_resp_ns")
        if not (begin_req <= end_req <= begin_resp <= end_resp):
            raise DemoError(
                f"{config.case_name}: phase ordering failed for txn {row['txn_id']}"
            )


def summarize_case(config: CaseConfig, rows: List[Dict[str, str]]) -> Dict[str, str]:
    request_accept = [
        parse_decimal(row["request_accept_latency_ns"], "request_accept_latency_ns")
        for row in rows
    ]
    target_service = [
        parse_decimal(row["target_service_latency_ns"], "target_service_latency_ns")
        for row in rows
    ]
    response = [
        parse_decimal(row["response_latency_ns"], "response_latency_ns")
        for row in rows
    ]
    blocked = [
        parse_decimal(row["initiator_blocked_ns"], "initiator_blocked_ns")
        for row in rows
    ]
    begin_times = [parse_decimal(row["begin_req_ns"], "begin_req_ns") for row in rows]
    end_times = [parse_decimal(row["end_resp_ns"], "end_resp_ns") for row in rows]
    duration_ns = max(end_times) - min(begin_times)
    throughput = (
        Decimal(config.num_transactions) * Decimal("1000") / duration_ns
        if duration_ns > 0
        else Decimal("0")
    )
    backpressure_events = sum(1 for row in rows if row["backpressure"] == "YES")

    return {
        "case_name": config.case_name,
        "pattern": config.pattern,
        "num_transactions": str(config.num_transactions),
        "queue_depth": str(config.queue_depth),
        "service_latency_ns": fmt(config.service_latency_ns),
        "issue_gap_ns": fmt(config.issue_gap_ns),
        "avg_request_accept_latency_ns": fmt(average(request_accept)),
        "p50_request_accept_latency_ns": fmt(percentile(request_accept, Decimal("0.50"))),
        "p95_request_accept_latency_ns": fmt(percentile(request_accept, Decimal("0.95"))),
        "avg_target_service_latency_ns": fmt(average(target_service)),
        "avg_response_latency_ns": fmt(average(response)),
        "avg_initiator_blocked_ns": fmt(average(blocked)),
        "max_queue_depth_observed": str(
            max(int(row["queue_depth_on_accept"]) for row in rows)
        ),
        "backpressure_events": str(backpressure_events),
        "throughput_txn_per_us": fmt(throughput),
        "claim_boundary": "PASS",
    }


def write_summary(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def table_row(row: Dict[str, str]) -> str:
    return (
        f"| {row['case_name']} | {row['pattern']} | "
        f"{row['avg_request_accept_latency_ns']} | "
        f"{row['avg_initiator_blocked_ns']} | "
        f"{row['backpressure_events']} | "
        f"{row['throughput_txn_per_us']} |"
    )


def write_report(path: Path, rows: List[Dict[str, str]]) -> None:
    lines = [
        "# Project AT-1 Four-Phase AT Memory Transaction Timing Lab",
        "",
        "schema_version: `at1.0`",
        "",
        "## Architecture Story",
        "",
        "AT-1 moves from LT-style blocking latency observation into TLM-2.0 approximately-timed non-blocking transport. LT can compress a transaction into one blocking call; AT-1 keeps the request and response phases visible so request acceptance, target queueing, initiator stall, and response timing can be measured separately.",
        "",
        "## Four-Phase Timing Explanation",
        "",
        "- `BEGIN_REQ`: initiator starts a request on the forward path.",
        "- `END_REQ`: target accepts that request; long `BEGIN_REQ -> END_REQ` means request-side stall or back-pressure.",
        "- `BEGIN_RESP`: target has produced the response after queueing and modeled service latency.",
        "- `END_RESP`: initiator acknowledges the response on the forward path.",
        "",
        "## Case Comparison Table",
        "",
        "| case_name | pattern | avg_request_accept_latency_ns | avg_initiator_blocked_ns | backpressure_events | throughput_txn_per_us |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(table_row(row) for row in rows)
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This is a SystemC/TLM AT teaching and architecture modeling lab.",
            "- This is not AXI / CHI protocol compliance.",
            "- This is not cycle-accurate simulation.",
            "- This is not silicon validation.",
            "- This is not production signoff.",
            "- This is not a real DRAM timing model.",
            "",
            "## Unsupported Claims",
            "",
            "- No AXI channel, CHI coherence, NoC routing, DRAM timing, RTL equivalence, silicon correlation, or production release readiness is claimed.",
            "- Metrics are generated from a small synthetic AT memory timing model and are intended for phase-semantics and architecture-exploration discussion only.",
            "",
            "## Portfolio / Interview Narrative",
            "",
            "LT abstracts transaction latency into one blocking call. AT exposes transaction phase timing and back-pressure through `nb_transport_fw` / `nb_transport_bw` and the four base-protocol phases. AT-1 demonstrates understanding of TLM 2.0 non-blocking transport semantics and is useful for early SoC architecture exploration before RTL, while keeping the protocol and validation boundaries explicit.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def line_has_positive_claim(line: str, phrase: str) -> bool:
    lowered = line.lower()
    if phrase not in lowered:
        return False
    boundary_words = ["not ", "no ", "unsupported", "does not", "is not", "不是", "不声称"]
    return not any(word in lowered for word in boundary_words)


def forbidden_claim_scan(report_path: Path) -> None:
    phrases = [
        "axi compliant",
        "chi compliant",
        "protocol compliant",
        "cycle-accurate simulation",
        "cycle accurate simulation",
        "silicon validated",
        "production signoff ready",
        "real dram timing model",
    ]
    for line_number, line in enumerate(report_path.read_text(encoding="utf-8").splitlines(), start=1):
        for phrase in phrases:
            if line_has_positive_claim(line, phrase):
                raise DemoError(
                    f"forbidden positive claim in report line {line_number}: {line}"
                )


def acceptance_checks(
    summary_rows: List[Dict[str, str]], report_path: Path, trace_paths: List[Path]
) -> None:
    if len(summary_rows) != 3:
        raise DemoError(f"summary row count {len(summary_rows)} != 3")
    if len(trace_paths) != 3:
        raise DemoError(f"case count {len(trace_paths)} != 3")
    if not all(row["claim_boundary"] == "PASS" for row in summary_rows):
        raise DemoError("not all claim_boundary fields are PASS")

    pressure_rows = {
        row["case_name"]: int(row["backpressure_events"]) for row in summary_rows
    }
    if (
        pressure_rows.get("bursty_queue_pressure", 0) == 0
        and pressure_rows.get("hotspot_backpressure", 0) == 0
    ):
        raise DemoError("expected bursty or hotspot case to show backpressure")

    if not report_path.exists():
        raise DemoError(f"missing report: {report_path}")
    report = report_path.read_text(encoding="utf-8").lower()
    if "## claim boundary" not in report or "## unsupported claims" not in report:
        raise DemoError("report is missing claim boundary / unsupported claims sections")
    forbidden_claim_scan(report_path)


def print_outputs(output_dir: Path) -> None:
    print("[at1] Output files:")
    print(f"[at1]   summary: {output_dir / 'project_at1_summary.csv'}")
    print(f"[at1]   report: {output_dir / 'project_at1_report.md'}")
    for config in CASES:
        print(
            "[at1]   trace: "
            f"{output_dir / 'model_runs' / config.case_name / 'trace.csv'}"
        )


def main() -> int:
    args = parse_args()
    output_dir = resolve_repo_path(args.output_dir)
    build_dir = resolve_repo_path(args.build_dir)

    if not args.no_build:
        default_binary = build_binary(build_dir)
        binary = resolve_repo_path(args.binary) if args.binary else default_binary
    else:
        binary = (
            resolve_repo_path(args.binary)
            if args.binary
            else binary_for_build_dir(build_dir)
        )
    require_binary(binary)

    summary_rows: List[Dict[str, str]] = []
    trace_paths: List[Path] = []
    failures: List[str] = []

    for config in CASES:
        print(f"[at1] running case={config.case_name}")
        try:
            trace_path = run_case(binary, output_dir, config)
            rows = read_trace(trace_path)
            validate_trace(config, rows)
            summary_rows.append(summarize_case(config, rows))
            trace_paths.append(trace_path)
            print(f"[at1] case={config.case_name} status=OK")
        except DemoError as exc:
            failures.append(str(exc))
            print(f"[at1] case={config.case_name} status=FAIL error={exc}")
            if not args.keep_going:
                raise

    summary_path = output_dir / "project_at1_summary.csv"
    report_path = output_dir / "project_at1_report.md"
    write_summary(summary_path, summary_rows)
    write_report(report_path, summary_rows)

    if failures:
        raise DemoError("; ".join(failures))

    acceptance_checks(summary_rows, report_path, trace_paths)
    print_outputs(output_dir)
    print("Project AT-1 Four-Phase AT Memory Transaction Timing Lab PASS")
    print("cases=3")
    print("claim_boundary=PASS")
    print(f"schema_version={SCHEMA_VERSION}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        sys.exit(2)
    except DemoError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
