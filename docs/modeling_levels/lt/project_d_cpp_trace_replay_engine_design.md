# Project D Design: C++ Trace Replay Engine

状态：设计文档

本文档定义 Project D 的设计：把 Project B / Project C 当前 Python replay 的核心模型逻辑
迁移到 standalone C++ trace replay engine。本文档只描述设计，不创建 C++ 源码、不修改
Python 脚本、不改变现有 CSV schema。

Project D 仍然服务于同一条证据链：

```text
workload -> normalized trace -> replay engine -> metrics -> comparison -> demo
```

## 1. Motivation

Project B 已经证明 normalized trace replay 的工程价值：外部 trace source 可以通过
稳定 CSV contract 进入 LT replay / analysis backend。Project C 进一步把 gem5 SE 放在
offline trace producer 的位置，通过 `PROJECT_C_MEM` markers 生成 Project B 可消费的
normalized trace。

当前 Python replay 适合快速验证 schema、orchestration 和 artifact chain，但工业界
performance modeling / simulator engineering 岗位通常更重视高质量 C++：

- C++ 更接近 SystemC/TLM、gem5、RTL simulator wrapper、commercial simulator model 的工程语言。
- C++ 更适合长期承载 core latency model、trace parser、event scheduler 和 metric engine。
- Python 可以继续负责 demo、batch orchestration、comparison report 和 glue logic。
- 将 core replay 迁移到 C++，可以让项目从教学实验进一步变成可演进的 architecture-level performance modeling framework。

Project D 的核心目标是：

> 用 standalone C++ engine 复现 Project B Python replay 的 normalized trace parsing、
> latency / bank conflict / throughput metric computation，以及 `trace.csv` /
> `summary.csv` artifact generation。

第一版强调等价迁移，不扩大模型 claim。

## 2. Scope

Project D 第一版范围：

1. 输入 Project B / Project C normalized trace CSV。
2. C++ 解析 trace、校验 schema、报告错误。
3. C++ 按 `timestamp_ns` 和 `txn_id` 做 deterministic ordering。
4. C++ 计算当前 MVP latency model。
5. C++ 计算 minimal bank conflict。
6. C++ 计算 summary metrics，包括 latency percentiles、`bank_conflict_ratio_pct` 和 `throughput_txn_per_us`。
7. C++ 输出 replayed `trace.csv`。
8. C++ 输出 `summary.csv`。
9. Python 继续负责 one-command demo wrapper。
10. Python 继续负责从 `summary.csv` 生成 `comparison.md`。

Project D 第一版应保持 Project B MVP 约束：

- 每个输入 trace 文件只有一个 `workload_name`。
- 支持 `initiator_id=101`。
- 支持 `command=READ`。
- 支持 `size_bytes=4`。
- 支持 decimal 或 `0x` hexadecimal address。
- 地址必须能 decode 到当前 LT MVP target window。

这些约束不是最终目标，而是第一版用来保证 Python vs C++ 等价验证足够清晰。

## 3. Non-Goals

Project D 第一版明确不做：

- 不接 SystemC kernel。
- 不创建 `sc_module`。
- 不接 gem5 live co-simulation。
- 不接 socket、pipe、shared memory 或 gem5 plugin。
- 不实现 cache model。
- 不实现 DRAM protocol 或 DRAM timing model。
- 不实现 AXI / CHI / NoC protocol model。
- 不实现 GPU shared memory real model。
- 不实现 multi-core memory consistency 或 cache coherence。
- 不声称 cycle accuracy。
- 不替换 Project C 的 gem5 SE marker extraction。
- 不要求 Python demo / comparison 立刻删除。

Project D 不是为了提高模型 fidelity，而是为了把当前 core replay / metric logic 迁移到更接近工业 simulator engineering 的 C++ 实现。

## 4. Directory Structure

建议未来实现放在 `examples/lt` 下，因为 Project D 消费 Project B / Project C 的 normalized traces，属于 LT replay backend 的演进。

建议目录结构：

