# Industry Evidence Matrix

schema_version=industry-r1.0

## Purpose

This matrix is the Project X industry-inspired mapping layer over existing AT-6, AT-7, and AT-8 evidence. It organizes already generated `summary.csv` and `comparison.md` artifacts for portfolio, interview, and release-pack discussion.

## Source Projects

- AT-6: Heterogeneous SoC Shared Memory Fabric Lab
- AT-7: GPU-like Throughput Engine and Memory Saturation Lab
- AT-8: AMBA-inspired NoC QoS and Coherency Boundary Lab

## Evidence Matrix

| project | industry-inspired mapping | architecture problem type | input evidence | key metrics | observed bottleneck | recommendation style | unsupported claims |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AT-6 | Apple-like heterogeneous SoC shared fabric pressure | heterogeneous initiators sharing one bounded memory fabric under latency-sensitive and throughput-oriented pressure | `examples/at/results/project_at6_heterogeneous_soc_fabric/summary.csv`<br>`examples/at/results/project_at6_heterogeneous_soc_fabric/comparison.md` | p99_latency_ns, fabric_queue_peak, starvation_events, cpu_p99_latency_ns, npu_bandwidth_share, dma_bandwidth_share, isp_p99_latency_ns | mixed_stress: p99_latency_ns=17103.600; fabric_queue_peak=171; starvation_events=277; dma_bandwidth_share=48.338 | compare latency priority and bandwidth cap policies before claiming latency-flow protection | Not supported: Apple Silicon simulation; Not supported: real unified memory controller; Not supported: real NoC behavior; Not supported: cycle-accurate modeling; Not supported: silicon validation; Not supported: production signoff |
| AT-7 | NVIDIA-like throughput engine bandwidth wall | throughput engine outstanding-depth sensitivity, latency hiding approximation, bandwidth saturation, and queue buildup | `examples/at/results/project_at7_gpu_like_throughput_saturation/summary.csv`<br>`examples/at/results/project_at7_gpu_like_throughput_saturation/comparison.md` | throughput_req_per_us, effective_bandwidth_bytes_per_ns, memory_utilization_ratio, queue_peak, avg_outstanding, stall_ratio, saturation_flag, knee_point_hint | bandwidth_saturation: throughput_req_per_us=80.321; memory_utilization_ratio=1.000; p99_latency_ns=800.220; queue_peak=63; stall_ratio=0.821; knee_point_hint=past_knee_bandwidth_wall | stop increasing outstanding depth after the knee; throttle injection when p95/p99 latency or queue peak is the risk | Not supported: NVIDIA GPU simulation; Not supported: CUDA execution modeling; Not supported: SM scheduler behavior; Not supported: real HBM controller; Not supported: Tensor Core behavior; Not supported: TMEM behavior; Not supported: cycle-accurate modeling; Not supported: silicon validation; Not supported: production signoff |
| AT-8 | Arm-like AMBA-inspired NoC QoS and coherency-boundary pressure | QoS class protection, route contention, boundary crossing, ordering delay, and read/write interference | `examples/at/results/project_at8_amba_noc_qos_coherency_boundary/summary.csv`<br>`examples/at/results/project_at8_amba_noc_qos_coherency_boundary/comparison.md` | p99_latency_ns, route_queue_peak, shared_route_utilization, boundary_route_utilization, ordering_delay_ns, coherency_boundary_events, starvation_events, collapse_score | mixed_qos_collapse: p99_latency_ns=30426.455; route_queue_peak=140; boundary_route_utilization=1.000; ordering_delay_ns=4578.000; coherency_boundary_events=104; starvation_events=297; collapse_score=100.000 | switch from priority tuning to route capacity, partitioning, or traffic shaping when collapse score is high | Not supported: Arm CHI compliance; Not supported: AXI compliance; Not supported: ACE compliance; Not supported: real AMBA protocol behavior; Not supported: real NoC behavior; Not supported: real cache coherency; Not supported: cycle-accurate modeling; Not supported: silicon validation; Not supported: production signoff |

## Industry-Inspired Mapping

- Apple-like: AT-6 maps heterogeneous initiators, shared fabric pressure, bandwidth cap behavior, latency-sensitive flow protection, and starvation risk.
- NVIDIA-like: AT-7 maps throughput-engine pressure, outstanding-depth sensitivity, bandwidth saturation, latency-hiding approximation, burstiness, queue buildup, and the memory wall.
- Arm-like: AT-8 maps AMBA-inspired QoS classes, route contention, coherency-boundary pressure, ordering delay, read/write interference, starvation signal, and collapse risk.

## Claim Boundary

This industry evidence matrix is an industry-inspired mapping layer over bounded synthetic architecture explorations. It does not claim any unsupported item listed below.

claim_boundary=PASS

## Unsupported Claims

- Not supported: ACE compliance
- Not supported: AXI compliance
- Not supported: Apple Silicon simulation
- Not supported: Arm CHI compliance
- Not supported: CUDA execution modeling
- Not supported: NVIDIA GPU simulation
- Not supported: SM scheduler behavior
- Not supported: TMEM behavior
- Not supported: Tensor Core behavior
- Not supported: cycle-accurate modeling
- Not supported: production signoff
- Not supported: real AMBA protocol behavior
- Not supported: real HBM controller
- Not supported: real NoC behavior
- Not supported: real cache coherency
- Not supported: real unified memory controller
- Not supported: silicon validation

## Validation

Regenerate this file with:

```bash
python3 tools/generate_industry_evidence_matrix.py --strict
```

Expected PASS marker:

```text
Industry Evidence Matrix PASS
projects=AT-6,AT-7,AT-8
industry_mappings=Apple-like,NVIDIA-like,Arm-like
claim_boundary=PASS
schema_version=industry-r1.0
```
