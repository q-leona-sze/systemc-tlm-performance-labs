# Project AT-7: GPU-like Throughput Engine and Memory Saturation Lab

## Purpose

Project AT-7 建立一个 bounded AT-level synthetic GPU-like throughput problem type
lab。它用多个 throughput-oriented logical lanes 产生高并发 memory requests，观察
outstanding-depth sensitivity、memory bandwidth saturation、latency hiding
approximation、burstiness、queue buildup、throughput knee point 和 bandwidth wall。

当前状态：

```text
Status: independent lab implemented and integrated into portfolio evidence harness
```

Project V 已经把 AT-7 纳入 portfolio evidence harness；当前 portfolio evidence
schema 是 `p0.4`，Stage 2 harness projects 包含 AT-6 和 AT-7。

## Model

AT-7 使用 deterministic synthetic model。它不是复杂 scheduler，也不模拟真实 CUDA
block / thread / warp 语义；它只抽象 throughput-oriented memory pressure。

核心组件：

- GPU-like throughput engine: 多个 logical lanes，固定 request count、burst
  length、compute gap、per-lane outstanding limit 和 global outstanding limit。
- Shared memory subsystem: 一个 shared memory request queue，一个 bounded service
  path，以及 queue capacity。
- Bandwidth wall: 通过 `memory_service_time_ns` 和
  `service_bandwidth_bytes_per_ns` 形成有效 service limit。
- Backpressure / stall detection: 当 per-lane outstanding、global outstanding 或
  memory queue capacity 达到限制时记录 stall episode。
- Latency hiding approximation: 当 outstanding depth 足够时，模型按 synthetic rule
  隐藏部分 service latency；当 queue saturated 时，更多 latency 转化为 exposed stall。

这个模型的目的不是复刻任何真实 GPU 微结构，而是隔离 throughput-oriented memory
pressure 下的 architecture tradeoff。

## Cases

| case | interpretation |
| --- | --- |
| `low_occupancy` | 低 lane count 和浅 outstanding depth；memory system 未被打满，吞吐较低但 tail latency 可控。 |
| `balanced_occupancy` | 中等 outstanding depth；接近有效 bandwidth 利用，并保持相对可控的 queue delay。 |
| `high_occupancy` | 高 request injection pressure；吞吐接近 saturation knee，queue delay 和 tail latency 上升。 |
| `bandwidth_saturation` | 更多 lanes 和 outstanding depth 继续施压；throughput 提升有限，bandwidth wall 更明显。 |
| `bursty_stress` | 增大 burst length；观察 burst traffic 对 queue peak、tail latency 和 stall ratio 的影响。 |
| `throttled_occupancy` | 限制 outstanding depth / injection rate；观察牺牲少量峰值吞吐后 tail latency 是否改善。 |

## Metrics

`summary.csv` 每个 case 一行，核心字段包括：

- latency: `avg_latency_ns`, `p50_latency_ns`, `p95_latency_ns`,
  `p99_latency_ns`, `max_latency_ns`
- throughput / bandwidth: `throughput_req_per_us`,
  `effective_bandwidth_bytes_per_ns`, `memory_utilization_ratio`
- queue pressure: `avg_queue_delay_ns`, `p95_queue_delay_ns`, `queue_peak`,
  `avg_queue_depth`
- outstanding depth: `avg_outstanding`, `peak_outstanding`
- stall / saturation: `stall_events`, `stall_ratio`, `saturation_flag`,
  `knee_point_hint`
- latency hiding approximation: `hidden_latency_ns`, `exposed_stall_ns`

这些 metrics 是 synthetic run 内的 architecture reasoning signals，不是硬件带宽测量
或 silicon timing data。

## Portfolio Evidence Integration

Project V 后，portfolio evidence harness 会检查 AT-7 的以下内容：

- `summary.csv` exists:
  `examples/at/results/project_at7_gpu_like_throughput_saturation/summary.csv`
- `comparison.md` exists:
  `examples/at/results/project_at7_gpu_like_throughput_saturation/comparison.md`
- `summary.csv` covers six expected cases: `low_occupancy`,
  `balanced_occupancy`, `high_occupancy`, `bandwidth_saturation`,
  `bursty_stress`, and `throttled_occupancy`
