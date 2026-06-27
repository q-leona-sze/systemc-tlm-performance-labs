#include "project_e/cli.h"
#include "project_e/csv.h"
#include "project_e/banked_memory_model.h"

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
    const auto config = project_e::parse_cli(argc, argv);
    project_e::validate_config(config);

    std::vector<project_e::MemoryRequest> all_requests;
    for (const auto& trace_path : config.traces) {
      auto requests = project_e::read_requests_from_trace(trace_path, config);
      std::cout << "[project-e] trace OK " << display_path(trace_path)
                << ": rows=" << requests.size() << "\n";
      all_requests.insert(all_requests.end(), requests.begin(), requests.end());
    }

    if (config.validate_only) {
      std::cout << "[project-e] normalized trace compatibility PASS\n";
      return 0;
    }

    const auto result = project_e::run_banked_memory_model(all_requests, config);
    std::filesystem::create_directories(config.output_dir);
    const auto trace_output = config.output_dir / "trace.csv";
    const auto summary_output = config.output_dir / "summary.csv";
    project_e::write_trace_csv(trace_output, result.trace_rows);
    project_e::write_summary_csv(summary_output, result.summary_rows);

    std::cout << "[project-e] outputs\n"
              << "  - trace: " << display_path(trace_output) << "\n"
              << "  - summary: " << display_path(summary_output) << "\n"
              << "[project-e] Project E banked memory controller queueing model PASS\n"
              << "[project-e] scope: standalone C++ memory subsystem abstraction; "
                 "no SystemC kernel, no gem5 live co-simulation, no JEDEC DRAM "
                 "timing, no AXI/CHI/NoC protocol, no cycle-accuracy claim.\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "[project-e] ERROR: " << error.what() << "\n";
    return 1;
  }
}
