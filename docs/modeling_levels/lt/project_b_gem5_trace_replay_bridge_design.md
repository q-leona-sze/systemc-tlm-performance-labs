# Project B Design: gem5 Trace Replay Bridge

## 1. Motivation

`SystemC/TLM Architecture Performance Labs` already has a reproducible
architecture-level performance workflow:

```text
workload -> trace -> metrics -> sweep -> comparison -> demo
```

Phase 16A proved that the LT lab can compare memory access patterns with
measurable outputs. The current validated patterns are:

| Pattern | avg_latency_ns | p99_latency_ns | bank_conflict_ratio_pct | throughput_txn_per_us |
| --- | ---: | ---: | ---: | ---: |
| `sequential` | `100.000` | `120.000` | `0.000` | `20.000` |
| `stride` | `119.688` | `140.000` | `98.438` | `16.710` |
| `hotspot` | `100.000` | `120.000` | `0.000` | `20.000` |

Project B extends the traffic source from synthetic memory access patterns to
workload trace replay. The goal is to make the LT lab capable of consuming a
normalized memory-access trace and replaying it through the existing
SystemC/TLM performance model.

The useful engineering claim is narrow:

> This project can replay normalized workload memory traces through a
> SystemC/TLM LT performance model and compare latency, bank conflict, and
> throughput metrics.

This is not a gem5-SystemC co-simulation phase. It is the trace-contract phase
that makes later gem5-derived traffic possible.

## 2. Why Trace Replay Before gem5-SystemC Co-Simulation

Trace replay is the right first step because it separates three concerns:

1. Workload memory-access description.
2. SystemC/TLM replay and latency modeling.
3. Future simulator integration.

Direct gem5-SystemC co-simulation would introduce several variables at once:

- gem5 build and configuration dependencies.
- host/target execution environment setup.
- event synchronization between simulators.
- debug complexity across two simulation kernels.
- unclear ownership of timing, ordering, and backpressure semantics.

Normalized trace replay gives the project a stable interface before any live
integration exists. It allows the LT lab to answer:

- Can a workload-derived memory stream be represented in a simple schema?
- Can the LT model replay that stream deterministically?
- Do the generated metrics match the same artifact chain as Phase 16A?
- Are malformed traces rejected with useful diagnostics?

Only after this contract is validated should gem5 SE mode extraction or live
co-simulation be considered.

## 3. Scope

In scope for the first Project B implementation:

- Define a normalized workload trace CSV schema.
- Design a small sample trace set.
- Replay trace rows through the existing `examples/lt` LT path.
- Preserve the generated artifact chain:
  - input normalized trace
  - replayed LT trace
  - metrics
  - `summary.csv`
  - `comparison.md`
  - demo result
- Compute latency, bank conflict, and throughput metrics.
- Keep the implementation dependency-free with respect to gem5.
- Keep the replay deterministic and suitable for one-command validation.

The intended project placement is `examples/lt`, because this phase extends the
LT Architecture-Level Performance Workflow rather than the AT arbitration lab.

## 4. Non-Goals

Project B first phase explicitly does not provide:

- Real gem5 integration.
- Live gem5-SystemC co-simulation.
- Full-system Linux simulation.
- gem5 timing-mode validation.
- A gem5 build dependency.
- GPU cycle accuracy.
- AXI cycle accuracy.
- CHI cycle accuracy.
- NoC cycle accuracy.
- Production interconnect modeling.
- Cache coherence modeling.
- Silicon correlation.

Any future gem5 references should be phrased as trace source options, not as
current runtime dependencies.

## 5. Relationship to standalone LT replay

```text
normalized trace fixtures
-> Project B replay
-> trace.csv
-> summary.csv
-> comparison.md
-> demo PASS
```

Project B preserves the same performance-analysis shape while making the trace
source explicit and file-based:

```text
normalized workload trace
-> SystemC/TLM LT replay
-> latency / bank conflict / throughput metrics
-> summary.csv
-> comparison.md
```

Conceptual difference:

| Phase | Traffic source | Main value |
| --- | --- | --- |
| Phase 16A | Synthetic named patterns | Controlled memory-pattern experiments. |
| Project B | Normalized workload trace | Replay of workload-like access streams. |

Project B should reuse the Phase 16A metric vocabulary where possible:

- `avg_latency_ns`
- `p99_latency_ns`
- `bank_conflict_ratio_pct`
- `throughput_txn_per_us`

The initial Project B design should not change `examples/at`.

## 6. Normalized Trace Schema

The normalized trace is a CSV file. Each row represents one memory transaction
request to be replayed by the LT model.

Required fields:

| Field | Type | Description |
| --- | --- | --- |
| `workload_name` | string | Logical workload or trace case name. |
| `txn_id` | integer or string | Stable transaction identifier within the trace. |
| `timestamp_ns` | numeric | Intended issue time in normalized trace time. |
| `initiator_id` | string or integer | Logical initiator that issues the transaction. |
| `command` | string | `READ` or `WRITE`. |
| `address` | integer or hex string | Transaction byte address. |
| `size_bytes` | integer | Access size in bytes. |

Optional fields:

| Field | Type | Description |
| --- | --- | --- |
| `pc` | integer or hex string | Program counter associated with the access, when available. |
| `symbol` | string | Function or source-level symbol, when available. |
| `source` | string | Trace origin, such as `synthetic`, `gem5_se`, or `manual`. |
| `comment` | string | Short human-readable note for debugging or documentation. |

Schema rules:

- `timestamp_ns` is a replay ordering hint, not a claim of cycle-accurate
  timing.
- Rows should be sorted by `timestamp_ns`, then by `txn_id` when timestamps are
  equal.
- Replayer behavior should remain deterministic even if the input row order is
  not sorted.
- `command` should be case-normalized to `READ` or `WRITE`.
- `address` may use decimal or `0x` hexadecimal notation.
- `size_bytes` must be positive.
- Unknown extra columns should be preserved in diagnostics when possible, but
  they should not be required for replay.

## 7. Sample Trace Design

The first sample traces should be small, readable, and deterministic. They are
not intended to represent full applications.

Recommended future sample directory:

```text
examples/lt/traces/project_b/
```

Recommended sample cases:

| Trace | Purpose |
| --- | --- |
| `sequential_normalized.csv` | Baseline ordered memory stream. |
| `stride_normalized.csv` | Reproduce the Phase 16A bank-conflict-style pattern through the replay path. |
| `hotspot_normalized.csv` | Concentrated address-region stream. |
| `two_initiator_interleave.csv` | Deterministic interleaving from two logical initiators. |

Minimal sample row shape:

```csv
workload_name,txn_id,timestamp_ns,initiator_id,command,address,size_bytes,pc,symbol,source,comment
sequential_demo,1,0,cpu0,READ,0x00000000,4,0x80000000,load_loop,manual,baseline access
sequential_demo,2,50,cpu0,READ,0x00000004,4,0x80000004,load_loop,manual,baseline access
stride_demo,1,0,cpu0,READ,0x00000000,4,0x80000100,stride_loop,manual,stride seed
stride_demo,2,50,cpu0,READ,0x00000010,4,0x80000104,stride_loop,manual,stride 16
```

Design notes:

- Keep sample traces short enough to inspect manually.
- Include at least one trace that maps to the Phase 16A `stride` behavior.
- Include at least one multi-initiator trace to validate ordering and
  initiator attribution.
- Do not require gem5 to generate these first samples.

## 8. Replay Mechanism in `examples/lt`

The replay mechanism should live in the LT lab path because it extends the
architecture-level performance workflow.

Recommended conceptual flow:

```text
normalized trace CSV
      |
      v
trace parser and validator
      |
      v
deterministic replay scheduler
      |
      v
existing LT transaction path
      |
      v
LT trace output
      |
      v
metrics / summary / comparison
```

Replay behavior:

- Parse all rows before simulation starts.
- Validate required fields before replay begins.
- Sort rows by `timestamp_ns`, then `txn_id`.
- Map `initiator_id` to an LT initiator lane.
- Issue each row as an LT transaction with the normalized command, address, and
  size.
- Preserve original trace metadata in output where practical.
- Use `timestamp_ns` as normalized issue-time spacing, not host wall-clock time.
- Keep replay deterministic across runs.

The first implementation should use a file-based trace input rather than a live
socket, pipe, or gem5 plugin. That keeps the debug boundary clear.

Recommended future command shape:

```bash
python3 examples/lt/tools/demo_trace_replay_lab.py \
  --trace examples/lt/traces/project_b/stride_normalized.csv
```

