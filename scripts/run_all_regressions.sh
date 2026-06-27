#!/usr/bin/env bash
set -euo pipefail

USER_SYSTEMC_LIB_DIR="${USER_SYSTEMC_LIB_DIR:-}"
USER_SYSTEMC_INCLUDE_DIR="${USER_SYSTEMC_INCLUDE_DIR:-}"

ARTIFACT_DIR="artifacts"
LOG_DIR="${ARTIFACT_DIR}/logs"
SUMMARY_PATH="${ARTIFACT_DIR}/regression_summary.md"

ENV_STATUS="PENDING"
ENV_NOTE="not run"
LT_BUILD_STATUS="PENDING"
LT_BUILD_NOTE="not run"
PROJECT_D_STATUS="PENDING"
PROJECT_D_NOTE="not run"
PROJECT_E_STATUS="PENDING"
PROJECT_E_NOTE="not run"
PROJECT_F_STATUS="PENDING"
PROJECT_F_NOTE="not run"
PROJECT_B_STATUS="PENDING"
PROJECT_B_NOTE="not run"
PROJECT_C_STATUS="PENDING"
PROJECT_C_NOTE="not run"
HARD_GATE_RESULT="PASS"

PROJECT_D_SUMMARY="examples/lt/results/cpp_trace_replay_lab/summary.csv"
PROJECT_E_SUMMARY="examples/lt/results/project_e_banked_memory_controller/summary.csv"
PROJECT_F_SUMMARY="examples/lt/results/project_f_gem5_stats_correlation/correlation_summary.csv"

PROJECT_C_OUTPUTS=(
  "examples/lt/results/gem5_se_trace_extraction/sequential/stats.txt"
  "examples/lt/results/gem5_se_trace_extraction/stride/stats.txt"
  "examples/lt/results/gem5_trace_replay_lab/summary.csv"
  "examples/lt/results/gem5_trace_replay_lab/comparison.md"
)

print_start() {
  echo "[regression] START $1"
}

print_pass() {
  echo "[regression] PASS $1"
}

print_skip() {
  echo "[regression] SKIP $1"
}

print_fail() {
  echo "[regression] FAIL $1"
}

is_repo_root() {
  [[ -f "CMakeLists.txt" && -d "examples/lt" && -d "docs" && -d "scripts" && -d "tools" ]]
}

path_state() {
  local path="$1"
  if [[ -e "$path" ]]; then
    printf "exists"
  else
    printf "missing"
  fi
}

git_metadata() {
  GIT_BRANCH="unavailable"
  GIT_COMMIT="unavailable"
  GIT_DIRTY="unknown"

  if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    GIT_BRANCH="$(git branch --show-current 2>/dev/null || true)"
    if [[ -z "$GIT_BRANCH" ]]; then
      GIT_BRANCH="detached-or-unavailable"
    fi
    GIT_COMMIT="$(git rev-parse HEAD 2>/dev/null || true)"
    if [[ -z "$GIT_COMMIT" ]]; then
      GIT_COMMIT="unavailable"
    fi
    if [[ -n "$(git status --porcelain 2>/dev/null || true)" ]]; then
      GIT_DIRTY="yes"
    else
      GIT_DIRTY="no"
    fi
  fi
}

