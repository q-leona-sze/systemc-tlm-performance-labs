# Project J: Accuracy Validation Report

状态：MVP design and report source

## 1. Purpose

Project J is an accuracy validation report, not a new simulator.

它的目标是把 Project G / H / I 已经建立的 validation taxonomy、bounded RTL
reference path 和 profiler / counter interface 收束成一份 claim-bounded evidence
packet。Project J 不运行 Project H，不运行 Project I，不生成新的 reference data，也不补造
missing results。

Project J 只回答：

- 当前仓库能支持哪些 validation claim；
- 每个 claim 依赖哪个 evidence source；
- 每个 claim 对应哪个 validation level；
- reference source 是什么；
- metric、error budget 和 observed error 是否存在；
- 当前哪些 claim 必须保持 unsupported 或 future。

## 2. Current Scope

Current scope：

- 读取 static Project J claim matrix。
- 读取 static Project J evidence table。
- 读取 static unsupported-claim table。
- 如果 Project H generated results 存在，读取 bounded model-vs-RTL correlation evidence。
- 如果 Project I generated results 存在，读取 sample-only counter interface evidence。
- 如果 Project H / I generated results 不存在，标记 `not_generated` 或 `not_available`。

Out of scope：

- 不新增 simulator。
- 不修改 Project H RTL flow。
- 不修改 Project I counter flow。
- 不新增真实 profiler data。
- 不新增 silicon data。
- 不做 production signoff。
- 不做 full-system cycle accuracy claim。

## 3. Validation Philosophy

Accuracy claims are bounded by workload, region, metric definition, reference
source, and error budget.

Project J 采用最低可支撑 claim 原则：

```text
No reference, no correlation.
No aligned metric and measurement region, no quantitative error.
No real RTL, profiler, counter, FPGA, or silicon data, no golden-reference claim.
```

数字本身不构成 accuracy evidence。只有当 workload、measurement region、metric
definition、reference source、unit conversion、error formula 和 error budget 对齐时，Project J
才允许记录 observed error。

## 4. Evidence Sources

Project G defines taxonomy and claim boundaries.

Project H provides local Verilator RTL reference evidence for a banked memory
controller micro-model only.

Project I provides sample-only counter schema and ingest interface, not
hardware-counter evidence.

主要 evidence sources：

| Source | Role | Claim Boundary |
| --- | --- | --- |
| `docs/validation/accuracy_validation_taxonomy.md` | validation level taxonomy | 约束 claim level |
| `docs/validation/project_g_golden_reference_correlation_plan.md` | roadmap and claim boundary | 不提供 observed error |
| `docs/validation/project_h_verilator_rtl_golden_model_report.md` | bounded RTL reference design note | 只覆盖 local banked memory controller micro-model |
| `examples/lt/results/project_h_verilator_rtl_golden_model/model_vs_rtl_correlation.csv` | optional generated model-vs-RTL observed-error table | 缺失时为 `not_generated` |
| `docs/validation/project_i_profiler_counter_correlation_interface_report.md` | counter interface design note | sample-only interface evidence |
| `examples/lt/results/project_i_profiler_counter_correlation_interface/counter_correlation_ready.csv` | optional generated counter interface output | sample data is not hardware evidence |

## 5. Validation Level Summary

| Level | Meaning | Current Project J Mapping |
| --- | --- | --- |
| Level 0 Internal consistency | implementation consistency and schema stability | Project D replay consistency, Project I sample-only interface readiness |
| Level 1 Trend correlation | qualitative direction / ranking evidence | Project F gem5 stats trend correlation |
| Level 2 Quantitative correlation | aligned metric with reference and explicit error budget | only when Project H generated correlation rows are available |
| Level 3 Golden reference validation | real bounded reference data with Level 2 alignment | Project H is bounded local Verilator RTL reference, not full SoC |
| Level 4 Production signoff | enterprise release process | unsupported / out of scope |

Current repository does not provide silicon validation.
Current repository does not provide production signoff.
Current repository does not prove full-system cycle accuracy.
Current repository does not validate full SoC behavior.

## 6. Claim Matrix

The claim matrix lives at:

```text
examples/lt/validation_packet/project_j_claim_matrix.csv
```

Required fields：

```text
claim_id,project,validation_level,claim,workload_scope,region_scope,metric_scope,
reference_source,evidence_source,error_budget,observed_error,status,valid_wording,
invalid_wording,limitation,next_step
```

Project J treats the matrix as the authoritative source for current claim status.
It distinguishes `pass`, `partial`, `future`, `unsupported`, and `not_applicable`.

## 7. Evidence Inventory

The evidence table lives at:

```text
examples/lt/validation_packet/project_j_evidence_table.csv
```

Static source files are required. If a required static file is missing, the packet
builder must fail.

Generated results are optional. If a generated result is missing, the packet
builder must mark it as `not_generated` and continue.

## 8. Metric / Reference / Error Budget Summary

