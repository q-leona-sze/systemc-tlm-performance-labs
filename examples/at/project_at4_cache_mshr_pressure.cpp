// SPDX-License-Identifier: Apache-2.0

#include <algorithm>
#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "systemc"
#include "tlm.h"

namespace project_at4 {
namespace {

constexpr std::size_t kInitiatorCount = 3;
constexpr const char *kSchemaVersion = "at4.0";
constexpr double kInterconnectAcceptNs = 1.0;
constexpr double kCacheLookupNs = 1.0;
constexpr double kEndRespNs = 1.0;

struct InitiatorSpec {
    std::size_t index;
    const char *name;
    std::uint64_t base_addr;
};

constexpr std::array<InitiatorSpec, kInitiatorCount> kInitiators = {{
    {0, "cpu0", 0x50000000ULL},
    {1, "dma0", 0x60000000ULL},
    {2, "accel0", 0x70000000ULL},
}};

struct Options {
    std::string case_name = "mixed_cpu_dma_accel_interference";
    std::filesystem::path output_dir =
        "examples/at/results/project_at4_cache_mshr_pressure/model_runs/default";
    std::size_t num_transactions_per_initiator = 32;
    std::size_t mshr_capacity = 4;
    std::size_t cache_like_capacity = 64;
    double memory_service_latency_ns = 42.0;
    double hit_latency_ns = 4.0;
};

struct Profile {
    std::array<double, kInitiatorCount> hit_rate;
    std::array<double, kInitiatorCount> issue_gap_ns;
    std::array<std::size_t, kInitiatorCount> burst_every;
    std::array<double, kInitiatorCount> burst_pause_ns;
    double pollution_proxy;
    double interference_score;
    unsigned int seed;
};

struct TransactionRecord {
    std::string case_name;
    std::size_t txn_id = 0;
    std::size_t initiator_id = 0;
    std::string initiator;
    std::string pattern_class;
    std::uint64_t address = 0;
    unsigned int size_bytes = 64;
    std::size_t cache_like_capacity = 0;
    std::size_t mshr_capacity = 0;
    double hit_latency_ns = 0.0;
    double configured_memory_service_latency_ns = 0.0;
    double begin_req_ns = 0.0;
    double interconnect_accept_ns = 0.0;
    double cache_lookup_done_ns = 0.0;
    double mshr_grant_ns = 0.0;
    double memory_begin_ns = 0.0;
    double memory_end_ns = 0.0;
    double begin_resp_ns = 0.0;
    double end_resp_ns = 0.0;
    bool hit = false;
    std::size_t mshr_occupancy_on_arrival = 0;
    std::size_t mshr_occupancy_peak = 0;
    bool mshr_full = false;
    double miss_queue_delay_ns = 0.0;
    double memory_service_delay_ns = 0.0;
    double initiator_blocked_ns = 0.0;
    double pollution_proxy = 0.0;
    double interference_score = 0.0;
};

double clamp(double value, double low, double high)
{
    return std::max(low, std::min(value, high));
}

std::string hex_value(std::uint64_t value)
{
    std::ostringstream out;
    out << "0x" << std::hex << std::nouppercase << std::setw(16)
        << std::setfill('0') << value;
    return out.str();
}

std::string pattern_class_for(const std::string &case_name,
                              const InitiatorSpec &initiator)
{
    if (case_name == "cpu_latency_sensitive_hotset") {
        return initiator.index == 0 ? "cpu_latency_sensitive_hotset"
                                    : "background_shared_resource";
    }
    if (case_name == "dma_streaming_pollution") {
        return initiator.index == 1 ? "dma_streaming_pollution"
                                    : "pollution_victim";
    }
    if (case_name == "accel_tiled_reuse") {
        return initiator.index == 2 ? "accel_tiled_reuse"
                                    : "background_shared_resource";
    }
    return case_name;
}

Profile profile_for(const std::string &case_name)
{
    if (case_name == "cpu_latency_sensitive_hotset") {
        return {{{0.88, 0.16, 0.74}},
                {{9.0, 18.0, 13.0}},
                {{1, 1, 4}},
                {{0.0, 0.0, 14.0}},
                0.15,
                0.12,
                11};
    }
    if (case_name == "dma_streaming_pollution") {
        return {{{0.58, 0.05, 0.60}},
                {{7.0, 3.0, 10.0}},
                {{1, 1, 3}},
                {{0.0, 0.0, 9.0}},
                0.78,
                0.56,
                23};
    }
    if (case_name == "accel_tiled_reuse") {
        return {{{0.70, 0.12, 0.86}},
                {{10.0, 18.0, 5.0}},
                {{1, 1, 8}},
                {{0.0, 0.0, 22.0}},
                0.24,
                0.22,
                31};
    }
    if (case_name == "mixed_cpu_dma_accel_interference") {
        return {{{0.48, 0.04, 0.58}},
                {{5.0, 2.0, 4.0}},
                {{2, 1, 4}},
                {{7.0, 0.0, 11.0}},
                0.92,
                0.76,
                43};
    }
    if (case_name == "low_mshr_capacity_pressure") {
        return {{{0.42, 0.04, 0.52}},
                {{2.0, 1.0, 2.0}},
                {{2, 1, 3}},
                {{4.0, 0.0, 6.0}},
                0.88,
                0.84,
                59};
    }
    if (case_name == "high_mshr_diminishing_return") {
        return {{{0.48, 0.04, 0.58}},
                {{2.0, 1.0, 2.0}},
                {{2, 1, 3}},
                {{4.0, 0.0, 6.0}},
                0.82,
                0.68,
                71};
    }
    if (case_name == "slow_memory_mshr_saturation") {
        return {{{0.50, 0.08, 0.55}},
                {{3.0, 2.0, 3.0}},
                {{2, 1, 4}},
                {{5.0, 0.0, 8.0}},
                0.72,
                0.66,
                89};
    }

    return {{{0.52, 0.08, 0.58}},
            {{5.0, 3.0, 5.0}},
            {{2, 1, 4}},
            {{7.0, 0.0, 10.0}},
            0.70,
            0.60,
            97};
}

std::uint64_t address_for(const std::string &case_name,
                          const InitiatorSpec &initiator,
                          std::size_t txn_index)
{
    if (initiator.index == 0) {
        const std::uint64_t hotset_lines =
            case_name == "cpu_latency_sensitive_hotset" ? 8ULL : 24ULL;
        return initiator.base_addr + ((txn_index % hotset_lines) * 64ULL);
    }
    if (initiator.index == 1) {
        return initiator.base_addr + (txn_index * 64ULL);
    }

    const std::uint64_t tile = (txn_index / 8ULL) % 4ULL;
    const std::uint64_t line = txn_index % 8ULL;
    return initiator.base_addr + tile * 0x1000ULL + line * 64ULL;
}

double issue_time_for(const Options &options, const Profile &profile,
                      const InitiatorSpec &initiator, std::size_t txn_index)
{
    const double gap = profile.issue_gap_ns[initiator.index];
    const std::size_t burst = std::max<std::size_t>(
        1, profile.burst_every[initiator.index]);
    const double pause = profile.burst_pause_ns[initiator.index];
    const double jitter =
        static_cast<double>((txn_index + initiator.index * 3U) % 3U) * 0.25;

    double time = static_cast<double>(txn_index) * gap + jitter;
    if (burst > 1) {
        time += static_cast<double>(txn_index / burst) * pause;
    }

    if (options.case_name == "cpu_latency_sensitive_hotset" && initiator.index == 0) {
        time *= 0.85;
    }
    return time;
}

bool is_hit(const Options &options, const Profile &profile,
            const InitiatorSpec &initiator, std::size_t txn_index)
{
    const double capacity_adjust =
        (static_cast<double>(options.cache_like_capacity) - 64.0) / 640.0;
    const double pollution_penalty =
        initiator.index == 1 ? 0.0 : profile.pollution_proxy * 0.08;
    const double threshold = clamp(
        profile.hit_rate[initiator.index] + capacity_adjust - pollution_penalty,
        0.02, 0.95);
    const unsigned int score =
        (static_cast<unsigned int>(txn_index) * 37U
         + static_cast<unsigned int>(initiator.index) * 17U + profile.seed)
        % 100U;
    return static_cast<double>(score) < threshold * 100.0;
}

double service_delay_for(const Options &options, const Profile &profile,
                         const InitiatorSpec &initiator)
{
    const std::array<double, kInitiatorCount> factors = {{1.00, 1.08, 0.96}};
    const double pollution_stretch =
        1.0 + profile.pollution_proxy * (initiator.index == 1 ? 0.05 : 0.03);
    return options.memory_service_latency_ns * factors[initiator.index]
           * pollution_stretch;
}

void remove_completed(std::vector<double> &active_end_times, double time_ns)
{
    active_end_times.erase(
        std::remove_if(active_end_times.begin(), active_end_times.end(),
                       [time_ns](double end_time) { return end_time <= time_ns; }),
        active_end_times.end());
}

std::vector<TransactionRecord> make_initial_records(const Options &options)
{
    const Profile profile = profile_for(options.case_name);
    std::vector<TransactionRecord> records;
    records.reserve(kInitiatorCount * options.num_transactions_per_initiator);

    for (const InitiatorSpec &initiator : kInitiators) {
        for (std::size_t txn_index = 0;
             txn_index < options.num_transactions_per_initiator; ++txn_index) {
            TransactionRecord record;
            record.case_name = options.case_name;
            record.txn_id = (initiator.index + 1U) * 100000U + txn_index + 1U;
            record.initiator_id = initiator.index;
            record.initiator = initiator.name;
            record.pattern_class = pattern_class_for(options.case_name, initiator);
            record.address = address_for(options.case_name, initiator, txn_index);
            record.cache_like_capacity = options.cache_like_capacity;
            record.mshr_capacity = options.mshr_capacity;
            record.hit_latency_ns = options.hit_latency_ns;
            record.configured_memory_service_latency_ns =
                options.memory_service_latency_ns;
            record.begin_req_ns =
                issue_time_for(options, profile, initiator, txn_index);
            record.hit = is_hit(options, profile, initiator, txn_index);
            record.pollution_proxy =
                clamp(profile.pollution_proxy
                          + (initiator.index == 1 ? 0.08 : 0.0)
                          - static_cast<double>(options.cache_like_capacity) / 2000.0,
                      0.0, 1.0);
            record.interference_score = clamp(
                profile.interference_score
                    + (options.mshr_capacity <= 2 ? 0.10 : 0.0)
                    + (options.memory_service_latency_ns >= 90.0 ? 0.08 : 0.0),
                0.0, 1.0);
            records.push_back(record);
        }
    }

    std::sort(records.begin(), records.end(),
              [](const TransactionRecord &lhs, const TransactionRecord &rhs) {
                  if (lhs.begin_req_ns != rhs.begin_req_ns) {
                      return lhs.begin_req_ns < rhs.begin_req_ns;
                  }
                  return lhs.txn_id < rhs.txn_id;
              });

    return records;
}

void run_shared_resource_model(const Options &options,
                               std::vector<TransactionRecord> &records)
{
    const Profile profile = profile_for(options.case_name);
    std::vector<double> active_miss_end_times;
    active_miss_end_times.reserve(options.mshr_capacity);

    for (TransactionRecord &record : records) {
        const InitiatorSpec &initiator = kInitiators.at(record.initiator_id);
        record.interconnect_accept_ns = record.begin_req_ns + kInterconnectAcceptNs;
        record.cache_lookup_done_ns = record.interconnect_accept_ns + kCacheLookupNs;

        remove_completed(active_miss_end_times, record.cache_lookup_done_ns);
        record.mshr_occupancy_on_arrival = active_miss_end_times.size();
        record.mshr_occupancy_peak = active_miss_end_times.size();
        record.mshr_grant_ns = record.cache_lookup_done_ns;
        record.memory_begin_ns = record.cache_lookup_done_ns;
        record.memory_end_ns = record.cache_lookup_done_ns;

        if (record.hit) {
            const double hit_under_miss_surcharge =
                static_cast<double>(record.mshr_occupancy_on_arrival)
                * profile.interference_score * 0.35;
            record.begin_resp_ns =
                record.cache_lookup_done_ns + options.hit_latency_ns
                + hit_under_miss_surcharge;
            record.end_resp_ns = record.begin_resp_ns + kEndRespNs;
            record.initiator_blocked_ns = hit_under_miss_surcharge;
            continue;
        }

        if (active_miss_end_times.size() >= options.mshr_capacity) {
            record.mshr_full = true;
            const auto earliest = std::min_element(active_miss_end_times.begin(),
                                                   active_miss_end_times.end());
            record.mshr_grant_ns = *earliest;
            record.miss_queue_delay_ns =
                std::max(0.0, record.mshr_grant_ns - record.cache_lookup_done_ns);
            remove_completed(active_miss_end_times, record.mshr_grant_ns);
        }

        record.memory_begin_ns = record.mshr_grant_ns;
        record.memory_service_delay_ns =
            service_delay_for(options, profile, initiator);
        record.memory_end_ns =
            record.memory_begin_ns + record.memory_service_delay_ns;
        active_miss_end_times.push_back(record.memory_end_ns);
        record.mshr_occupancy_peak =
            std::max(record.mshr_occupancy_on_arrival, active_miss_end_times.size());
        record.begin_resp_ns = record.memory_end_ns;
        record.end_resp_ns = record.begin_resp_ns + kEndRespNs;
        record.initiator_blocked_ns = record.miss_queue_delay_ns;
    }
}

std::string yes_no(bool value)
{
    return value ? "YES" : "NO";
}

void write_trace(const std::filesystem::path &trace_path,
                 const std::vector<TransactionRecord> &records)
{
    std::filesystem::create_directories(trace_path.parent_path());
    std::ofstream out(trace_path);
    if (!out) {
        throw std::runtime_error("failed to open trace for writing: "
                                 + trace_path.string());
    }

    out << "case_name,txn_id,initiator,pattern_class,address,size_bytes,"
           "cache_like_capacity,mshr_capacity,hit_latency_ns,"
           "configured_memory_service_latency_ns,begin_req_ns,"
           "interconnect_accept_ns,cache_lookup_done_ns,mshr_grant_ns,"
           "memory_begin_ns,memory_end_ns,begin_resp_ns,end_resp_ns,"
           "cache_result,total_latency_ns,hit_latency_observed_ns,"
           "miss_latency_observed_ns,mshr_occupancy_on_arrival,"
           "mshr_occupancy_peak,mshr_full,miss_queue_delay_ns,"
           "memory_service_delay_ns,initiator_blocked_ns,interference_score,"
           "pollution_proxy,claim_boundary,schema_version\n";

    out << std::fixed << std::setprecision(3);
    for (const TransactionRecord &record : records) {
        const double total_latency_ns = record.end_resp_ns - record.begin_req_ns;
        const double hit_latency_observed =
            record.hit ? record.begin_resp_ns - record.cache_lookup_done_ns : 0.0;
        const double miss_latency_observed =
            record.hit ? 0.0 : record.begin_resp_ns - record.cache_lookup_done_ns;
        out << record.case_name << ',' << record.txn_id << ',' << record.initiator
            << ',' << record.pattern_class << ',' << hex_value(record.address)
            << ',' << record.size_bytes << ',' << record.cache_like_capacity << ','
            << record.mshr_capacity << ',' << record.hit_latency_ns << ','
            << record.configured_memory_service_latency_ns << ','
            << record.begin_req_ns << ',' << record.interconnect_accept_ns << ','
            << record.cache_lookup_done_ns << ',' << record.mshr_grant_ns << ','
            << record.memory_begin_ns << ',' << record.memory_end_ns << ','
            << record.begin_resp_ns << ',' << record.end_resp_ns << ','
            << (record.hit ? "HIT" : "MISS") << ',' << total_latency_ns << ','
            << hit_latency_observed << ',' << miss_latency_observed << ','
            << record.mshr_occupancy_on_arrival << ','
            << record.mshr_occupancy_peak << ',' << yes_no(record.mshr_full) << ','
            << record.miss_queue_delay_ns << ','
            << record.memory_service_delay_ns << ','
            << record.initiator_blocked_ns << ',' << record.interference_score
            << ',' << record.pollution_proxy << ",PASS," << kSchemaVersion << '\n';
    }
}

bool require_value(int argc, char *argv[], int &index, std::string &value)
{
    if (index + 1 >= argc) {
        return false;
    }
    ++index;
    value = argv[index];
    return true;
}

Options parse_args(int argc, char *argv[])
{
    Options options;
    for (int index = 1; index < argc; ++index) {
        const std::string arg = argv[index];
        std::string value;
        if (arg == "--case-name") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error("--case-name requires a value");
            }
            options.case_name = value;
        } else if (arg == "--output-dir") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error("--output-dir requires a value");
            }
            options.output_dir = value;
        } else if (arg == "--num-transactions-per-initiator") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error(
                    "--num-transactions-per-initiator requires a value");
            }
            options.num_transactions_per_initiator =
                static_cast<std::size_t>(std::stoul(value));
        } else if (arg == "--mshr-capacity") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error("--mshr-capacity requires a value");
            }
            options.mshr_capacity = static_cast<std::size_t>(std::stoul(value));
        } else if (arg == "--cache-like-capacity") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error("--cache-like-capacity requires a value");
            }
            options.cache_like_capacity =
                static_cast<std::size_t>(std::stoul(value));
        } else if (arg == "--memory-service-latency-ns") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error(
                    "--memory-service-latency-ns requires a value");
            }
            options.memory_service_latency_ns = std::stod(value);
        } else if (arg == "--hit-latency-ns") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error("--hit-latency-ns requires a value");
            }
            options.hit_latency_ns = std::stod(value);
        } else if (arg == "--help") {
            std::cout
                << "Usage: project_at4_cache_mshr_pressure [options]\n"
                << "  --case-name NAME\n"
                << "  --output-dir DIR\n"
                << "  --num-transactions-per-initiator N\n"
                << "  --mshr-capacity N\n"
                << "  --cache-like-capacity N\n"
                << "  --memory-service-latency-ns NS\n"
                << "  --hit-latency-ns NS\n";
            std::exit(0);
        } else {
            throw std::runtime_error("unknown argument: " + arg);
        }
    }

    if (options.mshr_capacity == 0) {
        throw std::runtime_error("--mshr-capacity must be greater than zero");
    }
    if (options.cache_like_capacity == 0) {
        throw std::runtime_error("--cache-like-capacity must be greater than zero");
    }
    if (options.num_transactions_per_initiator == 0) {
        throw std::runtime_error(
            "--num-transactions-per-initiator must be greater than zero");
    }
    if (options.hit_latency_ns <= 0.0 || options.memory_service_latency_ns <= 0.0) {
        throw std::runtime_error("latency arguments must be positive");
    }

    return options;
}

int run(int argc, char *argv[])
{
    const Options options = parse_args(argc, argv);
    std::vector<TransactionRecord> records = make_initial_records(options);
    run_shared_resource_model(options, records);
    const std::filesystem::path trace_path = options.output_dir / "trace.csv";
    write_trace(trace_path, records);

    std::cout << "Project AT-4 case complete\n";
    std::cout << "case_name=" << options.case_name << '\n';
    std::cout << "trace=" << trace_path << '\n';
    std::cout << "transactions=" << records.size() << '\n';
    std::cout << "schema_version=" << kSchemaVersion << '\n';
    return 0;
}

}  // namespace
}  // namespace project_at4

int sc_main(int argc, char *argv[])
{
    try {
        return project_at4::run(argc, argv);
    } catch (const std::exception &error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
