# Architecture Decision Memos

schema_version=memo-r1.0

## Purpose

This generated report is Project AB: Architecture Decision Memo Generator. It turns scenario-level decisions into bounded architecture review memos for portfolio and interview storytelling.

## Source Inputs

- Memo requests: `examples/decision_memos/sample_decision_memo_requests.csv`
- Project AA scenario report: `docs/generated/scenario_decision_benchmark.md`
- Project Z recommendation report: `docs/generated/architecture_recommendations.md`
- Project Y classification report: `docs/generated/workload_bottleneck_classification.md`

## Memo Index

| memo_id | scenario | workload | memo_type | audience | decision | evidence_project | industry_mapping | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| memo_mobile_ai_camera_shared_fabric | mobile_ai_camera_shared_fabric | mobile_ai_camera_pipeline | fabric_memo | architecture_review | protect_latency_initiator | AT-6 | Apple-like | high |
| memo_transformer_decode_bandwidth_wall | transformer_decode_bandwidth_wall | transformer_decode_memory_wall | bandwidth_wall_memo | architecture_review | throttle_outstanding_after_knee | AT-7 | NVIDIA-like | high |
| memo_gpu_bursty_kernel_tail_latency | gpu_bursty_kernel_tail_latency | gpu_like_bursty_kernel | bandwidth_wall_memo | performance_review | shape_bursty_traffic | AT-7 | NVIDIA-like | high |
| memo_dma_write_interference_boundary | dma_write_interference_boundary | dma_bulk_write_interference | noc_qos_boundary_memo | architecture_review | protect_read_latency_from_bulk_write | AT-8 | Arm-like | high |
| memo_coherent_noncoherent_boundary_mix | coherent_noncoherent_boundary_mix | coherent_noncoherent_boundary_mix | noc_qos_boundary_memo | architecture_review | reduce_boundary_crossing | AT-8 | Arm-like | high |
| memo_mixed_soc_decision_review | mixed_soc_decision_review | mixed_soc_stress | mixed_evidence_memo | architecture_review | run_targeted_evidence_checks | AT-6+AT-7+AT-8 | Mixed | medium |

## Memo Type Rules

| memo_type | default evidence project | default mapping | deterministic rule intent |
| --- | --- | --- | --- |
| fabric_memo | AT-6 | Apple-like | Decision defaults to protect_latency_initiator; measure queue peak, initiator-level latency, starvation, fabric utilization, and traffic mix. |
| bandwidth_wall_memo | AT-7 | NVIDIA-like | Decision defaults to throttle_outstanding_after_knee; measure throughput saturation knee, outstanding depth, queue peak, p99 latency, and burstiness. |
| noc_qos_boundary_memo | AT-8 | Arm-like | Decision defaults to protect_read_latency_from_bulk_write; measure boundary crossing rate, ordering events, read/write interference, QoS pressure, and starvation events. |
| mixed_evidence_memo | AT-6+AT-7+AT-8 | Mixed | Decision defaults to run_targeted_evidence_checks; measure split the scenario into fabric, bandwidth-wall, and boundary/QoS symptoms; rerun targeted reasoning stack. |

## Complete Memos

## Memo: memo_mobile_ai_camera_shared_fabric

- Memo ID: `memo_mobile_ai_camera_shared_fabric`
- Scenario: `mobile_ai_camera_shared_fabric`
- Workload: `mobile_ai_camera_pipeline`
- Audience: `architecture_review`
- Memo Type: `fabric_memo`
- Decision Family: `fabric_decision`

### Executive Summary

For `mobile_ai_camera_shared_fabric`, the bounded architecture decision is `protect_latency_initiator`. The memo turns Project AA scenario output into an architecture review memo while preserving the Project X/Y/Z/AA evidence chain and claim boundary.

### Problem

Protect latency-sensitive camera/AI pipeline traffic under shared-fabric pressure. Shared-fabric pressure can expose latency-sensitive initiator traffic to queue growth, unfair bandwidth share, and starvation risk.

### Decision

- Decision: `protect_latency_initiator`
- Evidence project: `AT-6`
- Industry-inspired mapping: `Apple-like`

### Evidence Chain

