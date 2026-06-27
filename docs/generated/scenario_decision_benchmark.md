# Scenario Decision Benchmark

schema_version=scenario-r1.0
input_file=examples/scenarios/sample_architecture_scenarios.csv

## Purpose

This generated report is the Project AA scenario decision benchmark. It consumes architecture scenario rows, candidate actions, sensitivity constraints, and evidence mappings, then produces bounded scenario-level decision outputs.

It is a bounded rule-based scenario decision benchmark and architecture reasoning layer. It is not an optimizer, not machine learning, not a profiler, not a real hardware design-space exploration tool, and not a signoff artifact.

## Source Input

- Architecture scenarios: `examples/scenarios/sample_architecture_scenarios.csv`
- Scenario rows are deterministic sample cases for portfolio and interview discussion.

## Scenario Decision Table

| scenario | workload | bottleneck_family | recommendation_family | decision_family | recommended_action | evidence_project | industry_mapping | confidence | risk_if_wrong | what_to_measure_next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mobile_ai_camera_shared_fabric | mobile_camera_ai_pipeline | shared_fabric_pressure | fabric_mitigation | fabric_decision | protect_latency_initiator | AT-6 | Apple-like | high | latency-sensitive traffic can still lose tail behavior if bulk pressure or starvation is the real dominant symptom | per-initiator p95/p99 latency, bandwidth share, fabric queue peak, and starvation events |
| transformer_decode_bandwidth_wall | transformer_decode_tokens | throughput_bandwidth_wall | bandwidth_wall_mitigation | bandwidth_wall_decision | throttle_outstanding_after_knee | AT-7 | NVIDIA-like | high | too little throttling leaves queue buildup; too much throttling cuts useful throughput | throughput knee point, memory utilization, queue peak, average outstanding depth, and tail latency |
| gpu_bursty_kernel_tail_latency | bursty_gpu_like_kernel | throughput_bandwidth_wall | bandwidth_wall_mitigation | bandwidth_wall_decision | shape_bursty_traffic | AT-7 | NVIDIA-like | high | burst shaping can reduce tails but may underfill the bandwidth path | throughput knee point, memory utilization, queue peak, average outstanding depth, and tail latency |
| dma_write_interference_boundary | dma_write_read_tail_mix | noc_qos_coherency_boundary | noc_qos_boundary_mitigation | noc_qos_boundary_decision | protect_read_latency_from_bulk_write | AT-8 | Arm-like | high | read protection can help tails but may not fix boundary serialization | boundary crossings, ordering events, read/write interference, QoS class pressure, route utilization, and starvation events |
| coherent_noncoherent_boundary_mix | coherent_noncoherent_mix | noc_qos_coherency_boundary | noc_qos_boundary_mitigation | noc_qos_boundary_decision | reduce_boundary_crossing | AT-8 | Arm-like | high | boundary reduction can help ordering pressure but may not solve route hotspots | boundary crossings, ordering events, read/write interference, QoS class pressure, route utilization, and starvation events |
| mixed_soc_decision_review | mixed_soc_review | mixed_or_uncertain | mixed_evidence_required | mixed_decision | run_targeted_evidence_checks | AT-6+AT-7+AT-8 | Mixed | medium | without targeted checks, a single-family action can overfit mixed symptoms | phase-split workload symptoms plus targeted AT-6, AT-7, and AT-8 evidence checks before choosing one action |

## Action Scoring Notes

