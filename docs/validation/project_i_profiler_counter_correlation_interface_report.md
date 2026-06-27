# Project I：Profiler / Counter Correlation Interface

状态：MVP implementation note

Project I 的目标是为未来接入真实 profiler、hardware counter、FPGA counter 或 silicon
profiler 数据建立统一 counter schema、sample ingest flow、normalization tool 和
claim-boundary report。

Project I 第一版只做 sample-only schema smoke test。它不是硬件验证，不是 silicon
validation，不是 production signoff，也不是 full-system cycle accuracy 证据。

## Purpose

Project I 服务于当前项目的 accuracy validation path：

```text
sample counter CSV
+ source metadata CSV
-> normalize_profiler_counters.py
-> normalized_counter_summary.csv
-> counter_source_metadata.csv
-> counter_correlation_ready.csv
-> counter_claim_boundary_report.md
```

它的核心价值是定义未来真实 counter data 进入 Project J accuracy report 前需要满足的
接口、metadata 和 claim boundary。

## Current Scope

当前 Project I MVP 覆盖：

- 统一 profiler / counter sample CSV schema。
- 统一 source metadata CSV schema。
- sample counter CSV ingest。
- source metadata ingest。
- required column validation。
- `data_class` / `source_type` validation。
- metadata join by `capture_id`。
- basic normalization。
- correlation-ready table generation。
- claim-boundary report generation。

当前 Project I 只使用 sample synthetic data：

```text
data_class=sample_synthetic
source_type=sample_synthetic
claim_status=sample_only_not_evidence
```

## Counter Schema

Project I counter sample CSV：

```text
examples/lt/counter_samples/sample_counter_samples.csv
```

字段：

```text
schema_version,capture_id,sample_id,data_class,source_type,workload,region_id,
counter_name,counter_vendor_name,counter_category,counter_definition,raw_value,
raw_unit,aggregation,sampling_mode,window_start_ns,window_end_ns,
normalization_basis,normalization_denominator,notes
```

当前 sample 数据要求：

- `data_class=sample_synthetic`。
- `source_type=sample_synthetic`。
- `notes` 必须包含 `sample_only_not_evidence`。
- `counter_definition` 必须说明 sample-only counter。
- `normalization_denominator` 必须大于 0，除非 `normalization_basis=none`。

预留 source type：

- `linux_perf`
- `arm_pmu`
- `apple_instruments`
- `apple_powermetrics`
- `nvidia_nsight`
- `fpga_counter`
- `silicon_profiler`
- `emulator_counter`
- `sample_synthetic`

这些字段只是接口预留。当前 MVP 不声称已经接入这些真实工具或平台。

## Source Metadata Schema

Project I source metadata CSV：

```text
examples/lt/counter_samples/sample_counter_source_metadata.csv
```

字段：

```text
schema_version,capture_id,data_class,is_real_capture,source_type,tool_name,
tool_version,platform_vendor,platform_model,os_name,os_version,cpu_model,
gpu_model,fpga_board,silicon_stepping,workload,binary_sha256,input_dataset,
region_id,region_start_marker,region_end_marker,capture_timestamp_utc,
permission_notes,multiplexing_notes,overflow_notes,calibration_notes,limitations
```

当前 sample metadata 要求：

- `data_class=sample_synthetic`。
- `is_real_capture=false`。
- `source_type=sample_synthetic`。
- `tool_name=sample_generator`。
- 真实平台字段填 `NA`，不能伪造硬件型号、OS、CPU、GPU、FPGA board 或 silicon stepping。
- `limitations` 必须说明 sample-only, not real hardware counter evidence。

## Normalized Output

`normalize_profiler_counters.py` 生成：

```text
examples/lt/results/project_i_profiler_counter_correlation_interface/normalized_counter_summary.csv
```

字段：

```text
schema_version,capture_id,data_class,source_type,workload,region_id,
counter_name,counter_category,raw_total,raw_unit,normalized_value,
normalized_unit,normalization_basis,sample_count,window_ns,quality_status,
claim_status,notes
```

