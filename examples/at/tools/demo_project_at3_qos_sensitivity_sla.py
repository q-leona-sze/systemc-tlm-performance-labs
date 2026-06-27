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


SCHEMA_VERSION = "at3.0"
INITIATORS = ("cpu0", "dma0", "accel0")
TRAFFIC_CLASSES = {
    "cpu0": "interactive_cpu",
    "dma0": "bulk_dma",
    "accel0": "latency_sensitive_accelerator",
}
PROJECT_DIR = Path("examples/at/results/project_at3_qos_sensitivity_sla")
TARGET_NAME = "project_at3_qos_sensitivity_sla"

TRACE_FIELDS = [
    "case_name",
    "txn_id",
    "initiator_id",
    "initiator_name",
    "traffic_class",
    "weight_cpu",
    "weight_dma",
    "weight_accel",
    "queue_depth",
    "service_latency_ns",
    "sla_target_ns",
    "addr",
    "size_bytes",
    "begin_req_ns",
    "arbiter_accept_ns",
    "target_begin_req_ns",
    "target_end_req_ns",
    "begin_resp_ns",
    "end_resp_ns",
    "arbitration_delay_ns",
    "request_accept_latency_ns",
    "response_latency_ns",
    "total_latency_ns",
    "initiator_blocked_ns",
    "total_pending_on_accept",
    "target_queue_depth_on_accept",
    "backpressure",
    "sla_violation",
    "winner_order",
    "claim_boundary",
]

SUMMARY_FIELDS = [
    "case_name",
    "initiator_name",
    "traffic_class",
    "weight",
    "queue_depth",
    "service_latency_ns",
    "sla_target_ns",
    "num_transactions",
    "avg_total_latency_ns",
    "p50_total_latency_ns",
    "p95_total_latency_ns",
    "p99_total_latency_ns",
    "avg_arbitration_delay_ns",
    "p95_arbitration_delay_ns",
    "avg_blocked_ns",
    "backpressure_events",
    "sla_violations",
    "sla_violation_rate",
    "throughput_txn_per_us",
    "fairness_share",
    "expected_share",
    "fairness_error",
    "claim_boundary",
]

POLICY_SWEEP_FIELDS = [
    "case_name",
    "weight_vector",
    "queue_depth",
    "service_latency_ns",
    "total_transactions",
    "aggregate_throughput_txn_per_us",
    "total_backpressure_events",
    "total_sla_violations",
    "max_sla_violation_rate",
    "max_p99_total_latency_ns",
    "fairness_index",
    "protected_initiator",
    "worst_initiator",
    "claim_boundary",
]

RECOMMENDATION_FIELDS = [
    "case_name",
    "primary_bottleneck",
    "recommended_action",
    "recommendation_priority",
    "evidence_summary",
    "protected_initiator",
    "worst_initiator",
    "max_sla_violation_rate",
    "max_p99_total_latency_ns",
    "fairness_index",
    "claim_boundary",
]


class DemoError(Exception):
    pass


@dataclass(frozen=True)
class CaseConfig:
    case_name: str
    weights: Tuple[int, int, int]
    queue_depth: int
    service_latency_ns: Decimal
    num_transactions_per_initiator: int
    issue_gap_cpu_ns: Decimal
    issue_gap_dma_ns: Decimal
    issue_gap_accel_ns: Decimal
    burstiness_cpu: int
    burstiness_dma: int
    burstiness_accel: int
    sla_cpu_ns: Decimal
    sla_dma_ns: Decimal
    sla_accel_ns: Decimal
    protected_initiator: str


