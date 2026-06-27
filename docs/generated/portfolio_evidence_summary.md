# Portfolio Evidence Summary

由可复现 demo 输出生成。

- schema_version: `p0.5`
- claim_boundary: `PASS`
- stage1_projects: `AT-1,AT-2,AT-3,AT-4,AT-5,K,L`
- stage2_projects: `AT-6,AT-7,AT-8`
- projects: `AT-1,AT-2,AT-3,AT-4,AT-5,K,L,AT-6,AT-7,AT-8`
- portfolio_pass: `Portfolio Evidence Pack PASS`
- portfolio_claim_boundary: `claim_boundary=PASS`
- portfolio_schema_version: `schema_version=p0.5`

## 1. Validation Scope

- Stage 1 projects: AT-1, AT-2, AT-3, AT-4, AT-5, K, L
- Stage 2 projects: AT-6, AT-7, AT-8
- Project K/L: LT bottleneck and recommendation
- Project AT-1: four-phase transaction timing
- Project AT-2: multi-initiator arbitration and contention
- Project AT-3: QoS-like sensitivity and SLA violation analysis
- Project AT-4: cache-like shared-resource and MSHR pressure analysis
- Project AT-5: memory-system backpressure and QoS collapse analysis
- Project AT-6: heterogeneous SoC shared-memory fabric pressure analysis
- Project AT-7: GPU-like throughput engine and memory saturation analysis
- Project AT-8: AMBA-inspired NoC QoS and coherency-boundary analysis

## 2. Project K: LT Bottleneck Summary

Source: `examples/lt/results/project_k_workload_bottleneck/project_k_workload_bottleneck_summary.csv`

| workload | pattern_class | avg_latency_ns | p95_latency_ns | throughput_txn_per_us | bank_conflict_proxy | primary_bottleneck | claim_boundary | phase_count | total_requests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| streaming | core_baseline | 36.000 | 60.000 | 12.585 | 0.000 | service_latency_bound | trend-level synthetic trace over Project E simplified banked memory model; not GPU, silicon, PMU/perf/Nsight, AXI/CHI, GEMM, Transformer, FlashAttention, or LLM inference evidence | 1 | 96 |
| stride | core_stressor | 142.000 | 228.000 | 55.046 | 0.979 | queueing_bound | trend-level synthetic trace over Project E simplified banked memory model; not GPU, silicon, PMU/perf/Nsight, AXI/CHI, GEMM, Transformer, FlashAttention, or LLM inference evidence | 1 | 96 |
| hot_bank | core_stressor | 695.515 | 958.000 | 16.667 | 0.970 | queueing_bound | trend-level synthetic trace over Project E simplified banked memory model; not GPU, silicon, PMU/perf/Nsight, AXI/CHI, GEMM, Transformer, FlashAttention, or LLM inference evidence | 1 | 96 |
| tiled_gemm_like | optional_synthetic_pattern | 163.000 | 266.000 | 86.957 | 0.896 | queueing_bound | trend-level synthetic trace over Project E simplified banked memory model; not GPU, silicon, PMU/perf/Nsight, AXI/CHI, GEMM, Transformer, FlashAttention, or LLM inference evidence | 4 | 48 |
| attention_like_blocked | optional_synthetic_pattern | 209.250 | 372.000 | 108.291 | 0.938 | queueing_bound | trend-level synthetic trace over Project E simplified banked memory model; not GPU, silicon, PMU/perf/Nsight, AXI/CHI, GEMM, Transformer, FlashAttention, or LLM inference evidence | 4 | 64 |

## 3. Project L: Recommendation Summary

Source: `examples/lt/results/project_l_memory_architecture_recommendation/project_l_recommendations.csv`

