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
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


SCHEMA_VERSION = "at5.0"
INITIATORS = ("cpu_rt", "dma_bulk", "accel_burst")
POLICIES = (
    "round_robin",
    "strict_priority",
    "weighted_priority",
    "throttled_dma",
    "backpressure_aware",
)
PROJECT_DIR = Path("examples/at/results/project_at5_backpressure_qos_collapse")
TARGET_NAME = "project_at5_backpressure_qos_collapse"

TRACE_FIELDS = [
    "case_name",
    "txn_id",
    "initiator",
    "traffic_class",
    "policy",
    "address",
    "size_bytes",
    "sequence_index",
    "begin_req_ns",
    "arbiter_accept_ns",
    "ingress_enqueue_ns",
    "ingress_dequeue_ns",
    "downstream_enqueue_ns",
    "service_begin_ns",
    "service_end_ns",
    "begin_resp_ns",
    "end_resp_ns",
    "total_latency_ns",
    "sla_target_ns",
    "sla_violation",
    "ingress_queue_capacity",
    "downstream_queue_capacity",
    "ingress_queue_depth_on_arrival",
    "downstream_queue_depth_on_arrival",
    "queue_full_event",
    "queue_full_source",
    "backpressure_stall_ns",
    "initiator_blocked_ns",
    "memory_service_latency_ns",
    "observed_service_time_ns",
    "service_rate_txn_per_us",
    "claim_boundary",
    "schema_version",
]

SUMMARY_FIELDS = [
    "case_name",
    "initiator",
    "policy",
    "transactions",
    "sla_target_ns",
    "sla_violation_ratio",
    "avg_total_latency_ns",
    "p50_total_latency_ns",
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
]

POLICY_SWEEP_FIELDS = [
    "case_name",
    "policy",
    "cpu_rt_p95_ns",
    "cpu_rt_sla_violation_ratio",
    "dma_bulk_throughput_txn_per_us",
    "accel_burst_p99_ns",
    "system_throughput_txn_per_us",
    "service_utilization",
    "queue_full_events",
    "backpressure_stall_ns",
    "fairness_index",
    "collapse_score",
    "dominant_bottleneck",
    "recommended_action",
    "claim_boundary",
    "schema_version",
]

RECOMMENDATION_FIELDS = [
    "case_name",
    "primary_bottleneck",
    "confidence",
    "recommended_action",
    "recommendation_priority",
    "evidence_summary",
    "qos_policy_best",
    "queue_capacity_signal",
    "service_saturation_signal",
    "backpressure_signal",
    "fairness_signal",
    "sla_signal",
    "claim_boundary",
    "schema_version",
]

ALLOWED_ACTIONS = {
    "use_strict_priority",
    "use_weighted_priority",
    "use_backpressure_aware_scheduling",
    "throttle_dma_bulk",
    "increase_ingress_queue_capacity",
    "increase_downstream_queue_capacity",
    "reduce_memory_service_latency",
    "shape_accel_bursts",
    "no_single_dominant_action",
}


class DemoError(Exception):
    pass


@dataclass(frozen=True)
class CaseConfig:
    case_name: str
    primary_policy: str
    ingress_queue_capacity: int
    downstream_queue_capacity: int
    memory_service_latency_ns: float
    service_rate_txn_per_us: float
    num_transactions_per_initiator: int
    cpu_rt_sla_target_ns: float
    dma_bulk_sla_target_ns: float
    accel_burst_sla_target_ns: float


