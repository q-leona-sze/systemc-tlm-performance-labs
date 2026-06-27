#include "replay_cpp/cli.h"
#include "replay_cpp/csv_reader.h"
#include "replay_cpp/csv_writer.h"
#include "replay_cpp/metrics.h"
#include "replay_cpp/replay_model.h"
#include "replay_cpp/trace_validator.h"

#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace {

std::string display_path(const std::filesystem::path& path) {
  return path.lexically_normal().string();
}

}  // namespace

int main(int argc, char** argv) {
  try {
    const auto config = replay_cpp::parse_cli(argc, argv);

    std::vector<replay_cpp::ReplayTraceRecord> all_output_rows;
    std::vector<replay_cpp::SummaryRow> summary_rows;
    for (const auto& trace_path : config.traces) {
      const auto table = replay_cpp::read_csv_table(trace_path);
      const auto input_rows = replay_cpp::validate_trace_table(table);
      std::cout << "[validate] OK " << display_path(trace_path)
                << ": workload=" << input_rows.front().workload_name
                << " rows=" << input_rows.size() << "\n";

      if (!config.validate_only) {
        auto output_rows = replay_cpp::replay_records(input_rows);
        summary_rows.push_back(replay_cpp::summarize_workload(output_rows));
        all_output_rows.insert(all_output_rows.end(),
                               output_rows.begin(),
                               output_rows.end());
      }
    }

    if (config.validate_only) {
      std::cout << "[validate] C++ normalized trace schema PASS\n";
      return 0;
    }

    replay_cpp::validate_summary_rows(summary_rows);

    std::filesystem::create_directories(config.output_dir);
    const auto trace_output = config.output_dir / "trace.csv";
    const auto summary_output = config.output_dir / "summary.csv";
    replay_cpp::write_trace_csv(trace_output, all_output_rows);
    replay_cpp::write_summary_csv(summary_output, summary_rows);

    std::cout << "[replay-cpp] outputs\n"
              << "  - trace: " << display_path(trace_output) << "\n"
              << "  - summary: " << display_path(summary_output) << "\n"
              << "[replay-cpp] Project D standalone C++ trace replay PASS\n"
              << "[replay-cpp] scope: standalone C++ replay only; no SystemC "
                 "kernel, no gem5 live co-simulation, no cycle-accuracy claim.\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "[replay-cpp] ERROR: " << error.what() << "\n";
    return 1;
  }
}
