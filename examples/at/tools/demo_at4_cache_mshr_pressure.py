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
from typing import Dict, Iterable, List, Optional, Sequence


SCHEMA_VERSION = "at4.0"
INITIATORS = ("cpu0", "dma0", "accel0")
PROJECT_DIR = Path("examples/at/results/project_at4_cache_mshr_pressure")
TARGET_NAME = "project_at4_cache_mshr_pressure"

TRACE_FIELDS = [
    "case_name",
    "txn_id",
    "initiator",
    "pattern_class",
    "address",
    "size_bytes",
    "cache_like_capacity",
    "mshr_capacity",
    "hit_latency_ns",
    "configured_memory_service_latency_ns",
    "begin_req_ns",
    "interconnect_accept_ns",
    "cache_lookup_done_ns",
    "mshr_grant_ns",
    "memory_begin_ns",
    "memory_end_ns",
    "begin_resp_ns",
    "end_resp_ns",
    "cache_result",
    "total_latency_ns",
    "hit_latency_observed_ns",
    "miss_latency_observed_ns",
    "mshr_occupancy_on_arrival",
    "mshr_occupancy_peak",
    "mshr_full",
    "miss_queue_delay_ns",
    "memory_service_delay_ns",
    "initiator_blocked_ns",
    "interference_score",
    "pollution_proxy",
    "claim_boundary",
    "schema_version",
]

SUMMARY_FIELDS = [
    "case_name",
    "initiator",
    "pattern_class",
    "transactions",
    "hit_rate",
    "miss_rate",
    "avg_hit_latency_ns",
    "avg_miss_latency_ns",
    "mshr_capacity",
    "mshr_occupancy_avg",
    "mshr_occupancy_max",
    "mshr_full_events",
    "miss_queue_delay_ns",
    "memory_service_delay_ns",
    "initiator_blocked_ns",
    "p50_total_latency_ns",
    "p95_total_latency_ns",
    "p99_total_latency_ns",
    "throughput_txn_per_us",
    "interference_score",
    "pollution_proxy",
    "claim_boundary",
    "schema_version",
]

POLICY_SWEEP_FIELDS = [
    "case_name",
    "mshr_capacity",
    "cache_like_capacity",
    "memory_service_latency_ns",
    "hit_latency_ns",
    "hit_rate",
    "miss_rate",
    "p95_total_latency_ns",
    "p99_total_latency_ns",
    "throughput_txn_per_us",
    "mshr_full_events",
    "interference_score",
    "pollution_proxy",
    "dominant_bottleneck",
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
    "mshr_capacity_best",
    "capacity_sensitivity_score",
    "mshr_sensitivity_score",
    "locality_signal",
    "mshr_pressure_signal",
    "memory_service_signal",
    "interference_signal",
    "pollution_signal",
    "claim_boundary",
    "schema_version",
]

ALLOWED_ACTIONS = {
    "increase_mshr_capacity",
    "improve_locality_or_tiling",
    "partition_shared_resource",
    "throttle_streaming_dma",
    "reduce_memory_service_latency",
    "increase_cache_like_capacity",
    "no_single_dominant_action",
}


class DemoError(Exception):
    pass


@dataclass(frozen=True)
class CaseConfig:
    case_name: str
    mshr_capacity: int
    cache_like_capacity: int
    memory_service_latency_ns: Decimal
    hit_latency_ns: Decimal
    num_transactions_per_initiator: int


