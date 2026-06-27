# Project AT-6: Heterogeneous SoC Shared Memory Fabric Lab

## Purpose

Project AT-6 建立一个 bounded AT-level synthetic heterogeneous SoC shared-memory
fabric exploration。它用 CPU-like、NPU-like、DMA-like、ISP-like 四类 initiator
共享一个 synthetic memory fabric，观察 mixed traffic interference、bandwidth
partitioning、latency-sensitive flow protection、starvation risk、QoS policy 和
bandwidth cap 的趋势。

当前状态：

```text
Status: independent Stage 2 lab implemented and integrated into portfolio evidence harness
```

Project U 将 AT-6 纳入 portfolio evidence harness，但 AT-6 仍然是 Stage 2
independent lab，不是 Stage 1 内容。

## Model

AT-6 使用 deterministic synthetic model：

- CPU-like initiator: latency-sensitive、moderate request rate、small bursts、low
  outstanding-style pressure，并带 SLA latency threshold。
- NPU-like initiator: throughput-oriented、bursty traffic、high pressure、较高
  latency tolerance，容易占用 shared fabric bandwidth。
- DMA-like initiator: long sequential bursts、bulk transfer pressure、连续 request
  pattern。
- ISP-like initiator: periodic streaming traffic、medium burst、latency-sensitive
  / deadline-sensitive-ish，并带 SLA latency threshold。

Shared fabric 抽象包含：

- request queue
- arbitration policy
- per-initiator latency / throughput / bandwidth-share stats
- service delay and queue delay
- priority-like protection
- NPU token-like bandwidth cap
- starvation event detection

这个模型不要求真实协议，不做完整 TLM protocol checker，也不提供 cycle accuracy。

## Cases

| case | policy | interpretation |
| --- | --- | --- |
| `baseline_rr` | round-robin arbitration, no bandwidth cap | 建立 balanced mixed traffic baseline |
| `priority_latency` | CPU-like / ISP-like priority, no bandwidth cap | 观察 priority 是否降低 latency-sensitive tail latency |
| `bandwidth_cap_npu` | latency priority plus NPU token-like cap | 观察牺牲部分 NPU throughput 后 CPU/ISP p95/p99 是否改善 |
| `dma_stress` | round-robin with stronger DMA pressure | 隔离 bulk transfer 对 shared fabric 的影响 |
| `mixed_stress` | NPU + DMA high pressure, latency priority, no cap | 观察 shared fabric pressure 下 starvation、tail latency collapse 或 QoS failure risk |

## Metrics

`summary.csv` 每个 case 一行，核心字段包括：

- overall latency: `avg_latency_ns`, `p50_latency_ns`, `p95_latency_ns`,
  `p99_latency_ns`, `max_latency_ns`
- throughput: `throughput_txn_per_us`
- pressure indicators: `fabric_queue_peak`, `starvation_events`
- per-flow metrics: CPU/NPU/DMA/ISP p95/p99 latency and throughput
- SLA indicators: `cpu_sla_violation_ratio`, `isp_sla_violation_ratio`
- byte-share indicators: `npu_bandwidth_share`, `dma_bandwidth_share`,
  `isp_bandwidth_share`

`bandwidth_share` 字段是本 synthetic run 内按 bytes 计算的百分比，不是硬件带宽测量。

## Portfolio Evidence Integration

Project U 后，portfolio evidence harness 会检查 AT-6 的以下内容：

- `examples/at/results/project_at6_heterogeneous_soc_fabric/summary.csv` 存在。
- `examples/at/results/project_at6_heterogeneous_soc_fabric/comparison.md` 存在。
- `summary.csv` 覆盖 `baseline_rr`、`priority_latency`、`bandwidth_cap_npu`、
  `dma_stress`、`mixed_stress` 五个 case。
- `summary.csv` 保留 AT-6 的真实 metrics schema，包括 latency、throughput、
  bandwidth share、queue peak、starvation events 和 SLA violation ratio。
- `comparison.md` 保留 bounded claim boundary，明确 AT-6 remains a bounded
  AT-level synthetic heterogeneous SoC shared-memory fabric exploration.

Expected portfolio PASS marker:

```text
Portfolio Evidence Pack PASS
stage1_projects=AT-1,AT-2,AT-3,AT-4,AT-5,K,L
stage2_projects=AT-6
claim_boundary=PASS
schema_version=p0.3
```

## Expected Interpretation

AT-6 的结果应该用于 trend comparison、bottleneck isolation 和 bounded
recommendation logic：

- 如果 `priority_latency` 降低 CPU-like / ISP-like p99 latency，说明 priority
  可以重新分配 contention，但不代表 fabric service capacity 增加。
- 如果 `bandwidth_cap_npu` 改善 CPU/ISP p95/p99，同时降低 NPU throughput，说明
  bandwidth partitioning 有保护 latency-sensitive flow 的趋势成本。
- 如果 `dma_stress` 增加 queue peak 或 DMA bandwidth share，说明 bulk transfer
  是独立瓶颈来源。
- 如果 `mixed_stress` 出现 starvation events 或 SLA violation，说明 shared-memory
  fabric pressure 已超过简单 priority policy 的保护能力。

## Claim Boundary

This lab is a bounded AT-level synthetic heterogeneous SoC shared-memory fabric
exploration. It does not claim Apple Silicon simulation, real NoC behavior,
cycle-accurate modeling, silicon validation, or production signoff.

安全表达：

- bounded AT-level synthetic architecture exploration
- heterogeneous SoC problem type
- Apple-like heterogeneous SoC problem type
- shared-memory fabric pressure
- trend comparison
- bottleneck isolation
- recommendation logic

不支持的 claim：

- not a real Apple SoC model
- not real NoC behavior
- not a real DRAM controller
- not a cycle-accurate fabric model
- not silicon validation
- not production signoff

## How To Build

从仓库根目录运行：

```bash
cmake -S . -B build-at \
  -DCMAKE_BUILD_TYPE=Release \
  -DUSER_SYSTEMC_ROOT=$HOME/local/systemc
cmake --build build-at --target project_at6_heterogeneous_soc_fabric -j
```

如果本地使用独立 `examples/at` configure，也可以显式传入 SystemC include/lib：

```bash
cmake -S examples/at -B build-at \
  -DUSER_SYSTEMC_INCLUDE_DIR=$HOME/local/systemc/include \
  -DUSER_SYSTEMC_LIB_DIR=$HOME/local/systemc/lib
cmake --build build-at --target project_at6_heterogeneous_soc_fabric -j
```

## How To Run

默认运行会生成 `summary.csv`、`comparison.md` 和 compact `trace.csv`：

```bash
./build-at/examples/at/project_at6_heterogeneous_soc_fabric
```

如果使用独立 `examples/at` build directory，可执行路径通常是：

```bash
./build-at/project_at6_heterogeneous_soc_fabric
```

输出目录：

```text
examples/at/results/project_at6_heterogeneous_soc_fabric/
```

核心产物：

```text
examples/at/results/project_at6_heterogeneous_soc_fabric/summary.csv
examples/at/results/project_at6_heterogeneous_soc_fabric/comparison.md
examples/at/results/project_at6_heterogeneous_soc_fabric/trace.csv
```
