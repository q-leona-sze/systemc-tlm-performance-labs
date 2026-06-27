# Project F：gem5 Stats Trend Correlation Report MVP

## Current

Project F 是 `examples/lt` 下的 qualitative / trend-level correlation report。它把
gem5 SE `stats.txt` 的 run-level stats，与现有 replay model / Project E
`summary.csv` 的 architecture-level metrics 放到同一张表里，用于说明
`sequential` vs `stride` workload 的趋势是否一致。

当前链路是：

```text
gem5 SE stats.txt
+ replay summary.csv
+ Project E summary.csv
-> correlation_summary.csv
-> correlation_report.md
```

Project F 不改变 Project B / C / D / E 的输出语义。Python 只负责 stats parsing、
summary joining 和 report generation，不承载 replay model 或 memory controller model。

## Goal

MVP 目标：

- 从 gem5 SE `stats.txt` 提取 `simTicks`、`simSeconds`、`simInsts`、`simOps`，
  并在存在时提取 `hostSeconds`。
- 从 replay `summary.csv` 提取 `avg_latency_ns`、`p99_latency_ns`、
  `bank_conflict_ratio_pct`。
- 从 Project E `summary.csv` 提取 queueing / utilization 指标。
- 生成面试可讲述的 `correlation_summary.csv` 和 `correlation_report.md`。
- 明确说明这只是 trend-level correlation，不是 cycle accuracy、RTL correlation、
  silicon correlation 或 profiler correlation。

## Inputs

默认 gem5 stats 输入：

```text
examples/lt/results/gem5_se_trace_extraction/sequential/stats.txt
examples/lt/results/gem5_se_trace_extraction/stride/stats.txt
```

默认 replay summary 优先级：

```text
examples/lt/results/gem5_trace_replay_lab/summary.csv
examples/lt/results/cpp_trace_replay_lab/summary.csv
examples/lt/results/project_e_banked_memory_controller/summary.csv
```

默认 Project E summary：

```text
examples/lt/results/project_e_banked_memory_controller/summary.csv
```

如果默认 stats 或 summary 不存在，tool 会输出清晰错误信息，并提示先运行 Project C
gem5 SE extraction、Project C replay、Project D demo 或 Project E demo。

## Outputs

默认输出目录：

```text
examples/lt/results/project_f_gem5_stats_correlation/
```

输出文件：

- `correlation_summary.csv`
- `correlation_report.md`

`correlation_summary.csv` 至少包含：

```text
workload
gem5_sim_ticks
gem5_sim_seconds
gem5_sim_insts
gem5_sim_ops
gem5_host_seconds
replay_avg_latency_ns
replay_p99_latency_ns
bank_conflict_ratio_pct
project_e_avg_latency_ns
project_e_p99_latency_ns
project_e_avg_queue_occupancy
project_e_bank_utilization_pct
trend_notes
```

## Run

从仓库根目录执行：

```bash
python3 examples/lt/tools/demo_gem5_stats_correlation_lab.py
```

如果 stats 或 summary 位于非默认路径，可以显式传入：

```bash
python3 examples/lt/tools/demo_gem5_stats_correlation_lab.py \
  --sequential-stats examples/lt/results/gem5_se_trace_extraction/sequential/stats.txt \
  --stride-stats examples/lt/results/gem5_se_trace_extraction/stride/stats.txt \
  --replay-summary examples/lt/results/gem5_trace_replay_lab/summary.csv \
  --project-e-summary examples/lt/results/project_e_banked_memory_controller/summary.csv
```

也可以直接调用底层 tool：

```bash
python3 examples/lt/tools/gem5_stats_correlation.py
```

## Interpretation

Project F 的核心解释不是绝对 timing 对齐，而是趋势对齐：

- replay model 观察 `sequential` 到 `stride` 后，`avg_latency_ns`、
  `p99_latency_ns` 和 `bank_conflict_ratio_pct` 是否上升。
- Project E 进一步观察 `stride` 是否带来更高 queue occupancy、tail latency 或 bank
  utilization。
- gem5 `stats.txt` 提供外部 SE run-level 参照，例如 `simTicks`、`simSeconds`、
  `simInsts`、`simOps` 和可选 `hostSeconds`，用于说明两个 workload 的外部执行上下文，
  而不是用来校准 replay latency。
