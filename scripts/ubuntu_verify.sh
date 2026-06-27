#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
cd "$repo_root"

run_id="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
run_dir="artifacts/ubuntu-validation/${run_id}"
python_bin="${PYTHON:-python3}"
cxx_bin="${CXX:-g++}"
jobs="${JOBS:-}"
requested_standard="${SCTL_CXX_STANDARD:-17}"

if [[ -z "$jobs" ]]; then
  if command -v nproc >/dev/null 2>&1; then
    jobs="$(nproc)"
  else
    jobs="2"
  fi
fi

if [[ -e "$run_dir" ]]; then
  echo "[ubuntu-verify] ERROR: run directory already exists: $run_dir" >&2
  echo "[ubuntu-verify] Choose a different RUN_ID; existing artifacts are preserved." >&2
  exit 2
fi

mkdir -p "$run_dir/logs" "$run_dir/pycache"

lt_cxx17="PENDING"
at_cxx17="SKIP"
at_cxx20="SKIP"
python_compile="PENDING"
sensitive_scan="PENDING"
unit_smoke="SKIP"

cmake_toolchain_args=()
if [[ -n "${CC:-}" ]]; then
  cmake_toolchain_args+=("-DCMAKE_C_COMPILER=${CC}")
fi
if [[ -n "${CXX:-}" ]]; then
  cmake_toolchain_args+=("-DCMAKE_CXX_COMPILER=${CXX}")
fi

systemc_args=()
for variable_name in SystemC_DIR SYSTEMC_ROOT SYSTEMC_HOME USER_SYSTEMC_ROOT USER_SYSTEMC_INCLUDE_DIR USER_SYSTEMC_LIB_DIR CMAKE_PREFIX_PATH; do
  variable_value="${!variable_name-}"
  if [[ -n "$variable_value" ]]; then
    systemc_args+=("-D${variable_name}=${variable_value}")
  fi
done

write_environment() {
  {
    echo "# Ubuntu Verification Environment"
    echo
    echo "run_id=${run_id}"
    echo "repo_root=${repo_root}"
    echo "requested_sctl_cxx_standard=${requested_standard}"
    echo "SystemC_DIR=${SystemC_DIR:-}"
    echo "SYSTEMC_HOME=${SYSTEMC_HOME:-}"
    echo "SYSTEMC_HOME_CXX20=${SYSTEMC_HOME_CXX20:-}"
    echo "SYSTEMC_ROOT=${SYSTEMC_ROOT:-}"
    echo "USER_SYSTEMC_ROOT=${USER_SYSTEMC_ROOT:-}"
    echo "USER_SYSTEMC_INCLUDE_DIR=${USER_SYSTEMC_INCLUDE_DIR:-}"
    echo "USER_SYSTEMC_LIB_DIR=${USER_SYSTEMC_LIB_DIR:-}"
    echo "CMAKE_PREFIX_PATH=${CMAKE_PREFIX_PATH:-}"
    echo "CC=${CC:-}"
    echo "CXX=${CXX:-}"
    echo "PYTHON=${PYTHON:-}"
    echo
    echo "## Platform"
    lsb_release -a 2>&1 || true
    uname -a
    echo
    echo "## Toolchain"
    cmake --version 2>&1 || true
    "$cxx_bin" --version 2>&1 || true
    "$python_bin" --version 2>&1 || true
  } > "$run_dir/environment.txt"
}

run_lt_cxx17() {
  local build_dir="$run_dir/build-lt-cxx17"
  local log_path="$run_dir/logs/lt-cxx17.log"

  echo "[ubuntu-verify] START LT_CXX17"
  if ! cmake -S . -B "$build_dir" \
    -DBUILD_LT_LABS=ON \
    -DBUILD_AT_LABS=OFF \
    -DBUILD_RTL_REFERENCE=OFF \
    -DSCTL_CXX_STANDARD=17 \
    "${cmake_toolchain_args[@]}" > "$log_path" 2>&1; then
    lt_cxx17="FAIL"
    echo "[ubuntu-verify] FAIL LT_CXX17 (configure; $log_path)"
    return
  fi
  if ! cmake --build "$build_dir" --parallel "$jobs" >> "$log_path" 2>&1; then
    lt_cxx17="FAIL"
    echo "[ubuntu-verify] FAIL LT_CXX17 (build; $log_path)"
    return
  fi
  lt_cxx17="PASS"
  echo "[ubuntu-verify] PASS LT_CXX17"
}

