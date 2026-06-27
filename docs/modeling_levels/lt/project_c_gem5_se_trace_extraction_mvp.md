# Project C MVP: gem5 SE Trace Extraction Flow

This runbook is for Ubuntu validation of Project C. It keeps gem5 external to
`SystemC/TLM Architecture Performance Labs` and feeds normalized CSV traces
into the existing Project B replay bridge.

Project C is an offline trace producer flow:

```text
gem5 SE workload
-> gem5 simout with PROJECT_C_MEM markers
-> normalized CSV
-> Project B replay
```

It is not gem5-SystemC live co-simulation, not full-system Linux, not CUDA, not
a GPU model, and not a cycle-accurate model.

## Ubuntu Paths

Use the repository path required for Project C validation:

```bash
cd ~/workspace/systemc-tlm-performance-labs
```

Keep gem5 outside this repository. Pass gem5 paths explicitly:

```bash
export GEM5_BINARY=/absolute/path/to/gem5/build/X86/gem5.opt
export GEM5_CONFIG=/absolute/path/to/gem5/configs/example/se.py
```

If your gem5 checkout uses another SE config path, pass that path through
`--gem5-config`.

## Build Workloads

For an X86 gem5 build:

```bash
mkdir -p build/project_c/gem5_se

gcc -O2 -static -fno-pie -no-pie \
  -o build/project_c/gem5_se/sequential_scan \
  examples/lt/workloads/gem5_se/sequential_scan.c

gcc -O2 -static -fno-pie -no-pie \
  -o build/project_c/gem5_se/stride_scan \
  examples/lt/workloads/gem5_se/stride_scan.c
```

Sanity checks:

```bash
file build/project_c/gem5_se/sequential_scan
readelf -h build/project_c/gem5_se/sequential_scan
readelf -l build/project_c/gem5_se/sequential_scan

file build/project_c/gem5_se/stride_scan
readelf -h build/project_c/gem5_se/stride_scan
readelf -l build/project_c/gem5_se/stride_scan
```

For ARM or RISC-V gem5, replace `gcc` with the matching cross-compiler and
verify the ELF machine before running gem5.

## Run gem5 SE and Convert

Sequential trace:

```bash
python3 examples/lt/tools/run_gem5_se_trace_extraction.py \
  --gem5-binary "${GEM5_BINARY}" \
  --gem5-config "${GEM5_CONFIG}" \
  --workload build/project_c/gem5_se/sequential_scan \
  --workload-name sequential_scan \
  --output-dir build/project_c/gem5_se_runs/sequential_scan \
  --normalized-output examples/lt/traces/gem5_sequential_trace.csv
```

Stride trace:

```bash
python3 examples/lt/tools/run_gem5_se_trace_extraction.py \
  --gem5-binary "${GEM5_BINARY}" \
  --gem5-config "${GEM5_CONFIG}" \
  --workload build/project_c/gem5_se/stride_scan \
  --workload-name stride_scan \
  --output-dir build/project_c/gem5_se_runs/stride_scan \
  --normalized-output examples/lt/traces/gem5_stride_trace.csv
```

Expected normalized schema:

```csv
workload_name,txn_id,timestamp_ns,initiator_id,command,address,size_bytes,pc,symbol,source
```

The `source` field should be `gem5_se_simout` for real Ubuntu gem5 output.

## Project B Replay

Validate the generated normalized traces:

```bash
python3 examples/lt/tools/run_trace_replay_lab.py \
  --validate-only \
  --trace examples/lt/traces/gem5_sequential_trace.csv \
  --trace examples/lt/traces/gem5_stride_trace.csv
```

Replay them through Project B:

```bash
python3 examples/lt/tools/run_trace_replay_lab.py \
  --trace examples/lt/traces/gem5_sequential_trace.csv \
  --trace examples/lt/traces/gem5_stride_trace.csv \
  --output-dir examples/lt/results/gem5_trace_replay_lab
```

Expected outputs:

```text
examples/lt/results/gem5_trace_replay_lab/trace.csv
examples/lt/results/gem5_trace_replay_lab/summary.csv
examples/lt/results/gem5_trace_replay_lab/comparison.md
```

## Mac-Local Format Samples

When gem5 is unavailable on macOS, this command can generate Project B-readable
expected-format CSV samples:

```bash
python3 examples/lt/tools/convert_gem5_se_trace.py \
  --sample-pattern sequential \
  --output examples/lt/traces/gem5_sequential_trace.csv

python3 examples/lt/tools/convert_gem5_se_trace.py \
  --sample-pattern stride \
  --output examples/lt/traces/gem5_stride_trace.csv
```

These samples use `source=sample_expected_format_not_real_gem5`. They are not
real gem5 traces and must not be described as completed gem5 integration.

## Regression Checks

Project B default replay:

```bash
python3 examples/lt/tools/demo_trace_replay_lab.py
```

Standalone Project D / Project E checks:

```bash
python3 examples/lt/tools/demo_cpp_trace_replay_lab.py
python3 examples/lt/tools/demo_banked_memory_controller_lab.py
```
