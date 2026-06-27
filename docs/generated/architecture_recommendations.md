# Architecture Recommendations

schema_version=recommendation-r1.0
input_file=examples/workloads/sample_workload_symptoms.csv
classification_file=docs/generated/workload_bottleneck_classification.md

## Purpose

This generated report is the Project Z architecture recommendation layer over Project Y bottleneck families. It is a bounded rule-based recommendation engine and architecture reasoning layer. It is not an optimizer, not machine learning, not a profiler, and not a hardware design synthesis tool.

## Source Inputs

- Workload symptoms: `examples/workloads/sample_workload_symptoms.csv`
- Project Y classification: `docs/generated/workload_bottleneck_classification.md`
- Project Z consumes the same workload symptom source and uses Project Y family definitions.

## Workload Recommendation Table

| workload | predicted bottleneck family | recommendation family | evidence project | industry-inspired mapping | primary recommendation | secondary recommendation | risk if ignored | confidence | what to measure next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mobile_ai_camera_pipeline | shared_fabric_pressure | fabric_mitigation | AT-6 | Apple-like heterogeneous SoC shared fabric pressure | protect latency-sensitive initiators with bounded priority or bandwidth partitioning | cap bulk/DMA-like traffic; schedule high-pressure initiators; increase shared fabric capacity only if queue pressure persists | tail latency, starvation risk, and unfair bandwidth share can grow under mixed initiator pressure | high | fabric queue peak, per-initiator p95/p99 latency, bandwidth share, and starvation events |
| transformer_decode_memory_wall | throughput_bandwidth_wall | bandwidth_wall_mitigation | AT-7 | NVIDIA-like throughput engine bandwidth wall | stop increasing outstanding depth after the knee point and tune occupancy/outstanding limits | shape burstiness, prefer bandwidth-aware batching, and use a throttled profile when tail latency is a risk | extra outstanding pressure can become queue delay and p99 tail growth without useful throughput gain | high | memory utilization ratio, queue peak, average outstanding depth, stall ratio, and throughput |
| dma_bulk_write_interference | noc_qos_coherency_boundary | noc_qos_boundary_mitigation | AT-8 | Arm-like AMBA-inspired NoC QoS and coherency-boundary pressure | isolate boundary-crossing traffic and reduce ordering-sensitive serialization | protect read latency from write-heavy bulk traffic, partition QoS/VC-like resources, and avoid route hotspot mapping | route and boundary queues can dominate tail latency, while QoS priority collapses under hotspot pressure | high | boundary crossing rate, ordering events, read/write interference, QoS class pressure, and starvation events |
| coherent_noncoherent_boundary_mix | noc_qos_coherency_boundary | noc_qos_boundary_mitigation | AT-8 | Arm-like AMBA-inspired NoC QoS and coherency-boundary pressure | isolate boundary-crossing traffic and reduce ordering-sensitive serialization | protect read latency from write-heavy bulk traffic, partition QoS/VC-like resources, and avoid route hotspot mapping | route and boundary queues can dominate tail latency, while QoS priority collapses under hotspot pressure | high | boundary crossing rate, ordering events, read/write interference, QoS class pressure, and starvation events |
| gpu_like_bursty_kernel | throughput_bandwidth_wall | bandwidth_wall_mitigation | AT-7 | NVIDIA-like throughput engine bandwidth wall | stop increasing outstanding depth after the knee point and tune occupancy/outstanding limits | shape burstiness, prefer bandwidth-aware batching, and use a throttled profile when tail latency is a risk | extra outstanding pressure can become queue delay and p99 tail growth without useful throughput gain | high | memory utilization ratio, queue peak, average outstanding depth, stall ratio, and throughput |
| mixed_soc_stress | mixed_or_uncertain | mixed_evidence_required | AT-6/AT-7/AT-8 | Mixed Apple-like / NVIDIA-like / Arm-like evidence family | do not overfit one bottleneck family; run targeted AT-6/AT-7/AT-8 evidence checks | collect additional workload symptoms and separate shared-fabric, bandwidth-wall, and boundary/QoS phases | a single mitigation can improve one symptom while hiding or worsening another bottleneck family | low | phase-split symptoms plus targeted AT-6, AT-7, and AT-8 metrics before choosing an architecture action |

## Recommendation Rule Summary

| predicted bottleneck family | recommendation family | deterministic rule |
| --- | --- | --- |
| shared_fabric_pressure | fabric_mitigation | Map shared-fabric symptoms to latency-flow protection, bandwidth caps, scheduling separation, and starvation checks. |
| throughput_bandwidth_wall | bandwidth_wall_mitigation | Map bandwidth-wall symptoms to outstanding-depth control, burst shaping, and knee-point validation. |
| noc_qos_coherency_boundary | noc_qos_boundary_mitigation | Map boundary/QoS symptoms to traffic isolation, serialization reduction, QoS partitioning, and hotspot avoidance. |
| mixed_or_uncertain | mixed_evidence_required | Map mixed symptoms to additional evidence collection before choosing a primary mitigation. |

## Evidence Mapping

