# Project AT-8: AMBA-inspired NoC QoS and Coherency Boundary Lab

## Purpose

Project AT-8 建立一个 bounded AT-level synthetic AMBA-inspired NoC QoS and
coherency-boundary exploration。它面向 Arm-like interconnect problem type，但保持
protocol-inspired but not protocol-compliant 的边界：用多个 initiator、route、QoS
class、read/write flow 和 coherent-vs-noncoherent boundary crossing 的抽象，观察
QoS class pressure、route contention、ordering pressure、coherency-boundary
pressure、read/write interference、tail latency、starvation risk 和 recommendation
logic。

当前状态：

```text
Status: independent lab implemented and integrated into portfolio evidence harness
```

Project W 已把 AT-8 纳入 portfolio evidence harness。当前 portfolio evidence
schema 是 `p0.5`，Stage 2 harness projects 是 AT-6、AT-7 和 AT-8。

## Model

AT-8 使用 deterministic synthetic model，不引入外部依赖，不模拟真实 AMBA
transaction，也不实现真实 coherency state machine。

核心 initiator：

- CPU-like coherent initiator: latency-sensitive、read-heavy、coherent-domain
  traffic。
- DMA-like noncoherent initiator: bulk transfer、write-heavy、noncoherent-domain
  traffic。
- NPU-like accelerator initiator: high-throughput、bursty、mixed noncoherent /
  boundary-crossing traffic。
- IO-like peripheral initiator: low-throughput、latency-sensitive、
  ordering-sensitive traffic。

Route / interconnect resource：

- `local_route`
- `shared_route`
- `boundary_route`

每条 route 有 queue capacity、base service delay、congestion multiplier、
route utilization 和 queue peak。QoS class 影响 arbitration / service order，但不创造
新的 downstream capacity。

QoS classes：

- `latency_high`
- `best_effort`
- `bulk_low`

Coherency-boundary abstraction：

- coherent traffic
- noncoherent traffic
- boundary crossing traffic

Boundary crossing 会增加 synthetic `boundary_penalty_ns`、
`ordering_delay_ns`、serialization event 和 `coherency_boundary_events`。这些字段只用于
architecture-level pressure reasoning。

Read/write interference：

- write-heavy bulk pressure 会延长 route service 和 write drain window。
- read flow 在 write pressure window 内会看到 bounded interference delay。
- ordering-sensitive / boundary-crossing transaction 会引入 serialization pressure。

## Cases

| case | interpretation |
| --- | --- |
| `baseline_qos_rr` | balanced traffic、round-robin arbitration、moderate route pressure，用作 baseline。 |
| `latency_qos_priority` | `latency_high` class 优先，CPU-like / IO-like flow 被保护，观察 QoS class protection。 |
| `bulk_dma_pressure` | DMA-like bulk writes 增加，观察 write-heavy / bulk traffic 对 shared route 和 read tail latency 的影响。 |
| `boundary_crossing_stress` | coherent / noncoherent boundary crossing 增加，观察 boundary penalty、ordering delay 和 serialization events。 |
| `route_hotspot` | 多个 initiator 映射到同一 hotspot route，观察 route contention、queue peak 和 starvation risk。 |
| `mixed_qos_collapse` | latency_high、bulk_low、boundary crossing 和 saturated downstream route 同时高压，观察 QoS policy 的硬边界。 |

## Metrics

`summary.csv` 每个 case 一行，核心字段包括：

- latency: `avg_latency_ns`, `p50_latency_ns`, `p95_latency_ns`,
  `p99_latency_ns`, `max_latency_ns`
- throughput: `throughput_txn_per_us`
- route pressure: `route_queue_peak`, `local_route_utilization`,
  `shared_route_utilization`, `boundary_route_utilization`,
  `avg_route_delay_ns`, `p95_route_delay_ns`
- boundary / ordering: `ordering_delay_ns`, `boundary_penalty_ns`,
  `coherency_boundary_events`, `ordering_serialization_events`
- read/write interference: `read_avg_latency_ns`, `read_p95_latency_ns`,
  `write_avg_latency_ns`, `write_p95_latency_ns`
- QoS class tail: `latency_high_p99_ns`, `best_effort_p99_ns`,
  `bulk_low_p99_ns`
- risk / recommendation: `starvation_events`, `qos_protection_score`,
  `collapse_score`, `recommendation`

这些 metrics 是 synthetic run 内的 architecture reasoning signals，不是 hardware
measurement 或 protocol verification evidence。

## Expected Interpretation

- 如果 `latency_qos_priority` 的 `latency_high_p99_ns` 低于 baseline 或明显低于
  `bulk_low_p99_ns`，说明 QoS priority 在当前 route capacity bound 内有保护趋势。
