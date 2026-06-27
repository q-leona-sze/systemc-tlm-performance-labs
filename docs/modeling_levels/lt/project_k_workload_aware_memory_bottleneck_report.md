# Project K：Workload-Aware Memory System Bottleneck Characterization MVP

状态：K.3 structure and quality hardening report

Project K 的目标是在不修改 Project G/H/I/J、不修改 Project H RTL path、不修改
Project I counter schema、不修改 Project J evidence packet、也不修改核心 C++ / SystemC
memory model 的前提下，建立一个第一天可落地的 workload-aware bottleneck
characterization 闭环。

K.2 继续复用 Project E simplified banked memory model。它把 v0.1 的三类 core
workloads 扩展到两类 optional synthetic access-pattern-inspired traces，并把 sweep 从
`bank_count` 扩展到 `bank_count × address_mapping`。Project K 仍只新增 Python
orchestration、CSV/markdown 输出和显式 bottleneck attribution 规则。

K.3 不新增 workload、不新增 sweep、不拆脚本、不修改 C++ / SystemC model。K.3 的目标是把
当前 K.2 能力固化为更稳定的工程证据包：明确 Project K CSV schema version、stable /
experimental fields、acceptance self-check 和 generated output policy。

## Architecture Story

Project K 回答的架构问题是：当 workload access pattern 改变时，一个简化的 banked
memory subsystem 会先在哪里表现出压力？它不从真实硬件 counter 或真实 AI kernel
性能出发，而是先把问题收敛到可控 trace：

```text
workload access pattern
-> memory-system stressor
-> measurable symptom
-> bottleneck attribution
-> bounded recommendation
```

这个 story 的重点是因果链，而不是单个数字。`streaming` 提供低冲突 baseline；
`stride` 用固定地址步长制造 bank mapping sensitivity；`hot_bank` 把访问集中到少数
modeled bank，并用 bursty issue pattern 放大 queueing 和 tail latency。K.2 额外加入
`tiled_gemm_like` 和 `attention_like_blocked`，但它们只表示 synthetic access-pattern
inspiration，不表示真实 GEMM、Transformer、GPU 或 AI kernel 执行。

因此 Project K 的展示价值是：同一套 `trace -> model -> metrics -> attribution ->
recommendation` 链路可以把 workload 形态、memory-system stressor 和可解释结论连起来。
它不是 accuracy validation，也不是真实硬件性能预测。

## Scope

Current scope：

- 生成三类 core synthetic workload traces：`streaming`、`stride`、`hot_bank`。
- 生成两类 optional synthetic access-pattern-inspired traces：`tiled_gemm_like`、
  `attention_like_blocked`。
- 使用 Project E-compatible trace schema：
  `workload_name,txn_id,timestamp_ns,initiator_id,command,address,size_bytes`。
- 运行现有 Project E C++ binary。
- 解析 Project E `summary.csv` 和 `trace.csv`。
- 计算 trace-derived features。
- 计算 model-derived metrics。
- 执行六类显式 bottleneck attribution。
- 执行 `bank_count = 4 / 8 / 16` 和
  `address_mapping = word_interleave / cacheline_interleave / row_interleave` sweep。
- 生成 CSV 和 generated markdown report。
- 固定 Project K CSV schema version：`k0.2`。
- 执行 demo acceptance self-check：workload 数、sweep rows、stable schema fields、
  claim boundary 和 forbidden affirmative claim scan。
- 输出 demo PASS marker。

Out of scope：

- 不实现真实 GEMM、attention、Transformer、FlashAttention 或 LLM inference。
- 不修改 Project E C++ model。
- 不修改 SystemC model。
- 不修改 Project G/H/I/J。
- 不接入 cache hierarchy、NoC、DRAM timing、HBM channel model、AXI / CHI、
  PMU、Linux perf、NVIDIA Nsight、real GPU kernel 或 full SoC semantics。

## Flow

```text
synthetic workload trace
-> workload feature extraction
-> Project E simplified banked memory model run
-> model metric normalization
-> bottleneck attribution
-> bank_count and address_mapping sweep
-> CSV / markdown report
-> demo PASS
```

## Workloads

| Workload | Pattern | Purpose |
| --- | --- | --- |
| `streaming` | 连续地址访问，issue gap 平滑 | low-conflict baseline，用来确认模型在低压力输入下主要由 service latency 主导。 |
| `stride` | 固定 stride 访问 | 观察 bank mapping sensitivity、stride resonance、queue build-up 和 tail amplification。 |
| `hot_bank` | 地址集中映射到少数 modeled bank，并带 bursty issue pattern | 观察 bank concentration、queueing、rejected transaction 和 latency tail。 |
| `tiled_gemm_like` | synthetic A/B/C tile read/write pattern | 观察 tile-shaped locality proxy、B tile mapping sensitivity 和 C write-back pressure；不建模 matrix multiply compute。 |
| `attention_like_blocked` | synthetic Q/K/V repeated-read + output-write pattern | 观察 blocked repeated read、phase locality proxy 和 output write pressure；不建模 softmax 或 attention compute。 |

