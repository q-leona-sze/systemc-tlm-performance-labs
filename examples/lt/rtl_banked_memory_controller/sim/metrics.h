#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace project_h {

struct TraceResultRow {
  std::string workload;
  std::string txn_id;
  std::uint64_t issue_cycle = 0;
  bool accepted = false;
  std::uint64_t accepted_cycle = 0;
  std::uint64_t done_cycle = 0;
  std::string status;
  std::uint64_t address = 0;
  std::uint64_t bank_id = 0;
  std::uint64_t latency_cycles = 0;
};

struct SummaryRow {
  std::string workload;
  std::size_t total_requests = 0;
  std::size_t accepted_requests = 0;
  std::size_t rejected_requests = 0;
  double avg_latency_cycles = 0.0;
  double p50_latency_cycles = 0.0;
  double p95_latency_cycles = 0.0;
  double p99_latency_cycles = 0.0;
  double max_latency_cycles = 0.0;
  double avg_latency_ns = 0.0;
  double p50_latency_ns = 0.0;
  double p95_latency_ns = 0.0;
  double p99_latency_ns = 0.0;
  double max_latency_ns = 0.0;
  double throughput_txn_per_cycle = 0.0;
  double throughput_txn_per_us = 0.0;
  double bank_conflict_ratio_pct = 0.0;
};

std::vector<SummaryRow> summarize_trace_results(
    const std::vector<TraceResultRow>& rows,
    double cycle_time_ns,
    std::uint64_t service_latency_cycles);

void write_trace_csv(const std::filesystem::path& path,
                     const std::vector<TraceResultRow>& rows);

void write_summary_csv(const std::filesystem::path& path,
                       const std::vector<SummaryRow>& rows);

}  // namespace project_h