CASES = [
    CaseConfig(
        case_name="balanced_qos_nominal",
        weights=(1, 1, 1),
        queue_depth=4,
        service_latency_ns=Decimal("14"),
        num_transactions_per_initiator=24,
        issue_gap_cpu_ns=Decimal("10"),
        issue_gap_dma_ns=Decimal("10"),
        issue_gap_accel_ns=Decimal("10"),
        burstiness_cpu=1,
        burstiness_dma=1,
        burstiness_accel=1,
        sla_cpu_ns=Decimal("420"),
        sla_dma_ns=Decimal("520"),
        sla_accel_ns=Decimal("360"),
        protected_initiator="none",
    ),
    CaseConfig(
        case_name="accel_favored_latency_protection",
        weights=(1, 1, 3),
        queue_depth=4,
        service_latency_ns=Decimal("14"),
        num_transactions_per_initiator=24,
        issue_gap_cpu_ns=Decimal("10"),
        issue_gap_dma_ns=Decimal("10"),
        issue_gap_accel_ns=Decimal("10"),
        burstiness_cpu=1,
        burstiness_dma=1,
        burstiness_accel=1,
        sla_cpu_ns=Decimal("420"),
        sla_dma_ns=Decimal("520"),
        sla_accel_ns=Decimal("320"),
        protected_initiator="accel0",
    ),
    CaseConfig(
        case_name="dma_favored_bandwidth_pressure",
        weights=(1, 3, 1),
        queue_depth=4,
        service_latency_ns=Decimal("16"),
        num_transactions_per_initiator=24,
        issue_gap_cpu_ns=Decimal("12"),
        issue_gap_dma_ns=Decimal("6"),
        issue_gap_accel_ns=Decimal("12"),
        burstiness_cpu=1,
        burstiness_dma=3,
        burstiness_accel=1,
        sla_cpu_ns=Decimal("440"),
        sla_dma_ns=Decimal("520"),
        sla_accel_ns=Decimal("380"),
        protected_initiator="dma0",
    ),
    CaseConfig(
        case_name="cpu_favored_interactive",
        weights=(3, 1, 1),
        queue_depth=4,
        service_latency_ns=Decimal("14"),
        num_transactions_per_initiator=24,
        issue_gap_cpu_ns=Decimal("7"),
        issue_gap_dma_ns=Decimal("11"),
        issue_gap_accel_ns=Decimal("11"),
        burstiness_cpu=2,
        burstiness_dma=1,
        burstiness_accel=1,
        sla_cpu_ns=Decimal("330"),
        sla_dma_ns=Decimal("520"),
        sla_accel_ns=Decimal("380"),
        protected_initiator="cpu0",
    ),
    CaseConfig(
        case_name="shallow_queue_backpressure",
        weights=(1, 1, 1),
        queue_depth=1,
        service_latency_ns=Decimal("18"),
        num_transactions_per_initiator=24,
        issue_gap_cpu_ns=Decimal("6"),
        issue_gap_dma_ns=Decimal("6"),
        issue_gap_accel_ns=Decimal("6"),
        burstiness_cpu=4,
        burstiness_dma=4,
        burstiness_accel=4,
        sla_cpu_ns=Decimal("420"),
        sla_dma_ns=Decimal("520"),
        sla_accel_ns=Decimal("360"),
        protected_initiator="none",
    ),
    CaseConfig(
        case_name="slow_memory_stress",
        weights=(1, 1, 1),
        queue_depth=4,
        service_latency_ns=Decimal("34"),
        num_transactions_per_initiator=24,
        issue_gap_cpu_ns=Decimal("10"),
        issue_gap_dma_ns=Decimal("10"),
        issue_gap_accel_ns=Decimal("10"),
        burstiness_cpu=2,
        burstiness_dma=2,
        burstiness_accel=2,
        sla_cpu_ns=Decimal("420"),
        sla_dma_ns=Decimal("520"),
        sla_accel_ns=Decimal("360"),
        protected_initiator="none",
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
        description="Run Project AT-3 QoS sensitivity and SLA violation lab."
    )
    parser.add_argument(
        "--binary",
        help=(
            "Project AT-3 binary. Relative paths are resolved from repo root. "
            "Default: <build-dir>/qos_sensitivity_sla/"
            "project_at3_qos_sensitivity_sla."
        ),
    )
    parser.add_argument(
        "--build-dir",
        default="build-at3",
        help="CMake build directory used when building the AT-3 target.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_DIR),
        help="Project AT-3 output directory.",
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
    if (
        bundled_lib.exists()
        and any(bundled_lib.glob("libsystemc*"))
        and bundled_include.exists()
    ):
        return [
            f"-DUSER_SYSTEMC_LIB_DIR={bundled_lib}",
            f"-DUSER_SYSTEMC_INCLUDE_DIR={bundled_include}",
        ]

    return []


def binary_for_build_dir(build_dir: Path) -> Path:
    return build_dir / "qos_sensitivity_sla" / TARGET_NAME


def cache_home_directory(cache: Path) -> Optional[Path]:
    if not cache.exists():
        return None
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("CMAKE_HOME_DIRECTORY:INTERNAL="):
            return Path(line.split("=", 1)[1])
    return None


def fallback_build_dir() -> Path:
    return Path(tempfile.gettempdir()) / "systemc_tlm_at3_demo_build"


def usable_build_dir(build_dir: Path) -> Path:
    cache = build_dir / "CMakeCache.txt"
    expected_source = repo_root() / "examples" / "at"
    cached_source = cache_home_directory(cache)

    if cached_source is not None and cached_source.resolve() != expected_source.resolve():
        fallback = fallback_build_dir()
        print(
            "[at3] existing build cache points to another source tree; "
            f"using fallback build dir: {fallback}"
        )
        return fallback

    return build_dir


def build_binary(build_dir: Path) -> Path:
    root = repo_root()
    build_dir = usable_build_dir(build_dir)
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
            "CMake configure failed for Project AT-3:\n"
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
            "CMake build failed for Project AT-3:\n" + result.stdout + result.stderr
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
        raise DemoError(f"AT-3 binary not found: {binary}")
    if not os.access(binary, os.X_OK):
        raise DemoError(f"AT-3 binary is not executable: {binary}")


def run_case(binary: Path, output_dir: Path, config: CaseConfig) -> Path:
    case_dir = output_dir / "model_runs" / config.case_name
    reset_case_dir(case_dir)

    command = [
        str(binary),
        "--case-name",
        config.case_name,
        "--weights",
        ",".join(str(weight) for weight in config.weights),
        "--queue-depth",
        str(config.queue_depth),
        "--service-latency-ns",
        str(config.service_latency_ns),
        "--num-transactions-per-initiator",
        str(config.num_transactions_per_initiator),
        "--issue-gap-cpu-ns",
        str(config.issue_gap_cpu_ns),
        "--issue-gap-dma-ns",
        str(config.issue_gap_dma_ns),
        "--issue-gap-accel-ns",
        str(config.issue_gap_accel_ns),
        "--burstiness-cpu",
        str(config.burstiness_cpu),
        "--burstiness-dma",
        str(config.burstiness_dma),
        "--burstiness-accel",
        str(config.burstiness_accel),
        "--sla-cpu-ns",
        str(config.sla_cpu_ns),
        "--sla-dma-ns",
        str(config.sla_dma_ns),
        "--sla-accel-ns",
        str(config.sla_accel_ns),
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


def weight_for(config: CaseConfig, initiator_name: str) -> int:
    return config.weights[INITIATORS.index(initiator_name)]


def weight_vector(config: CaseConfig) -> str:
    return (
        f"cpu={config.weights[0]},"
        f"dma={config.weights[1]},"
        f"accel={config.weights[2]}"
    )


def expected_share(config: CaseConfig, initiator_name: str) -> Decimal:
    total = Decimal(sum(config.weights))
    return Decimal(weight_for(config, initiator_name)) / total


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
        if row["initiator_name"] not in counts:
            raise DemoError(f"{config.case_name}: unexpected initiator name")
        if row["traffic_class"] != TRAFFIC_CLASSES[row["initiator_name"]]:
            raise DemoError(f"{config.case_name}: wrong traffic_class")
        if row["claim_boundary"] != "PASS":
            raise DemoError(f"{config.case_name}: non-PASS claim_boundary")

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

        total_latency = parse_decimal(row["total_latency_ns"], "total_latency_ns")
        sla_target = parse_decimal(row["sla_target_ns"], "sla_target_ns")
        expected_violation = "YES" if total_latency > sla_target else "NO"
        if row["sla_violation"] != expected_violation:
            raise DemoError(
                f"{config.case_name}: wrong SLA flag for txn {row['txn_id']}"
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
        total_latency = [
            parse_decimal(row["total_latency_ns"], "total_latency_ns")
            for row in initiator_rows
        ]
        arbitration = [
            parse_decimal(row["arbitration_delay_ns"], "arbitration_delay_ns")
            for row in initiator_rows
        ]
        blocked = [
            parse_decimal(row["initiator_blocked_ns"], "initiator_blocked_ns")
            for row in initiator_rows
        ]
        violations = sum(1 for row in initiator_rows if row["sla_violation"] == "YES")
        share = (
            throughputs[initiator_name] / throughput_sum
            if throughput_sum > 0
            else Decimal("0")
        )
        expected = expected_share(config, initiator_name)
        summary_rows.append(
            {
                "case_name": config.case_name,
                "initiator_name": initiator_name,
                "traffic_class": TRAFFIC_CLASSES[initiator_name],
                "weight": str(weight_for(config, initiator_name)),
                "queue_depth": str(config.queue_depth),
                "service_latency_ns": fmt(config.service_latency_ns),
                "sla_target_ns": fmt(
                    parse_decimal(initiator_rows[0]["sla_target_ns"], "sla_target_ns")
                ),
                "num_transactions": str(len(initiator_rows)),
                "avg_total_latency_ns": fmt(average(total_latency)),
                "p50_total_latency_ns": fmt(percentile(total_latency, Decimal("0.50"))),
                "p95_total_latency_ns": fmt(percentile(total_latency, Decimal("0.95"))),
                "p99_total_latency_ns": fmt(percentile(total_latency, Decimal("0.99"))),
                "avg_arbitration_delay_ns": fmt(average(arbitration)),
                "p95_arbitration_delay_ns": fmt(
                    percentile(arbitration, Decimal("0.95"))
                ),
                "avg_blocked_ns": fmt(average(blocked)),
                "backpressure_events": str(
                    sum(1 for row in initiator_rows if row["backpressure"] == "YES")
                ),
                "sla_violations": str(violations),
                "sla_violation_rate": fmt(
                    Decimal(violations) / Decimal(len(initiator_rows))
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
            row["p99_total_latency_ns"], "p99_total_latency_ns"
        )
        for row in initiator_rows
    }
    violation_rate_by_initiator = {
        row["initiator_name"]: parse_decimal(
            row["sla_violation_rate"], "sla_violation_rate"
        )
        for row in initiator_rows
    }
    worst_initiator = max(
        INITIATORS,
        key=lambda name: (violation_rate_by_initiator[name], p99_by_initiator[name]),
    )
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
        "weight_vector": weight_vector(config),
        "queue_depth": str(config.queue_depth),
        "service_latency_ns": fmt(config.service_latency_ns),
        "total_transactions": str(len(rows)),
        "aggregate_throughput_txn_per_us": fmt(aggregate_throughput),
        "total_backpressure_events": str(
            sum(1 for row in rows if row["backpressure"] == "YES")
        ),
        "total_sla_violations": str(
            sum(1 for row in rows if row["sla_violation"] == "YES")
        ),
        "max_sla_violation_rate": fmt(max(violation_rate_by_initiator.values())),
        "max_p99_total_latency_ns": fmt(max(p99_by_initiator.values())),
        "fairness_index": fmt(fairness_index),
        "protected_initiator": config.protected_initiator,
        "worst_initiator": worst_initiator,
        "claim_boundary": "PASS",
    }


def make_recommendation(policy_row: Dict[str, str]) -> Dict[str, str]:
    case_name = policy_row["case_name"]
    max_violation_rate = parse_decimal(
        policy_row["max_sla_violation_rate"], "max_sla_violation_rate"
    )
    total_backpressure = int(policy_row["total_backpressure_events"])
    fairness_index = parse_decimal(policy_row["fairness_index"], "fairness_index")

    if case_name == "slow_memory_stress":
        primary_bottleneck = "target_service_latency"
        action = "reduce_service_latency"
        priority = "high"
    elif case_name == "shallow_queue_backpressure":
        primary_bottleneck = "target_queue_depth"
        action = "increase_queue_depth"
        priority = "high"
    elif case_name == "accel_favored_latency_protection":
        primary_bottleneck = "latency_sensitive_accelerator_arbitration"
        action = "protect_latency_sensitive_initiator"
        priority = "medium"
    elif case_name == "dma_favored_bandwidth_pressure":
        primary_bottleneck = "dma_burstiness_and_weight_bias"
        action = "reduce_burstiness" if total_backpressure > 0 else "adjust_qos_weights"
        priority = "medium"
    elif case_name == "cpu_favored_interactive":
        primary_bottleneck = "interactive_cpu_tail_latency"
        action = "protect_latency_sensitive_initiator"
        priority = "medium"
    elif max_violation_rate == 0 and fairness_index > Decimal("0.90"):
        primary_bottleneck = "none_observed_in_bounded_sweep"
        action = "keep_observing_low_confidence"
        priority = "low"
    else:
        primary_bottleneck = "mixed_arbitration_queueing"
        action = "no_single_dominant_action"
        priority = "medium"

    evidence = (
        f"max_violation_rate={policy_row['max_sla_violation_rate']}; "
        f"max_p99_ns={policy_row['max_p99_total_latency_ns']}; "
        f"backpressure={policy_row['total_backpressure_events']}; "
        f"fairness_index={policy_row['fairness_index']}"
    )
    return {
        "case_name": case_name,
        "primary_bottleneck": primary_bottleneck,
        "recommended_action": action,
        "recommendation_priority": priority,
        "evidence_summary": evidence,
        "protected_initiator": policy_row["protected_initiator"],
        "worst_initiator": policy_row["worst_initiator"],
        "max_sla_violation_rate": policy_row["max_sla_violation_rate"],
        "max_p99_total_latency_ns": policy_row["max_p99_total_latency_ns"],
        "fairness_index": policy_row["fairness_index"],
        "claim_boundary": "PASS",
    }


def write_csv(path: Path, fields: Sequence[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def case_table_row(
    policy_row: Dict[str, str], recommendation_row: Dict[str, str]
) -> str:
    return (
        f"| {policy_row['case_name']} | "
        f"{policy_row['aggregate_throughput_txn_per_us']} | "
        f"{policy_row['total_backpressure_events']} | "
        f"{policy_row['total_sla_violations']} | "
        f"{policy_row['max_sla_violation_rate']} | "
        f"{policy_row['max_p99_total_latency_ns']} | "
        f"{policy_row['fairness_index']} | "
        f"{policy_row['worst_initiator']} | "
        f"{recommendation_row['recommended_action']} |"
    )


def initiator_table_row(row: Dict[str, str]) -> str:
    return (
        f"| {row['case_name']} | {row['initiator_name']} | "
        f"{row['p95_total_latency_ns']} | {row['p99_total_latency_ns']} | "
        f"{row['sla_target_ns']} | {row['sla_violation_rate']} | "
        f"{row['fairness_share']} |"
    )


def write_report(
    path: Path,
    summary_rows: List[Dict[str, str]],
    policy_rows: List[Dict[str, str]],
    recommendation_rows: List[Dict[str, str]],
) -> None:
    recommendation_by_case = {
        row["case_name"]: row for row in recommendation_rows
    }
    lines = [
        "# Project AT-3 QoS Sensitivity and SLA Violation Lab",
        "",
        "schema_version: `at3.0`",
        "",
        "## Architecture Story",
        "",
        "AT-3 extends AT-2 from multi-initiator arbitration and contention into QoS sensitivity and SLA violation analysis. AT-2 shows how `cpu0`, `dma0`, and `accel0` contend for a shared AT path; AT-3 keeps that bounded architecture model and adds QoS-like weighted arbitration, traffic-class SLA targets, queue-depth sensitivity, service-latency sensitivity, and recommendation output.",
        "",
        "The purpose is bounded SoC architecture exploration: compare design-space points, observe p95 / p99 latency, fairness, throughput, back-pressure, and SLA violation rate, then produce an explicit recommendation under a clear claim boundary.",
        "",
        "## QoS Modeling Boundary",
        "",
        "- Weighted arbitration is QoS-like and useful for sensitivity studies.",
        "- It is not AXI QoS compliance.",
        "- It is not CHI QoS compliance.",
        "- It is not a real NoC QoS implementation.",
        "- It is a small SystemC/TLM AT architecture model for early tradeoff exploration.",
        "",
        "## Case Comparison Table",
        "",
        "| case_name | aggregate throughput | total backpressure events | total SLA violations | max SLA violation rate | max p99 total latency | fairness index | worst initiator | recommended action |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    lines.extend(
        case_table_row(row, recommendation_by_case[row["case_name"]])
        for row in policy_rows
    )
    lines.extend(
        [
            "",
            "## Initiator SLA Analysis",
            "",
            "| case_name | initiator | p95 total latency | p99 total latency | SLA target | SLA violation rate | fairness share |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(initiator_table_row(row) for row in summary_rows)
    lines.extend(
        [
            "",
            "## Architecture Interpretation",
            "",
            "- Raising weights can protect one traffic class, but it may hurt fairness or move tail latency to another initiator.",
            "- Shallow queues create back-pressure and SLA violations when traffic bursts arrive faster than the target can accept requests.",
            "- Slow memory service is a target bottleneck; arbitration cannot fully compensate when service latency dominates total latency.",
            "- QoS tuning is most useful when arbitration is the dominant bottleneck. When target service time dominates, the better action is to reduce service latency or change the memory-side design point.",
            "",
            "## Claim Boundary / Unsupported Claims",
            "",
            "- This is a SystemC/TLM AT teaching and architecture modeling lab.",
            "- This is not AXI / CHI QoS compliance.",
            "- This is not a cycle-accurate interconnect model.",
            "- This is not a real NoC model.",
            "- This is not a cache coherence model.",
            "- This is not silicon validation.",
            "- This is not production signoff.",
            "- This is not a real DRAM timing model.",
            "",
            "## Portfolio / Interview Narrative",
            "",
            "- AT-1 shows transaction phase timing.",
            "- AT-2 shows arbitration, contention, fairness, and tail latency.",
            "- AT-3 shows QoS sensitivity, SLA violation detection, and architecture recommendation.",
            "- This demonstrates how early architecture modeling can guide trade-offs before RTL.",
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
        "axi qos compliance",
        "chi qos compliance",
        "axi / chi qos compliance",
        "cycle-accurate interconnect model",
        "cycle accurate interconnect model",
        "real noc model",
        "cache coherence model",
        "silicon validation",
        "production signoff",
        "real dram timing model",
        "silicon validated",
    ]
    for line_number, line in enumerate(
        report_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        for phrase in phrases:
            if line_has_positive_claim(line, phrase):
                raise DemoError(
                    f"forbidden positive claim in report line {line_number}: {line}"
                )


def row_for(
    summary_rows: List[Dict[str, str]], case_name: str, initiator_name: str
) -> Dict[str, str]:
    for row in summary_rows:
        if row["case_name"] == case_name and row["initiator_name"] == initiator_name:
            return row
    raise DemoError(f"missing summary row for {case_name}/{initiator_name}")


def policy_for(
    policy_rows: List[Dict[str, str]], case_name: str
) -> Dict[str, str]:
    for row in policy_rows:
        if row["case_name"] == case_name:
            return row
    raise DemoError(f"missing policy row for {case_name}")


def recommendation_for(
    recommendation_rows: List[Dict[str, str]], case_name: str
) -> Dict[str, str]:
    for row in recommendation_rows:
        if row["case_name"] == case_name:
            return row
    raise DemoError(f"missing recommendation row for {case_name}")


def acceptance_checks(
    summary_rows: List[Dict[str, str]],
    policy_rows: List[Dict[str, str]],
    recommendation_rows: List[Dict[str, str]],
    traces_by_case: Dict[str, List[Dict[str, str]]],
    report_path: Path,
) -> None:
    case_count = len(CASES)
    if len(traces_by_case) != case_count:
        raise DemoError(f"case count {len(traces_by_case)} != {case_count}")
    if len(summary_rows) != case_count * len(INITIATORS):
        raise DemoError(
            f"summary row count {len(summary_rows)} != {case_count * len(INITIATORS)}"
        )
    if len(policy_rows) != case_count:
        raise DemoError(f"policy sweep row count {len(policy_rows)} != {case_count}")
    if len(recommendation_rows) != case_count:
        raise DemoError(
            f"recommendations row count {len(recommendation_rows)} != {case_count}"
        )
    combined_rows = summary_rows + policy_rows + recommendation_rows
    if not all(row["claim_boundary"] == "PASS" for row in combined_rows):
        raise DemoError("not all claim_boundary fields are PASS")

    balanced_accel = row_for(summary_rows, "balanced_qos_nominal", "accel0")
    protected_accel = row_for(
        summary_rows, "accel_favored_latency_protection", "accel0"
    )
    protected_violation_lower = parse_decimal(
        protected_accel["sla_violation_rate"], "sla_violation_rate"
    ) < parse_decimal(balanced_accel["sla_violation_rate"], "sla_violation_rate")
    protected_p99_lower = parse_decimal(
        protected_accel["p99_total_latency_ns"], "p99_total_latency_ns"
    ) < parse_decimal(balanced_accel["p99_total_latency_ns"], "p99_total_latency_ns")
    if not (protected_violation_lower or protected_p99_lower):
        raise DemoError(
            "accel_favored_latency_protection did not improve accel0 violation rate "
            "or p99 latency over balanced_qos_nominal"
        )

    balanced_policy = policy_for(policy_rows, "balanced_qos_nominal")
    shallow_policy = policy_for(policy_rows, "shallow_queue_backpressure")
    if int(shallow_policy["total_backpressure_events"]) <= int(
        balanced_policy["total_backpressure_events"]
    ):
        raise DemoError(
            "shallow_queue_backpressure did not increase total backpressure events"
        )

    slow_policy = policy_for(policy_rows, "slow_memory_stress")
    if int(slow_policy["total_sla_violations"]) <= int(
        balanced_policy["total_sla_violations"]
    ):
        raise DemoError("slow_memory_stress did not increase total SLA violations")

    slow_recommendation = recommendation_for(recommendation_rows, "slow_memory_stress")
    if slow_recommendation["recommended_action"] not in {
        "reduce_service_latency",
        "no_single_dominant_action",
    }:
        raise DemoError(
            "slow_memory_stress recommendation is not reduce_service_latency "
            "or no_single_dominant_action"
        )

    if not report_path.exists():
        raise DemoError(f"missing report: {report_path}")
    report = report_path.read_text(encoding="utf-8")
    required_markers = [
        "## Architecture Story",
        "## QoS Modeling Boundary",
        "## Case Comparison Table",
        "## Initiator SLA Analysis",
        "## Architecture Interpretation",
        "## Claim Boundary / Unsupported Claims",
        "## Portfolio / Interview Narrative",
        "This is a SystemC/TLM AT teaching and architecture modeling lab.",
        "This is not AXI / CHI QoS compliance.",
        "This is not a cycle-accurate interconnect model.",
        "This is not a real NoC model.",
        "This is not a cache coherence model.",
        "This is not silicon validation.",
        "This is not production signoff.",
        "This is not a real DRAM timing model.",
    ]
    missing = [marker for marker in required_markers if marker not in report]
    if missing:
        raise DemoError("report is missing markers: " + ", ".join(missing))
    forbidden_claim_scan(report_path)


def print_outputs(output_dir: Path) -> None:
    print("[at3] Output files:")
    print(f"[at3]   summary: {output_dir / 'project_at3_summary.csv'}")
    print(f"[at3]   policy sweep: {output_dir / 'project_at3_policy_sweep.csv'}")
    print(f"[at3]   recommendations: {output_dir / 'project_at3_recommendations.csv'}")
    print(f"[at3]   report: {output_dir / 'project_at3_report.md'}")
    for config in CASES:
        print(
            "[at3]   trace: "
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
    recommendation_rows: List[Dict[str, str]] = []
    traces_by_case: Dict[str, List[Dict[str, str]]] = {}
    failures: List[str] = []

    for config in CASES:
        print(f"[at3] running case={config.case_name}")
        try:
            trace_path = run_case(binary, output_dir, config)
            rows = read_trace(trace_path)
            validate_trace(config, rows)
            case_summary = summarize_case(config, rows)
            policy_row = summarize_policy(config, rows, case_summary)
            recommendation_row = make_recommendation(policy_row)
            summary_rows.extend(case_summary)
            policy_rows.append(policy_row)
            recommendation_rows.append(recommendation_row)
            traces_by_case[config.case_name] = rows
            print(f"[at3] case={config.case_name} status=OK")
        except DemoError as exc:
            failures.append(str(exc))
            print(f"[at3] case={config.case_name} status=FAIL error={exc}")
            if not args.keep_going:
                raise

    summary_path = output_dir / "project_at3_summary.csv"
    policy_sweep_path = output_dir / "project_at3_policy_sweep.csv"
    recommendations_path = output_dir / "project_at3_recommendations.csv"
    report_path = output_dir / "project_at3_report.md"
    write_csv(summary_path, SUMMARY_FIELDS, summary_rows)
    write_csv(policy_sweep_path, POLICY_SWEEP_FIELDS, policy_rows)
    write_csv(recommendations_path, RECOMMENDATION_FIELDS, recommendation_rows)
    write_report(report_path, summary_rows, policy_rows, recommendation_rows)

    if failures:
        raise DemoError("; ".join(failures))

    acceptance_checks(
        summary_rows,
        policy_rows,
        recommendation_rows,
        traces_by_case,
        report_path,
    )
    print_outputs(output_dir)
    print("Project AT-3 QoS Sensitivity and SLA Violation Lab PASS")
    print(f"cases={len(CASES)}")
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
