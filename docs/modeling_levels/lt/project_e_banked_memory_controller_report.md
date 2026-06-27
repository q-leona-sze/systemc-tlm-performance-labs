# Project E：Banked Memory Controller Queueing Model MVP

## Current

Project E 是 `examples/lt` 下的 standalone C++ memory subsystem abstraction。它把
Project D 的 toy bank-conflict replay 继续推进到一个更可解释的 banked memory
controller + queueing model，但仍保持第一版足够小：

```text
normalized trace CSV
-> C++ banked memory controller model
-> trace.csv
-> summary.csv
-> comparison.md
```

当前核心模型逻辑在 C++ 中实现：

- C++ binary：`examples/lt/banked_memory_controller_cpp`
- demo wrapper：`examples/lt/tools/demo_banked_memory_controller_lab.py`
- 默认输出目录：`examples/lt/results/project_e_banked_memory_controller/`

Python 只负责 orchestration、生成 demo input traces，以及把 C++ `summary.csv` 转成
`comparison.md`。latency、queueing、row-buffer、bank utilization、throughput 和 reject
统计均由 C++ binary 计算。

## Supported

Project E MVP 支持：

- `bank_count`
- `queue_depth`
- per-bank `busy_until_ns`
- `address_mapping`
- `base_service_latency_ns`
- per-bank `open_row`
- `row_hit_latency_ns`
- `row_miss_latency_ns`
- `READ` / `WRITE` command 字段
- queue occupancy 统计
- avg / p95 / p99 / max latency
- bank utilization
- row hit ratio
- throughput
- queue full 时的 rejected transaction 统计

默认 address mapping 是：

```text
bank_id = (address / interleave_bytes) % bank_count
```

默认 `interleave_bytes = 4`，也就是 word-level interleave。这个选择故意保留对
`sequential_scan`、`stride_scan` 和 `hot_bank_stress` 的可解释差异：

- `sequential_scan` 会在多个 bank 间轮转。
- `stride_scan` 会对某些 bank 形成更强 pressure。
- `hot_bank_stress` 会集中压到一个 hot bank，并持续跨 row。

## Input Contract

输入复用 Project B / Project C / Project D 的 normalized trace CSV 思路。推荐字段：

```text
workload_name,txn_id,timestamp_ns,initiator_id,command,address,size_bytes
```

为了兼容字段不足的输入，Project E MVP 使用这些默认值：

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `workload_name` / `workload` | input filename stem | 二者都支持 |
| `txn_id` | 1-based row index | 用于同 timestamp 下的稳定排序 |
| `timestamp_ns` | row index * `default_timestamp_step_ns` | 默认 step 是 `100 ns` |
| `initiator_id` | `101` | 当前只作为 trace metadata 保留 |
| `command` | `READ` | 支持 `READ`、`WRITE`、`R`、`W` |
| `size_bytes` | `4` | 必须为正数 |
| `address` | required | 如果没有 `address`，可退回读取 `masked_address` |

`timestamp_ns` 仍然是 normalized issue-time / ordering hint，不是 gem5 timing，也不是
cycle timing。

## Output Contract

默认输出目录：

```text
examples/lt/results/project_e_banked_memory_controller/
```

输出文件：

- `trace.csv`
- `summary.csv`
- `comparison.md`

`summary.csv` 至少包含：

```text
workload
bank_count
queue_depth
transactions
avg_latency_ns
p95_latency_ns
p99_latency_ns
max_latency_ns
throughput_txn_per_us
avg_queue_occupancy
max_queue_occupancy
bank_utilization_pct
row_hit_ratio_pct
stalled_or_rejected_transactions
```

当前实现额外输出 `accepted_transactions`，用于区分 total input transactions 和 queue
full 后真正进入模型服务路径的 transactions。

## Workloads

one-command demo 会生成三类 deterministic normalized traces 到 `build/` 下：

