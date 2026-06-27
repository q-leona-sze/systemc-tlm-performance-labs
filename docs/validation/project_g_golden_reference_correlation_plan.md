# Project G：Golden Reference Correlation Plan

状态：路线图文档

Project G 定义 `SystemC/TLM Architecture Performance Labs` 的下一阶段 accuracy path：
从当前已经完成的 trend-level modeling evidence，推进到有边界、有 reference、有 error
budget 的 golden-reference correlation workflow。

Project G 不是新的模型实现，不新增源码、脚本、实验结果、build artifact、图片、PDF 或 CSV。
它只负责定义 claim 边界、reference 分级、验证路线和后续 Project H / I / J 的证据链。

当前项目已经具备 architecture-level evidence chain：

```text
workload -> trace -> metrics -> sweep -> comparison -> demo -> regression health
```

Project G 规划的下一阶段 evidence chain 是：

```text
workload
-> aligned measurement region
-> model metrics
-> reference metrics
-> error formula
-> error budget
-> validation report
-> regression gate
```

详细 taxonomy 见：

```text
docs/validation/accuracy_validation_taxonomy.md
```

## 1. 目标与边界

当前项目已经进入可展示的 architecture-level performance modeling 阶段：它可以接收
normalized trace，执行 replay，生成 summary，比较 Python / C++ replay 行为，建模
memory-subsystem pressure，基于 gem5 stats 做趋势相关性分析，并通过 headless regression
harness 保护 demo chain。

这些证据有工程价值，但还不足以支撑以下 claim：

- absolute accuracy validation；
- cycle accuracy；
- silicon correlation；
- production RTL validation；
- full-system timing validation；
- product release readiness。

Project G 的目标是说明：如果以后要说更强的 accuracy claim，需要补齐什么 reference、什么
metric alignment、什么 error budget，以及什么 report 证据。

Project G 区分以下层次：

- internal implementation consistency；
- trend-level correlation；
- quantitative correlation；
- golden-reference validation；
- enterprise production signoff process。

这个区分非常关键。工业 performance modeling 不是看数字是否“像真的”，而是看 claim 是否有
对应 evidence source、workload alignment、metric definition、measurement region 和 error
budget。

## 2. 什么是 Reference

reference 是用于比较、校准、约束或解释模型输出的数据源。

在本项目里，reference 可以是：

- internal baseline，例如用于检查 C++ replay 的 Python replay output；
- external architecture simulator artifact，例如作为 workload-level context 的 gem5 SE
  stats；
- RTL 或 cycle model output，例如 local banked memory controller 的 Verilator run；
- profiler 或 hardware counter capture；
- FPGA 或 emulation dataset；
- measured silicon dataset；
- 企业内部认可的 golden model 或 reference dataset。

reference 不自动等于 ground truth。它的强度取决于：

- 它实际测量了什么；
- 它如何采集；
- 它覆盖哪个 workload region；
- metric definition 是否与模型一致；
- unit conversion 是否明确；
- 是否有 explicit error budget；
- 是否有 limitation 和 unmodeled effect 说明。

## 3. 什么是 Golden Reference

golden reference 是更强的 reference。它必须是真实、可追溯、有边界、能支撑特定比较目的的
reference data。

对本项目而言，未来的 golden reference 至少需要：

- real reference data，不能把 synthetic sample data 包装成 measured data；
- workload identity，包括 source、binary、input、configuration；
- measurement-region alignment；
- metric definition 和 unit；
- versioned model configuration；
- versioned reference configuration；
- error formula；
- error budget；
- known limitation 和 unmodeled effect。

“golden” 不表示 universal truth。它只表示：在某个 bounded workload、bounded region、
bounded metric set 和指定 reference source 下，这个 reference 足以支撑 documented
validation claim。

## 4. 为什么 gem5 Stats 有价值但有限

gem5 stats 可以作为 architectural context reference，前提是 workload、measurement
region、metric definition 和 simulator configuration 被清楚记录。

gem5 stats 的价值：

- 提供 instruction count、memory access behavior、cache behavior、simulated ticks 等
  workload-level context；
- 帮助解释 `sequential` / `stride` 等 workload 的相对趋势；
- 可以作为 Project F 中 trend-level correlation 的外部上下文；
- 能帮助检查模型是否保留了合理的方向性和 ranking。

但 gem5 stats 不能自动等价于 absolute ground truth。

原因：

