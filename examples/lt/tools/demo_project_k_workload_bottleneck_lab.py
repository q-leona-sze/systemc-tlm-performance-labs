#!/usr/bin/env python3

import argparse
import csv
import math
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]

CPP_SOURCE_DIR = Path("examples/lt/banked_memory_controller_cpp")
CPP_BUILD_DIR = Path("build/examples/lt/banked_memory_controller_cpp")
DEFAULT_BINARY = CPP_BUILD_DIR / "banked_memory_controller"
DEFAULT_INPUT_DIR = Path("build/examples/lt/project_k_workload_bottleneck_inputs")
DEFAULT_OUTPUT_DIR = Path("examples/lt/results/project_k_workload_bottleneck")
DEFAULT_PROJECT_L_OUTPUT_DIR = Path(
    "examples/lt/results/project_l_memory_architecture_recommendation"
)

CORE_WORKLOADS = ("streaming", "stride", "hot_bank")
OPTIONAL_SYNTHETIC_PATTERNS = ("tiled_gemm_like", "attention_like_blocked")
ALL_WORKLOADS = CORE_WORKLOADS + OPTIONAL_SYNTHETIC_PATTERNS
BANK_COUNT_SWEEP = (4, 8, 16)
ADDRESS_MAPPING_SWEEP = (
    "word_interleave",
    "cacheline_interleave",
    "row_interleave",
)
DEFAULT_QUEUE_DEPTH = 16
DEFAULT_ADDRESS_MAPPING = "word_interleave"
DEFAULT_INTERLEAVE_BYTES = 4
DEFAULT_ROW_SIZE_BYTES = 64
DEFAULT_BASE_SERVICE_LATENCY_NS = 20.0
DEFAULT_ROW_HIT_LATENCY_NS = 8.0
DEFAULT_ROW_MISS_LATENCY_NS = 40.0
CACHELINE_BYTES = 64
FEATURE_BANK_COUNT = 4
PROJECT_K_SCHEMA_VERSION = "k0.2"
PROJECT_L_SCHEMA_VERSION = "l0.1"
EXPECTED_CORE_WORKLOADS = 3
EXPECTED_OPTIONAL_SYNTHETIC_PATTERNS = 2
EXPECTED_TOTAL_WORKLOADS = 5
EXPECTED_SWEEP_ROWS = 45
PROJECT_L_EXPECTED_TOTAL_WORKLOADS = 5
PROJECT_L_EXPECTED_RECOMMENDATION_ROWS = 5

MAX_BANK_SHARE_HIGH = 0.65
BANK_ENTROPY_LOW = 0.55
BANK_CONFLICT_PROXY_HIGH = 0.35
QUEUE_DELAY_RATIO_HIGH = 0.25
SERVICE_DELAY_RATIO_HIGH = 0.65
QUEUE_DELAY_RATIO_LOW = 0.20
TAIL_RATIO_HIGH = 2.0
BURSTINESS_SCORE_HIGH = 0.35
MAX_QUEUE_OCCUPANCY_HIGH = 4
REUSE_RATIO_LOW = 0.20
PHASE_LOCALITY_LOW = 0.25
ROW_HIT_RATIO_LOW = 25.0
BANK_UTILIZATION_HIGH = 70.0
SENSITIVITY_SCORE_LOW = 0.10

PROJECT_L_BANK_CONFLICT_SIGNAL_HIGH = 0.65
PROJECT_L_BANK_CONFLICT_SIGNAL_MEDIUM = 0.35
PROJECT_L_QUEUEING_SIGNAL_HIGH = 0.60
PROJECT_L_QUEUEING_SIGNAL_MEDIUM = 0.25
PROJECT_L_SERVICE_SIGNAL_HIGH = 0.65
PROJECT_L_SERVICE_SIGNAL_MEDIUM = 0.40
PROJECT_L_BANK_COUNT_SENSITIVITY_HIGH = 0.25
PROJECT_L_MAPPING_SENSITIVITY_HIGH = 0.25
PROJECT_L_DECISION_MARGIN = 0.20

CLAIM_BOUNDARY = (
    "trend-level synthetic trace over Project E simplified banked memory "
    "model; not GPU, silicon, PMU/perf/Nsight, AXI/CHI, GEMM, "
    "Transformer, FlashAttention, or LLM inference evidence"
)

STABLE_SUMMARY_FIELDS = (
    "workload",
    "pattern_class",
    "phase_count",
    "total_requests",
    "total_bytes",
    "read_ratio",
    "write_ratio",
    "unique_cacheline_count",
    "reuse_ratio",
    "sequentiality_score",
    "dominant_stride",
    "burstiness_score",
    "bank_entropy",
    "max_bank_share",
    "avg_latency_ns",
    "p50_latency_ns",
    "p95_latency_ns",
    "throughput_txn_per_us",
    "queue_delay_ratio",
    "service_delay_ratio",
    "bank_conflict_proxy",
    "p95_p50_latency_ratio",
    "bank_utilization_pct",
    "avg_queue_occupancy",
    "max_queue_occupancy",
    "stalled_or_rejected_transactions",
    "row_hit_ratio_pct",
    "primary_bottleneck",
    "confidence",
    "evidence_fields",
    "recommendation",
    "claim_boundary",
)

EXPERIMENTAL_SUMMARY_FIELDS = (
    "avg_reuse_distance",
    "p50_reuse_distance",
    "phase_locality_score",
    "mapping_sensitivity_score",
    "bank_count_sensitivity_score",
)

SUMMARY_FIELDS = (
    "workload",
    "pattern_class",
    "phase_count",
    "total_requests",
    "total_bytes",
    "read_ratio",
    "write_ratio",
    "unique_cacheline_count",
    "reuse_ratio",
    "avg_reuse_distance",
    "p50_reuse_distance",
    "phase_locality_score",
    "sequentiality_score",
    "dominant_stride",
    "burstiness_score",
    "bank_entropy",
    "max_bank_share",
    "avg_latency_ns",
    "p50_latency_ns",
    "p95_latency_ns",
    "throughput_txn_per_us",
    "queue_delay_ratio",
    "service_delay_ratio",
    "bank_conflict_proxy",
    "p95_p50_latency_ratio",
    "mapping_sensitivity_score",
    "bank_count_sensitivity_score",
    "bank_utilization_pct",
    "avg_queue_occupancy",
    "max_queue_occupancy",
    "stalled_or_rejected_transactions",
    "row_hit_ratio_pct",
    "primary_bottleneck",
    "confidence",
    "evidence_fields",
    "recommendation",
    "claim_boundary",
)

STABLE_SWEEP_FIELDS = (
    "workload",
    "bank_count",
    "address_mapping",
    "avg_latency_ns",
    "p50_latency_ns",
    "p95_latency_ns",
    "throughput_txn_per_us",
    "queue_delay_ratio",
    "service_delay_ratio",
    "bank_conflict_proxy",
    "p95_p50_latency_ratio",
    "sweep_delta_pct",
    "primary_bottleneck",
    "confidence",
)
SWEEP_FIELDS = STABLE_SWEEP_FIELDS

PROJECT_L_RECOMMENDATION_FIELDS = (
    "workload",
    "pattern_class",
    "primary_bottleneck",
    "confidence",
    "recommended_action",
    "recommendation_priority",
    "evidence_summary",
    "bank_count_best",
    "address_mapping_best",
    "bank_count_sensitivity_score",
    "mapping_sensitivity_score",
    "locality_signal",
    "queueing_signal",
    "service_signal",
    "bank_conflict_signal",
    "claim_boundary",
)

PROJECT_L_ALLOWED_RECOMMENDED_ACTIONS = (
    "increase_bank_parallelism",
    "change_address_mapping",
    "improve_locality_or_tiling",
    "reduce_queueing_pressure",
    "reduce_target_service_latency",
    "keep_observing_low_confidence",
    "no_single_dominant_action",
)

PROJECT_L_ALLOWED_RECOMMENDATION_PRIORITIES = ("high", "medium", "low")
PROJECT_L_CLAIM_BOUNDARY = "PASS"

PROJECT_L_REQUIRED_UNSUPPORTED_CLAIM_MARKERS = (
    "This is not cycle-accurate simulation",
    "This is not silicon validation",
    "This is not GPU simulation",
    "This is not real GEMM / Transformer / attention performance claim",
    "This is not AXI / CHI protocol compliance",
    "This is not production signoff",
)

REQUIRED_UNSUPPORTED_CLAIM_MARKERS = (
    "不声称真实 GPU 性能",
    "不声称 NVIDIA Nsight 集成",
    "不声称 ARM PMU 验证",
    "不声称 Linux perf 验证",
    "不声称 silicon validation",
    "不声称 production signoff",
    "不声称 full-system cycle accuracy",
    "不声称 AXI / CHI protocol compliance",
    "不声称真实 GEMM kernel performance",
    "不声称真实 Transformer / attention kernel performance",
    "不声称 FlashAttention 或 LLM inference performance",
    "不声称 GPU simulation",
)

