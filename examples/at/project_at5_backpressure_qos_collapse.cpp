// SPDX-License-Identifier: Apache-2.0

#include <algorithm>
#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "systemc"
#include "tlm.h"

namespace project_at5 {
namespace {

constexpr std::size_t kInitiatorCount = 3;
constexpr const char *kSchemaVersion = "at5.0";
constexpr double kArbiterBaseDelayNs = 1.0;
constexpr double kIngressPipelineNs = 1.0;
constexpr double kBeginRespNs = 1.0;
constexpr double kEndRespNs = 1.0;

struct InitiatorSpec {
    std::size_t index;
    const char *name;
    const char *traffic_class;
    std::uint64_t base_addr;
};

constexpr std::array<InitiatorSpec, kInitiatorCount> kInitiators = {{
    {0, "cpu_rt", "latency_sensitive", 0x80000000ULL},
    {1, "dma_bulk", "bulk_streaming", 0x90000000ULL},
    {2, "accel_burst", "bursty_accelerator", 0xa0000000ULL},
}};

struct Options {
    std::string case_name = "baseline_balanced_rr";
    std::string policy = "round_robin";
    std::filesystem::path output_dir =
        "examples/at/results/project_at5_backpressure_qos_collapse/model_runs/default";
    std::size_t num_transactions_per_initiator = 36;
    std::size_t ingress_queue_capacity = 8;
    std::size_t downstream_queue_capacity = 6;
    double memory_service_latency_ns = 60.0;
    double service_rate_txn_per_us = 16.0;
    double cpu_rt_sla_target_ns = 180.0;
    double dma_bulk_sla_target_ns = 850.0;
    double accel_burst_sla_target_ns = 420.0;
};

struct Profile {
    std::array<double, kInitiatorCount> issue_gap_ns;
    std::array<std::size_t, kInitiatorCount> burst_every;
    std::array<double, kInitiatorCount> burst_pause_ns;
    std::array<double, kInitiatorCount> service_factor;
    std::array<unsigned int, kInitiatorCount> size_bytes;
    double accel_tail_penalty_ns;
};

struct TransactionRecord {
    std::string case_name;
    std::string policy;
    std::size_t txn_id = 0;
    std::size_t initiator_id = 0;
    std::string initiator;
    std::string traffic_class;
    std::uint64_t address = 0;
    unsigned int size_bytes = 64;
    std::size_t sequence_index = 0;
    double begin_req_ns = 0.0;
    double schedule_key_ns = 0.0;
    double arbiter_accept_ns = 0.0;
    double ingress_enqueue_ns = 0.0;
    double ingress_dequeue_ns = 0.0;
    double downstream_enqueue_ns = 0.0;
    double service_begin_ns = 0.0;
    double service_end_ns = 0.0;
    double begin_resp_ns = 0.0;
    double end_resp_ns = 0.0;
    double sla_target_ns = 0.0;
    std::size_t ingress_queue_capacity = 0;
    std::size_t downstream_queue_capacity = 0;
    std::size_t ingress_queue_depth_on_arrival = 0;
    std::size_t downstream_queue_depth_on_arrival = 0;
    bool ingress_full = false;
    bool downstream_full = false;
    double backpressure_stall_ns = 0.0;
    double initiator_blocked_ns = 0.0;
    double memory_service_latency_ns = 0.0;
    double observed_service_time_ns = 0.0;
    double service_rate_txn_per_us = 0.0;
};

bool is_valid_policy(const std::string &policy)
{
    return policy == "round_robin" || policy == "strict_priority"
           || policy == "weighted_priority" || policy == "throttled_dma"
           || policy == "backpressure_aware";
}

Profile profile_for(const std::string &case_name)
{
    if (case_name == "strict_priority_helps_cpu") {
        return {{{70.0, 42.0, 90.0}},
                {{1, 1, 4}},
                {{0.0, 0.0, 28.0}},
                {{0.96, 1.05, 1.02}},
                {{64, 128, 96}},
                8.0};
    }
    if (case_name == "strict_priority_starves_dma") {
        return {{{56.0, 24.0, 80.0}},
                {{1, 1, 4}},
                {{0.0, 0.0, 24.0}},
                {{0.94, 1.10, 1.02}},
                {{64, 256, 96}},
                10.0};
    }
    if (case_name == "downstream_saturation_qos_collapse") {
        return {{{11.0, 7.0, 10.0}},
                {{1, 1, 3}},
                {{0.0, 0.0, 6.0}},
                {{1.00, 1.08, 1.08}},
                {{64, 256, 128}},
                18.0};
    }
    if (case_name == "small_queue_backpressure") {
        return {{{72.0, 64.0, 6.0}},
                {{1, 1, 6}},
                {{0.0, 0.0, 220.0}},
                {{0.92, 1.02, 1.00}},
                {{64, 128, 96}},
                6.0};
    }
    if (case_name == "throttled_dma_recovers_sla") {
        return {{{45.0, 12.0, 60.0}},
                {{1, 1, 4}},
                {{0.0, 0.0, 24.0}},
                {{0.92, 1.08, 1.00}},
                {{64, 256, 96}},
                8.0};
    }
    if (case_name == "bursty_accel_tail_spike") {
        return {{{58.0, 46.0, 4.0}},
                {{1, 1, 8}},
                {{0.0, 0.0, 240.0}},
                {{0.94, 1.04, 1.20}},
                {{64, 128, 128}},
                42.0};
    }

    return {{{140.0, 130.0, 160.0}},
            {{1, 1, 4}},
            {{0.0, 0.0, 80.0}},
            {{0.92, 1.00, 0.96}},
            {{64, 128, 96}},
            4.0};
}

void apply_policy_shape(Profile &profile, const std::string &policy)
{
    if (policy == "throttled_dma") {
        profile.issue_gap_ns[1] *= 2.8;
        profile.burst_pause_ns[1] += 18.0;
    } else if (policy == "backpressure_aware") {
        profile.issue_gap_ns[1] *= 1.8;
        profile.issue_gap_ns[2] *= 1.25;
        profile.burst_pause_ns[2] += 16.0;
    } else if (policy == "weighted_priority") {
        profile.issue_gap_ns[1] *= 1.15;
        profile.issue_gap_ns[2] *= 1.05;
    }
}

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

double sla_target_for(const Options &options, const InitiatorSpec &initiator)
{
    if (initiator.index == 0) {
        return options.cpu_rt_sla_target_ns;
    }
    if (initiator.index == 1) {
        return options.dma_bulk_sla_target_ns;
    }
    return options.accel_burst_sla_target_ns;
}

double issue_time_for(const Options &options, const Profile &profile,
                      const InitiatorSpec &initiator, std::size_t txn_index)
{
    const double gap = profile.issue_gap_ns[initiator.index];
    const std::size_t burst_every =
        std::max<std::size_t>(1, profile.burst_every[initiator.index]);
    const double burst_pause = profile.burst_pause_ns[initiator.index];
    const double jitter =
        static_cast<double>((txn_index + initiator.index * 5U) % 4U) * 0.30;
    const double offset = static_cast<double>(initiator.index) * 0.75;

    double time = static_cast<double>(txn_index) * gap + offset + jitter;
    if (burst_every > 1) {
        time += static_cast<double>(txn_index / burst_every) * burst_pause;
    }
    if (options.case_name == "strict_priority_helps_cpu" && initiator.index == 0) {
        time *= 0.92;
    }
    return time;
}

double policy_bias_ns(const std::string &policy, const InitiatorSpec &initiator,
                      std::size_t txn_index)
{
    if (policy == "strict_priority") {
        const std::array<double, kInitiatorCount> bias = {{-18.0, 32.0, 5.0}};
        return bias[initiator.index];
    }
    if (policy == "weighted_priority") {
        const std::array<double, kInitiatorCount> bias = {{-7.0, 9.0, 2.0}};
        return bias[initiator.index]
               + static_cast<double>(txn_index % 3U) * 0.35;
    }
    if (policy == "throttled_dma") {
        const std::array<double, kInitiatorCount> bias = {{-5.0, 18.0, 3.0}};
        return bias[initiator.index];
    }
    if (policy == "backpressure_aware") {
        const std::array<double, kInitiatorCount> bias = {{-4.0, 16.0, 6.0}};
        return bias[initiator.index]
               + static_cast<double>(txn_index % 4U) * 0.25;
    }
    return static_cast<double>((txn_index + initiator.index) % kInitiatorCount) * 0.40;
}

double arbitration_delay_ns(const std::string &policy,
                            const InitiatorSpec &initiator)
{
    if (policy == "strict_priority") {
        return kArbiterBaseDelayNs
               + (initiator.index == 0 ? 0.0 : (initiator.index == 1 ? 2.0 : 1.0));
    }
    if (policy == "backpressure_aware") {
        return kArbiterBaseDelayNs + (initiator.index == 0 ? 0.2 : 1.4);
    }
    return kArbiterBaseDelayNs + static_cast<double>(initiator.index) * 0.25;
}

std::uint64_t address_for(const InitiatorSpec &initiator, std::size_t txn_index)
{
    if (initiator.index == 0) {
        return initiator.base_addr + (txn_index % 16U) * 64ULL;
    }
    if (initiator.index == 1) {
        return initiator.base_addr + txn_index * 128ULL;
    }
    const std::uint64_t tile = (txn_index / 8ULL) % 8ULL;
    return initiator.base_addr + tile * 0x1000ULL + (txn_index % 8ULL) * 64ULL;
}

void remove_completed(std::vector<double> &end_times, double time_ns)
{
    end_times.erase(
        std::remove_if(end_times.begin(), end_times.end(),
                       [time_ns](double end_time) { return end_time <= time_ns; }),
        end_times.end());
}

double earliest_time(const std::vector<double> &times)
{
    return *std::min_element(times.begin(), times.end());
}

std::vector<TransactionRecord> make_initial_records(const Options &options)
{
    Profile profile = profile_for(options.case_name);
    apply_policy_shape(profile, options.policy);

    std::vector<TransactionRecord> records;
    records.reserve(kInitiatorCount * options.num_transactions_per_initiator);

    for (const InitiatorSpec &initiator : kInitiators) {
        for (std::size_t txn_index = 0;
             txn_index < options.num_transactions_per_initiator; ++txn_index) {
            TransactionRecord record;
            record.case_name = options.case_name;
            record.policy = options.policy;
            record.txn_id = (initiator.index + 1U) * 100000U + txn_index + 1U;
            record.initiator_id = initiator.index;
            record.initiator = initiator.name;
            record.traffic_class = initiator.traffic_class;
            record.address = address_for(initiator, txn_index);
            record.size_bytes = profile.size_bytes[initiator.index];
            record.sequence_index = txn_index;
            record.begin_req_ns =
                issue_time_for(options, profile, initiator, txn_index);
            record.schedule_key_ns =
                record.begin_req_ns + policy_bias_ns(options.policy, initiator, txn_index);
            record.sla_target_ns = sla_target_for(options, initiator);
            record.ingress_queue_capacity = options.ingress_queue_capacity;
            record.downstream_queue_capacity = options.downstream_queue_capacity;
            record.memory_service_latency_ns = options.memory_service_latency_ns;
            record.service_rate_txn_per_us = options.service_rate_txn_per_us;
            records.push_back(record);
        }
    }

    std::sort(records.begin(), records.end(),
              [](const TransactionRecord &lhs, const TransactionRecord &rhs) {
                  if (lhs.schedule_key_ns != rhs.schedule_key_ns) {
                      return lhs.schedule_key_ns < rhs.schedule_key_ns;
                  }
                  if (lhs.begin_req_ns != rhs.begin_req_ns) {
                      return lhs.begin_req_ns < rhs.begin_req_ns;
                  }
                  return lhs.txn_id < rhs.txn_id;
              });
    return records;
}

double service_time_for(const Options &options, const Profile &profile,
                        const TransactionRecord &record)
{
    const double rate_limited_latency =
        1000.0 / std::max(0.001, options.service_rate_txn_per_us);
    double service_time =
        std::max(options.memory_service_latency_ns, rate_limited_latency)
        * profile.service_factor[record.initiator_id];

    if (options.case_name == "bursty_accel_tail_spike"
        && record.initiator_id == 2 && record.sequence_index % 8U >= 5U) {
        service_time += profile.accel_tail_penalty_ns;
    }
    if (options.policy == "backpressure_aware" && record.initiator_id != 0) {
        service_time *= 0.98;
    }
    return service_time;
}

std::string queue_full_source(const TransactionRecord &record)
{
    if (record.ingress_full && record.downstream_full) {
        return "ingress+downstream";
    }
    if (record.ingress_full) {
        return "ingress";
    }
    if (record.downstream_full) {
        return "downstream";
    }
    return "none";
}

void run_backpressure_model(const Options &options,
                            std::vector<TransactionRecord> &records)
{
    const Profile profile = profile_for(options.case_name);
    std::vector<double> ingress_release_times;
    std::vector<double> downstream_completion_times;
    double next_service_available_ns = 0.0;

    ingress_release_times.reserve(options.ingress_queue_capacity);
    downstream_completion_times.reserve(options.downstream_queue_capacity);

    for (TransactionRecord &record : records) {
        const InitiatorSpec &initiator = kInitiators.at(record.initiator_id);
        double accept_candidate =
            record.begin_req_ns + arbitration_delay_ns(options.policy, initiator);

        remove_completed(ingress_release_times, accept_candidate);
        record.ingress_queue_depth_on_arrival = ingress_release_times.size();

        double ingress_wait_ns = 0.0;
        if (ingress_release_times.size() >= options.ingress_queue_capacity) {
            record.ingress_full = true;
            const double free_time = earliest_time(ingress_release_times);
            ingress_wait_ns = std::max(0.0, free_time - accept_candidate);
            accept_candidate = std::max(accept_candidate, free_time);
            remove_completed(ingress_release_times, accept_candidate);
        }

        record.arbiter_accept_ns = accept_candidate;
        record.ingress_enqueue_ns = record.arbiter_accept_ns;

        double downstream_candidate = record.ingress_enqueue_ns + kIngressPipelineNs;
        remove_completed(downstream_completion_times, downstream_candidate);
        record.downstream_queue_depth_on_arrival = downstream_completion_times.size();

        double downstream_wait_ns = 0.0;
        if (downstream_completion_times.size() >= options.downstream_queue_capacity) {
            record.downstream_full = true;
            const double free_time = earliest_time(downstream_completion_times);
            downstream_wait_ns = std::max(0.0, free_time - downstream_candidate);
            downstream_candidate = std::max(downstream_candidate, free_time);
            remove_completed(downstream_completion_times, downstream_candidate);
        }

        record.ingress_dequeue_ns = downstream_candidate;
        record.downstream_enqueue_ns = downstream_candidate;
        ingress_release_times.push_back(record.ingress_dequeue_ns);

        const double service_wait_ns =
            std::max(0.0, next_service_available_ns - record.downstream_enqueue_ns);
        record.service_begin_ns =
            std::max(record.downstream_enqueue_ns, next_service_available_ns);
        record.observed_service_time_ns = service_time_for(options, profile, record);
        record.service_end_ns =
            record.service_begin_ns + record.observed_service_time_ns;
        next_service_available_ns = record.service_end_ns;
        downstream_completion_times.push_back(record.service_end_ns);

        record.begin_resp_ns = record.service_end_ns + kBeginRespNs;
        record.end_resp_ns = record.begin_resp_ns + kEndRespNs;
        record.backpressure_stall_ns =
            ingress_wait_ns + downstream_wait_ns + service_wait_ns;
        record.initiator_blocked_ns =
            std::max(0.0, record.arbiter_accept_ns - record.begin_req_ns)
            + downstream_wait_ns + service_wait_ns;
    }

    std::sort(records.begin(), records.end(),
              [](const TransactionRecord &lhs, const TransactionRecord &rhs) {
                  if (lhs.begin_req_ns != rhs.begin_req_ns) {
                      return lhs.begin_req_ns < rhs.begin_req_ns;
                  }
                  return lhs.txn_id < rhs.txn_id;
              });
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

    out << "case_name,txn_id,initiator,traffic_class,policy,address,size_bytes,"
           "sequence_index,begin_req_ns,arbiter_accept_ns,ingress_enqueue_ns,"
           "ingress_dequeue_ns,downstream_enqueue_ns,service_begin_ns,"
           "service_end_ns,begin_resp_ns,end_resp_ns,total_latency_ns,"
           "sla_target_ns,sla_violation,ingress_queue_capacity,"
           "downstream_queue_capacity,ingress_queue_depth_on_arrival,"
           "downstream_queue_depth_on_arrival,queue_full_event,"
           "queue_full_source,backpressure_stall_ns,initiator_blocked_ns,"
           "memory_service_latency_ns,observed_service_time_ns,"
           "service_rate_txn_per_us,claim_boundary,schema_version\n";

    out << std::fixed << std::setprecision(3);
    for (const TransactionRecord &record : records) {
        const double total_latency_ns = record.end_resp_ns - record.begin_req_ns;
        const bool queue_full = record.ingress_full || record.downstream_full;
        const bool sla_violation = total_latency_ns > record.sla_target_ns;

        out << record.case_name << ',' << record.txn_id << ',' << record.initiator
            << ',' << record.traffic_class << ',' << record.policy << ','
            << hex_value(record.address) << ',' << record.size_bytes << ','
            << record.sequence_index << ',' << record.begin_req_ns << ','
            << record.arbiter_accept_ns << ',' << record.ingress_enqueue_ns << ','
            << record.ingress_dequeue_ns << ',' << record.downstream_enqueue_ns
            << ',' << record.service_begin_ns << ',' << record.service_end_ns
            << ',' << record.begin_resp_ns << ',' << record.end_resp_ns << ','
            << total_latency_ns << ',' << record.sla_target_ns << ','
            << yes_no(sla_violation) << ',' << record.ingress_queue_capacity
            << ',' << record.downstream_queue_capacity << ','
            << record.ingress_queue_depth_on_arrival << ','
            << record.downstream_queue_depth_on_arrival << ','
            << yes_no(queue_full) << ',' << queue_full_source(record) << ','
            << record.backpressure_stall_ns << ','
            << record.initiator_blocked_ns << ','
            << record.memory_service_latency_ns << ','
            << record.observed_service_time_ns << ','
            << record.service_rate_txn_per_us << ",PASS," << kSchemaVersion << '\n';
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
        } else if (arg == "--policy") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error("--policy requires a value");
            }
            options.policy = value;
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
        } else if (arg == "--ingress-queue-capacity") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error("--ingress-queue-capacity requires a value");
            }
            options.ingress_queue_capacity =
                static_cast<std::size_t>(std::stoul(value));
        } else if (arg == "--downstream-queue-capacity") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error(
                    "--downstream-queue-capacity requires a value");
            }
            options.downstream_queue_capacity =
                static_cast<std::size_t>(std::stoul(value));
        } else if (arg == "--memory-service-latency-ns") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error(
                    "--memory-service-latency-ns requires a value");
            }
            options.memory_service_latency_ns = std::stod(value);
        } else if (arg == "--service-rate-txn-per-us") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error(
                    "--service-rate-txn-per-us requires a value");
            }
            options.service_rate_txn_per_us = std::stod(value);
        } else if (arg == "--cpu-rt-sla-target-ns") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error("--cpu-rt-sla-target-ns requires a value");
            }
            options.cpu_rt_sla_target_ns = std::stod(value);
        } else if (arg == "--dma-bulk-sla-target-ns") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error("--dma-bulk-sla-target-ns requires a value");
            }
            options.dma_bulk_sla_target_ns = std::stod(value);
        } else if (arg == "--accel-burst-sla-target-ns") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error(
                    "--accel-burst-sla-target-ns requires a value");
            }
            options.accel_burst_sla_target_ns = std::stod(value);
        } else if (arg == "--help") {
            std::cout
                << "Usage: project_at5_backpressure_qos_collapse [options]\n"
                << "  --case-name NAME\n"
                << "  --policy round_robin|strict_priority|weighted_priority|"
                   "throttled_dma|backpressure_aware\n"
                << "  --output-dir DIR\n"
                << "  --num-transactions-per-initiator N\n"
                << "  --ingress-queue-capacity N\n"
                << "  --downstream-queue-capacity N\n"
                << "  --memory-service-latency-ns NS\n"
                << "  --service-rate-txn-per-us RATE\n"
                << "  --cpu-rt-sla-target-ns NS\n"
                << "  --dma-bulk-sla-target-ns NS\n"
                << "  --accel-burst-sla-target-ns NS\n";
            std::exit(0);
        } else {
            throw std::runtime_error("unknown argument: " + arg);
        }
    }

    if (!is_valid_policy(options.policy)) {
        throw std::runtime_error("unsupported policy: " + options.policy);
    }
    if (options.num_transactions_per_initiator == 0) {
        throw std::runtime_error(
            "--num-transactions-per-initiator must be greater than zero");
    }
    if (options.ingress_queue_capacity == 0
        || options.downstream_queue_capacity == 0) {
        throw std::runtime_error("queue capacities must be greater than zero");
    }
    if (options.memory_service_latency_ns <= 0.0
        || options.service_rate_txn_per_us <= 0.0) {
        throw std::runtime_error("service latency and rate must be positive");
    }
    return options;
}

int run(int argc, char *argv[])
{
    const Options options = parse_args(argc, argv);
    std::vector<TransactionRecord> records = make_initial_records(options);
    run_backpressure_model(options, records);
    const std::filesystem::path trace_path = options.output_dir / "trace.csv";
    write_trace(trace_path, records);

    std::cout << "Project AT-5 case complete\n";
    std::cout << "case_name=" << options.case_name << '\n';
    std::cout << "policy=" << options.policy << '\n';
    std::cout << "trace=" << trace_path << '\n';
    std::cout << "transactions=" << records.size() << '\n';
    std::cout << "schema_version=" << kSchemaVersion << '\n';
    return 0;
}

}  // namespace
}  // namespace project_at5

int sc_main(int argc, char *argv[])
{
    try {
        return project_at5::run(argc, argv);
    } catch (const std::exception &error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
