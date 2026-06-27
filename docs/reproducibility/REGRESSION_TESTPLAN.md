# Regression Test Plan

状态：回归测试计划

本文档给出 `SystemC/TLM Architecture Performance Labs` 当前回归命令。默认从仓库根目录
执行：

```bash
cd <repo-root>
```

注意：

- 这些命令会生成或覆盖 `build/`、`examples/lt/results/`、`examples/lt/traces/` 或
  `phase_trace.csv` 下的 generated artifacts。
- 如果已有结果需要保留，先复制到外部归档目录后再运行回归。
- 不要把 `build/`、`results/`、`phase_trace.csv`、`summary.csv`、`comparison.md` 当成 source artifacts 提交。

## 现代 toolchain baseline

对 SystemC 3.0.2、CMake 3.24+、C++17/C++20 与 Python 3.13/3.14 的现代 Ubuntu 验证，请使用
[`ubuntu_modern_toolchain_validation.md`](ubuntu_modern_toolchain_validation.md) 的
`scripts/ubuntu_verify.sh`；其 outputs 仅写入
`artifacts/ubuntu-validation/<run-id>/`，不会污染本仓库的 `examples/*/results/`。

## 1. Prerequisites

通用依赖：

- Python 3。
- 当前仓库源码。
- 对 Project C，需要外部 gem5 build、SE config、target compiler 和匹配 ISA 的 workload binary。

Project C 推荐环境变量：

```bash
export GEM5_BINARY=/absolute/path/to/gem5/build/X86/gem5.opt
export GEM5_CONFIG=/absolute/path/to/gem5/configs/example/se.py
export TARGET_CC=gcc
```

如果使用 ARM 或 RISC-V gem5，把 `GEM5_BINARY`、`GEM5_CONFIG` 和 `TARGET_CC` 换成匹配目标 ISA 的路径，并用 `file` / `readelf` 验证 target ELF。

## 2. Project B Normalized Trace Replay Regression

目的：验证 normalized trace schema 和 file-based replay backend。

先做 schema-only check：

```bash
python3 examples/lt/tools/run_trace_replay_lab.py \
  --validate-only \
  --trace examples/lt/traces/sample_sequential_trace.csv \
  --trace examples/lt/traces/sample_stride_trace.csv
```

再跑 one-command demo：

```bash
python3 examples/lt/tools/demo_trace_replay_lab.py
```

预期输出：

```text
examples/lt/results/trace_replay_lab/trace.csv
examples/lt/results/trace_replay_lab/summary.csv
examples/lt/results/trace_replay_lab/comparison.md
```

通过标准：

- schema-only check 输出 `Project B normalized trace schema PASS`。
- demo exit code 为 0。
- demo 输出包含 `Project B Normalized Trace Replay MVP PASS`。
- `summary.csv` workload 顺序为 sequential-like 然后 stride-like。
- `bank_conflict_ratio_pct` 在 `0.000` 到 `100.000` 之间。
- percentile ordering 满足 `p50_latency_ns <= p95_latency_ns <= p99_latency_ns <= max_latency_ns`。
- `comparison.md` 明确说明 `timestamp_ns` 是 normalized issue-time / ordering hint，不是 gem5 timing 或 cycle timing。

当前 MVP 输入约束：

- required fields 为 `workload_name,txn_id,timestamp_ns,initiator_id,command,address,size_bytes`。
- 当前支持 `initiator_id=101`。
- 当前支持 `command=READ`。
- 当前支持 `size_bytes=4`。
- 每个输入 trace 文件只包含一个 `workload_name`。

## 4. Project C Workload Build and ELF Checks

目的：在 gem5 SE trace extraction 前确认 target workload binary 和 gem5 ISA 匹配。

X86 gem5 示例：

```bash
mkdir -p build/project_c/gem5_se

${TARGET_CC} -O2 -static -fno-pie -no-pie \
  -o build/project_c/gem5_se/sequential_scan \
  examples/lt/workloads/gem5_se/sequential_scan.c

${TARGET_CC} -O2 -static -fno-pie -no-pie \
  -o build/project_c/gem5_se/stride_scan \
  examples/lt/workloads/gem5_se/stride_scan.c
```

ELF sanity checks：

```bash
file build/project_c/gem5_se/sequential_scan
readelf -h build/project_c/gem5_se/sequential_scan
readelf -l build/project_c/gem5_se/sequential_scan

file build/project_c/gem5_se/stride_scan
readelf -h build/project_c/gem5_se/stride_scan
readelf -l build/project_c/gem5_se/stride_scan
```

通过标准：

- binary 存在且可执行。
- ELF machine 与 `GEM5_BINARY` 的 ISA 匹配。
- static binary 不依赖目标环境中不存在的 dynamic linker。

## 5. Project C gem5 SE Trace Extraction Regression