FORBIDDEN_AFFIRMATIVE_CLAIM_PATTERNS = (
    "real GPU performance",
    "real GEMM performance",
    "real attention performance",
    "real Transformer performance",
    "cycle accurate",
    "cycle-accurate",
    "production signoff",
    "silicon validation",
    "hardware validation claim",
    "Nsight correlation",
    "PMU correlation",
    "perf correlation",
)

CLAIM_NEGATION_MARKERS = (
    "不声称",
    "不是",
    "不支持",
    "not ",
    "no ",
    "unsupported",
    "without",
)

DANGEROUS_CLEAN_PATHS = {
    REPO_ROOT.resolve(),
    (REPO_ROOT / "build").resolve(),
    (REPO_ROOT / "examples").resolve(),
    (REPO_ROOT / "examples" / "lt").resolve(),
    (REPO_ROOT / "examples" / "lt" / "results").resolve(),
}


class DemoError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run Project K workload-aware memory bottleneck characterization MVP."
        )
    )
    parser.add_argument(
        "--binary",
        default=DEFAULT_BINARY,
        type=Path,
        help=(
            "Project E C++ model binary. Defaults to "
            "build/examples/lt/banked_memory_controller_cpp/banked_memory_controller."
        ),
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        type=Path,
        help="Generated Project K trace input directory under build/.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        type=Path,
        help="Project K output directory.",
    )
    parser.add_argument(
        "--project-l-output-dir",
        default=DEFAULT_PROJECT_L_OUTPUT_DIR,
        type=Path,
        help="Project L recommendation output directory.",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Do not build the Project E C++ binary automatically.",
    )
    return parser.parse_args()


def repo_path(path):
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def display_path(path):
    path = Path(path)
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def remove_path(path):
    path = repo_path(path)
    if not path.exists():
        return
    resolved = path.resolve()
    if resolved in DANGEROUS_CLEAN_PATHS:
        raise DemoError(f"refusing to remove broad path: {display_path(path)}")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def run_command(command):
    print("[demo-project-k] run: " + " ".join(str(part) for part in command))
    result = subprocess.run(
        [str(part) for part in command],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise DemoError(
            "command failed with exit code "
            f"{result.returncode}: {' '.join(str(part) for part in command)}"
        )


def ensure_binary(binary, no_build):
    binary = repo_path(binary)
    if binary.exists():
        return binary

    if no_build:
        raise DemoError(
            "Project E C++ model binary not found: "
            f"{display_path(binary)}\n"
            "Build it with:\n"
            "  cmake -S examples/lt/banked_memory_controller_cpp "
            "-B build/examples/lt/banked_memory_controller_cpp\n"
            "  cmake --build build/examples/lt/banked_memory_controller_cpp"
        )

    run_command(["cmake", "-S", CPP_SOURCE_DIR, "-B", CPP_BUILD_DIR])
    run_command(["cmake", "--build", CPP_BUILD_DIR])
    if not binary.exists():
        raise DemoError(
            "Project E C++ model binary not found after build: "
            f"{display_path(binary)}"
        )
    return binary


def format_hex(value):
    return f"0x{value:08X}"


def hot_bank_timestamp(index):
    burst_size = 8
    burst_gap_ns = 96.0
    in_burst_gap_ns = 2.0
    burst = index // burst_size
    offset = index % burst_size
    return burst * burst_gap_ns + offset * in_burst_gap_ns


def command_for_index(index, write_every):
    return "WRITE" if write_every > 0 and index % write_every == write_every - 1 else "READ"


def request_row(phase, timestamp_ns, address, command="READ", size_bytes=4):
    return {
        "phase": phase,
        "timestamp_ns": timestamp_ns,
        "address": address,
        "command": command,
        "size_bytes": size_bytes,
    }


def regular_requests(count, timestamp_fn, address_fn, command_fn, phase):
    return [
        request_row(
            phase=phase,
            timestamp_ns=timestamp_fn(index),
            address=address_fn(index),
            command=command_fn(index),
        )
        for index in range(count)
    ]


def tiled_gemm_like_requests():
    requests = []
    timestamp_ns = 0.0
    step_ns = 6.0
    a_base = 0x00100000
    b_base = 0x00200000
    c_base = 0x00300000
    tile_m = 4
    tile_n = 4
    tile_k = 4

    for index in range(tile_m * tile_k):
        row = index // tile_k
        col = index % tile_k
        requests.append(
            request_row(
                "a_tile_read",
                timestamp_ns,
                a_base + (row * tile_k + col) * 4,
                "READ",
            )
        )
        timestamp_ns += step_ns

    for index in range(tile_k * tile_n):
        row = index // tile_n
        col = index % tile_n
        requests.append(
            request_row(
                "b_tile_read",
                timestamp_ns,
                b_base + col * DEFAULT_ROW_SIZE_BYTES + row * 4,
                "READ",
            )
        )
        timestamp_ns += step_ns

    for index in range(8):
        requests.append(
            request_row(
                "c_tile_read",
                timestamp_ns,
                c_base + index * 4,
                "READ",
            )
        )
        timestamp_ns += step_ns

    for index in range(8):
        requests.append(
            request_row(
                "c_tile_write",
                timestamp_ns,
                c_base + index * 4,
                "WRITE",
            )
        )
        timestamp_ns += step_ns

    return requests


def attention_like_blocked_requests():
    requests = []
    timestamp_ns = 0.0
    step_ns = 5.0
    q_base = 0x00400000
    k_base = 0x00500000
    v_base = 0x00600000
    out_base = 0x00700000
    block_items = 8

    for index in range(block_items):
        requests.append(
            request_row(
                "q_block_read",
                timestamp_ns,
                q_base + index * 4,
                "READ",
            )
        )
        timestamp_ns += step_ns

    for repeat in range(3):
        for index in range(block_items):
            requests.append(
                request_row(
                    "k_block_repeated_read",
                    timestamp_ns,
                    k_base + index * 4,
                    "READ",
                )
            )
            timestamp_ns += step_ns if repeat == 0 else 2.0

    for repeat in range(3):
        for index in range(block_items):
            requests.append(
                request_row(
                    "v_block_repeated_read",
                    timestamp_ns,
                    v_base + index * 4,
                    "READ",
                )
            )
            timestamp_ns += step_ns if repeat == 0 else 2.0

    for index in range(block_items):
        requests.append(
            request_row(
                "output_write",
                timestamp_ns,
                out_base + index * 4,
                "WRITE",
            )
        )
        timestamp_ns += step_ns

    return requests


def workload_specs():
    return (
        {
            "workload": "streaming",
            "pattern_class": "core_baseline",
            "metadata": "consecutive addresses, smooth issue gap",
            "requests": regular_requests(
                96,
                lambda index: index * 80.0,
                lambda index: index * 4,
                lambda index: command_for_index(index, 32),
                "streaming_read",
            ),
        },
        {
            "workload": "stride",
            "pattern_class": "core_stressor",
            "metadata": "fixed stride addresses",
            "requests": regular_requests(
                96,
                lambda index: index * 16.0,
                lambda index: index * 8,
                lambda index: command_for_index(index, 24),
                "stride_read",
            ),
        },
        {
            "workload": "hot_bank",
            "pattern_class": "core_stressor",
            "metadata": "modeled hot-bank concentration with bursty issue",
            "requests": regular_requests(
                96,
                hot_bank_timestamp,
                lambda index: index * 64,
                lambda index: command_for_index(index, 8),
                "hot_bank_burst",
            ),
        },
        {
            "workload": "tiled_gemm_like",
            "pattern_class": "optional_synthetic_pattern",
            "metadata": (
                "synthetic tile_m=4 tile_n=4 tile_k=4 access-pattern-inspired "
                "trace; no GEMM compute or FLOPS model"
            ),
            "requests": tiled_gemm_like_requests(),
        },
        {
            "workload": "attention_like_blocked",
            "pattern_class": "optional_synthetic_pattern",
            "metadata": (
                "synthetic Q/K/V blocked access-pattern-inspired trace; "
                "no attention compute, softmax, FlashAttention, or LLM model"
            ),
            "requests": attention_like_blocked_requests(),
        },
    )


def write_workload_trace(path, spec):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=(
                "workload_name",
                "txn_id",
                "timestamp_ns",
                "initiator_id",
                "command",
                "address",
                "size_bytes",
            ),
        )
        writer.writeheader()
        for index, request in enumerate(spec["requests"]):
            writer.writerow(
                {
                    "workload_name": spec["workload"],
                    "txn_id": index + 1,
                    "timestamp_ns": f"{request['timestamp_ns']:.3f}",
                    "initiator_id": "101",
                    "command": request["command"],
                    "address": format_hex(request["address"]),
                    "size_bytes": request["size_bytes"],
                }
            )


def generate_workload_traces(input_dir):
    input_dir = repo_path(input_dir)
    remove_path(input_dir)
    input_dir.mkdir(parents=True, exist_ok=True)

    traces = []
    metadata_by_workload = {}
    for spec in workload_specs():
        trace_path = input_dir / f"{spec['workload']}.csv"
        write_workload_trace(trace_path, spec)
        traces.append(trace_path)
        metadata_by_workload[spec["workload"]] = {
            "pattern_class": spec["pattern_class"],
            "metadata": spec["metadata"],
            "requests": spec["requests"],
        }
    return traces, metadata_by_workload


