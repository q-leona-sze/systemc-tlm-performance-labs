#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace project_h {

struct RawCsvTable {
  std::string source_path;
  std::vector<std::string> header;
  std::vector<std::vector<std::string>> rows;
};

struct TraceRequest {
  std::string workload;
  std::string txn_id;
  double timestamp_ns = 0.0;
  std::uint64_t issue_cycle = 0;
  std::string initiator_id;
  std::string command;
  std::uint64_t address = 0;
  int size_bytes = 0;
  std::string source_trace;
  std::size_t source_row_number = 0;
};

std::vector<TraceRequest> read_trace_requests(
    const std::filesystem::path& path,
    double cycle_time_ns);

}  // namespace project_h

