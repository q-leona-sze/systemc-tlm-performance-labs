# Portfolio Architecture Story

## 1. 一分钟摘要

本仓库展示的是一条 bounded SystemC/TLM architecture performance modeling
实验链。它从 LT workload bottleneck characterization 起步，逐步扩展到 AT
transaction timing、multi-initiator contention、QoS-like sensitivity、SLA
violation、cache-like shared-resource pressure、downstream backpressure，再到
Stage 2 的 heterogeneous SoC shared-memory fabric、GPU-like throughput saturation
和 AMBA-inspired boundary pressure。

项目价值不在于声称 cycle accuracy 或协议合规，而在于把 synthetic workloads、
traces、metrics、sweeps、generated reports 和 PASS markers 串成可复现证据链，让读者
能看到每个结论来自哪些输入、哪些指标、哪些边界。

## 2. 建模管线

| Stage | Project | Modeling level | Main question | Key metrics | Claim boundary |
| --- | --- | --- | --- | --- | --- |
| LT bottleneck evidence | Project K | LT / memory subsystem abstraction | workload pattern 暴露哪类 memory bottleneck？ | queue latency、service latency、bank conflict proxy、throughput | synthetic trace 上的趋势级 attribution；不是真实 workload 或硬件 counter evidence |
| LT recommendation layer | Project L | LT / evidence-driven recommendation | metrics 支持什么 bounded architecture action？ | sensitivity score、bottleneck classification、confidence | 基于 Project K metrics；不是 production signoff 或 silicon claim |
| AT phase timing | AT-1 | AT / single-initiator timing | 四阶段事务如何暴露 request/response timing？ | request accept latency、service latency、response latency | TLM-2.0 AT phase observability；不是 AXI/CHI implementation |
| AT contention | AT-2 | AT / multi-initiator contention | arbitration policy 如何影响 fairness 与 tail latency？ | p95/p99 latency、arbitration delay、fairness index | bounded contention comparison；不是真实 NoC 或 silicon validation |
| AT QoS-like sensitivity | AT-3 | AT / SLA analysis | weights、queue depth、service latency 如何影响 SLA violations？ | SLA violation rate、p99 latency、fairness、throughput | QoS-like exploration；不是 AXI/CHI QoS compliance |
| AT cache-like pressure | AT-4 | AT / shared-resource bottleneck | locality、MSHR-like pressure、shared traffic 如何交互？ | hit/miss trend、mshr_full_events、interference score、p95/p99 | cache-like exploration；不是真实 cache hierarchy |
| AT backpressure collapse | AT-5 | AT / downstream bottleneck | downstream saturation 下 QoS policy 何时失效？ | queue_full_events、backpressure_stall_ns、collapse_score | bounded bottleneck isolation；不是 DRAM/NoC/cycle-accurate model |
| Stage 2 fabrics | AT-6/7/8 | AT / industry-inspired problem families | shared fabric、throughput bandwidth wall、QoS/coherency boundary 如何形成诊断信号？ | case summary、comparison、recommendation signals | industry-inspired synthetic labs；不是 vendor model |

## 3. 为什么同时保留 LT 和 AT

LT 适合快速建立可复现 pipeline：构造 workload、生成 transaction trace、做 latency
decomposition、运行 sweep、生成 comparison。它帮助回答“某类访问模式在当前抽象下会暴露哪种
memory pressure”。

AT 适合观察 transaction phase timing。它把 `BEGIN_REQ`、`END_REQ`、`BEGIN_RESP`、
`END_RESP` 暴露到 trace 层，让 request acceptance、response timing、queueing、
back-pressure、contention 和 QoS-like tradeoff 可以被单独分析。

两者不是竞争关系：LT 给出快速、稳定、可回归的架构级实验骨架；AT 用更细的 phase-level
observability 补充 timing refinement。

## 4. 架构诊断示例

1. 如果 Project K/L 中 `bank_conflict_ratio_pct` 占主导，可以提出调整 modeled bank
   count 或 address mapping 的 hypothesis，但不能把它说成真实 DRAM bank timing。
2. 如果 AT-2 fixed priority 提高 lower-priority traffic 的 p99 latency，说明 policy
   需要同时看 average latency、tail latency 和 fairness。
3. 如果 AT-3 保护某个 traffic class 却伤害另一个 class，QoS weights 需要显式 trade-off
   review，不能只报告 protected traffic 的改善。
4. 如果 AT-4 中高 MSHR-like capacity 仍然无法降低 slow-memory case 的 tail latency，
   说明 memory service latency 已经主导。
5. 如果 AT-5 downstream service capacity 已经饱和，priority policy 只能重新分配等待，
   不能创造新的服务能力。

## 5. 本作品集展示什么

- SystemC/TLM modeling 与 LT/AT 层级意识。
- synthetic workload design、trace generation、metrics extraction 与 sweep automation。
- latency decomposition、tail latency、fairness、back-pressure、SLA violation 与
  bottleneck attribution。
- evidence-driven recommendation 和 architecture decision memo 的 bounded workflow。
- claim-boundary discipline：每个结论都区分 Current、Supported、Not Supported 和
  Future Work。

## 6. 本作品集不声称什么

当前仓库不声称：

- AXI / CHI / ACE / NoC protocol compliance。
- cycle accuracy。
- real cache coherence、real DRAM timing、real HBM controller 或 real GPU execution。
- Apple Silicon、NVIDIA GPU、Arm interconnect 或任何公司内部系统仿真。
- silicon validation、production signoff、PMU/perf/Nsight correlation。
- real workload performance prediction。

这些边界不是削弱项目价值，而是保证 architecture reasoning 可信：当前项目展示的是早期建模、
指标解释、趋势比较和诊断链路，而不是生产级协议/RTL/芯片签核。

## 7. 推荐阅读路径

1. 先读仓库根目录 `README.md`，理解 book companion repository 主线。
2. 读 `examples/lt/README_performance_lab.md`，理解 LT trace replay 与 memory subsystem
   bottleneck workflow。
3. 读 `examples/at/README.md`，理解 AT-1 至 AT-8 的 problem families。
4. 运行 `tools/run_portfolio_validation.py`，检查 portfolio-level PASS marker。
5. 读 `docs/generated/portfolio_evidence_summary.md`，回到各 project report 查看具体证据。

## 8. Future Work

- LT-vs-AT comparison under equivalent synthetic workloads。
- 更明确的 metric versioning 和 generated artifact diff policy。
- 外部 trace / profiler / RTL reference 的 prerequisite-aware correlation path。
- 更丰富的 workload fixtures 与 architecture case studies。