write_summary() {
  mkdir -p "$ARTIFACT_DIR"
  git_metadata

  local timestamp
  timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  cat > "$SUMMARY_PATH" <<EOF
# Project R Headless Regression Summary

## Run Metadata

- Generated timestamp: ${timestamp}
- Git branch: ${GIT_BRANCH}
- Git commit hash: ${GIT_COMMIT}
- Dirty working tree: ${GIT_DIRTY}
- SystemC lib dir: \`${USER_SYSTEMC_LIB_DIR}\`
- SystemC include dir: \`${USER_SYSTEMC_INCLUDE_DIR}\`
- Hard-gate result: ${HARD_GATE_RESULT}

## Status Matrix

| Step | Component | Status | Hard Gate | Notes |
| --- | --- | --- | --- | --- |
| 0 | Environment check | ${ENV_STATUS} | yes | ${ENV_NOTE} |
| 1 | LT build | ${LT_BUILD_STATUS} | yes | ${LT_BUILD_NOTE} |
| 2 | Project D C++ trace replay | ${PROJECT_D_STATUS} | yes | ${PROJECT_D_NOTE} |
| 3 | Project E banked memory controller | ${PROJECT_E_STATUS} | yes | ${PROJECT_E_NOTE} |
| 4 | Project F stats trend correlation | ${PROJECT_F_STATUS} | yes | ${PROJECT_F_NOTE} |
| 5 | Project B normalized trace replay | ${PROJECT_B_STATUS} | no | ${PROJECT_B_NOTE} |
| 6 | Project C gem5 SE extraction | ${PROJECT_C_STATUS} | no | ${PROJECT_C_NOTE} |

## Key Output Paths

- Project D summary: \`${PROJECT_D_SUMMARY}\` ($(path_state "$PROJECT_D_SUMMARY"))
- Project E summary: \`${PROJECT_E_SUMMARY}\` ($(path_state "$PROJECT_E_SUMMARY"))
- Project F summary: \`${PROJECT_F_SUMMARY}\` ($(path_state "$PROJECT_F_SUMMARY"))
- Project B summary: \`examples/lt/results/trace_replay_lab/summary.csv\` ($(path_state "examples/lt/results/trace_replay_lab/summary.csv"))
- Project C replay summary: \`examples/lt/results/gem5_trace_replay_lab/summary.csv\` ($(path_state "examples/lt/results/gem5_trace_replay_lab/summary.csv"))
- Logs: \`${LOG_DIR}/\`

## Scope Boundary

- No cycle accuracy validation.
- No RTL / silicon / profiler correlation.
- No gem5-SystemC live co-simulation.
- Regression validates demo chain health and generated artifact presence only.

## Generated Files Policy

- \`artifacts/regression_summary.md\` is a generated local artifact.
- \`artifacts/logs/\` contains generated local command logs.
- \`examples/lt/results/\` and \`examples/at/results/\` remain generated outputs and should not be committed.
EOF
}

set_pending_steps_skipped() {
  local reason="$1"
  if [[ "$LT_BUILD_STATUS" == "PENDING" ]]; then
    LT_BUILD_STATUS="SKIPPED"
    LT_BUILD_NOTE="$reason"
    print_skip "LT build - $reason"
  fi
  if [[ "$PROJECT_D_STATUS" == "PENDING" ]]; then
    PROJECT_D_STATUS="SKIPPED"
    PROJECT_D_NOTE="$reason"
    print_skip "Project D - $reason"
  fi
  if [[ "$PROJECT_E_STATUS" == "PENDING" ]]; then
    PROJECT_E_STATUS="SKIPPED"
    PROJECT_E_NOTE="$reason"
    print_skip "Project E - $reason"
  fi
  if [[ "$PROJECT_F_STATUS" == "PENDING" ]]; then
    PROJECT_F_STATUS="SKIPPED"
    PROJECT_F_NOTE="$reason"
    print_skip "Project F - $reason"
  fi
  if [[ "$PROJECT_B_STATUS" == "PENDING" ]]; then
    PROJECT_B_STATUS="SKIPPED"
    PROJECT_B_NOTE="$reason"
    print_skip "Project B - $reason"
  fi
  if [[ "$PROJECT_C_STATUS" == "PENDING" ]]; then
    PROJECT_C_STATUS="SKIPPED"
    PROJECT_C_NOTE="$reason"
    print_skip "Project C - $reason"
  fi
}

exit_hard_fail() {
  local reason="$1"
  HARD_GATE_RESULT="FAIL"
  set_pending_steps_skipped "$reason"
  write_summary
  print_fail "hard gate failed; summary written to ${SUMMARY_PATH}"
  exit 1
}

run_logged() {
  local label="$1"
  local log_path="$2"
  shift 2

  print_start "$label"
  if "$@" > "$log_path" 2>&1; then
    print_pass "$label"
    return 0
  else
    local rc=$?
    print_fail "$label (exit ${rc}; log: ${log_path})"
    return "$rc"
  fi
}

check_required_paths() {
  local label="$1"
  shift
  local missing=()
  local path

  for path in "$@"; do
    if [[ ! -e "$path" ]]; then
      missing+=("$path")
    fi
  done

  if [[ "${#missing[@]}" -eq 0 ]]; then
    return 0
  fi

  print_fail "${label} missing required output(s): ${missing[*]}"
  return 1
}

run_environment_check() {
  print_start "environment check"
  local missing=()
  local cmd

  for cmd in python3 cmake git nproc; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      missing+=("$cmd")
    fi
  done

  if [[ ! -d "$USER_SYSTEMC_LIB_DIR" ]]; then
    missing+=("USER_SYSTEMC_LIB_DIR=${USER_SYSTEMC_LIB_DIR}")
  fi
  if [[ ! -d "$USER_SYSTEMC_INCLUDE_DIR" ]]; then
    missing+=("USER_SYSTEMC_INCLUDE_DIR=${USER_SYSTEMC_INCLUDE_DIR}")
  fi

  if [[ "${#missing[@]}" -ne 0 ]]; then
    ENV_STATUS="FAIL"
    ENV_NOTE="missing or invalid: ${missing[*]}"
    print_fail "environment check - ${ENV_NOTE}"
    return 1
  fi

  ENV_STATUS="PASS"
  ENV_NOTE="python3, cmake, git, nproc, and SystemC paths available"
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    ENV_NOTE="${ENV_NOTE}; git metadata unavailable outside a Git worktree"
  fi
  print_pass "environment check"
}

run_lt_build() {
  local log_path="${LOG_DIR}/lt_build.log"
  print_start "LT build"

  if {
    cmake -S examples/lt -B build/examples/lt \
      -DUSER_SYSTEMC_LIB_DIR="$USER_SYSTEMC_LIB_DIR" \
      -DUSER_SYSTEMC_INCLUDE_DIR="$USER_SYSTEMC_INCLUDE_DIR"
    cmake --build build/examples/lt -j"$(nproc)"
  } > "$log_path" 2>&1; then
    LT_BUILD_STATUS="PASS"
    LT_BUILD_NOTE="log: ${log_path}"
    print_pass "LT build"
    return 0
  else
    local rc=$?
    LT_BUILD_STATUS="FAIL"
    LT_BUILD_NOTE="exit ${rc}; log: ${log_path}"
    print_fail "LT build (exit ${rc}; log: ${log_path})"
    return "$rc"
  fi
}

run_project_d() {
  local log_path="${LOG_DIR}/project_d.log"
  if run_logged "Project D C++ trace replay" "$log_path" \
    python3 examples/lt/tools/demo_cpp_trace_replay_lab.py &&
    check_required_paths "Project D" \
      "examples/lt/results/cpp_trace_replay_lab/trace.csv" \
      "$PROJECT_D_SUMMARY" \
      "examples/lt/results/cpp_trace_replay_lab/comparison.md"; then
    PROJECT_D_STATUS="PASS"
    PROJECT_D_NOTE="log: ${log_path}"
    return 0
  fi

  PROJECT_D_STATUS="FAIL"
  PROJECT_D_NOTE="command or output check failed; log: ${log_path}"
  return 1
}

run_project_e() {
  local log_path="${LOG_DIR}/project_e.log"
  if run_logged "Project E banked memory controller" "$log_path" \
    python3 examples/lt/tools/demo_banked_memory_controller_lab.py &&
    check_required_paths "Project E" \
      "examples/lt/results/project_e_banked_memory_controller/trace.csv" \
      "$PROJECT_E_SUMMARY" \
      "examples/lt/results/project_e_banked_memory_controller/comparison.md"; then
    PROJECT_E_STATUS="PASS"
    PROJECT_E_NOTE="log: ${log_path}"
    return 0
  fi

  PROJECT_E_STATUS="FAIL"
  PROJECT_E_NOTE="command or output check failed; log: ${log_path}"
  return 1
}

run_project_f() {
  local log_path="${LOG_DIR}/project_f.log"
  if run_logged "Project F stats trend correlation" "$log_path" \
    python3 examples/lt/tools/demo_gem5_stats_correlation_lab.py &&
    check_required_paths "Project F" \
      "$PROJECT_F_SUMMARY" \
      "examples/lt/results/project_f_gem5_stats_correlation/correlation_report.md"; then
    PROJECT_F_STATUS="PASS"
    PROJECT_F_NOTE="log: ${log_path}"
    return 0
  fi

  PROJECT_F_STATUS="FAIL"
  PROJECT_F_NOTE="command or output check failed; log: ${log_path}"
  return 1
}

run_project_b_optional() {
  local demo="examples/lt/tools/demo_trace_replay_lab.py"
  local log_path="${LOG_DIR}/project_b.log"

  if [[ ! -f "$demo" ]]; then
    print_start "Project B normalized trace replay optional"
    PROJECT_B_STATUS="SKIPPED"
    PROJECT_B_NOTE="optional demo wrapper not found"
    print_skip "Project B normalized trace replay - ${PROJECT_B_NOTE}"
    return 0
  fi

  if run_logged "Project B normalized trace replay optional" "$log_path" python3 "$demo" &&
    check_required_paths "Project B" \
      "examples/lt/results/trace_replay_lab/summary.csv" \
      "examples/lt/results/trace_replay_lab/comparison.md"; then
    PROJECT_B_STATUS="PASS"
    PROJECT_B_NOTE="optional soft check passed; log: ${log_path}"
    return 0
  fi

  PROJECT_B_STATUS="FAIL"
  PROJECT_B_NOTE="optional soft check failed; log: ${log_path}"
  return 0
}

run_project_c_optional() {
  local demo="examples/lt/tools/demo_gem5_se_trace_extraction_lab.py"
  local log_path="${LOG_DIR}/project_c.log"

  if [[ -f "$demo" ]]; then
    if run_logged "Project C gem5 SE extraction optional" "$log_path" python3 "$demo"; then
      PROJECT_C_STATUS="PASS"
      PROJECT_C_NOTE="optional demo wrapper passed; log: ${log_path}"
      return 0
    fi
    PROJECT_C_STATUS="FAIL"
    PROJECT_C_NOTE="optional demo wrapper failed; log: ${log_path}"
    return 0
  fi

  print_start "Project C gem5 SE extraction optional"

  local existing_count=0
  local missing=()
  local path

  for path in "${PROJECT_C_OUTPUTS[@]}"; do
    if [[ -e "$path" ]]; then
      existing_count=$((existing_count + 1))
    else
      missing+=("$path")
    fi
  done

  if [[ "$existing_count" -eq "${#PROJECT_C_OUTPUTS[@]}" ]]; then
    PROJECT_C_STATUS="PASS"
    PROJECT_C_NOTE="default Project C outputs found"
    print_pass "Project C gem5 SE extraction optional outputs"
    return 0
  fi

  if [[ "$existing_count" -eq 0 ]]; then
    PROJECT_C_STATUS="SKIPPED"
    PROJECT_C_NOTE="no one-command wrapper and default gem5 outputs are absent"
    print_skip "Project C gem5 SE extraction - ${PROJECT_C_NOTE}"
    return 0
  fi

  PROJECT_C_STATUS="FAIL"
  PROJECT_C_NOTE="partial Project C outputs; missing: ${missing[*]}"
  print_fail "Project C gem5 SE extraction optional - ${PROJECT_C_NOTE}"
  return 0
}

if ! is_repo_root; then
  print_fail "repo root check - run from repository root containing CMakeLists.txt, docs/, scripts/, tools/, and examples/lt/"
  exit 1
fi

mkdir -p "$LOG_DIR"

if ! run_environment_check; then
  exit_hard_fail "environment check failed"
fi

if ! run_lt_build; then
  exit_hard_fail "LT build failed"
fi

if ! run_project_d; then
  exit_hard_fail "Project D failed"
fi

if ! run_project_e; then
  exit_hard_fail "Project E failed"
fi

if ! run_project_f; then
  run_project_c_optional
  exit_hard_fail "Project F failed"
fi

run_project_b_optional
run_project_c_optional

write_summary
print_pass "headless regression hard gates complete; summary written to ${SUMMARY_PATH}"
