# Project Z: Architecture Recommendation Engine

schema_version: `recommendation-r1.0`

## Purpose

Project Z 在 Project Y workload-to-bottleneck classifier 之上增加一个
lightweight deterministic architecture recommendation engine。它把 workload
symptoms / classifier family 转换为 bounded architecture recommendation，用于
portfolio、interview 和 architecture reasoning。

This recommendation engine is a bounded rule-based architecture reasoning layer. It does not claim Apple Silicon simulation, NVIDIA GPU simulation, Arm CHI compliance, AXI compliance, ACE compliance, real hardware profiling, automatic hardware optimization, real NoC behavior, real cache coherency, cycle-accurate modeling, silicon validation, or production signoff.

## Inputs

Project Z consumes:

- `examples/workloads/sample_workload_symptoms.csv`
- `docs/generated/workload_bottleneck_classification.md`

它承接 Project Y 的 family definitions：

- `shared_fabric_pressure`
- `throughput_bandwidth_wall`
- `noc_qos_coherency_boundary`
- `mixed_or_uncertain`

## Recommendation Families

| Project Y family | Project Z recommendation family | Evidence project | Industry-inspired mapping |
| --- | --- | --- | --- |
| `shared_fabric_pressure` | `fabric_mitigation` | AT-6 | Apple-like heterogeneous SoC shared fabric pressure |
| `throughput_bandwidth_wall` | `bandwidth_wall_mitigation` | AT-7 | NVIDIA-like throughput engine bandwidth wall |
| `noc_qos_coherency_boundary` | `noc_qos_boundary_mitigation` | AT-8 | Arm-like AMBA-inspired NoC QoS and coherency-boundary pressure |
| `mixed_or_uncertain` | `mixed_evidence_required` | AT-6/AT-7/AT-8 | Mixed Apple-like / NVIDIA-like / Arm-like evidence family |

## Rule-Based Recommendation Logic

Project Z is not machine learning and not an optimizer. It uses deterministic
rules:

- `fabric_mitigation`: protect latency-sensitive initiators, cap bulk/DMA-like
  traffic, separate or schedule high-pressure initiators, increase shared fabric
  capacity only if queue pressure persists, and monitor starvation risk.
- `bandwidth_wall_mitigation`: stop increasing outstanding depth after the knee
  point, tune occupancy / outstanding limits, shape burstiness, prefer
  bandwidth-aware batching, and use a throttled profile when tail latency is a
  risk.
- `noc_qos_boundary_mitigation`: isolate boundary-crossing traffic, reduce
  ordering-sensitive serialization, protect read latency from write-heavy bulk
  traffic, partition QoS / VC-like resources, and avoid route hotspot mapping.
- `mixed_evidence_required`: do not overfit one bottleneck family; run targeted
  AT-6 / AT-7 / AT-8 evidence checks, collect additional symptoms, and split
  shared-fabric, bandwidth-wall, and boundary/QoS signals.

## Evidence Mapping

Project Z keeps the Project X / Project Y evidence chain explicit:

```text
workload symptoms -> Project Y bottleneck family -> Project Z recommendation family -> AT-6 / AT-7 / AT-8 evidence-backed action
```

The recommendation output is a discussion aid. It points to what to measure next
and which mitigation family to inspect; it does not synthesize hardware.

## Example Command

```bash
python3 tools/generate_architecture_recommendations.py \
  --input examples/workloads/sample_workload_symptoms.csv \
  --classification docs/generated/workload_bottleneck_classification.md \
  --output docs/generated/architecture_recommendations.md \
  --strict
```

Expected PASS marker:

```text
Architecture Recommendation Engine PASS
workloads=6
recommendation_families=fabric_mitigation,bandwidth_wall_mitigation,noc_qos_boundary_mitigation,mixed_evidence_required
claim_boundary=PASS
schema_version=recommendation-r1.0
```

## Output Interpretation

Generated output:

- `docs/generated/architecture_recommendations.md`

Each workload row includes:

- predicted bottleneck family
- evidence project
- industry-inspired mapping
- primary recommendation
- secondary recommendation
- risk if ignored
- confidence
- what to measure next

## How This Supports Architecture Decision Discussion

Project Y answers which bottleneck family the workload symptoms resemble.
Project Z answers what bounded architecture action family should be discussed
next. This creates an interview-friendly path:

```text
observable symptoms -> bottleneck family -> evidence-backed action -> claim boundary
```

It demonstrates architecture judgment: recommendations are tied to AT-6 / AT-7 /
AT-8 evidence families and remain explicit about unsupported claims.

## Project AA Next-Layer Scenario Decision Benchmark

Project AA consumes recommendation families and scenario constraints to produce
decision benchmark outputs. It starts from the Project Z family-to-action
layer, then evaluates candidate actions under scenario-specific latency,
throughput, fairness, ordering, and implementation-risk constraints.

Project AA artifacts:

- `tools/run_scenario_decision_benchmark.py`
- `examples/scenarios/sample_architecture_scenarios.csv`
- `docs/metrics_and_diagnosis/scenario_decision_benchmark.md`
- `docs/generated/scenario_decision_benchmark.md`

Decision-stack view:

```text
Project Y bottleneck family -> Project Z recommendation family -> Project AA scenario-level decision
```

Project AA keeps Project Z `recommendation-r1.0` unchanged. It adds
`scenario-r1.0` generated benchmark evidence and does not claim automatic
hardware optimization, real hardware profiling, real design-space exploration,
silicon validation, or production signoff.

## Project AB Next-Layer Architecture Decision Memo Generator

Project AB consumes Project AA scenario decisions and turns them into bounded
architecture decision memos. It keeps Project Z `recommendation-r1.0` unchanged
and uses Project Z output as one evidence link in the memo chain.

Project AB artifacts:

- `tools/generate_architecture_decision_memos.py`
- `examples/decision_memos/sample_decision_memo_requests.csv`
- `docs/metrics_and_diagnosis/architecture_decision_memo_generator.md`
- `docs/generated/architecture_decision_memos.md`

Decision-stack overview:

```text
Project Z -> Project AA -> Project AB
```

Project AB generates `memo-r1.0` architecture review memos. It is not automatic
hardware optimization, not real hardware profiling, not real design-space
exploration, not silicon validation, and not production signoff.

## Limitations

- Not a SystemC simulation model.
- Not machine learning.
- Not a hardware profiler.
- Not a hardware design synthesis tool.
- Not an automatic hardware optimization flow.
- Does not regenerate trace CSV.
- Does not modify portfolio evidence harness p0.5.
- Does not modify Project X `industry-r1.0`.
- Does not modify Project Y `classifier-r1.0`.

## Claim Boundary

Current:

- Project Z is implemented as a deterministic recommendation generator over
  Project Y workload bottleneck families.
- It generates `recommendation-r1.0` markdown evidence.

Supported:

- bounded rule-based recommendation engine
- architecture reasoning layer
- recommendation family mapping
- evidence-backed action discussion
- portfolio / interview decision narrative

Not Supported:

- Apple Silicon simulation
- NVIDIA GPU simulation
- Arm CHI compliance
- AXI compliance
- ACE compliance
- real hardware profiling
- automatic hardware optimization
- real NoC behavior
- real cache coherency
- cycle-accurate modeling
- silicon validation
- production signoff

Future Work:

- Add more deterministic recommendation rules only when new evidence artifacts
  exist.
- Keep recommendation output tied to measurable workload symptoms and explicit
  claim boundaries.