目的：验证 gem5 SE 作为 offline trace producer，输出 `PROJECT_C_MEM` marker stream，并转换为 Project B normalized trace。

Sequential extraction：

```bash
python3 examples/lt/tools/run_gem5_se_trace_extraction.py \
  --gem5-binary "${GEM5_BINARY}" \
  --gem5-config "${GEM5_CONFIG}" \
  --workload build/project_c/gem5_se/sequential_scan \
  --workload-name gem5_sequential_scan \
  --output-dir examples/lt/results/gem5_se_trace_extraction/sequential \
  --normalized-output examples/lt/traces/gem5_sequential_trace.csv
```

Stride extraction：

```bash
python3 examples/lt/tools/run_gem5_se_trace_extraction.py \
  --gem5-binary "${GEM5_BINARY}" \
  --gem5-config "${GEM5_CONFIG}" \
  --workload build/project_c/gem5_se/stride_scan \
  --workload-name gem5_stride_scan \
  --output-dir examples/lt/results/gem5_se_trace_extraction/stride \
  --normalized-output examples/lt/traces/gem5_stride_trace.csv
```

预期输出：

```text
examples/lt/results/gem5_se_trace_extraction/sequential/run_stdout.txt
examples/lt/results/gem5_se_trace_extraction/sequential/run_stderr.txt
examples/lt/results/gem5_se_trace_extraction/sequential/convert_stdout.txt
examples/lt/results/gem5_se_trace_extraction/sequential/convert_stderr.txt
examples/lt/traces/gem5_sequential_trace.csv

examples/lt/results/gem5_se_trace_extraction/stride/run_stdout.txt
examples/lt/results/gem5_se_trace_extraction/stride/run_stderr.txt
examples/lt/results/gem5_se_trace_extraction/stride/convert_stdout.txt
examples/lt/results/gem5_se_trace_extraction/stride/convert_stderr.txt
examples/lt/traces/gem5_stride_trace.csv
```

通过标准：

- 两条 extraction 命令 exit code 均为 0。
- marker source 为 gem5 output dir 下的 `simout` 或 wrapper 捕获的 `run_stdout.txt`。
- marker source 中存在 `PROJECT_C_MEM`。
- normalized trace schema 包含：

```text
workload_name,txn_id,timestamp_ns,initiator_id,command,address,size_bytes,pc,symbol,source
```

- real gem5 run 的 `source` 为 `gem5_se_simout`。
- `timestamp_ns` 是 converter 生成的 normalized replay timestamp，不是 gem5 tick。

如果 gem5 不可用，可以用 `convert_gem5_se_trace.py --sample-pattern` 生成格式样例，但这只能验证 CSV 格式，不能作为真实 Project C gem5 validation。

## 6. Project C Replay Regression

目的：验证 gem5 SE-derived normalized traces 可以复用 Project B replay backend。

先验证 schema：

```bash
python3 examples/lt/tools/run_trace_replay_lab.py \
  --validate-only \
  --trace examples/lt/traces/gem5_sequential_trace.csv \
  --trace examples/lt/traces/gem5_stride_trace.csv
```

再执行 replay：

```bash
python3 examples/lt/tools/run_trace_replay_lab.py \
  --trace examples/lt/traces/gem5_sequential_trace.csv \
  --trace examples/lt/traces/gem5_stride_trace.csv \
  --output-dir examples/lt/results/gem5_trace_replay_lab
```

预期输出：

```text
examples/lt/results/gem5_trace_replay_lab/trace.csv
examples/lt/results/gem5_trace_replay_lab/summary.csv
examples/lt/results/gem5_trace_replay_lab/comparison.md
```

通过标准：

- validate-only 输出 `Project B normalized trace schema PASS`。
- replay exit code 为 0。
- `summary.csv` 包含 `gem5_sequential_scan` 和 `gem5_stride_scan`。
- `comparison.md` 明确说明这是 gem5 SE-derived trace replay，不是 gem5-SystemC live co-simulation。
- stride-shaped trace 在当前 minimal bank abstraction 下应比 sequential-shaped trace 有更高的 `bank_conflict_ratio_pct`，除非 workload 或 converter 参数被刻意改变。

## 7. Project D Standalone C++ Replay Regression

目的：验证 Project D C++ replay engine 没有被 Project E 改动破坏，并且 Python vs C++
summary equivalence 仍通过。

命令：

```bash
cmake -S examples/lt/replay_cpp -B build/examples/lt/replay_cpp
cmake --build build/examples/lt/replay_cpp

python3 examples/lt/tools/demo_cpp_trace_replay_lab.py --no-build
```

预期输出：

```text
examples/lt/results/cpp_trace_replay_lab/trace.csv
examples/lt/results/cpp_trace_replay_lab/summary.csv
examples/lt/results/cpp_trace_replay_lab/comparison.md
examples/lt/results/cpp_trace_replay_lab_python/trace.csv
examples/lt/results/cpp_trace_replay_lab_python/summary.csv
```

