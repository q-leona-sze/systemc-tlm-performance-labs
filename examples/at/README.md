# AT 架构性能建模实验链

[项目总览](../../README.md) | [LT 实验链](../lt/README_performance_lab.md)

`examples/at/` 是本书配套仓库的 AT 主线，用 TLM-2.0 approximately-timed
四阶段事务、multi-initiator contention、QoS-like policy sensitivity、
backpressure、shared-fabric pressure、GPU-like throughput saturation 和
AMBA-inspired boundary pressure 来观察早期架构权衡。

本目录的目标不是实现真实 AXI、CHI、ACE、NoC、cache coherence、DRAM controller
或 GPU/HBM model。所有 AT-1 至 AT-8 项目都是 bounded synthetic architecture
experiments，用于把：

```text
workload -> trace -> metrics -> sweep -> comparison -> validation -> diagnosis
```

做成可复现、可审查、可在面试中讲清楚边界的实验链。

## Current / Supported / Not Supported / Future Work

| Category | Scope |
| --- | --- |
| Current | AT-1 至 AT-8 的独立 SystemC/TLM AT labs、Python demo wrappers、summary/comparison artifacts 和 portfolio harness checks。 |
| Supported | 在同一模型、同一 CSV contract、同一 generated report 规则下做趋势、相对比较、瓶颈定位和 claim-boundary 检查。 |
| Not Supported | cycle accuracy、AXI/CHI/ACE/NoC protocol compliance、real cache coherence、real DRAM/HBM timing、vendor GPU/SoC simulation、silicon validation、production signoff。 |
| Future Work | 更强的 reference correlation、更多 workload fixtures、明确版本化的 metric contracts、可选 RTL/profiler 对齐路径。 |

## 实验地图

| Lab | 路径 / Target | 架构问题 | 主要输出 |
| --- | --- | --- | --- |
| AT smoke | `examples/at/systemc/` / `at` | TLM-2.0 AT 四阶段事务与双 initiator arbitration 的最小可视化。 | `phase_trace.csv`、analysis summary |
| AT-1 | `four_phase_memory_timing/` / `project_at1_four_phase_memory_timing` | request accept latency、target service latency、response latency 与 initiator blocked time。 | `project_at1_summary.csv`、`project_at1_report.md` |
| AT-2 | `multi_initiator_arbitration/` / `project_at2_multi_initiator_arbitration` | multi-initiator arbitration、fairness、back-pressure 与 tail latency。 | `project_at2_policy_summary.csv`、`project_at2_report.md` |
| AT-3 | `qos_sensitivity_sla/` / `project_at3_qos_sensitivity_sla` | QoS-like weights、queue depth、service latency 与 SLA violation。 | `project_at3_policy_sweep.csv`、`project_at3_recommendations.csv`、`project_at3_report.md` |
| AT-4 | `project_at4_cache_mshr_pressure.cpp` | cache-like shared resource、MSHR-like pressure、pollution proxy 与 diminishing return。 | `project_at4_summary.csv`、`project_at4_policy_sweep.csv`、`project_at4_report.md` |
| AT-5 | `project_at5_backpressure_qos_collapse.cpp` | downstream saturation 下 QoS policy 的边界、backpressure propagation 与 collapse signal。 | `project_at5_summary.csv`、`project_at5_policy_sweep.csv`、`project_at5_report.md` |
| AT-6 | `project_at6_heterogeneous_soc_fabric.cpp` | CPU/NPU/DMA/ISP-like traffic 共享 memory fabric 时的 interference、bandwidth partitioning 与 starvation risk。 | `summary.csv`、`comparison.md` |
| AT-7 | `project_at7_gpu_like_throughput_saturation.cpp` | throughput-engine outstanding depth、latency hiding approximation、queue buildup 与 bandwidth wall。 | `summary.csv`、`comparison.md` |
| AT-8 | `project_at8_amba_noc_qos_coherency_boundary.cpp` | AMBA-inspired QoS class、route contention、ordering pressure 与 coherency-boundary pressure。 | `summary.csv`、`comparison.md` |

## 构建方式

SystemC 是外部依赖。若安装在标准搜索路径，`USER_SYSTEMC_*` 可以省略；否则从仓库根目录显式提供 include/lib：

```bash
cmake -S examples/at -B build/examples/at \
  -DUSER_SYSTEMC_LIB_DIR=<absolute path to SystemC lib> \
  -DUSER_SYSTEMC_INCLUDE_DIR=<absolute path to SystemC include>
cmake --build build/examples/at
```

