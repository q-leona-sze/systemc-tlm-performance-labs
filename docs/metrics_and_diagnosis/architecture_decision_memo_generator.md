# Project AB: Architecture Decision Memo Generator

schema_version: `memo-r1.0`

## Purpose

Project AB 在 Project AA scenario decision benchmark 之上增加一个 lightweight
deterministic architecture decision memo generator。它读取 memo request CSV、
Project AA scenario decision benchmark、Project Z recommendation report 和
Project Y classification report，为每个 scenario 生成 bounded architecture
decision memo。

This architecture decision memo generator is a bounded rule-based architecture reasoning layer. It does not claim Apple Silicon simulation, NVIDIA GPU simulation, Arm CHI compliance, AXI compliance, ACE compliance, real hardware profiling, automatic hardware optimization, real design-space exploration, real NoC behavior, real cache coherency, cycle-accurate modeling, silicon validation, or production signoff.

它的用途是把 evidence chain 变成 architecture review memo：不仅说明 metric 或
classification，也说明 decision、risk、what to measure next 和 claim boundary。

## Inputs

Project AB consumes:

- `examples/decision_memos/sample_decision_memo_requests.csv`
- `docs/generated/scenario_decision_benchmark.md`
- `docs/generated/architecture_recommendations.md`
- `docs/generated/workload_bottleneck_classification.md`

Generated output:

- `docs/generated/architecture_decision_memos.md`

Project AB 不读取 trace，不重新生成 `summary.csv`，不修改 AT-6 / AT-7 / AT-8
core simulation `.cpp`，不修改 Project X/Y/Z/AA schema，也不改变 portfolio
validation `p0.5`。

## Memo Request Format

Required columns:

- `memo_id`
- `scenario`
- `workload`
- `decision_family`
- `recommended_action`
- `evidence_project`
- `industry_mapping`
- `memo_type`
- `audience`
- `decision_context`
- `expected_primary_decision`
- `expected_memo_type`

`expected_primary_decision` 和 `expected_memo_type` 只用于 `--strict`
self-check。它们不是训练标签，也不表示 machine learning。

## Memo Types

| memo_type | evidence project | industry mapping | primary decision family |
| --- | --- | --- | --- |
| `fabric_memo` | AT-6 | Apple-like | protect latency-sensitive initiator traffic |
| `bandwidth_wall_memo` | AT-7 | NVIDIA-like | avoid pressure past the bandwidth knee or shape burstiness |
| `noc_qos_boundary_memo` | AT-8 | Arm-like | protect read latency or reduce boundary crossing |
| `mixed_evidence_memo` | AT-6+AT-7+AT-8 | Mixed | run targeted evidence checks before choosing one action |

## Evidence Chain

Project AB keeps the full decision stack visible:

```text
AT-6/AT-7/AT-8 evidence
-> Project X industry mapping
-> Project Y bottleneck classification
-> Project Z recommendation
-> Project AA scenario decision
-> Project AB memo
```

This chain is the core claim boundary. A memo can discuss architecture reasoning
only to the extent that the upstream evidence supports it.

## Rule-Based Memo Generation Logic

Project AB is deterministic, rule-based, and request-driven:

- `fabric_memo`: use AT-6 / Apple-like shared-fabric evidence. The default
  decision is `protect_latency_initiator`, or the request's
  `recommended_action`. Risk if ignored: shared-fabric pressure can turn
  concurrent initiator traffic into queue growth and latency outliers. Measure
  queue peak, initiator-level latency, starvation, fabric utilization, and
  traffic mix.
- `bandwidth_wall_memo`: use AT-7 / NVIDIA-like bandwidth-wall evidence. The
  default decisions are `throttle_outstanding_after_knee` or
  `shape_bursty_traffic`. Risk if ignored: increasing pressure past the
  bandwidth knee may grow queues without proportional throughput gains. Measure
  throughput saturation knee, outstanding depth, queue peak, p99 latency, and
  burstiness.
- `noc_qos_boundary_memo`: use AT-8 / Arm-like boundary/QoS evidence. The
  default decisions are `protect_read_latency_from_bulk_write` or
  `reduce_boundary_crossing`. Risk if ignored: boundary-crossing,
  ordering-sensitive, or write-heavy pressure can create tail latency and
  starvation symptoms. Measure boundary crossing rate, ordering events,
  read/write interference, QoS pressure, and starvation events.
- `mixed_evidence_memo`: use AT-6+AT-7+AT-8 evidence. The default decision is
  `run_targeted_evidence_checks`. Risk if ignored: overfitting one bottleneck
  family can lead to wrong mitigation and hidden regressions. Measure by
  splitting the scenario into fabric, bandwidth-wall, and boundary/QoS symptoms,
  then rerun the targeted reasoning stack.

## Example Command

```bash
python3 tools/generate_architecture_decision_memos.py \
  --requests examples/decision_memos/sample_decision_memo_requests.csv \
  --scenario-report docs/generated/scenario_decision_benchmark.md \
  --recommendation-report docs/generated/architecture_recommendations.md \
  --classification-report docs/generated/workload_bottleneck_classification.md \
  --output docs/generated/architecture_decision_memos.md \
  --strict
```

Expected PASS marker:

```text
Architecture Decision Memo Generator PASS
memos=6
memo_types=fabric_memo,bandwidth_wall_memo,noc_qos_boundary_memo,mixed_evidence_memo
claim_boundary=PASS
schema_version=memo-r1.0
```

## Output Interpretation

Each memo includes:

- Memo ID
- Scenario
- Workload
- Audience
- Executive Summary
- Problem
- Decision
- Evidence Chain
- Primary Recommendation
- Secondary Considerations
- Risk if Ignored
- Risk if Wrong
- What to Measure Next
- Confidence
- Claim Boundary

The output should be read as an architecture review memo, not as a design tool.
It is useful for explaining why a decision is defensible, what evidence supports
it, and what still needs measurement.

## How This Supports Architecture Review And Interview Storytelling

Project AB turns the reasoning stack into review language:

```text
workload symptoms -> bottleneck classification -> recommendation -> scenario decision -> architecture memo
```

In an interview, this demonstrates how performance evidence becomes an
architecture decision narrative. The memo format makes the reasoning reviewable:
decision, evidence chain, risks, next measurements, and unsupported claims are
visible in one artifact.

## Limitations

- Not a SystemC simulation model.
- Not machine learning.
- Not a profiler.
- Not an optimizer.
- Not automatic hardware optimization.
- Not real design-space exploration.
- Does not regenerate trace CSV.
- Does not modify AT-6 / AT-7 / AT-8 core simulation `.cpp`.
- Does not modify AT-6 / AT-7 / AT-8 `summary.csv` schema.
- Does not modify portfolio evidence harness `p0.5`.
- Does not modify Project X `industry-r1.0`.
- Does not modify Project Y `classifier-r1.0`.
- Does not modify Project Z `recommendation-r1.0`.
- Does not modify Project AA `scenario-r1.0`.

## Claim Boundary

Current:

- Project AB is implemented as a deterministic architecture decision memo
  generator over memo request CSV input.
- It generates `memo-r1.0` markdown evidence.

Supported:

- bounded rule-based architecture decision memo generator
- architecture reasoning layer
- architecture review memo
- evidence chain
- decision memo
- portfolio / interview architecture review storytelling

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

- Add more deterministic memo templates only when new upstream evidence justifies
  them.
- Keep future versions request-driven, deterministic, and claim-bounded.
