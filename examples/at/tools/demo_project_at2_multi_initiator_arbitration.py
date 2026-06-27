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
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


SCHEMA_VERSION = "at2.0"
INITIATORS = ("cpu0", "dma0", "accel0")
PROJECT_DIR = Path("examples/at/results/project_at2_multi_initiator_arbitration")
TARGET_NAME = "project_at2_multi_initiator_arbitration"

TRACE_FIELDS = [
    "case_name",
    "policy",
    "txn_id",
    "initiator_id",
    "initiator_name",
    "addr",
    "size_bytes",
    "cmd",
    "begin_req_ns",
    "arbiter_accept_ns",
    "target_begin_req_ns",
    "target_end_req_ns",
    "begin_resp_ns",
    "end_resp_ns",
    "arbitration_delay_ns",
    "request_accept_latency_ns",
    "target_service_latency_ns",
    "response_latency_ns",
    "initiator_blocked_ns",
    "initiator_queue_depth_on_accept",
    "total_pending_on_accept",
    "backpressure",
    "winner_order",
    "status",
]

SUMMARY_FIELDS = [
    "case_name",
    "policy",
    "initiator_name",
    "num_transactions",
    "avg_arbitration_delay_ns",
    "p50_arbitration_delay_ns",
    "p95_arbitration_delay_ns",
    "p99_arbitration_delay_ns",
    "avg_request_accept_latency_ns",
    "p95_request_accept_latency_ns",
    "p99_request_accept_latency_ns",
    "avg_response_latency_ns",
    "p95_response_latency_ns",
    "p99_response_latency_ns",
    "avg_initiator_blocked_ns",
    "backpressure_events",
    "throughput_txn_per_us",
    "fairness_share",
    "expected_share",
    "fairness_error",
    "claim_boundary",
]

POLICY_SUMMARY_FIELDS = [
    "case_name",
    "policy",
    "total_transactions",
    "total_backpressure_events",
    "aggregate_throughput_txn_per_us",
    "max_p99_response_latency_ns",
    "fairness_index",
    "worst_initiator",
    "claim_boundary",
]


class DemoError(Exception):
    pass


@dataclass(frozen=True)
class CaseConfig:
    case_name: str
    policy: str
    num_transactions_per_initiator: int
    queue_depth: int
    service_latency_ns: Decimal
    issue_gap_cpu_ns: Decimal
    issue_gap_dma_ns: Decimal
    issue_gap_accel_ns: Decimal


