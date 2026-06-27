# Engineering Lessons

## Ubuntu Validation Is the Source of Truth

Ubuntu validation is the final source of truth for this portfolio. Mac-local editing is useful for development, but it is not enough to claim release readiness. A change should be treated as accepted only after the intended Ubuntu validation path can reproduce the expected PASS markers and artifacts.

## SystemC Linking Discipline

SystemC linking must stay explicit and conservative. Avoid bare `target_link_libraries(... systemc)` because it can silently bind to the wrong library name or search path. Use the explicit SystemC library variable already established in the AT targets, and protect the AT-4 / AT-5 linking logic that has already been fixed.

Use this check when reviewing linking-sensitive changes:

```bash
grep -n "PROJECT_AT4_SYSTEMC_LIBRARY\|PROJECT_AT5_SYSTEMC_LIBRARY\|Project AT-4 linking\|Project AT-5 linking" \
  examples/at/CMakeLists.txt
```

## Named Targets Instead of Aggregate Targets

The aggregate `at` target should not be the acceptance boundary for the portfolio. Stage 1 validation should use named project targets so each lab has an explicit build gate:

```bash
cmake --build build-at --target project_at1_four_phase_memory_timing -j
cmake --build build-at --target project_at2_multi_initiator_arbitration -j
cmake --build build-at --target project_at3_qos_sensitivity_sla -j
cmake --build build-at --target project_at4_cache_mshr_pressure -j
cmake --build build-at --target project_at5_backpressure_qos_collapse -j
```

## Protect Existing CMake Fixes When Adding New Targets

New targets should not break old targets. In particular, do not regress the explicit SystemC linking logic already used by AT-4 and AT-5. When adding a target, check that the named-target build path remains valid for AT-1 through AT-5.

## Branch, HEAD, and Origin Hygiene

Each project should use a separate branch. Before modifying files, confirm the current branch and worktree state. Before pushing, confirm that `origin` points to the intended repository.

```bash
git status --short
git branch --show-current
git remote -v
git log --oneline --decorate -5
```

## Tag Discipline

Important portfolio stages should have explicit tags so release state and evidence state stay aligned. Current and planned examples include:

- v0.10
- v0.11
- v0.12
- v0.13
- planned v0.14-stage1-roadmap

This document only describes tag discipline. It does not create tags.

## Packaging From Mac Without AppleDouble Pollution

When packaging from Mac to Ubuntu, avoid AppleDouble files, `.DS_Store`, and xattrs polluting the source tree.

```bash
tar --disable-copyfile --no-xattrs -czf systemc-tlm-performance-labs.tar.gz systemc-tlm-performance-labs
```

On Ubuntu, check the extracted tree with:

```bash
find . -name "._*" -o -name ".DS_Store"
```

## Source, Generated Evidence, and Build Artifacts

Source files should be versioned. Generated results should have a clear policy and should not be mixed with source changes accidentally. Build artifacts should not be committed. A docs-only change should not regenerate evidence, alter result directories, or change build outputs.

## Claim Boundary Discipline

Documentation should stay claim-bounded. Safe expressions include:

- bounded AT-level synthetic architecture exploration
- trend comparison
- bottleneck isolation
- recommendation logic
- not cycle-accurate
- not protocol-compliant
- not silicon validation
- not production signoff

Avoid unsupported claims:

- Do not claim Apple Silicon simulation.
- Do not claim NVIDIA GPU simulation.
- Do not claim Arm CHI compliance.
- Do not claim real NoC behavior.
- Do not claim real DRAM-controller behavior.

If these terms appear, they should appear only in an explicit negative boundary statement.

## Repeatable Project Rhythm

Stage 1 follows a repeatable engineering rhythm:

```text
independent lab -> Ubuntu validation -> PR -> tag -> evidence integration -> Ubuntu validation -> PR -> tag
```

This rhythm matters because it separates experiment implementation, validation, and portfolio integration. That separation lowers regression risk and makes each claim easier to review.
