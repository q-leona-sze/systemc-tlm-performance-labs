#pragma once

#include <filesystem>
#include <string>
#include <vector>

namespace replay_cpp {

struct ReplayConfig {
  std::vector<std::filesystem::path> traces;
  std::filesystem::path output_dir = "examples/lt/results/cpp_trace_replay_lab";
  bool validate_only = false;
};

ReplayConfig parse_cli(int argc, char** argv);
void print_usage(const char* program);

}  // namespace replay_cpp
