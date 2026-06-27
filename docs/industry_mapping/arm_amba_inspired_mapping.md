# Arm-Like AMBA-Inspired NoC QoS And Coherency-Boundary Mapping

schema_version: `industry-r1.0`

## Purpose

这份文档说明 AT-8 如何作为 Arm-like AMBA-inspired interconnect / NoC QoS /
coherency-boundary problem type 的问题类型映射。它是 protocol-inspired mapping，不是
protocol-compliant implementation。

## Mapping

AT-8 使用 bounded AT-level synthetic AMBA-inspired NoC QoS and
coherency-boundary exploration，观察多个 initiator classes、route resources、QoS
classes、read/write flows，以及 coherent-vs-noncoherent boundary crossings 下的压力。

AT-8 支持讨论：

- QoS classes
- route contention
- coherency-boundary pressure
- ordering delay
- read/write interference
- starvation / collapse signal
- protocol-inspired not protocol-compliant behavior

## Evidence

Primary artifacts:

- `examples/at/results/project_at8_amba_noc_qos_coherency_boundary/summary.csv`
- `examples/at/results/project_at8_amba_noc_qos_coherency_boundary/comparison.md`

Key evidence examples:

- `latency_qos_priority` protects latency_high traffic only inside route capacity
  bounds.
- `bulk_dma_pressure` exposes write-heavy pressure and read tail interference.
- `boundary_crossing_stress` makes ordering delay and boundary events visible.
- `route_hotspot` shows route mapping can dominate QoS intent.
- `mixed_qos_collapse` shows QoS priority cannot compensate for saturated route
  capacity and boundary pressure.

## What Can Be Claimed

- Current: AT-8 is in the portfolio evidence harness p0.5.
- Supported: Arm-like AMBA-inspired NoC QoS and coherency-boundary problem type.
- Supported: bounded synthetic analysis of QoS classes, route contention,
  coherency-boundary pressure, ordering delay, read/write interference,
  starvation signal, collapse signal, and recommendation logic.
- Supported: protocol-inspired exploration with explicit unsupported claims.

## What Cannot Be Claimed

- Not supported: Arm CHI compliance.
- Not supported: AXI compliance.
- Not supported: ACE compliance.
- Not supported: real AMBA protocol behavior.
- Not supported: real NoC behavior.
- Not supported: real cache coherency.
- Not supported: cycle-accurate modeling.
- Not supported: silicon validation.
- Not supported: production signoff.

## Claim Boundary

AT-8 is an Arm-like problem-type mapping over a bounded synthetic architecture
exploration. It is not Arm CHI compliance, not AXI compliance, not ACE
compliance, not real AMBA protocol behavior, not real NoC behavior, not real
cache coherency, not cycle-accurate modeling, not silicon validation, and not
production signoff.