def trace_args(traces):
    args = []
    for trace in traces:
        args.extend(("--trace", trace))
    return args


def read_csv_rows(path):
    path = repo_path(path)
    if not path.exists():
        raise DemoError(f"CSV not found: {display_path(path)}")
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    if not rows:
        raise DemoError(f"CSV is empty: {display_path(path)}")
    return rows


def parse_float(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "NA":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int_value(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "NA":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_address(value):
    if value is None:
        raise DemoError("trace row missing address")
    try:
        return int(str(value).strip(), 0)
    except ValueError as error:
        raise DemoError(f"invalid address value: {value}") from error


def percentile(values, percentile_value):
    if not values:
        return None
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    rank = round((percentile_value / 100.0) * (len(values) - 1))
    rank = max(0, min(rank, len(values) - 1))
    return values[rank]


def fmt(value, digits=3):
    if value is None:
        return "NA"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return "NA"
        return f"{value:.{digits}f}"
    return str(value)


def safe_ratio(numerator, denominator):
    if denominator is None or denominator == 0:
        return None
    return numerator / denominator


def bank_id_for_address(address, bank_count=FEATURE_BANK_COUNT):
    return (address // DEFAULT_INTERLEAVE_BYTES) % bank_count


def normalized_entropy(counts, bucket_count):
    total = sum(counts.values())
    if total == 0 or bucket_count <= 1:
        return None
    entropy = 0.0
    for count in counts.values():
        if count == 0:
            continue
        probability = count / total
        entropy -= probability * math.log(probability)
    return entropy / math.log(bucket_count)


def phase_locality_score(requests):
    if not requests:
        return None
    phases = defaultdict(list)
    for request in requests:
        phases[request["phase"]].append(request["address"] // CACHELINE_BYTES)
    locality_scores = []
    for cachelines in phases.values():
        if not cachelines:
            continue
        unique_count = len(set(cachelines))
        locality_scores.append(1.0 - (unique_count / len(cachelines)))
    if not locality_scores:
        return None
    return sum(locality_scores) / len(locality_scores)


def reuse_distances_for_cachelines(cachelines):
    last_seen = {}
    distances = []
    for index, cacheline in enumerate(cachelines):
        if cacheline in last_seen:
            distances.append(index - last_seen[cacheline])
        last_seen[cacheline] = index
    return distances


def characterize_trace(trace_path, metadata):
    rows = read_csv_rows(trace_path)
    workload = rows[0].get("workload_name") or rows[0].get("workload") or Path(trace_path).stem
    metadata = metadata or {}
    requests = metadata.get("requests", [])

    addresses = [parse_address(row.get("address") or row.get("masked_address")) for row in rows]
    sizes = [parse_int_value(row.get("size_bytes")) or 4 for row in rows]
    timestamps = [parse_float(row.get("timestamp_ns")) or 0.0 for row in rows]
    commands = [(row.get("command") or "READ").upper() for row in rows]

    total_requests = len(rows)
    total_bytes = sum(sizes)
    read_count = sum(1 for command in commands if command in ("READ", "R"))
    write_count = sum(1 for command in commands if command in ("WRITE", "W"))
    cachelines = [address // CACHELINE_BYTES for address in addresses]
    unique_cacheline_count = len(set(cachelines))
    reuse_distances = reuse_distances_for_cachelines(cachelines)
    seen_cachelines = set()
    repeated_cacheline_accesses = 0
    for cacheline in cachelines:
        if cacheline in seen_cachelines:
            repeated_cacheline_accesses += 1
        seen_cachelines.add(cacheline)

    deltas = [right - left for left, right in zip(addresses, addresses[1:])]
    dominant_stride = Counter(deltas).most_common(1)[0][0] if deltas else None
    sequential_hits = sum(
        1 for index, delta in enumerate(deltas) if delta == sizes[index]
    )
    sequentiality_score = safe_ratio(sequential_hits, len(deltas)) or 0.0

    gaps = [right - left for left, right in zip(timestamps, timestamps[1:])]
    if gaps:
        p50_gap = percentile(gaps, 50.0) or 0.0
        p95_gap = percentile(gaps, 95.0) or 0.0
        burstiness_score = 0.0 if p95_gap <= 0.0 else max(0.0, (p95_gap - p50_gap) / p95_gap)
    else:
        burstiness_score = 0.0

    bank_counts = Counter(
        bank_id_for_address(address, FEATURE_BANK_COUNT) for address in addresses
    )
    max_bank_share = (
        max(bank_counts.values()) / total_requests if total_requests > 0 else None
    )
    bank_entropy = normalized_entropy(bank_counts, FEATURE_BANK_COUNT)

    return {
        "workload": workload,
        "pattern_class": metadata.get("pattern_class", "unknown"),
        "phase_count": len({request["phase"] for request in requests}) if requests else 1,
        "total_requests": total_requests,
        "total_bytes": total_bytes,
        "read_ratio": safe_ratio(read_count, total_requests),
        "write_ratio": safe_ratio(write_count, total_requests),
        "unique_cacheline_count": unique_cacheline_count,
        "reuse_ratio": safe_ratio(repeated_cacheline_accesses, total_requests),
        "avg_reuse_distance": (
            sum(reuse_distances) / len(reuse_distances) if reuse_distances else None
        ),
        "p50_reuse_distance": percentile(reuse_distances, 50.0),
        "phase_locality_score": phase_locality_score(requests),
        "sequentiality_score": sequentiality_score,
        "dominant_stride": dominant_stride,
        "burstiness_score": burstiness_score,
        "bank_entropy": bank_entropy,
        "max_bank_share": max_bank_share,
    }


def group_trace_rows(trace_rows):
    grouped = defaultdict(list)
    for row in trace_rows:
        grouped[row.get("workload", "")].append(row)
    return grouped


def summarize_model_metrics(summary_rows, trace_rows):
    traces_by_workload = group_trace_rows(trace_rows)
    metrics = {}
    for row in summary_rows:
        workload = row.get("workload", "")
        workload_trace_rows = traces_by_workload.get(workload, [])
        accepted_rows = [
            trace_row
            for trace_row in workload_trace_rows
            if trace_row.get("response_status") == "ACCEPTED"
        ]
        latencies = [
            value
            for value in (
                parse_float(trace_row.get("total_latency_ns"))
                for trace_row in accepted_rows
            )
            if value is not None
        ]
        queue_delays = [
            value
            for value in (
                parse_float(trace_row.get("queue_delay_ns"))
                for trace_row in accepted_rows
            )
            if value is not None
        ]
        service_delays = [
            value
            for value in (
                parse_float(trace_row.get("service_latency_ns"))
                for trace_row in accepted_rows
            )
            if value is not None
        ]

        latency_sum = sum(latencies) if latencies else None
        queue_delay_sum = sum(queue_delays) if queue_delays else None
        service_delay_sum = sum(service_delays) if service_delays else None
        p50_latency = percentile(latencies, 50.0)
        p95_latency = parse_float(row.get("p95_latency_ns"))
        if p95_latency is None:
            p95_latency = percentile(latencies, 95.0)
        queue_delay_ratio = (
            safe_ratio(queue_delay_sum, latency_sum)
            if queue_delay_sum is not None and latency_sum is not None
            else None
        )
        service_delay_ratio = (
            safe_ratio(service_delay_sum, latency_sum)
            if service_delay_sum is not None and latency_sum is not None
            else None
        )
        queue_waits = sum(
            1
            for value in queue_delays
            if value is not None and value > 0.0
        )
        bank_conflict_proxy = safe_ratio(queue_waits, len(accepted_rows))
        p95_p50_ratio = (
            safe_ratio(p95_latency, p50_latency)
            if p95_latency is not None and p50_latency not in (None, 0.0)
            else None
        )

        metrics[workload] = {
            "workload": workload,
            "avg_latency_ns": parse_float(row.get("avg_latency_ns")),
            "p50_latency_ns": p50_latency,
            "p95_latency_ns": p95_latency,
            "throughput_txn_per_us": parse_float(row.get("throughput_txn_per_us")),
            "queue_delay_ratio": queue_delay_ratio,
            "service_delay_ratio": service_delay_ratio,
            "bank_conflict_proxy": bank_conflict_proxy,
            "p95_p50_latency_ratio": p95_p50_ratio,
            "bank_utilization_pct": parse_float(row.get("bank_utilization_pct")),
            "avg_queue_occupancy": parse_float(row.get("avg_queue_occupancy")),
            "max_queue_occupancy": parse_int_value(row.get("max_queue_occupancy")),
            "stalled_or_rejected_transactions": parse_int_value(
                row.get("stalled_or_rejected_transactions")
            ),
            "row_hit_ratio_pct": parse_float(row.get("row_hit_ratio_pct")),
        }
    return metrics


def has_high(value, threshold):
    return value is not None and value >= threshold


def has_low(value, threshold):
    return value is not None and value <= threshold


def evidence_text(evidence):
    return "; ".join(f"{key}={fmt(value)}" for key, value in evidence.items())


def score_confidence(score):
    if score >= 3:
        return "high"
    if score == 2:
        return "medium"
    if score == 1:
        return "low"
    return "low"


def rule_scores(features, metrics):
    max_bank_share = features.get("max_bank_share")
    bank_entropy = features.get("bank_entropy")
    bank_conflict_proxy = metrics.get("bank_conflict_proxy")
    tail_ratio = metrics.get("p95_p50_latency_ratio")
    queue_delay_ratio = metrics.get("queue_delay_ratio")
    service_delay_ratio = metrics.get("service_delay_ratio")
    max_queue_occupancy = metrics.get("max_queue_occupancy")
    rejected = metrics.get("stalled_or_rejected_transactions")
    burstiness_score = features.get("burstiness_score")
    reuse_ratio = features.get("reuse_ratio")
    phase_locality = features.get("phase_locality_score")
    row_hit_ratio = metrics.get("row_hit_ratio_pct")
    bank_utilization = metrics.get("bank_utilization_pct")
    bank_count_sensitivity = features.get("bank_count_sensitivity_score")

    bank_score = 0
    bank_score += 1 if has_high(max_bank_share, MAX_BANK_SHARE_HIGH) else 0
    bank_score += 1 if has_low(bank_entropy, BANK_ENTROPY_LOW) else 0
    bank_score += 1 if has_high(bank_conflict_proxy, BANK_CONFLICT_PROXY_HIGH) else 0
    bank_score += 1 if has_high(tail_ratio, TAIL_RATIO_HIGH) else 0

    queue_score = 0
    queue_score += 2 if has_high(queue_delay_ratio, QUEUE_DELAY_RATIO_HIGH) else 0
    queue_score += 1 if max_queue_occupancy is not None and max_queue_occupancy >= MAX_QUEUE_OCCUPANCY_HIGH else 0
    queue_score += 2 if rejected is not None and rejected > 0 else 0

    service_score = 0
    service_score += 2 if has_high(service_delay_ratio, SERVICE_DELAY_RATIO_HIGH) else 0
    service_score += 1 if has_low(queue_delay_ratio, QUEUE_DELAY_RATIO_LOW) else 0

    burst_score = 0
    burst_score += 1 if has_high(burstiness_score, BURSTINESS_SCORE_HIGH) else 0
    burst_score += 1 if has_high(tail_ratio, TAIL_RATIO_HIGH) else 0
    burst_score += 1 if max_queue_occupancy is not None and max_queue_occupancy >= MAX_QUEUE_OCCUPANCY_HIGH else 0
    burst_score += 1 if rejected is not None and rejected > 0 else 0

    locality_score = 0
    locality_score += 1 if has_low(reuse_ratio, REUSE_RATIO_LOW) else 0
    locality_score += 1 if has_low(phase_locality, PHASE_LOCALITY_LOW) else 0
    locality_score += 1 if has_low(row_hit_ratio, ROW_HIT_RATIO_LOW) else 0
    locality_score += 1 if has_high(service_delay_ratio, SERVICE_DELAY_RATIO_HIGH) else 0
    locality_score += 1 if has_low(queue_delay_ratio, QUEUE_DELAY_RATIO_LOW) else 0

    bandwidth_score = 0
    bandwidth_score += 1 if has_high(bank_utilization, BANK_UTILIZATION_HIGH) else 0
    bandwidth_score += 1 if has_high(queue_delay_ratio, QUEUE_DELAY_RATIO_HIGH) else 0
    bandwidth_score += 1 if rejected is not None and rejected > 0 else 0
    bandwidth_score += 1 if has_low(bank_count_sensitivity, SENSITIVITY_SCORE_LOW) else 0

    return {
        "bank_conflict_bound": bank_score,
        "queueing_bound": queue_score,
        "service_latency_bound": service_score,
        "burstiness_bound": burst_score,
        "locality_loss_bound": locality_score,
        "bandwidth_pressure_bound": bandwidth_score,
    }


def attribution_for(features, metrics):
    scores = rule_scores(features, metrics)
    priority = {
        "bank_conflict_bound": 0,
        "queueing_bound": 1,
        "bandwidth_pressure_bound": 2,
        "burstiness_bound": 3,
        "locality_loss_bound": 4,
        "service_latency_bound": 5,
    }
    primary = max(scores, key=lambda name: (scores[name], -priority[name]))
    score = scores[primary]
    if score <= 0:
        primary = "no_dominant_bottleneck"

    recommendations = {
        "bank_conflict_bound": (
            "Expected direction: increase bank parallelism or spread addresses "
            "across banks in the synthetic mapping before making stronger claims."
        ),
        "queueing_bound": (
            "Expected direction: reduce injection pressure, smooth request issue, "
            "or increase modeled buffering/bank parallelism in a bounded sweep."
        ),
        "service_latency_bound": (
            "Expected direction: reduce modeled service latency or improve "
            "synthetic locality; queue-depth changes alone may have limited effect."
        ),
        "burstiness_bound": (
            "Expected direction: smooth burst issue pattern or evaluate buffering "
            "as a future Project K knob."
        ),
        "locality_loss_bound": (
            "Expected direction: improve synthetic phase locality or tile/block "
            "ordering in the current model; this is not a cache hit/miss claim."
        ),
        "bandwidth_pressure_bound": (
            "Expected direction: treat the workload as modeled throughput-pressure "
            "limited and compare bank/mapping alternatives before stronger claims."
        ),
        "no_dominant_bottleneck": (
            "Expected direction: treat as current-model baseline and compare "
            "against stressed workloads."
        ),
    }
    evidence_by_rule = {
        "bank_conflict_bound": {
            "max_bank_share": features.get("max_bank_share"),
            "bank_entropy": features.get("bank_entropy"),
            "bank_conflict_proxy": metrics.get("bank_conflict_proxy"),
            "p95_p50_latency_ratio": metrics.get("p95_p50_latency_ratio"),
            "bank_utilization_pct": metrics.get("bank_utilization_pct"),
        },
        "queueing_bound": {
            "queue_delay_ratio": metrics.get("queue_delay_ratio"),
            "avg_queue_occupancy": metrics.get("avg_queue_occupancy"),
            "max_queue_occupancy": metrics.get("max_queue_occupancy"),
            "stalled_or_rejected_transactions": metrics.get(
                "stalled_or_rejected_transactions"
            ),
            "p95_latency_ns": metrics.get("p95_latency_ns"),
        },
        "service_latency_bound": {
            "service_delay_ratio": metrics.get("service_delay_ratio"),
            "avg_latency_ns": metrics.get("avg_latency_ns"),
            "row_hit_ratio_pct": metrics.get("row_hit_ratio_pct"),
            "queue_delay_ratio": metrics.get("queue_delay_ratio"),
        },
        "burstiness_bound": {
            "burstiness_score": features.get("burstiness_score"),
            "p95_p50_latency_ratio": metrics.get("p95_p50_latency_ratio"),
            "max_queue_occupancy": metrics.get("max_queue_occupancy"),
            "stalled_or_rejected_transactions": metrics.get(
                "stalled_or_rejected_transactions"
            ),
        },
        "locality_loss_bound": {
            "reuse_ratio": features.get("reuse_ratio"),
            "unique_cacheline_count": features.get("unique_cacheline_count"),
            "row_hit_ratio_pct": metrics.get("row_hit_ratio_pct"),
            "phase_locality_score": features.get("phase_locality_score"),
            "service_delay_ratio": metrics.get("service_delay_ratio"),
        },
        "bandwidth_pressure_bound": {
            "throughput_txn_per_us": metrics.get("throughput_txn_per_us"),
            "bank_utilization_pct": metrics.get("bank_utilization_pct"),
            "queue_delay_ratio": metrics.get("queue_delay_ratio"),
            "stalled_or_rejected_transactions": metrics.get(
                "stalled_or_rejected_transactions"
            ),
            "bank_count_sensitivity_score": features.get(
                "bank_count_sensitivity_score"
            ),
        },
        "no_dominant_bottleneck": {
            "avg_latency_ns": metrics.get("avg_latency_ns"),
            "p95_latency_ns": metrics.get("p95_latency_ns"),
        },
    }
    return {
        "primary_bottleneck": primary,
        "confidence": score_confidence(score),
        "evidence_fields": evidence_text(evidence_by_rule[primary]),
        "recommendation": recommendations[primary],
        "claim_boundary": CLAIM_BOUNDARY,
    }


def run_project_e(binary, traces, output_dir, bank_count, address_mapping):
    output_dir = repo_path(output_dir)
    remove_path(output_dir)
    command = [
        binary,
        *trace_args(traces),
        "--output-dir",
        output_dir,
        "--bank-count",
        str(bank_count),
        "--queue-depth",
        str(DEFAULT_QUEUE_DEPTH),
        "--address-mapping",
        address_mapping,
        "--base-service-latency-ns",
        str(DEFAULT_BASE_SERVICE_LATENCY_NS),
        "--row-hit-latency-ns",
        str(DEFAULT_ROW_HIT_LATENCY_NS),
        "--row-miss-latency-ns",
        str(DEFAULT_ROW_MISS_LATENCY_NS),
        "--row-size-bytes",
        str(DEFAULT_ROW_SIZE_BYTES),
        "--interleave-bytes",
        str(DEFAULT_INTERLEAVE_BYTES),
    ]
    run_command(command)

    summary_path = output_dir / "summary.csv"
    trace_path = output_dir / "trace.csv"
    if not summary_path.exists():
        raise DemoError(f"Project E summary.csv not found: {display_path(summary_path)}")
    if not trace_path.exists():
        raise DemoError(f"Project E trace.csv not found: {display_path(trace_path)}")
    return read_csv_rows(summary_path), read_csv_rows(trace_path)


def add_sweep_delta_pct(sweep_rows):
    baseline_by_workload = {}
    for row in sweep_rows:
        if (
            row["bank_count"] == BANK_COUNT_SWEEP[0]
            and row["address_mapping"] == DEFAULT_ADDRESS_MAPPING
        ):
            baseline_by_workload[row["workload"]] = row.get("p95_latency_ns")

    for row in sweep_rows:
        baseline = baseline_by_workload.get(row["workload"])
        p95_latency = row.get("p95_latency_ns")
        if baseline in (None, 0.0) or p95_latency is None:
            row["sweep_delta_pct"] = None
        else:
            row["sweep_delta_pct"] = 100.0 * (p95_latency - baseline) / baseline


def sensitivity_score(values):
    clean_values = [value for value in values if value is not None]
    if len(clean_values) < 2:
        return None
    high = max(clean_values)
    low = min(clean_values)
    if high == 0.0:
        return None
    return (high - low) / high


def compute_sensitivity_by_workload(sweep_rows):
    grouped = defaultdict(list)
    for row in sweep_rows:
        grouped[row["workload"]].append(row)

    sensitivity = {}
    for workload, rows in grouped.items():
        mapping_values = [
            row.get("p95_latency_ns")
            for row in rows
            if row["bank_count"] == BANK_COUNT_SWEEP[0]
        ]
        bank_count_values = [
            row.get("p95_latency_ns")
            for row in rows
            if row["address_mapping"] == DEFAULT_ADDRESS_MAPPING
        ]
        sensitivity[workload] = {
            "mapping_sensitivity_score": sensitivity_score(mapping_values),
            "bank_count_sensitivity_score": sensitivity_score(bank_count_values),
        }
    return sensitivity


def build_summary_rows(features_by_workload, model_metrics, sensitivity_by_workload):
    rows = []
    for workload in ALL_WORKLOADS:
        features = features_by_workload.get(workload)
        metrics = model_metrics.get(workload)
        if features is None:
            raise DemoError(f"missing features for workload: {workload}")
        if metrics is None:
            raise DemoError(f"missing model metrics for workload: {workload}")
        features = dict(features)
        features.update(sensitivity_by_workload.get(workload, {}))
        attribution = attribution_for(features, metrics)
        combined = {}
        combined.update(features)
        combined.update(metrics)
        combined.update(attribution)
        rows.append(combined)
    return rows


def write_csv(path, fieldnames, rows):
    path = repo_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt(row.get(field)) for field in fieldnames})
    return path


def csv_header(path):
    with repo_path(path).open(newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        return next(reader, [])


def missing_fields(actual_fields, required_fields):
    actual = set(actual_fields)
    return [field for field in required_fields if field not in actual]


def forbidden_affirmative_claim_hits(report_text):
    hits = []
    for line_number, line in enumerate(report_text.splitlines(), start=1):
        lower_line = line.lower()
        if any(marker in lower_line for marker in CLAIM_NEGATION_MARKERS):
            continue
        for pattern in FORBIDDEN_AFFIRMATIVE_CLAIM_PATTERNS:
            if pattern.lower() in lower_line:
                hits.append(f"line {line_number}: {line.strip()}")
                break
    return hits


def validate_project_k_acceptance(
    summary_path,
    sweep_path,
    report_path,
    summary_rows,
    sweep_rows,
):
    errors = []
    if len(CORE_WORKLOADS) != EXPECTED_CORE_WORKLOADS:
        errors.append(
            f"core workload count {len(CORE_WORKLOADS)} != {EXPECTED_CORE_WORKLOADS}"
        )
    if len(OPTIONAL_SYNTHETIC_PATTERNS) != EXPECTED_OPTIONAL_SYNTHETIC_PATTERNS:
        errors.append(
            "optional synthetic pattern count "
            f"{len(OPTIONAL_SYNTHETIC_PATTERNS)} "
            f"!= {EXPECTED_OPTIONAL_SYNTHETIC_PATTERNS}"
        )
    if len(ALL_WORKLOADS) != EXPECTED_TOTAL_WORKLOADS:
        errors.append(
            f"total workload count {len(ALL_WORKLOADS)} != {EXPECTED_TOTAL_WORKLOADS}"
        )
    if len(summary_rows) != EXPECTED_TOTAL_WORKLOADS:
        errors.append(f"summary rows {len(summary_rows)} != {EXPECTED_TOTAL_WORKLOADS}")
    if len(sweep_rows) != EXPECTED_SWEEP_ROWS:
        errors.append(f"sweep rows {len(sweep_rows)} != {EXPECTED_SWEEP_ROWS}")
    expected_sweep_from_knobs = (
        EXPECTED_TOTAL_WORKLOADS * len(BANK_COUNT_SWEEP) * len(ADDRESS_MAPPING_SWEEP)
    )
    if EXPECTED_SWEEP_ROWS != expected_sweep_from_knobs:
        errors.append(
            f"expected sweep rows {EXPECTED_SWEEP_ROWS} != knob product "
            f"{expected_sweep_from_knobs}"
        )
    if any(row.get("claim_boundary") != CLAIM_BOUNDARY for row in summary_rows):
        errors.append("one or more summary rows have a mismatched claim boundary")

    summary_missing = missing_fields(csv_header(summary_path), STABLE_SUMMARY_FIELDS)
    if summary_missing:
        errors.append("summary CSV missing stable fields: " + ", ".join(summary_missing))

    sweep_missing = missing_fields(csv_header(sweep_path), STABLE_SWEEP_FIELDS)
    if sweep_missing:
        errors.append("sweep CSV missing stable fields: " + ", ".join(sweep_missing))

    report_text = repo_path(report_path).read_text(encoding="utf-8")
    missing_claim_markers = [
        marker
        for marker in REQUIRED_UNSUPPORTED_CLAIM_MARKERS
        if marker not in report_text
    ]
    if missing_claim_markers:
        errors.append(
            "generated report missing unsupported-claim markers: "
            + ", ".join(missing_claim_markers)
        )

    forbidden_hits = forbidden_affirmative_claim_hits(report_text)
    if forbidden_hits:
        errors.append(
            "generated report has possible affirmative forbidden claim(s): "
            + "; ".join(forbidden_hits)
        )

    if errors:
        raise DemoError("Project K acceptance self-check failed: " + " | ".join(errors))


def markdown_cell(value):
    return str(value).replace("\n", " ").replace("|", "\\|")


def markdown_table(headers, rows):
    lines = [
        "| " + " | ".join(markdown_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(markdown_cell(value) for value in row) + " |")
    return lines


def write_generated_report(path, summary_rows, sweep_rows, generated_paths):
    path = repo_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    summary_headers = (
        "workload",
        "pattern_class",
        "primary_bottleneck",
        "confidence",
        "max_bank_share",
        "bank_entropy",
        "phase_locality_score",
        "queue_delay_ratio",
        "service_delay_ratio",
        "mapping_sensitivity_score",
        "bank_count_sensitivity_score",
        "p95_p50_latency_ratio",
    )
    sweep_headers = (
        "workload",
        "bank_count",
        "address_mapping",
        "avg_latency_ns",
        "p95_latency_ns",
        "bank_conflict_proxy",
        "sweep_delta_pct",
        "primary_bottleneck",
    )

    lines = [
        "# Project K.3 Workload-Aware Memory Bottleneck Report",
        "",
        "状态：generated demo report with K.3 schema and self-check hardening。",
        "",
        "## Scope",
        "",
        "Project K.3 使用受控 synthetic workload traces 运行 Project E simplified "
        "banked memory model，并输出趋势级 bottleneck attribution 和 mapping "
        "sensitivity sweep。它不是新的 C++ memory model，也不修改 Project G/H/I/J。",
        "",
        "## Architecture Summary",
        "",
        "Project K frames the architecture question as a bounded evidence chain: "
        "`workload access pattern -> memory-system stressor -> measurable symptom "
        "-> bottleneck attribution -> bounded recommendation`. The demo keeps "
        "`streaming`, `stride`, and `hot_bank` as core workloads, then adds "
        "`tiled_gemm_like` and `attention_like_blocked` as optional synthetic "
        "access-pattern-inspired traces.",
        "",
        "Recommendations in this report are expected directions inside the "
        "Project E simplified model. They are not hardware performance claims, "
        "not GPU claims, and not GEMM / attention / AI-kernel performance claims.",
        "",
        "## Flow",
        "",
        "```text",
        "synthetic workload trace",
        "-> workload feature extraction",
        "-> Project E simplified banked memory model run",
        "-> model metric normalization",
        "-> bottleneck attribution",
        "-> bank_count and address_mapping sweep",
        "-> CSV / markdown report",
        "-> demo PASS",
        "```",
        "",
        "## Workloads",
        "",
        "- `streaming`: consecutive addresses, low-conflict baseline.",
        "- `stride`: fixed stride addresses, exposes mapping sensitivity.",
        "- `hot_bank`: addresses concentrated on one modeled bank with bursty issue.",
        "- `tiled_gemm_like`: synthetic A/B/C tile read/write pattern; no matrix "
        "multiply compute, FLOPS, or GEMM throughput model.",
        "- `attention_like_blocked`: synthetic Q/K/V repeated-read plus output-write "
        "pattern; no softmax, FlashAttention, Transformer, or LLM inference model.",
        "",
        "`tiled_gemm_like` and `attention_like_blocked` are optional synthetic "
        "access-pattern-inspired traces. They are not real AI kernel workloads.",
        "",
        "## Metric Split",
        "",
        "Trace-derived features describe the input shape: request count, bytes, "
        "read/write mix, locality proxies, stride, burstiness, and modeled bank "
        "concentration. Model-derived metrics describe the symptoms after replay: "
        "latency, throughput, queue delay, service delay, bank-conflict proxy, "
        "tail amplification, and sweep sensitivity.",
        "",
        "## CSV Schema Contract",
        "",
        f"- Project K CSV schema version: `{PROJECT_K_SCHEMA_VERSION}`.",
        "- Stable summary fields: "
        + ", ".join(f"`{field}`" for field in STABLE_SUMMARY_FIELDS)
        + ".",
        "- Experimental summary fields: "
        + ", ".join(f"`{field}`" for field in EXPERIMENTAL_SUMMARY_FIELDS)
        + ".",
        "- Stable sweep fields: "
        + ", ".join(f"`{field}`" for field in STABLE_SWEEP_FIELDS)
        + ".",
        "",
        "## Attribution Summary",
        "",
    ]
    lines.extend(
        markdown_table(
            summary_headers,
            ([fmt(row.get(field)) for field in summary_headers] for row in summary_rows),
        )
    )
    lines.extend(
        [
            "",
            "## Evidence Chain",
            "",
            "- `streaming`: low queue pressure in the current model, so the baseline "
            "is expected to be service-latency dominated.",
            "- `stride`: fixed address deltas can concentrate modeled bank access and "
            "increase same-bank waiting.",
            "- `hot_bank`: concentrated addresses plus bursty issue can saturate the "
            "modeled bank queue, increasing tail latency and rejected transactions.",
            "- `tiled_gemm_like`: synthetic A/B/C tile phases expose locality proxy "
            "and mapping sensitivity without modeling matrix multiply compute.",
            "- `attention_like_blocked`: synthetic Q/K/V repeated-read phases expose "
            "blocked reuse and output-write pressure without modeling attention.",
            "",
            "Each row keeps `evidence_fields` in the CSV so the primary bottleneck "
            "can be audited without treating the attribution as a black-box model.",
            "",
            "## Current Sweep",
            "",
            "The current hard sweep covers `bank_count = 4 / 8 / 16` and "
            "`address_mapping = word_interleave / cacheline_interleave / "
            "row_interleave`. `xor_folded`, queue-depth sweep, service-latency "
            "sweep, and burstiness-mode sweep are future work.",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            sweep_headers,
            ([fmt(row.get(field)) for field in sweep_headers] for row in sweep_rows),
        )
    )
    lines.extend(
        [
            "",
            "## Generated Outputs",
            "",
        ]
    )
    for label, generated_path in generated_paths:
        lines.append(f"- `{label}`: `{display_path(generated_path)}`")
    lines.extend(
        [
            "",
            "## Acceptance Result",
            "",
            f"- `core_workloads={len(CORE_WORKLOADS)}`",
            f"- `optional_synthetic_patterns={len(OPTIONAL_SYNTHETIC_PATTERNS)}`",
            f"- `total_workloads={len(ALL_WORKLOADS)}`",
            f"- `summary_rows={len(summary_rows)}`",
            f"- `sweep_rows={len(sweep_rows)}`",
            "- `claim_boundary=PASS`",
            f"- `schema_version={PROJECT_K_SCHEMA_VERSION}`",
            "",
            "## Supported Claims",
            "",
            "- 本项目展示一种受控 synthetic trace 方法，用于观察 workload access "
            "pattern 如何影响当前 Project E simplified banked memory model。",
            "- 本项目支持趋势级 bottleneck attribution，不支持真实硬件 accuracy claim。",
            "- 本项目可以比较 `bank_count` 和 `address_mapping` 在当前模型定义下对 "
            "latency、queueing、bank concentration proxy 和 throughput 的相对影响。",
            "",
            "## Unsupported Claims",
            "",
            "- 不声称真实 GPU 性能。",
            "- 不声称 Apple Silicon 验证。",
            "- 不声称 NVIDIA Nsight 集成。",
            "- 不声称 ARM PMU 验证。",
            "- 不声称 Linux perf 验证。",
            "- 不声称 silicon validation。",
            "- 不声称 production signoff。",
            "- 不声称 full-system cycle accuracy。",
            "- 不声称 full SoC validation。",
            "- 不声称 AXI / CHI protocol compliance。",
            "- 不声称真实 GEMM kernel performance。",
            "- 不声称真实 Transformer / attention kernel performance。",
            "- 不声称 FlashAttention 或 LLM inference performance。",
            "- 不声称 GPU simulation。",
            "",
            "## Future Work",
            "",
            "- Keep optional synthetic patterns small and bounded.",
            "- Add future `xor_folded` mapping only after the model interface "
            "explicitly supports it.",
            "- Add queue-depth, service-latency, and burstiness sweeps in a later "
            "Project K step.",
            "- Keep Project G/H/I/J unchanged unless a later validation-integration "
            "task explicitly requests it.",
            "",
            f"Claim boundary: {CLAIM_BOUNDARY}.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def metric_value(row, field):
    value = row.get(field)
    if isinstance(value, (int, float)):
        return value
    return parse_float(value)


def project_l_best_sweep_by_workload(sweep_rows):
    grouped = defaultdict(list)
    for row in sweep_rows:
        grouped[row.get("workload", "")].append(row)

    best_by_workload = {}
    for workload, rows in grouped.items():
        if not workload or not rows:
            continue

        def sort_key(row):
            p95_latency = metric_value(row, "p95_latency_ns")
            avg_latency = metric_value(row, "avg_latency_ns")
            bank_count = parse_int_value(row.get("bank_count"))
            address_mapping = row.get("address_mapping", "")
            mapping_rank = (
                ADDRESS_MAPPING_SWEEP.index(address_mapping)
                if address_mapping in ADDRESS_MAPPING_SWEEP
                else len(ADDRESS_MAPPING_SWEEP)
            )
            return (
                p95_latency if p95_latency is not None else math.inf,
                avg_latency if avg_latency is not None else math.inf,
                bank_count if bank_count is not None else math.inf,
                mapping_rank,
            )

        best_row = min(rows, key=sort_key)
        best_by_workload[workload] = {
            "bank_count_best": parse_int_value(best_row.get("bank_count")),
            "address_mapping_best": best_row.get("address_mapping", "unknown"),
        }
    return best_by_workload


def project_l_bank_conflict_signal(row):
    bank_conflict_proxy = metric_value(row, "bank_conflict_proxy")
    max_bank_share = metric_value(row, "max_bank_share")
    bank_entropy = metric_value(row, "bank_entropy")
    concentrated_trace = (
        has_high(max_bank_share, MAX_BANK_SHARE_HIGH)
        and has_low(bank_entropy, BANK_ENTROPY_LOW)
    )
    if has_high(bank_conflict_proxy, PROJECT_L_BANK_CONFLICT_SIGNAL_HIGH):
        return "high"
    if concentrated_trace or has_high(
        bank_conflict_proxy, PROJECT_L_BANK_CONFLICT_SIGNAL_MEDIUM
    ):
        return "medium"
    return "low"


def project_l_queueing_signal(row):
    queue_delay_ratio = metric_value(row, "queue_delay_ratio")
    max_queue_occupancy = parse_int_value(row.get("max_queue_occupancy"))
    rejected = parse_int_value(row.get("stalled_or_rejected_transactions"))
    if (
        has_high(queue_delay_ratio, PROJECT_L_QUEUEING_SIGNAL_HIGH)
        or (max_queue_occupancy is not None and max_queue_occupancy >= 8)
        or (rejected is not None and rejected > 0)
    ):
        return "high"
    if has_high(queue_delay_ratio, PROJECT_L_QUEUEING_SIGNAL_MEDIUM) or (
        max_queue_occupancy is not None and max_queue_occupancy >= MAX_QUEUE_OCCUPANCY_HIGH
    ):
        return "medium"
    return "low"


def project_l_service_signal(row):
    service_delay_ratio = metric_value(row, "service_delay_ratio")
    if has_high(service_delay_ratio, PROJECT_L_SERVICE_SIGNAL_HIGH):
        return "high"
    if has_high(service_delay_ratio, PROJECT_L_SERVICE_SIGNAL_MEDIUM):
        return "medium"
    return "low"


def project_l_locality_signal(row):
    reuse_ratio = metric_value(row, "reuse_ratio")
    sequentiality_score = metric_value(row, "sequentiality_score")
    phase_locality = metric_value(row, "phase_locality_score")
    avg_reuse_distance = metric_value(row, "avg_reuse_distance")
    weak_low_reuse = (
        has_low(reuse_ratio, REUSE_RATIO_LOW)
        and has_low(sequentiality_score, PHASE_LOCALITY_LOW)
    )
    weak_phase = has_low(phase_locality, PHASE_LOCALITY_LOW)
    weak_reuse_distance = (
        avg_reuse_distance is not None and avg_reuse_distance >= 16.0
    )
    if weak_low_reuse or weak_phase or weak_reuse_distance:
        return "weak"
    if (
        has_low(reuse_ratio, 0.50)
        or has_low(sequentiality_score, 0.50)
        or has_low(phase_locality, 0.50)
        or (avg_reuse_distance is not None and avg_reuse_distance >= 4.0)
    ):
        return "mixed"
    return "strong"


def project_l_recommendation_priority(action, row, signals):
    confidence = row.get("confidence", "")
    queue_delay_ratio = metric_value(row, "queue_delay_ratio")
    service_delay_ratio = metric_value(row, "service_delay_ratio")
    bank_count_sensitivity = metric_value(row, "bank_count_sensitivity_score")
    mapping_sensitivity = metric_value(row, "mapping_sensitivity_score")

    if action in (
        "keep_observing_low_confidence",
        "no_single_dominant_action",
    ):
        return "low"
    if confidence != "high":
        return "medium"
    if action == "increase_bank_parallelism":
        return "high" if has_high(bank_count_sensitivity, 0.50) else "medium"
    if action == "change_address_mapping":
        return "high" if has_high(mapping_sensitivity, 0.50) else "medium"
    if action == "reduce_queueing_pressure":
        return "high" if has_high(queue_delay_ratio, 0.75) else "medium"
    if action == "reduce_target_service_latency":
        return "high" if has_high(service_delay_ratio, 0.75) else "medium"
    if action == "improve_locality_or_tiling":
        return "medium" if signals["locality_signal"] == "weak" else "low"
    return "low"


def project_l_action_for(row, best_knobs, signals):
    confidence = row.get("confidence", "")
    bank_count_sensitivity = metric_value(row, "bank_count_sensitivity_score")
    mapping_sensitivity = metric_value(row, "mapping_sensitivity_score")
    queue_delay_ratio = metric_value(row, "queue_delay_ratio")
    service_delay_ratio = metric_value(row, "service_delay_ratio")
    bank_count_best = best_knobs.get("bank_count_best")
    address_mapping_best = best_knobs.get("address_mapping_best")

    if confidence == "low":
        return "keep_observing_low_confidence"
    if (
        signals["bank_conflict_signal"] == "high"
        and has_high(bank_count_sensitivity, PROJECT_L_BANK_COUNT_SENSITIVITY_HIGH)
        and bank_count_best is not None
        and bank_count_best != BANK_COUNT_SWEEP[0]
    ):
        return "increase_bank_parallelism"
    if (
        has_high(mapping_sensitivity, PROJECT_L_MAPPING_SENSITIVITY_HIGH)
        and address_mapping_best
        and address_mapping_best != DEFAULT_ADDRESS_MAPPING
    ):
        return "change_address_mapping"
    if signals["locality_signal"] == "weak":
        return "improve_locality_or_tiling"
    if (
        queue_delay_ratio is not None
        and service_delay_ratio is not None
        and queue_delay_ratio - service_delay_ratio >= PROJECT_L_DECISION_MARGIN
    ):
        return "reduce_queueing_pressure"
    if (
        queue_delay_ratio is not None
        and service_delay_ratio is not None
        and service_delay_ratio - queue_delay_ratio >= PROJECT_L_DECISION_MARGIN
        and signals["bank_conflict_signal"] == "low"
    ):
        return "reduce_target_service_latency"
    return "no_single_dominant_action"


def project_l_evidence_summary(row, best_knobs, signals):
    return (
        f"bank_conflict_proxy={fmt(metric_value(row, 'bank_conflict_proxy'))}; "
        f"bank_count_sensitivity_score="
        f"{fmt(metric_value(row, 'bank_count_sensitivity_score'))}; "
        f"mapping_sensitivity_score="
        f"{fmt(metric_value(row, 'mapping_sensitivity_score'))}; "
        f"queue_delay_ratio={fmt(metric_value(row, 'queue_delay_ratio'))}; "
        f"service_delay_ratio={fmt(metric_value(row, 'service_delay_ratio'))}; "
        f"best={fmt(best_knobs.get('bank_count_best'))}/"
        f"{best_knobs.get('address_mapping_best', 'unknown')}; "
        f"signals=locality:{signals['locality_signal']},"
        f"queueing:{signals['queueing_signal']},"
        f"service:{signals['service_signal']},"
        f"bank_conflict:{signals['bank_conflict_signal']}"
    )


def build_project_l_recommendation_rows(summary_rows, sweep_rows):
    best_by_workload = project_l_best_sweep_by_workload(sweep_rows)
    rows = []
    for row in summary_rows:
        workload = row.get("workload", "")
        best_knobs = best_by_workload.get(
            workload,
            {"bank_count_best": None, "address_mapping_best": "unknown"},
        )
        signals = {
            "locality_signal": project_l_locality_signal(row),
            "queueing_signal": project_l_queueing_signal(row),
            "service_signal": project_l_service_signal(row),
            "bank_conflict_signal": project_l_bank_conflict_signal(row),
        }
        action = project_l_action_for(row, best_knobs, signals)
        priority = project_l_recommendation_priority(action, row, signals)
        rows.append(
            {
                "workload": workload,
                "pattern_class": row.get("pattern_class", ""),
                "primary_bottleneck": row.get("primary_bottleneck", ""),
                "confidence": row.get("confidence", ""),
                "recommended_action": action,
                "recommendation_priority": priority,
                "evidence_summary": project_l_evidence_summary(
                    row, best_knobs, signals
                ),
                "bank_count_best": best_knobs.get("bank_count_best"),
                "address_mapping_best": best_knobs.get("address_mapping_best"),
                "bank_count_sensitivity_score": metric_value(
                    row, "bank_count_sensitivity_score"
                ),
                "mapping_sensitivity_score": metric_value(
                    row, "mapping_sensitivity_score"
                ),
                **signals,
                "claim_boundary": PROJECT_L_CLAIM_BOUNDARY,
            }
        )
    return rows


def write_project_l_report(path, recommendation_rows, generated_paths):
    path = repo_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    table_headers = (
        "workload",
        "primary_bottleneck",
        "recommended_action",
        "recommendation_priority",
        "evidence_summary",
    )
    lines = [
        "# Project L Evidence-Driven Memory Architecture Recommendation Report",
        "",
        "状态：generated recommendation layer over Project K evidence。",
        "",
        "## Architecture Story",
        "",
        "Project L keeps the Project K model boundary intact and adds a lightweight "
        "recommendation layer above the generated workload metrics. It converts "
        "trace-derived and model-derived evidence into bounded memory-architecture "
        "hypotheses: bank parallelism, address mapping, locality / tiling, "
        "queueing pressure, service latency, or continued observation when the "
        "evidence is not strong enough.",
        "",
        "This layer does not change Project E or the underlying SystemC/TLM model. "
        "It reads Project K summary and sweep evidence, applies deterministic "
        "heuristics, and writes auditable CSV / markdown artifacts for early "
        "architecture tradeoff discussion.",
        "",
        "## Workload-Level Recommendations",
        "",
    ]
    lines.extend(
        markdown_table(
            table_headers,
            ([fmt(row.get(field)) for field in table_headers] for row in recommendation_rows),
        )
    )
    lines.extend(
        [
            "",
            "## Rule Logic",
            "",
            "- Low Project K confidence keeps the workload in observation mode.",
            "- High bank-conflict evidence plus high bank-count sensitivity maps "
            "to `increase_bank_parallelism`.",
            "- High mapping sensitivity maps to `change_address_mapping` only when "
            "the best observed mapping differs from the current baseline.",
            "- Weak locality evidence maps to `improve_locality_or_tiling`.",
            "- Queue delay clearly above service delay maps to "
            "`reduce_queueing_pressure`.",
            "- Service delay clearly above queue delay, with low bank-conflict "
            "evidence, maps to `reduce_target_service_latency`.",
            "- If no single rule dominates, the recommendation stays "
            "`no_single_dominant_action`.",
            "",
            "## Generated Outputs",
            "",
        ]
    )
    for label, generated_path in generated_paths:
        lines.append(f"- `{label}`: `{display_path(generated_path)}`")
    lines.extend(
        [
            "",
            "## Acceptance Result",
            "",
            f"- `recommendation_rows={len(recommendation_rows)}`",
            "- `claim_boundary=PASS`",
            f"- `schema_version={PROJECT_L_SCHEMA_VERSION}`",
            "",
            "## Claim Boundary / Unsupported Claims",
            "",
            "- This is not cycle-accurate simulation.",
            "- This is not silicon validation.",
            "- This is not GPU simulation.",
            "- This is not real GEMM / Transformer / attention performance claim.",
            "- This is not AXI / CHI protocol compliance.",
            "- This is not production signoff.",
            "- This layer does not claim PMU / perf / Nsight correlation.",
            "",
            "## Portfolio / Interview Narrative",
            "",
            "Project L is an evidence-driven architecture recommendation layer. "
            "It shows how workload traces, model-derived metrics, bank-conflict "
            "proxies, queueing symptoms, service-latency split, and sweep "
            "sensitivity can be interpreted as bounded design hypotheses.",
            "",
            "The useful interview framing is architecture decision support, not "
            "absolute prediction. The output helps explain why an early-stage "
            "SoC architecture or performance modeling discussion might prioritize "
            "more modeled bank parallelism, a different address mapping, locality "
            "improvement, queue-pressure reduction, service-latency work, or more "
            "measurement before recommending a design change.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def validate_project_l_acceptance(recommendation_path, report_path, recommendation_rows):
    errors = []
    if len(ALL_WORKLOADS) != PROJECT_L_EXPECTED_TOTAL_WORKLOADS:
        errors.append(
            f"Project L workload count {len(ALL_WORKLOADS)} "
            f"!= {PROJECT_L_EXPECTED_TOTAL_WORKLOADS}"
        )
    if len(recommendation_rows) != PROJECT_L_EXPECTED_RECOMMENDATION_ROWS:
        errors.append(
            "Project L recommendation rows "
            f"{len(recommendation_rows)} "
            f"!= {PROJECT_L_EXPECTED_RECOMMENDATION_ROWS}"
        )

    missing = missing_fields(
        csv_header(recommendation_path), PROJECT_L_RECOMMENDATION_FIELDS
    )
    if missing:
        errors.append(
            "Project L recommendation CSV missing fields: " + ", ".join(missing)
        )

    allowed_actions = set(PROJECT_L_ALLOWED_RECOMMENDED_ACTIONS)
    allowed_priorities = set(PROJECT_L_ALLOWED_RECOMMENDATION_PRIORITIES)
    for row in recommendation_rows:
        if row.get("recommended_action") not in allowed_actions:
            errors.append(
                "Project L row has invalid recommended_action: "
                f"{row.get('workload')}={row.get('recommended_action')}"
            )
        if row.get("recommendation_priority") not in allowed_priorities:
            errors.append(
                "Project L row has invalid recommendation_priority: "
                f"{row.get('workload')}={row.get('recommendation_priority')}"
            )
        if row.get("claim_boundary") != PROJECT_L_CLAIM_BOUNDARY:
            errors.append(
                "Project L row has mismatched claim_boundary: "
                f"{row.get('workload')}={row.get('claim_boundary')}"
            )

    report_path = repo_path(report_path)
    if not report_path.exists():
        errors.append(f"Project L report not found: {display_path(report_path)}")
    else:
        report_text = report_path.read_text(encoding="utf-8")
        required_sections = (
            "## Architecture Story",
            "## Workload-Level Recommendations",
            "## Rule Logic",
            "## Claim Boundary / Unsupported Claims",
            "## Portfolio / Interview Narrative",
        )
        missing_sections = [
            section for section in required_sections if section not in report_text
        ]
        if missing_sections:
            errors.append(
                "Project L report missing sections: " + ", ".join(missing_sections)
            )
        missing_claim_markers = [
            marker
            for marker in PROJECT_L_REQUIRED_UNSUPPORTED_CLAIM_MARKERS
            if marker not in report_text
        ]
        if missing_claim_markers:
            errors.append(
                "Project L report missing unsupported-claim markers: "
                + ", ".join(missing_claim_markers)
            )
        forbidden_hits = forbidden_affirmative_claim_hits(report_text)
        if forbidden_hits:
            errors.append(
                "Project L report has possible affirmative forbidden claim(s): "
                + "; ".join(forbidden_hits)
            )

    if errors:
        raise DemoError("Project L acceptance self-check failed: " + " | ".join(errors))


def main():
    args = parse_args()
    binary = ensure_binary(args.binary, args.no_build)
    input_dir = repo_path(args.input_dir)
    output_dir = repo_path(args.output_dir)
    project_l_output_dir = repo_path(args.project_l_output_dir)

    remove_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    remove_path(project_l_output_dir)
    project_l_output_dir.mkdir(parents=True, exist_ok=True)

    traces, metadata_by_workload = generate_workload_traces(input_dir)
    features_by_workload = {
        feature["workload"]: feature
        for feature in (
            characterize_trace(
                trace,
                metadata_by_workload.get(Path(trace).stem, {}),
            )
            for trace in traces
        )
    }

    sweep_rows = []
    baseline_model_metrics = None
    for address_mapping in ADDRESS_MAPPING_SWEEP:
        for bank_count in BANK_COUNT_SWEEP:
            run_dir = (
                output_dir
                / "model_runs"
                / address_mapping
                / f"bank_count_{bank_count}"
            )
            summary_rows, trace_rows = run_project_e(
                binary,
                traces,
                run_dir,
                bank_count,
                address_mapping,
            )
            model_metrics = summarize_model_metrics(summary_rows, trace_rows)
            if (
                bank_count == BANK_COUNT_SWEEP[0]
                and address_mapping == DEFAULT_ADDRESS_MAPPING
            ):
                baseline_model_metrics = model_metrics
            for workload in ALL_WORKLOADS:
                features = features_by_workload[workload]
                metrics = model_metrics[workload]
                attribution = attribution_for(features, metrics)
                sweep_rows.append(
                    {
                        "workload": workload,
                        "bank_count": bank_count,
                        "address_mapping": address_mapping,
                        **metrics,
                        "primary_bottleneck": attribution["primary_bottleneck"],
                        "confidence": attribution["confidence"],
                    }
                )

    if baseline_model_metrics is None:
        raise DemoError("baseline bank_count run did not produce model metrics")

    add_sweep_delta_pct(sweep_rows)
    sensitivity_by_workload = compute_sensitivity_by_workload(sweep_rows)
    summary_rows = build_summary_rows(
        features_by_workload,
        baseline_model_metrics,
        sensitivity_by_workload,
    )

    summary_path = write_csv(
        output_dir / "project_k_workload_bottleneck_summary.csv",
        SUMMARY_FIELDS,
        summary_rows,
    )
    sweep_path = write_csv(
        output_dir / "project_k_what_if_sweep_summary.csv",
        SWEEP_FIELDS,
        sweep_rows,
    )
    report_path = write_generated_report(
        output_dir / "project_k_report.md",
        summary_rows,
        sweep_rows,
        (
            ("workload_bottleneck_summary", summary_path),
            ("what_if_sweep_summary", sweep_path),
            ("generated_report", output_dir / "project_k_report.md"),
        ),
    )

    summary_row_count = len(summary_rows)
    sweep_row_count = len(sweep_rows)
    validate_project_k_acceptance(
        summary_path,
        sweep_path,
        report_path,
        summary_rows,
        sweep_rows,
    )

    recommendation_rows = build_project_l_recommendation_rows(
        summary_rows, sweep_rows
    )
    recommendation_path = write_csv(
        project_l_output_dir / "project_l_recommendations.csv",
        PROJECT_L_RECOMMENDATION_FIELDS,
        recommendation_rows,
    )
    project_l_report_path = write_project_l_report(
        project_l_output_dir / "project_l_recommendation_report.md",
        recommendation_rows,
        (
            ("recommendations", recommendation_path),
            (
                "recommendation_report",
                project_l_output_dir / "project_l_recommendation_report.md",
            ),
            ("project_k_summary_input", summary_path),
            ("project_k_sweep_input", sweep_path),
        ),
    )
    validate_project_l_acceptance(
        recommendation_path,
        project_l_report_path,
        recommendation_rows,
    )

    print("[demo-project-k] outputs")
    print(f"  - generated inputs: {display_path(input_dir)}")
    print(f"  - summary: {display_path(summary_path)}")
    print(f"  - sweep summary: {display_path(sweep_path)}")
    print(f"  - generated report: {display_path(report_path)}")
    print(f"  - Project L recommendations: {display_path(recommendation_path)}")
    print(f"  - Project L report: {display_path(project_l_report_path)}")
    print("Project K Workload-Aware Memory Bottleneck Characterization MVP PASS")
    print(f"core_workloads={len(CORE_WORKLOADS)}")
    print(f"optional_synthetic_patterns={len(OPTIONAL_SYNTHETIC_PATTERNS)}")
    print(f"total_workloads={len(ALL_WORKLOADS)}")
    print(f"summary_rows={summary_row_count}")
    print(f"sweep_rows={sweep_row_count}")
    print("claim_boundary=PASS")
    print(f"schema_version={PROJECT_K_SCHEMA_VERSION}")
    print(
        "scope: synthetic traces over Project E simplified banked memory model; "
        "no GPU simulation, no real GEMM/attention performance, no PMU/perf/Nsight, "
        "no silicon validation, no AXI/CHI protocol claim."
    )
    print("Project L Evidence-Driven Memory Architecture Recommendation Lab PASS")
    print(f"recommendation_rows={len(recommendation_rows)}")
    print(f"schema_version={PROJECT_L_SCHEMA_VERSION}")
    print("claim_boundary=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DemoError as error:
        print(f"[demo-project-k] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
