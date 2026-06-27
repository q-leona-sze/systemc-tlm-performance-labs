# Project H：Verilator RTL Golden Model MVP

状态：MVP implementation note

Project H 的目标是为当前项目中的 local banked memory controller / queueing micro-model
建立一个最小 RTL golden reference，并用 Verilator 跑 deterministic trace replay，生成
RTL summary、H-aligned model summary 和 model-vs-RTL quantitative correlation table。

Project H 的核心不是复杂 RTL，也不是扩大 accuracy claim，而是建立一条可复现、可审计的
bounded model-vs-RTL correlation path：

```text
normalized trace CSV
-> Verilator RTL banked memory controller
+ H-aligned C++ model summary
-> rtl_summary.csv
-> model_summary_aligned.csv
-> model_vs_rtl_correlation.csv
-> correlation_report.md
```

## Current Scope

当前 Project H 只覆盖一个 local banked memory controller RTL micro-model。

实现路径：

- RTL module：`examples/lt/rtl_banked_memory_controller/rtl/banked_memory_controller.sv`
- Verilator C++ harness：`examples/lt/rtl_banked_memory_controller/sim/main.cpp`
- CSV reader：`examples/lt/rtl_banked_memory_controller/sim/csv_reader.*`
- metrics writer：`examples/lt/rtl_banked_memory_controller/sim/metrics.*`
- demo wrapper：`examples/lt/tools/demo_rtl_golden_model_lab.py`
- correlation tool：`examples/lt/tools/correlate_model_rtl_summaries.py`

默认输出目录：

```text
examples/lt/results/project_h_verilator_rtl_golden_model/
```

默认输出：

- `rtl_trace.csv`
- `rtl_summary.csv`
- `model_summary_aligned.csv`
- `model_vs_rtl_correlation.csv`
- `error_budget.csv`
- `correlation_report.md`

## Reference Source

Project H 的 reference source 是本仓库内的 local Verilator RTL model：

```text
examples/lt/rtl_banked_memory_controller/rtl/banked_memory_controller.sv
```

默认 RTL parameters：

| Parameter | Default | Meaning |
| --- | ---: | --- |
| `BANK_COUNT` | 4 | bank 数量 |
| `INTERLEAVE_BYTES` | 64 | `bank_id = (addr / INTERLEAVE_BYTES) % BANK_COUNT` |
| `SERVICE_LATENCY_CYCLES` | 10 | 每个 accepted request 的 fixed service latency |
| `QUEUE_DEPTH` | 8 | 每个 bank 可容纳的 outstanding request 数量 |

这些参数是 Verilator build-time parameters。CLI 支持 `--bank-count`、
`--interleave-bytes`、`--service-latency-cycles` 和 `--queue-depth`，但它们必须与当前
Verilated build 参数一致；如果要改变参数，需要重新 CMake configure/build。

## Supported Claims

完成 Project H MVP 后，允许的 claim 是：

```text
This project establishes a local RTL golden reference for a banked memory
controller micro-model and compares replay-model metrics against Verilator RTL
metrics using deterministic workloads and explicit error budgets.
```

更具体地说，Project H 支持：

- local banked memory controller block-level reference。
- deterministic normalized trace replay。
- accepted / rejected request count comparison。
- latency percentile comparison。
- throughput comparison。
- Project H 固定定义下的 `bank_conflict_ratio_pct` comparison。
- explicit error budget 和 pass/fail/warning status。

## Unsupported Claims

Project H 不支持以下 claim：

- silicon validation。
- production signoff。
- full-system cycle accuracy。
- full SoC accuracy。
- AXI / CHI / NoC protocol compliance。
- gem5-Verilator live co-simulation。
- NVIDIA / Apple / ARM production-level validation。
- real DRAM timing validation。
- real product memory-controller validation。

Project H 的 RTL 是 bounded local reference，不是 enterprise product RTL，也不是 silicon
measurement source。

## Input Trace Contract

Project H 复用 normalized trace CSV 思路。推荐字段：

```text
workload_name,txn_id,timestamp_ns,initiator_id,command,address,size_bytes
```

兼容字段：

- `workload_name` 或 `workload`
- `address` 或 `masked_address`
- `command`: `READ`、`WRITE`、`R`、`W`

Project H 要求：

- `timestamp_ns` 必须存在。
- `timestamp_ns / cycle_time_ns` 必须能稳定转换为整数 cycle。
- 同一个 workload 内 `issue_cycle` 必须严格递增。
- 第一版 RTL interface 每个 cycle 最多接受一个 request。
- queue full 时输出 `REJECTED_QUEUE_FULL`，第一版默认不 retry。

