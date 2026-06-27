#pragma once

#include <vector>

#include "replay_cpp/trace_record.h"

namespace replay_cpp {

std::vector<NormalizedTraceRecord> validate_trace_table(const RawCsvTable& table);

}  // namespace replay_cpp
