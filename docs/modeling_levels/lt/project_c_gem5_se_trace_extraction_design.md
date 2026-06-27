# Project C Design: gem5 SE Trace Extraction MVP

## 1. Motivation

`SystemC/TLM Architecture Performance Labs` already has a validated LT-side
experiment chain:

```text
workload -> trace -> metrics -> sweep -> comparison -> demo
```

Project B proves that the LT lab can replay a normalized memory trace CSV and
generate `trace.csv`, `summary.csv`, and `comparison.md`.

Project C adds an external trace producer: gem5 SE mode. The MVP goal is to run
tiny C workloads in gem5 SE mode, extract memory events into the Project B
normalized CSV schema, and replay those traces through the existing LT backend.

Project C should be described as planned trace extraction until a real gem5 SE
run, normalized trace, Project B replay, and generated artifacts have all been
validated.

## 2. Relationship to Project B

Project B remains the replay and analysis backend. Project C should only
produce input traces for it.

Target chain:

```text
C workload
-> external gem5 SE run
-> raw memory trace
-> normalized CSV
-> Project B replay
-> trace.csv / summary.csv / comparison.md
```

Current Project B required schema:

```csv
workload_name,txn_id,timestamp_ns,initiator_id,command,address,size_bytes
```

The first Project C traces should fit the current Project B MVP constraints:

- one workload per trace file
- `initiator_id=101`
- `command=READ`
- `size_bytes=4`
- addresses normalized into the LT replay address window

Additional gem5 metadata such as PC, raw tick, CPU id, or original address may
be preserved as optional columns, but must not be required by Project B replay.

## 3. Why SE Mode First

SE mode is the smallest useful gem5 entry point for this project because it runs
user-level programs without full-system Linux bring-up.

Starting with SE mode avoids:

- guest kernel and disk-image setup
- boot-time noise in the first trace experiment
- device/platform modeling work
- gem5-SystemC synchronization
- timing ownership questions between two simulators

The first milestone should validate the file-based trace boundary before any
live co-simulation path is considered.

## 4. Scope

In scope:

- plain C workloads for gem5 SE mode
- `sequential_scan`
- `stride_scan`
- external gem5 SE execution
- raw memory trace extraction
- conversion to Project B normalized CSV
- Project B replay using existing LT tools
- validation through generated `trace.csv`, `summary.csv`, and `comparison.md`

Preferred future additions to this repository:

- docs
- small sample C workloads
- small scripts
- optional sample normalized traces

Out of scope for this design-only step:

- writing source code
- adding gem5 configs
- changing SystemC C++
- changing `examples/at`
- changing `references`

## 5. Non-Goals

Project C MVP does not provide:

- full-system Linux simulation
- gem5-SystemC live co-simulation
- CUDA
- GPU cycle-accurate modeling
- AXI, CHI, or NoC cycle accuracy
- production interconnect protocol support
- cache-coherence modeling
- silicon correlation
- a vendored gem5 tree
- a committed gem5 build
- modifications to `examples/at`
- modifications to `references`
- modifications to SystemC C++ code

gem5 is only an offline trace producer in this phase. The SystemC/TLM lab
remains the replay and analysis backend.

## 6. Proposed Directory Structure

Proposed future structure only; this design document does not create these
files.

```text
docs/
  project_c_gem5_se_trace_extraction_design.md

examples/lt/workloads/gem5_se/
  README.md
  sequential_scan.c
  stride_scan.c

examples/lt/tools/
  convert_gem5_se_trace.py

examples/lt/traces/gem5_se/
  sequential_scan_normalized.csv
  stride_scan_normalized.csv

examples/lt/results/gem5_se_trace_replay/
  trace.csv
  summary.csv
  comparison.md
```

Rules:

- Keep Project C under `examples/lt` because it feeds Project B replay.
- Keep external gem5 source/build directories outside this repository.
- Keep raw gem5 traces and compiled workload binaries as generated artifacts.
- Do not make Project C a dependency of `examples/at`.
- Do not depend on `references`.

## 7. Workload Design

The first workloads should be deterministic and small enough to inspect by hand.
They are trace producers, not benchmark claims.

### `sequential_scan`

Purpose:

- produce a baseline contiguous access stream
- map naturally to the Project B sequential replay case

Minimal behavior:

- use a fixed integer buffer
- read 32-bit elements in increasing order
- accumulate into a volatile sink
- avoid threads, CUDA, GPU APIs, and SystemC dependencies

