# Interview Notes

适用方向：SoC Architecture、Performance Modeling、SystemC/TLM、ESL、Architecture
Performance Analysis。

项目名：`SystemC/TLM Architecture Performance Labs`

核心链路：

```text
workload -> trace -> metrics -> sweep -> comparison -> diagnosis
```

## 1. 30 秒版本

我做的是一个 bounded SystemC/TLM architecture performance modeling 项目。它从 LT
trace replay 和 memory bottleneck characterization 开始，扩展到 AT transaction timing、
multi-initiator contention、QoS-like sensitivity、backpressure、shared-fabric pressure
和 Stage 2 的 industry-inspired problem families。重点不是声称 cycle accuracy 或协议合规，
而是把 workload、trace、metrics、sweep、comparison 和 validation 做成可复现证据链。

## 2. 90 秒版本

这个项目展示的是早期 SoC 架构性能建模的工作方法。LT 侧先把 synthetic workload 或
normalized trace 转成 transaction-level evidence，再计算 latency decomposition、
bank-conflict proxy、queueing、throughput 和 bottleneck attribution。这样可以在 RTL 之前
快速讨论 workload pattern 对 memory subsystem pressure 的影响。

AT 侧进一步暴露 TLM-2.0 四阶段事务。AT-1 看 request/response phase timing；AT-2 看
multi-initiator arbitration 和 fairness；AT-3 看 QoS-like weights、queue depth、
service latency 与 SLA violation；AT-4 看 cache-like shared resource 和 MSHR-like
pressure；AT-5 看 downstream saturation 下 QoS policy 的边界。Stage 2 的 AT-6/7/8
把问题扩展到 heterogeneous fabric、throughput bandwidth wall 和 AMBA-inspired
boundary pressure。

我会主动说明边界：这些都是 bounded synthetic architecture experiments，不是 AXI/CHI/NoC
协议合规，不是 cycle-accurate timing，不是真实芯片验证，也不是 production signoff。

## 3. 三个核心 bullet

- 建立 LT/AT 两层 SystemC/TLM modeling workflow，并输出 trace / summary / comparison
  artifacts。
- 用 metrics 讨论 contention、fairness、tail latency、back-pressure、SLA violation 和
  bottleneck attribution。
- 用 PASS markers、CSV-derived generated reports 和 claim-boundary checks 约束项目叙事。

## 4. 项目边界一句话

这是一个用于展示 architecture modeling judgment 和 reproducibility 的证据包，不是生产级协议模型或芯片准确性验证。

## 5. Stage 1 讲法

Stage 1 关注 memory-system bottleneck isolation：

- LT replay 负责 workload -> trace -> metrics 的稳定证据链。
- Project K/L 把 memory pressure 转成 bottleneck classification 和 bounded recommendation。
- AT-1/2/3/4/5 把 timing、contention、QoS-like sensitivity、cache-like pressure 和
  backpressure collapse 逐步展开。

面试中可以强调：priority policy 不是魔法。如果 downstream service capacity 已经饱和，
QoS 只能重新分配等待，不能创造新的服务能力。

## 6. Stage 2 讲法

Stage 2 用三个 bounded problem families 连接更接近工业讨论的问题类型：

- AT-6：heterogeneous SoC shared-memory fabric pressure。
- AT-7：GPU-like throughput engine bandwidth wall。
- AT-8：AMBA-inspired NoC QoS and coherency-boundary pressure。

这些模型不是 Apple、NVIDIA、Arm 或任何公司内部系统的 replica。它们只用常见架构角色组织
synthetic evidence，展示 trend comparison、bottleneck isolation 和 recommendation logic。

## 7. Project X/Y/Z/AA/AB 讲法

Project X 是 industry-inspired mapping layer：把 AT-6/7/8 映射到常见问题族，但不增加模型
claim。

Project Y 是 workload-to-bottleneck classifier：从 observable symptoms 映射到 bounded
evidence families。它不替代真实 profiling。

Project Z 是 architecture recommendation layer：把 bottleneck family 映射到 bounded
recommendation families。它不是自动硬件优化。

Project AA 是 scenario decision benchmark：把 scenario constraints 和 candidate actions
映射到 bounded scenario-level decision。它不是真实 design-space exploration。

Project AB 是 architecture decision memo layer：把 scenario decision 转成可审阅 memo。
它强调 evidence、risk、claim boundary 和 next validation step。

## 8. 明确不能说的话

不要说：

- 这是 cycle-accurate model。
- 这是 AXI / CHI / ACE / NoC protocol compliance。
- 这是 real cache coherence、real DRAM timing、real HBM controller 或 real GPU simulator。
- 这是 Apple Silicon / NVIDIA GPU / Arm interconnect simulation。
- 这是 silicon validation、production signoff、PMU/perf/Nsight correlation。
- 这些数字能预测真实产品性能。

可以说：

- 这是 bounded architecture performance modeling evidence chain。
- 这是 early-stage tradeoff exploration 和 bottleneck diagnosis。
- 每个结论都有 trace、metrics、summary/comparison 或 PASS marker 作为支撑。
- 当前 claim boundary 是显式写入文档和 validation harness 的。

## 9. 面试问答提示

如果被问“为什么不用 RTL 或真实硬件数据”，可以回答：这个阶段先建立 implementation
consistency 和 trend-level evidence，避免在没有 aligned reference、measurement region 和
error budget 时做 quantitative accuracy claim。后续可以通过 RTL/profiler/silicon
reference 升级 validation level。

如果被问“为什么这些 synthetic workloads 有价值”，可以回答：synthetic workloads 的价值是
把单个 pressure source 分离出来，让 queueing、bank conflict proxy、QoS policy、tail
latency 和 saturation boundary 可观察。它们不是产品 workload，但适合建立 architecture
diagnosis 方法。

如果被问“项目最重要的工程能力是什么”，可以回答：不是某一个模型数字，而是把模型假设、
trace contract、metric semantics、generated artifacts、PASS markers 和 claim boundary
放在同一条可复现链路里。
