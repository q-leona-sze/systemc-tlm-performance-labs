#pragma once

#include <filesystem>

#include "replay_cpp/trace_record.h"

namespace replay_cpp {

RawCsvTable read_csv_table(const std::filesystem::path& path);

}  // namespace replay_cpp