Conceptual pattern:

```text
base + 0
base + 4
base + 8
base + 12
...
```

### `stride_scan`

Purpose:

- produce a stride access stream
- preserve the Project B bank-conflict intuition

Minimal behavior:

- use the same buffer shape as `sequential_scan`
- read 32-bit elements with a fixed stride
- keep the access count and stride documented
- accumulate into a volatile sink

Conceptual pattern:

```text
base + 0
base + 16
base + 32
base + 48
...
```

## 8. How to Build C Workloads for gem5 SE Mode

The workloads are target binaries for gem5 SE mode. They should not be added to
the SystemC C++ build.

Recommended command shape:

```bash
mkdir -p build/project_c/gem5_se

${TARGET_CC} -O2 -static \
  -o build/project_c/gem5_se/sequential_scan \
  examples/lt/workloads/gem5_se/sequential_scan.c

${TARGET_CC} -O2 -static \
  -o build/project_c/gem5_se/stride_scan \
  examples/lt/workloads/gem5_se/stride_scan.c
```

Validation before gem5 execution:

```bash
file build/project_c/gem5_se/sequential_scan
readelf -h build/project_c/gem5_se/sequential_scan
readelf -l build/project_c/gem5_se/sequential_scan
```

Use the matching target compiler for the gem5 ISA. Prefer static linking for
the MVP; if dynamic linking is required, document loader and library
requirements explicitly.

## 9. How to Run gem5 SE Mode

Do not hard-code a gem5 checkout or real gem5 config path into this repository.
Use explicit external paths.

Recommended command shape:

```bash
export GEM5_BIN=/absolute/path/to/external/gem5.opt
export GEM5_SE_CONFIG=/absolute/path/to/external/se_mode_config.py
export TARGET_BIN=/absolute/path/to/build/project_c/gem5_se/sequential_scan
export GEM5_OUT=build/project_c/gem5_se_runs/sequential_scan

mkdir -p "${GEM5_OUT}"

"${GEM5_BIN}" \
  --outdir="${GEM5_OUT}" \
  "${GEM5_SE_CONFIG}" \
  --cmd="${TARGET_BIN}"
```

Expected generated evidence, once implementation exists:

```text
build/project_c/gem5_se_runs/sequential_scan/stats.txt
build/project_c/gem5_se_runs/sequential_scan/simout
build/project_c/gem5_se_runs/sequential_scan/simerr
build/project_c/gem5_se_runs/sequential_scan/raw_memory_trace.csv
```

Do not claim a gem5 run has succeeded unless these artifacts come from a real
run.

## 10. Memory Trace Extraction Strategy

Use a file-based extraction boundary:

```text
external gem5 SE run
-> raw_memory_trace.csv
-> converter
-> Project B normalized CSV
```

Raw trace information needed:

| Raw concept | Normalized use |
| --- | --- |
| event order | `txn_id` |
| tick or event index | `timestamp_ns` |
| CPU/thread id | `initiator_id` |
| access type | `command` |
| address | `address` |
| access size | `size_bytes` |
| optional PC | optional metadata |

Conservative rules:

- Filter startup/library noise when possible.
- Prefer workload-buffer events over whole-process memory traffic.
- Normalize workload-buffer addresses to a replay-safe address range if needed.
- Treat `timestamp_ns` as normalized ordering unless a documented tick-to-time
  conversion exists.
- Keep raw gem5 traces as generated outputs.

## 11. Normalized CSV Schema

Initial required schema:

```csv
workload_name,txn_id,timestamp_ns,initiator_id,command,address,size_bytes
```

Initial values:

| Field | MVP rule |
| --- | --- |
| `workload_name` | `sequential_scan` or `stride_scan`. |
| `txn_id` | Stable event id after filtering. |
| `timestamp_ns` | Normalized issue time. |
| `initiator_id` | `101`. |
| `command` | `READ`. |
| `address` | Decimal or `0x` hex, normalized for LT replay. |
| `size_bytes` | `4`. |

Optional future columns:

- `pc`
- `symbol`
- `source`
- `raw_tick`
- `raw_address`
- `target_isa`
- `comment`

Schema rules:

- Keep Project B required columns first.
- Keep row ordering deterministic.
- Reject empty traces.
- Reject unsupported commands or sizes in the MVP.
- Do not require optional gem5 metadata for replay.

## 12. Converter Design, If Needed