| workload | pattern | 目标 |
| --- | --- | --- |
| `sequential_scan` | 4-byte sequential address | 稳定 baseline，多 bank 轮转，并复用 row locality |
| `stride_scan` | 16-byte stride | 观察 bank pressure 和 row-boundary 行为 |
| `hot_bank_stress` | 64-byte stride with short issue spacing | 集中压测一个 hot bank，制造 queue build-up 和 row miss |

这些 demo input traces 是 generated artifacts，默认放在：

```text
build/examples/lt/project_e_banked_memory_controller_inputs/
```

它们不是 source results，也不应提交为结果文件。

## Run

从仓库根目录执行：

```bash
cmake -S examples/lt/banked_memory_controller_cpp \
  -B build/examples/lt/banked_memory_controller_cpp
cmake --build build/examples/lt/banked_memory_controller_cpp

python3 examples/lt/tools/demo_banked_memory_controller_lab.py
```

也可以直接调用 C++ binary：

```bash
./build/examples/lt/banked_memory_controller_cpp/banked_memory_controller \
  --trace examples/lt/traces/sample_sequential_trace.csv \
  --trace examples/lt/traces/sample_stride_trace.csv \
  --output-dir examples/lt/results/project_e_banked_memory_controller
```

## Interpretation

当前默认 demo 结果：

| workload | avg_latency_ns | p99_latency_ns | max_queue_occupancy | row_hit_ratio_pct | stalled_or_rejected_transactions |
| --- | ---: | ---: | ---: | ---: | ---: |
| `sequential_scan` | 36.000 | 60.000 | 1 | 75.000 | 0 |
| `stride_scan` | 238.000 | 424.000 | 12 | 75.000 | 0 |
| `hot_bank_stress` | 664.857 | 960.000 | 16 | 0.000 | 68 |

`sequential_scan` 的 latency tail 应该较稳，因为连续 4-byte access 在默认
`word_interleave` mapping 下会在多个 bank 间轮转；同一个 bank 中的短距离 access 也更
容易命中当前 open row。

`stride_scan` 会改变 bank pressure 和 row behavior。16-byte stride 在 4-bank、
4-byte interleave 下会更频繁回到同一 bank；当 address 跨 row 时，又会触发 row miss。
因此它适合解释 bank mapping 和 row locality 对 tail latency 的趋势影响。

`hot_bank_stress` 会显著恶化 queue occupancy、p99/max latency 和 reject 风险。它把
请求集中在一个 hot bank，并用短 issue spacing 持续推高 per-bank outstanding requests。
当 outstanding requests 达到 `queue_depth`，MVP 会把新 transaction 记为
`REJECTED_QUEUE_FULL`。

## Not Supported

Project E MVP 不支持：

- SystemC kernel integration。
- gem5 live co-simulation。
- JEDEC DRAM timing。
- AXI / CHI / NoC protocol。
- cycle accuracy。
- cache hierarchy。
- DRAM command scheduler。
- refresh / activate / precharge / timing-closure-level modeling。
- production interconnect protocol behavior。

这个模型证明的是 trend-level memory subsystem behavior，不是 cycle-accurate DRAM。

## Regression

建议每次 Project E 修改后至少运行：

```bash
python3 examples/lt/tools/demo_cpp_trace_replay_lab.py --no-build
python3 examples/lt/tools/demo_banked_memory_controller_lab.py
```

通过标准：

- Project D demo 仍输出 `Project D Standalone C++ Trace Replay MVP PASS`。
- Project D Python vs C++ comparison 仍输出 `Python vs C++ replay summary equivalence PASS`。
- Project E demo 输出 `Project E Banked Memory Controller Queueing MVP PASS`。
- Project E `summary.csv` 包含本文列出的关键字段。
- 当前目录不产生 tar.gz patch 包或大量 generated results 垃圾文件。

## Future Work

后续方向保持小步、可验证：

- 增加更多 address mapping knobs。
- 对 read/write 使用不同 service latency。
- 增加 per-bank service trace sanity checks。
- 增加固定小型 golden fixture，用于 CI 检查 summary field presence 和 queue-full case。
- 未来如果接入 SystemC 或 gem5 trace producer，应先保持 file-based replay contract
  稳定，再扩展实时集成。