| recommendation family | evidence project | industry-inspired mapping | evidence-backed action |
| --- | --- | --- | --- |
| fabric_mitigation | AT-6 | Apple-like heterogeneous SoC shared fabric pressure | protect latency-sensitive initiators with bounded priority or bandwidth partitioning |
| bandwidth_wall_mitigation | AT-7 | NVIDIA-like throughput engine bandwidth wall | stop increasing outstanding depth after the knee point and tune occupancy/outstanding limits |
| noc_qos_boundary_mitigation | AT-8 | Arm-like AMBA-inspired NoC QoS and coherency-boundary pressure | isolate boundary-crossing traffic and reduce ordering-sensitive serialization |
| mixed_evidence_required | AT-6/AT-7/AT-8 | Mixed Apple-like / NVIDIA-like / Arm-like evidence family | do not overfit one bottleneck family; run targeted AT-6/AT-7/AT-8 evidence checks |

## Validation / Confidence Notes

- High confidence means Project Y family evidence is dominant or the expected family agrees with the predicted family.
- Medium confidence means the symptoms are mixed but still support a dominant recommendation family.
- Low confidence means Project Y returned `mixed_or_uncertain` or the top symptoms conflict.

| workload | confidence | evidence notes |
| --- | --- | --- |
| mobile_ai_camera_pipeline | high | high concurrent initiators; high shared queue; elevated p99 latency; memory path is not fully saturated; concurrent_initiators=5; memory_utilization_ratio=0.68; queue_peak=22; p99_latency_ns=190; throughput_req_per_us=0.95; avg_outstanding=12; boundary_crossing_rate=0.15; ordering_events=1; read_write_interference_score=0.28; qos_class_pressure=0.25; starvation_events=1 |
| transformer_decode_memory_wall | high | memory utilization near saturation; high request throughput; high outstanding depth; moderate burstiness; concurrent_initiators=2; memory_utilization_ratio=0.96; queue_peak=34; p99_latency_ns=260; throughput_req_per_us=1.75; avg_outstanding=36; boundary_crossing_rate=0.18; ordering_events=1; read_write_interference_score=0.22; qos_class_pressure=0.20; starvation_events=0 |
| dma_bulk_write_interference | high | high boundary crossing rate; high ordering events; high read/write interference; high QoS class pressure; concurrent_initiators=3; memory_utilization_ratio=0.74; queue_peak=28; p99_latency_ns=220; throughput_req_per_us=0.82; avg_outstanding=10; boundary_crossing_rate=0.72; ordering_events=5; read_write_interference_score=0.88; qos_class_pressure=0.78; starvation_events=3 |
| coherent_noncoherent_boundary_mix | high | high boundary crossing rate; high ordering events; high read/write interference; moderate QoS class pressure; concurrent_initiators=4; memory_utilization_ratio=0.70; queue_peak=20; p99_latency_ns=240; throughput_req_per_us=0.78; avg_outstanding=14; boundary_crossing_rate=0.85; ordering_events=7; read_write_interference_score=0.70; qos_class_pressure=0.63; starvation_events=2 |
| gpu_like_bursty_kernel | high | memory utilization near saturation; high request throughput; high outstanding depth; bursty injection; concurrent_initiators=2; memory_utilization_ratio=0.91; queue_peak=30; p99_latency_ns=280; throughput_req_per_us=1.60; avg_outstanding=28; boundary_crossing_rate=0.22; ordering_events=1; read_write_interference_score=0.25; qos_class_pressure=0.25; starvation_events=0 |
| mixed_soc_stress | low | shared, throughput, and boundary symptoms are all high; concurrent_initiators=5; memory_utilization_ratio=0.90; queue_peak=32; p99_latency_ns=300; throughput_req_per_us=1.45; avg_outstanding=30; boundary_crossing_rate=0.68; ordering_events=5; read_write_interference_score=0.78; qos_class_pressure=0.72; starvation_events=3 |

## Unsupported Claims

- Not supported: Apple Silicon simulation.
- Not supported: NVIDIA GPU simulation.
- Not supported: Arm CHI compliance.
- Not supported: AXI compliance.
- Not supported: ACE compliance.
- Not supported: real hardware profiling.
- Not supported: automatic hardware optimization.
- Not supported: real NoC behavior.
- Not supported: real cache coherency.
- Not supported: cycle-accurate modeling.
- Not supported: silicon validation.
- Not supported: production signoff.

## Claim Boundary

Current:

- Project Z is implemented as a lightweight deterministic architecture recommendation engine over Project Y workload families.

Supported:

- It supports bounded architecture reasoning, recommendation families, evidence-backed action discussion, and portfolio / interview explanation.

Not Supported:

- It does not claim Apple Silicon simulation, NVIDIA GPU simulation, Arm CHI compliance, AXI compliance, ACE compliance, real hardware profiling, automatic hardware optimization, real NoC behavior, real cache coherency, cycle-accurate modeling, silicon validation, or production signoff.

Future Work:

- Future versions may add more deterministic rules or more workload symptoms while preserving the same claim boundary.

claim_boundary=PASS