- `summary.csv` preserves key schema fields for latency percentiles,
  throughput, effective bandwidth, memory utilization, queue delay,
  outstanding depth, stall ratio, hidden latency, exposed stall,
  `saturation_flag`, and `knee_point_hint`
- `comparison.md` preserves claim-boundary wording: AT-7 remains a bounded
  AT-level synthetic GPU-like throughput and memory saturation exploration; it
  does not claim NVIDIA GPU simulation, real GPU behavior, CUDA execution
  modeling, real HBM-controller behavior, cycle-accurate modeling, silicon
  validation, or production signoff

Expected portfolio PASS footer:

```text
Portfolio Evidence Pack PASS
stage1_projects=AT-1,AT-2,AT-3,AT-4,AT-5,K,L
stage2_projects=AT-6,AT-7
projects=AT-1,AT-2,AT-3,AT-4,AT-5,K,L,AT-6,AT-7
claim_boundary=PASS
schema_version=p0.4
```

## Expected Interpretation

AT-7 的结果应当用于 trend comparison、bottleneck isolation 和 recommendation
logic：

- 如果 `low_occupancy` memory utilization 明显低于 saturation 区间，说明 throughput
  受 occupancy / outstanding depth 限制。
- 如果 `balanced_occupancy` 提升 throughput 且 p95/p99 latency 仍可控，说明该区间更适合作为
  latency hiding / throughput balance 的参考点。
- 如果 `high_occupancy` 或 `bandwidth_saturation` 的 throughput 增幅变小，而
  queue delay、p99 latency 和 stall ratio 增大，说明已经接近或越过 throughput knee。
- 如果 `bursty_stress` 的 queue peak 和 p99 latency 明显上升，说明 burstiness 是独立压力来源。
- 如果 `throttled_occupancy` 的 throughput 只小幅下降但 tail latency 改善，它可以作为 bounded
  recommendation baseline。

## Claim Boundary

This lab is a bounded AT-level synthetic GPU-like throughput and memory saturation
exploration. It does not claim NVIDIA GPU simulation, real GPU behavior, CUDA
execution modeling, real HBM-controller behavior, cycle-accurate modeling,
silicon validation, or production signoff.

安全表达：

- GPU-like throughput problem type
- NVIDIA-like throughput problem type
- bounded AT-level synthetic architecture exploration
- throughput-oriented memory pressure
- outstanding-depth sensitivity
- bandwidth saturation
- latency hiding approximation
- bottleneck isolation
- recommendation logic

不支持的 claim：

- not a real CUDA execution model
- not a real SM / warp scheduler
- not a real HBM / GDDR memory controller
- not a cycle-accurate model
- not silicon validation
- not production signoff

## How To Build

从仓库根目录运行：

```bash
cmake -S examples/at -B build-at \
  -DUSER_SYSTEMC_LIB_DIR=$HOME/local/systemc/lib \
  -DUSER_SYSTEMC_INCLUDE_DIR=$HOME/local/systemc/include
cmake --build build-at --target project_at7_gpu_like_throughput_saturation -j
```

## How To Run

默认运行只生成 `summary.csv` 和 `comparison.md`：

```bash
./build-at/project_at7_gpu_like_throughput_saturation
```

输出目录：

```text
examples/at/results/project_at7_gpu_like_throughput_saturation/
```

核心产物：

```text
examples/at/results/project_at7_gpu_like_throughput_saturation/summary.csv
examples/at/results/project_at7_gpu_like_throughput_saturation/comparison.md
```

如果需要 compact trace，可显式运行：

```bash
./build-at/project_at7_gpu_like_throughput_saturation --write-trace
```

默认不建议提交 `trace.csv`。

## How This Differs From Real GPU Simulation

AT-7 不包含真实 ISA、CUDA kernel semantics、SM pipeline、warp issue policy、cache
hierarchy、coalescing rules、HBM/GDDR timing、memory-controller protocol 或 vendor
microarchitecture。它只保留一个有边界的 architecture-level question：

```text
在 synthetic throughput-oriented memory pressure 下，outstanding depth 从不足到过量时，
throughput、queue depth、tail latency、stall ratio 和 bandwidth wall 如何变化？
```

因此，AT-7 可以支持 portfolio discussion 中的 bounded architecture reasoning；它不能支持
真实 GPU performance claim、cycle-level timing claim 或 production signoff claim。