A converter is expected because raw gem5 output should not be treated as the
stable Project B contract.

Converter responsibilities:

- parse raw trace rows
- filter workload-relevant memory events
- assign stable `txn_id`
- normalize timestamps
- normalize addresses
- enforce MVP fields
- write normalized CSV
- optionally run Project B `--validate-only`

Recommended future command shape:

```bash
python3 examples/lt/tools/convert_gem5_se_trace.py \
  --input build/project_c/gem5_se_runs/sequential_scan/raw_memory_trace.csv \
  --output examples/lt/traces/gem5_se/sequential_scan_normalized.csv \
  --workload-name sequential_scan \
  --initiator-id 101 \
  --command-filter READ \
  --size-bytes 4 \
  --timestamp-step-ns 100 \
  --address-normalize zero_based
```

The converter should be file-based and should not import gem5 Python modules or
require a gem5 checkout at conversion time.

## 13. How to Feed Generated Traces into Project B Replay

Once the normalized traces exist:

```bash
python3 examples/lt/tools/run_trace_replay_lab.py \
  --trace examples/lt/traces/gem5_se/sequential_scan_normalized.csv \
  --trace examples/lt/traces/gem5_se/stride_scan_normalized.csv \
  --output-dir examples/lt/results/gem5_se_trace_replay
```

Optional schema check:

```bash
python3 examples/lt/tools/run_trace_replay_lab.py \
  --validate-only \
  --trace examples/lt/traces/gem5_se/sequential_scan_normalized.csv \
  --trace examples/lt/traces/gem5_se/stride_scan_normalized.csv
```

Expected replay outputs:

```text
examples/lt/results/gem5_se_trace_replay/trace.csv
examples/lt/results/gem5_se_trace_replay/summary.csv
examples/lt/results/gem5_se_trace_replay/comparison.md
```

The report should describe the inputs as gem5-SE-derived normalized traces
replayed through an LT performance model, not as live gem5-SystemC
co-simulation.

## 14. Validation Plan

Validation gates:

1. Workload binary sanity.
   - Build both workloads.
   - Check `file`, `readelf -h`, and `readelf -l`.
2. gem5 SE run evidence.
   - Confirm external `GEM5_BIN`.
   - Confirm external SE config.
   - Produce `stats.txt`, `simout`, and `simerr`.
3. Raw trace evidence.
   - Produce non-empty `raw_memory_trace.csv`.
   - Document filtering assumptions.
4. Normalized CSV evidence.
   - Produce one normalized CSV per workload.
   - Validate required Project B fields.
   - Confirm `initiator_id=101`, `command=READ`, and `size_bytes=4`.
5. Project B replay evidence.
   - Run `--validate-only`.
   - Run replay.
   - Confirm `trace.csv`, `summary.csv`, and `comparison.md`.
6. Interpretation.
   - Compare `sequential_scan` and `stride_scan`.
   - Explain results as LT replay effects of the memory stream.
   - Avoid cycle-accuracy, GPU, AXI, CHI, NoC, or silicon-correlation claims.

## 15. Risks

| Risk | Mitigation |
| --- | --- |
| gem5 setup is too heavy | Keep gem5 external and paths explicit. |
| Wrong target binary ISA | Check with `file` and `readelf` before running. |
| Dynamic loader problems | Prefer static linking for the MVP. |
| Startup/library traffic pollutes traces | Use tiny workloads and filtering. |
| Raw gem5 time is overclaimed | Treat `timestamp_ns` as normalized unless conversion is documented. |
| Raw addresses do not fit replay | Normalize to a Project B-safe address range. |
| Converter becomes coupled to gem5 internals | Keep it file-based and gem5-module-free. |
| Scope drifts into co-simulation | Keep Project C as offline trace extraction. |

## 16. Future Path Toward Full-System and Live Co-Simulation

Recommended staged path:

1. Project C MVP.
   - gem5 SE workload run
   - raw memory trace
   - normalized CSV
   - Project B replay
2. SE trace quality improvements.
   - better workload-region filtering
   - optional PC/symbol metadata
   - read/write support
   - broader Project B schema support if needed
3. Full-system exploration.
   - only after SE extraction is validated
   - document kernel, image, and platform requirements explicitly
4. Live gem5-SystemC co-simulation research.
   - only after file-based traces are stable
   - define time ownership, ordering, backpressure, and completion semantics

Until each stage has real generated artifacts, describe it as future work rather
than completed integration.