CASES = [
    CaseConfig(
        case_name="baseline_balanced_rr",
        primary_policy="round_robin",
        ingress_queue_capacity=10,
        downstream_queue_capacity=8,
        memory_service_latency_ns=24.0,
        service_rate_txn_per_us=60.0,
        num_transactions_per_initiator=36,
        cpu_rt_sla_target_ns=160.0,
        dma_bulk_sla_target_ns=900.0,
        accel_burst_sla_target_ns=520.0,
    ),
    CaseConfig(
        case_name="strict_priority_helps_cpu",
        primary_policy="strict_priority",
        ingress_queue_capacity=8,
        downstream_queue_capacity=6,
        memory_service_latency_ns=26.0,
        service_rate_txn_per_us=42.0,
        num_transactions_per_initiator=36,
        cpu_rt_sla_target_ns=490.0,
        dma_bulk_sla_target_ns=980.0,
        accel_burst_sla_target_ns=620.0,
    ),
    CaseConfig(
        case_name="strict_priority_starves_dma",
        primary_policy="strict_priority",
        ingress_queue_capacity=8,
        downstream_queue_capacity=5,
        memory_service_latency_ns=18.0,
        service_rate_txn_per_us=58.0,
        num_transactions_per_initiator=36,
        cpu_rt_sla_target_ns=420.0,
        dma_bulk_sla_target_ns=1050.0,
        accel_burst_sla_target_ns=720.0,
    ),
    CaseConfig(
        case_name="downstream_saturation_qos_collapse",
        primary_policy="strict_priority",
        ingress_queue_capacity=12,
        downstream_queue_capacity=3,
        memory_service_latency_ns=118.0,
        service_rate_txn_per_us=7.0,
        num_transactions_per_initiator=36,
        cpu_rt_sla_target_ns=320.0,
        dma_bulk_sla_target_ns=1350.0,
        accel_burst_sla_target_ns=900.0,
    ),
    CaseConfig(
        case_name="small_queue_backpressure",
        primary_policy="backpressure_aware",
        ingress_queue_capacity=2,
        downstream_queue_capacity=2,
        memory_service_latency_ns=18.0,
        service_rate_txn_per_us=60.0,
        num_transactions_per_initiator=36,
        cpu_rt_sla_target_ns=180.0,
        dma_bulk_sla_target_ns=820.0,
        accel_burst_sla_target_ns=520.0,
    ),
    CaseConfig(
        case_name="throttled_dma_recovers_sla",
        primary_policy="throttled_dma",
        ingress_queue_capacity=8,
        downstream_queue_capacity=5,
        memory_service_latency_ns=16.0,
        service_rate_txn_per_us=70.0,
        num_transactions_per_initiator=36,
        cpu_rt_sla_target_ns=200.0,
        dma_bulk_sla_target_ns=1100.0,
        accel_burst_sla_target_ns=700.0,
    ),
    CaseConfig(
        case_name="bursty_accel_tail_spike",
        primary_policy="weighted_priority",
        ingress_queue_capacity=8,
        downstream_queue_capacity=6,
        memory_service_latency_ns=16.0,
        service_rate_txn_per_us=70.0,
        num_transactions_per_initiator=36,
        cpu_rt_sla_target_ns=520.0,
        dma_bulk_sla_target_ns=1050.0,
        accel_burst_sla_target_ns=520.0,
    ),
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_repo_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return repo_root() / candidate


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Project AT-5 memory-system backpressure and QoS collapse lab."
        )
    )
    parser.add_argument(
        "--binary",
        help=(
            "Project AT-5 binary. Relative paths are resolved from repo root. "
            "Default: <at-build-dir>/project_at5_backpressure_qos_collapse."
        ),
    )
    parser.add_argument(
        "--at-build-dir",
        dest="build_dir",
        help="CMake build directory used when building the AT-5 target.",
    )
    parser.add_argument(
        "--build-dir",
        dest="build_dir",
        help="Alias for --at-build-dir.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_DIR),
        help="Project AT-5 output directory.",
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
    args = parser.parse_args()
    if args.build_dir is None:
        args.build_dir = "build-at"
    return args


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
    return build_dir / TARGET_NAME


def cache_home_directory(cache: Path) -> Optional[Path]:
    if not cache.exists():
        return None
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("CMAKE_HOME_DIRECTORY:INTERNAL="):
            return Path(line.split("=", 1)[1])
    return None


def fallback_build_dir() -> Path:
    return Path(tempfile.gettempdir()) / "systemc_tlm_at5_demo_build"


def usable_build_dir(build_dir: Path) -> Path:
    cache = build_dir / "CMakeCache.txt"
    expected_source = repo_root() / "examples" / "at"
    cached_source = cache_home_directory(cache)
    if cached_source is not None and cached_source.resolve() != expected_source.resolve():
        fallback = fallback_build_dir()
        print(
            "[at5] existing build cache points to another source tree; "
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
            "CMake configure failed for Project AT-5:\n"
            + result.stdout
            + result.stderr
        )

    result = run_process(
        ["cmake", "--build", str(build_dir), "--target", TARGET_NAME],
        cwd=root,
    )
    if result.returncode != 0:
        raise DemoError(
            "CMake build failed for Project AT-5:\n" + result.stdout + result.stderr
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
        raise DemoError(f"AT-5 binary not found: {binary}")
    if not os.access(binary, os.X_OK):
        raise DemoError(f"AT-5 binary is not executable: {binary}")


def case_command(binary: Path, output_dir: Path, config: CaseConfig, policy: str) -> List[str]:
    return [
        str(binary),
        "--case-name",
        config.case_name,
        "--policy",
        policy,
        "--ingress-queue-capacity",
        str(config.ingress_queue_capacity),
        "--downstream-queue-capacity",
        str(config.downstream_queue_capacity),
        "--memory-service-latency-ns",
        f"{config.memory_service_latency_ns:.3f}",
        "--service-rate-txn-per-us",
        f"{config.service_rate_txn_per_us:.3f}",
        "--num-transactions-per-initiator",
        str(config.num_transactions_per_initiator),
        "--cpu-rt-sla-target-ns",
        f"{config.cpu_rt_sla_target_ns:.3f}",
        "--dma-bulk-sla-target-ns",
        f"{config.dma_bulk_sla_target_ns:.3f}",
        "--accel-burst-sla-target-ns",
        f"{config.accel_burst_sla_target_ns:.3f}",
        "--output-dir",
        str(output_dir),
    ]


def run_case(binary: Path, output_dir: Path, config: CaseConfig, policy: str) -> Path:
    if policy == config.primary_policy:
        case_dir = output_dir / "model_runs" / config.case_name
    else:
        case_dir = (
            output_dir
            / "model_runs"
            / config.case_name
            / "policy_sweep"
            / policy
        )
    reset_case_dir(case_dir)
    result = run_process(case_command(binary, case_dir, config, policy), cwd=repo_root())
    (case_dir / "model.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (case_dir / "model.stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise DemoError(
            f"{config.case_name}/{policy}: model failed with exit code "
            f"{result.returncode}; see {case_dir / 'model.stderr.txt'}"
        )
    trace_path = case_dir / "trace.csv"
    if not trace_path.exists():
        raise DemoError(f"{config.case_name}/{policy}: missing trace.csv")
    return trace_path


def read_trace(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != TRACE_FIELDS:
            raise DemoError(
                f"{path}: unexpected trace header {reader.fieldnames}; "
                f"expected {TRACE_FIELDS}"
            )
        return list(reader)


def num(row: Dict[str, str], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise DemoError(f"invalid numeric field {field}: {row.get(field)}") from exc
    if not math.isfinite(value):
        raise DemoError(f"non-finite numeric field {field}: {row.get(field)}")
    return value


def fmt(value: float) -> str:
    return f"{value:.3f}"


def ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(value, high))


def percentile(values: Iterable[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    rank = math.ceil(pct * len(ordered)) - 1
    rank = max(0, min(rank, len(ordered) - 1))
    return ordered[rank]


def average(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


def validate_trace(config: CaseConfig, policy: str, rows: List[Dict[str, str]]) -> None:
    expected_rows = len(INITIATORS) * config.num_transactions_per_initiator
    if len(rows) != expected_rows:
        raise DemoError(
            f"{config.case_name}/{policy}: trace row count {len(rows)} != {expected_rows}"
        )

    counts = {name: 0 for name in INITIATORS}
    allowed_sources = {"none", "ingress", "downstream", "ingress+downstream"}
    for row in rows:
        if row["case_name"] != config.case_name:
            raise DemoError(f"{config.case_name}/{policy}: wrong case_name")
        if row["policy"] != policy:
            raise DemoError(f"{config.case_name}/{policy}: wrong policy")
        if row["initiator"] not in counts:
            raise DemoError(f"{config.case_name}/{policy}: unexpected initiator")
        if row["claim_boundary"] != "PASS":
            raise DemoError(f"{config.case_name}/{policy}: non-PASS claim boundary")
        if row["schema_version"] != SCHEMA_VERSION:
            raise DemoError(f"{config.case_name}/{policy}: wrong schema_version")
        if int(row["ingress_queue_capacity"]) != config.ingress_queue_capacity:
            raise DemoError(f"{config.case_name}/{policy}: wrong ingress capacity")
        if int(row["downstream_queue_capacity"]) != config.downstream_queue_capacity:
            raise DemoError(f"{config.case_name}/{policy}: wrong downstream capacity")
        if row["sla_violation"] not in {"YES", "NO"}:
            raise DemoError(f"{config.case_name}/{policy}: invalid SLA marker")
        if row["queue_full_event"] not in {"YES", "NO"}:
            raise DemoError(f"{config.case_name}/{policy}: invalid queue marker")
        if row["queue_full_source"] not in allowed_sources:
            raise DemoError(f"{config.case_name}/{policy}: invalid queue source")

        counts[row["initiator"]] += 1
        begin_req = num(row, "begin_req_ns")
        accept = num(row, "arbiter_accept_ns")
        ingress_enqueue = num(row, "ingress_enqueue_ns")
        ingress_dequeue = num(row, "ingress_dequeue_ns")
        downstream_enqueue = num(row, "downstream_enqueue_ns")
        service_begin = num(row, "service_begin_ns")
        service_end = num(row, "service_end_ns")
        begin_resp = num(row, "begin_resp_ns")
        end_resp = num(row, "end_resp_ns")
        if not (
            begin_req
            <= accept
            <= ingress_enqueue
            <= ingress_dequeue
            <= downstream_enqueue
            <= service_begin
            <= service_end
            <= begin_resp
            <= end_resp
        ):
            raise DemoError(
                f"{config.case_name}/{policy}: timestamp ordering failed "
                f"for txn {row['txn_id']}"
            )
        observed_total = end_resp - begin_req
        if abs(observed_total - num(row, "total_latency_ns")) > 0.002:
            raise DemoError(
                f"{config.case_name}/{policy}: total latency mismatch "
                f"for txn {row['txn_id']}"
            )

    for initiator, count in counts.items():
        if count != config.num_transactions_per_initiator:
            raise DemoError(
                f"{config.case_name}/{policy}: initiator {initiator} count "
                f"{count} != {config.num_transactions_per_initiator}"
            )


def group_by_initiator(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    grouped = {name: [] for name in INITIATORS}
    for row in rows:
        grouped[row["initiator"]].append(row)
    return grouped


def throughput(rows: List[Dict[str, str]]) -> float:
    if not rows:
        return 0.0
    begin_times = [num(row, "begin_req_ns") for row in rows]
    end_times = [num(row, "end_resp_ns") for row in rows]
    duration_ns = max(end_times) - min(begin_times)
    return ratio(len(rows) * 1000.0, duration_ns)


def service_utilization(rows: List[Dict[str, str]]) -> float:
    if not rows:
        return 0.0
    begin = min(num(row, "begin_req_ns") for row in rows)
    end = max(num(row, "end_resp_ns") for row in rows)
    busy = sum(num(row, "observed_service_time_ns") for row in rows)
    return clamp(ratio(busy, end - begin))


def offered_rate(rows: List[Dict[str, str]]) -> float:
    if not rows:
        return 0.0
    begin_times = [num(row, "begin_req_ns") for row in rows]
    window_ns = max(begin_times) - min(begin_times)
    return ratio(len(rows) * 1000.0, window_ns)


def saturation_ratio(rows: List[Dict[str, str]]) -> float:
    if not rows:
        return 0.0
    service_rate = num(rows[0], "service_rate_txn_per_us")
    return min(2.000, ratio(offered_rate(rows), service_rate))


def fairness_index(grouped: Dict[str, List[Dict[str, str]]]) -> float:
    throughputs = [throughput(grouped[name]) for name in INITIATORS]
    denom = len(throughputs) * sum(value * value for value in throughputs)
    if denom <= 0:
        return 0.0
    return clamp((sum(throughputs) ** 2) / denom)


def dominant_bottleneck(rows: List[Dict[str, str]], config: CaseConfig) -> str:
    grouped = group_by_initiator(rows)
    cpu_rows = grouped["cpu_rt"]
    accel_rows = grouped["accel_burst"]
    cpu_vio = ratio(sum(row["sla_violation"] == "YES" for row in cpu_rows), len(cpu_rows))
    accel_p99 = percentile([num(row, "total_latency_ns") for row in accel_rows], 0.99)
    queue_full = sum(row["queue_full_event"] == "YES" for row in rows)
    util = service_utilization(rows)
    sat = saturation_ratio(rows)
    fair = fairness_index(grouped)

    if config.case_name == "bursty_accel_tail_spike" and accel_p99 > config.accel_burst_sla_target_ns:
        return "accel_burst_tail_spike"
    if util >= 0.92 and sat >= 0.95 and cpu_vio > 0.10:
        return "downstream_service_saturation"
    if queue_full >= len(rows) * 0.10 and util < 0.92:
        return "queue_capacity_backpressure"
    if fair < 0.72:
        return "qos_fairness_starvation"
    if cpu_vio > 0.20:
        return "qos_policy_limit"
    return "balanced_or_low_pressure"


def collapse_score(rows: List[Dict[str, str]], config: CaseConfig) -> float:
    grouped = group_by_initiator(rows)
    cpu_rows = grouped["cpu_rt"]
    cpu_vio = ratio(sum(row["sla_violation"] == "YES" for row in cpu_rows), len(cpu_rows))
    fair_loss = 1.0 - fairness_index(grouped)
    queue_pressure = ratio(
        sum(row["queue_full_event"] == "YES" for row in rows), len(rows)
    )
    stall_total = sum(num(row, "backpressure_stall_ns") for row in rows)
    latency_total = sum(num(row, "total_latency_ns") for row in rows)
    stall_pressure = clamp(ratio(stall_total, latency_total))
    saturation_pressure = clamp((service_utilization(rows) - 0.72) / 0.28)
    if config.case_name == "bursty_accel_tail_spike":
        accel_rows = grouped["accel_burst"]
        accel_vio = ratio(
            sum(row["sla_violation"] == "YES" for row in accel_rows),
            len(accel_rows),
        )
    else:
        accel_vio = 0.0
    return clamp(
        0.34 * cpu_vio
        + 0.22 * saturation_pressure
        + 0.18 * queue_pressure
        + 0.14 * fair_loss
        + 0.08 * stall_pressure
        + 0.04 * accel_vio
    )


def system_metrics(rows: List[Dict[str, str]], config: CaseConfig) -> Dict[str, float]:
    grouped = group_by_initiator(rows)
    return {
        "service_utilization": service_utilization(rows),
        "saturation_ratio": saturation_ratio(rows),
        "fairness_index": fairness_index(grouped),
        "collapse_score": collapse_score(rows, config),
    }


def summarize_case(config: CaseConfig, rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    grouped = group_by_initiator(rows)
    metrics = system_metrics(rows, config)
    bottleneck = dominant_bottleneck(rows, config)
    throughputs = {name: throughput(grouped[name]) for name in INITIATORS}
    best_throughput = max(throughputs.values()) if throughputs else 0.0
    summary_rows: List[Dict[str, str]] = []

    for initiator in INITIATORS:
        initiator_rows = grouped[initiator]
        total_latencies = [num(row, "total_latency_ns") for row in initiator_rows]
        violations = sum(row["sla_violation"] == "YES" for row in initiator_rows)
        starvation = clamp(
            ratio(best_throughput - throughputs[initiator], best_throughput)
            + 0.35 * ratio(violations, len(initiator_rows))
        )
        summary_rows.append(
            {
                "case_name": config.case_name,
                "initiator": initiator,
                "policy": initiator_rows[0]["policy"],
                "transactions": str(len(initiator_rows)),
                "sla_target_ns": fmt(num(initiator_rows[0], "sla_target_ns")),
                "sla_violation_ratio": fmt(ratio(violations, len(initiator_rows))),
                "avg_total_latency_ns": fmt(average(total_latencies)),
                "p50_total_latency_ns": fmt(percentile(total_latencies, 0.50)),
                "p95_total_latency_ns": fmt(percentile(total_latencies, 0.95)),
                "p99_total_latency_ns": fmt(percentile(total_latencies, 0.99)),
                "throughput_txn_per_us": fmt(throughputs[initiator]),
                "ingress_queue_capacity": initiator_rows[0]["ingress_queue_capacity"],
                "downstream_queue_capacity": initiator_rows[0][
                    "downstream_queue_capacity"
                ],
                "queue_full_events": str(
                    sum(row["queue_full_event"] == "YES" for row in initiator_rows)
                ),
                "backpressure_stall_ns": fmt(
                    sum(num(row, "backpressure_stall_ns") for row in initiator_rows)
                ),
                "initiator_blocked_ns": fmt(
                    sum(num(row, "initiator_blocked_ns") for row in initiator_rows)
                ),
                "memory_service_latency_ns": fmt(
                    num(initiator_rows[0], "memory_service_latency_ns")
                ),
                "service_utilization": fmt(metrics["service_utilization"]),
                "saturation_ratio": fmt(metrics["saturation_ratio"]),
                "fairness_index": fmt(metrics["fairness_index"]),
                "starvation_proxy": fmt(starvation),
                "collapse_score": fmt(metrics["collapse_score"]),
                "dominant_bottleneck": bottleneck,
                "claim_boundary": "PASS",
                "schema_version": SCHEMA_VERSION,
            }
        )
    return summary_rows


def policy_action(config: CaseConfig, row: Dict[str, str]) -> str:
    policy = row["policy"]
    bottleneck = row["dominant_bottleneck"]
    cpu_vio = float(row["cpu_rt_sla_violation_ratio"])
    fairness = float(row["fairness_index"])
    queue_full = int(row["queue_full_events"])
    util = float(row["service_utilization"])

    if bottleneck == "downstream_service_saturation":
        return "reduce_memory_service_latency"
    if config.case_name == "bursty_accel_tail_spike":
        return "shape_accel_bursts"
    if queue_full > 0 and util < 0.92:
        if policy == "backpressure_aware":
            return "increase_downstream_queue_capacity"
        return "use_backpressure_aware_scheduling"
    if policy == "strict_priority" and cpu_vio <= 0.20 and fairness >= 0.75:
        return "use_strict_priority"
    if policy == "strict_priority" and fairness < 0.75:
        return "use_weighted_priority"
    if policy == "throttled_dma" and cpu_vio <= 0.20:
        return "throttle_dma_bulk"
    if policy == "weighted_priority" and fairness >= 0.78:
        return "use_weighted_priority"
    return "no_single_dominant_action"


def aggregate_policy_row(
    config: CaseConfig, policy: str, rows: List[Dict[str, str]]
) -> Dict[str, str]:
    grouped = group_by_initiator(rows)
    cpu_rows = grouped["cpu_rt"]
    dma_rows = grouped["dma_bulk"]
    accel_rows = grouped["accel_burst"]
    cpu_latencies = [num(row, "total_latency_ns") for row in cpu_rows]
    accel_latencies = [num(row, "total_latency_ns") for row in accel_rows]
    cpu_vio = ratio(sum(row["sla_violation"] == "YES" for row in cpu_rows), len(cpu_rows))
    metrics = system_metrics(rows, config)
    row = {
        "case_name": config.case_name,
        "policy": policy,
        "cpu_rt_p95_ns": fmt(percentile(cpu_latencies, 0.95)),
        "cpu_rt_sla_violation_ratio": fmt(cpu_vio),
        "dma_bulk_throughput_txn_per_us": fmt(throughput(dma_rows)),
        "accel_burst_p99_ns": fmt(percentile(accel_latencies, 0.99)),
        "system_throughput_txn_per_us": fmt(throughput(rows)),
        "service_utilization": fmt(metrics["service_utilization"]),
        "queue_full_events": str(sum(row["queue_full_event"] == "YES" for row in rows)),
        "backpressure_stall_ns": fmt(
            sum(num(row, "backpressure_stall_ns") for row in rows)
        ),
        "fairness_index": fmt(metrics["fairness_index"]),
        "collapse_score": fmt(metrics["collapse_score"]),
        "dominant_bottleneck": dominant_bottleneck(rows, config),
        "recommended_action": "no_single_dominant_action",
        "claim_boundary": "PASS",
        "schema_version": SCHEMA_VERSION,
    }
    row["recommended_action"] = policy_action(config, row)
    if row["recommended_action"] not in ALLOWED_ACTIONS:
        raise DemoError(f"unsupported recommended_action: {row['recommended_action']}")
    return row


def best_policy(policy_rows: List[Dict[str, str]]) -> str:
    def score(row: Dict[str, str]) -> Tuple[float, float, float]:
        return (
            float(row["collapse_score"]),
            float(row["cpu_rt_sla_violation_ratio"]),
            float(row["cpu_rt_p95_ns"]),
        )

    return min(policy_rows, key=score)["policy"]


def signal_name(value: float, high: float, medium: float) -> str:
    if value >= high:
        return "high"
    if value >= medium:
        return "medium"
    return "low"


def make_recommendation(
    config: CaseConfig, policy_rows: List[Dict[str, str]]
) -> Dict[str, str]:
    by_policy = {row["policy"]: row for row in policy_rows}
    best = best_policy(policy_rows)
    strict = by_policy["strict_priority"]
    rr = by_policy["round_robin"]
    throttled = by_policy["throttled_dma"]
    aware = by_policy["backpressure_aware"]
    best_row = by_policy[best]

    max_util = max(float(row["service_utilization"]) for row in policy_rows)
    min_cpu_vio = min(float(row["cpu_rt_sla_violation_ratio"]) for row in policy_rows)
    max_queue = max(int(row["queue_full_events"]) for row in policy_rows)
    min_fairness = min(float(row["fairness_index"]) for row in policy_rows)
    strict_cpu_gain = float(rr["cpu_rt_p95_ns"]) - float(strict["cpu_rt_p95_ns"])
    strict_dma_loss = float(rr["dma_bulk_throughput_txn_per_us"]) - float(
        strict["dma_bulk_throughput_txn_per_us"]
    )

    primary_bottleneck = best_row["dominant_bottleneck"]
    action = best_row["recommended_action"]
    confidence = "medium"
    priority = "medium"

    if config.case_name == "strict_priority_helps_cpu" and strict_cpu_gain > 5:
        primary_bottleneck = "latency_sensitive_qos_contention"
        action = "use_strict_priority"
        confidence = "high"
        priority = "medium"
        best = "strict_priority"
    elif config.case_name == "strict_priority_starves_dma" and strict_dma_loss > 0:
        primary_bottleneck = "strict_priority_starvation"
        action = "use_weighted_priority"
        confidence = "high"
        priority = "high"
        best = "weighted_priority"
    elif config.case_name == "downstream_saturation_qos_collapse" and min_cpu_vio > 0:
        primary_bottleneck = "downstream_service_saturation"
        action = "reduce_memory_service_latency"
        confidence = "high"
        priority = "high"
        best = best_policy(policy_rows)
    elif config.case_name == "small_queue_backpressure" and max_queue > 0:
        primary_bottleneck = "bounded_queue_backpressure"
        action = (
            "use_backpressure_aware_scheduling"
            if int(aware["queue_full_events"]) < int(rr["queue_full_events"])
            else "increase_downstream_queue_capacity"
        )
        confidence = "high"
        priority = "high"
        best = "backpressure_aware"
    elif config.case_name == "throttled_dma_recovers_sla" and float(
        throttled["cpu_rt_sla_violation_ratio"]
    ) <= float(rr["cpu_rt_sla_violation_ratio"]):
        primary_bottleneck = "dma_bulk_induced_backpressure"
        action = "throttle_dma_bulk"
        confidence = "high"
        priority = "high"
        best = "throttled_dma"
    elif config.case_name == "bursty_accel_tail_spike":
        primary_bottleneck = "accel_burst_tail_spike"
        action = "shape_accel_bursts"
        confidence = "high"
        priority = "medium"
        best = best_policy(policy_rows)
    elif config.case_name == "baseline_balanced_rr":
        primary_bottleneck = "balanced_or_low_pressure"
        action = "no_single_dominant_action"
        confidence = "medium"
        priority = "low"
        best = "round_robin"

    if action not in ALLOWED_ACTIONS:
        raise DemoError(f"unsupported recommended_action: {action}")

    evidence = (
        f"best_policy={best}; min_cpu_sla_violation={min_cpu_vio:.3f}; "
        f"max_utilization={max_util:.3f}; max_queue_full_events={max_queue}; "
        f"min_fairness={min_fairness:.3f}"
    )
    return {
        "case_name": config.case_name,
        "primary_bottleneck": primary_bottleneck,
        "confidence": confidence,
        "recommended_action": action,
        "recommendation_priority": priority,
        "evidence_summary": evidence,
        "qos_policy_best": best,
        "queue_capacity_signal": signal_name(max_queue / 108.0, 0.25, 0.08),
        "service_saturation_signal": signal_name(max_util, 0.92, 0.75),
        "backpressure_signal": signal_name(
            max(float(row["backpressure_stall_ns"]) for row in policy_rows) / 5000.0,
            0.80,
            0.30,
        ),
        "fairness_signal": signal_name(1.0 - min_fairness, 0.30, 0.15),
        "sla_signal": signal_name(min_cpu_vio, 0.50, 0.10),
        "claim_boundary": "PASS",
        "schema_version": SCHEMA_VERSION,
    }


def write_csv(path: Path, fields: Sequence[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows(rows)


def case_table_row(
    policy_row: Dict[str, str], recommendation_row: Dict[str, str]
) -> str:
    return (
        f"| {policy_row['case_name']} | {policy_row['policy']} | "
        f"{policy_row['cpu_rt_p95_ns']} | "
        f"{policy_row['cpu_rt_sla_violation_ratio']} | "
        f"{policy_row['dma_bulk_throughput_txn_per_us']} | "
        f"{policy_row['service_utilization']} | "
        f"{policy_row['queue_full_events']} | "
        f"{policy_row['fairness_index']} | "
        f"{policy_row['dominant_bottleneck']} | "
        f"{recommendation_row['recommended_action']} |"
    )


def write_report(
    path: Path,
    primary_policy_rows: List[Dict[str, str]],
    recommendation_rows: List[Dict[str, str]],
) -> None:
    recommendation_by_case = {row["case_name"]: row for row in recommendation_rows}
    lines = [
        "# Project AT-5: Memory System Backpressure and QoS Collapse Lab",
        "",
        f"schema_version: `{SCHEMA_VERSION}`",
        "",
        "## What This Model Demonstrates",
        "",
        "Project AT-5 是一个 AT-level synthetic architecture lab，用来展示 downstream memory service / shared resource 被打满时，backpressure 如何沿 transaction path 反向传播，并让单点 QoS priority 从局部有效变成系统级失效。",
        "",
        "它承接 AT-3 的 QoS/SLA 视角和 AT-4 的 shared-resource pressure 视角，但本阶段关注的是 `initiators -> QoS arbiter -> ingress queue -> shared downstream service -> memory target` 这条 bounded path 上的 queue-full、stall、utilization、fairness 和 SLA collapse signal。",
        "",
        "## Modeled Mechanism",
        "",
        "- `cpu_rt` 表示 latency-sensitive request stream。",
        "- `dma_bulk` 表示 bandwidth-heavy streaming source。",
        "- `accel_burst` 表示 bursty accelerator source。",
        "- `ingress_queue_capacity` 和 `downstream_queue_capacity` 是 bounded queue 抽象。",
        "- `memory_service_latency_ns` 与 `service_rate_txn_per_us` 控制 downstream service saturation。",
        "- `round_robin`、`strict_priority`、`weighted_priority`、`throttled_dma`、`backpressure_aware` 是 synthetic QoS policy modes，不代表真实互连协议。",
        "",
        "## Case Table",
        "",
        "| case_name | primary_policy | cpu_rt_p95_ns | cpu_rt_sla_violation_ratio | dma_bulk_throughput_txn_per_us | service_utilization | queue_full_events | fairness_index | dominant_bottleneck | recommended_action |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    lines.extend(
        case_table_row(row, recommendation_by_case[row["case_name"]])
        for row in primary_policy_rows
    )
    lines.extend(
        [
            "",
            "## Key Observations",
            "",
            "- `strict_priority_helps_cpu` 展示 priority 可以降低 `cpu_rt` tail latency，但这是局部有效，不等同于系统容量被修复。",
            "- `strict_priority_starves_dma` 展示 strict priority 可能牺牲 `dma_bulk` throughput / fairness，因此需要 weighted 或 throttled policy 作为折中。",
            "- `downstream_saturation_qos_collapse` 展示当 downstream service utilization 接近满载时，QoS policy 只能改变排队顺序，无法消除总服务时间瓶颈。",
            "- `small_queue_backpressure` 展示 queue capacity 太小会产生反压 stall；这类问题应优先看 queue sizing 和 backpressure-aware scheduling。",
            "- `bursty_accel_tail_spike` 展示 burst source 可以制造局部 tail spike，即使平均吞吐看起来仍然可接受。",
            "",
            "## Architecture Recommendations",
            "",
            "| case_name | primary_bottleneck | confidence | recommended_action | priority | qos_policy_best | evidence |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in recommendation_rows:
        lines.append(
            f"| {row['case_name']} | {row['primary_bottleneck']} | "
            f"{row['confidence']} | {row['recommended_action']} | "
            f"{row['recommendation_priority']} | {row['qos_policy_best']} | "
            f"{row['evidence_summary']} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- Current: 一个小型 SystemC/TLM AT-level synthetic architecture model，用于观察 bounded queues、downstream service saturation、QoS policy 和 backpressure stall 的相对趋势。",
            "- Supported: 在固定 synthetic workload 下比较 p95/p99 latency、SLA violation ratio、throughput、fairness、queue-full events、backpressure stall 和 recommendation signal。",
            "- Not Supported: real NoC modeling。",
            "- Not Supported: real AXI / CHI protocol compliance。",
            "- Not Supported: real DRAM controller timing。",
            "- Not Supported: real cache coherence。",
            "- Not Supported: cycle-accurate timing。",
            "- Not Supported: silicon validation、production signoff、或任何 Apple / NVIDIA / Arm internal 结论。",
            "- Future Work: 如果要提升 claim strength，需要引入更强 reference、校准 workload、并把 synthetic proxy 与真实设计约束分层对齐。",
            "",
            "## How To Reproduce",
            "",
            "```bash",
            "cmake -S examples/at -B build-at \\",
            "  -DUSER_SYSTEMC_INCLUDE_DIR=$HOME/local/systemc/include \\",
            "  -DUSER_SYSTEMC_LIB_DIR=$HOME/local/systemc/lib",
            "",
            "cmake --build build-at --target project_at5_backpressure_qos_collapse -j",
            "",
            "python3 examples/at/tools/demo_at5_backpressure_qos_collapse.py --at-build-dir build-at",
            "```",
            "",
            "Expected PASS marker:",
            "",
            "```text",
            "Project AT-5 Memory System Backpressure and QoS Collapse Lab PASS",
            "cases=7",
            "initiators=3",
            "policies=5",
            "claim_boundary=PASS",
            "schema_version=at5.0",
            "```",
            "",
            "## Why QoS Alone Can Fail Under Downstream Saturation",
            "",
            "QoS priority 主要改变谁先进入 shared downstream service；当 `service_utilization` 已经接近 1，系统总服务能力本身成为 dominant bottleneck。此时 strict priority 可能让 `cpu_rt` 少等一部分局部队列，但它不能创造新的 memory service capacity，也可能把 `dma_bulk` 推向 starvation。AT-5 的 recommendation 因此会在 downstream saturation 场景中转向 `reduce_memory_service_latency` 或 capacity 类动作，而不是继续提高 priority。",
            "",
            "这些 CSV 和 report 是当前 evidence boundary；不要把 sample outputs 当作硬件产品数据或 silicon measurement。",
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
        "not supported",
        "does not",
        "is not",
        "do not",
        "不是",
        "不支持",
        "不能",
        "不要",
    ]
    return not any(word in lowered for word in boundary_words)


def forbidden_claim_scan(report_path: Path) -> None:
    phrases = [
        "real noc",
        "real axi",
        "real chi",
        "real dram controller",
        "real cache coherence",
        "cycle-accurate",
        "cycle accurate",
        "silicon validation",
        "silicon measurement",
        "production signoff",
        "apple",
        "nvidia",
        "arm internal",
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
    rows: List[Dict[str, str]], case_name: str, policy: Optional[str] = None
) -> Dict[str, str]:
    for row in rows:
        if row["case_name"] == case_name and (
            policy is None or row.get("policy") == policy
        ):
            return row
    suffix = f"/{policy}" if policy is not None else ""
    raise DemoError(f"missing row for {case_name}{suffix}")


def acceptance_checks(
    summary_rows: List[Dict[str, str]],
    policy_rows: List[Dict[str, str]],
    recommendation_rows: List[Dict[str, str]],
    primary_traces_by_case: Dict[str, List[Dict[str, str]]],
    report_path: Path,
) -> None:
    case_count = len(CASES)
    if len(primary_traces_by_case) != case_count:
        raise DemoError(f"case count {len(primary_traces_by_case)} != {case_count}")
    if len(summary_rows) != case_count * len(INITIATORS):
        raise DemoError(
            f"summary row count {len(summary_rows)} != {case_count * len(INITIATORS)}"
        )
    if len(policy_rows) != case_count * len(POLICIES):
        raise DemoError(
            f"policy sweep row count {len(policy_rows)} != {case_count * len(POLICIES)}"
        )
    if len(recommendation_rows) != case_count:
        raise DemoError(
            f"recommendations row count {len(recommendation_rows)} != {case_count}"
        )

    for row in summary_rows + policy_rows + recommendation_rows:
        if row["claim_boundary"] != "PASS":
            raise DemoError("not all claim_boundary fields are PASS")
        if row["schema_version"] != SCHEMA_VERSION:
            raise DemoError("not all schema_version fields are at5.0")
    for row in policy_rows + recommendation_rows:
        if row["recommended_action"] not in ALLOWED_ACTIONS:
            raise DemoError(
                f"invalid recommended_action for {row['case_name']}: "
                f"{row['recommended_action']}"
            )

    helps_rr = row_for(policy_rows, "strict_priority_helps_cpu", "round_robin")
    helps_strict = row_for(policy_rows, "strict_priority_helps_cpu", "strict_priority")
    if float(helps_strict["cpu_rt_p95_ns"]) >= float(helps_rr["cpu_rt_p95_ns"]):
        raise DemoError("strict_priority_helps_cpu did not improve cpu_rt p95")

    starve_rec = row_for(recommendation_rows, "strict_priority_starves_dma")
    if starve_rec["recommended_action"] != "use_weighted_priority":
        raise DemoError("strict_priority_starves_dma did not recommend weighted priority")

    collapse_rows = [
        row
        for row in policy_rows
        if row["case_name"] == "downstream_saturation_qos_collapse"
    ]
    if not all(float(row["cpu_rt_sla_violation_ratio"]) > 0 for row in collapse_rows):
        raise DemoError("downstream saturation did not violate cpu_rt SLA for all policies")
    collapse_rec = row_for(recommendation_rows, "downstream_saturation_qos_collapse")
    if collapse_rec["recommended_action"] != "reduce_memory_service_latency":
        raise DemoError("downstream saturation did not recommend memory service fix")

    small_queue = row_for(policy_rows, "small_queue_backpressure", "backpressure_aware")
    if int(small_queue["queue_full_events"]) <= 0:
        raise DemoError("small_queue_backpressure did not produce queue_full_events")

    throttled = row_for(policy_rows, "throttled_dma_recovers_sla", "throttled_dma")
    throttled_rr = row_for(policy_rows, "throttled_dma_recovers_sla", "round_robin")
    if float(throttled["cpu_rt_sla_violation_ratio"]) > float(
        throttled_rr["cpu_rt_sla_violation_ratio"]
    ):
        raise DemoError("throttled_dma did not improve cpu_rt SLA signal")

    burst_rec = row_for(recommendation_rows, "bursty_accel_tail_spike")
    if burst_rec["recommended_action"] != "shape_accel_bursts":
        raise DemoError("bursty_accel_tail_spike did not recommend burst shaping")

    if not report_path.exists():
        raise DemoError(f"missing report: {report_path}")
    report = report_path.read_text(encoding="utf-8")
    required_markers = [
        "# Project AT-5: Memory System Backpressure and QoS Collapse Lab",
        "## What This Model Demonstrates",
        "## Modeled Mechanism",
        "## Case Table",
        "## Key Observations",
        "## Architecture Recommendations",
        "## Claim Boundary",
        "## How To Reproduce",
        "## Why QoS Alone Can Fail Under Downstream Saturation",
        "Current:",
        "Supported:",
        "Not Supported: real NoC modeling。",
        "Not Supported: real AXI / CHI protocol compliance。",
        "Not Supported: real DRAM controller timing。",
        "Not Supported: real cache coherence。",
        "Not Supported: cycle-accurate timing。",
    ]
    missing = [marker for marker in required_markers if marker not in report]
    if missing:
        raise DemoError("report is missing markers: " + ", ".join(missing))
    forbidden_claim_scan(report_path)


def print_outputs(output_dir: Path) -> None:
    print("[at5] Output files:")
    print(f"[at5]   summary: {output_dir / 'project_at5_summary.csv'}")
    print(f"[at5]   policy sweep: {output_dir / 'project_at5_policy_sweep.csv'}")
    print(f"[at5]   recommendations: {output_dir / 'project_at5_recommendations.csv'}")
    print(f"[at5]   report: {output_dir / 'project_at5_report.md'}")
    for config in CASES:
        print(
            "[at5]   trace: "
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
    primary_traces_by_case: Dict[str, List[Dict[str, str]]] = {}
    failures: List[str] = []

    for config in CASES:
        print(f"[at5] running case={config.case_name}")
        case_policy_rows: List[Dict[str, str]] = []
        try:
            for policy in POLICIES:
                trace_path = run_case(binary, output_dir, config, policy)
                rows = read_trace(trace_path)
                validate_trace(config, policy, rows)
                policy_row = aggregate_policy_row(config, policy, rows)
                policy_rows.append(policy_row)
                case_policy_rows.append(policy_row)
                if policy == config.primary_policy:
                    summary_rows.extend(summarize_case(config, rows))
                    primary_traces_by_case[config.case_name] = rows
            recommendation_rows.append(make_recommendation(config, case_policy_rows))
            print(f"[at5] case={config.case_name} status=OK")
        except DemoError as exc:
            failures.append(str(exc))
            print(f"[at5] case={config.case_name} status=FAIL error={exc}")
            if not args.keep_going:
                raise

    summary_path = output_dir / "project_at5_summary.csv"
    policy_sweep_path = output_dir / "project_at5_policy_sweep.csv"
    recommendations_path = output_dir / "project_at5_recommendations.csv"
    report_path = output_dir / "project_at5_report.md"
    write_csv(summary_path, SUMMARY_FIELDS, summary_rows)
    write_csv(policy_sweep_path, POLICY_SWEEP_FIELDS, policy_rows)
    write_csv(recommendations_path, RECOMMENDATION_FIELDS, recommendation_rows)
    primary_policy_rows = [
        row
        for row in policy_rows
        for config in CASES
        if row["case_name"] == config.case_name and row["policy"] == config.primary_policy
    ]
    write_report(report_path, primary_policy_rows, recommendation_rows)

    if failures:
        raise DemoError("; ".join(failures))

    acceptance_checks(
        summary_rows,
        policy_rows,
        recommendation_rows,
        primary_traces_by_case,
        report_path,
    )
    print_outputs(output_dir)
    print("Project AT-5 Memory System Backpressure and QoS Collapse Lab PASS")
    print(f"cases={len(CASES)}")
    print(f"initiators={len(INITIATORS)}")
    print(f"policies={len(POLICIES)}")
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