通过标准：

- C++ replay 输出 `[replay-cpp] Project D standalone C++ trace replay PASS`。
- comparison tool 输出 `[compare] Python vs C++ replay summary equivalence PASS`。
- demo 输出 `[demo-cpp] Project D Standalone C++ Trace Replay MVP PASS`。
- `summary.csv` 字段顺序仍与 Project B Python replay 对齐。
- Project D 不新增 SystemC、gem5 live、DRAM、AXI、CHI、NoC 或 cycle-accuracy claim。

## 8. Project E Banked Memory Controller Queueing Regression

目的：验证 standalone C++ banked memory controller + queueing model 可以一键运行，并生成
Project E 所需的 trace、summary 和 comparison。

命令：

```bash
cmake -S examples/lt/banked_memory_controller_cpp \
  -B build/examples/lt/banked_memory_controller_cpp
cmake --build build/examples/lt/banked_memory_controller_cpp

python3 examples/lt/tools/demo_banked_memory_controller_lab.py --no-build
```

预期输出：

```text
examples/lt/results/project_e_banked_memory_controller/trace.csv
examples/lt/results/project_e_banked_memory_controller/summary.csv
examples/lt/results/project_e_banked_memory_controller/comparison.md
```

通过标准：

- demo exit code 为 0。
- demo 输出 `Project E Banked Memory Controller Queueing MVP PASS`。
- `summary.csv` 包含 `sequential_scan`、`stride_scan`、`hot_bank_stress`。
- `summary.csv` 至少包含：

```text
workload,bank_count,queue_depth,transactions,avg_latency_ns,
p95_latency_ns,p99_latency_ns,max_latency_ns,throughput_txn_per_us,
avg_queue_occupancy,max_queue_occupancy,bank_utilization_pct,
row_hit_ratio_pct,stalled_or_rejected_transactions
```

- `hot_bank_stress` 的 `max_queue_occupancy` 和 p99/max latency 应明显高于
  `sequential_scan`。
- `hot_bank_stress` 在默认 `queue_depth=16` 下应产生非零
  `stalled_or_rejected_transactions`。
- `comparison.md` 明确说明这是 trend-level memory subsystem behavior，不是
  cycle-accurate DRAM，也不声称 AXI、CHI 或 NoC protocol compliance。

常见失败桶：

- C++ binary 未构建，且 demo 使用了 `--no-build`。
- 输入 trace 缺少 `address` 或 `masked_address`。
- `queue_depth` 或 `bank_count` 被设为 0。
- 使用了不支持的 `command` 字段值。

## 9. Optional AT Arbitration Regression

虽然 Project B / Project C 当前走 LT replay backend，AT lab 仍是当前模型层级的一部分。需要验证 AT phase-level timing refinement 时运行：

```bash
cmake -S examples/at -B build/examples/at
cmake --build build/examples/at

python3 examples/at/tools/demo_at_lab.py \
  --binary ./build/examples/at/at
```

如果 SystemC 不在默认搜索路径，构建时显式传入：

```bash
cmake -S examples/at -B build/examples/at \
  -DUSER_SYSTEMC_LIB_DIR=<absolute path to SystemC lib> \
  -DUSER_SYSTEMC_INCLUDE_DIR=<absolute path to SystemC include>
cmake --build build/examples/at
```

通过标准：

- demo exit code 为 0。
- `phase_trace.csv` 存在。
- `examples/at/results/analysis.txt` 存在。
- `examples/at/results/arbitration_sweep/summary.csv` 存在。
- `examples/at/results/arbitration_sweep/comparison.md` 存在。
- comparison 不声称 AXI、CHI、NoC 或 cycle accuracy。

## 10. Regression Result Template

每次手工回归建议记录：

```text
date:
host:
repo path:
SystemC path:
gem5 binary:
gem5 config:
target compiler:

Project B validate-only: PASS/FAIL
Project B demo: PASS/FAIL
Project C workload ELF checks: PASS/FAIL
Project C extraction sequential: PASS/FAIL
Project C extraction stride: PASS/FAIL
Project C replay validate-only: PASS/FAIL
Project C replay: PASS/FAIL
Project D demo + equivalence: PASS/FAIL
Project E demo: PASS/FAIL
Optional AT demo: PASS/FAIL

generated artifacts:
known failures:
scope notes:
```

## 11. Mac-to-Ubuntu Packaging Reminder

从 Mac 打包到 Ubuntu 环境时，使用：

```bash
tar --disable-copyfile --no-xattrs -czf systemc-tlm-performance-labs.tar.gz \
  systemc-tlm-performance-labs
```

这样可以避免 macOS resource fork 和 xattrs 生成 `._*` 文件污染源码。
