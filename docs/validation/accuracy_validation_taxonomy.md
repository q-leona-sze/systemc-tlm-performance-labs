# Accuracy Validation Taxonomy

状态：accuracy validation taxonomy 文档

本文档定义 `SystemC/TLM Architecture Performance Labs` 的 accuracy validation taxonomy。
它用于约束 README、comparison report、roadmap、portfolio note 和 interview wording 中的
claim 边界。

核心规则：

```text
No reference, no correlation.
No aligned metric and measurement region, no quantitative error.
No real RTL, profiler, counter, FPGA, or silicon data, no golden-reference claim.
```

当前仓库主要处于 Level 0 和 Level 1。Project G 定义进入 Level 2 / Level 3 的路线。
Level 4 是企业内部 release process，不是公开项目可以直接声称的能力。

## Level Overview

| Level | Name | Primary Question | Current Mapping |
| --- | --- | --- | --- |
| Level 0 | Internal consistency | 项目实现是否稳定、可复现、内部自洽？ | Project D / Project R |
| Level 1 | Trend correlation | 模型是否保留 expected direction 或 ranking？ | Project E / Project F |
| Level 2 | Quantitative correlation | 在 aligned metric 上，model-vs-reference observed error 是多少？ | Future Project J target |
| Level 3 | Golden reference validation | 模型是否与 real bounded reference data 做过对齐？ | Future Project H/I/J target |
| Level 4 | Enterprise production signoff | 企业内部 release process 是否接受该模型进入产品决策？ | Out of scope |

## Level 0：Internal Consistency

### Definition

Level 0 建立 implementation consistency evidence。它检查 deterministic input、stable
schema、reproducible summary、baseline equivalence 和 regression health。

Level 0 只能说明当前实现可运行、可比较、可回归，不能证明 architectural accuracy。

### Reference Source

Level 0 的 reference source 是项目内部 baseline：

- Python replay output；
- known sample traces；
- documented CSV schema；
- deterministic demo output；
- PASS markers；
- regression harness status。

### Required Inputs

- deterministic workload trace；
- fixed model configuration；
- fixed CSV schema；
- repeatable demo command；
- internal baseline output；
- comparison tolerance where needed。

### Required Outputs

- `trace.csv`；
- `summary.csv`；
- `comparison.md`；
- comparison PASS marker；
- regression summary；
- prerequisites 缺失时的 clear failure 或 skipped status。

### Metrics That Can Be Compared

- transaction count；
- workload order；
- 来自同一 internal model definition 的 average latency；
- 来自同一 internal model definition 的 p50 / p95 / p99 latency；
- 来自同一 internal model definition 的 bank conflict ratio；
- 来自同一 internal model definition 的 throughput；
- 当双方实现同一规则时的 accepted / rejected transaction counts。

### Metrics That Should Not Be Claimed

- real hardware latency；
- RTL latency；
- silicon counter values；
- full-system cycles；
- product bandwidth；
- protocol-level correctness；
- architectural accuracy against an external system。

### Error Budget

Level 0 可以使用 implementation tolerance，例如 Project D Python/C++ summary comparison
tolerance。

这不是 external accuracy error budget。它只回答：当前项目的两个实现是否在 documented
metrics 上一致。

### Valid Claim

```text
The current replay workflow is internally consistent. The standalone C++ replay
engine matches the Python replay baseline on documented summary metrics within
the configured tolerance.
```

### Invalid Claim

```text
The C++ replay engine is architecturally accurate because it matches Python.
```

### Example in This Repository

Project D 是主要 Level 0 例子。它验证 Python/C++ replay equivalence for summary metrics。
这证明 implementation consistency，不证明 architectural accuracy。

Project R 也属于 Level 0。它检查 demo-chain regression health 和 output-contract
stability，不验证 model fidelity。

### Interview Wording

```text
I first built internal consistency gates: deterministic trace replay, stable
summary schemas, Python/C++ replay equivalence, and headless regression health.
This proves the implementation is controlled before I make stronger correlation
claims.
```

### Upgrade Path

从 Level 0 升级到 Level 1，需要：

- 引入至少两个 workload 或 configuration point；
- 比较 direction、ordering 或 trend behavior；
- 说明为什么该 trend 是 expected behavior；
- 继续保留 implementation consistency gates。

## Level 1：Trend Correlation

### Definition

Level 1 建立 trend-level alignment evidence。它可以说明某个 workload 相比另一个 workload
有更高 pressure、更高 queueing、更高 tail latency 或不同 ranking。

Level 1 是 qualitative / directional，不提供 absolute error bound。

### Reference Source

