#include "replay_cpp/trace_validator.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>

namespace replay_cpp {
namespace {

const char* const kRequiredFields[] = {
    "workload_name",
    "txn_id",
    "timestamp_ns",
    "initiator_id",
    "command",
    "address",
    "size_bytes",
};

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

std::unordered_map<std::string, std::size_t> header_index(const RawCsvTable& table) {
  std::unordered_map<std::string, std::size_t> index;
  for (std::size_t column = 0; column < table.header.size(); ++column) {
    index.emplace(trim(table.header[column]), column);
  }

  for (const char* field : kRequiredFields) {
    if (index.find(field) == index.end()) {
      throw std::runtime_error(table.source_path + " missing column: " + field);
    }
  }
  return index;
}

const std::string& value_at(const RawCsvTable& table,
                            const std::vector<std::string>& row,
                            const std::unordered_map<std::string, std::size_t>& index,
                            const std::string& field,
                            std::size_t row_index) {
  const auto iter = index.find(field);
  if (iter == index.end()) {
    throw std::runtime_error(table.source_path + " missing column: " + field);
  }
  if (iter->second >= row.size()) {
    throw std::runtime_error(row_context(table, row_index) + ": malformed row: missing " + field);
  }
  return row[iter->second];
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

bool sort_less(const NormalizedTraceRecord& left,
               const NormalizedTraceRecord& right) {
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

}  // namespace

std::vector<NormalizedTraceRecord> validate_trace_table(const RawCsvTable& table) {
  const auto index = header_index(table);
  std::vector<NormalizedTraceRecord> records;
  std::unordered_set<std::string> workload_names;
  std::unordered_set<std::string> txn_ids;

  for (std::size_t row_index = 0; row_index < table.rows.size(); ++row_index) {
    const auto& row = table.rows[row_index];
    if (row.size() < table.header.size()) {
      throw std::runtime_error(row_context(table, row_index) + ": malformed row: expected " +
                               std::to_string(table.header.size()) + " columns, got " +
                               std::to_string(row.size()));
    }

    const std::string context = row_context(table, row_index);
    NormalizedTraceRecord record;
    record.workload_name = trim(value_at(table, row, index, "workload_name", row_index));
    record.txn_id = trim(value_at(table, row, index, "txn_id", row_index));
    record.initiator_id = trim(value_at(table, row, index, "initiator_id", row_index));
    record.command = uppercase(trim(value_at(table, row, index, "command", row_index)));
    record.source_trace = table.source_path;
    record.source_row_number = row_index + 2;

    if (record.workload_name.empty()) {
      throw std::runtime_error(context + ": workload_name is empty");
    }
    if (record.txn_id.empty()) {
      throw std::runtime_error(context + ": txn_id is empty");
    }

    record.timestamp_ns = parse_double(
        value_at(table, row, index, "timestamp_ns", row_index), "timestamp_ns", context);
    if (record.timestamp_ns < 0.0) {
      throw std::runtime_error(context + ": timestamp_ns is negative");
    }

    if (record.initiator_id != kMvpInitiatorId) {
      throw std::runtime_error(context + ": MVP only supports initiator_id=" +
                               std::string(kMvpInitiatorId));
    }
    if (record.command != kMvpCommand) {
      throw std::runtime_error(context + ": unsupported command: " + record.command +
                               " (MVP only supports READ)");
    }

    record.address = parse_uint64(
        value_at(table, row, index, "address", row_index), "address", context);
    record.size_bytes = parse_int(
        value_at(table, row, index, "size_bytes", row_index), "size_bytes", context);
    if (record.size_bytes != kMvpSizeBytes) {
      throw std::runtime_error(context + ": MVP only supports size_bytes=4");
    }

    record.decoded_port = static_cast<int>(record.address >> 28);
    if (record.decoded_port != 0 && record.decoded_port != 1) {
      throw std::runtime_error(context + ": address decodes outside LT MVP targets");
    }
    record.target_id = 201 + record.decoded_port;
    record.masked_address = record.address & 0x0FFFFFFFULL;

    workload_names.insert(record.workload_name);
    if (!txn_ids.insert(record.txn_id).second) {
      throw std::runtime_error(table.source_path + " has duplicate txn_id: " + record.txn_id);
    }
    records.push_back(record);
  }

  if (records.empty()) {
    throw std::runtime_error("empty trace: " + table.source_path);
  }
  if (workload_names.size() != 1) {
    throw std::runtime_error(table.source_path + " must contain exactly one workload_name");
  }

  std::sort(records.begin(), records.end(), sort_less);
  return records;
}

}  // namespace replay_cpp