| scenario | recommended_action | secondary_recommendation | scoring_notes |
| --- | --- | --- | --- |
| mobile_ai_camera_shared_fabric | protect_latency_initiator | none | protect_latency_initiator=12 (protect_latency_initiator+12: high latency sensitivity favors protecting latency-sensitive initiators) \| throttle_bulk_dma=0 (no rule matched) \| increase_fabric_capacity=0 (no rule matched) \| schedule_high_pressure_initiators=0 (no rule matched) |
| transformer_decode_bandwidth_wall | throttle_outstanding_after_knee | bandwidth_aware_batching | throttle_outstanding_after_knee=11 (throttle_outstanding_after_knee+11: throughput memory-wall signal favors throttling after the knee point) \| bandwidth_aware_batching=3 (bandwidth_aware_batching+3: bandwidth-aware batching is a secondary mitigation when present) \| increase_outstanding_depth=0 (no rule matched) |
| gpu_bursty_kernel_tail_latency | shape_bursty_traffic | throttle_outstanding_after_knee | shape_bursty_traffic=18 (shape_bursty_traffic+14: bursty or tail-latency wording favors burst shaping; shape_bursty_traffic+4: high latency sensitivity avoids blindly increasing outstanding depth) \| throttle_outstanding_after_knee=3 (throttle_outstanding_after_knee+3: high latency sensitivity favors controlled outstanding pressure) \| bandwidth_aware_batching=3 (bandwidth_aware_batching+3: bandwidth-aware batching is a secondary mitigation when present) |
| dma_write_interference_boundary | protect_read_latency_from_bulk_write | none | protect_read_latency_from_bulk_write=14 (protect_read_latency_from_bulk_write+14: write-heavy read-tail interference favors read-latency protection) \| reduce_boundary_crossing=0 (no rule matched) \| qos_partition=0 (no rule matched) |
| coherent_noncoherent_boundary_mix | reduce_boundary_crossing | none | reduce_boundary_crossing=12 (reduce_boundary_crossing+12: high ordering sensitivity favors reducing boundary crossings) \| protect_read_latency_from_bulk_write=0 (no rule matched) \| route_isolation=0 (no rule matched) |
| mixed_soc_decision_review | run_targeted_evidence_checks | collect_more_workload_symptoms | run_targeted_evidence_checks=12 (run_targeted_evidence_checks+12: mixed evidence should start with targeted AT-6/AT-7/AT-8 checks) \| collect_more_workload_symptoms=8 (collect_more_workload_symptoms+8: mixed evidence benefits from more workload symptoms) \| split_scenario_by_bottleneck_family=7 (split_scenario_by_bottleneck_family+7: mixed evidence benefits from splitting by bottleneck family) \| avoid_single_family_overfit=6 (avoid_single_family_overfit+6: mixed evidence should avoid overfitting one family) |

## Scenario Decision Rule Summary

| bottleneck_family | decision_family | deterministic rule summary |
| --- | --- | --- |
| shared_fabric_pressure | fabric_decision | High latency sensitivity favors `protect_latency_initiator`; high fairness sensitivity favors `throttle_bulk_dma` or `fairness_guard`; high implementation risk favors `schedule_high_pressure_initiators`. |
| throughput_bandwidth_wall | bandwidth_wall_decision | Throughput memory-wall signals favor `throttle_outstanding_after_knee`; bursty or tail-latency signals favor `shape_bursty_traffic`; high latency sensitivity penalizes blind `increase_outstanding_depth`. |
| noc_qos_coherency_boundary | noc_qos_boundary_decision | High ordering sensitivity favors `reduce_boundary_crossing`; write-heavy read-tail interference favors `protect_read_latency_from_bulk_write`; fairness and hotspot signals favor `qos_partition` or `route_isolation`. |
| mixed_or_uncertain | mixed_decision | Mixed evidence favors `run_targeted_evidence_checks`, then more symptoms, phase splitting, and avoiding single-family overfit. |

## Evidence Mapping

| decision_family | evidence_project | industry_mapping | interpretation |
| --- | --- | --- | --- |
| fabric_decision | AT-6 | Apple-like | Shared-fabric pressure decisions should be backed by latency, bandwidth-share, queue, and starvation evidence. |
| bandwidth_wall_decision | AT-7 | NVIDIA-like | Bandwidth-wall decisions should be backed by throughput knee, outstanding-depth, queue, utilization, and tail-latency evidence. |
| noc_qos_boundary_decision | AT-8 | Arm-like | NoC/QoS boundary decisions should be backed by route pressure, boundary crossing, ordering, QoS, read/write interference, and starvation evidence. |
| mixed_decision | AT-6+AT-7+AT-8 | Mixed | Mixed decisions should run targeted evidence checks before choosing a single architecture action. |

## Unsupported Claims

- Not supported: Apple Silicon simulation.
- Not supported: NVIDIA GPU simulation.
- Not supported: Arm CHI compliance.
- Not supported: AXI compliance.
- Not supported: ACE compliance.
- Not supported: real hardware profiling.
- Not supported: automatic hardware optimization.
- Not supported: real design-space exploration.
- Not supported: real NoC behavior.
- Not supported: real cache coherency.
- Not supported: cycle-accurate modeling.
- Not supported: silicon validation.
- Not supported: production signoff.

## Claim Boundary

Current:

- Project AA is implemented as a lightweight deterministic scenario decision benchmark with `schema_version=scenario-r1.0`.

Supported:

- It supports bounded rule-based scenario decision benchmarking, scenario-level decision discussion, evidence-backed decision review, and portfolio / interview architecture reasoning.

Not Supported:

- It does not claim Apple Silicon simulation, NVIDIA GPU simulation, Arm CHI compliance, AXI compliance, ACE compliance, real hardware profiling, automatic hardware optimization, real design-space exploration, real NoC behavior, real cache coherency, cycle-accurate modeling, silicon validation, or production signoff.

Future Work:

- Future versions may add more deterministic scenario rows or scoring rules only when new evidence artifacts justify them.

claim_boundary=PASS
