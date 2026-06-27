# Model Assumptions

状态：模型假设与 claim boundary 文档

本文档定义 `SystemC/TLM Architecture Performance Labs` 当前可以声称的模型层级、
指标语义和边界。它的目的不是扩大项目 claim，而是把当前教学实验收敛成一个可验证的
architecture-level performance modeling framework。

核心证据链保持为：

```text
workload -> trace -> metrics -> sweep -> comparison -> demo
```

## 1. 当前模型层级

| 层级 | 当前位置 | 当前作用 | 不能扩展成的 claim |
| --- | --- | --- | --- |
| LT architecture-level model | `examples/lt` | 用 transaction trace、latency decomposition、minimal bank abstraction 和 workload sweep 做架构级性能分析。 | 不能声称 cycle accuracy、真实 cache / DRAM / GPU shared memory 行为。 |
| AT phase-level timing refinement | `examples/at` | 用 TLM-2.0 `BEGIN_REQ` / `END_REQ` / `BEGIN_RESP` / `END_RESP` trace 观察 arbitration policy 对 phase-level timing 的影响。 | 不能声称 AXI / CHI / NoC protocol compliance。 |
| offline trace-driven replay | Project B, `examples/lt/tools/run_trace_replay_lab.py` | 读取 normalized CSV trace，通过 LT replay backend 生成 `trace.csv`、`summary.csv`、`comparison.md`。 | 不能声称 live simulator integration 或 gem5 timing validation。 |
| gem5 SE as offline trace producer | Project C, `examples/lt/tools/run_gem5_se_trace_extraction.py` 和 `convert_gem5_se_trace.py` | 让 gem5 SE 运行小型 user-level workload，捕获 `PROJECT_C_MEM` markers，再转换成 Project B normalized trace。 | 不能声称 gem5-SystemC live co-simulation 或 full-system Linux。 |

LT 和 AT 是两个互补层级：

- LT 是当前稳定的 architecture-level workflow baseline。
- AT 是 phase-level timing refinement 方向，用于观察 TLM phase ordering 和 arbitration effect。
- Project B / Project C 当前走 LT replay backend，不把 gem5 接入 SystemC kernel。

## 2. Latency Model 假设

当前 latency model 是可解释的 architecture-level latency composition，不是硬件 cycle
模型。

LT 侧指标语义：

- `queue_delay_ns`：模型里的 shared resource / target path 等待时间。
- `target_service_delay_ns`：目标侧服务成本的模型值。
- `bank_conflict_delay_ns`：minimal bank abstraction 命中冲突时附加的模型延迟。
- `total_delay_ns` / `delay_ns`：用于 analyzer 和 summary 的 transaction latency。

Project B replay MVP 的当前简化更强：

- 只支持当前 MVP 约束下的 normalized traces。
- 当前 replay path 使用固定 target service delay 和 fixed bank conflict penalty 来产生可比较指标。
- `queue_delay_ns` 在当前 Project B MVP 中为 `0.0`，因为它验证的是 trace contract 和 minimal bank replay，不是多 initiator contention。

这些延迟值适合做 case-to-case comparison，例如 sequential vs stride，不适合作为真实硬件绝对 timing。

## 3. Minimal Bank Abstraction 假设

minimal bank abstraction 用来把 address pattern 转成可观测的 conflict signal。它是一个
小型架构级抽象，不是 DRAM bank timing、cache bank、GPU shared memory bank 或 memory
controller 的真实模型。

当前语义：

- trace 中的 `bank_id` 是模型内部根据地址得到的 bank label。
- trace 中的 `bank_conflict` 是模型内部判断出的 repeated same-bank / same-target conflict signal。
- `bank_conflict_delay_ns` 是 conflict signal 触发后的模型附加延迟。
- Project B replay 当前使用 4-bank style 的 minimal mapping；`stride=16` 会有意制造 repeated same-bank pattern。

可声称：

- 访问模式变化可以在当前抽象中改变 `bank_conflict_ratio_pct`、tail latency 和 throughput。

不可声称：

- 这不是真实 DRAM bank conflict。
- 这不是 NVIDIA GPU shared memory bank model。
- 这不是 cache bank、NoC VC、AXI channel 或 CHI transaction layer 行为。

## 4. `timestamp_ns` 语义

`timestamp_ns` 是 normalized trace 中的 issue-time / ordering hint。

它表示：

- replay 输入事件的规范化发起时间。
- 多行 trace 的 deterministic ordering anchor。
- Project B replay 排序时的主键之一；同一 timestamp 下再用 `txn_id` 稳定排序。

它不表示：

