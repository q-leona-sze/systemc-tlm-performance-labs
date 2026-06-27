#include "csv_reader.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

namespace project_h {
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

std::string uppercase(std::string text) {
  std::transform(text.begin(), text.end(), text.begin(), [](unsigned char ch) {
    return static_cast<char>(std::toupper(ch));
  });
  return text;
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

RawCsvTable read_csv_table(const std::filesystem::path& path) {
  std::ifstream input(path);
  if (!input) {
    throw std::runtime_error("trace not found: " + path.string());
  }

  RawCsvTable table;
  try {
    table.source_path =
        std::filesystem::relative(std::filesystem::absolute(path),
                                  std::filesystem::current_path())
            .string();
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

std::unordered_map<std::string, std::size_t> header_index(
    const RawCsvTable& table) {
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

std::string field_or_default(
    const std::vector<std::string>& row,
    const std::unordered_map<std::string, std::size_t>& index,
    const std::string& field,
    const std::string& default_value) {
  const auto iter = index.find(field);
  if (iter == index.end() || iter->second >= row.size()) {
    return default_value;
  }
  const std::string value = trim(row[iter->second]);
  return value.empty() ? default_value : value;
}

std::string first_existing_field_or_default(
    const std::vector<std::string>& row,
    const std::unordered_map<std::string, std::size_t>& index,
    const std::vector<std::string>& fields,
    const std::string& default_value) {
  for (const auto& field : fields) {
    if (has_field(index, field)) {
      return field_or_default(row, index, field, default_value);
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
      throw std::runtime_error(context + ": " + field +
                               " is not numeric: " + value);
    }
    return result;
  } catch (const std::invalid_argument&) {
    throw std::runtime_error(context + ": " + field +
                             " is not numeric: " + value);
  } catch (const std::out_of_range&) {
    throw std::runtime_error(context + ": " + field +
                             " is out of range: " + value);
  }
}

std::uint64_t parse_uint64(const std::string& value,
                           const std::string& field,
                           const std::string& context) {
  const std::string text = trim(value);
  if (text.empty()) {
    throw std::runtime_error(context + ": " + field + " is empty");
  }
  if (text.front() == '-') {
    throw std::runtime_error(context + ": " + field + " is negative");
  }
  std::size_t parsed = 0;
  try {
    const auto result = std::stoull(text, &parsed, 0);
    if (parsed != text.size()) {
      throw std::runtime_error(context + ": " + field +
                               " is not an integer: " + value);
    }
    return static_cast<std::uint64_t>(result);
  } catch (const std::invalid_argument&) {
    throw std::runtime_error(context + ": " + field +
                             " is not an integer: " + value);
  } catch (const std::out_of_range&) {
    throw std::runtime_error(context + ": " + field +
                             " is out of range: " + value);
  }
}

int parse_int(const std::string& value,
              const std::string& field,
              const std::string& context) {
  const auto parsed = parse_uint64(value, field, context);
  if (parsed > static_cast<std::uint64_t>(std::numeric_limits<int>::max())) {
    throw std::runtime_error(context + ": " + field +
                             " is out of range: " + value);
  }
  return static_cast<int>(parsed);
}

std::uint64_t timestamp_to_cycle(double timestamp_ns,
                                 double cycle_time_ns,
                                 const std::string& context) {
  if (timestamp_ns < 0.0) {
    throw std::runtime_error(context + ": timestamp_ns is negative");
  }
  const double cycles = timestamp_ns / cycle_time_ns;
  const double nearest = std::round(cycles);
  const double tolerance = 1e-6;
  if (std::fabs(cycles - nearest) > tolerance) {
    std::ostringstream message;
    message << context << ": timestamp_ns / cycle_time_ns must be an integer "
            << "cycle; timestamp_ns=" << timestamp_ns
            << " cycle_time_ns=" << cycle_time_ns
            << " computed_cycles=" << cycles;
    throw std::runtime_error(message.str());
  }
  if (nearest < 0.0 ||
      nearest > static_cast<double>(std::numeric_limits<std::uint64_t>::max())) {
    throw std::runtime_error(context + ": issue cycle is out of range");
  }
  return static_cast<std::uint64_t>(nearest);
}

}  // namespace

std::vector<TraceRequest> read_trace_requests(
    const std::filesystem::path& path,
    double cycle_time_ns) {
  if (cycle_time_ns <= 0.0) {
    throw std::runtime_error("--cycle-time-ns must be greater than zero");
  }

  const auto table = read_csv_table(path);
  const auto index = header_index(table);
  if (!has_field(index, "timestamp_ns")) {
    throw std::runtime_error(table.source_path + " missing column: timestamp_ns");
  }
  if (!has_field(index, "address") && !has_field(index, "masked_address")) {
    throw std::runtime_error(table.source_path +
                             " missing column: address or masked_address");
  }

  const std::string workload_default = path.stem().string();
  std::vector<TraceRequest> requests;
  requests.reserve(table.rows.size());

  for (std::size_t row_index = 0; row_index < table.rows.size(); ++row_index) {
    const auto& row = table.rows[row_index];
    const std::string context = row_context(table, row_index);

    TraceRequest request;
    request.workload = first_existing_field_or_default(
        row, index, {"workload", "workload_name"}, workload_default);
    request.txn_id = first_existing_field_or_default(
        row, index, {"txn_id", "transaction_id"},
        std::to_string(row_index + 1));
    request.initiator_id = field_or_default(row, index, "initiator_id", "101");
    request.command = uppercase(field_or_default(row, index, "command", "READ"));
    if (request.command == "R") {
      request.command = "READ";
    } else if (request.command == "W") {
      request.command = "WRITE";
    }
    if (request.command != "READ" && request.command != "WRITE") {
      throw std::runtime_error(context + ": unsupported command: " +
                               request.command);
    }
    request.timestamp_ns =
        parse_double(field_or_default(row, index, "timestamp_ns", ""),
                     "timestamp_ns", context);
    request.issue_cycle =
        timestamp_to_cycle(request.timestamp_ns, cycle_time_ns, context);
    request.address = parse_uint64(
        first_existing_field_or_default(row, index, {"address", "masked_address"},
                                        ""),
        "address", context);
    request.size_bytes =
        parse_int(field_or_default(row, index, "size_bytes", "4"),
                  "size_bytes", context);
    if (request.size_bytes <= 0) {
      throw std::runtime_error(context + ": size_bytes must be positive");
    }
    if (request.workload.empty()) {
      throw std::runtime_error(context + ": workload is empty");
    }
    if (request.txn_id.empty()) {
      throw std::runtime_error(context + ": txn_id is empty");
    }
    request.source_trace = table.source_path;
    request.source_row_number = row_index + 2;
    requests.push_back(request);
  }

  return requests;
}

}  // namespace project_h