`tiled_gemm_like` 和 `attention_like_blocked` 只能写成 synthetic access-pattern-inspired
traces。它们不能被写成真实 GEMM kernel simulator、真实 Transformer / attention
simulator、GPU simulator、FlashAttention simulator 或真实 AI kernel performance 验证。

## Metrics

Trace-derived features：

- `total_requests`
- `total_bytes`
- `read_ratio`
- `write_ratio`
- `unique_cacheline_count`
- `reuse_ratio`
- `avg_reuse_distance`
- `p50_reuse_distance`
- `phase_locality_score`
- `sequentiality_score`
- `dominant_stride`
- `burstiness_score`
- `bank_entropy`
- `max_bank_share`

`unique_cacheline_count` 和 `reuse_ratio` 只是 locality proxy，不声称真实 cache behavior。
`bank_entropy` 和 `max_bank_share` 基于 Project K synthetic bank mapping / Project E
bank-count assumption，不声称真实 DRAM bank conflict、GPU shared-memory bank conflict 或
silicon counter behavior。

Trace-derived features 只回答“输入长什么样”。例如：

- `sequentiality_score` 和 `dominant_stride` 描述地址序列；
- `burstiness_score` 描述 issue-time gap 是否集中成 burst；
- `bank_entropy` 和 `max_bank_share` 描述在当前 synthetic bank mapping 下访问是否集中；
- `reuse_ratio` 和 `unique_cacheline_count` 只是 locality proxy，不代表真实 cache hit/miss。

Model-derived metrics：

- `avg_latency_ns`
- `p50_latency_ns`
- `p95_latency_ns`
- `throughput_txn_per_us`
- `queue_delay_ratio`
- `service_delay_ratio`
- `bank_conflict_proxy`
- `p95_p50_latency_ratio`
- `mapping_sensitivity_score`
- `bank_count_sensitivity_score`

Model-derived metrics 回答“这个输入在当前 simplified model 里造成了什么症状”。例如：

- `queue_delay_ratio` 说明延迟中有多少来自 waiting；
- `service_delay_ratio` 说明延迟中有多少来自 modeled service latency；
- `p95_p50_latency_ratio` 说明 tail 是否被明显放大；
- `bank_conflict_proxy` 是 accepted requests 中出现 same-bank waiting 的 proxy，不是硬件
  bank-conflict counter。
- `mapping_sensitivity_score` 和 `bank_count_sensitivity_score` 来自 sweep，不是真实硬件
  sensitivity，只表示当前模型中 `address_mapping` 或 `bank_count` 改变后的指标变化。

## CSV Schema Contract

Project K CSV schema version：`k0.2`。

Stable summary schema fields：

```text
workload
pattern_class
phase_count
total_requests
total_bytes
read_ratio
write_ratio
unique_cacheline_count
reuse_ratio
sequentiality_score
dominant_stride
burstiness_score
bank_entropy
max_bank_share
avg_latency_ns
p50_latency_ns
p95_latency_ns
throughput_txn_per_us
queue_delay_ratio
service_delay_ratio
bank_conflict_proxy
p95_p50_latency_ratio
bank_utilization_pct
avg_queue_occupancy
max_queue_occupancy
stalled_or_rejected_transactions
row_hit_ratio_pct
primary_bottleneck
confidence
evidence_fields
recommendation
claim_boundary
```

Experimental summary fields：

```text
avg_reuse_distance
p50_reuse_distance
phase_locality_score
mapping_sensitivity_score
bank_count_sensitivity_score
```

这些 experimental fields 用于 K.2/K.3 的 locality proxy 和 sweep sensitivity 解释。它们可以
帮助面试展示分析路径，但不应被写成真实 cache behavior、真实 bandwidth claim 或真实硬件
optimization result。

Stable sweep schema fields：

```text
workload
bank_count
address_mapping
avg_latency_ns
p50_latency_ns
p95_latency_ns
throughput_txn_per_us
queue_delay_ratio
service_delay_ratio
bank_conflict_proxy
p95_p50_latency_ratio
sweep_delta_pct
primary_bottleneck
confidence
```

Field degradation rules：

- 如果 Project E `summary.csv` 没有 `p50_latency_ns`，但 `trace.csv` 有
  `total_latency_ns`，则从 `trace.csv` 计算。
- 如果没有 `queue_delay_ns`，则 `queue_delay_ratio=NA`，并降低 queueing attribution
  confidence。
- 如果没有 `service_latency_ns`，则 `service_delay_ratio=NA`，并降低
  service-latency attribution confidence。
