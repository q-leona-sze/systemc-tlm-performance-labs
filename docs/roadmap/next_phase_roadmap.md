# Next-Phase Roadmap

## Stage 2 Positioning

Stage 2 is an industry-inspired architecture performance modeling roadmap.

Working theme: Industry-inspired architecture performance modeling roadmap.

Stage 2 does not copy Apple, NVIDIA, or Arm internal implementations. It borrows industry problem types:

- heterogeneous SoC shared memory fabric
- GPU-like throughput and memory saturation
- AMBA-inspired NoC QoS and coherency-boundary exploration

Stage 2 is inspired by industry problem types, not by any proprietary Apple, NVIDIA, or Arm internal implementation. The models remain bounded AT-level synthetic explorations for trend comparison, bottleneck isolation, and architecture recommendation logic.

## What Stage 2 Is

- bounded AT-level synthetic modeling
- architecture performance exploration
- bottleneck isolation
- workload-to-metric reasoning
- architecture recommendation logic
- portfolio-grade evidence generation

## What Stage 2 Is Not

- not Apple Silicon simulation
- not NVIDIA GPU simulation
- not Arm CHI / AXI / ACE compliance
- not real NoC implementation
- not real DRAM-controller implementation
- not cycle-accurate modeling
- not silicon validation
- not production signoff

## Roadmap

### Project T: Stage-1 Summary and Industry Roadmap

Project T documents Stage 1 as a completed portfolio phase and opens the bridge toward Stage 2. It turns the completed memory-system bottleneck labs into a concise stage summary, engineering lesson set, and industry-inspired roadmap.

### Project AT-6: Heterogeneous SoC Shared Memory Fabric Lab

Project AT-6 builds a synthetic AT-level lab where CPU-like, NPU-like, DMA-like, and ISP-like initiators share a memory fabric.

Status:

```text
independent lab implemented and integrated into portfolio evidence harness
```

It observes:

- mixed traffic interference
- bandwidth partition
- latency-sensitive vs throughput-oriented flow
- fabric contention
- starvation risk
- simple QoS / bandwidth cap policy

Primary docs:

- [`docs/modeling_levels/at/project_at6_heterogeneous_soc_fabric.md`](../modeling_levels/at/project_at6_heterogeneous_soc_fabric.md)

This is not Apple Silicon simulation. It is an Apple-like heterogeneous SoC problem type.

### Project U: Integrate AT-6 into Evidence Harness

Project U is implemented: AT-6 is integrated into the portfolio evidence harness with clear PASS markers, result artifact checks, summary case coverage checks, and claim-boundary validation.

### Project AT-7: GPU-like Throughput Engine and Memory Saturation Lab

Project AT-7 builds a GPU-like throughput traffic generator focused on memory saturation and latency hiding.

Status:

```text
independent lab implemented and integrated into portfolio evidence harness
```

It observes:

- occupancy-like outstanding request depth
- memory bandwidth saturation
- latency hiding
- throughput knee point
- request burstiness
- bandwidth wall

This is not NVIDIA GPU simulation. It is an NVIDIA-like throughput problem type.

Primary docs:

- [`docs/modeling_levels/at/project_at7_gpu_like_throughput_saturation.md`](../modeling_levels/at/project_at7_gpu_like_throughput_saturation.md)

### Project V: Integrate AT-7 into Evidence Harness

Project V is implemented: AT-7 is integrated into the portfolio evidence harness with reproducible output checks, expected case coverage checks, key summary schema checks, and explicit unsupported-claim validation.

### Project AT-8: AMBA-inspired NoC QoS and Coherency Boundary Lab

Project AT-8 builds an AMBA-inspired NoC / interconnect-level synthetic lab.

Status:

```text
independent lab implemented and integrated into portfolio evidence harness
```

It observes:

- QoS classes
- route contention
- coherency boundary effect
- read/write interference
- ordering pressure
- protocol-inspired but not protocol-compliant behavior

This is not an Arm CHI / AXI / ACE compliance model.

Primary docs:

- [`docs/modeling_levels/at/project_at8_amba_noc_qos_coherency_boundary.md`](../modeling_levels/at/project_at8_amba_noc_qos_coherency_boundary.md)

### Project W: Integrate AT-8 into Evidence Harness

Project W is implemented: AT-8 is integrated into the portfolio evidence harness with repeatable checks for `summary.csv`, `comparison.md`, expected case coverage, key summary schema fields, and claim-boundary language.

### Project X: Apple / NVIDIA / Arm Industry Evidence Release Pack

Status:

```text
implemented release-pack layer over AT-6 / AT-7 / AT-8 evidence
```

Project X organizes the Stage 2 evidence into an industry-inspired release pack:

- `docs/industry_mapping/industry_evidence_release_pack.md`
- `docs/industry_mapping/apple_silicon_inspired_mapping.md`
- `docs/industry_mapping/nvidia_gpu_inspired_mapping.md`
- `docs/industry_mapping/arm_amba_inspired_mapping.md`
- `docs/generated/industry_evidence_matrix.md`
- `tools/generate_industry_evidence_matrix.py`

It does not add a simulation model, does not modify AT-6 / AT-7 / AT-8 core
simulation behavior, does not modify their `summary.csv` schema, and does not
change portfolio validation p0.5 behavior. It maps existing evidence to
Apple-like, NVIDIA-like, and Arm-like problem families while keeping explicit
unsupported-claim boundaries.