Level 1 的 reference source 可以包括：

- 作为 workload-level architectural context 的 gem5 stats；
- expected access-pattern behavior；
- known memory-pressure patterns；
- Project E queueing behavior；
- internal 或 external trend expectations。

gem5 stats 在这一层有价值，因为它提供 architectural context。但它不会自动成为本仓库的
absolute ground truth。

### Required Inputs

- 至少两个可比较 workload 或 configuration points；
- shared model configuration where applicable；
- documented metric names；
- trend expectation；
- reference context，例如 gem5 stats；
- model summary outputs。

### Required Outputs

- trend table；
- ranking 或 direction comparison；
- matched / mismatched trend notes；
- qualitative status；
- `correlation_report.md` 或等价 report。

### Metrics That Can Be Compared

- average latency change direction；
- p95 / p99 latency change direction；
- bank conflict trend；
- queue occupancy trend；
- accepted / rejected transaction trend；
- workload ranking；
- `sequential` 与 `stride` 类 workload 的 relative pressure。

### Metrics That Should Not Be Claimed

- absolute cycle count；
- absolute latency error；
- product bandwidth；
- silicon counter accuracy；
- exact cache behavior；
- exact DRAM timing；
- exact RTL scheduler behavior。

### Error Budget

Level 1 不使用 absolute error budget。

允许的检查包括：

- trend direction match；
- ranking agreement；
- monotonicity check；
- qualitative pass/fail/warning。

如果 report 开始给出 relative error percentage，就已经超出 Level 1，必须满足 Level 2 条件。

### Valid Claim

```text
For selected workloads, the model preserves the expected trend direction and
ranking against gem5 stats context or known workload behavior.
```

### Invalid Claim

```text
Project F proves absolute accuracy because its trends agree with gem5 stats.
```

### Example in This Repository

Project F 是主要 Level 1 例子。它把 gem5 stats context 与 replay / Project E summaries
联合起来，做 trend-level correlation。

Project E 也支持 Level 1，因为它提供 memory-subsystem trend abstraction，例如 bank
pressure、queue occupancy、tail latency、accepted/rejected transaction behavior。

### Interview Wording

```text
At this stage I claim trend-level alignment only. Project F shows that selected
workloads preserve expected direction and ranking when gem5 stats context is
joined with replay and queueing-model summaries. I do not claim absolute
accuracy.
```

### Upgrade Path

从 Level 1 升级到 Level 2，需要：

- select one workload；
- define one measurement region；
- define one metric precisely；
- choose one reference source；
- define unit conversion；
- define an error formula；
- define an explicit error budget；
- report observed error and pass/fail status。

## Level 2：Quantitative Correlation

### Definition

Level 2 从严格 alignment 条件下计算 model-vs-reference error 开始。

必须同时满足：

- same workload；
- same measurement region；
- same metric definition；
- same reference source；
- explicit error budget；
- observed error；
- pass/fail/warning status。

缺少任一条件，都应该退回 Level 1，而不是声称 quantitative correlation。

### Reference Source

Level 2 的 reference source 可以包括：

- aligned gem5 region stats；
- RTL summary metrics；
- profiler 或 counter captures；
- FPGA counters；
- silicon measurement data；
- approved internal reference data。

reference 必须明确命名，并记录 version / configuration。

### Required Inputs

- model output；
- reference output；
- workload identity；
- workload source 或 binary version；
- input dataset；
- measurement region marker；
- metric definition；
- unit conversion；
- model configuration；
- reference configuration；
- error formula；
- error budget。

### Required Outputs

- model value；
- reference value；
- unit；
- absolute error；
- relative error where valid；
- error budget；
- observed error；
- pass/fail/warning status；
- reference source；
- model version；
- reference version；
- limitation notes。

### Metrics That Can Be Compared

- transaction count；
- accepted transaction count；
- rejected transaction count；
- average latency；
- p95 latency；
- p99 latency；
- max latency；
- throughput；
- bandwidth；
- counter events with clear definitions；
- region 和 definition 对齐后的 stall cycles。

### Metrics That Should Not Be Claimed

- 没有 shared definition 的 metric；
- multiplexing 或 overflow 行为未知的 counter；
- 来自不同 workload region 的 samples；
- 没有 documented rule 的 unit conversion；
- 用 block-level dataset 推断 full-system behavior；
- 用 MVP workload 推断 product-level performance。

### Error Budget

Level 2 必须使用 metric-specific error budget。

示例：

