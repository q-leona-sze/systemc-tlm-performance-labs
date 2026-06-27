#pragma once

#include "project_e/banked_memory_model.h"

#include <filesystem>
#include <string>
#include <vector>

namespace project_e {

struct RawCsvTable {
  std::string source_path;
  std::vector<std::string> header;
  std::vector<std::vector<std::string>> rows;
};

RawCsvTable read_csv_table(const std::filesystem::path& path);
void write_trace_csv(const std::filesystem::path& path,
                     const std::vector<TraceRow>& rows);
void write_summary_csv(const std::filesystem::path& path,
                       const std::vector<SummaryRow>& rows);
std::string format_number(double value);
std::string format_hex(std::uint64_t value);

}  // namespace project_e
