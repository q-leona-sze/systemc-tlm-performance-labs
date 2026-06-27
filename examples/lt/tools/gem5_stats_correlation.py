#!/usr/bin/env python3

import argparse
import csv
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SEQUENTIAL_STATS = Path(
    "examples/lt/results/gem5_se_trace_extraction/sequential/stats.txt"
)
DEFAULT_STRIDE_STATS = Path(
    "examples/lt/results/gem5_se_trace_extraction/stride/stats.txt"
)
DEFAULT_REPLAY_SUMMARY_CANDIDATES = (
    Path("examples/lt/results/gem5_trace_replay_lab/summary.csv"),
    Path("examples/lt/results/cpp_trace_replay_lab/summary.csv"),
    Path("examples/lt/results/project_e_banked_memory_controller/summary.csv"),
)
DEFAULT_PROJECT_E_SUMMARY = Path(
    "examples/lt/results/project_e_banked_memory_controller/summary.csv"
)
DEFAULT_OUTPUT_DIR = Path("examples/lt/results/project_f_gem5_stats_correlation")
NA_VALUE = "NA"

GEM5_STATS = {
    "simTicks": "gem5_sim_ticks",
    "simSeconds": "gem5_sim_seconds",
    "simInsts": "gem5_sim_insts",
    "simOps": "gem5_sim_ops",
    "hostSeconds": "gem5_host_seconds",
}

SUMMARY_FIELDS = (
    "workload",
    "gem5_sim_ticks",
    "gem5_sim_seconds",
    "gem5_sim_insts",
    "gem5_sim_ops",
    "gem5_host_seconds",
    "replay_avg_latency_ns",
    "replay_p99_latency_ns",
    "bank_conflict_ratio_pct",
    "project_e_avg_latency_ns",
    "project_e_p99_latency_ns",
    "project_e_avg_queue_occupancy",
    "project_e_bank_utilization_pct",
    "trend_notes",
)


