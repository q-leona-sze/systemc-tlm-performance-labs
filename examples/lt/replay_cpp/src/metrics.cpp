#include "replay_cpp/metrics.h"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

namespace replay_cpp {
namespace {

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

}  // namespace

SummaryRow summarize_workload(const std::vector<ReplayTraceRecord>& rows) {
  if (rows.empty()) {
    throw std::runtime_error("cannot summarize empty replay output");
  }

  const std::string workload_name = rows.front().workload_name;
  std::vector<double> latencies;
  std::vector<double> starts;
  std::vector<double> ends;
  latencies.reserve(rows.size());
  starts.reserve(rows.size());
  ends.reserve(rows.size());
  std::size_t bank_conflicts = 0;

  for (const auto& row : rows) {
    if (row.workload_name != workload_name) {
      throw std::runtime_error("summary input contains mixed workloads");
    }
    latencies.push_back(row.total_delay_ns);
    starts.push_back(row.start_time_ns);
    ends.push_back(row.end_time_ns);
    if (row.bank_conflict) {
      ++bank_conflicts;
    }
  }

  const auto min_start = *std::min_element(starts.begin(), starts.end());
  const auto max_end = *std::max_element(ends.begin(), ends.end());
  const double replay_window_ns = max_end - min_start;

  SummaryRow summary;
  summary.workload_name = workload_name;
  summary.num_transactions = rows.size();
  summary.avg_latency_ns = average(latencies);
  summary.p50_latency_ns = percentile(latencies, 50.0);
  summary.p95_latency_ns = percentile(latencies, 95.0);
  summary.p99_latency_ns = percentile(latencies, 99.0);
  summary.max_latency_ns = *std::max_element(latencies.begin(), latencies.end());
  summary.bank_conflict_ratio_pct =
      100.0 * static_cast<double>(bank_conflicts) / static_cast<double>(rows.size());
  summary.throughput_txn_per_us = 0.0;
  if (replay_window_ns > 0.0) {
    summary.throughput_txn_per_us =
        static_cast<double>(rows.size()) / (replay_window_ns / 1000.0);
  }

  return summary;
}

void validate_summary_rows(const std::vector<SummaryRow>& rows) {
  if (rows.empty()) {
    throw std::runtime_error("summary must contain at least one workload");
  }
  for (const auto& row : rows) {
    if (row.num_transactions == 0) {
      throw std::runtime_error(row.workload_name + " has no transactions");
    }
    if (!(row.p50_latency_ns <= row.p95_latency_ns &&
          row.p95_latency_ns <= row.p99_latency_ns &&
          row.p99_latency_ns <= row.max_latency_ns)) {
      throw std::runtime_error(row.workload_name + " percentile ordering failed");
    }
    if (row.bank_conflict_ratio_pct < 0.0 || row.bank_conflict_ratio_pct > 100.0) {
      throw std::runtime_error(row.workload_name +
                               " bank_conflict_ratio_pct out of range");
    }
    if (row.throughput_txn_per_us < 0.0) {
      throw std::runtime_error(row.workload_name +
                               " throughput_txn_per_us is negative");
    }
  }
}

}  // namespace replay_cpp