Project J does not invent metric values. It only reports observed error when the
source artifact already contains it.

Project H metric / reference / error-budget source：

```text
examples/lt/results/project_h_verilator_rtl_golden_model/model_vs_rtl_correlation.csv
examples/lt/results/project_h_verilator_rtl_golden_model/error_budget.csv
```

Project H bounded metrics may include:

- `total_requests`
- `accepted_requests`
- `rejected_requests`
- `avg_latency_cycles`
- `p50_latency_cycles`
- `p95_latency_cycles`
- `p99_latency_cycles`
- `max_latency_cycles`
- `throughput_txn_per_cycle`
- `throughput_txn_per_us`
- `bank_conflict_ratio_pct`

If Project H outputs are missing, Project J must report:

```text
observed_error=not_available
quality_status=not_generated
```

Project I sample counter rows do not provide a hardware error budget. They are
schema and interface evidence only.

## 9. Project H Bounded RTL Correlation Evidence

Project H can support a bounded local Verilator RTL reference correlation claim
only for the local banked memory controller micro-model.

Valid Project H scope：

- deterministic normalized traces；
- local RTL module；
- H-aligned model summary；
- aligned metrics from `model_vs_rtl_correlation.csv`；
- explicit error budget from Project H correlation rules。

Invalid Project H scope：

- full SoC behavior；
- real product memory controller；
- AXI / CHI / NoC protocol validation；
- silicon behavior；
- enterprise production validation。

If generated Project H results are absent in a clean checkout, Project J must mark
the Project H observed-error evidence as `not_generated`.

## 10. Project I Counter Interface Evidence

Project I is sample-only in the current repository.

Supported claim：

```text
Project I validates counter schema, metadata join, normalization, and
correlation-ready formatting on sample_synthetic data.
```

Unsupported claim：

```text
Project I validates hardware counters.
```

Project I rows with `data_class=sample_synthetic` and
`claim_status=sample_only_not_evidence` are not hardware evidence. They may be
used for parser smoke tests, schema stability checks, normalization checks, and
future Project J report formatting.

## 11. Missing Evidence and not_generated Items

Project J must not fail when optional generated evidence is absent.

Missing generated results must be represented as:

- `quality_status=not_generated`
- `observed_error=not_available`
- `reference_value=not_available`
- `model_value=not_available`

This is an evidence-state marker, not a model failure.

## 12. Unsupported Claims

The unsupported-claim table lives at:

```text
examples/lt/validation_packet/project_j_unsupported_claims.csv
```

It records claims that are outside current evidence:

- silicon validation；
- production release signoff；
- full-system cycle accuracy；
- full SoC validation；
- AXI / CHI protocol validation；
- real NVIDIA Nsight integration；
- real Apple Instruments / powermetrics integration；
- real ARM PMU integration；
- real Linux perf validation；
- FPGA counter validation；
- hardware-counter claim from sample synthetic data；
- Apple / NVIDIA / ARM production-level validation。

## 13. Claim Boundary

Project J supports evidence reporting, not claim expansion.

Current repository can say:

```text
The project has an explicit validation ladder and an evidence packet that ties
each accuracy statement to a reference source, metric definition, workload
region, and error-budget state.
```

Current repository cannot say:

```text
The model is validated against silicon, accepted for production release, or
cycle-accurate for the full system.
```

## 14. Interview-Safe Wording

```text
I built a compact architecture performance modeling lab with an explicit validation ladder: internal replay consistency, gem5 trend correlation, local Verilator RTL reference correlation, and a sample-only profiler/counter interface for future real captures. The project is careful about claim boundaries: every accuracy statement is tied to a reference source, metric definition, workload region, and error budget.
```

Forbidden Wording：

- silicon validated
- production signoff
- full-system cycle accurate
- Apple/NVIDIA/ARM production-level validation
- full SoC validated
- hardware-counter validated

## 15. Future Work

Future upgrades require real evidence, not stronger wording.

Possible next steps：

- run Project H in a Verilator-capable environment and generate bounded RTL correlation outputs；
- add a validation manifest with tool version, workload identity, config, trace hash, and output hash；
- add real profiler / counter captures with source metadata；
- define counter-specific error budgets；
- add measurement-region markers for real captures；
- record measurement noise, overflow, multiplexing, permission, and calibration notes；
- keep Level 4 enterprise production signoff outside public-project claims。

## 16. Relationship to Project G, Project H, Project I

Project G defines the taxonomy and claim-boundary rules.

Project H provides a bounded local Verilator RTL reference path for a banked memory
controller micro-model. It does not provide full SoC validation or silicon
validation.

Project I provides a sample-only profiler / counter ingestion interface. It does
not provide hardware-counter evidence until real captures with metadata, region
alignment, metric definitions, and error budgets are added.

Project J consumes these artifacts and emits a claim-bounded validation packet.
It does not modify Project G, Project H, Project I, existing results, RTL, or
regression flows.