- Required chain: AT-6/AT-7/AT-8 evidence -> Project X industry mapping -> Project Y bottleneck classification -> Project Z recommendation -> Project AA scenario decision -> Project AB memo.
- Selected chain: AT-6 evidence -> Project X industry mapping (Apple-like) -> Project Y bottleneck classification (shared_fabric_pressure) -> Project Z recommendation (fabric_mitigation) -> Project AA scenario decision (protect_latency_initiator) -> Project AB memo (fabric_memo).
- Project Y classification: `mobile_ai_camera_pipeline` -> `shared_fabric_pressure` (high concurrent initiators; high shared queue; elevated p99 latency; memory path is not fully saturated).
- Project Z recommendation: `fabric_mitigation`; primary evidence-backed action: protect latency-sensitive initiators with bounded priority or bandwidth partitioning.
- Project AA scenario decision: `mobile_ai_camera_shared_fabric` -> `protect_latency_initiator` with `high` confidence.

### Primary Recommendation

- `protect_latency_initiator`

### Secondary Considerations

- Use bounded priority, bandwidth partitioning, bulk-traffic caps, and starvation checks before arguing for more fabric capacity.
- Project Z secondary recommendation: cap bulk/DMA-like traffic; schedule high-pressure initiators; increase shared fabric capacity only if queue pressure persists.

### Risk if Ignored

- shared-fabric pressure can turn concurrent initiator traffic into queue growth and latency outliers.

### Risk if Wrong

- latency-sensitive traffic can still lose tail behavior if bulk pressure or starvation is the real dominant symptom.

### What to Measure Next

- queue peak, initiator-level latency, starvation, fabric utilization, and traffic mix.
- Project AA next measurement hook: per-initiator p95/p99 latency, bandwidth share, fabric queue peak, and starvation events.

### Confidence

- high. Classification confidence is `high` and recommendation confidence is `high`.

### Claim Boundary

- This memo is a bounded rule-based architecture decision memo. It supports architecture review storytelling and evidence-chain communication, not automatic hardware design or signoff.

## Memo: memo_transformer_decode_bandwidth_wall

- Memo ID: `memo_transformer_decode_bandwidth_wall`
- Scenario: `transformer_decode_bandwidth_wall`
- Workload: `transformer_decode_memory_wall`
- Audience: `architecture_review`
- Memo Type: `bandwidth_wall_memo`
- Decision Family: `bandwidth_wall_decision`

### Executive Summary

For `transformer_decode_bandwidth_wall`, the bounded architecture decision is `throttle_outstanding_after_knee`. The memo turns Project AA scenario output into an architecture review memo while preserving the Project X/Y/Z/AA evidence chain and claim boundary.

### Problem

Avoid adding outstanding depth past the saturation knee. A throughput-oriented workload can hit a bandwidth knee where additional outstanding pressure grows queues faster than useful throughput.

### Decision

- Decision: `throttle_outstanding_after_knee`
- Evidence project: `AT-7`
- Industry-inspired mapping: `NVIDIA-like`

### Evidence Chain

- Required chain: AT-6/AT-7/AT-8 evidence -> Project X industry mapping -> Project Y bottleneck classification -> Project Z recommendation -> Project AA scenario decision -> Project AB memo.
- Selected chain: AT-7 evidence -> Project X industry mapping (NVIDIA-like) -> Project Y bottleneck classification (throughput_bandwidth_wall) -> Project Z recommendation (bandwidth_wall_mitigation) -> Project AA scenario decision (throttle_outstanding_after_knee) -> Project AB memo (bandwidth_wall_memo).
- Project Y classification: `transformer_decode_memory_wall` -> `throughput_bandwidth_wall` (memory utilization near saturation; high request throughput; high outstanding depth; moderate burstiness).
- Project Z recommendation: `bandwidth_wall_mitigation`; primary evidence-backed action: stop increasing outstanding depth after the knee point and tune occupancy/outstanding limits.
- Project AA scenario decision: `transformer_decode_bandwidth_wall` -> `throttle_outstanding_after_knee` with `high` confidence.

### Primary Recommendation

- `throttle_outstanding_after_knee`

### Secondary Considerations

- Shape bursty traffic, identify the saturation knee, and compare throughput gain against p99 latency and queue growth.
- Project Z secondary recommendation: shape burstiness, prefer bandwidth-aware batching, and use a throttled profile when tail latency is a risk.

### Risk if Ignored

- increasing pressure past the bandwidth knee may grow queues without proportional throughput gains.

### Risk if Wrong

- too little throttling leaves queue buildup; too much throttling cuts useful throughput.

### What to Measure Next