class CorrelationError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Generate the Project F gem5 stats vs replay trend-correlation "
            "summary and report."
        )
    )
    parser.add_argument(
        "--sequential-stats",
        default=DEFAULT_SEQUENTIAL_STATS,
        type=Path,
        help="gem5 SE stats.txt for the sequential workload.",
    )
    parser.add_argument(
        "--stride-stats",
        default=DEFAULT_STRIDE_STATS,
        type=Path,
        help="gem5 SE stats.txt for the stride workload.",
    )
    parser.add_argument(
        "--replay-summary",
        type=Path,
        help=(
            "Replay summary.csv. If omitted, the tool checks Project C replay, "
            "Project D C++ replay, then Project E in that order."
        ),
    )
    parser.add_argument(
        "--project-e-summary",
        default=DEFAULT_PROJECT_E_SUMMARY,
        type=Path,
        help="Optional Project E summary.csv used for queueing-model columns.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        type=Path,
        help="Output directory for correlation_summary.csv and correlation_report.md.",
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


def require_file(path, label, hint):
    path = repo_path(path)
    if not path.exists():
        raise CorrelationError(
            f"{label} not found: {display_path(path)}\n{hint}"
        )
    if not path.is_file():
        raise CorrelationError(f"{label} is not a file: {display_path(path)}")
    return path


def parse_numeric_token(value, source_path, line_number, stat_name):
    try:
        float(value)
    except ValueError as error:
        raise CorrelationError(
            f"{display_path(source_path)}:{line_number}: {stat_name} is not numeric: {value}"
        ) from error
    return value


def parse_gem5_stats(stats_path, workload):
    hint = (
        "Run Project C gem5 SE extraction first so the gem5 output directory "
        "contains stats.txt, simout/run_stdout.txt, and conversion logs."
    )
    stats_path = require_file(stats_path, f"{workload} gem5 stats.txt", hint)
    found = {field: NA_VALUE for field in GEM5_STATS.values()}
    with stats_path.open(encoding="utf-8") as stats_file:
        for line_number, raw_line in enumerate(stats_file, start=1):
            line = raw_line.split("#", 1)[0].strip()
            if not line or line.startswith("-"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            stat_name, stat_value = parts[0], parts[1]
            if stat_name in GEM5_STATS:
                found[GEM5_STATS[stat_name]] = parse_numeric_token(
                    stat_value,
                    stats_path,
                    line_number,
                    stat_name,
                )

    missing = [field for field, value in found.items() if value == NA_VALUE]
    found["_missing_gem5_stats"] = ", ".join(missing)
    return found


def replay_summary_hint():
    checked = "\n".join(
        f"  - {display_path(repo_path(path))}"
        for path in DEFAULT_REPLAY_SUMMARY_CANDIDATES
    )
    return (
        "Replay summary.csv not found. Checked:\n"
        f"{checked}\n"
        "Run one of these first:\n"
        "  python3 examples/lt/tools/run_trace_replay_lab.py "
        "--trace examples/lt/traces/gem5_sequential_trace.csv "
        "--trace examples/lt/traces/gem5_stride_trace.csv "
        "--output-dir examples/lt/results/gem5_trace_replay_lab\n"
        "  python3 examples/lt/tools/demo_cpp_trace_replay_lab.py\n"
        "  python3 examples/lt/tools/demo_banked_memory_controller_lab.py"
    )


def select_replay_summary(explicit_path):
    if explicit_path:
        path = repo_path(explicit_path)
        return require_file(path, "replay summary.csv", replay_summary_hint())

    for candidate in DEFAULT_REPLAY_SUMMARY_CANDIDATES:
        path = repo_path(candidate)
        if path.exists():
            return path

    raise CorrelationError(replay_summary_hint())


def read_csv_rows(csv_path, label):
    csv_path = repo_path(csv_path)
    if not csv_path.exists():
        raise CorrelationError(f"{label} not found: {display_path(csv_path)}")

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        rows = list(reader)

    if not fieldnames:
        raise CorrelationError(f"{label} has no CSV header: {display_path(csv_path)}")
    if not rows:
        raise CorrelationError(f"{label} is empty: {display_path(csv_path)}")
    return fieldnames, rows


def canonical_workload(value):
    text = str(value or "").strip().lower()
    if "stride" in text:
        return "stride"
    if "sequential" in text:
        return "sequential"
    return ""


def replay_row_score(row):
    name = (row.get("workload_name") or row.get("workload") or "").lower()
    if "gem5" in name:
        return 4
    if name.endswith("_scan") or "sequential_scan" in name or "stride_scan" in name:
        return 3
    if name.startswith("sample_"):
        return 1
    return 2


def rows_by_workload(rows, name_fields):
    selected = {}
    scores = {}
    for row in rows:
        workload_name = ""
        for field in name_fields:
            if row.get(field):
                workload_name = row[field]
                break
        workload = canonical_workload(workload_name)
        if not workload:
            continue
        score = replay_row_score(row)
        if workload not in selected or score > scores[workload]:
            selected[workload] = row
            scores[workload] = score
    return selected


def load_replay_summary(summary_path):
    _, rows = read_csv_rows(summary_path, "replay summary.csv")
    by_workload = rows_by_workload(rows, ("workload_name", "workload"))
    missing = [workload for workload in ("sequential", "stride") if workload not in by_workload]
    if missing:
        raise CorrelationError(
            f"{display_path(summary_path)} missing workloads: {', '.join(missing)}"
        )
    return by_workload


def load_project_e_summary(summary_path):
    summary_path = repo_path(summary_path)
    hint = (
        "Run Project E first:\n"
        "  python3 examples/lt/tools/demo_banked_memory_controller_lab.py"
    )
    require_file(summary_path, "Project E summary.csv", hint)
    _, rows = read_csv_rows(summary_path, "Project E summary.csv")
    return rows_by_workload(rows, ("workload", "workload_name")), ""


def get_value(row, *fields):
    for field in fields:
        value = row.get(field)
        if value not in (None, ""):
            return str(value)
    return NA_VALUE


def missing_groups(row, field_groups):
    missing = []
    for label, fields in field_groups:
        if get_value(row, *fields) == NA_VALUE:
            missing.append(label)
    return missing


def as_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def trend_label(stride_value, sequential_value):
    stride_number = as_float(stride_value)
    sequential_number = as_float(sequential_value)
    if stride_number is None or sequential_number is None:
        return "not available"
    if stride_number > sequential_number:
        return "higher"
    if stride_number < sequential_number:
        return "lower"
    return "flat"


def build_summary_rows(stats_by_workload, replay_by_workload, project_e_by_workload):
    rows = []
    for workload in ("sequential", "stride"):
        replay = replay_by_workload[workload]
        project_e = project_e_by_workload.get(workload, {})
        missing = []
        missing_stats = stats_by_workload[workload].get("_missing_gem5_stats", "")
        if missing_stats:
            missing.append(f"missing gem5 stats: {missing_stats}")
        replay_missing = missing_groups(
            replay,
            (
                ("replay_avg_latency_ns", ("avg_latency_ns", "avg_delay_ns")),
                ("replay_p99_latency_ns", ("p99_latency_ns", "p99_delay_ns")),
                ("bank_conflict_ratio_pct", ("bank_conflict_ratio_pct",)),
            ),
        )
        if replay_missing:
            missing.append("missing replay fields: " + ", ".join(replay_missing))
        project_e_missing = missing_groups(
            project_e,
            (
                ("project_e_avg_latency_ns", ("avg_latency_ns",)),
                ("project_e_p99_latency_ns", ("p99_latency_ns",)),
                ("project_e_avg_queue_occupancy", ("avg_queue_occupancy",)),
                ("project_e_bank_utilization_pct", ("bank_utilization_pct",)),
            ),
        )
        if project_e_missing:
            missing.append("missing Project E fields: " + ", ".join(project_e_missing))
        row = {
            "workload": workload,
            **{
                field: stats_by_workload[workload].get(field, NA_VALUE)
                for field in GEM5_STATS.values()
            },
            "replay_avg_latency_ns": get_value(
                replay,
                "avg_latency_ns",
                "avg_delay_ns",
            ),
            "replay_p99_latency_ns": get_value(
                replay,
                "p99_latency_ns",
                "p99_delay_ns",
            ),
            "bank_conflict_ratio_pct": get_value(replay, "bank_conflict_ratio_pct"),
            "project_e_avg_latency_ns": get_value(project_e, "avg_latency_ns"),
            "project_e_p99_latency_ns": get_value(project_e, "p99_latency_ns"),
            "project_e_avg_queue_occupancy": get_value(
                project_e,
                "avg_queue_occupancy",
            ),
            "project_e_bank_utilization_pct": get_value(
                project_e,
                "bank_utilization_pct",
            ),
            "_missing_notes": "; ".join(missing),
            "trend_notes": "",
        }
        rows.append(row)

    sequential, stride = rows
    sequential_notes = ["baseline row for sequential-vs-stride trend comparison"]
    if sequential["_missing_notes"]:
        sequential_notes.append(sequential["_missing_notes"])
    sequential["trend_notes"] = "; ".join(sequential_notes)
    stride_notes = [
        "vs sequential: "
        f"gem5_sim_ticks {trend_label(stride['gem5_sim_ticks'], sequential['gem5_sim_ticks'])}; "
        f"replay_avg_latency_ns {trend_label(stride['replay_avg_latency_ns'], sequential['replay_avg_latency_ns'])}; "
        f"bank_conflict_ratio_pct {trend_label(stride['bank_conflict_ratio_pct'], sequential['bank_conflict_ratio_pct'])}; "
        f"project_e_avg_latency_ns {trend_label(stride['project_e_avg_latency_ns'], sequential['project_e_avg_latency_ns'])}"
    ]
    if stride["_missing_notes"]:
        stride_notes.append(stride["_missing_notes"])
    stride["trend_notes"] = (
        "; ".join(stride_notes)
    )
    return rows


def markdown_cell(value):
    return str(value).replace("\n", " ").replace("|", "\\|")


def markdown_table(headers, rows):
    lines = [
        "| " + " | ".join(markdown_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(markdown_cell(row.get(header, "")) for header in headers)
            + " |"
        )
    return lines


def trend_sentence(rows, field, label):
    sequential, stride = rows
    direction = trend_label(stride.get(field), sequential.get(field))
    if direction == "higher":
        relation = "高于"
    elif direction == "lower":
        relation = "低于"
    elif direction == "flat":
        relation = "持平于"
    else:
        relation = "无法比较"
    return (
        f"- `{label}`：`stride` 为 `{stride.get(field, '')}`，"
        f"`sequential` 为 `{sequential.get(field, '')}`，趋势为 {relation} baseline。"
    )


def write_summary_csv(output_dir, rows):
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "correlation_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in SUMMARY_FIELDS})
    return summary_path


def write_report(output_dir, rows, source_info, project_e_note):
    report_path = output_dir / "correlation_report.md"
    lines = [
        "# Project F：gem5 Stats Trend Correlation Report",
        "",
        "## Current",
        "",
        "Project F 当前是一个 file-based qualitative / trend-level correlation report。"
        "它把 gem5 SE `stats.txt` 中的 run-level stats，与 replay model / Project E "
        "`summary.csv` 中的 architecture-level metrics 放到同一张表里，用于解释 "
        "`sequential` 和 `stride` workload 的趋势是否一致。",
        "",
        "当前产物链路是：",
        "",
        "```text",
        "gem5 SE stats.txt",
        "+ replay summary.csv",
        "+ Project E summary.csv",
        "-> correlation_summary.csv",
        "-> correlation_report.md",
        "```",
        "",
        "## Inputs",
        "",
        f"- sequential gem5 stats: `{source_info['sequential_stats']}`",
        f"- stride gem5 stats: `{source_info['stride_stats']}`",
        f"- replay summary: `{source_info['replay_summary']}`",
        f"- Project E summary: `{source_info['project_e_summary']}`",
    ]
    if project_e_note:
        lines.append(f"- Project E note: {project_e_note}")

    lines.extend(
        [
            "",
            "## Summary",
            "",
        ]
    )
    lines.extend(markdown_table(SUMMARY_FIELDS, rows))
    lines.extend(
        [
            "",
            "## Trend Interpretation",
            "",
            trend_sentence(rows, "gem5_sim_ticks", "gem5_sim_ticks"),
            trend_sentence(rows, "gem5_host_seconds", "gem5_host_seconds"),
            trend_sentence(rows, "replay_avg_latency_ns", "replay_avg_latency_ns"),
            trend_sentence(rows, "replay_p99_latency_ns", "replay_p99_latency_ns"),
            trend_sentence(rows, "bank_conflict_ratio_pct", "bank_conflict_ratio_pct"),
            trend_sentence(rows, "project_e_avg_latency_ns", "project_e_avg_latency_ns"),
            trend_sentence(rows, "project_e_p99_latency_ns", "project_e_p99_latency_ns"),
            trend_sentence(
                rows,
                "project_e_avg_queue_occupancy",
                "project_e_avg_queue_occupancy",
            ),
            "",
            "`stride` workload 在 replay model 中通常会比 `sequential` 显示更高的 "
            "`bank_conflict_ratio_pct` 和 replay latency；Project E 进一步把这个趋势解释成 "
            "bank pressure、queue occupancy 和 tail latency 的变化。gem5 `stats.txt` 在这里"
            "作为外部 SE run-level 参照，用来确认两个 workload 来自同一类外部执行流，并观察 "
            "`simTicks`、`simSeconds`、`simInsts`、`simOps` 和可选 `hostSeconds` 的 "
            "run-level 差异。",
            "",
            "## Why Qualitative",
            "",
            "当前 correlation 只能称为 qualitative / trend-level，原因是三类时间语义并不相同：",
            "",
            "- gem5 `simTicks` / `simSeconds` 是外部 gem5 SE run 的模拟统计。",
            "- replay `avg_latency_ns` / `p99_latency_ns` 是当前 LT replay model 或 Project E "
            "queueing model 的架构级指标。",
            "- normalized trace 的 `timestamp_ns` 只是 issue-time / ordering hint，用来稳定排序"
            "和重放 transaction，不是 gem5 timing，也不是 cycle timing。",
            "",
            "因此，本报告只比较 `sequential` 和 `stride` 的趋势是否朝同一方向变化，不比较"
            "绝对 cycle、不做误差百分比，也不声称 gem5 timing 与 replay latency 已校准。",
            "",
            "`NA` 表示对应输入文件中没有该字段。Project F 会在 `trend_notes` 中记录缺失"
            "字段原因；只有输入文件本身缺失、CSV 为空、或无法找到 `sequential` / `stride` "
            "workload 时才会失败并提示先运行对应 demo。",
            "",
            "## Supported",
            "",
            "- 解析 gem5 `stats.txt` 中的 `simTicks`、`simSeconds`、`simInsts`、`simOps`，"
            "以及可选 `hostSeconds`。",
            "- 读取 Project B / C / D replay `summary.csv`，优先级为 gem5 trace replay、"
            "C++ replay、Project E fallback。",
            "- 读取 Project E `summary.csv` 中的 queueing / utilization 指标。",
            "- 生成 `correlation_summary.csv` 和 `correlation_report.md`。",
            "",
            "## Not Supported",
            "",
            "- 不做 gem5 live co-simulation。",
            "- 不声称 cycle accuracy。",
            "- 不声称 RTL correlation、silicon correlation 或 profiler correlation。",
            "- 不声称 AXI、CHI、NoC、JEDEC DRAM 或 production interconnect compliance。",
            "- 不把 normalized `timestamp_ns` 当成 gem5 tick、gem5 cycle 或硬件时间。",
            "",
            "## Future Work",
            "",
            "后续如果要扩展到 profiler / hardware counters / RTL / silicon correlation，需要先增加"
            "更严格的对齐和校准证据：",
            "",
            "- 在 workload 中加入 region markers，把 gem5 stats、profiler counters、RTL trace "
            "和 replay trace 对齐到同一段代码区间。",
            "- 保留 raw gem5 tick / event index / memory event count，明确每个字段的时间语义。",
            "- 引入 profiler 或 hardware counters 时，单独记录采样窗口、counter 名称和采样误差。",
            "- 引入 RTL / silicon 数据时，定义 model version、workload binary hash、trace hash、"
            "校准参数和 error budget。",
            "- 只有完成 calibration dataset 和误差解释后，才能讨论 quantitative correlation；"
            "在此之前仍只称为 trend-level correlation。",
            "",
            "## Reproduce",
            "",
            "```bash",
            "python3 examples/lt/tools/demo_cpp_trace_replay_lab.py",
            "python3 examples/lt/tools/demo_banked_memory_controller_lab.py",
            "python3 examples/lt/tools/demo_gem5_stats_correlation_lab.py",
            "```",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main():
    args = parse_args()
    sequential_stats = repo_path(args.sequential_stats)
    stride_stats = repo_path(args.stride_stats)
    replay_summary = select_replay_summary(args.replay_summary)
    project_e_summary = repo_path(args.project_e_summary)
    output_dir = repo_path(args.output_dir)

    stats_by_workload = {
        "sequential": parse_gem5_stats(sequential_stats, "sequential"),
        "stride": parse_gem5_stats(stride_stats, "stride"),
    }
    replay_by_workload = load_replay_summary(replay_summary)
    project_e_by_workload, project_e_note = load_project_e_summary(project_e_summary)
    rows = build_summary_rows(
        stats_by_workload,
        replay_by_workload,
        project_e_by_workload,
    )

    summary_path = write_summary_csv(output_dir, rows)
    report_path = write_report(
        output_dir,
        rows,
        {
            "sequential_stats": display_path(sequential_stats),
            "stride_stats": display_path(stride_stats),
            "replay_summary": display_path(replay_summary),
            "project_e_summary": display_path(project_e_summary),
        },
        project_e_note,
    )

    print("[project-f] outputs")
    print(f"  - summary: {display_path(summary_path)}")
    print(f"  - report: {display_path(report_path)}")
    print("[project-f] Project F gem5 stats trend correlation report PASS")
    print(
        "[project-f] scope: file-based qualitative trend report; no live "
        "gem5-SystemC co-simulation, no cycle-accuracy claim, no RTL/silicon/profiler "
        "correlation claim."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, CorrelationError) as error:
        print(f"[project-f] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