| workload | primary_bottleneck | confidence | recommended_action | recommendation_priority | evidence_summary | claim_boundary | pattern_class | bank_count_best | address_mapping_best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| streaming | service_latency_bound | high | reduce_target_service_latency | high | bank_conflict_proxy=0.000; bank_count_sensitivity_score=0.000; mapping_sensitivity_score=0.000; queue_delay_ratio=0.000; service_delay_ratio=1.000; best=4/cacheline_interleave; signals=locality:strong,queueing:low,service:high,bank_conflict:low | PASS | core_baseline | 4 | cacheline_interleave |
| stride | queueing_bound | high | increase_bank_parallelism | high | bank_conflict_proxy=0.979; bank_count_sensitivity_score=0.737; mapping_sensitivity_score=0.368; queue_delay_ratio=0.746; service_delay_ratio=0.254; best=8/word_interleave; signals=locality:mixed,queueing:high,service:low,bank_conflict:high | PASS | core_stressor | 8 | word_interleave |
| hot_bank | queueing_bound | high | change_address_mapping | high | bank_conflict_proxy=0.970; bank_count_sensitivity_score=0.000; mapping_sensitivity_score=0.633; queue_delay_ratio=0.914; service_delay_ratio=0.086; best=8/cacheline_interleave; signals=locality:weak,queueing:high,service:low,bank_conflict:high | PASS | core_stressor | 8 | cacheline_interleave |
| tiled_gemm_like | queueing_bound | high | reduce_queueing_pressure | medium | bank_conflict_proxy=0.896; bank_count_sensitivity_score=0.105; mapping_sensitivity_score=0.476; queue_delay_ratio=0.730; service_delay_ratio=0.270; best=8/word_interleave; signals=locality:strong,queueing:high,service:low,bank_conflict:high | PASS | optional_synthetic_pattern | 8 | word_interleave |
| attention_like_blocked | queueing_bound | high | increase_bank_parallelism | high | bank_conflict_proxy=0.938; bank_count_sensitivity_score=0.548; mapping_sensitivity_score=0.273; queue_delay_ratio=0.828; service_delay_ratio=0.172; best=8/word_interleave; signals=locality:strong,queueing:high,service:low,bank_conflict:high | PASS | optional_synthetic_pattern | 8 | word_interleave |

## 4. Project AT-1: Transaction Timing Summary

Source: `examples/at/results/project_at1_four_phase_memory_timing/project_at1_summary.csv`

| case_name | num_transactions | avg_request_accept_latency_ns | p95_request_accept_latency_ns | avg_target_service_latency_ns | avg_response_latency_ns | avg_initiator_blocked_ns | backpressure_events | claim_boundary | pattern |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sequential_moderate_gap | 8 | 1.000 | 1.000 | 8.000 | 1.000 | 0.000 | 0 | PASS | sequential |
| bursty_queue_pressure | 12 | 10.167 | 12.000 | 22.083 | 1.000 | 9.167 | 10 | PASS | bursty |
| hotspot_backpressure | 12 | 15.667 | 17.000 | 16.000 | 1.000 | 14.667 | 11 | PASS | hotspot |

## 5. Project AT-2: Arbitration / Contention Summary

Source: `examples/at/results/project_at2_multi_initiator_arbitration/project_at2_policy_summary.csv`

| case_name | policy | total_transactions | total_backpressure_events | aggregate_throughput_txn_per_us | max_p99_response_latency_ns | fairness_index | worst_initiator | claim_boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rr_balanced | round_robin | 60 | 57 | 110.701 | 447.000 | 1.000 | accel0 | PASS |
| fixed_priority_dma_pressure | fixed_priority | 72 | 70 | 83.141 | 820.000 | 0.824 | accel0 | PASS |
| weighted_priority_accel_favored | weighted_priority | 72 | 70 | 99.723 | 699.000 | 0.907 | dma0 | PASS |
| bursty_mixed_contention | weighted_priority | 60 | 59 | 66.593 | 886.000 | 0.926 | cpu0 | PASS |

## 6. Project AT-3: QoS / SLA Summary

Source: `examples/at/results/project_at3_qos_sensitivity_sla/project_at3_policy_sweep.csv`

