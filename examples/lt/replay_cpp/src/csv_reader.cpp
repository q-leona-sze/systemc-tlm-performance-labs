#include "replay_cpp/csv_reader.h"

#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace replay_cpp {
namespace {

std::string trim_cr(std::string text) {
  if (!text.empty() && text.back() == '\r') {
    text.pop_back();
  }
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
    message << path << " row " << row_number << ": malformed row: unterminated quote";
    throw std::runtime_error(message.str());
  }

  fields.push_back(trim_cr(field));
  return fields;
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
    if (line.empty()) {
      continue;
    }
    table.rows.push_back(parse_csv_line(line, table.source_path, row_number));
  }

  if (table.rows.empty()) {
    throw std::runtime_error("empty trace: " + table.source_path);
  }

  return table;
}

}  // namespace replay_cpp
