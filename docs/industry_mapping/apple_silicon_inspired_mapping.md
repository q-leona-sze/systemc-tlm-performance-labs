# Apple-Like Heterogeneous SoC Shared Fabric Mapping

schema_version: `industry-r1.0`

## Purpose

这份文档说明 AT-6 如何作为 Apple-like heterogeneous SoC shared fabric pressure
的问题类型映射。它是 Project X release pack 的一部分，目的是帮助面试和作品集讨论
时把 AT-6 的 synthetic evidence 对应到产业中常见的 shared fabric / shared memory
pressure 问题。

## Mapping

AT-6 使用 bounded AT-level synthetic lab 表达 heterogeneous initiators 共享一个
memory fabric 的压力。可以把 CPU-like、GPU-like、NPU-like、ISP-like、DMA-like
角色作为 architectural roles 来讨论，但这些角色不是任何真实 Apple product block。

AT-6 支持讨论：

- heterogeneous initiators
- shared fabric / shared memory pressure
- bandwidth cap
- latency-sensitive flow protection
- starvation risk
- unified-memory-inspired pressure
- CPU/GPU/NPU/ISP/DMA-like roles as architectural roles only

## Evidence

Primary artifacts:

- `examples/at/results/project_at6_heterogeneous_soc_fabric/summary.csv`
- `examples/at/results/project_at6_heterogeneous_soc_fabric/comparison.md`

Key evidence examples:

- `priority_latency` protects CPU-like and ISP-like tail latency inside this
  bounded model.
- `bandwidth_cap_npu` shows the cost of bandwidth partitioning for a
  throughput-oriented initiator.
- `dma_stress` and `mixed_stress` expose bulk-transfer pressure, queue growth,
  and starvation risk.

## What Can Be Claimed

- Current: AT-6 is in the portfolio evidence harness p0.5.
- Supported: Apple-like heterogeneous SoC shared fabric pressure problem type.
- Supported: bounded analysis of mixed traffic interference, bandwidth cap,
  latency-sensitive flow protection, and starvation risk.
- Supported: unified-memory-inspired pressure at the architecture discussion
  level.

## What Cannot Be Claimed

- Not supported: Apple Silicon simulation.
- Not supported: M-series internal fabric.
- Not supported: real unified memory controller.
- Not supported: real NoC behavior.
- Not supported: real Neural Engine behavior.
- Not supported: real GPU behavior.
- Not supported: real ISP behavior.
- Not supported: cycle-accurate modeling.
- Not supported: silicon validation.
- Not supported: production signoff.

## Claim Boundary

AT-6 is an Apple-like problem-type mapping over a bounded synthetic architecture
exploration. It is not Apple Silicon simulation, not a claim about M-series
internal fabric, not a real unified memory controller model, not real NoC
behavior, not cycle-accurate modeling, not silicon validation, and not production
signoff.