- 如果 `bulk_dma_pressure` 的 `read_p95_latency_ns` 明显上升，说明 write-heavy bulk
  flow 会通过 shared route pressure 推高 read tail latency。
- 如果 `boundary_crossing_stress` 的 `coherency_boundary_events`、
  `ordering_delay_ns` 和 `ordering_serialization_events` 上升，说明 boundary crossing
  是独立 pressure source。
- 如果 `route_hotspot` 的 `route_queue_peak` 和 `starvation_events` 上升，说明 route
  mapping / hotspot 是瓶颈，不应只调 QoS priority。
- 如果 `mixed_qos_collapse` 的 `collapse_score` 高，recommendation logic 应转向
  capacity、partitioning 或 traffic shaping，而不是继续提高 priority。

## Claim Boundary

This lab is a bounded AT-level synthetic AMBA-inspired NoC QoS and coherency-boundary exploration. It does not claim Arm CHI compliance, AXI compliance, ACE compliance, real AMBA protocol behavior, real NoC behavior, real cache coherency, cycle-accurate modeling, silicon validation, or production signoff.

安全表达：

- AMBA-inspired NoC problem type
- protocol-inspired but not protocol-compliant
- bounded AT-level synthetic architecture exploration
- QoS class pressure
- route contention
- coherency-boundary pressure
- ordering pressure
- read/write interference
- bottleneck isolation
- recommendation logic

不支持的 claim：

- not Arm CHI compliance
- not AXI compliance
- not ACE compliance
- not a real AMBA protocol model
- not a real NoC implementation
- not a real cache coherency model
- not a real DRAM controller model
- not cycle-accurate modeling
- not silicon validation
- not production signoff

## Portfolio Evidence Integration

Project W integrates AT-8 into the portfolio evidence harness without changing
AT-8 core simulation behavior, case definitions, or the `summary.csv` schema.
The harness checks:

- `summary.csv` existence:
  `examples/at/results/project_at8_amba_noc_qos_coherency_boundary/summary.csv`
- `comparison.md` existence:
  `examples/at/results/project_at8_amba_noc_qos_coherency_boundary/comparison.md`
- case coverage for `baseline_qos_rr`, `latency_qos_priority`,
  `bulk_dma_pressure`, `boundary_crossing_stress`, `route_hotspot`, and
  `mixed_qos_collapse`
- key schema fields for latency, throughput, route utilization, ordering delay,
  boundary penalty, coherency-boundary events, read/write tail latency,
  QoS-class p99 latency, starvation, collapse score, and recommendation
- claim-boundary wording that keeps AT-8 as a bounded AT-level synthetic
  AMBA-inspired NoC QoS and coherency-boundary exploration, not Arm CHI
  compliance, AXI compliance, ACE compliance, real AMBA protocol behavior,
  real NoC behavior, real cache coherency, cycle-accurate modeling, silicon
  validation, or production signoff

## How To Build

从仓库根目录运行：

```bash
cmake -S examples/at -B build-at \
  -DUSER_SYSTEMC_LIB_DIR=$HOME/local/systemc/lib \
  -DUSER_SYSTEMC_INCLUDE_DIR=$HOME/local/systemc/include
cmake --build build-at --target project_at8_amba_noc_qos_coherency_boundary -j
```

## How To Run

默认运行只生成 `summary.csv` 和 `comparison.md`：

```bash
./build-at/project_at8_amba_noc_qos_coherency_boundary
```

输出目录：

```text
examples/at/results/project_at8_amba_noc_qos_coherency_boundary/
```

核心产物：

```text
examples/at/results/project_at8_amba_noc_qos_coherency_boundary/summary.csv
examples/at/results/project_at8_amba_noc_qos_coherency_boundary/comparison.md
```

如果需要 compact trace，可显式运行：

```bash
./build-at/project_at8_amba_noc_qos_coherency_boundary --write-trace
```

默认不建议提交 `trace.csv`。

## How This Differs From Real AMBA / CHI / AXI / ACE / NoC / Cache Coherency

AT-8 不实现 AMBA、CHI、AXI 或 ACE transaction semantics，不包含 protocol checker、
cache coherency state machine、真实 NoC routing algorithm、真实 DRAM controller timing
或 cycle-level timing closure。它只保留一个有边界的 architecture-level question：

```text
在 synthetic interconnect pressure 下，QoS class、route contention、boundary crossing、
ordering pressure 和 read/write interference 如何影响 tail latency、starvation risk 和
recommendation logic？
```

因此，AT-8 可以支持 portfolio discussion 中的 bounded architecture reasoning；它不能支持
protocol compliance、silicon validation 或 production signoff claim。