```text
examples/lt/replay_cpp/
  CMakeLists.txt
  include/
    trace_replay/
      csv_reader.h
      trace_record.h
      trace_validator.h
      replay_model.h
      metrics.h
      csv_writer.h
      cli.h
  src/
    main.cpp
    csv_reader.cpp
    trace_validator.cpp
    replay_model.cpp
    metrics.cpp
    csv_writer.cpp
    cli.cpp
  tests/
    README.md

examples/lt/tools/
  demo_cpp_trace_replay_lab.py
  compare_python_cpp_replay_outputs.py

examples/lt/results/
  cpp_trace_replay_lab/
    trace.csv
    summary.csv
    comparison.md
```

设计规则：

- `examples/lt/replay_cpp` 是 standalone C++ executable，不依赖 SystemC。
- Python wrapper 只调用 C++ binary，不复制 replay logic。
- `comparison.md` 仍由 Python 从 `summary.csv` 生成，延续现有 report 风格。
- 不修改 `examples/at`。
- 不依赖 `references/doulos_at_example`。
- 不把 generated `results/` 当作 source artifact。

可选未来命令形态：

```bash
cmake -S examples/lt/replay_cpp -B build/examples/lt/replay_cpp
cmake --build build/examples/lt/replay_cpp

./build/examples/lt/replay_cpp/replay_cpp \
  --trace examples/lt/traces/sample_sequential_trace.csv \
  --trace examples/lt/traces/sample_stride_trace.csv \
  --output-dir examples/lt/results/cpp_trace_replay_lab
```

## 5. C++ Module Breakdown

建议模块按数据流拆分，避免把 parser、model、metrics 和 CLI 混在一个文件里。

| 模块 | 责任 | 关键输入 | 关键输出 |
| --- | --- | --- | --- |
| `cli` | 解析命令行参数，处理 `--trace`、`--output-dir`、`--validate-only`。 | `argv` | `ReplayConfig` |
| `csv_reader` | 读取 CSV header 和 rows，保留 source file / row number。 | CSV path | raw row records |
| `trace_record` | 定义 normalized input record 和 replay output record 的 typed structs。 | parsed fields | typed records |
| `trace_validator` | 校验 required fields、MVP constraints、duplicate `txn_id`、address decode。 | raw records | validated input records |
| `replay_model` | 实现当前 latency / bank conflict model。 | sorted input records | replay output records |
| `metrics` | 计算 per-workload summary metrics。 | replay output records | summary rows |
| `csv_writer` | 写 `trace.csv` 和 `summary.csv`，保证 field order 与 Python 对齐。 | typed rows | CSV files |
| `error` / diagnostics | 统一错误消息，包含 file、row number、field。 | validation/model errors | non-zero exit and clear stderr |

关键数据类型建议：

```text
NormalizedTraceRecord
  workload_name
  txn_id
  timestamp_ns
  initiator_id
  command
  address
  size_bytes
  source_trace
  source_row_number

ReplayTraceRecord
  normalized input fields
  target_id
  decoded_port
  masked_address
  start_time_ns
  end_time_ns
  target_service_delay_ns
  bank_id
  bank_conflict
  bank_conflict_delay_ns
  total_delay_ns

SummaryRow
  workload_name
  num_transactions
  avg_latency_ns
  p50_latency_ns
  p95_latency_ns
  p99_latency_ns
  max_latency_ns
  bank_conflict_ratio_pct
  throughput_txn_per_us
```

第一版建议只使用 C++ standard library，避免引入第三方 CSV 或 CLI 依赖。CSV parser 可以先支持当前 repo 生成的简单 CSV：逗号分隔、header row、无嵌套换行。更完整的 quoted-field 支持可以作为后续 hardening。

## 6. Input Schema

Project D 输入必须兼容 Project B required schema：

```text
workload_name,txn_id,timestamp_ns,initiator_id,command,address,size_bytes
```

字段语义：

| Field | Type | Required | Semantics |
| --- | --- | --- | --- |
| `workload_name` | string | yes | 单个 trace 文件内的 logical workload name。 |
| `txn_id` | string or integer-like | yes | 单个 workload 内稳定 transaction id；用于 tie-break sorting 和 traceability。 |
| `timestamp_ns` | numeric | yes | normalized issue-time / ordering hint，不是 gem5 timing，不是 cycle timing。 |
| `initiator_id` | string | yes | 第一版只接受 `101`。 |
| `command` | string | yes | 第一版只接受 `READ`，并做 uppercase normalization。 |
| `address` | integer | yes | 支持 decimal 或 `0x` hexadecimal；必须非负。 |
| `size_bytes` | integer | yes | 第一版只接受 `4`。 |