- Project C 使用 gem5 SE 作为 offline trace producer 和 stats source，不是
  gem5-SystemC live co-simulation。
- Project B/C normalized trace 中的 `timestamp_ns` 是 replay workflow 的 ordering hint，
  不是 gem5 timing-mode cycle measurement。
- Project F 比较的是 trends 和 context，不是 cycle-by-cycle event alignment。
- gem5 stat 与 replay summary metric 可能相关，但不一定共享同一个 measurement region 或
  metric definition。
- gem5 本身也是模型。它有价值，但不能自动替代 product RTL、profiler、hardware counter 或
  silicon reference。

可用表达：

```text
Project F shows qualitative trend-level correlation between gem5 stats context
and replay/model summaries for selected workloads.
```

禁止表达：

```text
Project F proves absolute model accuracy against hardware.
```

## 5. Cycle Accuracy、RTL、Counter、Silicon 的区别

### Cycle Accuracy

cycle accuracy 关注事件是否能在 cycle-level timeline 上对齐。它通常需要 clock domain、
pipeline state、scheduler state、request/response timing、backpressure、per-cycle event
ordering 和 cycle trace。

当前项目没有 cycle-level state machine，也没有与 RTL cycle trace 对齐，所以不能声称
cycle accuracy。

### RTL Correlation

RTL correlation 是把模型输出与 RTL simulation、Verilator、commercial simulator 或
emulation reference 进行同口径比较。

RTL correlation 的 claim 必须限定在：

- 被测 block；
- workload；
- measurement region；
- metric set；
- RTL configuration；
- error budget。

如果只有 local RTL MVP，只能说 bounded block-level RTL correlation path，不能说 full SoC
validation。

### Profiler / Counter Correlation

profiler / counter correlation 是把模型指标与 profiler、PMU、hardware counter、FPGA
counter 或 silicon-visible counter 进行比较。

它必须说明：

- counter definition；
- sampling window；
- region marker；
- sampling error；
- overflow / multiplexing risk；
- platform configuration；
- permission limitation。

schema 或 sample data 只能证明接口可读，不能证明 hardware-counter correlation。

### Silicon Correlation

silicon correlation 是把模型与真实芯片测量结果对齐。它需要真实 silicon capture、counter
definition、measurement window、noise characterization、firmware / OS / compiler / thermal
context。

当前项目没有 silicon measurement，所以不能声称 silicon correlation。

## 6. 为什么 Verilator RTL 是下一阶段更强 Reference

对这个仓库来说，bounded Verilator RTL cycle model 是合理的下一阶段 reference，因为它能在
不承诺 full SoC 的前提下提供更强的 block-level reference。

Project H 的目标 reference 应该是 local banked memory controller RTL model。它应足够小、
确定性强、可复现，并且与 Project E 的 memory subsystem abstraction 有明确的可比较指标。

预期比较范围：

- deterministic workload streams；
- accepted transactions；
- rejected transactions；
- per-bank queue behavior；
- latency cycles；
- average latency；
- p95 / p99 latency；
- throughput 或 service rate，前提是 metric definition 对齐。

它比 Project F 更强，因为：

- RTL 可以为 bounded block 提供 cycle-level behavior；
- accepted/rejected transaction 可以直接比较；
- queueing behavior 可以在 block boundary 测量；
- 只有在 same workload、same region、same metric、same reference source 成立后，才计算
  observed error。

但 Project H 即使完成，也仍然不是 full-system claim。local RTL model 只能支持 bounded
block-level correlation，不能代表 entire SoC、memory hierarchy、product platform，也不
声称 AXI、CHI、NoC protocol completeness 或 gem5-Verilator live co-simulation。

## 7. 为什么 Profiler、Counter、FPGA、Silicon 是更高层 Reference

profiler、hardware counter、FPGA 和 silicon data 更强，是因为它们把 model 与真实执行环境
连接起来。

未来可能支持的 reference source：

- NVIDIA Nsight capture；
- Apple Instruments capture；
- Apple `powermetrics` capture；
- ARM PMU events；
- Linux `perf` counters；
- FPGA counters；
- emulator counters；
- silicon performance-lab measurements。

这些 reference 更强，但也更容易被误用。必须记录：

- counter definition；
- workload source / binary / input version；
- region marker；
- sampling-window control；
- unit conversion；
- measurement-noise characterization；
- permission 和 counter availability；
- overflow / multiplexing checks；
- platform configuration。