| Metric Class | Error Formula | Budget Style |
| --- | --- | --- |
| Count | `abs(model_count - reference_count)` | exact match 或 small absolute delta |
| Average latency | `abs(model_avg - reference_avg)` and relative percent | absolute cycles/ns plus percent |
| p95 / p99 latency | percentile delta | cycles/ns 或 percent，并说明 sample size |
| Throughput | relative percent | percentage threshold |
| Counter event | absolute and relative count error | counter-specific threshold |
| Ranking | rank agreement | 只支持 trend status，除非 numeric values 也对齐 |

当 reference value 为 0 时，report 必须避免无效 relative error math，并输出 warning 或只使用
absolute error。

### Valid Claim

```text
For workload W, measurement region R, metric M, and reference source S, the
model has observed error E under error budget B, with status pass/fail/warning.
```

### Invalid Claim

```text
A single quantitative comparison proves the model is accurate for all workloads
and systems.
```

### Example in This Repository

当前仓库还没有完成 Level 2 result。

Project J 是未来的 reporting layer。它应消费 model output 和真实或明确命名的 reference
output，然后生成包含 error budget 和 observed error 的 accuracy report。

### Interview Wording

```text
Quantitative correlation starts only after I align workload, region, metric, and
reference source. Then I compute observed error using a documented formula and
classify the result against an explicit budget.
```

### Upgrade Path

从 Level 2 升级到 Level 3，需要：

- 用 real bounded reference data 替代 weak 或 contextual reference；
- 添加 configuration manifest；
- 记录 reference source、tool version 和输入身份；
- 包含 limitation 和 coverage table；
- 让 reference 足以支撑 golden-reference claim。

## Level 3：Golden Reference Validation

### Definition

Level 3 使用 real bounded reference data 与模型做对齐，支撑更强但仍有边界的 validation
claim。

可作为 Level 3 reference 的数据包括：

- Verilator RTL model；
- cycle model；
- profiler capture；
- hardware counter capture；
- FPGA counter data；
- silicon measurement data；
- approved internal golden model data。

reference data 必须真实。synthetic sample data 可以测试 parser 或 report formatting，但不能
支撑 Level 3 validation claim。

### Reference Source

reference source 必须具体且可追溯：

- tool name and version；
- RTL 或 model version；
- platform；
- workload；
- binary 或 source hash where possible；
- input dataset；
- measurement region；
- configuration；
- clock 或 unit definition；
- known limitations。

### Required Inputs

- golden reference dataset；
- model dataset；
- workload identity；
- input identity；
- region marker；
- model configuration；
- reference configuration；
- metric definition；
- unit conversion；
- error formula；
- error budget；
- coverage notes。

### Required Outputs

- golden correlation report；
- coverage table；
- per-metric model/reference values；
- per-metric error；
- pass/fail/warning status；
- known limitations；
- waived 或 unsupported metrics；
- reproduction command 或 manifest path。

### Metrics That Can Be Compared

- accepted transactions；
- rejected transactions；
- latency cycles；
- average latency；
- p95 / p99 latency；
- queue occupancy；
- service rate；
- bandwidth；
- counter events with exact definitions；
- bounded block-level throughput；
- region-level elapsed cycles。

### Metrics That Should Not Be Claimed

- measured block 之外的 behavior；
- unmeasured workload classes；
- product-level behavior；
- 未测量的 platform-wide thermal 或 power effects；
- reference 和 checker 没覆盖的 protocol completeness；
- 只有 RTL data 时声称 silicon behavior；
- 只有 synthetic data 时声称 RTL behavior。

### Error Budget

Level 3 需要带 reference-specific notes 的 documented error budget。

它应包含：

- metric threshold；
- absolute / relative formula；
- sample-size requirement；
- measurement noise；
- counter ambiguity；
- clock conversion assumptions；
- known unmodeled effects；
- waiver policy where applicable。

### Valid Claim

```text
For the bounded workload, region, metric set, and real reference source listed
in the manifest, the model has been correlated against the golden reference and
the observed error is reported.
```

### Invalid Claim

```text
A bounded Verilator block comparison proves full-system cycle accuracy.
```

### Example in This Repository

当前仓库还没有完成 Level 3 result。

Project H 是预期的第一个 Level 3 step：为 banked memory controller 建立 local Verilator
RTL cycle reference，并在 deterministic workloads 下与 C++ model 比较。

Project I 准备 profiler / counter ingestion，但只有 real captures 才能支撑 Level 3 claim。

### Interview Wording

```text
The golden-reference phase uses real bounded reference data. For example, a
Verilator RTL banked-memory-controller reference can support correlation for a
specific queueing behavior before making broader claims.
```

### Upgrade Path

从 Level 3 升级到 Level 4，需要：

