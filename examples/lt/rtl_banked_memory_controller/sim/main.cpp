#include "csv_reader.h"
#include "metrics.h"

#include "Vbanked_memory_controller.h"
#include "verilated.h"

#include <algorithm>
#include <cstdlib>
#include <cstdint>
#include <deque>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#ifndef PROJECT_H_BANK_COUNT
#define PROJECT_H_BANK_COUNT 4
#endif
#ifndef PROJECT_H_INTERLEAVE_BYTES
#define PROJECT_H_INTERLEAVE_BYTES 64
#endif
#ifndef PROJECT_H_SERVICE_LATENCY_CYCLES
#define PROJECT_H_SERVICE_LATENCY_CYCLES 10
#endif
#ifndef PROJECT_H_QUEUE_DEPTH
#define PROJECT_H_QUEUE_DEPTH 8
#endif

namespace {

struct Config {
  std::vector<std::filesystem::path> traces;
  std::filesystem::path output_dir =
      "examples/lt/results/project_h_verilator_rtl_golden_model";
  double cycle_time_ns = 1.0;
  std::uint64_t bank_count = PROJECT_H_BANK_COUNT;
  std::uint64_t interleave_bytes = PROJECT_H_INTERLEAVE_BYTES;
  std::uint64_t service_latency_cycles = PROJECT_H_SERVICE_LATENCY_CYCLES;
  std::uint64_t queue_depth = PROJECT_H_QUEUE_DEPTH;
};

struct TxnSortKey {
  bool numeric = false;
  long long numeric_value = 0;
  std::string text;
};

struct BankModelState {
  std::uint64_t busy_until_cycle = 0;
  std::deque<std::uint64_t> completion_cycles;
};

std::string display_path(const std::filesystem::path& path) {
  try {
    return std::filesystem::relative(std::filesystem::absolute(path),
                                     std::filesystem::current_path())
        .string();
  } catch (const std::filesystem::filesystem_error&) {
    return path.string();
  }
}

std::uint64_t parse_uint64_arg(const std::string& value,
                               const std::string& name) {
  if (value.empty() || value.front() == '-') {
    throw std::runtime_error(name + " must be a non-negative integer");
  }
  std::size_t parsed = 0;
  const auto result = std::stoull(value, &parsed, 0);
  if (parsed != value.size()) {
    throw std::runtime_error(name + " must be an integer: " + value);
  }
  return static_cast<std::uint64_t>(result);
}

double parse_double_arg(const std::string& value, const std::string& name) {
  std::size_t parsed = 0;
  const auto result = std::stod(value, &parsed);
  if (parsed != value.size()) {
    throw std::runtime_error(name + " must be numeric: " + value);
  }
  return result;
}

Config parse_args(int argc, char** argv) {
  Config config;
  for (int index = 1; index < argc; ++index) {
    const std::string arg = argv[index];
    auto require_value = [&](const std::string& name) -> std::string {
      if (index + 1 >= argc) {
        throw std::runtime_error(name + " requires a value");
      }
      ++index;
      return argv[index];
    };

    if (arg == "--trace") {
      config.traces.emplace_back(require_value(arg));
    } else if (arg == "--output-dir") {
      config.output_dir = require_value(arg);
    } else if (arg == "--cycle-time-ns") {
      config.cycle_time_ns = parse_double_arg(require_value(arg), arg);
    } else if (arg == "--bank-count") {
      config.bank_count = parse_uint64_arg(require_value(arg), arg);
    } else if (arg == "--interleave-bytes") {
      config.interleave_bytes = parse_uint64_arg(require_value(arg), arg);
    } else if (arg == "--service-latency-cycles") {
      config.service_latency_cycles = parse_uint64_arg(require_value(arg), arg);
    } else if (arg == "--queue-depth") {
      config.queue_depth = parse_uint64_arg(require_value(arg), arg);
    } else {
      throw std::runtime_error("unknown argument: " + arg);
    }
  }
  return config;
}

void validate_config(const Config& config) {
  if (config.traces.empty()) {
    throw std::runtime_error("at least one --trace is required");
  }
  if (config.cycle_time_ns <= 0.0) {
    throw std::runtime_error("--cycle-time-ns must be greater than zero");
  }
  if (config.bank_count == 0) {
    throw std::runtime_error("--bank-count must be greater than zero");
  }
  if (config.interleave_bytes == 0) {
    throw std::runtime_error("--interleave-bytes must be greater than zero");
  }
  if (config.service_latency_cycles == 0) {
    throw std::runtime_error("--service-latency-cycles must be greater than zero");
  }
  if (config.queue_depth == 0) {
    throw std::runtime_error("--queue-depth must be greater than zero");
  }

  if (config.bank_count != PROJECT_H_BANK_COUNT ||
      config.interleave_bytes != PROJECT_H_INTERLEAVE_BYTES ||
      config.service_latency_cycles != PROJECT_H_SERVICE_LATENCY_CYCLES ||
      config.queue_depth != PROJECT_H_QUEUE_DEPTH) {
    throw std::runtime_error(
        "runtime RTL parameters must match the Verilated build. Reconfigure "
        "CMake with PROJECT_H_BANK_COUNT, PROJECT_H_INTERLEAVE_BYTES, "
        "PROJECT_H_SERVICE_LATENCY_CYCLES, and PROJECT_H_QUEUE_DEPTH to change "
        "them.");
  }
}

TxnSortKey txn_sort_key(const std::string& txn_id) {
  TxnSortKey key;
  key.text = txn_id;
  char* end = nullptr;
  const long long value = std::strtoll(txn_id.c_str(), &end, 0);
  if (end != txn_id.c_str() && end != nullptr && *end == '\0') {
    key.numeric = true;
    key.numeric_value = value;
  }
  return key;
}

bool request_less(const project_h::TraceRequest& left,
                  const project_h::TraceRequest& right) {
  if (left.workload != right.workload) {
    return left.workload < right.workload;
  }
  if (left.issue_cycle != right.issue_cycle) {
    return left.issue_cycle < right.issue_cycle;
  }

  const TxnSortKey left_key = txn_sort_key(left.txn_id);
  const TxnSortKey right_key = txn_sort_key(right.txn_id);
  if (left_key.numeric != right_key.numeric) {
    return left_key.numeric;
  }
  if (left_key.numeric) {
    return left_key.numeric_value < right_key.numeric_value;
  }
  return left_key.text < right_key.text;
}

std::vector<std::string> workload_order(
    const std::vector<project_h::TraceRequest>& requests) {
  std::vector<std::string> order;
  std::unordered_map<std::string, bool> seen;
  for (const auto& request : requests) {
    if (!seen[request.workload]) {
      seen[request.workload] = true;
      order.push_back(request.workload);
    }
  }
  return order;
}

std::unordered_map<std::string, std::vector<project_h::TraceRequest>>
group_requests(const std::vector<project_h::TraceRequest>& requests) {
  std::unordered_map<std::string, std::vector<project_h::TraceRequest>> grouped;
  for (const auto& request : requests) {
    grouped[request.workload].push_back(request);
  }
  for (auto& pair : grouped) {
    auto& rows = pair.second;
    std::sort(rows.begin(), rows.end(), request_less);
    for (std::size_t index = 1; index < rows.size(); ++index) {
      if (rows[index].issue_cycle <= rows[index - 1].issue_cycle) {
        throw std::runtime_error(
            rows[index].workload +
            ": Project H MVP requires strictly increasing issue_cycle values "
            "within each workload because the RTL interface accepts one request "
            "per cycle");
      }
    }
  }
  return grouped;
}

std::uint64_t bank_id_for_address(std::uint64_t address, const Config& config) {
  return (address / config.interleave_bytes) % config.bank_count;
}

std::vector<project_h::TraceResultRow> run_aligned_model(
    const std::vector<project_h::TraceRequest>& requests,
    const Config& config) {
  const auto order = workload_order(requests);
  const auto grouped = group_requests(requests);
  std::vector<project_h::TraceResultRow> rows;

  for (const auto& workload : order) {
    std::vector<BankModelState> banks(config.bank_count);
    for (const auto& request : grouped.at(workload)) {
      const auto bank_id = bank_id_for_address(request.address, config);
      auto& bank = banks[bank_id];
      while (!bank.completion_cycles.empty() &&
             bank.completion_cycles.front() <= request.issue_cycle) {
        bank.completion_cycles.pop_front();
      }

      project_h::TraceResultRow row;
      row.workload = request.workload;
      row.txn_id = request.txn_id;
      row.issue_cycle = request.issue_cycle;
      row.address = request.address;
      row.bank_id = bank_id;

      if (bank.completion_cycles.size() >= config.queue_depth) {
        row.accepted = false;
        row.status = "REJECTED_QUEUE_FULL";
        rows.push_back(row);
        continue;
      }

      const auto service_start =
          std::max(request.issue_cycle, bank.busy_until_cycle);
      row.accepted = true;
      row.accepted_cycle = request.issue_cycle;
      row.done_cycle = service_start + config.service_latency_cycles;
      row.latency_cycles = row.done_cycle - row.accepted_cycle;
      row.status = "ACCEPTED";
      bank.busy_until_cycle = row.done_cycle;
      bank.completion_cycles.push_back(row.done_cycle);
      rows.push_back(row);
    }
  }

  return rows;
}

void reset_rtl(Vbanked_memory_controller& rtl) {
  rtl.valid = 0;
  rtl.addr = 0;
  rtl.is_write = 0;
  rtl.reset = 1;
  for (int count = 0; count < 2; ++count) {
    rtl.clk = 0;
    rtl.eval();
    rtl.clk = 1;
    rtl.eval();
  }
  rtl.clk = 0;
  rtl.eval();
  rtl.reset = 0;
  rtl.eval();
}

void tick(Vbanked_memory_controller& rtl) {
  rtl.clk = 0;
  rtl.eval();
  rtl.clk = 1;
  rtl.eval();
  rtl.clk = 0;
  rtl.eval();
}

std::vector<project_h::TraceResultRow> run_rtl(
    const std::vector<project_h::TraceRequest>& requests,
    const Config& config) {
  const auto order = workload_order(requests);
  const auto grouped = group_requests(requests);
  std::vector<project_h::TraceResultRow> rows;

  for (const auto& workload : order) {
    Vbanked_memory_controller rtl;
    reset_rtl(rtl);
    std::uint64_t current_cycle = 0;

    for (const auto& request : grouped.at(workload)) {
      while (current_cycle < request.issue_cycle) {
        rtl.valid = 0;
        tick(rtl);
        ++current_cycle;
      }

      rtl.valid = 1;
      rtl.addr = request.address;
      rtl.is_write = request.command == "WRITE" ? 1 : 0;
      rtl.eval();

      project_h::TraceResultRow row;
      row.workload = request.workload;
      row.txn_id = request.txn_id;
      row.issue_cycle = request.issue_cycle;
      row.address = request.address;
      row.bank_id = rtl.bank_id;

      if (rtl.ready) {
        row.accepted = true;
        row.accepted_cycle = current_cycle;
        row.latency_cycles = rtl.latency_cycles;
        row.done_cycle = row.accepted_cycle + row.latency_cycles;
        row.status = "ACCEPTED";
      } else {
        row.accepted = false;
        row.status = "REJECTED_QUEUE_FULL";
      }

      tick(rtl);
      ++current_cycle;
      rows.push_back(row);
    }
  }

  return rows;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    Verilated::commandArgs(argc, argv);
    const auto config = parse_args(argc, argv);
    validate_config(config);

    std::vector<project_h::TraceRequest> all_requests;
    for (const auto& trace_path : config.traces) {
      auto requests =
          project_h::read_trace_requests(trace_path, config.cycle_time_ns);
      std::cout << "[project-h] trace OK " << display_path(trace_path)
                << ": rows=" << requests.size() << "\n";
      all_requests.insert(all_requests.end(), requests.begin(), requests.end());
    }

    const auto model_rows = run_aligned_model(all_requests, config);
    const auto rtl_rows = run_rtl(all_requests, config);
    const auto model_summary = project_h::summarize_trace_results(
        model_rows, config.cycle_time_ns, config.service_latency_cycles);
    const auto rtl_summary = project_h::summarize_trace_results(
        rtl_rows, config.cycle_time_ns, config.service_latency_cycles);

    std::filesystem::create_directories(config.output_dir);
    const auto rtl_trace_path = config.output_dir / "rtl_trace.csv";
    const auto rtl_summary_path = config.output_dir / "rtl_summary.csv";
    const auto model_summary_path =
        config.output_dir / "model_summary_aligned.csv";
    project_h::write_trace_csv(rtl_trace_path, rtl_rows);
    project_h::write_summary_csv(rtl_summary_path, rtl_summary);
    project_h::write_summary_csv(model_summary_path, model_summary);

    std::cout << "[project-h] outputs\n"
              << "  - rtl_trace: " << display_path(rtl_trace_path) << "\n"
              << "  - rtl_summary: " << display_path(rtl_summary_path) << "\n"
              << "  - model_summary_aligned: "
              << display_path(model_summary_path) << "\n"
              << "[project-h] Project H Verilator RTL golden reference run PASS\n"
              << "[project-h] scope: local banked memory controller RTL "
                 "reference only; no full SoC, no AXI/CHI, no gem5-Verilator "
                 "live co-simulation, no silicon validation, no production "
                 "signoff, no full-system cycle-accuracy claim.\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "[project-h] ERROR: " << error.what() << "\n";
    return 1;
  }
}