synthetic profiler samples 可以用于 parser smoke test、schema check 和 report formatting。
它们不能支撑 hardware-counter validation claim。

## 8. 为什么 Production Signoff 是独立企业流程

enterprise production signoff 不是公开个人项目可以直接声称的东西。

企业内部 signoff 通常需要：

- internal RTL 和 verification environment；
- commercial simulation 或 emulation；
- silicon data；
- profiler 和 counter infrastructure；
- PPA、power、thermal analysis；
- firmware / OS workload coverage；
- SoC integration knowledge；
- release workload suite；
- versioned configuration management；
- formal owner、threshold、waiver、review gate。

这个仓库可以构建类似的 evidence chain，但不能声称替代企业内部 signoff process。

## 9. 当前项目能力边界

| Project | Current Capability | Valid Claim | Invalid Claim |
| --- | --- | --- | --- |
| Project B | normalized trace replay bridge | 外部 trace-like stream 可以通过稳定 CSV contract 进入 replay workflow。 | gem5 timing validation、hardware accuracy、cycle-level timing。 |
| Project C | gem5 SE trace extraction path | gem5 SE workload 可以离线生成 normalized memory trace 和 stats context。 | gem5-SystemC live co-simulation、full-system timing validation。 |
| Project D | standalone C++ replay engine with Python/C++ equivalence | C++ replay 在 documented summary metrics 上与当前 Python baseline 等价。 | architectural accuracy、RTL correlation、silicon correlation。 |
| Project E | banked memory controller queueing abstraction | 模型能暴露 memory pressure、bank locality、queueing、accepted/rejected transactions 和 latency trend。 | JEDEC DRAM timing、AXI/CHI/NoC compliance、cycle accuracy。 |
| Project F | gem5 stats trend correlation report | gem5 stats 可以与 model summaries 联合，用于 qualitative workload trend discussion。 | absolute accuracy、RTL correlation、hardware-counter validation。 |
| Project R | headless regression harness | demo chain 和 output contract 可以做 regression health check。 | model fidelity validation、quantitative accuracy validation、release signoff。 |

## 10. Evidence Ladder

| Level | Name | Reference Source | Current Project Status | Valid Claim | Invalid Claim | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| Level 0 | Internal consistency | internal baseline、deterministic traces、replay outputs、PASS markers | Project D equivalence 和 Project R regression health 已覆盖 | workflow 在 documented tolerance 内可复现、自洽 | architectural accuracy、RTL correlation、hardware validation | 保留内部 gate，同时引入外部 reference |
| Level 1 | Trend correlation | gem5 stats context、expected workload behavior、model trend summaries | Project F 已完成 qualitative trend-level correlation | selected workloads 保留 expected direction 或 ranking | absolute error bound、cycle accuracy、hardware-counter validation | 对齐 workload region 和 metric definition，升级到 Level 2 |
| Level 2 | Quantitative correlation | same workload / region / metric / reference 的 model-reference dataset | 尚未完成 | 对 bounded metric 和 reference，报告 observed error 与 pass/fail/warning status | 泛化到所有 workload，或暗示 RTL / silicon validation | Project H/I 提供 reference data 后，由 Project J 生成 report |
| Level 3 | Golden reference validation | real Verilator RTL、cycle model、profiler、hardware counter、FPGA 或 silicon dataset | Future target，通过 Project H/I/J 推进 | bounded model behavior 与 real reference dataset 对齐，并报告 limitation | full-system coverage、未测 block coverage、product readiness | 建立真实 reference capture 和 validation manifest |
| Level 4 | Enterprise production signoff | enterprise RTL、emulation、silicon、profiler、PPA、power、thermal、firmware workload suite | 公开项目范围外 | 只有企业内部 product process 可以做这个 claim | public MVP 替代 enterprise signoff | 公开表达保持在 Level 4 以下 |

## 11. Claim Boundary Table

