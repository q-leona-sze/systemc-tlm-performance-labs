# Project Y: Workload-to-Bottleneck Classifier

schema_version: `classifier-r1.0`

## Purpose

Project Y 在 Project X industry evidence release pack 之上增加一个 lightweight
decision layer。它读取 workload symptom CSV，把 observable workload symptoms
映射到 bounded evidence families：

- `shared_fabric_pressure`
- `throughput_bandwidth_wall`
- `noc_qos_coherency_boundary`
- `mixed_or_uncertain`

This classifier is a bounded rule-based architecture reasoning tool. It does
not claim Apple Silicon simulation, NVIDIA GPU simulation, Arm CHI compliance,
AXI compliance, ACE compliance, real hardware profiling, real NoC behavior,
real cache coherency, cycle-accurate modeling, silicon validation, or production
signoff.

## Inputs

默认 sample input:

- `examples/workloads/sample_workload_symptoms.csv`

Required columns:

- `workload`
- `description`
- `concurrent_initiators`
- `memory_utilization_ratio`
- `queue_peak`
- `p99_latency_ns`
- `throughput_req_per_us`
- `avg_outstanding`
- `burstiness_score`
- `boundary_crossing_rate`
- `ordering_events`
- `read_write_interference_score`
- `qos_class_pressure`
- `starvation_events`
- `expected_family`

`expected_family` 只用于 `--strict` self-check，不作为训练标签，也不参与 scoring。

## Rule-Based Classification Model

这个工具不是 machine learning model。它使用 deterministic scoring rules：

- `shared_fabric_pressure`: concurrent initiators 高、queue peak 上升、p99 latency
  上升，同时 boundary / ordering / QoS symptoms 不是 dominant signal。
- `throughput_bandwidth_wall`: memory utilization 接近 saturation、throughput 高、
  outstanding depth 高、burstiness 高，并伴随 queue buildup。
- `noc_qos_coherency_boundary`: boundary crossing、ordering events、read/write
  interference、QoS class pressure、starvation events 或 route / boundary queue
  symptoms 明显。
- `mixed_or_uncertain`: top scores 接近、三个 family signal 同时偏高，或所有
  evidence 都偏弱。

## Bottleneck Families

| Family | Interpretation |
| --- | --- |
| `shared_fabric_pressure` | 多个 heterogeneous initiators 争用 shared fabric / shared memory path。 |
| `throughput_bandwidth_wall` | throughput-oriented engine 遇到 memory utilization / outstanding-depth / burstiness 带来的 bandwidth wall。 |
| `noc_qos_coherency_boundary` | QoS class、route contention、boundary crossing、ordering 和 read/write interference 主导 tail latency。 |
| `mixed_or_uncertain` | workload symptom 不够单一，需要拆 phase 或补充 targeted evidence。 |

## Evidence Mapping

| Classifier family | Evidence family |
| --- | --- |
| `shared_fabric_pressure` | AT-6 -> Apple-like heterogeneous SoC shared fabric pressure |
| `throughput_bandwidth_wall` | AT-7 -> NVIDIA-like throughput engine bandwidth wall |
| `noc_qos_coherency_boundary` | AT-8 -> Arm-like AMBA-inspired NoC QoS and coherency-boundary pressure |
| `mixed_or_uncertain` | needs more evidence |

## Example Command

```bash
python3 tools/classify_workload_bottleneck.py \
  --input examples/workloads/sample_workload_symptoms.csv \
  --output docs/generated/workload_bottleneck_classification.md \
  --strict
```

Expected PASS marker:

```text
Workload Bottleneck Classifier PASS
workloads=6
families=shared_fabric_pressure,throughput_bandwidth_wall,noc_qos_coherency_boundary,mixed_or_uncertain
claim_boundary=PASS
schema_version=classifier-r1.0
```

## Output Interpretation

Generated output:

- `docs/generated/workload_bottleneck_classification.md`

每一行 workload 会得到：

- predicted family
- expected family self-check result under `--strict`
- deterministic scores
- evidence mapping
- recommendation
- claim-boundary text

## How This Supports Architecture Decision Discussion

Project X 把 AT-6 / AT-7 / AT-8 映射到 Apple-like、NVIDIA-like、Arm-like
industry problem families。Project Y 则从 workload symptom 角度反向提问：

```text
observable workload symptoms -> bottleneck family -> AT-6 / AT-7 / AT-8 evidence family
```

这让面试讨论可以从 symptoms 出发，而不是直接跳到 vendor-like narrative。它展示的是
architecture diagnosis structure：先看 observable signals，再选择 evidence family，
最后说明 claim boundary。

## Project Z Next-Layer Recommendation Engine

Project Z consumes classifier families and produces recommendation families.
It reads the same workload symptom source plus
`docs/generated/workload_bottleneck_classification.md`, then generates:

- `docs/generated/architecture_recommendations.md`

Mapping:

| Project Y classifier family | Project Z recommendation family |
| --- | --- |
| `shared_fabric_pressure` | `fabric_mitigation` |
| `throughput_bandwidth_wall` | `bandwidth_wall_mitigation` |
| `noc_qos_coherency_boundary` | `noc_qos_boundary_mitigation` |
| `mixed_or_uncertain` | `mixed_evidence_required` |

Project Z keeps Project Y `classifier-r1.0` unchanged. It adds a bounded
rule-based architecture recommendation layer and does not claim automatic
hardware optimization, real hardware profiling, silicon validation, or
production signoff.

## Decision-Stack Overview

The current decision stack is:

```text
Project Y -> Project Z -> Project AA -> Project AB
```

- Project Y maps workload symptoms to bottleneck families.
- Project Z maps bottleneck families to bounded recommendation families.
- Project AA maps scenario constraints and candidate actions to scenario-level
  recommended actions.
- Project AB turns scenario-level decisions into bounded architecture review
  memos.

Project AA keeps Project Y `classifier-r1.0` and Project Z
`recommendation-r1.0` unchanged. Project AB keeps Project Y/Z/AA schemas
unchanged and produces `memo-r1.0` output for bounded architecture review, not
automatic hardware optimization, real hardware profiling, real design-space
exploration, silicon validation, or production signoff.

## Limitations

- 不替代 real profiler。
- 不使用 machine learning。
- 不从 trace 自动学习 thresholds。
- 不声称 real hardware profiling。
- 不声称 real NoC behavior 或 real cache coherency。
- 不声称 Apple Silicon simulation、NVIDIA GPU simulation、Arm CHI compliance、
  AXI compliance 或 ACE compliance。
- 不声称 cycle-accurate modeling、silicon validation 或 production signoff。

## Claim Boundary

Current:

- Project Y is implemented as a deterministic classifier over sample workload
  symptom CSV input.
- It generates `classifier-r1.0` markdown evidence.

Supported:

- bounded rule-based classifier
- architecture reasoning tool
- workload symptoms to bottleneck family mapping
- AT-6 / AT-7 / AT-8 evidence-family discussion

Not Supported:

- Apple Silicon simulation
- NVIDIA GPU simulation
- Arm CHI compliance
- AXI compliance
- ACE compliance
- real hardware profiling
- real NoC behavior
- real cache coherency
- cycle-accurate modeling
- silicon validation
- production signoff

Future Work:

- Add more workload symptom examples.
- Add phase-split inputs for workloads that naturally contain multiple bottleneck
  families.
- Keep future versions deterministic and claim-bounded.
