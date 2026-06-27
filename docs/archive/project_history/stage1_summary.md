# Stage 1 Summary

## Purpose

Stage 1 establishes a bounded, reproducible SystemC/TLM architecture performance modeling portfolio for memory-system bottleneck isolation. It intentionally avoids cycle accuracy and real protocol claims, focusing instead on fast trend comparison, bottleneck attribution, and architecture recommendation logic.

The purpose of this repository is to make early memory-system architecture questions reviewable through synthetic workloads, traces, metrics, sweeps, reports, and a repeatable evidence harness. Its value is not cycle accuracy. Its value is:

- trend comparison
- bottleneck isolation
- latency attribution
- architecture recommendation logic

## Version Line

- v0.10: AT-4 independent cache-like MSHR pressure lab
- v0.11: AT-4 integrated into portfolio evidence harness
- v0.12: AT-5 independent backpressure QoS collapse lab
- v0.13: AT-5 integrated into portfolio evidence harness

## Evidence Chain

```text
LT -> AT timing -> arbitration -> QoS -> cache-like MSHR pressure -> backpressure QoS collapse -> portfolio validation
```

- LT: workload pattern and memory access characterization.
- AT timing: transaction-level latency structure.
- arbitration: multi-initiator contention.
- QoS: priority policy and SLA sensitivity.
- cache-like MSHR pressure: locality, hit/miss behavior, and outstanding request pressure.
- backpressure QoS collapse: downstream saturation and queue propagation.
- portfolio validation: repeatable evidence pack and claim boundary check.

## Completed Projects

### Project K/L: LT Memory Characterization and Recommendation

Project K/L provide the LT-side foundation for workload, trace, latency, and recommendation reasoning. Project K turns synthetic workload patterns into memory-bottleneck metrics and bounded attribution. Project L turns that evidence into recommendation logic without claiming hardware performance gains or production signoff.

### Project AT-1: Four-Phase AT Transaction Timing

Project AT-1 establishes the AT-level timing skeleton. It makes request acceptance, target service, response timing, and backpressure visible through four-phase TLM-2.0 transaction timing.

### Project AT-2: Multi-Initiator Arbitration and Contention

Project AT-2 observes how multiple initiators contend for shared transaction-level resources. It compares arbitration behavior and exposes latency, fairness, tail-latency, and backpressure differences across synthetic policies.

### Project AT-3: QoS Sensitivity and SLA Violation

Project AT-3 observes how priority policy and queue/service constraints affect latency-sensitive traffic. It uses QoS-like policy sweeps to reason about protected traffic, SLA violation risk, and bounded recommendation choices.

### Project AT-4: Cache-like Shared Resource and MSHR Pressure

Project AT-4 introduces a cache-like shared resource, locality effects, hit/miss behavior, shared interference, and MSHR-like outstanding request limits. It is a bounded architecture exploration of shared-resource pressure, not a real cache hierarchy or coherence model.

### Project AT-5: Memory System Backpressure and QoS Collapse

Project AT-5 shows how downstream saturation and bounded queues can create upstream backpressure and hard limits for QoS policy. Priority policies can redistribute contention, but they cannot create downstream service capacity.

### Portfolio Evidence Harness

The portfolio evidence harness connects AT-1 through AT-5 and K/L into one repeatable evidence pack. It checks that the current portfolio remains reproducible and that the claim boundary is explicit.

```text
Portfolio Evidence Pack PASS
projects=AT-1,AT-2,AT-3,AT-4,AT-5,K,L
claim_boundary=PASS
schema_version=p0.2
```

## Key Architecture Lessons

1. Workload pattern decides what kind of bottleneck becomes visible.
2. AT timing exposes transaction-level latency structure without pretending to be cycle-accurate.
3. Arbitration turns local transaction behavior into system-level contention.
4. QoS is useful under bounded contention but fragile under downstream saturation.
5. Shared resources introduce locality, hit/miss behavior, and outstanding request pressure.
6. MSHR-like pressure can dominate even when average service latency looks acceptable.
7. Backpressure reveals whether the system is capacity-limited rather than policy-limited.
8. A portfolio evidence harness is valuable because it turns isolated labs into a repeatable architecture argument.

## Final Stage 1 Claim

Stage 1 shows that this repository can model and explain memory-system bottlenecks at a bounded AT-level abstraction, connect synthetic workloads to latency metrics, and produce architecture recommendation logic across arbitration, QoS, shared-resource pressure, and backpressure collapse.

## Claim Boundary

This portfolio does not claim:

- cycle-accurate modeling
- protocol compliance
- real Apple Silicon simulation
- real NVIDIA GPU simulation
- Arm CHI / AXI / ACE compliance
- real NoC behavior
- real DRAM-controller behavior
- silicon validation
- production signoff

It only claims:

- bounded AT-level synthetic architecture exploration
- trend comparison
- bottleneck isolation
- latency attribution
- recommendation logic
