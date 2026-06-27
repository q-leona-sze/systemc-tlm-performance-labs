#include "replay_cpp/replay_model.h"

#include <unordered_map>

namespace replay_cpp {
namespace {

int bank_id_for_address(std::uint64_t masked_address) {
  return static_cast<int>((masked_address / static_cast<std::uint64_t>(kMvpSizeBytes)) % 4);
}

}  // namespace

std::vector<ReplayTraceRecord> replay_records(
    const std::vector<NormalizedTraceRecord>& input_rows) {
  std::unordered_map<int, int> last_bank_by_target;
  std::vector<ReplayTraceRecord> output_rows;
  output_rows.reserve(input_rows.size());

  for (const auto& input : input_rows) {
    ReplayTraceRecord output;
    output.workload_name = input.workload_name;
    output.txn_id = input.txn_id;
    output.timestamp_ns = input.timestamp_ns;
    output.initiator_id = input.initiator_id;
    output.command = input.command;
    output.address = input.address;
    output.size_bytes = input.size_bytes;
    output.target_id = input.target_id;
    output.decoded_port = input.decoded_port;
    output.masked_address = input.masked_address;
    output.data_length = input.size_bytes;
    output.start_time_ns = input.timestamp_ns;
    output.request_time_ns = output.start_time_ns;
    output.bus_grant_time_ns = output.start_time_ns;
    output.queue_delay_ns = 0.0;
    output.target_service_delay_ns = kTargetServiceDelayNs;
    output.bank_id = bank_id_for_address(input.masked_address);

    const auto last_bank = last_bank_by_target.find(input.decoded_port);
    output.bank_conflict =
        last_bank != last_bank_by_target.end() && last_bank->second == output.bank_id;
    last_bank_by_target[input.decoded_port] = output.bank_id;

    output.bank_conflict_delay_ns =
        output.bank_conflict ? kBankConflictDelayNs : 0.0;
    output.total_delay_ns = output.queue_delay_ns + output.target_service_delay_ns +
                            output.bank_conflict_delay_ns;
    output.delay_ns = output.total_delay_ns;
    output.end_time_ns = output.start_time_ns + output.total_delay_ns;
    output.target_busy_until_ns = output.end_time_ns;
    output.source_trace = input.source_trace;

    output_rows.push_back(output);
  }

  return output_rows;
}

}  // namespace replay_cpp
