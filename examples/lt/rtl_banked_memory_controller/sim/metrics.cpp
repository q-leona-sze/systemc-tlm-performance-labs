#include "metrics.h"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

namespace project_h {
namespace {

std::string format_number(double value) {
  std::ostringstream stream;
  stream << std::fixed << std::setprecision(3) << value;
  return stream.str();
}

std::string format_hex(std::uint64_t value) {
  std::ostringstream stream;
  stream << "0x" << std::uppercase << std::hex << std::setw(16)
         << std::setfill('0') << value;
  return stream.str();
}

std::string csv_escape(const std::string& value) {
  if (value.find_first_of(",\"\n\r") == std::string::npos) {
    return value;
  }
  std::string escaped = "\"";
  for (const char ch : value) {
    if (ch == '"') {
      escaped += "\"\"";
    } else {
      escaped += ch;
    }
  }
  escaped += '"';
  return escaped;
}

void ensure_parent_dir(const std::filesystem::path& path) {
  const auto parent = path.parent_path();
  if (!parent.empty()) {
    std::filesystem::create_directories(parent);
  }
}

void require_output_stream(const std::ofstream& output,
                           const std::filesystem::path& path) {
  if (!output) {
    throw std::runtime_error("failed to open output: " + path.string());
  }
}

double average(const std::vector<double>& values) {
  if (values.empty()) {
    return 0.0;
  }
  double sum = 0.0;
  for (const double value : values) {
    sum += value;
  }
  return sum / static_cast<double>(values.size());
}

long long python_round(double value) {
  const double floor_value = std::floor(value);
  const double fraction = value - floor_value;
  if (fraction > 0.5) {
    return static_cast<long long>(floor_value) + 1;
  }
  if (fraction < 0.5) {
    return static_cast<long long>(floor_value);
  }
  const auto floor_int = static_cast<long long>(floor_value);
  return (floor_int % 2 == 0) ? floor_int : floor_int + 1;
}

double percentile(std::vector<double> values, double percentile_value) {
  if (values.empty()) {
    return 0.0;
  }
  std::sort(values.begin(), values.end());
  if (values.size() == 1) {
    return values.front();
  }

  long long rank = python_round(
      (percentile_value / 100.0) * static_cast<double>(values.size() - 1));
  rank = std::max<long long>(0, std::min<long long>(rank, values.size() - 1));
  return values[static_cast<std::size_t>(rank)];
}

struct WorkloadAccum {
  std::vector<double> latencies;
  std::size_t total = 0;
  std::size_t accepted = 0;
  std::size_t rejected = 0;
  std::size_t bank_conflicts = 0;
  bool has_accepted = false;
  std::uint64_t first_accepted_cycle = 0;
  std::uint64_t last_done_cycle = 0;
};

}  // namespace

std::vector<SummaryRow> summarize_trace_results(
    const std::vector<TraceResultRow>& rows,
    double cycle_time_ns,
    std::uint64_t service_latency_cycles) {
  std::vector<std::string> workload_order;
  std::unordered_map<std::string, WorkloadAccum> by_workload;

  for (const auto& row : rows) {
    if (by_workload.find(row.workload) == by_workload.end()) {
      workload_order.push_back(row.workload);
    }
    auto& accum = by_workload[row.workload];
    ++accum.total;
    if (row.accepted) {
      ++accum.accepted;
      accum.latencies.push_back(static_cast<double>(row.latency_cycles));
      if (row.latency_cycles > service_latency_cycles) {
        ++accum.bank_conflicts;
      }
      if (!accum.has_accepted) {
        accum.first_accepted_cycle = row.accepted_cycle;
        accum.has_accepted = true;
      }
      accum.last_done_cycle = std::max(accum.last_done_cycle, row.done_cycle);
    } else {
      ++accum.rejected;
    }
  }

  std::vector<SummaryRow> summaries;
  for (const auto& workload : workload_order) {
    const auto& accum = by_workload.at(workload);
    SummaryRow summary;
    summary.workload = workload;
    summary.total_requests = accum.total;
    summary.accepted_requests = accum.accepted;
    summary.rejected_requests = accum.rejected;
    summary.avg_latency_cycles = average(accum.latencies);
    summary.p50_latency_cycles = percentile(accum.latencies, 50.0);
    summary.p95_latency_cycles = percentile(accum.latencies, 95.0);
    summary.p99_latency_cycles = percentile(accum.latencies, 99.0);
    summary.max_latency_cycles =
        accum.latencies.empty()
            ? 0.0
            : *std::max_element(accum.latencies.begin(), accum.latencies.end());
    summary.avg_latency_ns = summary.avg_latency_cycles * cycle_time_ns;
    summary.p50_latency_ns = summary.p50_latency_cycles * cycle_time_ns;
    summary.p95_latency_ns = summary.p95_latency_cycles * cycle_time_ns;
    summary.p99_latency_ns = summary.p99_latency_cycles * cycle_time_ns;
    summary.max_latency_ns = summary.max_latency_cycles * cycle_time_ns;
    if (accum.has_accepted) {
      const auto window_cycles = accum.last_done_cycle - accum.first_accepted_cycle;
      if (window_cycles > 0) {
        summary.throughput_txn_per_cycle =
            static_cast<double>(accum.accepted) /
            static_cast<double>(window_cycles);
        const double window_ns =
            static_cast<double>(window_cycles) * cycle_time_ns;
        if (window_ns > 0.0) {
          summary.throughput_txn_per_us =
              static_cast<double>(accum.accepted) / (window_ns / 1000.0);
        }
      }
    }
    if (accum.accepted > 0) {
      summary.bank_conflict_ratio_pct =
          100.0 * static_cast<double>(accum.bank_conflicts) /
          static_cast<double>(accum.accepted);
    }
    summaries.push_back(summary);
  }

  return summaries;
}

void write_trace_csv(const std::filesystem::path& path,
                     const std::vector<TraceResultRow>& rows) {
  ensure_parent_dir(path);
  std::ofstream output(path);
  require_output_stream(output, path);

  output << "workload,txn_id,issue_cycle,accepted_cycle,done_cycle,status,"
         << "address,bank_id,latency_cycles\n";

  for (const auto& row : rows) {
    output << csv_escape(row.workload) << ','
           << csv_escape(row.txn_id) << ','
           << row.issue_cycle << ',';
    if (row.accepted) {
      output << row.accepted_cycle << ',' << row.done_cycle << ',';
    } else {
      output << "NA,NA,";
    }
    output << row.status << ','
           << format_hex(row.address) << ','
           << row.bank_id << ',';
    if (row.accepted) {
      output << row.latency_cycles;
    } else {
      output << "NA";
    }
    output << '\n';
  }
}

void write_summary_csv(const std::filesystem::path& path,
                       const std::vector<SummaryRow>& rows) {
  ensure_parent_dir(path);
  std::ofstream output(path);
  require_output_stream(output, path);

  output << "workload,total_requests,accepted_requests,rejected_requests,"
         << "avg_latency_cycles,p50_latency_cycles,p95_latency_cycles,"
         << "p99_latency_cycles,max_latency_cycles,avg_latency_ns,"
         << "p50_latency_ns,p95_latency_ns,p99_latency_ns,max_latency_ns,"
         << "throughput_txn_per_cycle,throughput_txn_per_us,"
         << "bank_conflict_ratio_pct\n";

  for (const auto& row : rows) {
    output << csv_escape(row.workload) << ','
           << row.total_requests << ','
           << row.accepted_requests << ','
           << row.rejected_requests << ','
           << format_number(row.avg_latency_cycles) << ','
           << format_number(row.p50_latency_cycles) << ','
           << format_number(row.p95_latency_cycles) << ','
           << format_number(row.p99_latency_cycles) << ','
           << format_number(row.max_latency_cycles) << ','
           << format_number(row.avg_latency_ns) << ','
           << format_number(row.p50_latency_ns) << ','
           << format_number(row.p95_latency_ns) << ','
           << format_number(row.p99_latency_ns) << ','
           << format_number(row.max_latency_ns) << ','
           << format_number(row.throughput_txn_per_cycle) << ','
           << format_number(row.throughput_txn_per_us) << ','
           << format_number(row.bank_conflict_ratio_pct) << '\n';
  }
}

}  // namespace project_h