| Claim | Allowed? | Evidence Required | Current Status | Recommended Wording |
| --- | --- | --- | --- | --- |
| Internal replay implementation consistency | Yes | Python / C++ replay outputs 在 documented summary metrics 上比较，并有 tolerance。 | Project D 支持 | "The C++ replay engine matches the current Python replay baseline on documented summary metrics." |
| Demo chain regression health | Yes | headless script、PASS/FAIL/SKIPPED status、output-contract checks。 | Project R 支持 | "The regression harness checks demo-chain health and output contracts." |
| Memory-subsystem trend abstraction | Yes | deterministic workloads、queueing metrics、tail-latency trends、accepted/rejected counts。 | Project E 支持 | "Project E exposes memory pressure and queueing trends for controlled workloads." |
| gem5 stats trend correlation | Yes | gem5 stats context 与 replay/model summaries 联合，并做 trend-level interpretation。 | Project F 支持 | "Project F provides qualitative trend correlation against gem5 stats context." |
| Quantitative correlation | Not yet | same workload、same measurement region、same metric definition、same reference source、explicit error budget、observed error、status。 | Future Project J target | "The project is preparing a quantitative correlation path; current results do not yet provide an error budget." |
| RTL golden-reference validation | Not yet | real RTL 或 Verilator reference data、aligned workloads、cycle metrics、error table、limitations。 | Future Project H target | "The next step is a bounded Verilator RTL reference for the banked memory controller." |
| Profiler/counter correlation | Not yet | real profiler / counter captures、schema、region markers、counter definitions、noise notes。 | Future Project I target | "The project will define a profiler/counter interface before making counter-based claims." |
| Absolute model accuracy | No | strong reference data、aligned metrics、error budget、coverage definition。 | Not supported | "Current evidence supports consistency and trends, not absolute accuracy." |
| Full-system cycle accuracy | No | full-system cycle model、clocking、protocol、state alignment、cycle-by-cycle trace comparison。 | Not supported | "The current project is architecture-level and does not claim full-system cycle accuracy." |
| Silicon-level validation | No | real silicon captures、counter definitions、region alignment、measurement-noise analysis。 | Not supported | "No silicon-level claim is made in the current project." |
| Enterprise production signoff | No | enterprise release process、internal references、coverage matrix、owners、waivers、approval。 | Out of scope | "Enterprise release signoff is outside the scope of this public project." |

## 12. Project H / I / J Roadmap

| Project | Purpose | Reference Source | Main Deliverable | Valid Claim After Completion | Limitation |
| --- | --- | --- | --- | --- | --- |
| Project H：Verilator RTL Golden Model MVP | 为 Project E 当前抽象的 banked memory controller behavior 建立 bounded RTL reference。 | local Verilator RTL cycle model for banked memory controller | RTL model、deterministic workloads、aligned model-vs-RTL summary、quantitative error table | 对 bounded workload / metric，C++ model 可以与 bounded local RTL cycle reference 做 quantitative comparison。 | 不覆盖 full SoC、real DRAM timing、AXI/CHI/NoC protocol completeness、silicon behavior 或 gem5-Verilator live co-simulation。 |
| Project I：Profiler / Counter Correlation Interface | 定义 future profiler / hardware-counter capture 的稳定 schema。 | NVIDIA Nsight、Apple Instruments / `powermetrics`、ARM PMU、Linux `perf`、FPGA counters、real captures | counter schema、manifest format、parser smoke tests、sample-data policy、reference-source metadata | 项目具备接收 real profiler/counter capture 的接口和 metric definition 框架。 | sample data 只能证明 parser/schema behavior，不能证明 hardware-counter correlation。 |
| Project J：Accuracy Validation Report | 把 real reference data 和 model outputs 转成 claim-bounded accuracy evidence report。 | Project H RTL data；Project I real capture data when available | claim table、evidence source、metric、reference、error budget、observed error、limitation、status | 对 specific workload/region/metric/reference，报告 observed error 和 pass/fail/warning/invalid/not_applicable status。 | 不泛化到未测 coverage，不能替代 enterprise signoff。 |

## 13. Project H 细化：Verilator RTL Golden Model MVP

Project H 应从 local banked memory controller RTL reference 开始，而不是 full SoC。目标是建立
controlled block-level reference，用于比较 Project E 中已经存在的 memory queueing abstraction。

Required inputs：

- deterministic transaction stream；
- model configuration；
- RTL configuration；
- clock definition；
- reset / warm-up policy；
- measurement-region marker；
- accepted/rejected transaction definition。

Required outputs：

- RTL trace 或 summary；
- C++ model summary；
- aligned workload manifest；
- latency cycles；
- accepted transaction count；
- rejected transaction count；
- p95 / p99 latency；
- quantitative error table。

完成后可以说：

```text
For the bounded banked-memory-controller workload set, the C++ model has been
compared against a bounded local Verilator RTL cycle reference with explicit
per-metric error reporting.
```

完成后仍不能说：

```text
The full system is cycle accurate.
```

