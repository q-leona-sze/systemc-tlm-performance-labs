#include "project_e/cli.h"

#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>

namespace project_e {
namespace {

std::size_t parse_size(const std::string& value, const std::string& option) {
  std::size_t parsed = 0;
  const unsigned long long result = std::stoull(value, &parsed, 0);
  if (parsed != value.size()) {
    throw std::runtime_error(option + " is not an integer: " + value);
  }
  return static_cast<std::size_t>(result);
}

std::uint64_t parse_u64(const std::string& value, const std::string& option) {
  std::size_t parsed = 0;
  const unsigned long long result = std::stoull(value, &parsed, 0);
  if (parsed != value.size()) {
    throw std::runtime_error(option + " is not an integer: " + value);
  }
  return static_cast<std::uint64_t>(result);
}

double parse_double(const std::string& value, const std::string& option) {
  std::size_t parsed = 0;
  const double result = std::stod(value, &parsed);
  if (parsed != value.size()) {
    throw std::runtime_error(option + " is not numeric: " + value);
  }
  return result;
}

std::string next_value(int& index,
                       int argc,
                       char** argv,
                       const std::string& option) {
  if (index + 1 >= argc) {
    throw std::runtime_error(option + " requires a value");
  }
  return argv[++index];
}

}  // namespace

void print_usage(const char* program) {
  std::cerr
      << "Usage: " << program
      << " --trace <normalized.csv> [--trace <normalized.csv> ...]\n"
      << "       [--output-dir <dir>] [--bank-count <n>] [--queue-depth <n>]\n"
      << "       [--address-mapping word_interleave|cacheline_interleave|row_interleave]\n"
      << "       [--base-service-latency-ns <ns>] [--row-hit-latency-ns <ns>]\n"
      << "       [--row-miss-latency-ns <ns>] [--row-size-bytes <bytes>]\n"
      << "       [--interleave-bytes <bytes>] [--validate-only]\n\n"
      << "Project E standalone C++ banked memory controller queueing model.\n"
      << "This tool does not connect to the SystemC kernel, does not run gem5\n"
      << "live co-simulation, and does not claim cycle accuracy or DRAM/AXI/CHI/NoC\n"
      << "protocol compliance.\n";
}

ModelConfig parse_cli(int argc, char** argv) {
  ModelConfig config;

  for (int index = 1; index < argc; ++index) {
    const std::string arg = argv[index];
    if (arg == "--help" || arg == "-h") {
      print_usage(argv[0]);
      std::exit(0);
    }
    if (arg == "--trace") {
      config.traces.emplace_back(next_value(index, argc, argv, arg));
      continue;
    }
    if (arg == "--output-dir") {
      config.output_dir = next_value(index, argc, argv, arg);
      continue;
    }
    if (arg == "--bank-count") {
      config.bank_count = parse_size(next_value(index, argc, argv, arg), arg);
      continue;
    }
    if (arg == "--queue-depth") {
      config.queue_depth = parse_size(next_value(index, argc, argv, arg), arg);
      continue;
    }
    if (arg == "--address-mapping") {
      config.address_mapping = next_value(index, argc, argv, arg);
      continue;
    }
    if (arg == "--base-service-latency-ns") {
      config.base_service_latency_ns =
          parse_double(next_value(index, argc, argv, arg), arg);
      continue;
    }
    if (arg == "--row-hit-latency-ns") {
      config.row_hit_latency_ns =
          parse_double(next_value(index, argc, argv, arg), arg);
      continue;
    }
    if (arg == "--row-miss-latency-ns") {
      config.row_miss_latency_ns =
          parse_double(next_value(index, argc, argv, arg), arg);
      continue;
    }
    if (arg == "--row-size-bytes") {
      config.row_size_bytes = parse_u64(next_value(index, argc, argv, arg), arg);
      continue;
    }
    if (arg == "--interleave-bytes") {
      config.interleave_bytes = parse_u64(next_value(index, argc, argv, arg), arg);
      continue;
    }
    if (arg == "--default-timestamp-step-ns") {
      config.default_timestamp_step_ns =
          parse_double(next_value(index, argc, argv, arg), arg);
      continue;
    }
    if (arg == "--validate-only") {
      config.validate_only = true;
      continue;
    }
    throw std::runtime_error("unknown argument: " + arg);
  }

  return config;
}

}  // namespace project_e
