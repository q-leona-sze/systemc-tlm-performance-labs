#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
cd "$repo_root"

python_bin="${PYTHON:-python3}"
cxx_bin="${CXX:-}"

resolve_run_id() {
  if [[ -n "${RUN_ID:-}" ]]; then
    echo "$RUN_ID"
    return
  fi

  local validation_root="artifacts/ubuntu-validation"
  if [[ ! -d "$validation_root" ]]; then
    echo "[project-validate] ERROR: RUN_ID is not set and ${validation_root}/ does not exist." >&2
    exit 2
  fi

  shopt -s nullglob
  local runs=("${validation_root}"/*)
  shopt -u nullglob

  if [[ "${#runs[@]}" -eq 0 ]]; then
    echo "[project-validate] ERROR: RUN_ID is not set and ${validation_root}/ has no runs." >&2
    exit 2
  fi

  local latest="${runs[0]}"
  local candidate
  for candidate in "${runs[@]}"; do
    if [[ -d "$candidate" && "$candidate" -nt "$latest" ]]; then
      latest="$candidate"
    fi
  done

  basename "$latest"
}

run_id="$(resolve_run_id)"
ubuntu_run_dir="artifacts/ubuntu-validation/${run_id}"
project_run_dir="artifacts/project-validation/${run_id}"
logs_dir="${project_run_dir}/logs"
results_dir="${project_run_dir}/results"
summary_path="${project_run_dir}/summary.md"

build_at_cxx17="${ubuntu_run_dir}/build-at-cxx17"
build_at_cxx20="${ubuntu_run_dir}/build-at-cxx20"
build_lt_cxx17="${ubuntu_run_dir}/build-lt-cxx17"
sample_trace="examples/lt/traces/sample_sequential_trace.csv"

mkdir -p "$logs_dir" "$results_dir"

summary_rows=()
fail_count=0

log_safe_name() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | tr -c '[:alnum:]_' '_'
}

append_result() {
  local check_name="$1"
  local status="$2"
  local exit_code="$3"
  local log_path="$4"
  local note="$5"

  summary_rows+=("| ${check_name} | ${status} | ${exit_code} | ${log_path} | ${note} |")
  if [[ "$status" == "FAIL" ]]; then
    fail_count=$((fail_count + 1))
  fi
}

find_binary() {
  local build_dir="$1"
  local binary_name="$2"

  if [[ ! -d "$build_dir" ]]; then
    return 0
  fi

  local found=""
  while IFS= read -r path; do
    found="$path"
    break
  done < <(find "$build_dir" -type f -name "$binary_name" -perm -111 2>/dev/null | sort)

  echo "$found"
}

runtime_env_prefix() {
  local standard="$1"
  local prefix=""

  if [[ "$standard" == "20" ]]; then
    prefix="${SYSTEMC_HOME_CXX20:-}"
  else
    prefix="${SYSTEMC_HOME:-}"
  fi

  if [[ -z "$prefix" ]]; then
    return 0
  fi

  echo "LD_LIBRARY_PATH=${prefix}/lib:${prefix}/lib64:${prefix}/lib-linux64:${LD_LIBRARY_PATH:-}"
  echo "DYLD_LIBRARY_PATH=${prefix}/lib:${prefix}/lib64:${prefix}/lib-linux64:${DYLD_LIBRARY_PATH:-}"
}

run_with_runtime_env() {
  local standard="$1"
  shift

  local env_args=()
  while IFS= read -r env_entry; do
    if [[ -n "$env_entry" ]]; then
      env_args+=("$env_entry")
    fi
  done < <(runtime_env_prefix "$standard")

  if [[ "${#env_args[@]}" -gt 0 ]]; then
    env "${env_args[@]}" "$@"
  else
    "$@"
  fi
}

record_skip() {
  local check_name="$1"
  local reason="$2"
  local log_path="${logs_dir}/$(log_safe_name "$check_name").log"

  {
    echo "check=${check_name}"
    echo "status=SKIP"
    echo "reason=${reason}"
  } > "$log_path"

  echo "[project-validate] SKIP ${check_name} - ${reason}"
  append_result "$check_name" "SKIP" "n/a" "$log_path" "$reason"
}

record_fail_without_run() {
  local check_name="$1"
  local reason="$2"
  local log_path="${logs_dir}/$(log_safe_name "$check_name").log"

  {
    echo "check=${check_name}"
    echo "status=FAIL"
    echo "reason=${reason}"
  } > "$log_path"

  echo "[project-validate] FAIL ${check_name} - ${reason}"
  append_result "$check_name" "FAIL" "n/a" "$log_path" "$reason"
}

run_project() {
  local check_name="$1"
  local standard="$2"
  local binary_path="$3"
  shift 3

  local log_path="${logs_dir}/$(log_safe_name "$check_name").log"
  local result_dir="${results_dir}/${check_name}"

  if [[ -z "$binary_path" ]]; then
    record_skip "$check_name" "binary not found in expected build artifact"
    return
  fi
  if [[ ! -x "$binary_path" ]]; then
    record_skip "$check_name" "binary is not executable: ${binary_path}"
    return
  fi

  mkdir -p "$result_dir"

  {
    echo "check=${check_name}"
    echo "binary=${binary_path}"
    echo "result_dir=${result_dir}"
    echo "standard=${standard}"
    echo "command=${binary_path} $*"
  } > "$log_path"

  echo "[project-validate] START ${check_name}"
  local rc=0
  if run_with_runtime_env "$standard" "$binary_path" "$@" >> "$log_path" 2>&1; then
    rc=0
    echo "[project-validate] PASS ${check_name}"
    append_result "$check_name" "PASS" "$rc" "$log_path" "runtime smoke completed"
  else
    rc=$?
    echo "[project-validate] FAIL ${check_name} (exit ${rc}; log: ${log_path})"
    append_result "$check_name" "FAIL" "$rc" "$log_path" "runtime smoke failed"
  fi
}

at_binary() {
  local standard="$1"
  local binary_name="$2"
  local build_dir="$build_at_cxx17"
  if [[ "$standard" == "20" ]]; then
    build_dir="$build_at_cxx20"
  fi

  find_binary "$build_dir" "$binary_name"
}

lt_binary() {
  local binary_name="$1"
  find_binary "$build_lt_cxx17" "$binary_name"
}

run_at_matrix_for_standard() {
  local standard="$1"
  local suffix="CXX17"
  if [[ "$standard" == "20" ]]; then
    suffix="CXX20"
  fi

  run_project "AT1_${suffix}" "$standard" "$(at_binary "$standard" project_at1_four_phase_memory_timing)" \
    --case-name "at1_${suffix}_smoke" \
    --pattern sequential \
    --num-transactions 8 \
    --queue-depth 4 \
    --service-latency-ns 10 \
    --issue-gap-ns 5 \
    --output-dir "${results_dir}/AT1_${suffix}"

  run_project "AT2_${suffix}" "$standard" "$(at_binary "$standard" project_at2_multi_initiator_arbitration)" \
    --case-name "at2_${suffix}_smoke" \
    --policy round_robin \
    --num-transactions-per-initiator 4 \
    --queue-depth 4 \
    --service-latency-ns 10 \
    --issue-gap-cpu-ns 3 \
    --issue-gap-dma-ns 4 \
    --issue-gap-accel-ns 5 \
    --output-dir "${results_dir}/AT2_${suffix}"

  run_project "AT3_${suffix}" "$standard" "$(at_binary "$standard" project_at3_qos_sensitivity_sla)" \
    --case-name "at3_${suffix}_smoke" \
    --weights 2,1,3 \
    --queue-depth 4 \
    --service-latency-ns 10 \
    --num-transactions-per-initiator 4 \
    --issue-gap-cpu-ns 3 \
    --issue-gap-dma-ns 4 \
    --issue-gap-accel-ns 5 \
    --burstiness-cpu 1 \
    --burstiness-dma 1 \
    --burstiness-accel 1 \
    --sla-cpu-ns 80 \
    --sla-dma-ns 120 \
    --sla-accel-ns 100 \
    --output-dir "${results_dir}/AT3_${suffix}"

  run_project "AT4_${suffix}" "$standard" "$(at_binary "$standard" project_at4_cache_mshr_pressure)" \
    --case-name "at4_${suffix}_smoke" \
    --num-transactions-per-initiator 4 \
    --mshr-capacity 2 \
    --cache-like-capacity 8 \
    --memory-service-latency-ns 20 \
    --hit-latency-ns 5 \
    --output-dir "${results_dir}/AT4_${suffix}"

  run_project "AT5_${suffix}" "$standard" "$(at_binary "$standard" project_at5_backpressure_qos_collapse)" \
    --case-name "at5_${suffix}_smoke" \
    --policy round_robin \
    --num-transactions-per-initiator 4 \
    --ingress-queue-capacity 4 \
    --downstream-queue-capacity 4 \
    --memory-service-latency-ns 20 \
    --service-rate-txn-per-us 5 \
    --cpu-rt-sla-target-ns 100 \
    --dma-bulk-sla-target-ns 150 \
    --accel-burst-sla-target-ns 120 \
    --output-dir "${results_dir}/AT5_${suffix}"

  run_project "AT6_${suffix}" "$standard" "$(at_binary "$standard" project_at6_heterogeneous_soc_fabric)" \
    --output-dir "${results_dir}/AT6_${suffix}" \
    --no-trace

  run_project "AT7_${suffix}" "$standard" "$(at_binary "$standard" project_at7_gpu_like_throughput_saturation)" \
    --output-dir "${results_dir}/AT7_${suffix}"

  run_project "AT8_${suffix}" "$standard" "$(at_binary "$standard" project_at8_amba_noc_qos_coherency_boundary)" \
    --output-dir "${results_dir}/AT8_${suffix}" \
    --no-trace
}

run_lt_validations() {
  if [[ ! -f "$sample_trace" ]]; then
    record_fail_without_run "LT_REPLAY_VALIDATE" "missing input trace: ${sample_trace}"
    record_fail_without_run "LT_BANKED_MEMORY_VALIDATE" "missing input trace: ${sample_trace}"
    return
  fi

  run_project "LT_REPLAY_VALIDATE" "none" "$(lt_binary replay_cpp)" \
    --trace "$sample_trace" \
    --output-dir "${results_dir}/LT_REPLAY_VALIDATE" \
    --validate-only

  run_project "LT_BANKED_MEMORY_VALIDATE" "none" "$(lt_binary banked_memory_controller)" \
    --trace "$sample_trace" \
    --output-dir "${results_dir}/LT_BANKED_MEMORY_VALIDATE" \
    --validate-only
}

write_summary() {
  {
    echo "# Project Runtime Validation Summary"
    echo
    echo "This artifact records runtime smoke checks that consume an existing Ubuntu"
    echo "validation build artifact. The script does not rebuild the repository and does"
    echo "not write to examples/at/results, examples/lt/results, docs/generated, or assets/portfolio."
    echo
    echo "## Run Metadata"
    echo
    echo "- Run ID: ${run_id}"
    echo "- Ubuntu validation artifact: ${ubuntu_run_dir}"
    echo "- Project validation artifact: ${project_run_dir}"
    echo "- BUILD_AT_CXX17: ${build_at_cxx17}"
    echo "- BUILD_AT_CXX20: ${build_at_cxx20}"
    echo "- BUILD_LT_CXX17: ${build_lt_cxx17}"
    echo "- PYTHON: ${python_bin}"
    echo "- CXX: ${cxx_bin}"
    echo "- SYSTEMC_HOME: ${SYSTEMC_HOME:-}"
    echo "- SYSTEMC_HOME_CXX20: ${SYSTEMC_HOME_CXX20:-}"
    echo
    echo "## Status"
    echo
    echo "| Check | Status | Exit Code | Log Path | Note |"
    echo "| --- | --- | --- | --- | --- |"
    local row
    for row in "${summary_rows[@]}"; do
      echo "$row"
    done
  } > "$summary_path"
}

echo "[project-validate] RUN_ID=${run_id}"
echo "[project-validate] ubuntu artifact: ${ubuntu_run_dir}"
echo "[project-validate] project artifact: ${project_run_dir}"

run_at_matrix_for_standard 17
run_at_matrix_for_standard 20
run_lt_validations
write_summary

echo "[project-validate] summary: ${summary_path}"
if [[ "$fail_count" -gt 0 ]]; then
  exit 1
fi
exit 0