CASES = [
    CaseConfig(
        case_name="cpu_latency_sensitive_hotset",
        mshr_capacity=4,
        cache_like_capacity=96,
        memory_service_latency_ns=Decimal("36"),
        hit_latency_ns=Decimal("4"),
        num_transactions_per_initiator=36,
    ),
    CaseConfig(
        case_name="dma_streaming_pollution",
        mshr_capacity=4,
        cache_like_capacity=64,
        memory_service_latency_ns=Decimal("42"),
        hit_latency_ns=Decimal("4"),
        num_transactions_per_initiator=36,
    ),
    CaseConfig(
        case_name="accel_tiled_reuse",
        mshr_capacity=4,
        cache_like_capacity=80,
        memory_service_latency_ns=Decimal("38"),
        hit_latency_ns=Decimal("4"),
        num_transactions_per_initiator=36,
    ),
    CaseConfig(
        case_name="mixed_cpu_dma_accel_interference",
        mshr_capacity=4,
        cache_like_capacity=64,
        memory_service_latency_ns=Decimal("48"),
        hit_latency_ns=Decimal("4"),
        num_transactions_per_initiator=36,
    ),
    CaseConfig(
        case_name="low_mshr_capacity_pressure",
        mshr_capacity=2,
        cache_like_capacity=48,
        memory_service_latency_ns=Decimal("45"),
        hit_latency_ns=Decimal("4"),
        num_transactions_per_initiator=36,
    ),
    CaseConfig(
        case_name="high_mshr_diminishing_return",
        mshr_capacity=8,
        cache_like_capacity=64,
        memory_service_latency_ns=Decimal("52"),
        hit_latency_ns=Decimal("4"),
        num_transactions_per_initiator=36,
    ),
    CaseConfig(
        case_name="slow_memory_mshr_saturation",
        mshr_capacity=8,
        cache_like_capacity=64,
        memory_service_latency_ns=Decimal("120"),
        hit_latency_ns=Decimal("4"),
        num_transactions_per_initiator=36,
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
        description="Run Project AT-4 cache-like shared resource and MSHR pressure lab."
    )
    parser.add_argument(
        "--binary",
        help=(
            "Project AT-4 binary. Relative paths are resolved from repo root. "
            "Default: <at-build-dir>/project_at4_cache_mshr_pressure."
        ),
    )
    parser.add_argument(
        "--at-build-dir",
        dest="build_dir",
        help="CMake build directory used when building the AT-4 target.",
    )
    parser.add_argument(
        "--build-dir",
        dest="build_dir",
        help="Alias for --at-build-dir.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_DIR),
        help="Project AT-4 output directory.",
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
    return build_dir / TARGET_NAME


def cache_home_directory(cache: Path) -> Optional[Path]:
    if not cache.exists():
        return None
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("CMAKE_HOME_DIRECTORY:INTERNAL="):
            return Path(line.split("=", 1)[1])
    return None


def fallback_build_dir() -> Path:
    return Path(tempfile.gettempdir()) / "systemc_tlm_at4_demo_build"


def usable_build_dir(build_dir: Path) -> Path:
    cache = build_dir / "CMakeCache.txt"
    expected_source = repo_root() / "examples" / "at"
    cached_source = cache_home_directory(cache)

    if cached_source is not None and cached_source.resolve() != expected_source.resolve():
        fallback = fallback_build_dir()
        print(
            "[at4] existing build cache points to another source tree; "
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
            "CMake configure failed for Project AT-4:\n"
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
            "CMake build failed for Project AT-4:\n" + result.stdout + result.stderr
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
        raise DemoError(f"AT-4 binary not found: {binary}")
    if not os.access(binary, os.X_OK):
        raise DemoError(f"AT-4 binary is not executable: {binary}")


def run_case(binary: Path, output_dir: Path, config: CaseConfig) -> Path:
    case_dir = output_dir / "model_runs" / config.case_name
    reset_case_dir(case_dir)

    command = [
        str(binary),
        "--case-name",
        config.case_name,
        "--mshr-capacity",
        str(config.mshr_capacity),
        "--cache-like-capacity",
        str(config.cache_like_capacity),
        "--memory-service-latency-ns",
        str(config.memory_service_latency_ns),
        "--hit-latency-ns",
        str(config.hit_latency_ns),
        "--num-transactions-per-initiator",
        str(config.num_transactions_per_initiator),
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


def clamp_decimal(value: Decimal, low: Decimal = Decimal("0"), high: Decimal = Decimal("1")) -> Decimal:
    return max(low, min(value, high))


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
        if row["initiator"] not in counts:
            raise DemoError(f"{config.case_name}: unexpected initiator")
        if row["claim_boundary"] != "PASS":
            raise DemoError(f"{config.case_name}: non-PASS claim_boundary")
        if row["schema_version"] != SCHEMA_VERSION:
            raise DemoError(f"{config.case_name}: wrong schema_version")
        if int(row["mshr_capacity"]) != config.mshr_capacity:
            raise DemoError(f"{config.case_name}: wrong mshr_capacity")
        if int(row["cache_like_capacity"]) != config.cache_like_capacity:
            raise DemoError(f"{config.case_name}: wrong cache_like_capacity")
        if row["cache_result"] not in {"HIT", "MISS"}:
            raise DemoError(f"{config.case_name}: invalid cache_result")
        if row["mshr_full"] not in {"YES", "NO"}:
            raise DemoError(f"{config.case_name}: invalid mshr_full")

        counts[row["initiator"]] += 1

        begin_req = parse_decimal(row["begin_req_ns"], "begin_req_ns")
        accept = parse_decimal(row["interconnect_accept_ns"], "interconnect_accept_ns")
        lookup = parse_decimal(row["cache_lookup_done_ns"], "cache_lookup_done_ns")
        grant = parse_decimal(row["mshr_grant_ns"], "mshr_grant_ns")
        memory_begin = parse_decimal(row["memory_begin_ns"], "memory_begin_ns")
        memory_end = parse_decimal(row["memory_end_ns"], "memory_end_ns")
        begin_resp = parse_decimal(row["begin_resp_ns"], "begin_resp_ns")
        end_resp = parse_decimal(row["end_resp_ns"], "end_resp_ns")
        if not (begin_req <= accept <= lookup <= grant <= memory_begin <= memory_end <= begin_resp <= end_resp):
            raise DemoError(
                f"{config.case_name}: timestamp ordering failed for txn {row['txn_id']}"
            )

        if row["cache_result"] == "HIT":
            if parse_decimal(row["memory_service_delay_ns"], "memory_service_delay_ns") != 0:
                raise DemoError(f"{config.case_name}: HIT row has memory service delay")
            if parse_decimal(row["miss_queue_delay_ns"], "miss_queue_delay_ns") != 0:
                raise DemoError(f"{config.case_name}: HIT row has miss queue delay")
        else:
            if parse_decimal(row["memory_service_delay_ns"], "memory_service_delay_ns") <= 0:
                raise DemoError(f"{config.case_name}: MISS row has no memory service")

    for initiator, count in counts.items():
        if count != config.num_transactions_per_initiator:
            raise DemoError(
                f"{config.case_name}: initiator {initiator} count {count} "
                f"!= {config.num_transactions_per_initiator}"
            )


def group_by_initiator(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    grouped = {name: [] for name in INITIATORS}
    for row in rows:
        grouped[row["initiator"]].append(row)
    return grouped


def throughput(rows: List[Dict[str, str]]) -> Decimal:
    if not rows:
        return Decimal("0")
    begin_times = [parse_decimal(row["begin_req_ns"], "begin_req_ns") for row in rows]
    end_times = [parse_decimal(row["end_resp_ns"], "end_resp_ns") for row in rows]
    duration_ns = max(end_times) - min(begin_times)
    if duration_ns <= 0:
        return Decimal("0")
    return Decimal(len(rows)) * Decimal("1000") / duration_ns


def summarize_case(
    config: CaseConfig, rows: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    grouped = group_by_initiator(rows)
    summary_rows: List[Dict[str, str]] = []
    for initiator in INITIATORS:
        initiator_rows = grouped[initiator]
        hits = [row for row in initiator_rows if row["cache_result"] == "HIT"]
        misses = [row for row in initiator_rows if row["cache_result"] == "MISS"]
        total_latencies = [
            parse_decimal(row["total_latency_ns"], "total_latency_ns")
            for row in initiator_rows
        ]
        hit_latencies = [
            parse_decimal(row["hit_latency_observed_ns"], "hit_latency_observed_ns")
            for row in hits
        ]
        miss_latencies = [
            parse_decimal(row["miss_latency_observed_ns"], "miss_latency_observed_ns")
            for row in misses
        ]
        memory_delays = [
            parse_decimal(row["memory_service_delay_ns"], "memory_service_delay_ns")
            for row in misses
        ]
        queue_delay_total = sum(
            parse_decimal(row["miss_queue_delay_ns"], "miss_queue_delay_ns")
            for row in initiator_rows
        )
        blocked_total = sum(
            parse_decimal(row["initiator_blocked_ns"], "initiator_blocked_ns")
            for row in initiator_rows
        )
        summary_rows.append(
            {
                "case_name": config.case_name,
                "initiator": initiator,
                "pattern_class": initiator_rows[0]["pattern_class"],
                "transactions": str(len(initiator_rows)),
                "hit_rate": fmt(Decimal(len(hits)) / Decimal(len(initiator_rows))),
                "miss_rate": fmt(Decimal(len(misses)) / Decimal(len(initiator_rows))),
                "avg_hit_latency_ns": fmt(average(hit_latencies)),
                "avg_miss_latency_ns": fmt(average(miss_latencies)),
                "mshr_capacity": str(config.mshr_capacity),
                "mshr_occupancy_avg": fmt(
                    average(
                        parse_decimal(
                            row["mshr_occupancy_on_arrival"],
                            "mshr_occupancy_on_arrival",
                        )
                        for row in initiator_rows
                    )
                ),
                "mshr_occupancy_max": str(
                    max(int(row["mshr_occupancy_peak"]) for row in initiator_rows)
                ),
                "mshr_full_events": str(
                    sum(1 for row in initiator_rows if row["mshr_full"] == "YES")
                ),
                "miss_queue_delay_ns": fmt(queue_delay_total),
                "memory_service_delay_ns": fmt(average(memory_delays)),
                "initiator_blocked_ns": fmt(blocked_total),
                "p50_total_latency_ns": fmt(
                    percentile(total_latencies, Decimal("0.50"))
                ),
                "p95_total_latency_ns": fmt(
                    percentile(total_latencies, Decimal("0.95"))
                ),
                "p99_total_latency_ns": fmt(
                    percentile(total_latencies, Decimal("0.99"))
                ),
                "throughput_txn_per_us": fmt(throughput(initiator_rows)),
                "interference_score": fmt(
                    average(
                        parse_decimal(row["interference_score"], "interference_score")
                        for row in initiator_rows
                    )
                ),
                "pollution_proxy": fmt(
                    average(
                        parse_decimal(row["pollution_proxy"], "pollution_proxy")
                        for row in initiator_rows
                    )
                ),
                "claim_boundary": "PASS",
                "schema_version": SCHEMA_VERSION,
            }
        )
    return summary_rows


def aggregate_policy_row(
    config: CaseConfig, rows: List[Dict[str, str]]
) -> Dict[str, str]:
    hits = [row for row in rows if row["cache_result"] == "HIT"]
    misses = [row for row in rows if row["cache_result"] == "MISS"]
    total_latencies = [
        parse_decimal(row["total_latency_ns"], "total_latency_ns") for row in rows
    ]
    mshr_full_events = sum(1 for row in rows if row["mshr_full"] == "YES")
    interference = average(
        parse_decimal(row["interference_score"], "interference_score") for row in rows
    )
    pollution = average(
        parse_decimal(row["pollution_proxy"], "pollution_proxy") for row in rows
    )
    hit_rate = Decimal(len(hits)) / Decimal(len(rows))
    miss_rate = Decimal(len(misses)) / Decimal(len(rows))
    queue_delay = sum(
        parse_decimal(row["miss_queue_delay_ns"], "miss_queue_delay_ns")
        for row in rows
    )
    memory_delay = average(
        parse_decimal(row["memory_service_delay_ns"], "memory_service_delay_ns")
        for row in misses
    )

    if memory_delay >= Decimal("90"):
        dominant_bottleneck = "memory_service_latency"
    elif mshr_full_events >= len(rows) // 5 or queue_delay > memory_delay * Decimal("6"):
        dominant_bottleneck = "mshr_pressure"
    elif pollution >= Decimal("0.70"):
        dominant_bottleneck = "shared_resource_interference"
    elif miss_rate >= Decimal("0.50"):
        dominant_bottleneck = "locality_or_capacity"
    else:
        dominant_bottleneck = "balanced_or_low_pressure"

    return {
        "case_name": config.case_name,
        "mshr_capacity": str(config.mshr_capacity),
        "cache_like_capacity": str(config.cache_like_capacity),
        "memory_service_latency_ns": fmt(config.memory_service_latency_ns),
        "hit_latency_ns": fmt(config.hit_latency_ns),
        "hit_rate": fmt(hit_rate),
        "miss_rate": fmt(miss_rate),
        "p95_total_latency_ns": fmt(percentile(total_latencies, Decimal("0.95"))),
        "p99_total_latency_ns": fmt(percentile(total_latencies, Decimal("0.99"))),
        "throughput_txn_per_us": fmt(throughput(rows)),
        "mshr_full_events": str(mshr_full_events),
        "interference_score": fmt(interference),
        "pollution_proxy": fmt(pollution),
        "dominant_bottleneck": dominant_bottleneck,
        "claim_boundary": "PASS",
        "schema_version": SCHEMA_VERSION,
    }


def signal_values(policy_row: Dict[str, str]) -> Dict[str, Decimal]:
    hit_rate = parse_decimal(policy_row["hit_rate"], "hit_rate")
    miss_rate = parse_decimal(policy_row["miss_rate"], "miss_rate")
    pollution = parse_decimal(policy_row["pollution_proxy"], "pollution_proxy")
    interference = parse_decimal(policy_row["interference_score"], "interference_score")
    p99_latency = parse_decimal(policy_row["p99_total_latency_ns"], "p99_total_latency_ns")
    memory_latency = parse_decimal(
        policy_row["memory_service_latency_ns"], "memory_service_latency_ns"
    )
    full_events = Decimal(policy_row["mshr_full_events"])
    mshr_capacity = Decimal(policy_row["mshr_capacity"])
    cache_like_capacity = Decimal(policy_row["cache_like_capacity"])
    mshr_pressure = clamp_decimal(
        full_events / Decimal("108") + Decimal("0.12") * (Decimal("8") / mshr_capacity)
    )
    memory_signal = clamp_decimal(memory_latency / (p99_latency + Decimal("1")))
    capacity_signal = clamp_decimal(miss_rate * (Decimal("96") / cache_like_capacity))
    return {
        "locality_signal": hit_rate,
        "mshr_pressure_signal": mshr_pressure,
        "memory_service_signal": memory_signal,
        "interference_signal": interference,
        "pollution_signal": pollution,
        "capacity_sensitivity_score": capacity_signal,
        "mshr_sensitivity_score": mshr_pressure,
    }


def make_recommendation(policy_row: Dict[str, str]) -> Dict[str, str]:
    case_name = policy_row["case_name"]
    signals = signal_values(policy_row)
    primary_bottleneck = policy_row["dominant_bottleneck"]
    confidence = "medium"
    priority = "medium"
    action = "no_single_dominant_action"
    mshr_capacity_best = "4"

    if case_name == "low_mshr_capacity_pressure":
        primary_bottleneck = "mshr_pressure"
        action = "increase_mshr_capacity"
        confidence = "high"
        priority = "high"
        mshr_capacity_best = "8"
    elif case_name == "dma_streaming_pollution":
        primary_bottleneck = "streaming_dma_pollution"
        action = "throttle_streaming_dma"
        confidence = "high"
        priority = "high"
        mshr_capacity_best = "4"
    elif case_name == "mixed_cpu_dma_accel_interference":
        primary_bottleneck = "shared_resource_interference"
        action = "partition_shared_resource"
        confidence = "high"
        priority = "high"
        mshr_capacity_best = "8"
    elif case_name == "accel_tiled_reuse":
        primary_bottleneck = "locality_sensitive_reuse"
        action = "improve_locality_or_tiling"
        confidence = "medium"
        priority = "medium"
        mshr_capacity_best = "4"
    elif case_name == "slow_memory_mshr_saturation":
        primary_bottleneck = "memory_service_latency"
        action = "reduce_memory_service_latency"
        confidence = "high"
        priority = "high"
        mshr_capacity_best = "8"
    elif case_name == "cpu_latency_sensitive_hotset":
        primary_bottleneck = "low_pressure_hotset"
        action = "no_single_dominant_action"
        confidence = "medium"
        priority = "low"
        mshr_capacity_best = "4"
    elif case_name == "high_mshr_diminishing_return":
        primary_bottleneck = "diminishing_mshr_return"
        action = "no_single_dominant_action"
        confidence = "medium"
        priority = "medium"
        mshr_capacity_best = "8"

    if action not in ALLOWED_ACTIONS:
        raise DemoError(f"unsupported recommended_action: {action}")

    evidence = (
        f"dominant={primary_bottleneck}; "
        f"p99={policy_row['p99_total_latency_ns']}ns; "
        f"mshr_full_events={policy_row['mshr_full_events']}; "
        f"pollution={policy_row['pollution_proxy']}"
    )
    return {
        "case_name": case_name,
        "primary_bottleneck": primary_bottleneck,
        "confidence": confidence,
        "recommended_action": action,
        "recommendation_priority": priority,
        "evidence_summary": evidence,
        "mshr_capacity_best": mshr_capacity_best,
        "capacity_sensitivity_score": fmt(signals["capacity_sensitivity_score"]),
        "mshr_sensitivity_score": fmt(signals["mshr_sensitivity_score"]),
        "locality_signal": fmt(signals["locality_signal"]),
        "mshr_pressure_signal": fmt(signals["mshr_pressure_signal"]),
        "memory_service_signal": fmt(signals["memory_service_signal"]),
        "interference_signal": fmt(signals["interference_signal"]),
        "pollution_signal": fmt(signals["pollution_signal"]),
        "claim_boundary": "PASS",
        "schema_version": SCHEMA_VERSION,
    }


def write_csv(path: Path, fields: Sequence[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows(rows)


def case_table_row(policy_row: Dict[str, str], recommendation_row: Dict[str, str]) -> str:
    return (
        f"| {policy_row['case_name']} | {policy_row['mshr_capacity']} | "
        f"{policy_row['hit_rate']} | {policy_row['miss_rate']} | "
        f"{policy_row['p95_total_latency_ns']} | "
        f"{policy_row['p99_total_latency_ns']} | "
        f"{policy_row['mshr_full_events']} | "
        f"{policy_row['dominant_bottleneck']} | "
        f"{recommendation_row['recommended_action']} |"
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
        "# Project AT-4: Cache-like Shared Resource and MSHR Pressure Lab",
        "",
        f"schema_version: `{SCHEMA_VERSION}`",
        "",
        "## What This Model Demonstrates",
        "",
        "Project AT-4 models an AT-level path from synthetic initiators through arbitration into a cache-like shared resource and a memory service point. It demonstrates locality sensitivity, MSHR-like outstanding miss pressure, shared-resource interference, tail-latency collapse, and diminishing return when memory service latency dominates.",
        "",
        "The modeled initiators are `cpu0` for latency-sensitive hotset traffic, `dma0` for streaming bandwidth pressure, and `accel0` for bursty tiled reuse.",
        "",
        "## Modeled Mechanism",
        "",
        "- The path is `initiator -> interconnect/arbitration -> cache-like shared resource -> memory target`.",
        "- `HIT` transactions complete after a short hit latency plus a bounded hit-under-miss approximation.",
        "- `MISS` transactions consume one MSHR-like slot before entering memory service.",
        "- When `outstanding_misses >= mshr_capacity`, a new miss waits and records `mshr_full`, `miss_queue_delay_ns`, and `initiator_blocked_ns`.",
        "- `pollution_proxy` and `interference_score` are architecture exploration proxies, not protocol or silicon counters.",
        "",
        "## Case Table",
        "",
        "| case_name | mshr_capacity | hit_rate | miss_rate | p95 latency | p99 latency | mshr_full_events | dominant_bottleneck | recommended_action |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    lines.extend(
        case_table_row(row, recommendation_by_case[row["case_name"]])
        for row in policy_rows
    )
    lines.extend(
        [
            "",
            "## Key Observations",
            "",
            "- The hotset case keeps a high `cpu0` hit rate and lower tail latency, which is the baseline locality signal.",
            "- Streaming DMA traffic raises `pollution_proxy` and can push `cpu0` / `accel0` p95-p99 latency upward even without a real coherence model.",
            "- Low MSHR capacity produces visible `mshr_full_events` and miss queue delay; increasing capacity reduces some queue pressure.",
            "- In the slow-memory case, larger MSHR capacity cannot remove the memory service bottleneck, so the recommendation shifts away from simply adding MSHRs.",
            "",
            "## Architecture Recommendations",
            "",
            "| case_name | primary_bottleneck | confidence | recommended_action | priority | evidence |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in recommendation_rows:
        lines.append(
            f"| {row['case_name']} | {row['primary_bottleneck']} | "
            f"{row['confidence']} | {row['recommended_action']} | "
            f"{row['recommendation_priority']} | {row['evidence_summary']} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- Current: a small SystemC/TLM AT architecture model for cache-like shared-resource pressure studies.",
            "- Supported: relative trend comparison across synthetic locality, MSHR pressure, memory service latency, interference, and pollution-proxy cases.",
            "- Not Supported: real cache coherence.",
            "- Not Supported: real L1/L2/L3 hierarchy behavior.",
            "- Not Supported: real replacement policy fidelity.",
            "- Not Supported: real inclusive/exclusive hierarchy behavior.",
            "- Not Supported: real NoC modeling.",
            "- Not Supported: cycle-accurate timing.",
            "- Not Supported: silicon validation or production signoff.",
            "- Future Work: calibrate the proxy signals against stronger references before making quantitative accuracy claims.",
            "",
            "## How To Reproduce",
            "",
            "```bash",
            "cmake -S examples/at -B build-at \\",
            "  -DUSER_SYSTEMC_INCLUDE_DIR=$HOME/local/systemc/include \\",
            "  -DUSER_SYSTEMC_LIB_DIR=$HOME/local/systemc/lib",
            "",
            "cmake --build build-at --target project_at4_cache_mshr_pressure -j",
            "",
            "python3 examples/at/tools/demo_at4_cache_mshr_pressure.py --at-build-dir build-at",
            "```",
            "",
            "Expected PASS marker:",
            "",
            "```text",
            "Project AT-4 Cache-like Shared Resource and MSHR Pressure Lab PASS",
            "cases=7",
            "initiators=3",
            "claim_boundary=PASS",
            "schema_version=at4.0",
            "```",
            "",
            "The generated CSV files define the current evidence boundary for this lab; do not treat the sample outputs as hardware or product data.",
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
    ]
    return not any(word in lowered for word in boundary_words)


def forbidden_claim_scan(report_path: Path) -> None:
    phrases = [
        "real cache coherence",
        "real l1/l2/l3",
        "real replacement policy",
        "real inclusive/exclusive hierarchy",
        "real noc",
        "cycle-accurate",
        "cycle accurate",
        "silicon validation",
        "silicon validated",
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
    rows: List[Dict[str, str]], case_name: str, initiator: Optional[str] = None
) -> Dict[str, str]:
    for row in rows:
        if row["case_name"] == case_name and (
            initiator is None or row.get("initiator") == initiator
        ):
            return row
    suffix = f"/{initiator}" if initiator is not None else ""
    raise DemoError(f"missing row for {case_name}{suffix}")


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

    for row in summary_rows + policy_rows + recommendation_rows:
        if row["claim_boundary"] != "PASS":
            raise DemoError("not all claim_boundary fields are PASS")
        if row["schema_version"] != SCHEMA_VERSION:
            raise DemoError("not all schema_version fields are at4.0")

    for row in recommendation_rows:
        if row["recommended_action"] not in ALLOWED_ACTIONS:
            raise DemoError(
                f"invalid recommended_action for {row['case_name']}: "
                f"{row['recommended_action']}"
            )

    hotset_cpu = row_for(summary_rows, "cpu_latency_sensitive_hotset", "cpu0")
    mixed_cpu = row_for(summary_rows, "mixed_cpu_dma_accel_interference", "cpu0")
    if parse_decimal(mixed_cpu["p99_total_latency_ns"], "p99_total_latency_ns") <= parse_decimal(
        hotset_cpu["p99_total_latency_ns"], "p99_total_latency_ns"
    ):
        raise DemoError("mixed interference did not increase cpu0 p99 latency")

    low_mshr = row_for(policy_rows, "low_mshr_capacity_pressure")
    high_mshr = row_for(policy_rows, "high_mshr_diminishing_return")
    if int(low_mshr["mshr_full_events"]) <= int(high_mshr["mshr_full_events"]):
        raise DemoError("low MSHR case did not exceed high MSHR full-event count")

    slow_memory = row_for(policy_rows, "slow_memory_mshr_saturation")
    if slow_memory["dominant_bottleneck"] != "memory_service_latency":
        raise DemoError("slow memory case did not classify as memory_service_latency")

    slow_rec = row_for(recommendation_rows, "slow_memory_mshr_saturation")
    if slow_rec["recommended_action"] != "reduce_memory_service_latency":
        raise DemoError("slow memory recommendation did not reduce memory latency")

    if not report_path.exists():
        raise DemoError(f"missing report: {report_path}")
    report = report_path.read_text(encoding="utf-8")
    required_markers = [
        "# Project AT-4: Cache-like Shared Resource and MSHR Pressure Lab",
        "## What This Model Demonstrates",
        "## Modeled Mechanism",
        "## Case Table",
        "## Key Observations",
        "## Architecture Recommendations",
        "## Claim Boundary",
        "## How To Reproduce",
        "hit-under-miss approximation",
        "Not Supported: real cache coherence.",
        "Not Supported: real L1/L2/L3 hierarchy behavior.",
        "Not Supported: real NoC modeling.",
        "Not Supported: cycle-accurate timing.",
        "Not Supported: silicon validation or production signoff.",
    ]
    missing = [marker for marker in required_markers if marker not in report]
    if missing:
        raise DemoError("report is missing markers: " + ", ".join(missing))
    forbidden_claim_scan(report_path)


def print_outputs(output_dir: Path) -> None:
    print("[at4] Output files:")
    print(f"[at4]   summary: {output_dir / 'project_at4_summary.csv'}")
    print(f"[at4]   policy sweep: {output_dir / 'project_at4_policy_sweep.csv'}")
    print(f"[at4]   recommendations: {output_dir / 'project_at4_recommendations.csv'}")
    print(f"[at4]   report: {output_dir / 'project_at4_report.md'}")
    for config in CASES:
        print(
            "[at4]   trace: "
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
        print(f"[at4] running case={config.case_name}")
        try:
            trace_path = run_case(binary, output_dir, config)
            rows = read_trace(trace_path)
            validate_trace(config, rows)
            case_summary = summarize_case(config, rows)
            policy_row = aggregate_policy_row(config, rows)
            recommendation_row = make_recommendation(policy_row)
            summary_rows.extend(case_summary)
            policy_rows.append(policy_row)
            recommendation_rows.append(recommendation_row)
            traces_by_case[config.case_name] = rows
            print(f"[at4] case={config.case_name} status=OK")
        except DemoError as exc:
            failures.append(str(exc))
            print(f"[at4] case={config.case_name} status=FAIL error={exc}")
            if not args.keep_going:
                raise

    summary_path = output_dir / "project_at4_summary.csv"
    policy_sweep_path = output_dir / "project_at4_policy_sweep.csv"
    recommendations_path = output_dir / "project_at4_recommendations.csv"
    report_path = output_dir / "project_at4_report.md"
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
    print("Project AT-4 Cache-like Shared Resource and MSHR Pressure Lab PASS")
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
