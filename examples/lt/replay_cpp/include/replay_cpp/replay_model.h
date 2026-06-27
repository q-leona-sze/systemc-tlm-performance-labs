#pragma once

#include <vector>

#include "replay_cpp/trace_record.h"

namespace replay_cpp {

std::vector<ReplayTraceRecord> replay_records(
    const std::vector<NormalizedTraceRecord>& input_rows);

}  // namespace replay_cpp
