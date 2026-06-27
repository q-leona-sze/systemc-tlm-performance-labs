#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import os
import shutil
import subprocess
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional


class DemoError(Exception):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_repo_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return repo_root() / candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the examples/at smoke and arbitration demo."
    )
    parser.add_argument(
        "--binary",
        default="./build/examples/at/at",
        help="AT executable path. Relative paths are resolved from the repo root.",
    )
    parser.add_argument(
        "--output-dir",
        default="examples/at/results/arbitration_sweep",
        help="Arbitration sweep output directory.",
    )
    parser.add_argument(
        "--analysis-output",
        default="examples/at/results/analysis.txt",
        help="Path for the one-shot phase trace analyzer output.",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Pass --keep-going to the arbitration sweep runner.",
    )
    parser.add_argument(
        "--python",
        default="python3",
        help="Python command used to run analyzer and sweep scripts.",
    )
    return parser.parse_args()


def is_protected_path(path: Path) -> bool:
    root = repo_root()
    protected = {
        Path("/").resolve(),
        Path("/tmp").resolve(),
        root,
        root / "examples",
        root / "examples" / "at",
        root / "examples" / "at" / "results",
    }

    try:
        resolved = path.resolve()
    except FileNotFoundError:
        resolved = path.parent.resolve() / path.name

    return resolved in protected


def remove_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def remove_output_dir(path: Path) -> None:
    if not path.exists():
        return

    if not path.is_dir():
        raise DemoError(f"output path is not a directory: {path}")

    if is_protected_path(path):
        raise DemoError(f"refusing to delete protected output directory: {path}")

    shutil.rmtree(path)


