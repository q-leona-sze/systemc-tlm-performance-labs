#!/usr/bin/env python3

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONVERTER = Path("examples/lt/tools/convert_gem5_se_trace.py")


class RunError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run an external gem5 SE workload and convert Project C simout "
            "markers into a Project B normalized trace CSV."
        )
    )
    parser.add_argument("--gem5-binary", required=True, type=Path)
    parser.add_argument("--gem5-config", required=True, type=Path)
    parser.add_argument("--workload", required=True, type=Path)
    parser.add_argument("--workload-name", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--normalized-output", required=True, type=Path)
    parser.add_argument("--converter", default=DEFAULT_CONVERTER, type=Path)
    parser.add_argument("--initiator-id", default="101")
    parser.add_argument("--timestamp-step-ns", default=100.0, type=float)
    parser.add_argument("--size-bytes", default=4, type=int)
    parser.add_argument("--debug-flags", default="")
    parser.add_argument(
        "--gem5-arg",
        action="append",
        default=[],
        help="Extra argument passed before the gem5 config. Can be repeated.",
    )
    parser.add_argument(
        "--config-arg",
        action="append",
        default=[],
        help="Extra argument passed after the gem5 config. Can be repeated.",
    )
    parser.add_argument(
        "--workload-arg",
        action="append",
        default=[],
        help="Workload argument forwarded through se.py --options.",
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


def require_file(path, label):
    if not path.exists():
        raise RunError(f"{label} not found: {path}")
    if not path.is_file():
        raise RunError(f"{label} is not a file: {path}")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or "", encoding="utf-8")


def run_command(command, cwd, stdout_path, stderr_path):
    print("[gem5-se] run: " + shlex.join(str(part) for part in command))
    result = subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    write_text(stdout_path, result.stdout)
    write_text(stderr_path, result.stderr)
    if result.returncode != 0:
        raise RunError(
            f"command failed with exit code {result.returncode}: "
            + shlex.join(str(part) for part in command)
        )


def gem5_command(args):
    command = [
        args.gem5_binary,
        f"--outdir={args.output_dir}",
    ]
    if args.debug_flags:
        command.append(f"--debug-flags={args.debug_flags}")
        command.append("--debug-file=debug.log")
    command.extend(args.gem5_arg)
    command.append(args.gem5_config)
    command.extend(args.config_arg)
    command.append(f"--cmd={args.workload}")
    if args.workload_arg:
        command.append("--options=" + shlex.join(args.workload_arg))
    return command


def output_dir_listing(output_dir):
    if not output_dir.exists():
        return "output_dir does not exist"
    entries = sorted(path.name for path in output_dir.iterdir())
    if not entries:
        return "output_dir is empty"
    return ", ".join(entries)


def marker_source_path(output_dir):
    candidates = (
        output_dir / "simout",
        output_dir / "run_stdout.txt",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise RunError(
        "gem5 marker source not found; checked "
        f"{display_path(candidates[0])} and {display_path(candidates[1])}. "
        "Existing output_dir files: " + output_dir_listing(output_dir)
    )


def converter_command(args, marker_path):
    return [
        sys.executable,
        args.converter,
        "--input",
        marker_path,
        "--output",
        args.normalized_output,
        "--workload-name",
        args.workload_name,
        "--initiator-id",
        args.initiator_id,
        "--timestamp-step-ns",
        str(args.timestamp_step_ns),
        "--size-bytes",
        str(args.size_bytes),
        "--source",
        "gem5_se_simout",
    ]


def main():
    args = parse_args()
    args.gem5_binary = repo_path(args.gem5_binary)
    args.gem5_config = repo_path(args.gem5_config)
    args.workload = repo_path(args.workload)
    args.output_dir = repo_path(args.output_dir)
    args.normalized_output = repo_path(args.normalized_output)
    args.converter = repo_path(args.converter)

    require_file(args.gem5_binary, "gem5 binary")
    require_file(args.gem5_config, "gem5 SE config")
    require_file(args.workload, "workload binary")
    require_file(args.converter, "converter")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_command(
        gem5_command(args),
        REPO_ROOT,
        args.output_dir / "run_stdout.txt",
        args.output_dir / "run_stderr.txt",
    )

    marker_path = marker_source_path(args.output_dir)
    print(f"[gem5-se] marker source: {display_path(marker_path)}")

    run_command(
        converter_command(args, marker_path),
        REPO_ROOT,
        args.output_dir / "convert_stdout.txt",
        args.output_dir / "convert_stderr.txt",
    )

    if not args.normalized_output.exists():
        raise RunError(
            f"normalized trace not found: {display_path(args.normalized_output)}"
        )

    print("[gem5-se] outputs")
    print(f"  - marker source: {display_path(marker_path)}")
    print(f"  - normalized trace: {display_path(args.normalized_output)}")
    print(
        "[gem5-se] scope: offline gem5 SE trace producer; no live "
        "gem5-SystemC co-simulation and no cycle-accuracy claim."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RunError) as error:
        print(f"[gem5-se] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
