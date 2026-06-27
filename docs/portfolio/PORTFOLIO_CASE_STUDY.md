# SystemC/TLM 架构性能建模 Case Study

目标读者：SoC Architecture Engineer、Performance Modeling Engineer、ESL Engineer
以及关注 architecture performance analysis 的面试官。

## 1. Case Study 摘要

本仓库围绕一条可复现实验链组织：

```text
workload -> trace -> metrics -> sweep -> comparison -> diagnosis
```

它不试图包装成 production interconnect model。更窄、也更可信的价值是：把 workload
或 trace source 送入 SystemC/TLM performance analysis backend，生成可审查的 latency、
bank-conflict、throughput、`summary.csv` 和 `comparison.md` artifacts。

当前 LT 侧演进路径是：

```text
synthetic workload
-> normalized trace replay
-> gem5 SE-derived trace replay
-> standalone C++ replay
-> banked memory controller queueing model
```

这个 staged flow 展示了如何先用可控 synthetic experiment 固化 trace contract，再接收外部
simulator 产生的 memory-access stream，最后把核心 replay/queueing 逻辑迁移到 standalone
C++ model。

## 2. 项目动机

Architecture performance work 需要证据链，而不只是一个模型文件。一个有用的性能模型至少要能回答：

- 使用了什么 workload 或 traffic pattern？
- 生成了什么 trace evidence？
- 计算了哪些 metrics？
- 多个 cases 是否能一致比较？
- 另一个工程师是否能复现结果？

本项目的核心问题不是“这是不是 cycle-accurate hardware”。核心问题是：

> 能否把 workload stream 转成 trace evidence 和 architecture-level performance metrics，并且让这个过程可重复、可检查、可解释？

## 3. 为什么从 SystemC/TLM LT 和 AT 开始

SystemC/TLM 适合 virtual platform 和 architecture-level performance experiments。
它能让模型先聚焦 transaction flow、latency decomposition、arbitration observability
和 workload sensitivity，再决定是否需要更低层 timing fidelity。

LT 是基础，因为它最快能建立：

- workload knobs；
- transaction trace generation；
- latency decomposition；
- metrics extraction；
- sweep automation；
- generated comparison reports。

AT 是 timing-refinement 方向。它暴露 TLM-2.0 `BEGIN_REQ`、`END_REQ`、`BEGIN_RESP`、
`END_RESP`，让 request-accept latency、response timing、back-pressure 和 arbitration
effects 可观测。

LT 和 AT 都不被表述为完整 AXI/CHI/NoC model。它们是 bounded labs，用于把性能问题变成可测量证据。

## 4. LT 证据链

### Project B：Normalized Trace Replay

Project B 在 LT workflow 上比较 `sample_sequential` 与 `sample_stride` 两类
controlled trace fixtures，观察 minimal bank-conflict abstraction 如何改变 latency 和
throughput。

| workload | avg_latency_ns | p99_latency_ns | bank_conflict_ratio_pct | throughput_txn_per_us |
| --- | ---: | ---: | ---: | ---: |
| `sample_sequential` | 100.000 | 100.000 | 0.000 | 10.000 |
| `sample_stride` | 119.688 | 120.000 | 98.438 | 9.969 |

解释边界：`stride=16` 在当前 minimal bank mapping 下反复回到同一 modeled bank，因此触发
bank conflict signal。这个结果不是 DRAM bank timing claim。

Project B 定义 normalized CSV trace interface：

```text
workload_name,txn_id,timestamp_ns,initiator_id,command,address,size_bytes
```

它证明 backend 可以消费外部 trace、验证 schema、replay 并生成同一套 metrics。`timestamp_ns`
是 replay ordering hint，不是 gem5 timing 或 cycle timing。

### Project C：gem5 SE Trace Extraction

Project C 使用 gem5 SE mode 作为 offline trace producer，捕获 `PROJECT_C_MEM` markers，
转换成 normalized trace，再复用 Project B replay path。

边界：

- gem5 只作为 offline trace producer。
- SystemC/TLM lab 只作为 replay and analysis backend。
- 这不是 gem5-SystemC live co-simulation，也不是 full-system Linux validation。

### Project D/E/F：C++ Replay、Queueing 与 Trend Correlation

Project D 把 Python replay 的核心 metrics 逻辑迁移到 standalone C++ replay engine，并用
Python/C++ summary equivalence check 保护实现一致性。

Project E 用 standalone C++ banked memory controller queueing model 观察 bank pressure、
row-buffer locality、queue occupancy、tail latency、bank utilization 和 rejected
transaction trends。

Project F 把 gem5 `stats.txt` 与 replay / Project E summary 做 file-based qualitative
trend-level correlation。它解释趋势，不比较绝对 cycle，也不声称 RTL/silicon/profiler
correlation。

## 5. AT 证据链

AT-1 至 AT-5 从 four-phase timing 逐步推进到 contention、QoS-like sensitivity、
cache-like shared-resource pressure 和 downstream backpressure collapse。

AT-6 至 AT-8 扩展为三类 industry-inspired problem families：

- heterogeneous SoC shared-memory fabric pressure；
- GPU-like throughput engine bandwidth wall；
- AMBA-inspired NoC QoS and coherency-boundary pressure。

这些名字是问题类型和架构角色，不是 vendor implementation claim。

## 6. Portfolio Evidence Pack

Portfolio evidence harness 汇总 Stage 1 K/L/AT-1 至 AT-5 和 Stage 2 AT-6 至 AT-8：

```bash
python3 tools/run_portfolio_validation.py --at-build-dir build-at
python3 tools/generate_portfolio_evidence_summary.py --strict
```

预期 PASS marker：

```text
Portfolio Evidence Pack PASS
stage1_projects=AT-1,AT-2,AT-3,AT-4,AT-5,K,L
stage2_projects=AT-6,AT-7,AT-8
claim_boundary=PASS
schema_version=p0.5
```

generated summary 来自 CSV outputs 和脚本，不是手写结论。

## 7. 面试表达边界

可以说：

- 我建立了从 workload 到 trace、metrics、sweep、comparison 和 diagnosis 的可复现实验链。
- 我能用 LT/AT 不同抽象层级讨论 workload sensitivity、contention、tail latency、
  QoS-like tradeoff 和 bottleneck attribution。
- 我用 PASS markers、CSV-derived reports 和 claim-boundary checks 保护证据链。

不能说：

- 这是 cycle-accurate model。
- 这是 AXI/CHI/NoC/DRAM/cache coherence compliance model。
- 这是 silicon validation、production signoff 或 vendor system simulation。
- 这些数字代表真实硬件绝对性能。

## 8. 结论

本 case study 的重点是 engineering discipline：先定义 bounded abstraction，再生成 trace
evidence，最后用 metrics 和 comparison 支撑有限 claim。它适合作为 SoC architecture
performance modeling 学习、作品集展示和面试讨论材料，但不能越界成为协议合规或芯片签核叙事。