| case_name | weight_vector | queue_depth | service_latency_ns | total_sla_violations | max_sla_violation_rate | max_p99_total_latency_ns | fairness_index | worst_initiator | claim_boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| balanced_qos_nominal | cpu=1,dma=1,accel=1 | 4 | 14.000 | 33 | 0.583 | 780.000 | 1.000 | accel0 | PASS |
| accel_favored_latency_protection | cpu=1,dma=1,accel=3 | 4 | 14.000 | 35 | 0.708 | 780.000 | 0.933 | cpu0 | PASS |
| dma_favored_bandwidth_pressure | cpu=1,dma=3,accel=1 | 4 | 16.000 | 35 | 0.750 | 878.000 | 0.927 | accel0 | PASS |
| cpu_favored_interactive | cpu=3,dma=1,accel=1 | 4 | 14.000 | 31 | 0.708 | 757.000 | 0.933 | accel0 | PASS |
| shallow_queue_backpressure | cpu=1,dma=1,accel=1 | 1 | 18.000 | 45 | 0.708 | 1129.000 | 1.000 | accel0 | PASS |
| slow_memory_stress | cpu=1,dma=1,accel=1 | 4 | 34.000 | 58 | 0.875 | 2010.000 | 1.000 | accel0 | PASS |

## 7. Project AT-3: Architecture Recommendations

Source: `examples/at/results/project_at3_qos_sensitivity_sla/project_at3_recommendations.csv`

| case_name | primary_bottleneck | recommended_action | recommendation_priority | evidence_summary | protected_initiator | worst_initiator | claim_boundary | max_sla_violation_rate | max_p99_total_latency_ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| balanced_qos_nominal | mixed_arbitration_queueing | no_single_dominant_action | medium | max_violation_rate=0.583; max_p99_ns=780.000; backpressure=68; fairness_index=1.000 | none | accel0 | PASS | 0.583 | 780.000 |
| accel_favored_latency_protection | latency_sensitive_accelerator_arbitration | protect_latency_sensitive_initiator | medium | max_violation_rate=0.708; max_p99_ns=780.000; backpressure=68; fairness_index=0.933 | accel0 | cpu0 | PASS | 0.708 | 780.000 |
| dma_favored_bandwidth_pressure | dma_burstiness_and_weight_bias | reduce_burstiness | medium | max_violation_rate=0.750; max_p99_ns=878.000; backpressure=68; fairness_index=0.927 | dma0 | accel0 | PASS | 0.750 | 878.000 |
| cpu_favored_interactive | interactive_cpu_tail_latency | protect_latency_sensitive_initiator | medium | max_violation_rate=0.708; max_p99_ns=757.000; backpressure=68; fairness_index=0.933 | cpu0 | accel0 | PASS | 0.708 | 757.000 |
| shallow_queue_backpressure | target_queue_depth | increase_queue_depth | high | max_violation_rate=0.708; max_p99_ns=1129.000; backpressure=71; fairness_index=1.000 | none | accel0 | PASS | 0.708 | 1129.000 |
| slow_memory_stress | target_service_latency | reduce_service_latency | high | max_violation_rate=0.875; max_p99_ns=2010.000; backpressure=68; fairness_index=1.000 | none | accel0 | PASS | 0.875 | 2010.000 |

## 8. Project AT-4: Cache-like Shared Resource and MSHR Pressure Lab

- Project AT-4 covers 7 cases and 3 initiators: `cpu0`, `dma0`, and `accel0`.
- It highlights locality / hit-miss trend, MSHR-like outstanding miss pressure, shared interference / pollution proxy, tail latency p95/p99, and diminishing return when memory service dominates.
- claim boundary: PASS means bounded AT-level architecture exploration only; it is not real cache coherence, a real L1-L2-L3 hierarchy, cycle accuracy, or silicon validation.

Source: `examples/at/results/project_at4_cache_mshr_pressure/project_at4_policy_sweep.csv`