仓库根目录的现代 build 也可以通过 `SYSTEMC_HOME` / `CMAKE_PREFIX_PATH` / `SystemC_DIR`
配置。推荐的 Ubuntu matrix 见
[`docs/reproducibility/ubuntu_modern_toolchain_validation.md`](../../docs/reproducibility/ubuntu_modern_toolchain_validation.md)。

## AT smoke lab

最小 AT smoke lab 包含两个 initiator、一个 simple AT bus / arbiter、一个 shared target，
并记录 `BEGIN_REQ`、`END_REQ`、`BEGIN_RESP`、`END_RESP` 四阶段 trace。

运行：

```bash
./build/examples/at/at
python3 examples/at/tools/analyze_phase_trace.py --trace phase_trace.csv --fail-on-sanity
```

policy knob：

```bash
AT_ARBITRATION_POLICY=fifo ./build/examples/at/at
AT_ARBITRATION_POLICY=priority_101 ./build/examples/at/at
AT_ARBITRATION_POLICY=priority_102 ./build/examples/at/at
```

一键 demo：

```bash
python3 examples/at/tools/demo_at_lab.py \
  --binary ./build/examples/at/at
```

该 smoke lab 只验证 AT phase flow、trace schema 和 request accept latency 的可观测性；
它不是真实互连或协议合规模型。

## AT-1：Four-Phase Memory Transaction Timing

AT-1 聚焦单 initiator 到 bounded memory target 的四阶段事务时序，展示 finite queue depth、
initiator stall 和 visible back-pressure。

运行：

```bash
python3 examples/at/tools/demo_project_at1_four_phase_memory_timing.py
```

输出：

- `examples/at/results/project_at1_four_phase_memory_timing/model_runs/<case_name>/trace.csv`
- `examples/at/results/project_at1_four_phase_memory_timing/project_at1_summary.csv`
- `examples/at/results/project_at1_four_phase_memory_timing/project_at1_report.md`

边界：AT-1 是 SystemC/TLM AT teaching and architecture modeling lab；不是 AXI/CHI
compliance、cycle-accurate simulation、silicon validation、production signoff 或真实
DRAM timing model。

## AT-2：Multi-Initiator Arbitration and Contention

AT-2 从单 initiator 扩展到 `cpu0`、`dma0`、`accel0` 共享 target path，比较
`round_robin`、`fixed_priority` 和 `weighted_priority` 对 fairness、p95/p99 tail
latency、back-pressure 与 throughput 的影响。

运行：

```bash
cmake -S examples/at -B build-at \
  -DUSER_SYSTEMC_INCLUDE_DIR=$HOME/local/systemc/include \
  -DUSER_SYSTEMC_LIB_DIR=$HOME/local/systemc/lib

cmake --build build-at --target project_at2_multi_initiator_arbitration -j

python3 examples/at/tools/demo_project_at2_multi_initiator_arbitration.py \
  --build-dir build-at
```

输出：

- `examples/at/results/project_at2_multi_initiator_arbitration/model_runs/<case_name>/trace.csv`
- `examples/at/results/project_at2_multi_initiator_arbitration/project_at2_summary.csv`
- `examples/at/results/project_at2_multi_initiator_arbitration/project_at2_policy_summary.csv`
- `examples/at/results/project_at2_multi_initiator_arbitration/project_at2_report.md`

边界：AT-2 只支持 bounded contention and arbitration comparison；不是 real NoC、
cache coherence、DRAM timing、cycle accuracy 或 silicon validation。

## AT-3：QoS Sensitivity and SLA Violation

AT-3 研究 QoS-like weighted arbitration、queue depth、service latency、SLA violation
rate、protected traffic class 与 fairness tradeoff。

运行：

```bash
cmake --build build-at --target project_at3_qos_sensitivity_sla -j

python3 examples/at/tools/demo_project_at3_qos_sensitivity_sla.py \
  --build-dir build-at
```

输出：

- `examples/at/results/project_at3_qos_sensitivity_sla/model_runs/<case_name>/trace.csv`
- `examples/at/results/project_at3_qos_sensitivity_sla/project_at3_summary.csv`
- `examples/at/results/project_at3_qos_sensitivity_sla/project_at3_policy_sweep.csv`
- `examples/at/results/project_at3_qos_sensitivity_sla/project_at3_recommendations.csv`
- `examples/at/results/project_at3_qos_sensitivity_sla/project_at3_report.md`