- 如果没有真实 `bank_conflict_ratio`，不要伪造，不叫 ratio；Project K 统一使用
  `bank_conflict_proxy`。
- 缺失字段写 `NA`，不补造数字。

## Attribution Rules

Project K 使用显式规则，不使用黑箱模型。

| Rule | Evidence fields | Trigger logic | Recommendation direction |
| --- | --- | --- | --- |
| `bank_conflict_bound` | `max_bank_share`, `bank_entropy`, `bank_conflict_proxy`, `p95_p50_latency_ratio`, `bank_utilization_pct` | `max_bank_share` 高、`bank_entropy` 低、`bank_conflict_proxy` 高或 tail amplification 明显。 | 增加 modeled bank parallelism，或让 synthetic address mapping 更分散。 |
| `queueing_bound` | `queue_delay_ratio`, `avg_queue_occupancy`, `max_queue_occupancy`, `stalled_or_rejected_transactions`, `p95_latency_ns` | queue delay 高，或 queue occupancy / rejected transactions 明显。 | 降低 injection pressure、平滑 request issue，或后续评估 buffering / bank parallelism。 |
| `service_latency_bound` | `service_delay_ratio`, `avg_latency_ns`, `row_hit_ratio_pct`, `queue_delay_ratio` | service delay 高且 queue delay 不高。缺少 `service_delay_ratio` 时不强行触发。 | 降低 modeled service latency 或改善 synthetic locality。 |
| `burstiness_bound` | `burstiness_score`, `p95_p50_latency_ratio`, `max_queue_occupancy`, `stalled_or_rejected_transactions` | burstiness 高且 tail amplification 明显。 | 平滑 burst issue pattern；queue-depth sweep 留到后续 Project K step。 |
| `locality_loss_bound` | `reuse_ratio`, `unique_cacheline_count`, `row_hit_ratio_pct`, `phase_locality_score`, `service_delay_ratio` | locality proxy 低、row hit 低、service delay 高，且 queueing 不是主导。 | 调整 synthetic phase order 或 tile/block access order；不写成 cache miss claim。 |
| `bandwidth_pressure_bound` | `throughput_txn_per_us`, `bank_utilization_pct`, `queue_delay_ratio`, `stalled_or_rejected_transactions`, `bank_count_sensitivity_score` | throughput 或 queue/reject 压力高，且增加 bank count 后改善有限。 | 在当前模型内比较 bank/mapping alternatives；不写成真实 bandwidth claim。 |

每个 workload 输出：

- `primary_bottleneck`
- `confidence`: `high / medium / low`
- `evidence_fields`
- `recommendation`
- `claim_boundary`

Recommendation 只表达 expected direction，不写真实硬件收益百分比。

## Observed Core Results

当前默认 demo 的 presentation-level 观察结果如下。它们来自 Project E simplified banked
memory model 的 generated CSV，只能用于趋势级解释。

| Workload | Primary bottleneck | Key evidence | Interpretation |
| --- | --- | --- | --- |
| `streaming` | `service_latency_bound` | `queue_delay_ratio=0.000`, `service_delay_ratio=1.000`, `max_queue_occupancy=1` | 连续访问没有形成明显 queue pressure；在当前模型里，延迟主要由 fixed service / row latency 组成。 |
| `stride` | `queueing_bound` | `queue_delay_ratio=0.746`, `bank_conflict_proxy=0.979`, `max_queue_occupancy=7` | 固定 stride 让请求更容易压到相同 modeled bank，queue waiting 成为主要症状。 |
| `hot_bank` | `queueing_bound` | `max_bank_share=1.000`, `queue_delay_ratio=0.914`, `max_queue_occupancy=16`, `stalled_or_rejected_transactions=63` | hot-bank + bursty issue 把请求集中到一个 modeled bank，触发 queue saturation、tail latency 和 reject。 |

这组结果形成的 evidence chain 是：

```text
streaming / stride / hot_bank synthetic traces
-> sequentiality / stride / bank concentration / burstiness features
-> queue_delay_ratio / service_delay_ratio / bank_conflict_proxy / tail metrics
-> service_latency_bound or queueing_bound attribution
-> bounded recommendation direction
```

其中 `recommendation` 只表示“在当前 simplified model 中，下一步可以尝试的架构方向”。
例如增加 modeled bank parallelism 或让 synthetic address mapping 更分散，只是 expected
direction；它不是真实硬件性能收益百分比，也不是 production memory-system recommendation。

## Current Sweep

Current hard sweep：

```text
bank_count = 4 / 8 / 16
address_mapping = word_interleave / cacheline_interleave / row_interleave
```

固定项：

- `queue_depth = 16`
- `base_service_latency_ns = 20`
- `row_hit_latency_ns = 8`
- `row_miss_latency_ns = 40`