- throughput saturation knee, outstanding depth, queue peak, p99 latency, and burstiness.
- Project AA next measurement hook: throughput knee point, memory utilization, queue peak, average outstanding depth, and tail latency.

### Confidence

- high. Classification confidence is `high` and recommendation confidence is `high`.

### Claim Boundary

- This memo is a bounded rule-based architecture decision memo. It supports architecture review storytelling and evidence-chain communication, not automatic hardware design or signoff.

## Memo: memo_gpu_bursty_kernel_tail_latency

- Memo ID: `memo_gpu_bursty_kernel_tail_latency`
- Scenario: `gpu_bursty_kernel_tail_latency`
- Workload: `gpu_like_bursty_kernel`
- Audience: `performance_review`
- Memo Type: `bandwidth_wall_memo`
- Decision Family: `bandwidth_wall_decision`

### Executive Summary

For `gpu_bursty_kernel_tail_latency`, the bounded architecture decision is `shape_bursty_traffic`. The memo turns Project AA scenario output into an architecture review memo while preserving the Project X/Y/Z/AA evidence chain and claim boundary.

### Problem

Reduce burst-driven queue peaks and tail latency without claiming real GPU behavior. A throughput-oriented workload can hit a bandwidth knee where additional outstanding pressure grows queues faster than useful throughput.

### Decision

- Decision: `shape_bursty_traffic`
- Evidence project: `AT-7`
- Industry-inspired mapping: `NVIDIA-like`

### Evidence Chain

- Required chain: AT-6/AT-7/AT-8 evidence -> Project X industry mapping -> Project Y bottleneck classification -> Project Z recommendation -> Project AA scenario decision -> Project AB memo.
- Selected chain: AT-7 evidence -> Project X industry mapping (NVIDIA-like) -> Project Y bottleneck classification (throughput_bandwidth_wall) -> Project Z recommendation (bandwidth_wall_mitigation) -> Project AA scenario decision (shape_bursty_traffic) -> Project AB memo (bandwidth_wall_memo).
- Project Y classification: `gpu_like_bursty_kernel` -> `throughput_bandwidth_wall` (memory utilization near saturation; high request throughput; high outstanding depth; bursty injection).
- Project Z recommendation: `bandwidth_wall_mitigation`; primary evidence-backed action: stop increasing outstanding depth after the knee point and tune occupancy/outstanding limits.
- Project AA scenario decision: `gpu_bursty_kernel_tail_latency` -> `shape_bursty_traffic` with `high` confidence.

### Primary Recommendation

- `shape_bursty_traffic`

### Secondary Considerations

- Shape bursty traffic, identify the saturation knee, and compare throughput gain against p99 latency and queue growth.
- Project Z secondary recommendation: shape burstiness, prefer bandwidth-aware batching, and use a throttled profile when tail latency is a risk.

### Risk if Ignored

- increasing pressure past the bandwidth knee may grow queues without proportional throughput gains.

### Risk if Wrong

- burst shaping can reduce tails but may underfill the bandwidth path.

### What to Measure Next

- throughput saturation knee, outstanding depth, queue peak, p99 latency, and burstiness.
- Project AA next measurement hook: throughput knee point, memory utilization, queue peak, average outstanding depth, and tail latency.

### Confidence

- high. Classification confidence is `high` and recommendation confidence is `high`.

### Claim Boundary

- This memo is a bounded rule-based architecture decision memo. It supports architecture review storytelling and evidence-chain communication, not automatic hardware design or signoff.

## Memo: memo_dma_write_interference_boundary

- Memo ID: `memo_dma_write_interference_boundary`
- Scenario: `dma_write_interference_boundary`
- Workload: `dma_bulk_write_interference`
- Audience: `architecture_review`
- Memo Type: `noc_qos_boundary_memo`
- Decision Family: `noc_qos_boundary_decision`

### Executive Summary

For `dma_write_interference_boundary`, the bounded architecture decision is `protect_read_latency_from_bulk_write`. The memo turns Project AA scenario output into an architecture review memo while preserving the Project X/Y/Z/AA evidence chain and claim boundary.

### Problem

Protect read latency from write-heavy boundary/interference pressure. Boundary crossing, ordering-sensitive traffic, and write-heavy interference can create tail latency even when average throughput looks acceptable.

### Decision

- Decision: `protect_read_latency_from_bulk_write`
- Evidence project: `AT-8`
- Industry-inspired mapping: `Arm-like`

### Evidence Chain