### Project Y: Workload-to-Bottleneck Classifier

Status:

```text
implemented workload-to-bottleneck classifier
```

Project Y adds a lightweight deterministic architecture decision tool over
sample workload symptoms:

- `tools/classify_workload_bottleneck.py`
- `examples/workloads/sample_workload_symptoms.csv`
- `docs/metrics_and_diagnosis/workload_bottleneck_classifier.md`
- `docs/generated/workload_bottleneck_classification.md`

It maps workload symptom rows to:

- `shared_fabric_pressure` -> AT-6 -> Apple-like heterogeneous SoC shared fabric pressure
- `throughput_bandwidth_wall` -> AT-7 -> NVIDIA-like throughput engine bandwidth wall
- `noc_qos_coherency_boundary` -> AT-8 -> Arm-like AMBA-inspired NoC QoS and coherency-boundary pressure
- `mixed_or_uncertain` -> needs more evidence

It is a bounded rule-based classifier and architecture reasoning tool. It does
not add a SystemC simulation model, does not modify AT-6 / AT-7 / AT-8 core
simulation behavior, does not modify their `summary.csv` schema, and does not
change portfolio validation p0.5 behavior.

### Project Z: Architecture Recommendation Engine

Status:

```text
implemented architecture recommendation engine
```

Project Z adds a lightweight deterministic recommendation layer over Project Y:

- `tools/generate_architecture_recommendations.py`
- `docs/metrics_and_diagnosis/architecture_recommendation_engine.md`
- `docs/generated/architecture_recommendations.md`

It maps Project Y bottleneck families to bounded recommendation families:

- `shared_fabric_pressure` -> `fabric_mitigation`
- `throughput_bandwidth_wall` -> `bandwidth_wall_mitigation`
- `noc_qos_coherency_boundary` -> `noc_qos_boundary_mitigation`
- `mixed_or_uncertain` -> `mixed_evidence_required`

It is a bounded rule-based recommendation engine and architecture reasoning
layer. It does not add a SystemC simulation model, does not modify AT-6 / AT-7 /
AT-8 core simulation behavior, does not modify their `summary.csv` schema, does
not change portfolio validation p0.5 behavior, and does not claim automatic
hardware optimization or production signoff.

### Project AA: Scenario Decision Benchmark

Status:

```text
implemented scenario decision benchmark
```

Project AA adds a lightweight deterministic scenario decision benchmark over
Project Z:

- `tools/run_scenario_decision_benchmark.py`
- `examples/scenarios/sample_architecture_scenarios.csv`
- `docs/metrics_and_diagnosis/scenario_decision_benchmark.md`
- `docs/generated/scenario_decision_benchmark.md`

It maps scenario rows to bounded decision families:

- `shared_fabric_pressure` -> `fabric_decision`
- `throughput_bandwidth_wall` -> `bandwidth_wall_decision`
- `noc_qos_coherency_boundary` -> `noc_qos_boundary_decision`
- `mixed_or_uncertain` -> `mixed_decision`

It is a bounded rule-based scenario decision benchmark and architecture
reasoning layer. It does not add a SystemC simulation model, does not modify
AT-6 / AT-7 / AT-8 core simulation behavior, does not modify their
`summary.csv` schema, does not change portfolio validation p0.5 behavior, and
does not claim automatic hardware optimization, real design-space exploration,
silicon validation, or production signoff.

### Project AB: Architecture Decision Memo Generator

Status:

```text
implemented architecture decision memo generator
```

Project AB adds a lightweight deterministic architecture decision memo generator
over Project AA:

- `tools/generate_architecture_decision_memos.py`
- `examples/decision_memos/sample_decision_memo_requests.csv`
- `docs/metrics_and_diagnosis/architecture_decision_memo_generator.md`
- `docs/generated/architecture_decision_memos.md`

It maps Project AA scenario decisions to bounded architecture review memo types:

- `fabric_memo`
- `bandwidth_wall_memo`
- `noc_qos_boundary_memo`
- `mixed_evidence_memo`

It is a bounded rule-based architecture reasoning layer. It does not add a
SystemC simulation model, does not modify AT-6 / AT-7 / AT-8 core simulation
behavior, does not modify their `summary.csv` schema, does not change portfolio
validation p0.5 behavior, and does not claim automatic hardware optimization,
real design-space exploration, silicon validation, or production signoff.

## Apple-like Direction

The Apple-like direction is heterogeneous SoC shared memory fabric / unified memory pressure.

This is a problem type, not Apple Silicon simulation.

## NVIDIA-like Direction

The NVIDIA-like direction is GPU-like throughput engine / occupancy vs memory bandwidth.

This is a problem type, not NVIDIA GPU simulation.

## Arm-like interconnect problem type

This direction is AMBA-inspired NoC QoS / coherency boundary.

This is protocol-inspired exploration, not CHI / AXI / ACE compliance.

## Recommended Next Project

Project AB is now implemented as the architecture decision memo generator over
Project AA scenario decisions. Planned next work should remain small,
validation-oriented, and clearly separate from implemented classifier,
recommendation, scenario decision, memo generation, release-pack, and p0.5
portfolio harness artifacts.

Do not describe AT-9 or later projects as implemented until their models,
generated artifacts, and claim-boundary evidence exist.