def run_process(command: List[str], env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(repo_root()),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def require_binary(binary: Path) -> None:
    if not binary.exists():
        raise DemoError(f"AT binary not found: {binary}")

    if not os.access(binary, os.X_OK):
        raise DemoError(f"AT binary is not executable: {binary}")


def run_default_at(binary: Path, trace_path: Path) -> None:
    env = os.environ.copy()
    env.pop("AT_ARBITRATION_POLICY", None)

    result = run_process([str(binary)], env=env)
    if result.returncode != 0:
        message = f"AT binary failed with exit code {result.returncode}"
        if result.stderr.strip():
            message += f": {result.stderr.strip()}"
        raise DemoError(message)

    if not trace_path.exists():
        raise DemoError(f"AT binary did not produce trace: {trace_path}")


def write_analysis_output(path: Path, stdout: str, stderr: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = stdout
    if stderr:
        output += "\n[stderr]\n" + stderr
    path.write_text(output, encoding="utf-8")


def run_analyzer(python_cmd: str, trace_path: Path, analysis_output: Path) -> None:
    analyzer = repo_root() / "examples" / "at" / "tools" / "analyze_phase_trace.py"
    result = run_process(
        [
            python_cmd,
            str(analyzer),
            "--trace",
            str(trace_path),
            "--fail-on-sanity",
        ]
    )
    write_analysis_output(analysis_output, result.stdout, result.stderr)

    if result.returncode != 0:
        raise DemoError(
            f"phase trace analyzer failed with exit code {result.returncode}; "
            f"see {analysis_output}"
        )


def run_sweep(
    python_cmd: str, binary: Path, output_dir: Path, keep_going: bool
) -> None:
    sweep = repo_root() / "examples" / "at" / "tools" / "run_arbitration_sweep.py"
    command = [
        python_cmd,
        str(sweep),
        "--binary",
        str(binary),
        "--output-dir",
        str(output_dir),
    ]
    if keep_going:
        command.append("--keep-going")

    result = run_process(command)
    if result.returncode != 0:
        message = f"arbitration sweep failed with exit code {result.returncode}"
        if result.stderr.strip():
            message += f": {result.stderr.strip()}"
        raise DemoError(message)


def read_single_row_csv(path: Path, key_field: str) -> Dict[str, Dict[str, str]]:
    with path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None or key_field not in reader.fieldnames:
            raise DemoError(f"{path}: missing field {key_field}")
        return {row.get(key_field, ""): row for row in reader}


def parse_decimal(value: str) -> Optional[Decimal]:
    if value == "":
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


def average_latency_for_prefix(rows: List[Dict[str, str]], prefix: str) -> Optional[Decimal]:
    values = [
        parse_decimal(row.get("request_accept_latency_ns", ""))
        for row in rows
        if row.get("txn_id", "").startswith(prefix)
    ]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(len(values))


def format_decimal(value: Optional[Decimal]) -> str:
    if value is None:
        return "NA"
    return f"{value:.3f}"


def read_timeline(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        required = {"txn_id", "request_accept_latency_ns"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise DemoError(f"{path}: missing timeline fields")
        return list(reader)


def print_outputs(trace_path: Path, analysis_output: Path, output_dir: Path) -> None:
    print("[demo] Output files:")
    print(f"[demo]   phase_trace: {trace_path}")
    print(f"[demo]   analysis: {analysis_output}")
    print(f"[demo]   sweep_summary: {output_dir / 'summary.csv'}")
    print(f"[demo]   sweep_comparison: {output_dir / 'comparison.md'}")


def print_conclusions(output_dir: Path) -> None:
    summary_path = output_dir / "summary.csv"
    comparison_path = output_dir / "comparison.md"
    summary = read_single_row_csv(summary_path, "policy")

    fifo = summary.get("fifo")
    if fifo is None:
        raise DemoError(f"{summary_path}: missing fifo row")

    priority101 = read_timeline(output_dir / "priority_101" / "timeline.csv")
    priority102 = read_timeline(output_dir / "priority_102" / "timeline.csv")

    p101_101_avg = average_latency_for_prefix(priority101, "101")
    p101_102_avg = average_latency_for_prefix(priority101, "102")
    p102_102_avg = average_latency_for_prefix(priority102, "102")
    p102_101_avg = average_latency_for_prefix(priority102, "101")

    if not comparison_path.exists():
        raise DemoError(f"comparison.md not generated: {comparison_path}")

    print("[demo] Key conclusions:")
    print(
        "[demo]   fifo complete_transactions = "
        f"{fifo.get('complete_transactions', 'NA')}"
    )
    print(
        "[demo]   priority_101 accepts 101xxx faster: "
        f"101xxx avg={format_decimal(p101_101_avg)} ns, "
        f"102xxx avg={format_decimal(p101_102_avg)} ns"
    )
    print(
        "[demo]   priority_102 accepts 102xxx faster: "
        f"102xxx avg={format_decimal(p102_102_avg)} ns, "
        f"101xxx avg={format_decimal(p102_101_avg)} ns"
    )
    print(f"[demo]   sweep comparison.md generated: {comparison_path}")


def main() -> int:
    args = parse_args()
    binary = resolve_repo_path(args.binary)
    output_dir = resolve_repo_path(args.output_dir)
    analysis_output = resolve_repo_path(args.analysis_output)
    trace_path = repo_root() / "phase_trace.csv"

    require_binary(binary)

    print("[demo] Cleaning old AT demo outputs")
    remove_file(trace_path)
    remove_file(analysis_output)
    remove_output_dir(output_dir)

    print("[demo] Running default AT smoke lab")
    run_default_at(binary, trace_path)
    default_trace = trace_path.read_bytes()

    print("[demo] Analyzing default phase_trace.csv")
    run_analyzer(args.python, trace_path, analysis_output)

    print("[demo] Running arbitration policy sweep")
    try:
        run_sweep(args.python, binary, output_dir, args.keep_going)
    finally:
        trace_path.write_bytes(default_trace)

    print_outputs(trace_path, analysis_output, output_dir)
    print_conclusions(output_dir)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("[demo] ERROR: interrupted", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"[demo] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
