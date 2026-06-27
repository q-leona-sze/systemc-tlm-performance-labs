# Project AA: Scenario Decision Benchmark

schema_version: `scenario-r1.0`

## Purpose

Project AA 在 Project Z architecture recommendation engine 之上增加一个
lightweight deterministic scenario decision benchmark。它读取 architecture
scenario CSV，把 scenario、bottleneck family、candidate actions、risk / impact /
features 和 evidence mapping 组合起来，为每个 scenario 选择一个 bounded
recommended action。

This scenario decision benchmark is a bounded rule-based architecture reasoning layer. It does not claim Apple Silicon simulation, NVIDIA GPU simulation, Arm CHI compliance, AXI compliance, ACE compliance, real hardware profiling, automatic hardware optimization, real design-space exploration, real NoC behavior, real cache coherency, cycle-accurate modeling, silicon validation, or production signoff.

## Inputs

默认 sample input:

- `examples/scenarios/sample_architecture_scenarios.csv`

生成输出:

- `docs/generated/scenario_decision_benchmark.md`

Project AA 不读取 trace，不重新生成 `summary.csv`，不修改 AT-6 / AT-7 / AT-8
core simulation `.cpp`，也不改变 portfolio validation `p0.5`。

## Scenario Format

Required columns:

- `scenario`
- `description`
- `workload`
- `bottleneck_family`
- `recommendation_family`
- `candidate_actions`
- `primary_metric`
- `secondary_metric`
- `latency_sensitivity`
- `throughput_sensitivity`
- `fairness_sensitivity`
- `ordering_sensitivity`
- `implementation_risk`
- `evidence_project`
- `industry_mapping`
- `expected_decision_family`
- `expected_recommended_action`

`candidate_actions` 使用 semicolon 分隔。`expected_decision_family` 和
`expected_recommended_action` 只用于 `--strict` self-check，不参与训练，也不是
machine learning label。

## Decision Families

| bottleneck family | decision family | evidence project |
| --- | --- | --- |
| `shared_fabric_pressure` | `fabric_decision` | AT-6 |
| `throughput_bandwidth_wall` | `bandwidth_wall_decision` | AT-7 |
| `noc_qos_coherency_boundary` | `noc_qos_boundary_decision` | AT-8 |
| `mixed_or_uncertain` | `mixed_decision` | AT-6+AT-7+AT-8 |

## Rule-Based Decision Logic

Project AA is not machine learning and not an optimizer. It uses deterministic
scoring over the candidate actions provided by each scenario:

- `fabric_decision`: high latency sensitivity favors
  `protect_latency_initiator`; high fairness sensitivity favors
  `throttle_bulk_dma` or `fairness_guard`; high throughput sensitivity without
  high latency sensitivity can consider `increase_fabric_capacity`; high
  implementation risk favors `schedule_high_pressure_initiators`.
- `bandwidth_wall_decision`: throughput memory-wall symptoms favor
  `throttle_outstanding_after_knee`; bursty / tail-latency scenarios favor
  `shape_bursty_traffic`; high latency sensitivity avoids blind
  `increase_outstanding_depth`; `bandwidth_aware_batching` can be a secondary
  recommendation.
- `noc_qos_boundary_decision`: high ordering sensitivity favors
  `reduce_boundary_crossing`; write-heavy / read-tail interference favors
  `protect_read_latency_from_bulk_write`; high fairness sensitivity favors
  `qos_partition`; route hotspot scenarios favor `route_isolation`.
- `mixed_decision`: starts with `run_targeted_evidence_checks`, then considers
  `collect_more_workload_symptoms`, `split_scenario_by_bottleneck_family`, and
  `avoid_single_family_overfit`.

## Evidence Mapping

Project AA sits above Project X/Y/Z:

```text
Project X industry mapping -> Project Y bottleneck family -> Project Z recommendation family -> Project AA scenario-level decision
```

It uses evidence project tags to keep each decision grounded:

- AT-6 supports shared-fabric pressure discussion.
- AT-7 supports bandwidth-wall / throughput saturation discussion.
- AT-8 supports NoC/QoS/coherency-boundary discussion.
- AT-6+AT-7+AT-8 supports mixed evidence review before choosing one action.

## Example Command

```bash
python3 tools/run_scenario_decision_benchmark.py \
  --input examples/scenarios/sample_architecture_scenarios.csv \
  --output docs/generated/scenario_decision_benchmark.md \
  --strict
```

Expected PASS marker:

```text
Scenario Decision Benchmark PASS
scenarios=6
decision_families=fabric_decision,bandwidth_wall_decision,noc_qos_boundary_decision,mixed_decision
claim_boundary=PASS
schema_version=scenario-r1.0
```

## Output Interpretation

Each scenario row produces:

- `decision_family`
- `recommended_action`
- `confidence`
- `risk_if_wrong`
- `what_to_measure_next`
- action scoring notes
- evidence mapping
- claim boundary

The output should be read as a bounded scenario-level decision aid. It compares
candidate actions under workload-specific constraints; it does not synthesize
hardware or replace measurement.

## How This Supports Architecture Review

Project Y classifies symptoms. Project Z maps families to recommendation
families. Project AA asks a review-level question:

```text
given this scenario and candidate actions, which bounded action is most defensible?
```

This supports interview discussion because it shows the full reasoning stack:

```text
symptoms -> bottleneck family -> recommendation family -> scenario-level decision -> claim boundary
```

## Project AB Next-Layer Architecture Decision Memo Generator

Project AB consumes scenario decision benchmark outputs and turns them into
decision memos. It reads Project AA `scenario-r1.0`, Project Z
`recommendation-r1.0`, Project Y `classifier-r1.0`, and memo request CSV rows,
then emits `memo-r1.0` architecture review memos.

Project AB artifacts:

- `tools/generate_architecture_decision_memos.py`
- `examples/decision_memos/sample_decision_memo_requests.csv`
- `docs/metrics_and_diagnosis/architecture_decision_memo_generator.md`
- `docs/generated/architecture_decision_memos.md`

Decision-stack view:

```text
Project Y bottleneck family -> Project Z recommendation family -> Project AA scenario-level decision -> Project AB architecture decision memo
```

Project AB keeps Project AA `scenario-r1.0` unchanged. It adds `memo-r1.0`
generated memo evidence and does not claim automatic hardware optimization,
real hardware profiling, real design-space exploration, silicon validation, or
production signoff.

## Limitations

- Not a SystemC simulation model.
- Not machine learning.
- Not a hardware profiler.
- Not an automatic hardware optimization flow.
- Not real design-space exploration.
- Does not regenerate trace CSV.
- Does not modify AT-6 / AT-7 / AT-8 core simulation `.cpp`.
- Does not modify AT-6 / AT-7 / AT-8 `summary.csv` schema.
- Does not modify portfolio evidence harness `p0.5`.
- Does not modify Project X `industry-r1.0`.
- Does not modify Project Y `classifier-r1.0`.
- Does not modify Project Z `recommendation-r1.0`.

## Claim Boundary

Current:

- Project AA is implemented as a deterministic scenario decision benchmark over
  sample architecture scenario CSV input.
- It generates `scenario-r1.0` markdown evidence.

Supported:

- bounded rule-based scenario decision benchmark
- architecture reasoning layer
- scenario-level decision
- evidence-backed decision discussion
- portfolio / interview architecture review narrative

Not Supported:

- Apple Silicon simulation
- NVIDIA GPU simulation
- Arm CHI compliance
- AXI compliance
- ACE compliance
- real hardware profiling
- automatic hardware optimization
- real design-space exploration
- real NoC behavior
- real cache coherency
- cycle-accurate modeling
- silicon validation
- production signoff

Future Work:

- Add more deterministic scenario rows only when new evidence artifacts justify
  them.
- Keep future versions deterministic, review-oriented, and claim-bounded.