Project C converter 可额外输出：

```text
pc,symbol,source
```

Project D 第一版应允许这些 extra columns 存在，但它们不参与 replay model，也不作为 required fields。未来可以选择把 extra metadata 透传到 diagnostics 或 optional output trace，但不能阻断当前 Project B/C replay。

输入排序规则：

```text
sort by timestamp_ns ascending,
then txn_id numeric order when txn_id parses as integer,
otherwise txn_id lexical order
```

输入 validation rules：

- trace 文件必须存在且非空。
- required fields 必须全部存在。
- `workload_name` 不能为空。
- 单个 trace 文件必须只有一个 `workload_name`。
- `txn_id` 不能为空，且单个 trace 文件内不能重复。
- `timestamp_ns >= 0`。
- `address >= 0`。
- `decoded_port = address >> 28`，第一版只允许 `0` 或 `1`。
- `target_id = 201 + decoded_port`。
- `masked_address = address & 0x0FFFFFFF`。

## 7. Output Schema

Project D 第一版输出两个核心 artifacts：

```text
trace.csv
summary.csv
```

Python wrapper 可以继续根据 `summary.csv` 生成：

```text
comparison.md
```

### 7.1 `trace.csv`

为了和 Python replay 对齐，C++ `trace.csv` 第一版应保持以下 field order：

```text
workload_name,txn_id,timestamp_ns,initiator_id,command,address,size_bytes,
target_id,decoded_port,masked_address,data_length,data,start_time_ns,delay_ns,
end_time_ns,response_status,request_time_ns,bus_grant_time_ns,queue_delay_ns,
target_service_delay_ns,total_delay_ns,target_busy_until_ns,bank_id,
bank_conflict,bank_conflict_delay_ns,source_trace
```

字段规则：

- `timestamp_ns`、`start_time_ns`、`delay_ns`、`end_time_ns` 等时间字段使用三位小数格式。
- `address` 和 `masked_address` 使用 16 hex digit uppercase 格式，例如 `0x0000000000000010`。
- `data` 第一版固定为 `0x00000000`。
- `response_status` 第一版固定为 `TLM_OK_RESPONSE`。
- `request_time_ns` 等于 `start_time_ns`。
- `bus_grant_time_ns` 等于 `start_time_ns`。
- `queue_delay_ns` 第一版固定为 `0.000`。
- `target_service_delay_ns` 第一版固定为 `100.000`。
- `target_busy_until_ns` 等于 `end_time_ns`。
- `source_trace` 记录输入 CSV 路径。

### 7.2 `summary.csv`

C++ `summary.csv` 第一版应保持 Python replay 当前 field order：

```text
workload_name,num_transactions,avg_latency_ns,p50_latency_ns,p95_latency_ns,
p99_latency_ns,max_latency_ns,bank_conflict_ratio_pct,throughput_txn_per_us
```

每个输入 trace / workload 输出一行。第一版不在 `summary.csv` 中加入 status/error 列，保持与 Project B Python replay output 等价。错误通过 non-zero exit code 和 stderr diagnostics 表达。

## 8. Metrics Equivalence With Python Replay

Project D 第一版的核心验收标准是 Python replay 与 C++ replay 等价。

需要等价的 model constants：

| Constant | Value | Meaning |
| --- | ---: | --- |
| `MVP_INITIATOR_ID` | `101` | 第一版唯一 initiator。 |
| `MVP_COMMAND` | `READ` | 第一版唯一 command。 |
| `MVP_SIZE_BYTES` | `4` | 第一版访问粒度。 |
| `TARGET_SERVICE_DELAY_NS` | `100.0` | 固定 target service delay。 |
| `BANK_CONFLICT_DELAY_NS` | `20.0` | bank conflict 附加延迟。 |

需要等价的 model formulas：

