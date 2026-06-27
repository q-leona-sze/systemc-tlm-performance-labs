#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace replay_cpp {

constexpr const char* kMvpInitiatorId = "101";
constexpr const char* kMvpCommand = "READ";
constexpr int kMvpSizeBytes = 4;
constexpr double kTargetServiceDelayNs = 100.0;
constexpr double kBankConflictDelayNs = 20.0;

struct RawCsvTable {
  std::string source_path;
  std::vector<std::string> header;
  std::vector<std::vector<std::string>> rows;
};

struct NormalizedTraceRecord {
  std::string workload_name;
  std::string txn_id;
  double timestamp_ns = 0.0;
  std::string initiator_id;
  std::string command;
  std::uint64_t address = 0;
  int size_bytes = 0;
  std::string source_trace;
  std::size_t source_row_number = 0;
  int decoded_port = 0;
  int target_id = 0;
  std::uint64_t masked_address = 0;
};

struct ReplayTraceRecord {
  std::string workload_name;
  std::string txn_id;
  double timestamp_ns = 0.0;
  std::string initiator_id;
  std::string command;
  std::uint64_t address = 0;
  int size_bytes = 0;
  int target_id = 0;
  int decoded_port = 0;
  std::uint64_t masked_address = 0;
  int data_length = 0;
  double start_time_ns = 0.0;
  double delay_ns = 0.0;
  double end_time_ns = 0.0;
  double request_time_ns = 0.0;
  double bus_grant_time_ns = 0.0;
  double queue_delay_ns = 0.0;
  double target_service_delay_ns = 0.0;
  double total_delay_ns = 0.0;
  double target_busy_until_ns = 0.0;
  int bank_id = 0;
  bool bank_conflict = false;
  double bank_conflict_delay_ns = 0.0;
  std::string source_trace;
};

struct SummaryRow {
  std::string workload_name;
  std::size_t num_transactions = 0;
  double avg_latency_ns = 0.0;
  double p50_latency_ns = 0.0;
  double p95_latency_ns = 0.0;
  double p99_latency_ns = 0.0;
  double max_latency_ns = 0.0;
  double bank_conflict_ratio_pct = 0.0;
  double throughput_txn_per_us = 0.0;
};

}  // namespace replay_cpp