| case_name | hit_rate | miss_rate | mshr_capacity | mshr_full_events | interference_score | pollution_proxy | p95_total_latency_ns | p99_total_latency_ns | claim_boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cpu_latency_sensitive_hotset | 0.630 | 0.370 | 4 | 2 | 0.120 | 0.129 | 42.172 | 44.843 | PASS |
| dma_streaming_pollution | 0.370 | 0.630 | 4 | 64 | 0.560 | 0.775 | 468.758 | 471.546 | PASS |
| accel_tiled_reuse | 0.583 | 0.417 | 4 | 12 | 0.220 | 0.227 | 50.315 | 56.097 | PASS |
| mixed_cpu_dma_accel_interference | 0.306 | 0.694 | 4 | 71 | 0.760 | 0.915 | 696.430 | 704.522 | PASS |
| low_mshr_capacity_pressure | 0.259 | 0.741 | 2 | 78 | 0.940 | 0.883 | 1678.277 | 1754.110 | PASS |
| high_mshr_diminishing_return | 0.324 | 0.676 | 8 | 64 | 0.680 | 0.815 | 370.286 | 377.603 | PASS |
| slow_memory_mshr_saturation | 0.361 | 0.639 | 8 | 61 | 0.740 | 0.715 | 891.200 | 964.215 | PASS |

## 9. Project AT-4: Architecture Recommendations

Source: `examples/at/results/project_at4_cache_mshr_pressure/project_at4_recommendations.csv`

| case_name | primary_bottleneck | recommended_action | recommendation_priority | evidence_summary | locality_signal | mshr_pressure_signal | interference_signal | pollution_signal | claim_boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cpu_latency_sensitive_hotset | low_pressure_hotset | no_single_dominant_action | low | dominant=low_pressure_hotset; p99=44.843ns; mshr_full_events=2; pollution=0.129 | 0.630 | 0.259 | 0.120 | 0.129 | PASS |
| dma_streaming_pollution | streaming_dma_pollution | throttle_streaming_dma | high | dominant=streaming_dma_pollution; p99=471.546ns; mshr_full_events=64; pollution=0.775 | 0.370 | 0.833 | 0.560 | 0.775 | PASS |
| accel_tiled_reuse | locality_sensitive_reuse | improve_locality_or_tiling | medium | dominant=locality_sensitive_reuse; p99=56.097ns; mshr_full_events=12; pollution=0.227 | 0.583 | 0.351 | 0.220 | 0.227 | PASS |
| mixed_cpu_dma_accel_interference | shared_resource_interference | partition_shared_resource | high | dominant=shared_resource_interference; p99=704.522ns; mshr_full_events=71; pollution=0.915 | 0.306 | 0.897 | 0.760 | 0.915 | PASS |
| low_mshr_capacity_pressure | mshr_pressure | increase_mshr_capacity | high | dominant=mshr_pressure; p99=1754.110ns; mshr_full_events=78; pollution=0.883 | 0.259 | 1.000 | 0.940 | 0.883 | PASS |
| high_mshr_diminishing_return | diminishing_mshr_return | no_single_dominant_action | medium | dominant=diminishing_mshr_return; p99=377.603ns; mshr_full_events=64; pollution=0.815 | 0.324 | 0.713 | 0.680 | 0.815 | PASS |
| slow_memory_mshr_saturation | memory_service_latency | reduce_memory_service_latency | high | dominant=memory_service_latency; p99=964.215ns; mshr_full_events=61; pollution=0.715 | 0.361 | 0.685 | 0.740 | 0.715 | PASS |

## 10. Project AT-5: Backpressure / QoS Collapse Summary

- Project AT-5 covers bounded queues and downstream saturation: `cpu_rt`, `dma_bulk`, and `accel_burst` contend for a shared downstream service under 5 synthetic QoS policies.
- It highlights backpressure propagation and QoS collapse: QoS alone can redistribute contention but cannot create downstream service capacity.
- PASS marker: `Project AT-5 Memory System Backpressure and QoS Collapse Lab PASS`; claim boundary remains bounded AT-level trend comparison only.