CASES = [
    CaseConfig(
        case_name="rr_balanced",
        policy="round_robin",
        num_transactions_per_initiator=20,
        queue_depth=3,
        service_latency_ns=Decimal("9"),
        issue_gap_cpu_ns=Decimal("5"),
        issue_gap_dma_ns=Decimal("5"),
        issue_gap_accel_ns=Decimal("5"),
    ),
    CaseConfig(
        case_name="fixed_priority_dma_pressure",
        policy="fixed_priority",
        num_transactions_per_initiator=24,
        queue_depth=2,
        service_latency_ns=Decimal("12"),
        issue_gap_cpu_ns=Decimal("2"),
        issue_gap_dma_ns=Decimal("0"),
        issue_gap_accel_ns=Decimal("2"),
    ),
    CaseConfig(
        case_name="weighted_priority_accel_favored",
        policy="weighted_priority",
        num_transactions_per_initiator=24,
        queue_depth=2,
        service_latency_ns=Decimal("10"),
        issue_gap_cpu_ns=Decimal("1"),
        issue_gap_dma_ns=Decimal("1"),
        issue_gap_accel_ns=Decimal("1"),
    ),
    CaseConfig(
        case_name="bursty_mixed_contention",
        policy="weighted_priority",
        num_transactions_per_initiator=20,
        queue_depth=1,
        service_latency_ns=Decimal("14"),
        issue_gap_cpu_ns=Decimal("0"),
        issue_gap_dma_ns=Decimal("4"),
        issue_gap_accel_ns=Decimal("18"),
    ),
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_repo_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return repo_root() / candidate


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Project AT-2 multi-initiator AT arbitration and contention lab."
    )
    parser.add_argument(
        "--binary",
        help=(
            "Project AT-2 binary. Relative paths are resolved from repo root. "
            "Default: <build-dir>/multi_initiator_arbitration/"
            "project_at2_multi_initiator_arbitration."
        ),
    )
    parser.add_argument(
        "--build-dir",
        default="build-at2",
        help="CMake build directory used when building the AT-2 target.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_DIR),
        help="Project AT-2 output directory.",
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


def run_process(
    command: Sequence[object], cwd: Path, env: Optional[Dict[str, str]] = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(part) for part in command],
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def local_systemc_args() -> List[str]:
    root = repo_root()
    env_lib = os.environ.get("USER_SYSTEMC_LIB_DIR")
    env_include = os.environ.get("USER_SYSTEMC_INCLUDE_DIR")
    if env_lib and env_include:
        return [
            f"-DUSER_SYSTEMC_LIB_DIR={env_lib}",
            f"-DUSER_SYSTEMC_INCLUDE_DIR={env_include}",
        ]

    home_local = Path.home() / "local" / "systemc"
    home_lib = home_local / "lib"
    home_include = home_local / "include"
    if home_include.exists():
        for library_name in ("libsystemc.so", "libsystemc.dylib", "libsystemc.a"):
            if (home_lib / library_name).exists():
                return [
                    f"-DUSER_SYSTEMC_LIB_DIR={home_lib}",
                    f"-DUSER_SYSTEMC_INCLUDE_DIR={home_include}",
                ]

    bundled_lib = root / "build" / "systemc" / "src"
    bundled_include = root / "systemc" / "src"
    if bundled_lib.exists() and any(bundled_lib.glob("libsystemc*")) and bundled_include.exists():
        return [
            f"-DUSER_SYSTEMC_LIB_DIR={bundled_lib}",
            f"-DUSER_SYSTEMC_INCLUDE_DIR={bundled_include}",
        ]

    return []


def binary_for_build_dir(build_dir: Path) -> Path:
    return build_dir / "multi_initiator_arbitration" / TARGET_NAME


def cache_home_directory(cache: Path) -> Optional[Path]:
    if not cache.exists():
        return None
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("CMAKE_HOME_DIRECTORY:INTERNAL="):
            return Path(line.split("=", 1)[1])
    return None


def fallback_build_dir() -> Path:
    return Path(tempfile.gettempdir()) / "systemc_tlm_at2_demo_build"


def usable_build_dir(build_dir: Path) -> Path:
    cache = build_dir / "CMakeCache.txt"
    expected_source = repo_root() / "examples" / "at"
    cached_source = cache_home_directory(cache)

    if cached_source is not None and cached_source.resolve() != expected_source.resolve():
        fallback = fallback_build_dir()
        print(
            "[at2] existing build cache points to another source tree; "
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
            *local_systemc_args(),
        ]
        result = run_process(configure, cwd=root)
        if result.returncode != 0:
            raise DemoError(
                "CMake configure failed for Project AT-2:\n"
                + result.stdout
                + result.stderr
            )

    result = run_process(
        [
            "cmake",
            "--build",
            str(build_dir),
            "--target",
            TARGET_NAME,
        ],
        cwd=root,
    )
    if result.returncode != 0:
        raise DemoError(
            "CMake build failed for Project AT-2:\n" + result.stdout + result.stderr
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
        raise DemoError(f"AT-2 binary not found: {binary}")
    if not os.access(binary, os.X_OK):
        raise DemoError(f"AT-2 binary is not executable: {binary}")


def run_case(binary: Path, output_dir: Path, config: CaseConfig) -> Path:
    case_dir = output_dir / "model_runs" / config.case_name
    reset_case_dir(case_dir)

    command = [
        str(binary),
        "--case-name",
        config.case_name,
        "--policy",
        config.policy,
        "--num-transactions-per-initiator",
        str(config.num_transactions_per_initiator),
        "--queue-depth",
        str(config.queue_depth),
        "--service-latency-ns",
        str(config.service_latency_ns),
        "--issue-gap-cpu-ns",
        str(config.issue_gap_cpu_ns),
        "--issue-gap-dma-ns",
        str(config.issue_gap_dma_ns),
        "--issue-gap-accel-ns",
        str(config.issue_gap_accel_ns),
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
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != TRACE_FIELDS:
            raise DemoError(
                f"{path}: unexpected trace header {reader.fieldnames}; "
                f"expected {TRACE_FIELDS}"
            )
        return list(reader)


def percentile(values: Iterable[Decimal], pct: Decimal) -> Decimal:
    values = sorted(values)
    if not values:
        return Decimal("0")
    rank = int(math.ceil(float(pct * Decimal(len(values))))) - 1
    rank = max(0, min(rank, len(values) - 1))
    return values[rank]


def average(values: Iterable[Decimal]) -> Decimal:
    values = list(values)
    if not values:
        return Decimal("0")
    return sum(values, Decimal("0")) / Decimal(len(values))


def fmt(value: Decimal) -> str:
    return f"{value:.3f}"


def expected_share(policy: str, initiator_name: str) -> Decimal:
    if policy == "weighted_priority":
        return Decimal("0.600") if initiator_name == "accel0" else Decimal("0.200")
    return Decimal("0.333")


def validate_trace(config: CaseConfig, rows: List[Dict[str, str]]) -> None:
    expected_rows = len(INITIATORS) * config.num_transactions_per_initiator
    if len(rows) != expected_rows:
        raise DemoError(
            f"{config.case_name}: trace row count {len(rows)} != {expected_rows}"
        )

    counts = {name: 0 for name in INITIATORS}
    for row in rows:
        if row["case_name"] != config.case_name:
            raise DemoError(f"{config.case_name}: wrong case_name in trace row")
        if row["policy"] != config.policy:
            raise DemoError(f"{config.case_name}: wrong policy in trace row")
        if row["initiator_name"] not in counts:
            raise DemoError(f"{config.case_name}: unexpected initiator name")
        if row["status"] != "OK":
            raise DemoError(f"{config.case_name}: non-OK transaction status")

        counts[row["initiator_name"]] += 1

        begin_req = parse_decimal(row["begin_req_ns"], "begin_req_ns")
        arbiter_accept = parse_decimal(row["arbiter_accept_ns"], "arbiter_accept_ns")
        target_begin_req = parse_decimal(
            row["target_begin_req_ns"], "target_begin_req_ns"
        )
        target_end_req = parse_decimal(row["target_end_req_ns"], "target_end_req_ns")
        begin_resp = parse_decimal(row["begin_resp_ns"], "begin_resp_ns")
        end_resp = parse_decimal(row["end_resp_ns"], "end_resp_ns")
        if not (
            begin_req
            <= arbiter_accept
            <= target_begin_req
            <= target_end_req
            <= begin_resp
            <= end_resp
        ):
            raise DemoError(
                f"{config.case_name}: timestamp ordering failed for txn {row['txn_id']}"
            )

    for name, count in counts.items():
        if count < 16:
            raise DemoError(
                f"{config.case_name}: initiator {name} has only {count} transactions"
            )


def group_by_initiator(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    grouped = {name: [] for name in INITIATORS}
    for row in rows:
        grouped[row["initiator_name"]].append(row)
    return grouped


def initiator_throughputs(
    grouped: Dict[str, List[Dict[str, str]]]
) -> Dict[str, Decimal]:
    throughputs: Dict[str, Decimal] = {}
    for name, rows in grouped.items():
        begin_times = [parse_decimal(row["begin_req_ns"], "begin_req_ns") for row in rows]
        end_times = [parse_decimal(row["end_resp_ns"], "end_resp_ns") for row in rows]
        duration_ns = max(end_times) - min(begin_times) if rows else Decimal("0")
        throughputs[name] = (
            Decimal(len(rows)) * Decimal("1000") / duration_ns
            if duration_ns > 0
            else Decimal("0")
        )
    return throughputs


def summarize_case(config: CaseConfig, rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    grouped = group_by_initiator(rows)
    throughputs = initiator_throughputs(grouped)
    throughput_sum = sum(throughputs.values(), Decimal("0"))
    summary_rows: List[Dict[str, str]] = []

    for initiator_name in INITIATORS:
        initiator_rows = grouped[initiator_name]
        arbitration = [
            parse_decimal(row["arbitration_delay_ns"], "arbitration_delay_ns")
            for row in initiator_rows
        ]
        request_accept = [
            parse_decimal(
                row["request_accept_latency_ns"], "request_accept_latency_ns"
            )
            for row in initiator_rows
        ]
        response = [
            parse_decimal(row["response_latency_ns"], "response_latency_ns")
            for row in initiator_rows
        ]
        blocked = [
            parse_decimal(row["initiator_blocked_ns"], "initiator_blocked_ns")
            for row in initiator_rows
        ]
        share = (
            throughputs[initiator_name] / throughput_sum
            if throughput_sum > 0
            else Decimal("0")
        )
        expected = expected_share(config.policy, initiator_name)
        summary_rows.append(
            {
                "case_name": config.case_name,
                "policy": config.policy,
                "initiator_name": initiator_name,
                "num_transactions": str(len(initiator_rows)),
                "avg_arbitration_delay_ns": fmt(average(arbitration)),
                "p50_arbitration_delay_ns": fmt(percentile(arbitration, Decimal("0.50"))),
                "p95_arbitration_delay_ns": fmt(percentile(arbitration, Decimal("0.95"))),
                "p99_arbitration_delay_ns": fmt(percentile(arbitration, Decimal("0.99"))),
                "avg_request_accept_latency_ns": fmt(average(request_accept)),
                "p95_request_accept_latency_ns": fmt(
                    percentile(request_accept, Decimal("0.95"))
                ),
                "p99_request_accept_latency_ns": fmt(
                    percentile(request_accept, Decimal("0.99"))
                ),
                "avg_response_latency_ns": fmt(average(response)),
                "p95_response_latency_ns": fmt(percentile(response, Decimal("0.95"))),
                "p99_response_latency_ns": fmt(percentile(response, Decimal("0.99"))),
                "avg_initiator_blocked_ns": fmt(average(blocked)),
                "backpressure_events": str(
                    sum(1 for row in initiator_rows if row["backpressure"] == "YES")
                ),
                "throughput_txn_per_us": fmt(throughputs[initiator_name]),
                "fairness_share": fmt(share),
                "expected_share": fmt(expected),
                "fairness_error": fmt(abs(share - expected)),
                "claim_boundary": "PASS",
            }
        )

    return summary_rows


def summarize_policy(
    config: CaseConfig,
    rows: List[Dict[str, str]],
    initiator_rows: List[Dict[str, str]],
) -> Dict[str, str]:
    begin_times = [parse_decimal(row["begin_req_ns"], "begin_req_ns") for row in rows]
    end_times = [parse_decimal(row["end_resp_ns"], "end_resp_ns") for row in rows]
    duration_ns = max(end_times) - min(begin_times)
    aggregate_throughput = (
        Decimal(len(rows)) * Decimal("1000") / duration_ns
        if duration_ns > 0
        else Decimal("0")
    )
    p99_by_initiator = {
        row["initiator_name"]: parse_decimal(
            row["p99_response_latency_ns"], "p99_response_latency_ns"
        )
        for row in initiator_rows
    }
    worst_initiator = max(p99_by_initiator, key=p99_by_initiator.get)
    throughputs = [
        parse_decimal(row["throughput_txn_per_us"], "throughput_txn_per_us")
        for row in initiator_rows
    ]
    throughput_sum = sum(throughputs, Decimal("0"))
    throughput_square_sum = sum(value * value for value in throughputs)
    fairness_index = (
        (throughput_sum * throughput_sum)
        / (Decimal(len(throughputs)) * throughput_square_sum)
        if throughput_square_sum > 0
        else Decimal("0")
    )

    return {
        "case_name": config.case_name,
        "policy": config.policy,
        "total_transactions": str(len(rows)),
        "total_backpressure_events": str(
            sum(1 for row in rows if row["backpressure"] == "YES")
        ),
        "aggregate_throughput_txn_per_us": fmt(aggregate_throughput),
        "max_p99_response_latency_ns": fmt(max(p99_by_initiator.values())),
        "fairness_index": fmt(fairness_index),
        "worst_initiator": worst_initiator,
        "claim_boundary": "PASS",
    }


def write_csv(path: Path, fields: Sequence[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def case_table_row(row: Dict[str, str]) -> str:
    return (
        f"| {row['case_name']} | {row['policy']} | "
        f"{row['aggregate_throughput_txn_per_us']} | "
        f"{row['max_p99_response_latency_ns']} | "
        f"{row['total_backpressure_events']} | "
        f"{row['fairness_index']} | {row['worst_initiator']} |"
    )


def initiator_table_row(row: Dict[str, str]) -> str:
    return (
        f"| {row['case_name']} | {row['initiator_name']} | "
        f"{row['p95_response_latency_ns']} | {row['p99_response_latency_ns']} | "
        f"{row['avg_initiator_blocked_ns']} | {row['fairness_share']} | "
        f"{row['fairness_error']} |"
    )


def write_report(
    path: Path,
    summary_rows: List[Dict[str, str]],
    policy_rows: List[Dict[str, str]],
) -> None:
    lines = [
        "# Project AT-2 Multi-Initiator AT Arbitration and Contention Lab",
        "",
        "schema_version: `at2.0`",
        "",
        "## Architecture Story",
        "",
        "AT-2 extends AT-1 from a single-initiator four-phase memory timing model to a multi-initiator contention model. AT-1 shows transaction phase timing; AT-2 keeps the same approximately-timed non-blocking transport idea and adds shared-path arbitration, queueing pressure, initiator-level fairness, tail latency, and back-pressure observability.",
        "",
        "The model uses three synthetic initiators (`cpu0`, `dma0`, and `accel0`) sharing a small AT interconnect and a finite-depth memory target. It is intended for bounded SoC architecture exploration before RTL, not protocol-complete interconnect implementation.",
        "",
        "## Arbitration Policy Explanation",
        "",
        "- `round_robin`: rotates service opportunities across initiators when they have pending requests; it is useful as a fairness baseline.",
        "- `fixed_priority`: prioritizes `dma0`, then `cpu0`, then `accel0`; it shows how protecting one traffic class can raise lower-priority tail latency.",
        "- `weighted_priority`: gives `accel0` more service opportunities in a repeated weighted order; it is a QoS-like tradeoff model, but it is not AXI QoS or CHI QoS compliance.",
        "",
        "## Case Comparison",
        "",
        "| case_name | policy | aggregate throughput | max p99 latency | total backpressure events | fairness_index | worst_initiator |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    lines.extend(case_table_row(row) for row in policy_rows)
    lines.extend(
        [
            "",
            "## Initiator-Level Analysis",
            "",
            "| case_name | initiator | p95 latency | p99 latency | avg blocked time | fairness share | fairness error |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(initiator_table_row(row) for row in summary_rows)
    lines.extend(
        [
            "",
            "## Architecture Interpretation",
            "",
            "- `round_robin` is generally more fair, but it is not guaranteed to minimize tail latency for every initiator.",
            "- `fixed_priority` can protect high-priority traffic, but lower-priority initiators can pay with higher p95 / p99 latency.",
            "- `weighted_priority` is a QoS-like tradeoff: it can favor one initiator while still allowing others to make progress, but it is not AXI QoS / CHI QoS compliance.",
            "- Bursty traffic amplifies queueing and back-pressure because requests arrive faster than the finite target queue can accept and service them.",
            "",
            "## Claim Boundary / Unsupported Claims",
            "",
            "- This is a SystemC/TLM AT teaching and architecture modeling lab.",
            "- This is not AXI / CHI protocol compliance.",
            "- This is not a cycle-accurate interconnect model.",
            "- This is not a real NoC model.",
            "- This is not silicon validation.",
            "- This is not production signoff.",
            "- This is not a real DRAM timing model.",
            "- This does not model cache coherence.",
            "",
            "## Portfolio / Interview Narrative",
            "",
            "- AT-1 shows transaction phase timing.",
            "- AT-2 shows contention, arbitration, and fairness tradeoffs.",
            "- This is closer to early SoC architecture exploration.",
            "- It demonstrates how architecture modeling can expose tail latency and QoS tradeoffs before RTL.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def line_has_positive_claim(line: str, phrase: str) -> bool:
    lowered = line.lower()
    if phrase not in lowered:
        return False
    boundary_words = [
        "not ",
        "no ",
        "unsupported",
        "does not",
        "is not",
        "不是",
        "不声称",
    ]
    return not any(word in lowered for word in boundary_words)


def forbidden_claim_scan(report_path: Path) -> None:
    phrases = [
        "axi compliant",
        "chi compliant",
        "protocol compliant",
        "protocol compliance",
        "cycle-accurate interconnect model",
        "cycle accurate interconnect model",
        "real noc model",
        "silicon validation",
        "production signoff",
        "real dram timing model",
        "cache coherence",
    ]
    for line_number, line in enumerate(
        report_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        for phrase in phrases:
            if line_has_positive_claim(line, phrase):
                raise DemoError(
                    f"forbidden positive claim in report line {line_number}: {line}"
                )


def case_average_fairness_error(
    summary_rows: List[Dict[str, str]], case_name: str
) -> Decimal:
    errors = [
        parse_decimal(row["fairness_error"], "fairness_error")
        for row in summary_rows
        if row["case_name"] == case_name
    ]
    return average(errors)


def acceptance_checks(
    summary_rows: List[Dict[str, str]],
    policy_rows: List[Dict[str, str]],
    traces_by_case: Dict[str, List[Dict[str, str]]],
    report_path: Path,
) -> None:
    if len(traces_by_case) != 4:
        raise DemoError(f"case count {len(traces_by_case)} != 4")
    if len(policy_rows) != 4:
        raise DemoError(f"policy summary row count {len(policy_rows)} != 4")
    if len(summary_rows) < 12:
        raise DemoError("summary does not contain case x initiator rows")
    if not all(row["claim_boundary"] == "PASS" for row in summary_rows + policy_rows):
        raise DemoError("not all claim_boundary fields are PASS")

    fixed_rows = [
        row
        for row in summary_rows
        if row["case_name"] == "fixed_priority_dma_pressure"
    ]
    fixed_by_name = {row["initiator_name"]: row for row in fixed_rows}
    high_priority_p99 = parse_decimal(
        fixed_by_name["dma0"]["p99_response_latency_ns"], "p99_response_latency_ns"
    )
    low_priority_tail_is_higher = any(
        parse_decimal(row["p95_response_latency_ns"], "p95_response_latency_ns")
        > high_priority_p99
        or parse_decimal(row["p99_response_latency_ns"], "p99_response_latency_ns")
        > high_priority_p99
        for name, row in fixed_by_name.items()
        if name != "dma0"
    )
    if not low_priority_tail_is_higher:
        raise DemoError(
            "fixed_priority_dma_pressure did not raise a low-priority tail latency"
        )

    rr_fairness_error = case_average_fairness_error(summary_rows, "rr_balanced")
    fixed_fairness_error = case_average_fairness_error(
        summary_rows, "fixed_priority_dma_pressure"
    )
    if rr_fairness_error >= fixed_fairness_error:
        raise DemoError(
            "rr_balanced fairness_error is not lower than fixed_priority_dma_pressure"
        )

    bursty_backpressure = sum(
        int(row["total_backpressure_events"])
        for row in policy_rows
        if row["case_name"] == "bursty_mixed_contention"
    )
    if bursty_backpressure <= 0:
        raise DemoError("bursty_mixed_contention did not show backpressure")

    if not report_path.exists():
        raise DemoError(f"missing report: {report_path}")
    report = report_path.read_text(encoding="utf-8")
    required_markers = [
        "## Architecture Story",
        "## Arbitration Policy Explanation",
        "## Case Comparison",
        "## Initiator-Level Analysis",
        "## Architecture Interpretation",
        "## Claim Boundary / Unsupported Claims",
        "## Portfolio / Interview Narrative",
        "This is a SystemC/TLM AT teaching and architecture modeling lab.",
        "This is not AXI / CHI protocol compliance.",
        "This is not a cycle-accurate interconnect model.",
        "This is not a real NoC model.",
        "This is not silicon validation.",
        "This is not production signoff.",
        "This is not a real DRAM timing model.",
        "This does not model cache coherence.",
    ]
    missing = [marker for marker in required_markers if marker not in report]
    if missing:
        raise DemoError("report is missing markers: " + ", ".join(missing))
    forbidden_claim_scan(report_path)


def print_outputs(output_dir: Path) -> None:
    print("[at2] Output files:")
    print(f"[at2]   summary: {output_dir / 'project_at2_summary.csv'}")
    print(f"[at2]   policy summary: {output_dir / 'project_at2_policy_summary.csv'}")
    print(f"[at2]   report: {output_dir / 'project_at2_report.md'}")
    for config in CASES:
        print(
            "[at2]   trace: "
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
    policy_rows: List[Dict[str, str]] = []
    traces_by_case: Dict[str, List[Dict[str, str]]] = {}
    failures: List[str] = []

    for config in CASES:
        print(f"[at2] running case={config.case_name}")
        try:
            trace_path = run_case(binary, output_dir, config)
            rows = read_trace(trace_path)
            validate_trace(config, rows)
            case_summary = summarize_case(config, rows)
            summary_rows.extend(case_summary)
            policy_rows.append(summarize_policy(config, rows, case_summary))
            traces_by_case[config.case_name] = rows
            print(f"[at2] case={config.case_name} status=OK")
        except DemoError as exc:
            failures.append(str(exc))
            print(f"[at2] case={config.case_name} status=FAIL error={exc}")
            if not args.keep_going:
                raise

    summary_path = output_dir / "project_at2_summary.csv"
    policy_summary_path = output_dir / "project_at2_policy_summary.csv"
    report_path = output_dir / "project_at2_report.md"
    write_csv(summary_path, SUMMARY_FIELDS, summary_rows)
    write_csv(policy_summary_path, POLICY_SUMMARY_FIELDS, policy_rows)
    write_report(report_path, summary_rows, policy_rows)

    if failures:
        raise DemoError("; ".join(failures))

    acceptance_checks(summary_rows, policy_rows, traces_by_case, report_path)
    print_outputs(output_dir)
    print("Project AT-2 Multi-Initiator AT Arbitration and Contention Lab PASS")
    print("cases=4")
    print(f"initiators={len(INITIATORS)}")
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
