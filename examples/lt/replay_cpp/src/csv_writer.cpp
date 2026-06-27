#include "replay_cpp/csv_writer.h"

#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace replay_cpp {
namespace {

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

}  // namespace

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

void write_trace_csv(const std::filesystem::path& path,
                     const std::vector<ReplayTraceRecord>& rows) {
  ensure_parent_dir(path);
  std::ofstream output(path);
  require_output_stream(output, path);

  output
      << "workload_name,txn_id,timestamp_ns,initiator_id,command,address,size_bytes,"
      << "target_id,decoded_port,masked_address,data_length,data,start_time_ns,delay_ns,"
      << "end_time_ns,response_status,request_time_ns,bus_grant_time_ns,queue_delay_ns,"
      << "target_service_delay_ns,total_delay_ns,target_busy_until_ns,bank_id,"
      << "bank_conflict,bank_conflict_delay_ns,source_trace\n";

  for (const auto& row : rows) {
    output << row.workload_name << ','
           << row.txn_id << ','
           << format_number(row.timestamp_ns) << ','
           << row.initiator_id << ','
           << row.command << ','
           << format_hex(row.address) << ','
           << row.size_bytes << ','
           << row.target_id << ','
           << row.decoded_port << ','
           << format_hex(row.masked_address) << ','
           << row.data_length << ','
           << "0x00000000" << ','
           << format_number(row.start_time_ns) << ','
           << format_number(row.delay_ns) << ','
           << format_number(row.end_time_ns) << ','
           << "TLM_OK_RESPONSE" << ','
           << format_number(row.request_time_ns) << ','
           << format_number(row.bus_grant_time_ns) << ','
           << format_number(row.queue_delay_ns) << ','
           << format_number(row.target_service_delay_ns) << ','
           << format_number(row.total_delay_ns) << ','
           << format_number(row.target_busy_until_ns) << ','
           << row.bank_id << ','
           << (row.bank_conflict ? "1" : "0") << ','
           << format_number(row.bank_conflict_delay_ns) << ','
           << row.source_trace << '\n';
  }
}

void write_summary_csv(const std::filesystem::path& path,
                       const std::vector<SummaryRow>& rows) {
  ensure_parent_dir(path);
  std::ofstream output(path);
  require_output_stream(output, path);

  output
      << "workload_name,num_transactions,avg_latency_ns,p50_latency_ns,"
      << "p95_latency_ns,p99_latency_ns,max_latency_ns,"
      << "bank_conflict_ratio_pct,throughput_txn_per_us\n";

  for (const auto& row : rows) {
    output << row.workload_name << ','
           << row.num_transactions << ','
           << format_number(row.avg_latency_ns) << ','
           << format_number(row.p50_latency_ns) << ','
           << format_number(row.p95_latency_ns) << ','
           << format_number(row.p99_latency_ns) << ','
           << format_number(row.max_latency_ns) << ','
           << format_number(row.bank_conflict_ratio_pct) << ','
           << format_number(row.throughput_txn_per_us) << '\n';
  }
}

}  // namespace replay_cpp
