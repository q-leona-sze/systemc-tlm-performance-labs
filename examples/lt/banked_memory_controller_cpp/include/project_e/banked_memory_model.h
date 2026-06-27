#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace project_e {

struct ModelConfig {
  std::vector<std::filesystem::path> traces;
  std::filesystem::path output_dir =
      "examples/lt/results/project_e_banked_memory_controller";
  std::size_t bank_count = 4;
  std::size_t queue_depth = 16;
  std::uint64_t interleave_bytes = 4;
  std::uint64_t row_size_bytes = 64;
  double base_service_latency_ns = 20.0;
  double row_hit_latency_ns = 8.0;
  double row_miss_latency_ns = 40.0;
  double default_timestamp_step_ns = 100.0;
  std::string address_mapping = "word_interleave";
  bool validate_only = false;
};

struct MemoryRequest {
  std::string workload;
  std::string txn_id;
  double timestamp_ns = 0.0;
  std::string initiator_id = "101";
  std::string command = "READ";
  std::uint64_t address = 0;
  int size_bytes = 4;
  std::string source_trace;
  std::size_t source_row_number = 0;
};

struct TraceRow {
  std::string workload;
  std::string txn_id;
  double timestamp_ns = 0.0;
  std::string initiator_id;
  std::string command;
  std::uint64_t address = 0;
  int size_bytes = 0;
  std::size_t bank_id = 0;
  std::uint64_t row_id = 0;
  std::string row_buffer_result;
  std::size_t queue_occupancy_before = 0;
  std::size_t queue_occupancy_after = 0;
  double queue_delay_ns = 0.0;
  double base_service_latency_ns = 0.0;
  double row_latency_ns = 0.0;
  double service_latency_ns = 0.0;
  double start_service_ns = 0.0;
  double end_time_ns = 0.0;
  double total_latency_ns = 0.0;
  double bank_busy_until_ns = 0.0;
  std::string response_status;
  std::string source_trace;
};

struct SummaryRow {
  std::string workload;
  std::size_t bank_count = 0;
  std::size_t queue_depth = 0;
  std::size_t transactions = 0;
  std::size_t accepted_transactions = 0;
  double avg_latency_ns = 0.0;
  double p95_latency_ns = 0.0;
  double p99_latency_ns = 0.0;
  double max_latency_ns = 0.0;
  double throughput_txn_per_us = 0.0;
  double avg_queue_occupancy = 0.0;
  std::size_t max_queue_occupancy = 0;
  double bank_utilization_pct = 0.0;
  double row_hit_ratio_pct = 0.0;
  std::size_t stalled_or_rejected_transactions = 0;
};

struct ModelResult {
  std::vector<TraceRow> trace_rows;
  std::vector<SummaryRow> summary_rows;
};

std::vector<MemoryRequest> read_requests_from_trace(
    const std::filesystem::path& path,
    const ModelConfig& config);

ModelResult run_banked_memory_model(
    const std::vector<MemoryRequest>& requests,
    const ModelConfig& config);

void validate_config(const ModelConfig& config);

}  // namespace project_e