边界：AT-3 的 weighted arbitration 是 QoS-like architecture exploration；不是
AXI/CHI QoS compliance、real NoC、cache coherence、silicon validation 或 production
signoff。

## AT-4：Cache-Like Shared Resource and MSHR Pressure

AT-4 建模 bounded path：

```text
initiator -> interconnect/arbitration -> cache-like shared resource -> memory target
```

它把 locality、MSHR-like outstanding miss pressure、shared interference、
pollution proxy、p95/p99 tail latency 与 diminishing return 分开观察。

运行：

```bash
cmake --build build-at --target project_at4_cache_mshr_pressure -j

python3 examples/at/tools/demo_at4_cache_mshr_pressure.py \
  --at-build-dir build-at
```

边界：AT-4 不是真实 cache hierarchy、replacement policy、cache coherence、real NoC、
cycle-accurate timing、silicon validation 或 production signoff。

## AT-5：Backpressure and QoS Collapse

AT-5 建模 bounded path：

```text
initiators -> QoS arbiter -> ingress queue -> shared downstream service -> memory target
```

核心观察是：当 downstream memory service / shared resource 已经饱和时，priority policy
只能改变局部排队顺序，不能创造新的系统服务能力。因此 `cpu_rt` 可能短期受益，
`dma_bulk` 可能被牺牲，而 latency-sensitive SLA 仍然无法满足。

运行：

```bash
cmake --build build-at --target project_at5_backpressure_qos_collapse -j

python3 examples/at/tools/demo_at5_backpressure_qos_collapse.py \
  --at-build-dir build-at
```

输出：

- `examples/at/results/project_at5_backpressure_qos_collapse/model_runs/<case_name>/trace.csv`
- `examples/at/results/project_at5_backpressure_qos_collapse/project_at5_summary.csv`
- `examples/at/results/project_at5_backpressure_qos_collapse/project_at5_policy_sweep.csv`
- `examples/at/results/project_at5_backpressure_qos_collapse/project_at5_recommendations.csv`
- `examples/at/results/project_at5_backpressure_qos_collapse/project_at5_report.md`

边界：AT-5 支持 synthetic trend comparison across queue capacity、downstream service
latency、QoS policy、backpressure、fairness 和 SLA collapse signals；不支持 real
NoC、AXI/CHI compliance、real DRAM controller timing、cache coherence、cycle accuracy、
silicon validation 或 production signoff。

## AT-6 / AT-7 / AT-8：Stage 2 Problem Families

AT-6、AT-7 和 AT-8 是 Stage 2 的三个 bounded synthetic problem families。它们已经接入
portfolio evidence harness，用 `summary.csv`、`comparison.md`、case coverage、schema
fields 和 claim-boundary wording 做验证。

运行：

```bash
cmake --build build-at --target project_at6_heterogeneous_soc_fabric -j
./build-at/project_at6_heterogeneous_soc_fabric --no-trace

cmake --build build-at --target project_at7_gpu_like_throughput_saturation -j
./build-at/project_at7_gpu_like_throughput_saturation

cmake --build build-at --target project_at8_amba_noc_qos_coherency_boundary -j
./build-at/project_at8_amba_noc_qos_coherency_boundary
```

边界：

- AT-6 不是 Apple Silicon simulation、real NoC behavior、cycle-accurate modeling、
  silicon validation 或 production signoff。
- AT-7 不是 NVIDIA GPU simulation、CUDA execution modeling、real GPU behavior、
  real HBM-controller behavior、cycle-accurate modeling、silicon validation 或
  production signoff。
- AT-8 不是 Arm CHI/AXI/ACE compliance、real AMBA protocol behavior、real NoC
  behavior、real cache coherency、cycle-accurate modeling、silicon validation 或
  production signoff。

## Trace analysis

AT smoke lab 的 `phase_trace.csv` 可以用 analyzer 重建 transaction timeline：

```bash
python3 examples/at/tools/analyze_phase_trace.py --trace phase_trace.csv
python3 examples/at/tools/analyze_phase_trace.py --trace phase_trace.csv --fail-on-sanity
python3 examples/at/tools/analyze_phase_trace.py --trace phase_trace.csv --summary-csv-output /tmp/at_summary.csv
python3 examples/at/tools/analyze_phase_trace.py --trace phase_trace.csv --timeline-csv-output /tmp/at_timeline.csv
```

`--summary-csv-output` 写 run-level metrics；`--timeline-csv-output` 写 per-transaction
timeline。AT-1 至 AT-8 的 dedicated demo wrappers 会各自生成对应 `summary.csv`、
`comparison.md` 或 project report。