```text
bank_id = (masked_address / MVP_SIZE_BYTES) % 4
bank_conflict = last_bank_by_target[decoded_port] == bank_id
bank_conflict_delay_ns = bank_conflict ? 20.0 : 0.0
queue_delay_ns = 0.0
target_service_delay_ns = 100.0
total_delay_ns = queue_delay_ns + target_service_delay_ns + bank_conflict_delay_ns
start_time_ns = timestamp_ns
end_time_ns = start_time_ns + total_delay_ns
```

需要等价的 summary formulas：

```text
avg_latency_ns = average(total_delay_ns)
p50/p95/p99 = percentile(total_delay_ns, same rank rule as Python)
max_latency_ns = max(total_delay_ns)
bank_conflict_ratio_pct = 100.0 * bank_conflict_count / num_transactions
throughput_txn_per_us =
  num_transactions / ((max(end_time_ns) - min(start_time_ns)) / 1000.0)
```

Python percentile rule 当前使用：

```text
rank = round((percentile / 100.0) * (N - 1))
```

C++ 第一版必须实现同一 rule，而不是替换成 nearest-rank、linear interpolation 或统计库默认 percentile。

格式等价要求：

- 数值输出使用三位小数。
- hex address 输出使用 uppercase。
- CSV field order 完全一致。
- workload summary row order 跟输入 `--trace` 参数顺序一致。
- 单个 trace 内 replay row order 跟 deterministic sorted input order 一致。

## 9. Regression Strategy

Project D 回归分四层。

### 9.1 Schema Validation Regression

用现有 Project B sample traces：

```bash
./build/examples/lt/replay_cpp/replay_cpp \
  --validate-only \
  --trace examples/lt/traces/sample_sequential_trace.csv \
  --trace examples/lt/traces/sample_stride_trace.csv
```

通过标准：

- exit code 为 0。
- 输出明确 validation PASS。
- malformed trace 能返回 non-zero exit code，并指出 file、row number、field。

### 9.2 Replay Artifact Regression

运行 C++ replay：

```bash
./build/examples/lt/replay_cpp/replay_cpp \
  --trace examples/lt/traces/sample_sequential_trace.csv \
  --trace examples/lt/traces/sample_stride_trace.csv \
  --output-dir examples/lt/results/cpp_trace_replay_lab
```

通过标准：

- `examples/lt/results/cpp_trace_replay_lab/trace.csv` 存在且非空。
- `examples/lt/results/cpp_trace_replay_lab/summary.csv` 存在且非空。
- `summary.csv` percentile ordering 通过。
- `bank_conflict_ratio_pct` 在 `0.000` 到 `100.000` 之间。
- `throughput_txn_per_us` 非负。

### 9.3 Project C Input Regression

用 Project C 生成的 normalized traces：

```bash
./build/examples/lt/replay_cpp/replay_cpp \
  --trace examples/lt/traces/gem5_sequential_trace.csv \
  --trace examples/lt/traces/gem5_stride_trace.csv \
  --output-dir examples/lt/results/cpp_gem5_trace_replay_lab
```

通过标准：

- C++ replay 接受带 `pc,symbol,source` extra columns 的 Project C trace。
- summary 包含 `gem5_sequential_scan` 和 `gem5_stride_scan`。
- Project C 仍然只被描述为 gem5 SE offline trace producer，不是 live co-simulation。

### 9.4 Python Wrapper Regression

未来 Python wrapper 可以保持现有 demo 风格：

```bash
python3 examples/lt/tools/demo_cpp_trace_replay_lab.py \
  --binary ./build/examples/lt/replay_cpp/replay_cpp
```

通过标准：

- Python wrapper 只负责编译检查、调用 C++ binary、验证 artifacts、生成 `comparison.md`。
- wrapper 不重新实现 replay model。
- demo 输出包含 scope reminder：standalone C++ replay engine, no SystemC kernel, no gem5 live co-simulation, no cycle-accuracy claim。

## 10. How to Compare Python vs C++ Output

Python vs C++ 对比是 Project D 第一版最重要的 validation。

推荐运行顺序：

```bash
python3 examples/lt/tools/run_trace_replay_lab.py \
  --trace examples/lt/traces/sample_sequential_trace.csv \
  --trace examples/lt/traces/sample_stride_trace.csv \
  --output-dir examples/lt/results/trace_replay_lab_python

./build/examples/lt/replay_cpp/replay_cpp \
  --trace examples/lt/traces/sample_sequential_trace.csv \
  --trace examples/lt/traces/sample_stride_trace.csv \
  --output-dir examples/lt/results/trace_replay_lab_cpp
```