- 如果某个非必需字段在输入中不存在，Project F 会在 `correlation_summary.csv` 中写
  `NA`，并在 `trend_notes` 记录缺失原因；如果输入文件本身不存在、CSV 为空，或找不到
  `sequential` / `stride` workload，则会失败并提示先运行对应 demo。

如果 `stride` 在 replay / Project E 中表现出更高 bank pressure 和更高 latency tail，
报告可以表述为：

```text
gem5 SE stats provide an external workload-level reference;
the replay model and Project E queueing model preserve the expected
sequential-vs-stride trend at architecture-model level.
```

但不能表述为：

```text
the replay model is cycle-accurate against gem5
the model correlates with RTL
the model correlates with silicon
the model correlates with profiler counters
```

## Timing Semantics

Project F 必须保持三类时间语义分离：

| 字段 / 指标 | 来源 | 语义 |
| --- | --- | --- |
| `simTicks` / `simSeconds` | gem5 `stats.txt` | gem5 SE run-level simulation stats |
| `timestamp_ns` | Project B / C normalized trace | normalized issue-time / ordering hint |
| `avg_latency_ns` / `p99_latency_ns` | replay summary / Project E summary | replay model 或 queueing model 的 architecture-level latency |

`timestamp_ns` 不是 gem5 timing，不是 gem5 tick，不是 cycle timing，也不是硬件时间。
它只用于 deterministic ordering 和 file-based replay。

## Supported

Project F MVP 支持：

- 解析 gem5 `stats.txt` 的 `simTicks`、`simSeconds`、`simInsts`、`simOps`，以及可选
  `hostSeconds`。
- 读取 Project C replay、Project D C++ replay 或 Project E fallback summary。
- 读取 Project E queueing model summary。
- 按 `sequential` / `stride` 归一 workload name，例如 `gem5_sequential_scan`、
  `sequential_scan`、`sample_sequential`。
- 输出固定 schema 的 `correlation_summary.csv`。
- 输出中文 `correlation_report.md`，说明 Current / Supported / Not Supported /
  Future Work。

## Not Supported

Project F MVP 不支持：

- gem5 live co-simulation。
- gem5-SystemC synchronous simulation。
- cycle accuracy。
- RTL correlation。
- silicon correlation。
- profiler correlation。
- cache hierarchy calibration。
- DRAM timing calibration。
- AXI、CHI、NoC 或 JEDEC DRAM protocol compliance。
- 把 normalized `timestamp_ns` 当作 gem5 timing。

## Validation

建议 Project F 修改后至少运行：

```bash
python3 examples/lt/tools/demo_cpp_trace_replay_lab.py --no-build
python3 examples/lt/tools/demo_banked_memory_controller_lab.py
python3 examples/lt/tools/demo_gem5_stats_correlation_lab.py
```

通过标准：

- Project D demo 仍输出 `Project D Standalone C++ Trace Replay MVP PASS`。
- Project D Python vs C++ comparison 仍输出
  `Python vs C++ replay summary equivalence PASS`。
- Project E demo 仍输出 `Project E Banked Memory Controller Queueing MVP PASS`。
- Project F demo 输出 `Project F Gem5 Stats Trend Correlation MVP PASS`。
- Project F 输出 `correlation_summary.csv` 和 `correlation_report.md`。
- 当前目录不产生 tar.gz patch 包、`__pycache__` 或未忽略的 generated results 垃圾文件。

如果当前环境没有真实 gem5 `stats.txt`，默认 Project F demo 应该清晰失败并提示先运行
Project C gem5 SE extraction；不能用 synthetic stats 冒充真实 gem5 stats correlation。

## Future Work

后续扩展到 profiler / hardware counters / RTL / silicon correlation 前，需要补齐更强的
ground truth 和对齐机制：

- workload region markers，用同一段代码区间对齐 gem5 stats、replay trace、profiler
  counters、RTL trace 和 silicon counters。
- raw event count / memory access count / marker count，避免只看 run-level stats。
- input trace hash、workload binary hash、model version 和参数记录。
- calibration dataset 和 error budget，用于解释绝对误差。
- profiler 或 hardware counter 的采样窗口、counter 定义和采样误差说明。
- RTL / silicon 数据的采集平台、频率、counter 语义和 measurement noise 说明。

在这些证据完成前，Project F 只能称为 qualitative / trend-level correlation report。