- gem5 tick。
- CPU cycle。
- SystemC kernel 与 gem5 kernel 的同步时间。
- host wall-clock time。
- silicon / RTL measured timestamp。

在 Project C 中，gem5 SE 只负责产生 marker stream。converter 可以按固定
`--timestamp-step-ns` 生成 normalized `timestamp_ns`，这仍然是 replay input time，
不是 gem5 timing。

## 5. `throughput_txn_per_us` 语义

`throughput_txn_per_us` 是内部模型比较指标。

当前计算语义：

```text
throughput_txn_per_us =
  num_transactions / ((max(end_time_ns) - min(start_time_ns)) / 1000.0)
```

使用方式：

- 用于同一模型、同一 replay/analyzer 规则下的 case comparison。
- 可以比较 sequential、stride、hotspot 或 gem5-derived trace replay 在当前抽象下的吞吐差异。

不能解释为：

- 真实内存带宽。
- CPU IPC。
- NoC throughput。
- DRAM command throughput。
- GPU memory throughput。
- silicon performance number。

## 6. `bank_conflict_ratio_pct` 语义

`bank_conflict_ratio_pct` 是模型内部 conflict flag 的比例：

```text
bank_conflict_ratio_pct =
  100.0 * count(bank_conflict == true) / total_transactions
```

使用方式：

- 作为访问模式敏感性的架构级 signal。
- 用于说明 stride-shaped stream 在当前 minimal bank abstraction 下比 sequential stream 更容易触发 conflict。

不能解释为：

- 真实 DRAM bank conflict rate。
- 真实 GPU shared memory bank conflict rate。
- cache miss / bank conflict 统计。
- gem5 stats 里的 memory-system counter。

## 7. 当前不能声称的内容

本项目当前不能声称：

- cycle accuracy。
- AXI protocol compliance。
- CHI protocol compliance。
- NoC protocol compliance。
- DRAM protocol compliance。
- GPU shared memory real model。
- gem5-SystemC live co-simulation。
- full-system Linux。
- production interconnect model。
- cache coherence model。
- RTL equivalence。
- silicon correlation。
- profiler correlation。

面试或作品集表达中，应主动说清楚：当前价值是 architecture-level performance
modeling workflow、trace evidence、metrics、sweep、comparison 和 reproducible demo。

## 8. 当前模型证明了什么

当前模型可以证明：

- 能把 workload / trace source 转成可重复的 transaction-level evidence。
- 能把 trace 聚合成 latency、tail latency、bank conflict、throughput 等可比较指标。
- 能在 LT 层观察 workload pattern 对 architecture-level metrics 的影响。
- 能在 AT 层观察 arbitration policy 对 TLM phase trace 的影响。
- 能通过 Project B 定义 normalized file-based trace contract。
- 能通过 Project C 把 gem5 SE 作为 offline trace producer 接到 replay backend 前面。
- 能保持 `summary.csv` / `comparison.md` / demo PASS 形式的工程证据链。

## 9. 当前模型没有证明什么

当前模型没有证明：

- 真实 SoC interconnect 的 cycle-level timing。
- 真实 AXI / CHI / NoC ordering、channel、beat、credit、QoS 或 coherency 行为。
- 真实 DRAM scheduler、row buffer、bank group、refresh 或 timing constraints。
- 真实 GPU SM、warp scheduler、shared memory bank、L1/L2 cache 或 memory coalescing。
- gem5 与 SystemC 在同一仿真时间线上同步执行。
- Linux kernel、device model、driver、DMA 或 full-system workload 行为。
- 与 RTL、silicon counter 或 profiler trace 的相关性。

## 10. 走向 Industrial-Grade Modeling 还需要什么

要从当前 framework 走向 industrial-grade modeling，至少需要补齐：

- 校准过的 latency 参数来源，例如 RTL、silicon counter、profiler 或 vendor model。
- 明确的 memory hierarchy model，包括 cache、memory controller、DRAM timing 或片上存储层级。
- 更完整的 interconnect semantics，例如 ordering、backpressure、QoS、outstanding depth 和 arbitration fairness。
- 更丰富的 trace metadata，例如 PC、symbol、region marker、read/write mix、thread/core id、raw simulator tick。
- 更深入的 gem5 `stats.txt` correlation；Project F 当前只做 qualitative /
  trend-level report，不做 calibrated timing correlation。
- 与 RTL / silicon / profiler 数据的误差度量和 calibration workflow。
- CI/regression 中的 schema validation、demo checks、metric invariant checks 和 artifact diff policy。
- 明确的 model versioning，保证不同阶段的 `summary.csv` 可追溯到对应模型假设。

这些是未来工业级建模能力的方向，不是当前实现已经完成的 claim。