## 14. Project I 细化：Profiler / Counter Correlation Interface

Project I 不应该从“假装已有 hardware data”开始。它应该先定义能够接收 real captures 的 schema。

schema 应预留：

- reference source；
- platform；
- tool name and version；
- workload name；
- binary hash 或 source version；
- input dataset；
- region marker；
- metric name；
- unit；
- raw value；
- normalized value；
- sampling mode；
- counter definition；
- known limitations；
- capture timestamp；
- multiplexing / overflow / permission notes。

Target sources：

- NVIDIA Nsight；
- Apple Instruments；
- Apple `powermetrics`；
- ARM PMU；
- Linux `perf`；
- FPGA counters；
- emulator counters；
- internal lab captures when available。

Sample data policy：

- sample data 可以测试 parser behavior；
- sample data 可以测试 report formatting；
- sample data 可以用于 CI schema stability；
- sample data 必须明确标记为 sample 或 synthetic；
- sample data 不能作为 real hardware evidence。

## 15. Project J 细化：Accuracy Validation Report

Project J 是把 reference data 转成 explicit claim 的 reporting layer。

Project J report 应包含：

- claim；
- evidence source；
- workload；
- measurement region；
- metric；
- model value；
- reference value；
- unit；
- error formula；
- error budget；
- observed error；
- status；
- limitation；
- owner 或 source note；
- reproduction command 或 manifest path。

建议 status vocabulary：

- `pass`：observed error 在 error budget 内；
- `fail`：observed error 超出 error budget；
- `warning`：数据可计算但存在 sample size、noise、counter ambiguity 等风险；
- `invalid`：workload、region、metric 或 reference 未对齐，不能计算有效 error；
- `not_applicable`：该 metric 不适用于当前 reference 或 workload。

未来输出形态：

```text
accuracy_validation_summary.csv
accuracy_validation_report.md
validation_manifest.json
```

这些是 future deliverables。Project G 不生成这些文件。

## 16. Interview Wording

### Project F 完成后的保守表达

```text
Project F provides trend-level correlation. I compare gem5 stats context with
replay and queueing-model summaries to check whether selected workloads preserve
expected direction and ranking. I do not claim absolute accuracy, RTL
correlation, silicon correlation, or hardware-counter validation at this stage.
```

### Project G 完成后的路线图表达

```text
Project G defines the accuracy ladder. The current evidence is Level 0/1:
internal consistency, replay equivalence, regression health, and qualitative
trend correlation. The next step is to introduce real bounded references, then
compute explicit error only when workload, region, metric, and reference source
are aligned.
```

### Project H 完成后的更强表达

```text
After Project H, the intended claim is bounded RTL correlation: for a local
banked-memory-controller RTL reference and deterministic workload set, the C++
model can be compared against RTL cycle-level metrics with an explicit error
table. The claim remains limited to that block, workload set, metric set, and
reference configuration.
```

### 禁止表达

当前项目禁止使用：

```text
The model is guaranteed accurate.
Project F proves absolute accuracy.
The replay model matches hardware timing.
The current project is silicon validated.
Do not say the current project is production signoff ready.
The model is full-system cycle accurate.
The model implements AXI, CHI, or NoC protocol completeness.
Synthetic counter samples prove hardware-counter validation.
```

## 17. Forbidden Claims

当前仓库不能声称：

- absolute accuracy validation；
- silicon validation；
- production RTL validation；
- full-system cycle accuracy；
- AXI、CHI、NoC protocol compliance；
- product readiness；
- enterprise production signoff；
- sample data 支撑 hardware-counter validation；
- real RTL data 出现前声称 Verilator RTL validation；
- same workload、same region、same metric、same reference source、explicit error
  budget、observed error、status 全部存在前声称 quantitative correlation。

## 18. Project G 验收标准

Project G 完成条件：

- 本路线图文档存在；
- `docs/validation/accuracy_validation_taxonomy.md` 定义五级 validation taxonomy；
- 当前 Project B/C/D/E/F/R claim boundary 被明确记录；
- Level 0 到 Level 4 被清楚区分；
- Project H/I/J roadmap 被记录；
- forbidden wording 被记录；
- 不修改 source code；
- 不修改 README；
- 不生成 experiment artifacts。

Project G 当前可以声称：

```text
The repository now has a documented golden-reference correlation roadmap and
accuracy-claim taxonomy.
```

Project G 当前不能声称：

```text
The model has been quantitatively correlated against a golden reference.
```