Source: `examples/at/results/project_at5_backpressure_qos_collapse/project_at5_policy_sweep.csv`

| case_name | policy | cpu_rt_p95_ns | cpu_rt_sla_violation_ratio | system_throughput_txn_per_us | service_utilization | queue_full_events | backpressure_stall_ns | collapse_score | claim_boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_balanced_rr | round_robin | 41.380 | 0.000 | 17.227 | 0.397 | 0 | 391.100 | 0.012 | PASS |
| baseline_balanced_rr | strict_priority | 26.080 | 0.000 | 17.225 | 0.397 | 0 | 1352.590 | 0.027 | PASS |
| baseline_balanced_rr | weighted_priority | 34.580 | 0.000 | 16.490 | 0.380 | 0 | 415.820 | 0.012 | PASS |
| baseline_balanced_rr | throttled_dma | 30.820 | 0.000 | 8.458 | 0.195 | 0 | 206.800 | 0.021 | PASS |
| baseline_balanced_rr | backpressure_aware | 30.659 | 0.000 | 13.139 | 0.299 | 0 | 315.150 | 0.015 | PASS |
| strict_priority_helps_cpu | round_robin | 499.144 | 0.056 | 31.701 | 0.832 | 78 | 26922.876 | 0.315 | PASS |
| strict_priority_helps_cpu | strict_priority | 489.520 | 0.028 | 31.696 | 0.832 | 76 | 26759.016 | 0.301 | PASS |
| strict_priority_helps_cpu | weighted_priority | 409.308 | 0.000 | 30.300 | 0.796 | 70 | 21196.496 | 0.251 | PASS |
| strict_priority_helps_cpu | throttled_dma | 57.168 | 0.000 | 26.035 | 0.684 | 0 | 1418.952 | 0.033 | PASS |
| strict_priority_helps_cpu | backpressure_aware | 56.385 | 0.000 | 24.984 | 0.647 | 0 | 1564.945 | 0.034 | PASS |
| strict_priority_starves_dma | round_robin | 310.400 | 0.000 | 35.801 | 0.657 | 63 | 12900.400 | 0.191 | PASS |
| strict_priority_starves_dma | strict_priority | 272.240 | 0.000 | 35.795 | 0.657 | 60 | 12839.760 | 0.184 | PASS |
| strict_priority_starves_dma | weighted_priority | 231.420 | 0.000 | 34.213 | 0.628 | 56 | 9848.100 | 0.175 | PASS |
| strict_priority_starves_dma | throttled_dma | 25.580 | 0.000 | 35.801 | 0.657 | 0 | 937.560 | 0.026 | PASS |
| strict_priority_starves_dma | backpressure_aware | 39.741 | 0.000 | 28.087 | 0.509 | 0 | 1122.735 | 0.039 | PASS |
| downstream_saturation_qos_collapse | round_robin | 15120.829 | 0.972 | 6.644 | 1.000 | 105 | 852466.826 | 0.806 | PASS |
| downstream_saturation_qos_collapse | strict_priority | 14812.257 | 0.944 | 6.644 | 1.000 | 105 | 849768.687 | 0.796 | PASS |
| downstream_saturation_qos_collapse | weighted_priority | 14812.257 | 0.972 | 6.644 | 1.000 | 105 | 849696.043 | 0.805 | PASS |
| downstream_saturation_qos_collapse | throttled_dma | 12189.400 | 0.972 | 6.644 | 1.000 | 105 | 838003.114 | 0.805 | PASS |
| downstream_saturation_qos_collapse | backpressure_aware | 11887.200 | 0.944 | 6.736 | 1.000 | 105 | 826704.538 | 0.796 | PASS |
| small_queue_backpressure | round_robin | 109.540 | 0.000 | 42.495 | 0.750 | 63 | 3779.940 | 0.187 | PASS |
| small_queue_backpressure | strict_priority | 92.380 | 0.000 | 42.495 | 0.750 | 58 | 4582.140 | 0.181 | PASS |
| small_queue_backpressure | weighted_priority | 92.380 | 0.000 | 41.549 | 0.733 | 55 | 3185.120 | 0.159 | PASS |
| small_queue_backpressure | throttled_dma | 91.180 | 0.000 | 17.155 | 0.303 | 39 | 2235.660 | 0.135 | PASS |
| small_queue_backpressure | backpressure_aware | 78.153 | 0.000 | 26.626 | 0.463 | 45 | 2425.690 | 0.134 | PASS |
| throttled_dma_recovers_sla | round_robin | 445.420 | 0.528 | 46.666 | 0.747 | 79 | 20607.480 | 0.424 | PASS |
| throttled_dma_recovers_sla | strict_priority | 429.420 | 0.528 | 46.656 | 0.747 | 79 | 21715.180 | 0.422 | PASS |
| throttled_dma_recovers_sla | weighted_priority | 405.440 | 0.500 | 44.641 | 0.714 | 76 | 18658.900 | 0.387 | PASS |
| throttled_dma_recovers_sla | throttled_dma | 123.640 | 0.000 | 46.666 | 0.747 | 44 | 5902.520 | 0.159 | PASS |
| throttled_dma_recovers_sla | backpressure_aware | 237.684 | 0.194 | 36.390 | 0.574 | 60 | 10065.648 | 0.251 | PASS |
| bursty_accel_tail_spike | round_robin | 799.520 | 0.583 | 46.160 | 0.998 | 101 | 52376.520 | 0.679 | PASS |
| bursty_accel_tail_spike | strict_priority | 782.880 | 0.556 | 46.160 | 0.998 | 101 | 52586.080 | 0.668 | PASS |
| bursty_accel_tail_spike | weighted_priority | 749.600 | 0.500 | 46.160 | 0.998 | 101 | 48542.240 | 0.650 | PASS |
| bursty_accel_tail_spike | throttled_dma | 583.200 | 0.083 | 23.843 | 0.516 | 74 | 25582.740 | 0.245 | PASS |
| bursty_accel_tail_spike | backpressure_aware | 553.386 | 0.111 | 36.981 | 0.787 | 89 | 29850.957 | 0.322 | PASS |