run_at_build() {
  local standard="$1"
  local build_dir="$run_dir/build-at-cxx${standard}"
  local log_path="$run_dir/logs/at-cxx${standard}.log"
  local status_name=""
  local systemc_args_for_build=()

  if [[ "$standard" == "17" ]]; then
    status_name="at_cxx17"
    systemc_args_for_build=("${systemc_args[@]}")
  else
    status_name="at_cxx20"
    if [[ -z "${SYSTEMC_HOME_CXX20:-}" ]]; then
      at_cxx20="SKIP"
      echo "[ubuntu-verify] SKIP AT_CXX20_SYSTEMC (SYSTEMC_HOME_CXX20 not set; rebuild SystemC with C++20 and set SYSTEMC_HOME_CXX20 to avoid ABI mismatch)"
      return
    fi
    systemc_args_for_build=("-DSYSTEMC_HOME=${SYSTEMC_HOME_CXX20}")
  fi

  echo "[ubuntu-verify] START AT_CXX${standard}_SYSTEMC"
  if ! cmake -S . -B "$build_dir" \
    -DBUILD_LT_LABS=ON \
    -DBUILD_AT_LABS=ON \
    -DBUILD_RTL_REFERENCE=OFF \
    -DSCTL_CXX_STANDARD="$standard" \
    "${cmake_toolchain_args[@]}" \
    "${systemc_args_for_build[@]}" > "$log_path" 2>&1; then
    if grep -q "SystemC not found" "$log_path"; then
      printf -v "$status_name" '%s' "SKIP"
      echo "[ubuntu-verify] SKIP AT_CXX${standard}_SYSTEMC (SystemC unavailable; $log_path)"
    else
      printf -v "$status_name" '%s' "FAIL"
      echo "[ubuntu-verify] FAIL AT_CXX${standard}_SYSTEMC (configure; $log_path)"
    fi
    return
  fi
  if ! cmake --build "$build_dir" --parallel "$jobs" >> "$log_path" 2>&1; then
    printf -v "$status_name" '%s' "FAIL"
    echo "[ubuntu-verify] FAIL AT_CXX${standard}_SYSTEMC (build; $log_path)"
    return
  fi
  printf -v "$status_name" '%s' "PASS"
  echo "[ubuntu-verify] PASS AT_CXX${standard}_SYSTEMC"
}

run_python_compile() {
  local log_path="$run_dir/logs/python-compile.log"
  echo "[ubuntu-verify] START PYTHON_COMPILE"
  if PYTHONPYCACHEPREFIX="$run_dir/pycache" "$python_bin" -m compileall scripts tools examples > "$log_path" 2>&1; then
    python_compile="PASS"
    echo "[ubuntu-verify] PASS PYTHON_COMPILE"
  else
    python_compile="FAIL"
    echo "[ubuntu-verify] FAIL PYTHON_COMPILE ($log_path)"
  fi
}

run_unit_smoke_if_present() {
  local log_path="$run_dir/logs/unittest-smoke.log"
  if [[ ! -d smoke_tests ]]; then
    return
  fi

  echo "[ubuntu-verify] START UNIT_SMOKE"
  if PYTHONPYCACHEPREFIX="$run_dir/pycache" "$python_bin" -m unittest discover -s smoke_tests -v > "$log_path" 2>&1; then
    unit_smoke="PASS"
    echo "[ubuntu-verify] PASS UNIT_SMOKE"
  else
    unit_smoke="FAIL"
    echo "[ubuntu-verify] FAIL UNIT_SMOKE ($log_path)"
  fi
}

run_sensitive_scan() {
  local result_path="$run_dir/sensitive_scan.txt"
  echo "[ubuntu-verify] START SENSITIVE_SCAN"
  if grep -R --exclude=ubuntu_verify.sh --exclude-dir=artifacts --exclude-dir=.git -nE \
    'icy-leo-sze|icy-leo|/Users/|/home/leo|valentine' \
    . > "$result_path" 2>&1; then
    sensitive_scan="FAIL"
    echo "[ubuntu-verify] FAIL SENSITIVE_SCAN ($result_path)"
  else
    sensitive_scan="PASS"
    echo "[ubuntu-verify] PASS SENSITIVE_SCAN"
  fi
}

write_summary() {
  {
    echo "# Ubuntu Modern Toolchain Verification Summary"
    echo
    echo "This artifact records the host that ran the script. It is not an assertion that"
    echo "another platform completed validation."
    echo
    echo "## Environment"
    echo
    echo "- Run ID: ${run_id}"
    echo "- Requested C++ standard: ${requested_standard}"
    echo "- Environment capture: environment.txt"
    echo
    echo "## SystemC ABI Notes"
    echo
    echo "- AT_CXX17_SYSTEMC uses SYSTEMC_HOME and compatible legacy SystemC inputs."
    echo "- AT_CXX20_SYSTEMC uses SYSTEMC_HOME_CXX20 if provided."
    echo "- SystemC ABI must match the consuming target C++ standard."
    echo
    echo "## Status"
    echo
    echo "| Check | Status |"
    echo "| --- | --- |"
    echo "| LT_CXX17 | ${lt_cxx17} |"
    echo "| AT_CXX17_SYSTEMC | ${at_cxx17} |"
    echo "| AT_CXX20_SYSTEMC | ${at_cxx20} |"
    echo "| PYTHON_COMPILE | ${python_compile} |"
    echo "| UNIT_SMOKE | ${unit_smoke} |"
    echo "| SENSITIVE_SCAN | ${sensitive_scan} |"
    echo
    echo "## Artifact Policy"
    echo
    echo "All generated build trees, logs, Python bytecode, and scan output for this run"
    echo "are contained under ${run_dir}/."
  } > "$run_dir/summary.md"
}

write_environment
run_lt_cxx17
run_at_build 17
if [[ "$at_cxx17" == "PASS" ]]; then
  run_at_build 20
else
  echo "[ubuntu-verify] SKIP AT_CXX20_SYSTEMC (AT_CXX17_SYSTEMC did not pass)"
fi
run_python_compile
run_unit_smoke_if_present
run_sensitive_scan
write_summary

overall_result=0
for status in "$lt_cxx17" "$at_cxx17" "$at_cxx20" "$python_compile" "$unit_smoke" "$sensitive_scan"; do
  if [[ "$status" == "FAIL" ]]; then
    overall_result=1
  fi
done

echo "[ubuntu-verify] summary: $run_dir/summary.md"
exit "$overall_result"