- Required chain: AT-6/AT-7/AT-8 evidence -> Project X industry mapping -> Project Y bottleneck classification -> Project Z recommendation -> Project AA scenario decision -> Project AB memo.
- Selected chain: AT-8 evidence -> Project X industry mapping (Arm-like) -> Project Y bottleneck classification (noc_qos_coherency_boundary) -> Project Z recommendation (noc_qos_boundary_mitigation) -> Project AA scenario decision (protect_read_latency_from_bulk_write) -> Project AB memo (noc_qos_boundary_memo).
- Project Y classification: `dma_bulk_write_interference` -> `noc_qos_coherency_boundary` (high boundary crossing rate; high ordering events; high read/write interference; high QoS class pressure).
- Project Z recommendation: `noc_qos_boundary_mitigation`; primary evidence-backed action: isolate boundary-crossing traffic and reduce ordering-sensitive serialization.
- Project AA scenario decision: `dma_write_interference_boundary` -> `protect_read_latency_from_bulk_write` with `high` confidence.

### Primary Recommendation

- `protect_read_latency_from_bulk_write`

### Secondary Considerations

- Reduce boundary crossings, protect read latency from bulk writes, partition QoS-like pressure, and watch starvation events.
- Project Z secondary recommendation: protect read latency from write-heavy bulk traffic, partition QoS/VC-like resources, and avoid route hotspot mapping.

### Risk if Ignored

- boundary-crossing, ordering-sensitive, or write-heavy pressure can create tail latency and starvation symptoms.

### Risk if Wrong

- read protection can help tails but may not fix boundary serialization.

### What to Measure Next

- boundary crossing rate, ordering events, read/write interference, QoS pressure, and starvation events.
- Project AA next measurement hook: boundary crossings, ordering events, read/write interference, QoS class pressure, route utilization, and starvation events.

### Confidence

- high. Classification confidence is `high` and recommendation confidence is `high`.

### Claim Boundary

- This memo is a bounded rule-based architecture decision memo. It supports architecture review storytelling and evidence-chain communication, not automatic hardware design or signoff.

## Memo: memo_coherent_noncoherent_boundary_mix

- Memo ID: `memo_coherent_noncoherent_boundary_mix`
- Scenario: `coherent_noncoherent_boundary_mix`
- Workload: `coherent_noncoherent_boundary_mix`
- Audience: `architecture_review`
- Memo Type: `noc_qos_boundary_memo`
- Decision Family: `noc_qos_boundary_decision`

### Executive Summary

For `coherent_noncoherent_boundary_mix`, the bounded architecture decision is `reduce_boundary_crossing`. The memo turns Project AA scenario output into an architecture review memo while preserving the Project X/Y/Z/AA evidence chain and claim boundary.

### Problem

Reduce boundary-crossing and ordering-sensitive serialization pressure. Boundary crossing, ordering-sensitive traffic, and write-heavy interference can create tail latency even when average throughput looks acceptable.

### Decision

- Decision: `reduce_boundary_crossing`
- Evidence project: `AT-8`
- Industry-inspired mapping: `Arm-like`

### Evidence Chain

- Required chain: AT-6/AT-7/AT-8 evidence -> Project X industry mapping -> Project Y bottleneck classification -> Project Z recommendation -> Project AA scenario decision -> Project AB memo.
- Selected chain: AT-8 evidence -> Project X industry mapping (Arm-like) -> Project Y bottleneck classification (noc_qos_coherency_boundary) -> Project Z recommendation (noc_qos_boundary_mitigation) -> Project AA scenario decision (reduce_boundary_crossing) -> Project AB memo (noc_qos_boundary_memo).
- Project Y classification: `coherent_noncoherent_boundary_mix` -> `noc_qos_coherency_boundary` (high boundary crossing rate; high ordering events; high read/write interference; moderate QoS class pressure).
- Project Z recommendation: `noc_qos_boundary_mitigation`; primary evidence-backed action: isolate boundary-crossing traffic and reduce ordering-sensitive serialization.
- Project AA scenario decision: `coherent_noncoherent_boundary_mix` -> `reduce_boundary_crossing` with `high` confidence.

### Primary Recommendation

- `reduce_boundary_crossing`

### Secondary Considerations

- Reduce boundary crossings, protect read latency from bulk writes, partition QoS-like pressure, and watch starvation events.
- Project Z secondary recommendation: protect read latency from write-heavy bulk traffic, partition QoS/VC-like resources, and avoid route hotspot mapping.

