# NVIDIA-Like Throughput Engine Bandwidth Wall Mapping

schema_version: `industry-r1.0`

## Purpose

这份文档说明 AT-7 如何作为 NVIDIA-like throughput engine bandwidth wall /
GPU-like memory saturation problem type 的问题类型映射。它不改变 AT-7 模型或
`summary.csv` schema，只把现有 evidence 转成面试和 release pack 可用的产业表达。

## Mapping

AT-7 使用 bounded AT-level synthetic throughput engine 来观察 memory wall。它通过
logical lanes、outstanding-depth limits、global outstanding pressure、queue capacity
和 bandwidth saturation 信号，表达 throughput-oriented engine 在 memory service path
前遇到 bandwidth wall 的现象。

AT-7 支持讨论：

- throughput engine
- outstanding-depth sensitivity
- bandwidth saturation
- latency hiding approximation
- queue buildup
- burstiness
- memory wall
- roofline-like intuition, but not real roofline validation

## Evidence

Primary artifacts:

- `examples/at/results/project_at7_gpu_like_throughput_saturation/summary.csv`
- `examples/at/results/project_at7_gpu_like_throughput_saturation/comparison.md`

Key evidence examples:

- `balanced_occupancy` shows useful latency-hiding behavior before saturation.
- `high_occupancy` approaches the knee and exposes queue delay.
- `bandwidth_saturation` reaches memory utilization 1.000 while extra pressure
  mostly becomes p99 latency and queue buildup.
- `bursty_stress` shows burstiness as a separate tail-latency risk.
- `throttled_occupancy` provides a bounded safer reference for latency-sensitive
  recommendation.

## What Can Be Claimed

- Current: AT-7 is in the portfolio evidence harness p0.5.
- Supported: NVIDIA-like throughput engine bandwidth wall problem type.
- Supported: bounded synthetic analysis of outstanding depth, latency hiding
  approximation, bandwidth saturation, queue buildup, burstiness, and memory
  wall behavior.
- Supported: roofline-like intuition for explaining a bandwidth wall, not real
  roofline validation.

## What Cannot Be Claimed

- Not supported: NVIDIA GPU simulation.
- Not supported: CUDA execution modeling.
- Not supported: SM scheduler behavior.
- Not supported: warp scheduler behavior.
- Not supported: real HBM controller.
- Not supported: Tensor Core behavior.
- Not supported: TMEM behavior.
- Not supported: cycle-accurate modeling.
- Not supported: silicon validation.
- Not supported: production signoff.

## Claim Boundary

AT-7 is an NVIDIA-like problem-type mapping over a bounded synthetic architecture
exploration. It is not NVIDIA GPU simulation, not CUDA execution modeling, not
SM scheduler behavior, not real HBM controller behavior, not Tensor Core
behavior, not TMEM behavior, not cycle-accurate modeling, not silicon validation,
and not production signoff.