## 9. Metrics Design

Project B should report workload-level metrics that can be compared across
normalized traces.

Recommended metrics:

| Metric | Meaning |
| --- | --- |
| `total_transactions` | Number of input trace rows. |
| `complete_transactions` | Number of transactions replayed and observed in output. |
| `avg_latency_ns` | Average replayed LT transaction latency. |
| `p50_latency_ns` | Median replayed LT transaction latency. |
| `p95_latency_ns` | Tail latency indicator. |
| `p99_latency_ns` | Extreme tail latency indicator. |
| `max_latency_ns` | Maximum observed transaction latency. |
| `avg_queue_delay_ns` | Average modeled queue delay, when available. |
| `avg_target_service_delay_ns` | Average modeled target service delay. |
| `total_bank_conflicts` | Count of transactions with modeled bank conflict. |
| `bank_conflict_ratio_pct` | `100 * total_bank_conflicts / complete_transactions`. |
| `throughput_txn_per_us` | Completed transactions per microsecond of simulated replay time. |
| `initiator_count` | Number of distinct initiators observed in the normalized trace. |
| `read_transactions` | Count of replayed reads. |
| `write_transactions` | Count of replayed writes. |

Metric rules:

- Throughput must use simulated or normalized replay timestamps, not host
  wall-clock time.
- Percentiles should use a documented deterministic method.
- Missing optional metadata such as `pc` or `symbol` must not block metrics.
- Malformed required fields should produce `status=FAIL` with useful error
  text.
- Metrics should not imply cache, DRAM, NoC, AXI, CHI, or GPU hardware
  fidelity.

## 10. `summary.csv` Design

`summary.csv` should remain one row per replay case.

Recommended fields:

```text
case_id,status,workload_name,trace_path,source,total_transactions,
complete_transactions,initiator_count,read_transactions,write_transactions,
first_timestamp_ns,last_timestamp_ns,replay_window_ns,avg_latency_ns,
p50_latency_ns,p95_latency_ns,p99_latency_ns,max_latency_ns,
avg_queue_delay_ns,avg_target_service_delay_ns,total_bank_conflicts,
bank_conflict_ratio_pct,throughput_txn_per_us,sanity_failure_count,error
```

Design notes:

- Keep failed cases in the file with `status=FAIL`.
- Record `trace_path` so each row is reproducible.
- Use `source` from the normalized trace when present.
- Use `error` for missing files, malformed rows, invalid commands, invalid
  addresses, missing output traces, and failed sanity checks.
- Keep Phase 16A-style metric names so comparisons remain familiar.

## 11. `comparison.md` Design

`comparison.md` should be generated from `summary.csv`. It should read as a
short performance-modeling analysis, not as a raw CSV dump.

Recommended sections:

1. `Replay Cases`
2. `Baseline`
3. `Latency Distribution`
4. `Bank Conflict Effects`
5. `Throughput`
6. `Initiator Mix`
7. `Trace Quality and Sanity Checks`
8. `Engineering Interpretation`

Recommended observations:

- A stride-like replay trace should raise `bank_conflict_ratio_pct` relative to
  a sequential replay trace when the addresses alias into the minimal bank
  model.
- A hotspot replay trace should show whether concentrated address traffic
  changes latency or conflict behavior in the current LT model.
- A two-initiator replay trace should make queue-delay and throughput effects
  easier to inspect.
- A gem5-derived trace in a future phase should be compared with the same
  columns, not with a new reporting format.

The report should avoid claims such as:

- "This is a gem5-SystemC co-simulation result."
- "This is full-system Linux behavior."
- "This is GPU cycle accurate."
- "This models AXI, CHI, or NoC timing."

## 12. Demo Command Design

Recommended future one-command demo:

```bash
python3 examples/lt/tools/demo_trace_replay_lab.py \
  --trace examples/lt/traces/project_b/stride_normalized.csv
```

Recommended future sweep command:

```bash
python3 examples/lt/tools/run_trace_replay_sweep.py \
  --trace-dir examples/lt/traces/project_b \
  --output-dir examples/lt/results/trace_replay_sweep \
  --keep-going
```

Recommended generated outputs:

```text
examples/lt/results/trace_replay_sweep/summary.csv
examples/lt/results/trace_replay_sweep/comparison.md
examples/lt/results/trace_replay_sweep/<case_id>/trace.csv
examples/lt/results/trace_replay_sweep/<case_id>/analysis.txt
```

The demo should print:

- input trace path
- output directory
- `summary.csv` path
- `comparison.md` path
- pass/fail status
- the highest `bank_conflict_ratio_pct`
- the highest `p99_latency_ns`
- the highest `throughput_txn_per_us`

It should also print a short scope reminder:

```text
This is normalized trace replay through an LT performance model, not live
gem5-SystemC co-simulation.
```

## 13. Validation Plan

Validation should proceed in small steps:

1. Validate schema parsing with one tiny sequential trace.
2. Reject a trace missing each required field.
3. Reject invalid `command` values.
4. Reject non-positive `size_bytes`.
5. Confirm decimal and hexadecimal addresses parse consistently.
6. Confirm sorting by `timestamp_ns`, then `txn_id`.
7. Replay `sequential_normalized.csv`.
8. Replay `stride_normalized.csv`.
9. Replay `hotspot_normalized.csv`.
10. Replay `two_initiator_interleave.csv`.
11. Confirm the LT output trace exists and is non-empty for every `OK` case.
12. Confirm `summary.csv` has one row per replay case.
13. Confirm failed cases remain in `summary.csv` with `status=FAIL`.
14. Confirm `comparison.md` is generated from `summary.csv`.
15. Confirm demo output ends in `PASS` only when all required artifacts exist.

Required sanity checks:

- `total_transactions > 0`.
- `complete_transactions > 0` for `OK` cases.
- `complete_transactions <= total_transactions`.
- `first_timestamp_ns <= last_timestamp_ns`.
- `replay_window_ns >= 0`.
- `avg_latency_ns >= 0`.
- `p50_latency_ns <= p95_latency_ns <= p99_latency_ns <= max_latency_ns`.
- `bank_conflict_ratio_pct` is between `0` and `100`.
- `throughput_txn_per_us` is `NA` or non-negative.
- Every output transaction can be traced back to a normalized input `txn_id`.

## 14. Future Path

The intended path is staged:

1. Normalized trace replay.
   - Define the CSV contract.
   - Build deterministic file-based replay.
   - Validate metrics, `summary.csv`, `comparison.md`, and demo output.
2. gem5 SE mode trace extraction.
   - Run a small syscall-emulation workload in gem5.
   - Extract memory access events into the normalized CSV schema.
   - Keep gem5 as an offline trace producer, not a live dependency.
3. gem5-derived trace replay.
   - Replay the gem5-derived normalized trace through `examples/lt`.
   - Compare it with manual and synthetic sample traces using the same metrics.
   - Document differences as workload-stream effects, not hardware correlation.
4. Future live co-simulation.
   - Consider only after the normalized replay contract is stable.
   - Define ownership of time synchronization, transaction ordering, and
     backpressure before implementation.
   - Treat this as a later research direction, not a current Project B result.

This staged path keeps each milestone measurable and debuggable.

## 15. Interview Value

Project B is valuable for SoC, ESL, and Performance Modeling interviews because
it demonstrates a disciplined bridge from workload behavior to architecture
metrics.

Interview-relevant mapping:

| Interview topic | Project B artifact |
| --- | --- |
| Workload representation | Normalized trace CSV schema. |
| Simulator boundary design | File-based trace contract before live co-simulation. |
| TLM replay | `examples/lt` replay mechanism. |
| Performance metrics | Latency, bank conflict, throughput, queue delay. |
| Reproducibility | `summary.csv`, `comparison.md`, one-command demo. |
| Debuggability | Small sample traces and schema validation. |
| Scope control | No gem5 dependency in first phase; no cycle-accuracy claims. |

Suggested concise explanation:

> After validating synthetic memory access patterns in the LT lab, I designed a
> normalized trace replay bridge. The first phase does not integrate gem5
> directly. It defines a stable CSV contract, replays workload-like memory
> streams through the SystemC/TLM LT model, and generates latency, bank
> conflict, throughput, summary, and comparison artifacts. This keeps the
> simulator boundary clean before any future gem5-derived trace or live
> co-simulation work.

The key signal is engineering judgment: build the trace contract first, validate
the replay and metrics, then consider more complex simulator integration only
after the artifact chain is stable.