## 11. Project AT-5: Architecture Recommendations

- Project AT-5 recommendations separate QoS policy choices from capacity actions such as reducing memory service latency or increasing bounded queue capacity.

Source: `examples/at/results/project_at5_backpressure_qos_collapse/project_at5_recommendations.csv`

| case_name | primary_bottleneck | confidence | recommended_action | recommendation_priority | qos_policy_best | service_saturation_signal | backpressure_signal | sla_signal | claim_boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_balanced_rr | balanced_or_low_pressure | medium | no_single_dominant_action | low | round_robin | low | low | low | PASS |
| strict_priority_helps_cpu | latency_sensitive_qos_contention | high | use_strict_priority | medium | strict_priority | medium | high | low | PASS |
| strict_priority_starves_dma | strict_priority_starvation | high | use_weighted_priority | high | weighted_priority | low | high | low | PASS |
| downstream_saturation_qos_collapse | downstream_service_saturation | high | reduce_memory_service_latency | high | backpressure_aware | high | high | high | PASS |
| small_queue_backpressure | bounded_queue_backpressure | high | use_backpressure_aware_scheduling | high | backpressure_aware | medium | high | low | PASS |
| throttled_dma_recovers_sla | dma_bulk_induced_backpressure | high | throttle_dma_bulk | high | throttled_dma | low | high | low | PASS |
| bursty_accel_tail_spike | accel_burst_tail_spike | high | shape_accel_bursts | medium | throttled_dma | high | high | low | PASS |

## 12. Project AT-6: Heterogeneous SoC Shared Memory Fabric Summary

