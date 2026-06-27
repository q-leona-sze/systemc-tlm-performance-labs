#include "project_e/csv.h"

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

namespace project_e {
namespace {

std::string trim_cr(std::string text) {
  if (!text.empty() && text.back() == '\r') {
    text.pop_back();
  }
  return text;
}

std::string trim(const std::string& text) {
  std::size_t begin = 0;
  while (begin < text.size() &&
         std::isspace(static_cast<unsigned char>(text[begin]))) {
    ++begin;
  }
  std::size_t end = text.size();
  while (end > begin &&
         std::isspace(static_cast<unsigned char>(text[end - 1]))) {
    --end;
  }
  return text.substr(begin, end - begin);
}

std::vector<std::string> parse_csv_line(const std::string& line,
                                        const std::string& path,
                                        std::size_t row_number) {
  std::vector<std::string> fields;
  std::string field;
  bool in_quotes = false;

  for (std::size_t index = 0; index < line.size(); ++index) {
    const char ch = line[index];
    if (ch == '"') {
      if (in_quotes && index + 1 < line.size() && line[index + 1] == '"') {
        field.push_back('"');
        ++index;
      } else {
        in_quotes = !in_quotes;
      }
      continue;
    }
    if (ch == ',' && !in_quotes) {
      fields.push_back(field);
      field.clear();
      continue;
    }
    field.push_back(ch);
  }

  if (in_quotes) {
    std::ostringstream message;
    message << path << " row " << row_number << ": unterminated quote";
    throw std::runtime_error(message.str());
  }

  fields.push_back(trim_cr(field));
  return fields;
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

}  // namespace

RawCsvTable read_csv_table(const std::filesystem::path& path) {
  std::ifstream input(path);
  if (!input) {
    throw std::runtime_error("trace not found: " + path.string());
  }

  RawCsvTable table;
  try {
    table.source_path =
        std::filesystem::relative(std::filesystem::absolute(path),
                                  std::filesystem::current_path()).string();
  } catch (const std::filesystem::filesystem_error&) {
    table.source_path = path.string();
  }

  std::string line;
  if (!std::getline(input, line)) {
    throw std::runtime_error("empty trace: " + path.string());
  }
  table.header = parse_csv_line(trim_cr(line), table.source_path, 1);
  if (table.header.empty()) {
    throw std::runtime_error("empty CSV header: " + table.source_path);
  }

  std::size_t row_number = 1;
  while (std::getline(input, line)) {
    ++row_number;
    line = trim_cr(line);
    if (trim(line).empty()) {
      continue;
    }
    table.rows.push_back(parse_csv_line(line, table.source_path, row_number));
  }

  if (table.rows.empty()) {
    throw std::runtime_error("empty trace: " + table.source_path);
  }

  return table;
}

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
                     const std::vector<TraceRow>& rows) {
  ensure_parent_dir(path);
  std::ofstream output(path);
  require_output_stream(output, path);

  output
      << "workload,txn_id,timestamp_ns,initiator_id,command,address,size_bytes,"
      << "bank_id,row_id,row_buffer_result,queue_occupancy_before,"
      << "queue_occupancy_after,queue_delay_ns,base_service_latency_ns,"
      << "row_latency_ns,service_latency_ns,start_service_ns,end_time_ns,"
      << "total_latency_ns,bank_busy_until_ns,response_status,source_trace\n";

  for (const auto& row : rows) {
    output << row.workload << ','
           << row.txn_id << ','
           << format_number(row.timestamp_ns) << ','
           << row.initiator_id << ','
           << row.command << ','
           << format_hex(row.address) << ','
           << row.size_bytes << ','
           << row.bank_id << ','
           << row.row_id << ','
           << row.row_buffer_result << ','
           << row.queue_occupancy_before << ','
           << row.queue_occupancy_after << ','
           << format_number(row.queue_delay_ns) << ','
           << format_number(row.base_service_latency_ns) << ','
           << format_number(row.row_latency_ns) << ','
           << format_number(row.service_latency_ns) << ','
           << format_number(row.start_service_ns) << ','
           << format_number(row.end_time_ns) << ','
           << format_number(row.total_latency_ns) << ','
           << format_number(row.bank_busy_until_ns) << ','
           << row.response_status << ','
           << row.source_trace << '\n';
  }
}

void write_summary_csv(const std::filesystem::path& path,
                       const std::vector<SummaryRow>& rows) {
  ensure_parent_dir(path);
  std::ofstream output(path);
  require_output_stream(output, path);

  output
      << "workload,bank_count,queue_depth,transactions,accepted_transactions,"
      << "avg_latency_ns,p95_latency_ns,p99_latency_ns,max_latency_ns,"
      << "throughput_txn_per_us,avg_queue_occupancy,max_queue_occupancy,"
      << "bank_utilization_pct,row_hit_ratio_pct,"
      << "stalled_or_rejected_transactions\n";

  for (const auto& row : rows) {
    output << row.workload << ','
           << row.bank_count << ','
           << row.queue_depth << ','
           << row.transactions << ','
           << row.accepted_transactions << ','
           << format_number(row.avg_latency_ns) << ','
           << format_number(row.p95_latency_ns) << ','
           << format_number(row.p99_latency_ns) << ','
           << format_number(row.max_latency_ns) << ','
           << format_number(row.throughput_txn_per_us) << ','
           << format_number(row.avg_queue_occupancy) << ','
           << row.max_queue_occupancy << ','
           << format_number(row.bank_utilization_pct) << ','
           << format_number(row.row_hit_ratio_pct) << ','
           << row.stalled_or_rejected_transactions << '\n';
  }
}

}  // namespace project_e
