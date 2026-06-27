#pragma once

#include <vector>

#include "replay_cpp/trace_record.h"

namespace replay_cpp {

SummaryRow summarize_workload(const std::vector<ReplayTraceRecord>& rows);
void validate_summary_rows(const std::vector<SummaryRow>& rows);

}  // namespace replay_cpp
