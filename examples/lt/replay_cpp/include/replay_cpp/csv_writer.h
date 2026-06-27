#pragma once

#include <filesystem>
#include <string>
#include <vector>

#include "replay_cpp/trace_record.h"

namespace replay_cpp {

std::string format_number(double value);
std::string format_hex(std::uint64_t value);

void write_trace_csv(const std::filesystem::path& path,
                     const std::vector<ReplayTraceRecord>& rows);
void write_summary_csv(const std::filesystem::path& path,
                       const std::vector<SummaryRow>& rows);

}  // namespace replay_cpp