- Project AT-6 is the first Stage 2 lab in the portfolio evidence harness.
- It covers a bounded AT-level synthetic heterogeneous SoC problem type: CPU-like, NPU-like, DMA-like, and ISP-like traffic sharing one memory fabric.
- claim boundary: PASS means bounded AT-level synthetic architecture exploration only; it is not Apple Silicon simulation, real NoC behavior, cycle-accurate modeling, silicon validation, or production signoff.

Source: `examples/at/results/project_at6_heterogeneous_soc_fabric/summary.csv`

| case | total_transactions | p95_latency_ns | p99_latency_ns | fabric_queue_peak | starvation_events | cpu_p99_latency_ns | npu_throughput_txn_per_us | npu_bandwidth_share | dma_bandwidth_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_rr | 228 | 3727.750 | 3989.080 | 57 | 181 | 2200.440 | 6.371 | 34.783 | 42.391 |
| priority_latency | 228 | 5999.540 | 6357.320 | 46 | 103 | 76.100 | 6.371 | 34.783 | 42.391 |
| bandwidth_cap_npu | 226 | 10466.782 | 11420.691 | 50 | 163 | 89.813 | 3.386 | 29.213 | 45.506 |
| dma_stress | 252 | 10087.850 | 10529.850 | 124 | 231 | 5140.310 | 4.407 | 24.806 | 58.915 |
| mixed_stress | 300 | 16429.700 | 17103.600 | 171 | 277 | 115.425 | 4.416 | 34.743 | 48.338 |

## 13. Project AT-7: GPU-like Throughput Engine and Memory Saturation Summary

- Project name: Project AT-7, GPU-like Throughput Engine and Memory Saturation Lab.
- Result files: `examples/at/results/project_at7_gpu_like_throughput_saturation/summary.csv` and `examples/at/results/project_at7_gpu_like_throughput_saturation/comparison.md`.
- Cases: `low_occupancy`, `balanced_occupancy`, `high_occupancy`, `bandwidth_saturation`, `bursty_stress`, and `throttled_occupancy`.
- Key metrics: latency percentiles, throughput, effective bandwidth, memory utilization, queue delay, outstanding depth, stall ratio, hidden latency, exposed stall, saturation flag, and knee-point hint.
- Key observations: useful throughput improves from low to balanced occupancy, high pressure approaches the knee, bandwidth saturation mostly adds queue delay, burstiness raises tail risk, and throttling gives a bounded safer latency reference.
- claim boundary: PASS means bounded AT-level synthetic GPU-like throughput and memory saturation exploration only; it does not claim NVIDIA GPU simulation, real GPU behavior, CUDA execution modeling, real HBM-controller behavior, cycle-accurate modeling, silicon validation, or production signoff.
- schema_version=at7.0

Source: `examples/at/results/project_at7_gpu_like_throughput_saturation/summary.csv`

| case | num_lanes | requests_per_lane | total_requests | avg_latency_ns | p95_latency_ns | p99_latency_ns | throughput_req_per_us | effective_bandwidth_bytes_per_ns | memory_utilization_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| low_occupancy | 2 | 40 | 80 | 18.382 | 25.070 | 25.070 | 22.629 | 2.897 | 0.282 |
| balanced_occupancy | 4 | 64 | 256 | 55.015 | 97.240 | 98.680 | 55.573 | 7.113 | 0.692 |
| high_occupancy | 8 | 64 | 512 | 290.524 | 398.760 | 399.120 | 73.007 | 9.345 | 0.909 |
| bandwidth_saturation | 12 | 64 | 768 | 660.430 | 798.960 | 800.220 | 80.321 | 10.281 | 1.000 |
| bursty_stress | 8 | 64 | 512 | 424.988 | 511.980 | 512.700 | 80.330 | 10.282 | 1.000 |
| throttled_occupancy | 8 | 64 | 512 | 192.232 | 250.440 | 251.160 | 60.921 | 7.798 | 0.758 |

