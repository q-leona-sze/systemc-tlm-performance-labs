#include "replay_cpp/cli.h"

#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>

namespace replay_cpp {

void print_usage(const char* program) {
  std::cerr
      << "Usage: " << program
      << " --trace <normalized.csv> [--trace <normalized.csv> ...]\n"
      << "       [--output-dir <dir>] [--validate-only]\n\n"
      << "Standalone C++ normalized trace replay engine. This tool does not\n"
      << "connect to the SystemC kernel and does not run gem5 live co-simulation.\n";
}

ReplayConfig parse_cli(int argc, char** argv) {
  ReplayConfig config;
  for (int index = 1; index < argc; ++index) {
    const std::string arg = argv[index];
    if (arg == "--help" || arg == "-h") {
      print_usage(argv[0]);
      std::exit(0);
    }
    if (arg == "--trace") {
      if (index + 1 >= argc) {
        throw std::runtime_error("--trace requires a path");
      }
      config.traces.emplace_back(argv[++index]);
      continue;
    }
    if (arg == "--output-dir") {
      if (index + 1 >= argc) {
        throw std::runtime_error("--output-dir requires a path");
      }
      config.output_dir = argv[++index];
      continue;
    }
    if (arg == "--validate-only") {
      config.validate_only = true;
      continue;
    }
    throw std::runtime_error("unknown argument: " + arg);
  }

  if (config.traces.empty()) {
    config.traces = {
        "examples/lt/traces/sample_sequential_trace.csv",
        "examples/lt/traces/sample_stride_trace.csv",
    };
  }
  return config;
}

}  // namespace replay_cpp