比较对象：

```text
examples/lt/results/trace_replay_lab_python/trace.csv
examples/lt/results/trace_replay_lab_cpp/trace.csv
examples/lt/results/trace_replay_lab_python/summary.csv
examples/lt/results/trace_replay_lab_cpp/summary.csv
```

建议比较策略：

1. Header exact match。
2. Row count exact match。
3. Key columns exact match：
   - `workload_name`
   - `txn_id`
   - `timestamp_ns`
   - `initiator_id`
   - `command`
   - `address`
   - `target_id`
   - `decoded_port`
   - `masked_address`
   - `bank_id`
   - `bank_conflict`
4. Numeric columns exact string match for first MVP，或允许 `1e-9` tolerance 后再统一三位小数输出。
5. `summary.csv` exact match，尤其是：
   - `avg_latency_ns`
   - `p50_latency_ns`
   - `p95_latency_ns`
   - `p99_latency_ns`
   - `max_latency_ns`
   - `bank_conflict_ratio_pct`
   - `throughput_txn_per_us`

推荐未来增加比较工具：

```bash
python3 examples/lt/tools/compare_python_cpp_replay_outputs.py \
  --python-output examples/lt/results/trace_replay_lab_python \
  --cpp-output examples/lt/results/trace_replay_lab_cpp
```

比较工具职责：

- 读取两套 `trace.csv` / `summary.csv`。
- 检查 header、row count、key fields。
- 对 numeric fields 做 strict formatted comparison。
- 输出 mismatch 的 file、row、field、Python value、C++ value。
- 只有完全等价时打印 `Python vs C++ replay equivalence PASS`。

## 11. Future Path Toward SystemC Module Integration

Project D 第一版故意不接 SystemC kernel。未来如果 C++ standalone replay 已经通过 Python equivalence regression，可以分阶段走向 SystemC module integration。

建议路径：

| 阶段 | 目标 | 验证重点 |
| --- | --- | --- |
| D1 standalone C++ engine | 复现 Python replay model，输出 `trace.csv` / `summary.csv`。 | Python vs C++ exact equivalence。 |
| D2 C++ library split | 把 parser、model、metrics 从 CLI 中拆成可链接 library。 | CLI output 不变，unit tests 覆盖 model functions。 |
| D3 SystemC adapter prototype | 用 `sc_module` 包装 replay library，但不改变模型语义。 | standalone output 与 SystemC adapter output 等价。 |
| D4 Timed event scheduling | 把 `timestamp_ns` 映射到 SystemC event schedule。 | 明确 `timestamp_ns` 仍是 normalized replay time，不是 gem5 tick。 |
| D5 TLM transaction emission | 将 replay records 转成 TLM transaction path。 | traceability from input `txn_id` to TLM transaction output。 |
| D6 Optional gem5 live integration research | 评估 socket/pipe/co-sim boundary。 | 在实现前先定义 time ownership、ordering、backpressure。 |

未来 integration 仍需保持边界：

- SystemC adapter 不自动等于 cycle accuracy。
- gem5 live integration 不应在没有同步语义和 validation plan 前进入 mainline claim。
- cache / DRAM / AXI / CHI / NoC protocol model 必须作为独立设计和验证阶段，不应混入 Project D 第一版。

## 12. Interview Framing

Project D 在面试中的表达重点：

- Python 用来快速建立 trace contract 和 demo chain。
- C++ 用来承载长期 core replay / metric engine。
- 第一版 C++ 目标是 equivalence and engineering discipline，不是更高 fidelity。
- 通过 Python vs C++ output comparison 证明迁移正确性。
- 后续再把 standalone C++ library 接到 SystemC module，避免一开始把 parser、model、kernel scheduling、gem5 integration 全混在一起。

可以这样概括：

> Project D is the C++ simulator-engineering step. I keep Python as orchestration,
> but move the core trace parser, replay model, bank-conflict logic, and metric
> computation into a standalone C++ engine. The first milestone is strict
> equivalence with the Python replay output before any SystemC kernel or gem5
> live co-simulation integration.
