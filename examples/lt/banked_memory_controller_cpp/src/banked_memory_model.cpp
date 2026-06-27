#include "project_e/banked_memory_model.h"

#include "project_e/csv.h"

#include <algorithm>
#include <cmath>
#include <cctype>
#include <deque>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

namespace project_e {
namespace {

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

std::string uppercase(std::string text) {
  std::transform(text.begin(), text.end(), text.begin(), [](unsigned char ch) {
    return static_cast<char>(std::toupper(ch));
  });
  return text;
}

std::unordered_map<std::string, std::size_t> header_index(const RawCsvTable& table) {
  std::unordered_map<std::string, std::size_t> index;
  for (std::size_t column = 0; column < table.header.size(); ++column) {
    index.emplace(trim(table.header[column]), column);
  }
  return index;
}

bool has_field(const std::unordered_map<std::string, std::size_t>& index,
               const std::string& field) {
  return index.find(field) != index.end();
}

std::string field_or_default(const RawCsvTable& table,
                             const std::vector<std::string>& row,
                             const std::unordered_map<std::string, std::size_t>& index,
                             const std::string& field,
                             const std::string& default_value) {
  const auto iter = index.find(field);
  if (iter == index.end() || iter->second >= row.size()) {
    return default_value;
  }
  const std::string value = trim(row[iter->second]);
  (void)table;
  return value.empty() ? default_value : value;
}

std::string first_existing_field_or_default(
    const RawCsvTable& table,
    const std::vector<std::string>& row,
    const std::unordered_map<std::string, std::size_t>& index,
    const std::vector<std::string>& fields,
    const std::string& default_value) {
  for (const auto& field : fields) {
    if (has_field(index, field)) {
      return field_or_default(table, row, index, field, default_value);
    }
  }
  return default_value;
}

std::string row_context(const RawCsvTable& table, std::size_t row_index) {
  std::ostringstream context;
  context << table.source_path << " row " << (row_index + 2);
  return context.str();
}

double parse_double(const std::string& value,
                    const std::string& field,
                    const std::string& context) {
  const std::string text = trim(value);
  if (text.empty()) {
    throw std::runtime_error(context + ": " + field + " is empty");
  }
  std::size_t parsed = 0;
  try {
    const double result = std::stod(text, &parsed);
    if (parsed != text.size()) {
      throw std::runtime_error(context + ": " + field + " is not numeric: " + value);
    }
    return result;
  } catch (const std::invalid_argument&) {
    throw std::runtime_error(context + ": " + field + " is not numeric: " + value);
  } catch (const std::out_of_range&) {
    throw std::runtime_error(context + ": " + field + " is out of range: " + value);
  }
}

std::uint64_t parse_uint64(const std::string& value,
                           const std::string& field,
                           const std::string& context) {
  const std::string text = trim(value);
  if (text.empty()) {
    throw std::runtime_error(context + ": " + field + " is empty");
  }
  if (!text.empty() && text.front() == '-') {
    throw std::runtime_error(context + ": " + field + " is negative");
  }
  std::size_t parsed = 0;
  try {
    const auto result = std::stoull(text, &parsed, 0);
    if (parsed != text.size()) {
      throw std::runtime_error(context + ": " + field + " is not an integer: " + value);
    }
    return static_cast<std::uint64_t>(result);
  } catch (const std::invalid_argument&) {
    throw std::runtime_error(context + ": " + field + " is not an integer: " + value);
  } catch (const std::out_of_range&) {
    throw std::runtime_error(context + ": " + field + " is out of range: " + value);
  }
}

int parse_int(const std::string& value,
              const std::string& field,
              const std::string& context) {
  const auto parsed = parse_uint64(value, field, context);
  if (parsed > static_cast<std::uint64_t>(std::numeric_limits<int>::max())) {
    throw std::runtime_error(context + ": " + field + " is out of range: " + value);
  }
  return static_cast<int>(parsed);
}

struct TxnSortKey {
  bool numeric = false;
  long long numeric_value = 0;
  std::string text;
};

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

bool request_sort_less(const MemoryRequest& left, const MemoryRequest& right) {
  if (left.timestamp_ns != right.timestamp_ns) {
    return left.timestamp_ns < right.timestamp_ns;
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

std::size_t bank_id_for_address(std::uint64_t address, const ModelConfig& config) {
  if (config.address_mapping == "row_interleave") {
    return static_cast<std::size_t>(
        (address / config.row_size_bytes) % config.bank_count);
  }

  std::uint64_t unit = config.interleave_bytes;
  if (config.address_mapping == "cacheline_interleave") {
    unit = config.row_size_bytes;
  }
  if (unit == 0) {
    throw std::runtime_error("address mapping unit is zero");
  }
  return static_cast<std::size_t>((address / unit) % config.bank_count);
}

std::uint64_t row_id_for_address(std::uint64_t address, const ModelConfig& config) {
  return address / config.row_size_bytes;
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

struct BankState {
  double busy_until_ns = 0.0;
  double busy_time_ns = 0.0;
  bool has_open_row = false;
  std::uint64_t open_row = 0;
  std::deque<double> completion_times;
};

struct WorkloadAccum {
  std::vector<double> latencies;
  std::vector<double> queue_samples;
  std::size_t max_queue_occupancy = 0;
  std::size_t row_hits = 0;
  std::size_t row_misses = 0;
  std::size_t rejected = 0;
  std::size_t accepted = 0;
  double first_accepted_timestamp_ns = 0.0;
  double last_completion_ns = 0.0;
  bool has_accepted = false;
};

TraceRow make_base_trace_row(const MemoryRequest& request,
                             const ModelConfig& config) {
  TraceRow row;
  row.workload = request.workload;
  row.txn_id = request.txn_id;
  row.timestamp_ns = request.timestamp_ns;
  row.initiator_id = request.initiator_id;
  row.command = request.command;
  row.address = request.address;
  row.size_bytes = request.size_bytes;
  row.bank_id = bank_id_for_address(request.address, config);
  row.row_id = row_id_for_address(request.address, config);
  row.base_service_latency_ns = config.base_service_latency_ns;
  row.start_service_ns = request.timestamp_ns;
  row.end_time_ns = request.timestamp_ns;
  row.bank_busy_until_ns = request.timestamp_ns;
  row.source_trace = request.source_trace;
  return row;
}

SummaryRow summarize_workload(const std::string& workload,
                              std::size_t total_transactions,
                              const std::vector<BankState>& banks,
                              const WorkloadAccum& accum,
                              const ModelConfig& config) {
  SummaryRow summary;
  summary.workload = workload;
  summary.bank_count = config.bank_count;
  summary.queue_depth = config.queue_depth;
  summary.transactions = total_transactions;
  summary.accepted_transactions = accum.accepted;
  summary.avg_latency_ns = average(accum.latencies);
  summary.p95_latency_ns = percentile(accum.latencies, 95.0);
  summary.p99_latency_ns = percentile(accum.latencies, 99.0);
  summary.max_latency_ns =
      accum.latencies.empty()
          ? 0.0
          : *std::max_element(accum.latencies.begin(), accum.latencies.end());
  summary.throughput_txn_per_us = 0.0;

  if (accum.has_accepted) {
    const double window_ns =
        accum.last_completion_ns - accum.first_accepted_timestamp_ns;
    if (window_ns > 0.0) {
      summary.throughput_txn_per_us =
          static_cast<double>(accum.accepted) / (window_ns / 1000.0);
      double busy_time_ns = 0.0;
      for (const auto& bank : banks) {
        busy_time_ns += bank.busy_time_ns;
      }
      summary.bank_utilization_pct =
          100.0 * busy_time_ns /
          (static_cast<double>(config.bank_count) * window_ns);
      if (summary.bank_utilization_pct > 100.0) {
        summary.bank_utilization_pct = 100.0;
      }
    }
  }

  summary.avg_queue_occupancy = average(accum.queue_samples);
  summary.max_queue_occupancy = accum.max_queue_occupancy;
  const std::size_t row_accesses = accum.row_hits + accum.row_misses;
  if (row_accesses > 0) {
    summary.row_hit_ratio_pct =
        100.0 * static_cast<double>(accum.row_hits) /
        static_cast<double>(row_accesses);
  }
  summary.stalled_or_rejected_transactions = accum.rejected;
  return summary;
}

std::vector<MemoryRequest> sorted_workload_requests(
    std::vector<MemoryRequest> requests) {
  std::sort(requests.begin(), requests.end(), request_sort_less);
  return requests;
}

}  // namespace

void validate_config(const ModelConfig& config) {
  if (config.traces.empty()) {
    throw std::runtime_error("at least one --trace is required");
  }
  if (config.bank_count == 0) {
    throw std::runtime_error("--bank-count must be greater than zero");
  }
  if (config.queue_depth == 0) {
    throw std::runtime_error("--queue-depth must be greater than zero");
  }
  if (config.interleave_bytes == 0) {
    throw std::runtime_error("--interleave-bytes must be greater than zero");
  }
  if (config.row_size_bytes == 0) {
    throw std::runtime_error("--row-size-bytes must be greater than zero");
  }
  if (config.base_service_latency_ns < 0.0 ||
      config.row_hit_latency_ns < 0.0 ||
      config.row_miss_latency_ns < 0.0) {
    throw std::runtime_error("latency knobs must be non-negative");
  }
  if (config.default_timestamp_step_ns < 0.0) {
    throw std::runtime_error("--default-timestamp-step-ns must be non-negative");
  }
  if (config.address_mapping != "word_interleave" &&
      config.address_mapping != "cacheline_interleave" &&
      config.address_mapping != "row_interleave") {
    throw std::runtime_error(
        "--address-mapping must be word_interleave, cacheline_interleave, or "
        "row_interleave");
  }
}

std::vector<MemoryRequest> read_requests_from_trace(
    const std::filesystem::path& path,
    const ModelConfig& config) {
  const auto table = read_csv_table(path);
  const auto index = header_index(table);

  if (!has_field(index, "address") && !has_field(index, "masked_address")) {
    throw std::runtime_error(table.source_path +
                             " missing column: address or masked_address");
  }

  std::vector<MemoryRequest> requests;
  requests.reserve(table.rows.size());
  const std::string workload_default = path.stem().string();

  for (std::size_t row_index = 0; row_index < table.rows.size(); ++row_index) {
    const auto& row = table.rows[row_index];
    const std::string context = row_context(table, row_index);

    MemoryRequest request;
    request.workload = first_existing_field_or_default(
        table, row, index, {"workload", "workload_name"}, workload_default);
    request.txn_id = first_existing_field_or_default(
        table, row, index, {"txn_id", "transaction_id"},
        std::to_string(row_index + 1));
    request.initiator_id = field_or_default(
        table, row, index, "initiator_id", "101");
    request.command = uppercase(field_or_default(
        table, row, index, "command", "READ"));
    request.source_trace = table.source_path;
    request.source_row_number = row_index + 2;

    const std::string timestamp_value = field_or_default(
        table,
        row,
        index,
        "timestamp_ns",
        format_number(static_cast<double>(row_index) *
                      config.default_timestamp_step_ns));
    request.timestamp_ns = parse_double(timestamp_value, "timestamp_ns", context);
    if (request.timestamp_ns < 0.0) {
      throw std::runtime_error(context + ": timestamp_ns is negative");
    }

    const std::string address_value = first_existing_field_or_default(
        table, row, index, {"address", "masked_address"}, "");
    request.address = parse_uint64(address_value, "address", context);
    request.size_bytes = parse_int(field_or_default(
        table, row, index, "size_bytes", "4"), "size_bytes", context);
    if (request.size_bytes <= 0) {
      throw std::runtime_error(context + ": size_bytes must be positive");
    }
    if (request.command == "R") {
      request.command = "READ";
    } else if (request.command == "W") {
      request.command = "WRITE";
    }
    if (request.command != "READ" && request.command != "WRITE") {
      throw std::runtime_error(context + ": unsupported command: " +
                               request.command);
    }
    if (request.workload.empty()) {
      throw std::runtime_error(context + ": workload is empty");
    }
    if (request.txn_id.empty()) {
      throw std::runtime_error(context + ": txn_id is empty");
    }

    requests.push_back(request);
  }

  return requests;
}

ModelResult run_banked_memory_model(
    const std::vector<MemoryRequest>& requests,
    const ModelConfig& config) {
  std::unordered_map<std::string, std::vector<MemoryRequest>> by_workload;
  std::vector<std::string> workload_order;
  for (const auto& request : requests) {
    if (by_workload.find(request.workload) == by_workload.end()) {
      workload_order.push_back(request.workload);
    }
    by_workload[request.workload].push_back(request);
  }

  ModelResult result;

  for (const auto& workload : workload_order) {
    auto& workload_requests = by_workload.at(workload);
    auto sorted_requests = sorted_workload_requests(std::move(workload_requests));
    std::vector<BankState> banks(config.bank_count);
    WorkloadAccum accum;

    for (const auto& request : sorted_requests) {
      TraceRow row = make_base_trace_row(request, config);
      BankState& bank = banks[row.bank_id];

      while (!bank.completion_times.empty() &&
             bank.completion_times.front() <= request.timestamp_ns) {
        bank.completion_times.pop_front();
      }

      row.queue_occupancy_before = bank.completion_times.size();
      if (row.queue_occupancy_before >= config.queue_depth) {
        row.queue_occupancy_after = row.queue_occupancy_before;
        row.row_buffer_result = "rejected_queue_full";
        row.response_status = "REJECTED_QUEUE_FULL";
        row.bank_busy_until_ns = bank.busy_until_ns;
        accum.queue_samples.push_back(
            static_cast<double>(row.queue_occupancy_after));
        accum.max_queue_occupancy =
            std::max(accum.max_queue_occupancy, row.queue_occupancy_after);
        ++accum.rejected;
        result.trace_rows.push_back(row);
        continue;
      }

      const bool row_hit = bank.has_open_row && bank.open_row == row.row_id;
      row.row_buffer_result = row_hit ? "row_hit" : "row_miss";
      row.row_latency_ns =
          row_hit ? config.row_hit_latency_ns : config.row_miss_latency_ns;
      row.service_latency_ns =
          config.base_service_latency_ns + row.row_latency_ns;
      row.start_service_ns =
          std::max(request.timestamp_ns, bank.busy_until_ns);
      row.queue_delay_ns = row.start_service_ns - request.timestamp_ns;
      row.end_time_ns = row.start_service_ns + row.service_latency_ns;
      row.total_latency_ns = row.end_time_ns - request.timestamp_ns;
      row.bank_busy_until_ns = row.end_time_ns;
      row.response_status = "ACCEPTED";
      row.queue_occupancy_after = row.queue_occupancy_before + 1;

      bank.busy_until_ns = row.end_time_ns;
      bank.busy_time_ns += row.service_latency_ns;
      bank.has_open_row = true;
      bank.open_row = row.row_id;
      bank.completion_times.push_back(row.end_time_ns);

      accum.latencies.push_back(row.total_latency_ns);
      accum.queue_samples.push_back(
          static_cast<double>(row.queue_occupancy_after));
      accum.max_queue_occupancy =
          std::max(accum.max_queue_occupancy, row.queue_occupancy_after);
      if (row_hit) {
        ++accum.row_hits;
      } else {
        ++accum.row_misses;
      }
      ++accum.accepted;
      if (!accum.has_accepted) {
        accum.first_accepted_timestamp_ns = request.timestamp_ns;
        accum.has_accepted = true;
      }
      accum.last_completion_ns =
          std::max(accum.last_completion_ns, row.end_time_ns);

      result.trace_rows.push_back(row);
    }

    result.summary_rows.push_back(
        summarize_workload(workload, sorted_requests.size(), banks, accum, config));
  }

  return result;
}

}  // namespace project_e
