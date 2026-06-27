# Project C gem5 SE Workloads

These tiny C programs are Project C trace producer workloads for gem5 syscall
emulation mode. They do not include gem5 headers, SystemC headers, CUDA, GPU
APIs, or project CMake integration.

The programs print explicit `PROJECT_C_MEM` markers to stdout. In a gem5 SE
run, stdout is captured in the run directory's `simout`. The Project C
converter reads those markers and writes the normalized Project B CSV schema.

This MVP marker stream is a controlled SE workload trace contract. It is not
gem5-SystemC live co-simulation, not full-system Linux, and not a cycle-accurate
hardware trace.

Ubuntu build shape:

```bash
cd ~/workspace/systemc-tlm-performance-labs

mkdir -p build/project_c/gem5_se

gcc -O2 -static -fno-pie -no-pie \
  -o build/project_c/gem5_se/sequential_scan \
  examples/lt/workloads/gem5_se/sequential_scan.c

gcc -O2 -static -fno-pie -no-pie \
  -o build/project_c/gem5_se/stride_scan \
  examples/lt/workloads/gem5_se/stride_scan.c
```

If the gem5 binary targets a non-x86 ISA, replace `gcc` with the matching
cross-compiler and verify the result with `file`, `readelf -h`, and
`readelf -l`.
