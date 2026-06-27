# examples/lt 性能建模实验室

[项目总览](../../README.md) | [AT 实验链](../at/README.md)

`examples/lt/` 是本书配套仓库的 LT 主线。当前公开路径只保留 standalone trace replay、
standalone C++ replay engine、banked memory controller queueing model、gem5 SE
offline trace extraction 和 trend-level stats correlation。它不依赖外部协同仿真 bridge，
也不把历史集成路径作为公开仓库的一部分。

核心链路：

```text
workload -> trace -> metrics -> sweep -> comparison -> validation -> diagnosis
```

## Current / Supported / Not Supported / Future Work

| Category | Scope |
| --- | --- |
| Current | Project B normalized trace replay、Project C gem5 SE offline trace extraction、Project D standalone C++ replay、Project E banked memory controller queueing model、Project F trend-level stats correlation。 |
| Supported | 在固定 CSV schema、固定模型假设和同一分析脚本下做 workload-to-workload 的趋势比较、latency decomposition、bank conflict proxy、queueing、throughput 和 bottleneck attribution。 |
| Not Supported | cycle accuracy、AXI/CHI/NoC/DRAM protocol compliance、真实 cache coherence、真实硬件 counter correlation、silicon validation、production signoff。 |
| Future Work | 更多 trace fixtures、明确 metric versioning、外部 reference 的 prerequisite-aware correlation path、LT-vs-AT 对齐 workload。 |

## 实验地图

| Project | 路径 | 作用 |
| --- | --- | --- |
| Project B | `examples/lt/tools/run_trace_replay_lab.py`、`demo_trace_replay_lab.py` | 定义 normalized trace contract，并用 Python replay 生成 `trace.csv`、`summary.csv`、`comparison.md`。 |
| Project C | `examples/lt/tools/run_gem5_se_trace_extraction.py`、`convert_gem5_se_trace.py` | 把 gem5 SE marker stream 转成 Project B normalized trace；gem5 只作为 offline trace producer。 |
| Project D | `examples/lt/replay_cpp/`、`demo_cpp_trace_replay_lab.py` | 用 standalone C++ replay engine 复刻 Project B metrics，并与 Python baseline 做 equivalence check。 |
| Project E | `examples/lt/banked_memory_controller_cpp/`、`demo_banked_memory_controller_lab.py` | 用 standalone C++ banked memory controller + queueing model 观察 bank pressure、row locality、tail latency 和 reject risk。 |
| Project F | `examples/lt/tools/gem5_stats_correlation.py`、`demo_gem5_stats_correlation_lab.py` | 把 gem5 `stats.txt`、replay summary 和 Project E summary join 成 qualitative / trend-level report。 |

## 快速开始

从仓库根目录执行：

```bash
python3 examples/lt/tools/run_trace_replay_lab.py \
  --validate-only \
  --trace examples/lt/traces/sample_sequential_trace.csv \
  --trace examples/lt/traces/sample_stride_trace.csv

python3 examples/lt/tools/demo_trace_replay_lab.py
```

构建并运行 Project D：

```bash
cmake -S examples/lt/replay_cpp -B build/examples/lt/replay_cpp
cmake --build build/examples/lt/replay_cpp

python3 examples/lt/tools/demo_cpp_trace_replay_lab.py --no-build
```

构建并运行 Project E：

```bash
cmake -S examples/lt/banked_memory_controller_cpp \
  -B build/examples/lt/banked_memory_controller_cpp
cmake --build build/examples/lt/banked_memory_controller_cpp

python3 examples/lt/tools/demo_banked_memory_controller_lab.py
```

Project F 需要默认位置下已有 Project C / replay / Project E 输入 artifacts：

```bash
python3 examples/lt/tools/demo_gem5_stats_correlation_lab.py
```

## Trace contract

Project B/D/E 的基础 normalized trace schema：

```text
workload_name,txn_id,timestamp_ns,initiator_id,command,address,size_bytes
```

