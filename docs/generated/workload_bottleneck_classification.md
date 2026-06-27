# Workload Bottleneck Classification

schema_version=classifier-r1.0
input_file=examples/workloads/sample_workload_symptoms.csv

## Purpose

This generated report classifies sample workload symptoms into bounded architecture bottleneck families. The classifier is deterministic and rule-based; it is not machine learning and not a hardware profiler.

## Workload Classification Table

| workload | description | predicted_family | expected_family | confidence | scores | evidence mapping | recommendation | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mobile_ai_camera_pipeline | CPU NPU ISP DMA-like concurrent traffic | shared_fabric_pressure | shared_fabric_pressure | high | shared=8; throughput=2; noc=2 | AT-6 -> Apple-like heterogeneous SoC shared fabric pressure | inspect AT-6-style fabric contention, bandwidth partitioning, latency-flow protection, and starvation risk | high concurrent initiators; high shared queue; elevated p99 latency; memory path is not fully saturated |
| transformer_decode_memory_wall | high memory utilization and outstanding bandwidth saturation | throughput_bandwidth_wall | throughput_bandwidth_wall | high | shared=4; throughput=10; noc=1 | AT-7 -> NVIDIA-like throughput engine bandwidth wall | inspect AT-7-style memory utilization, outstanding-depth knee, queue buildup, and bandwidth-wall behavior | memory utilization near saturation; high request throughput; high outstanding depth; moderate burstiness |
| dma_bulk_write_interference | write-heavy DMA interference with ordering and read tail pressure | noc_qos_coherency_boundary | noc_qos_coherency_boundary | high | shared=6; throughput=0; noc=12 | AT-8 -> Arm-like AMBA-inspired NoC QoS and coherency-boundary pressure | inspect AT-8-style QoS class pressure, route contention, boundary crossings, ordering delay, and read/write interference | high boundary crossing rate; high ordering events; high read/write interference; high QoS class pressure |
| coherent_noncoherent_boundary_mix | boundary crossing and ordering events high | noc_qos_coherency_boundary | noc_qos_coherency_boundary | high | shared=7; throughput=0; noc=11 | AT-8 -> Arm-like AMBA-inspired NoC QoS and coherency-boundary pressure | inspect AT-8-style QoS class pressure, route contention, boundary crossings, ordering delay, and read/write interference | high boundary crossing rate; high ordering events; high read/write interference; moderate QoS class pressure |
| gpu_like_bursty_kernel | bursty high-throughput memory pressure | throughput_bandwidth_wall | throughput_bandwidth_wall | high | shared=4; throughput=11; noc=1 | AT-7 -> NVIDIA-like throughput engine bandwidth wall | inspect AT-7-style memory utilization, outstanding-depth knee, queue buildup, and bandwidth-wall behavior | memory utilization near saturation; high request throughput; high outstanding depth; bursty injection |
| mixed_soc_stress | shared fabric bandwidth wall and boundary pressure mixed | mixed_or_uncertain | mixed_or_uncertain | low | shared=6; throughput=9; noc=12 | needs more evidence -> split workload phases or run targeted AT-6/AT-7/AT-8 checks | collect more evidence, split the workload into phases, and compare AT-6 / AT-7 / AT-8 symptom families separately | shared, throughput, and boundary symptoms are all high |

## Classification Rules Summary

- `shared_fabric_pressure`: high concurrent initiators, shared queue pressure, elevated p99 latency, and no dominant boundary / ordering symptom.
- `throughput_bandwidth_wall`: memory utilization near saturation, high request throughput, high outstanding depth, burstiness, and queue buildup.
- `noc_qos_coherency_boundary`: high boundary crossing rate, ordering events, read/write interference, QoS class pressure, starvation, and route / boundary queue symptoms.
- `mixed_or_uncertain`: low evidence, close top scores, or simultaneous shared-fabric, throughput-wall, and boundary-pressure symptoms.

## Evidence Mapping

| family | evidence family | interpretation |
| --- | --- | --- |
| shared_fabric_pressure | AT-6 -> Apple-like | heterogeneous SoC shared fabric pressure |
| throughput_bandwidth_wall | AT-7 -> NVIDIA-like | throughput engine bandwidth wall |
| noc_qos_coherency_boundary | AT-8 -> Arm-like | AMBA-inspired NoC QoS and coherency-boundary pressure |
| mixed_or_uncertain | needs more evidence | split the workload or collect targeted symptoms before choosing a family |

## Recommendations

- Treat the predicted family as an architecture discussion starting point, not a final design decision.
- For shared fabric pressure, compare AT-6-style bandwidth caps, latency-sensitive flow protection, and starvation risk.
- For throughput bandwidth walls, compare AT-7-style outstanding-depth pressure, memory utilization, burstiness, and queue buildup.
- For NoC / QoS / coherency-boundary pressure, compare AT-8-style route pressure, boundary crossings, ordering delay, and read/write interference.
- For mixed or uncertain outputs, split the workload into phases and collect more targeted evidence before claiming a bottleneck family.

## Unsupported Claims

- Not supported: Apple Silicon simulation.
- Not supported: NVIDIA GPU simulation.
- Not supported: Arm CHI compliance.
- Not supported: AXI compliance.
- Not supported: ACE compliance.
- Not supported: real hardware profiling.
- Not supported: real NoC behavior.
- Not supported: real cache coherency.
- Not supported: cycle-accurate modeling.
- Not supported: silicon validation.
- Not supported: production signoff.

## Claim Boundary

Current:

- This report is generated by a bounded rule-based architecture reasoning tool over sample workload symptoms.

Supported:

- It supports portfolio and interview discussion about mapping workload symptoms to evidence families.

Not Supported:

- It does not replace real profiling, vendor simulators, protocol-compliance validation, cycle-accurate modeling, silicon validation, or production signoff.

Future Work:

- Future versions may add more symptom fields or compare multiple workload phases, while remaining deterministic and claim-bounded.

claim_boundary=PASS