- 从 MVP workloads 扩展到 approved workload suite；
- 添加 corner coverage；
- 添加 release thresholds；
- 添加 owner 和 review process；
- 添加 waiver tracking；
- 接入 enterprise RTL、emulation、silicon、profiler、power、thermal、firmware
  validation flows。

## Level 4：Enterprise Production Signoff

### Definition

Level 4 是企业内部 release process。它不是这个公开项目可以直接声称的能力。

在这一层，product team 决定某个 model 是否可以用于特定 product decision、release gate 或
internal review process。

### Reference Source

Level 4 可能需要：

- internal RTL；
- commercial simulation；
- emulation；
- FPGA data；
- silicon measurement data；
- profiler captures；
- hardware counters；
- PPA data；
- power data；
- thermal data；
- firmware workloads；
- OS / driver workloads；
- SoC integration data；
- approved internal reference suites。

### Required Inputs

- release workload suite；
- corner matrix；
- platform configuration；
- model version；
- reference version；
- measurement SOP；
- CI history；
- metric definitions；
- thresholds；
- owners；
- waiver database；
- risk register。

### Required Outputs

- signoff report；
- coverage matrix；
- pass/fail gate result；
- risk register；
- waiver approvals；
- known limitations；
- release notes 或 internal review package。

### Metrics That Can Be Compared

只有 product team 定义并由 enterprise reference data 支撑的 metric 才能在 Level 4 比较。

可能包括：

- performance counters；
- latency；
- bandwidth；
- throughput；
- PPA metrics；
- power；
- thermal behavior；
- firmware workload behavior；
- QoS metrics；
- regression history across releases。

### Metrics That Should Not Be Claimed

- 没有 product-team definition 的 metric；
- 没有 reference coverage 的 metric；
- 超出 validated workload / corner matrix 的 metric；
- 用 public-project MVP metric 替代 enterprise coverage。

### Error Budget

Level 4 error budget 由企业内部 product process 拥有，可能按以下维度变化：

- workload class；
- metric class；
- performance corner；
- power 或 thermal condition；
- risk level；
- release stage。

### Valid Claim

```text
Only the responsible product organization can claim that a model passed its
release criteria for the documented scope.
```

### Invalid Claim

```text
Do not say a public MVP repository is production signoff ready because it has
demos and trend reports.
```

### Example in This Repository

当前仓库没有 Level 4 example。

这个仓库可以构建类似 enterprise process input 的 evidence chain，但它不包含企业内部
reference、owner approval、waiver process、workload coverage 或 release gates。

### Interview Wording

```text
Production signoff is a separate enterprise process. My public project focuses
on building a disciplined evidence chain that could feed such a process, while
keeping claims bounded to the references I actually have.
```

### Upgrade Path

Level 4 不是普通公开项目升级路径。它需要 enterprise access、internal data、product
ownership 和 release review infrastructure。

对当前仓库来说，实际路线是在真实企业数据和流程访问出现前，保持在 documented Level 2 或
bounded Level 3 evidence。

## Cross-Level Claim Rules

使用能被现有 evidence 支撑的最低 level。

| Evidence Available | Maximum Claim Level |
| --- | --- |
| Python/C++ summary equivalence only | Level 0 |
| Demo-chain PASS markers only | Level 0 |
| gem5 stats trend and model summary direction | Level 1 |
| same workload、region、metric、reference、error budget、observed error | Level 2 |
| real RTL / profiler / counter / FPGA / silicon reference data plus Level 2 alignment | Level 3 |
| enterprise release process with approved references and owners | Level 4 |

不要因为数字看起来合理就升级 claim。只有 evidence source 和 alignment requirements 都满足时，
claim 才能升级。

## Forbidden Wording

当前 Project B/C/D/E/F/R evidence 禁止使用以下表达：

```text
guaranteed accurate
silicon validated
production signoff
production signoff ready
full-system cycle accurate
hardware validated
RTL validated
matches hardware timing
absolute accuracy proven
```

这些表达只能出现在 invalid claim、forbidden wording 或 future enterprise-only requirements 的
上下文中。

## Recommended Wording

当前 Level 0/1 wording：

```text
Current evidence supports implementation consistency, replay equivalence,
regression health, and trend-level correlation.
```

Level 2 wording：

```text
For workload W, measurement region R, metric M, and reference source S, the
model has observed error E under budget B, with status pass/fail/warning.
```

Level 3 wording：

```text
For the bounded block, workload set, metric set, and real reference dataset
listed in the manifest, the model has been correlated against a golden
reference and limitations are documented.
```

Level 4 wording：

```text
Enterprise release signoff is outside the scope of this public repository.
```