Project C 可额外保留 debug metadata：

```text
workload_name,txn_id,timestamp_ns,initiator_id,command,address,size_bytes,pc,symbol,source
```

语义边界：

- `timestamp_ns` 是 normalized issue-time / ordering hint，不是 gem5 timing，也不是 cycle timing。
- `bank_conflict_ratio_pct` 是当前模型内部 bank conflict proxy，不是真实 DRAM 或 GPU shared memory bank conflict。
- `throughput_txn_per_us` 是同一模型内的比较指标，不是真实带宽或 IPC。

## 关键输出

| Project | 输出 |
| --- | --- |
| Project B | `examples/lt/results/trace_replay_lab/trace.csv`、`summary.csv`、`comparison.md` |
| Project C | `examples/lt/traces/gem5_sequential_trace.csv`、`gem5_stride_trace.csv`、`examples/lt/results/gem5_trace_replay_lab/*` |
| Project D | `examples/lt/results/cpp_trace_replay_lab/trace.csv`、`summary.csv`、`comparison.md` |
| Project E | `examples/lt/results/project_e_banked_memory_controller/trace.csv`、`summary.csv`、`comparison.md` |
| Project F | `examples/lt/results/project_f_gem5_stats_correlation/correlation_summary.csv`、`correlation_report.md` |

Committed results 只作为小型 evidence snapshots。新的 raw traces、stdout/stderr、临时 CSV
和 build outputs 应写入 ignored `artifacts/` 或本地 build directory。

## Project B：Normalized Trace Replay

目标：

- 验证 normalized trace schema。
- 按 `timestamp_ns` 与 `txn_id` 稳定排序。
- 生成 latency、bank conflict proxy、throughput 等 summary metrics。
- 输出 CSV-derived comparison report。

Project B 不运行真实 gem5，也不接 SystemC kernel。它证明的是 trace contract 与 replay
metrics pipeline。

## Project C：gem5 SE Offline Trace Extraction

Project C 使用 gem5 SE mode 运行小型 user-level workload，捕获 `PROJECT_C_MEM` marker
stream，再转换成 normalized trace CSV。

```text
C workload
-> gem5 SE marker stream
-> normalized trace CSV
-> Project B replay
-> summary.csv / comparison.md
```

边界：

- gem5 只作为 offline trace producer。
- 本仓库只把 marker stream 转成 replay input。
- 不做 live co-simulation、full-system Linux、cycle-accurate timing 或硬件准确性验证。

## Project D：Standalone C++ Replay Engine

Project D 把 Project B Python replay 的核心 metrics 逻辑迁移到 standalone C++ binary。
Python wrapper 负责 orchestration、Python/C++ summary equivalence check 和
`comparison.md` 生成。

可声称：当前 C++ replay engine 与 Python baseline 在 documented summary metrics 上一致。

不可声称：这不是硬件准确性验证，也不是 cache、DRAM、AXI、CHI 或 NoC protocol model。

## Project E：Banked Memory Controller Queueing Model

Project E 使用 standalone C++ model 观察：

- bank count；
- queue depth；
- per-bank busy time；
- row-hit / row-miss proxy；
- p95 / p99 / max latency；
- bank utilization；
- queue full / rejected transaction risk。

它是 bounded memory subsystem exploration，不是 JEDEC DRAM timing，也不声称真实 memory
controller fidelity。

## Project F：Trend-Level Stats Correlation

Project F 生成 file-based qualitative / trend-level report。它可以说明 selected workload
之间的 trend 是否一致，但不提供 absolute error、cycle accuracy、RTL correlation、
silicon correlation 或 profiler correlation。

## 建模语义

当前 LT 主线的价值是建立可复现实验骨架：

- workload / trace source；
- trace contract；
- metrics extraction；
- sweep / comparison；
- generated report；
- claim boundary。

本实验室适合讨论 architecture-level trend、瓶颈定位和方法论，不适合作为真实硬件 timing
或协议行为的证据。