Project E CLI 已支持 `word_interleave`、`cacheline_interleave` 和 `row_interleave`。K.2
不实现 `xor_folded`。`queue_depth`、`service_latency` 和 burstiness-mode sweep 留给
后续 Project K step。

## Generated Outputs

默认运行：

```bash
python3 examples/lt/tools/demo_project_k_workload_bottleneck_lab.py
```

默认输出目录：

```text
examples/lt/results/project_k_workload_bottleneck/
```

Generated outputs：

- `project_k_workload_bottleneck_summary.csv`
- `project_k_what_if_sweep_summary.csv`
- `project_k_report.md`
- `model_runs/<address_mapping>/bank_count_<N>/summary.csv`
- `model_runs/<address_mapping>/bank_count_<N>/trace.csv`

Generated input traces 默认放在：

```text
build/examples/lt/project_k_workload_bottleneck_inputs/
```

这些 traces 和 results 是 generated artifacts，不是 source-level validation evidence。
它们默认位于 `.gitignore` 已覆盖的 `build/` 和 `examples/lt/results/` 路径下，不应作为
source artifact 进入 Git。需要展示时，应引用 source-level report、demo command、PASS
marker 和 schema contract，而不是提交 generated intermediate outputs。

## Acceptance

Project K.3 hardening 后的验收标准：

- demo 一键跑通。
- `core_workloads == 3`：`streaming`、`stride`、`hot_bank`。
- `optional_synthetic_patterns == 2`：`tiled_gemm_like`、`attention_like_blocked`。
- `total_workloads == 5`。
- 输出 `project_k_workload_bottleneck_summary.csv`，精确 5 行 data rows。
- 输出 `project_k_what_if_sweep_summary.csv`，精确 45 行 data rows。
- 每类 workload 至少有 trace-derived features。
- 每类 workload 至少有 model-derived metrics。
- 每类 workload 至少有一个 `primary_bottleneck`。
- 每个 attribution 有 `evidence_fields`。
- summary CSV 包含 stable summary schema fields。
- sweep CSV 包含 stable sweep schema fields。
- generated report 包含 unsupported claims / 不声称边界。
- generated report 不包含明显 forbidden affirmative claim。
- PASS 输出包含 `schema_version=k0.2`。
- 不修改 Project G/H/I/J。
- 不修改 Project H RTL path。
- 不修改 Project I counter schema。
- 不修改 Project J evidence packet。
- 不修改 C++ / SystemC model。

成功 PASS marker：

```text
Project K Workload-Aware Memory Bottleneck Characterization MVP PASS
core_workloads=3
optional_synthetic_patterns=2
total_workloads=5
summary_rows=5
sweep_rows=45
claim_boundary=PASS
schema_version=k0.2
```

## Supported Claims

Project K 当前支持以下 claim：

- 本项目展示了一种受控 synthetic trace 方法，用于观察 workload access pattern 如何影响
  Project E simplified banked memory model。
- 本项目支持当前模型定义内的趋势级 bottleneck attribution。
- 本项目可以比较 `bank_count` 和 `address_mapping` 在当前 simplified model 下对
  latency、queueing、bank concentration proxy 和 throughput 的相对影响。
- 本项目可以输出 claim-bounded recommendation direction。

## Unsupported Claims

Project K 当前不支持以下 claim：

- 不声称真实 GPU 性能。
- 不声称 Apple Silicon 验证。
- 不声称 NVIDIA Nsight 集成。
- 不声称 ARM PMU 验证。
- 不声称 Linux perf 验证。
- 不声称 silicon validation。
- 不声称 production signoff。
- 不声称 full-system cycle accuracy。
- 不声称 full SoC validation。
- 不声称 AXI / CHI protocol compliance。
- 不声称真实 GEMM kernel performance。
- 不声称真实 Transformer / attention kernel performance。
- 不声称 FlashAttention 或 LLM inference performance。
- 不声称 GPU simulation。

## Relationship to Existing Projects

- Project G 定义 validation taxonomy 和 claim boundary；Project K 不修改它。
- Project H 是 local Verilator RTL golden reference path；Project K 不修改 RTL path，也不把
  K 的 trend attribution 写成 RTL validation。
- Project I 是 sample-only profiler / counter interface；Project K 不修改 counter schema，也
  不生成伪 profiler / PMU / Nsight 数据。
- Project J 是 accuracy validation evidence packet；Project K 不把趋势级结果注入
  Project J claim matrix 或 evidence table。

## Future Work

后续 Project K step 可以考虑：

- 在模型明确支持后再考虑 `xor_folded` mapping。
- 增加 `queue_depth` sweep。
- 增加 `service_latency` sweep。
- 增加 burstiness-mode sweep。
- 后续如需接入 Project J，必须先定义 evidence status，不能把 synthetic trend result 写成
  accuracy validation。