### Risk if Ignored

- boundary-crossing, ordering-sensitive, or write-heavy pressure can create tail latency and starvation symptoms.

### Risk if Wrong

- boundary reduction can help ordering pressure but may not solve route hotspots.

### What to Measure Next

- boundary crossing rate, ordering events, read/write interference, QoS pressure, and starvation events.
- Project AA next measurement hook: boundary crossings, ordering events, read/write interference, QoS class pressure, route utilization, and starvation events.

### Confidence

- high. Classification confidence is `high` and recommendation confidence is `high`.

### Claim Boundary

- This memo is a bounded rule-based architecture decision memo. It supports architecture review storytelling and evidence-chain communication, not automatic hardware design or signoff.

## Memo: memo_mixed_soc_decision_review

- Memo ID: `memo_mixed_soc_decision_review`
- Scenario: `mixed_soc_decision_review`
- Workload: `mixed_soc_stress`
- Audience: `architecture_review`
- Memo Type: `mixed_evidence_memo`
- Decision Family: `mixed_decision`

### Executive Summary

For `mixed_soc_decision_review`, the bounded architecture decision is `run_targeted_evidence_checks`. The memo turns Project AA scenario output into an architecture review memo while preserving the Project X/Y/Z/AA evidence chain and claim boundary.

### Problem

Avoid overfitting one bottleneck family when evidence is mixed. Mixed symptoms make it risky to choose one mitigation family before separating fabric, bandwidth-wall, and boundary/QoS evidence.

### Decision

- Decision: `run_targeted_evidence_checks`
- Evidence project: `AT-6+AT-7+AT-8`
- Industry-inspired mapping: `Mixed`

### Evidence Chain

- Required chain: AT-6/AT-7/AT-8 evidence -> Project X industry mapping -> Project Y bottleneck classification -> Project Z recommendation -> Project AA scenario decision -> Project AB memo.
- Selected chain: AT-6+AT-7+AT-8 evidence -> Project X industry mapping (Mixed) -> Project Y bottleneck classification (mixed_or_uncertain) -> Project Z recommendation (mixed_evidence_required) -> Project AA scenario decision (run_targeted_evidence_checks) -> Project AB memo (mixed_evidence_memo).
- Project Y classification: `mixed_soc_stress` -> `mixed_or_uncertain` (shared, throughput, and boundary symptoms are all high).
- Project Z recommendation: `mixed_evidence_required`; primary evidence-backed action: do not overfit one bottleneck family; run targeted AT-6/AT-7/AT-8 evidence checks.
- Project AA scenario decision: `mixed_soc_decision_review` -> `run_targeted_evidence_checks` with `medium` confidence.

### Primary Recommendation

- `run_targeted_evidence_checks`

### Secondary Considerations

- Split the scenario into targeted evidence checks, then choose the narrowest action that survives the evidence review.
- Project Z secondary recommendation: collect additional workload symptoms and separate shared-fabric, bandwidth-wall, and boundary/QoS phases.

### Risk if Ignored

- overfitting one bottleneck family can lead to wrong mitigation and hidden regressions.

### Risk if Wrong

- without targeted checks, a single-family action can overfit mixed symptoms.

### What to Measure Next

- split the scenario into fabric, bandwidth-wall, and boundary/QoS symptoms; rerun targeted reasoning stack.
- Project AA next measurement hook: phase-split workload symptoms plus targeted AT-6, AT-7, and AT-8 evidence checks before choosing one action.

### Confidence

- medium. Classification confidence is `low` and recommendation confidence is `low`.

### Claim Boundary

- This memo is a bounded rule-based architecture decision memo. It supports architecture review storytelling and evidence-chain communication, not automatic hardware design or signoff.

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

- Project AB is implemented as a lightweight deterministic architecture decision memo generator with `schema_version=memo-r1.0`.

Supported:

- It supports bounded rule-based architecture reasoning, architecture review memo writing, evidence-chain explanation, portfolio discussion, and interview storytelling.

Not Supported:

- It does not claim Apple Silicon simulation, NVIDIA GPU simulation, Arm CHI compliance, AXI compliance, ACE compliance, real hardware profiling, automatic hardware optimization, real design-space exploration, real NoC behavior, real cache coherency, cycle-accurate modeling, silicon validation, or production signoff.

Future Work:

- Future versions may add more deterministic memo templates or request fields only when the upstream evidence chain supports them.

claim_boundary=PASS