Normalization rule：

| normalization_basis | normalized_value | normalized_unit |
| --- | --- | --- |
| `none` | `raw_total` | `raw_unit` |
| `per_request` | `raw_total / normalization_denominator` | `raw_unit/request` |
| `per_cycle` | `raw_total / normalization_denominator` | `raw_unit/cycle` |
| `per_us` | `raw_total / normalization_denominator` | `raw_unit/us` |
| invalid denominator | `NA` | `NA` |

当 denominator invalid 时，tool 不崩溃，输出 `quality_status=warning`。

## Correlation-Ready Output

Project I 生成：

```text
examples/lt/results/project_i_profiler_counter_correlation_interface/counter_correlation_ready.csv
```

字段：

```text
workload,region_id,model_metric_candidate,counter_name,counter_value,
counter_unit,capture_id,source_type,data_class,alignment_status,claim_status,
correlation_status,notes
```

Project I 第一版不计算 model-vs-counter error。sample data 的：

```text
claim_status=sample_only_not_evidence
correlation_status=sample_only_not_evidence
```

真实 counter correlation 必须留到 Project J，并且需要 aligned workload、aligned region、
metric definition、reference metadata 和 explicit error budget。

## Sample Data Policy

sample data 可以用于：

- parser smoke test。
- schema stability check。
- metadata join check。
- normalization formatting check。
- report formatting check。

sample data 不能用于：

- hardware-counter validation。
- silicon validation。
- production signoff。
- full-system cycle-accuracy claim。
- NVIDIA / Apple / ARM / FPGA / silicon profiler integration claim。

sample data is not real hardware evidence。

## Supported Claims

完成 Project I MVP 后，允许的 claim 是：

```text
Project I defines a profiler/counter ingestion interface and validates the CSV
schema, metadata join, normalization, and report formatting on sample synthetic
data.
```

更具体地说，Project I 支持：

- counter schema validation。
- source metadata schema validation。
- sample-only CSV ingest。
- metadata join by `capture_id`。
- normalized summary generation。
- correlation-ready table generation。
- claim-boundary report generation。

## Unsupported Claims

Project I 不支持以下 claim：

- 已经接入真实 Linux `perf`。
- 已经接入真实 ARM PMU。
- 已经接入真实 Apple Instruments。
- 已经接入真实 Apple `powermetrics`。
- 已经接入真实 NVIDIA Nsight。
- 已经接入真实 FPGA counter。
- 已经接入真实 silicon profiler。
- hardware counter accuracy validation。
- silicon validation。
- production signoff。
- full-system cycle accuracy。
- AXI / CHI / NoC protocol accuracy。

## Future Work

后续如果接入真实 reference capture，需要新增：

- real capture source adapter。
- real source metadata。
- workload region marker alignment。
- metric definition alignment。
- binary hash 或 source version。
- capture timestamp。
- permission、multiplexing、overflow 和 calibration notes。
- measurement noise notes。
- error budget。
- Project J model-vs-reference observed error report。

真实 Linux perf / ARM PMU / Apple Instruments / NVIDIA Nsight / FPGA / silicon
capture must be added later with metadata, workload region alignment, metric
definition alignment, and explicit error budget.

## Relationship to Project G, Project H, Project J

Project G 定义 golden-reference correlation roadmap 和 claim boundary。Project I 延续
Project G 的规则：sample data 只能证明接口可读，不能证明 hardware-counter correlation。

Project H 已经为 local banked memory controller 建立 bounded Verilator RTL reference path。
Project I 不修改 Project H 的 RTL flow，也不扩大 Project H 的 claim。

Project J 应该消费 Project H RTL data 和 Project I future real capture data，生成带
observed error、error budget、status 和 limitation 的 accuracy validation report。

在 Project J 完成真实 reference alignment 之前，Project I 只表示 interface readiness，不表示
hardware validation。