## 14. Project AT-8: AMBA-inspired NoC QoS and Coherency Boundary Summary

- Project name: Project AT-8, AMBA-inspired NoC QoS and Coherency Boundary Lab.
- Result files: `examples/at/results/project_at8_amba_noc_qos_coherency_boundary/summary.csv` and `examples/at/results/project_at8_amba_noc_qos_coherency_boundary/comparison.md`.
- Cases: `baseline_qos_rr`, `latency_qos_priority`, `bulk_dma_pressure`, `boundary_crossing_stress`, `route_hotspot`, and `mixed_qos_collapse`.
- Key metrics: latency percentiles, throughput, route queue peak, local/shared/boundary route utilization, route delay, ordering delay, boundary penalty, coherency-boundary events, read/write p95 latency, QoS-class p99 latency, starvation events, protection score, collapse score, and recommendation.
- Key observations: QoS priority protects latency_high traffic only within route-capacity bounds; bulk DMA pressure raises read/write tail latency; boundary crossing stress exposes ordering and serialization cost; route hotspots can dominate QoS intent; mixed pressure collapses into capacity or partitioning recommendations.
- claim boundary: PASS means bounded AT-level synthetic AMBA-inspired NoC QoS and coherency-boundary exploration only; it does not claim Arm CHI compliance, AXI compliance, ACE compliance, real AMBA protocol behavior, real NoC behavior, real cache coherency, cycle-accurate modeling, silicon validation, or production signoff.
- schema_version=at8.0

Source: `examples/at/results/project_at8_amba_noc_qos_coherency_boundary/summary.csv`

| case | total_transactions | avg_latency_ns | p95_latency_ns | p99_latency_ns | throughput_txn_per_us | route_queue_peak | shared_route_utilization | boundary_route_utilization | collapse_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_qos_rr | 160 | 31.363 | 60.360 | 161.941 | 31.064 | 3 | 0.522 | 0.149 | 42.764 |
| latency_qos_priority | 160 | 31.237 | 60.360 | 151.882 | 31.064 | 3 | 0.522 | 0.149 | 40.957 |
| bulk_dma_pressure | 248 | 2973.813 | 10444.803 | 11285.121 | 15.294 | 90 | 0.997 | 0.095 | 100.000 |
| boundary_crossing_stress | 204 | 1291.063 | 5725.532 | 7349.794 | 17.949 | 43 | 0.201 | 1.000 | 100.000 |
| route_hotspot | 230 | 8156.094 | 17396.064 | 17863.105 | 10.132 | 163 | 1.000 | 0.000 | 100.000 |
| mixed_qos_collapse | 310 | 11494.328 | 28471.440 | 30426.455 | 8.822 | 140 | 0.584 | 1.000 | 100.000 |

## 15. What This Evidence Pack Supports

- workload bottleneck reasoning
- evidence-driven memory architecture recommendation
- transaction phase timing analysis
- arbitration, fairness, and tail-latency tradeoff discussion
- QoS-like sensitivity discussion
- SLA violation and recommendation discussion
- locality, hit/miss trend, MSHR-like pressure, and shared-resource interference discussion
- bounded queues, downstream saturation, backpressure propagation, and QoS collapse discussion
- heterogeneous SoC shared-memory fabric pressure and bandwidth partitioning discussion
- GPU-like throughput pressure, latency hiding approximation, and bandwidth saturation discussion
- AMBA-inspired NoC QoS, route contention, coherency-boundary pressure, and bounded recommendation discussion
- reproducible portfolio validation

## 16. Claim Boundary

This evidence pack supports bounded architecture modeling discussion only. It does not claim Arm CHI compliance, AXI compliance, ACE compliance, real AMBA protocol behavior, real NoC behavior, real cache coherency, cycle-accurate modeling, Apple Silicon simulation, NVIDIA GPU simulation, real GPU behavior, CUDA execution modeling, real HBM-controller behavior, silicon validation, production signoff, real DRAM timing, or real workload performance.