`timestamp_ns` 在这里仍然是 normalized issue-time / ordering hint。Project H 使用
`--cycle-time-ns` 把它转换成 RTL issue cycle；这不代表 gem5 timing 或 silicon timing。

## Compared Metrics

Project H 生成的 `rtl_summary.csv` 和 `model_summary_aligned.csv` 使用相同 schema：

```text
workload,total_requests,accepted_requests,rejected_requests,
avg_latency_cycles,p50_latency_cycles,p95_latency_cycles,p99_latency_cycles,
max_latency_cycles,avg_latency_ns,p50_latency_ns,p95_latency_ns,
p99_latency_ns,max_latency_ns,throughput_txn_per_cycle,
throughput_txn_per_us,bank_conflict_ratio_pct
```

`bank_conflict_ratio_pct` 的 Project H 定义：

```text
100.0 * count(accepted request with latency_cycles > SERVICE_LATENCY_CYCLES)
/ accepted_requests
```

也就是说，它表示 accepted requests 中发生 same-bank queueing 的比例。这个字段不能解释为
真实 DRAM bank conflict、GPU shared memory bank conflict、cache bank conflict 或 silicon
counter。

## Error Budget

`model_vs_rtl_correlation.csv` 字段：

```text
workload,metric,unit,model_value,rtl_value,abs_error,rel_error_pct,tolerance_pct,status
```

status vocabulary：

- `pass`：observed error 在 error budget 内。
- `fail`：observed error 超出 error budget。
- `warning`：数据可计算但存在 reference value 为 0 等解释风险。
- `invalid`：workload、region、metric 或 reference 未对齐，不能计算有效 error。
- `not_applicable`：metric 不适用于当前 reference 或 workload。

当前 error budget：

| Metric Class | Metrics | Budget |
| --- | --- | --- |
| Count | `total_requests`, `accepted_requests`, `rejected_requests` | exact match |
| Latency | avg / p50 / p95 / p99 / max latency in cycles/ns | tiny floating tolerance |
| Throughput | `throughput_txn_per_cycle`, `throughput_txn_per_us` | relative error <= `0.1%` |
| Bank conflict | `bank_conflict_ratio_pct` | Project H fixed definition, tiny floating tolerance |

当 `rtl_value = 0` 时，`rel_error_pct = NA`，只看 absolute error。

## Run

Mac 或 Ubuntu 上如果已安装 Verilator：

```bash
python3 examples/lt/tools/demo_rtl_golden_model_lab.py
```

手动 build/run：

```bash
cmake -S examples/lt/rtl_banked_memory_controller \
  -B build/examples/lt/rtl_banked_memory_controller
cmake --build build/examples/lt/rtl_banked_memory_controller

python3 examples/lt/tools/demo_rtl_golden_model_lab.py --no-build
```

如果本机没有 Verilator，demo 必须失败并提示：

```text
[project-h] ERROR: verilator not found. Install Verilator or run on the Ubuntu validation environment.
```

这个失败是 prerequisite failure，不是 Project H correlation PASS。

## Known Limitations

- RTL module 是最小 banked queue reference，不是完整 memory controller。
- RTL 没有 AXI / CHI / NoC channel、beat、credit、QoS 或 ordering protocol。
- RTL 没有 real DRAM timing，例如 activate / precharge / refresh / bank group timing。
- `done` 只是 aggregate sanity pulse；C++ harness 使用 `accepted_cycle + latency_cycles`
  计算 per-request completion，不依赖 `done` 恢复所有 completion event。
- 第一版不 retry rejected request。
- 第一版要求同 workload 内 issue cycle 严格递增。
- C++ model summary 是 H-aligned bounded model summary，不修改 Project E 原有
  `summary.csv` schema。
- 当前输出是 generated artifacts，不应作为 source artifacts 提交。

## Future Work

后续可以小步扩展：

- 增加 manifest，记录 RTL parameter、tool version、trace hash 和 model version。
- 支持更丰富的 deterministic workload set。
- 支持 parameterized CMake regression profile。
- 把 Project H 纳入 Project R optional regression gate，再根据 Ubuntu Verilator 环境决定是否升为 hard gate。
- 增加 response scheduling 或 outstanding transaction depth 的更细粒度 trace。
- 与 Project I profiler / counter interface 和 Project J accuracy report 衔接。
