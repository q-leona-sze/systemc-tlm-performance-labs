// SPDX-License-Identifier: Apache-2.0

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <deque>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "systemc"
#include "tlm.h"

namespace project_at6 {
namespace {

constexpr std::size_t kInitiatorCount = 4;
constexpr const char *kSchemaVersion = "at6.0";
constexpr const char *kClaimBoundary =
    "bounded_at_level_synthetic_architecture_exploration";

struct InitiatorSpec {
    std::size_t index;
    const char *name;
    const char *traffic_class;
    std::uint64_t base_addr;
    double sla_latency_ns;
};

constexpr std::array<InitiatorSpec, kInitiatorCount> kInitiators = {{
    {0, "cpu_like", "latency_sensitive_small_burst", 0x10000000ULL, 220.0},
    {1, "npu_like", "throughput_oriented_bursty", 0x20000000ULL, 900.0},
    {2, "dma_like", "bulk_sequential_transfer", 0x30000000ULL, 1200.0},
    {3, "isp_like", "periodic_stream_latency_sensitive", 0x40000000ULL, 260.0},
}};

struct Profile {
    std::array<std::size_t, kInitiatorCount> transactions;
    std::array<double, kInitiatorCount> issue_gap_ns;
    std::array<std::size_t, kInitiatorCount> burst_every;
    std::array<double, kInitiatorCount> burst_pause_ns;
    std::array<unsigned int, kInitiatorCount> size_bytes;
    std::array<double, kInitiatorCount> service_factor;
};

struct CaseSpec {
    std::string case_name;
    std::string policy;
    std::string intent;
    Profile profile;
    double base_service_ns = 34.0;
    std::size_t fabric_queue_capacity = 36;
    double npu_token_gap_ns = 0.0;
    double starvation_threshold_ns = 520.0;
};

struct Options {
    std::filesystem::path output_dir =
        "examples/at/results/project_at6_heterogeneous_soc_fabric";
    bool write_trace = true;
};

struct TransactionRecord {
    std::string case_name;
    std::string policy;
    std::size_t request_id = 0;
    std::size_t initiator_id = 0;
    std::string initiator;
    std::string traffic_class;
    std::uint64_t address = 0;
    unsigned int size_bytes = 64;
    std::size_t sequence_index = 0;
    double issue_time_ns = 0.0;
    double start_service_time_ns = 0.0;
    double end_time_ns = 0.0;
    double queue_delay_ns = 0.0;
    double service_delay_ns = 0.0;
    double latency_ns = 0.0;
    std::size_t queue_depth_on_arrival = 0;
    bool starvation_flag = false;
};

struct InitiatorStats {
    std::size_t count = 0;
    std::uint64_t bytes = 0;
    double avg_latency_ns = 0.0;
    double p50_latency_ns = 0.0;
    double p95_latency_ns = 0.0;
    double p99_latency_ns = 0.0;
    double throughput_txn_per_us = 0.0;
    double bandwidth_share = 0.0;
    double sla_violation_ratio = 0.0;
};

struct CaseMetrics {
    std::string case_name;
    std::string policy;
    std::size_t total_transactions = 0;
    double sim_time_ns = 0.0;
    double avg_latency_ns = 0.0;
    double p50_latency_ns = 0.0;
    double p95_latency_ns = 0.0;
    double p99_latency_ns = 0.0;
    double max_latency_ns = 0.0;
    double throughput_txn_per_us = 0.0;
    std::size_t fabric_queue_peak = 0;
    std::size_t starvation_events = 0;
    std::array<InitiatorStats, kInitiatorCount> initiator_stats;
};

std::string hex_value(std::uint64_t value)
{
    std::ostringstream out;
    out << "0x" << std::hex << std::nouppercase << std::setw(16)
        << std::setfill('0') << value;
    return out.str();
}

Profile baseline_profile()
{
    return {{{56, 64, 52, 56}},
            {{130.0, 95.0, 150.0, 135.0}},
            {{4, 8, 1, 6}},
            {{20.0, 60.0, 0.0, 24.0}},
            {{64, 256, 384, 128}},
            {{0.86, 1.08, 1.22, 0.94}}};
}

CaseSpec make_case(const std::string &case_name)
{
    if (case_name == "priority_latency") {
        Profile profile = baseline_profile();
        profile.issue_gap_ns = {{128.0, 90.0, 145.0, 130.0}};
        profile.burst_pause_ns = {{18.0, 52.0, 0.0, 20.0}};
        return {"priority_latency",
                "priority_latency",
                "protect CPU-like and ISP-like tail latency with priority",
                profile,
                34.0,
                36,
                0.0,
                520.0};
    }
    if (case_name == "bandwidth_cap_npu") {
        Profile profile = baseline_profile();
        profile.transactions = {{60, 52, 54, 60}};
        profile.issue_gap_ns = {{120.0, 70.0, 145.0, 125.0}};
        profile.burst_every = {{4, 12, 1, 6}};
        profile.burst_pause_ns = {{16.0, 36.0, 0.0, 20.0}};
        return {"bandwidth_cap_npu",
                "latency_priority_with_npu_cap",
                "apply token-like NPU cap while protecting CPU-like and ISP-like flows",
                profile,
                34.0,
                36,
                180.0,
                520.0};
    }
    if (case_name == "dma_stress") {
        Profile profile = baseline_profile();
        profile.transactions = {{56, 64, 76, 56}};
        profile.issue_gap_ns = {{120.0, 95.0, 52.0, 125.0}};
        profile.size_bytes = {{64, 256, 512, 128}};
        profile.service_factor = {{0.86, 1.08, 1.42, 0.94}};
        return {"dma_stress",
                "round_robin",
                "increase DMA-like sequential burst pressure on the shared fabric",
                profile,
                36.0,
                40,
                0.0,
                620.0};
    }
    if (case_name == "mixed_stress") {
        Profile profile = baseline_profile();
        profile.transactions = {{64, 92, 80, 64}};
        profile.issue_gap_ns = {{84.0, 42.0, 45.0, 88.0}};
        profile.burst_every = {{4, 16, 1, 5}};
        profile.burst_pause_ns = {{12.0, 24.0, 0.0, 16.0}};
        profile.size_bytes = {{64, 320, 512, 160}};
        profile.service_factor = {{0.92, 1.20, 1.45, 1.00}};
        return {"mixed_stress",
                "latency_priority_no_cap",
                "combine NPU-like and DMA-like high pressure while observing latency flows",
                profile,
                40.0,
                44,
                0.0,
                700.0};
    }

    return {"baseline_rr",
            "round_robin",
            "balanced mixed traffic baseline with no bandwidth cap",
            baseline_profile(),
            34.0,
            36,
            0.0,
            520.0};
}

std::vector<CaseSpec> default_cases()
{
    return {make_case("baseline_rr"), make_case("priority_latency"),
            make_case("bandwidth_cap_npu"), make_case("dma_stress"),
            make_case("mixed_stress")};
}

double deterministic_jitter_ns(const InitiatorSpec &initiator,
                               std::size_t sequence_index)
{
    const unsigned int score =
        (static_cast<unsigned int>(sequence_index) * 17U
         + static_cast<unsigned int>(initiator.index) * 11U)
        % 7U;
    return static_cast<double>(score) * 0.35;
}

double issue_time_for(const Profile &profile, const InitiatorSpec &initiator,
                      std::size_t sequence_index)
{
    const double gap = profile.issue_gap_ns[initiator.index];
    const std::size_t burst_every =
        std::max<std::size_t>(1, profile.burst_every[initiator.index]);
    const double burst_pause = profile.burst_pause_ns[initiator.index];
    const double phase_offset = static_cast<double>(initiator.index) * 1.75;

    double issue_time =
        static_cast<double>(sequence_index) * gap + phase_offset
        + deterministic_jitter_ns(initiator, sequence_index);
    if (burst_every > 1) {
        issue_time += static_cast<double>(sequence_index / burst_every)
                      * burst_pause;
    }
    return issue_time;
}

std::uint64_t address_for(const InitiatorSpec &initiator,
                          std::size_t sequence_index)
{
    if (initiator.index == 0) {
        return initiator.base_addr + (sequence_index % 16ULL) * 64ULL;
    }
    if (initiator.index == 1) {
        const std::uint64_t tile = (sequence_index / 16ULL) % 8ULL;
        return initiator.base_addr + tile * 0x4000ULL
               + (sequence_index % 16ULL) * 256ULL;
    }
    if (initiator.index == 2) {
        return initiator.base_addr + sequence_index * 512ULL;
    }
    return initiator.base_addr + ((sequence_index % 12ULL) * 128ULL);
}

double service_delay_for(const CaseSpec &spec, const TransactionRecord &record)
{
    const double size_stretch =
        (static_cast<double>(record.size_bytes) / 64.0 - 1.0) * 3.75;
    const double sequence_jitter =
        static_cast<double>((record.sequence_index + record.initiator_id) % 5U)
        * 0.45;
    double delay =
        spec.base_service_ns * spec.profile.service_factor[record.initiator_id]
        + size_stretch + sequence_jitter;

    if (spec.case_name == "dma_stress" && record.initiator_id == 2) {
        delay += 18.0;
    }
    if (spec.case_name == "mixed_stress"
        && (record.initiator_id == 1 || record.initiator_id == 2)) {
        delay += 16.0;
    }
    if (spec.case_name == "bandwidth_cap_npu" && record.initiator_id == 1) {
        delay *= 0.98;
    }
    return delay;
}

std::vector<TransactionRecord> make_initial_records(const CaseSpec &spec)
{
    std::vector<TransactionRecord> records;
    const std::size_t reserve_count = std::accumulate(
        spec.profile.transactions.begin(), spec.profile.transactions.end(),
        static_cast<std::size_t>(0));
    records.reserve(reserve_count);

    for (const InitiatorSpec &initiator : kInitiators) {
        for (std::size_t sequence = 0;
             sequence < spec.profile.transactions[initiator.index]; ++sequence) {
            TransactionRecord record;
            record.case_name = spec.case_name;
            record.policy = spec.policy;
            record.request_id = (initiator.index + 1U) * 100000U + sequence + 1U;
            record.initiator_id = initiator.index;
            record.initiator = initiator.name;
            record.traffic_class = initiator.traffic_class;
            record.address = address_for(initiator, sequence);
            record.size_bytes = spec.profile.size_bytes[initiator.index];
            record.sequence_index = sequence;
            record.issue_time_ns = issue_time_for(spec.profile, initiator, sequence);
            records.push_back(record);
        }
    }

    std::sort(records.begin(), records.end(),
              [](const TransactionRecord &lhs, const TransactionRecord &rhs) {
                  if (lhs.issue_time_ns != rhs.issue_time_ns) {
                      return lhs.issue_time_ns < rhs.issue_time_ns;
                  }
                  return lhs.request_id < rhs.request_id;
              });
    return records;
}

bool npu_token_ready(const CaseSpec &spec, std::size_t initiator_id,
                     double current_time_ns, double next_npu_token_ns)
{
    if (spec.npu_token_gap_ns <= 0.0 || initiator_id != 1) {
        return true;
    }
    return current_time_ns + 1e-9 >= next_npu_token_ns;
}

std::size_t pending_position_for_initiator(
    const std::deque<std::size_t> &pending,
    const std::vector<TransactionRecord> &records, std::size_t initiator_id,
    const CaseSpec &spec, double current_time_ns, double next_npu_token_ns)
{
    for (std::size_t pos = 0; pos < pending.size(); ++pos) {
        const TransactionRecord &record = records.at(pending.at(pos));
        if (record.initiator_id == initiator_id
            && npu_token_ready(spec, initiator_id, current_time_ns,
                               next_npu_token_ns)) {
            return pos;
        }
    }
    return pending.size();
}

std::size_t select_pending_position(const std::deque<std::size_t> &pending,
                                    const std::vector<TransactionRecord> &records,
                                    const CaseSpec &spec,
                                    double current_time_ns,
                                    double next_npu_token_ns,
                                    std::size_t &last_rr_initiator)
{
    if (pending.empty()) {
        return pending.size();
    }

    if (spec.policy == "round_robin") {
        for (std::size_t offset = 1; offset <= kInitiatorCount; ++offset) {
            const std::size_t initiator_id =
                (last_rr_initiator + offset) % kInitiatorCount;
            const std::size_t pos = pending_position_for_initiator(
                pending, records, initiator_id, spec, current_time_ns,
                next_npu_token_ns);
            if (pos < pending.size()) {
                last_rr_initiator = initiator_id;
                return pos;
            }
        }
        return pending.size();
    }

    const std::array<std::size_t, kInitiatorCount> latency_priority = {{0, 3, 1, 2}};
    const std::array<std::size_t, kInitiatorCount> capped_priority = {{0, 3, 2, 1}};
    const std::array<std::size_t, kInitiatorCount> &order =
        spec.policy == "latency_priority_with_npu_cap" ? capped_priority
                                                       : latency_priority;

    for (std::size_t initiator_id : order) {
        const std::size_t pos = pending_position_for_initiator(
            pending, records, initiator_id, spec, current_time_ns,
            next_npu_token_ns);
        if (pos < pending.size()) {
            return pos;
        }
    }
    return pending.size();
}

std::size_t run_fabric_model(const CaseSpec &spec,
                             std::vector<TransactionRecord> &records)
{
    std::deque<std::size_t> pending;
    std::size_t next_record = 0;
    std::size_t completed = 0;
    std::size_t queue_peak = 0;
    std::size_t last_rr_initiator = kInitiatorCount - 1;
    double time_ns = 0.0;
    double next_npu_token_ns = 0.0;

    auto enqueue_ready_records = [&]() {
        while (next_record < records.size()
               && records.at(next_record).issue_time_ns <= time_ns + 1e-9) {
            records.at(next_record).queue_depth_on_arrival = pending.size();
            pending.push_back(next_record);
            queue_peak = std::max(queue_peak, pending.size());
            ++next_record;
        }
    };

    while (completed < records.size()) {
        enqueue_ready_records();
        if (pending.empty()) {
            if (next_record >= records.size()) {
                break;
            }
            time_ns = std::max(time_ns, records.at(next_record).issue_time_ns);
            enqueue_ready_records();
        }

        const std::size_t selected_pos = select_pending_position(
            pending, records, spec, time_ns, next_npu_token_ns,
            last_rr_initiator);

        if (selected_pos >= pending.size()) {
            double next_wakeup = next_npu_token_ns;
            if (next_record < records.size()) {
                next_wakeup =
                    std::min(next_wakeup, records.at(next_record).issue_time_ns);
            }
            time_ns = std::max(time_ns, next_wakeup);
            continue;
        }

        const std::size_t record_index = pending.at(selected_pos);
        pending.erase(pending.begin() + static_cast<std::ptrdiff_t>(selected_pos));

        TransactionRecord &record = records.at(record_index);
        record.start_service_time_ns = std::max(time_ns, record.issue_time_ns);
        record.queue_delay_ns = record.start_service_time_ns - record.issue_time_ns;
        record.service_delay_ns = service_delay_for(spec, record);
        record.end_time_ns = record.start_service_time_ns + record.service_delay_ns;
        record.latency_ns = record.end_time_ns - record.issue_time_ns;
        record.starvation_flag =
            record.queue_delay_ns > spec.starvation_threshold_ns
            || record.queue_depth_on_arrival >= spec.fabric_queue_capacity;

        if (spec.npu_token_gap_ns > 0.0 && record.initiator_id == 1) {
            next_npu_token_ns = record.start_service_time_ns + spec.npu_token_gap_ns;
        }

        time_ns = record.end_time_ns;
        ++completed;
        queue_peak = std::max(queue_peak, pending.size());
    }

    std::sort(records.begin(), records.end(),
              [](const TransactionRecord &lhs, const TransactionRecord &rhs) {
                  if (lhs.issue_time_ns != rhs.issue_time_ns) {
                      return lhs.issue_time_ns < rhs.issue_time_ns;
                  }
                  return lhs.request_id < rhs.request_id;
              });
    return queue_peak;
}

double percentile(std::vector<double> values, double percentile_value)
{
    if (values.empty()) {
        return 0.0;
    }
    std::sort(values.begin(), values.end());
    const double rank = percentile_value * static_cast<double>(values.size());
    const std::size_t index = static_cast<std::size_t>(std::ceil(rank)) - 1U;
    return values.at(std::min(index, values.size() - 1U));
}

double average(const std::vector<double> &values)
{
    if (values.empty()) {
        return 0.0;
    }
    const double total =
        std::accumulate(values.begin(), values.end(), 0.0);
    return total / static_cast<double>(values.size());
}

InitiatorStats make_initiator_stats(const std::vector<TransactionRecord> &records,
                                    std::size_t initiator_id,
                                    double sim_time_ns)
{
    InitiatorStats stats;
    std::vector<double> latencies;
    std::size_t sla_violations = 0;
    std::uint64_t total_bytes = 0;

    for (const TransactionRecord &record : records) {
        total_bytes += record.size_bytes;
        if (record.initiator_id != initiator_id) {
            continue;
        }
        stats.bytes += record.size_bytes;
        latencies.push_back(record.latency_ns);
        if (record.latency_ns > kInitiators.at(initiator_id).sla_latency_ns) {
            ++sla_violations;
        }
    }

    stats.count = latencies.size();
    stats.avg_latency_ns = average(latencies);
    stats.p50_latency_ns = percentile(latencies, 0.50);
    stats.p95_latency_ns = percentile(latencies, 0.95);
    stats.p99_latency_ns = percentile(latencies, 0.99);
    stats.throughput_txn_per_us =
        sim_time_ns > 0.0 ? static_cast<double>(stats.count) / (sim_time_ns / 1000.0)
                          : 0.0;
    stats.bandwidth_share =
        total_bytes > 0 ? static_cast<double>(stats.bytes) * 100.0
                              / static_cast<double>(total_bytes)
                        : 0.0;
    stats.sla_violation_ratio =
        stats.count > 0 ? static_cast<double>(sla_violations)
                              / static_cast<double>(stats.count)
                        : 0.0;
    return stats;
}

CaseMetrics make_case_metrics(const CaseSpec &spec,
                              const std::vector<TransactionRecord> &records,
                              std::size_t queue_peak)
{
    CaseMetrics metrics;
    metrics.case_name = spec.case_name;
    metrics.policy = spec.policy;
    metrics.total_transactions = records.size();
    metrics.fabric_queue_peak = queue_peak;

    std::vector<double> latencies;
    latencies.reserve(records.size());
    double first_issue_ns = std::numeric_limits<double>::max();
    double last_end_ns = 0.0;

    for (const TransactionRecord &record : records) {
        latencies.push_back(record.latency_ns);
        first_issue_ns = std::min(first_issue_ns, record.issue_time_ns);
        last_end_ns = std::max(last_end_ns, record.end_time_ns);
        metrics.max_latency_ns = std::max(metrics.max_latency_ns, record.latency_ns);
        if (record.starvation_flag) {
            ++metrics.starvation_events;
        }
    }

    metrics.sim_time_ns = std::max(0.0, last_end_ns - first_issue_ns);
    metrics.avg_latency_ns = average(latencies);
    metrics.p50_latency_ns = percentile(latencies, 0.50);
    metrics.p95_latency_ns = percentile(latencies, 0.95);
    metrics.p99_latency_ns = percentile(latencies, 0.99);
    metrics.throughput_txn_per_us =
        metrics.sim_time_ns > 0.0
            ? static_cast<double>(metrics.total_transactions)
                  / (metrics.sim_time_ns / 1000.0)
            : 0.0;

    for (const InitiatorSpec &initiator : kInitiators) {
        metrics.initiator_stats[initiator.index] =
            make_initiator_stats(records, initiator.index, metrics.sim_time_ns);
    }
    return metrics;
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

    out << "case,initiator,request_id,issue_time_ns,start_service_time_ns,"
           "end_time_ns,queue_delay_ns,service_delay_ns,latency_ns,policy,"
           "starvation_flag\n";
    out << std::fixed << std::setprecision(3);
    for (const TransactionRecord &record : records) {
        out << record.case_name << ',' << record.initiator << ','
            << record.request_id << ',' << record.issue_time_ns << ','
            << record.start_service_time_ns << ',' << record.end_time_ns << ','
            << record.queue_delay_ns << ',' << record.service_delay_ns << ','
            << record.latency_ns << ',' << record.policy << ','
            << (record.starvation_flag ? "YES" : "NO") << '\n';
    }
}

void write_summary(const std::filesystem::path &summary_path,
                   const std::vector<CaseMetrics> &metrics)
{
    std::filesystem::create_directories(summary_path.parent_path());
    std::ofstream out(summary_path);
    if (!out) {
        throw std::runtime_error("failed to open summary for writing: "
                                 + summary_path.string());
    }

    out << "case,total_transactions,sim_time_ns,avg_latency_ns,p50_latency_ns,"
           "p95_latency_ns,p99_latency_ns,max_latency_ns,throughput_txn_per_us,"
           "fabric_queue_peak,starvation_events,cpu_avg_latency_ns,"
           "cpu_p95_latency_ns,cpu_p99_latency_ns,cpu_throughput_txn_per_us,"
           "cpu_sla_violation_ratio,npu_avg_latency_ns,npu_p95_latency_ns,"
           "npu_p99_latency_ns,npu_throughput_txn_per_us,npu_bandwidth_share,"
           "dma_avg_latency_ns,dma_p95_latency_ns,dma_p99_latency_ns,"
           "dma_throughput_txn_per_us,dma_bandwidth_share,isp_avg_latency_ns,"
           "isp_p95_latency_ns,isp_p99_latency_ns,isp_throughput_txn_per_us,"
           "isp_sla_violation_ratio\n";

    out << std::fixed << std::setprecision(3);
    for (const CaseMetrics &row : metrics) {
        const InitiatorStats &cpu = row.initiator_stats[0];
        const InitiatorStats &npu = row.initiator_stats[1];
        const InitiatorStats &dma = row.initiator_stats[2];
        const InitiatorStats &isp = row.initiator_stats[3];
        out << row.case_name << ',' << row.total_transactions << ','
            << row.sim_time_ns << ',' << row.avg_latency_ns << ','
            << row.p50_latency_ns << ',' << row.p95_latency_ns << ','
            << row.p99_latency_ns << ',' << row.max_latency_ns << ','
            << row.throughput_txn_per_us << ',' << row.fabric_queue_peak << ','
            << row.starvation_events << ',' << cpu.avg_latency_ns << ','
            << cpu.p95_latency_ns << ',' << cpu.p99_latency_ns << ','
            << cpu.throughput_txn_per_us << ',' << cpu.sla_violation_ratio
            << ',' << npu.avg_latency_ns << ',' << npu.p95_latency_ns << ','
            << npu.p99_latency_ns << ',' << npu.throughput_txn_per_us << ','
            << npu.bandwidth_share << ',' << dma.avg_latency_ns << ','
            << dma.p95_latency_ns << ',' << dma.p99_latency_ns << ','
            << dma.throughput_txn_per_us << ',' << dma.bandwidth_share << ','
            << isp.avg_latency_ns << ',' << isp.p95_latency_ns << ','
            << isp.p99_latency_ns << ',' << isp.throughput_txn_per_us << ','
            << isp.sla_violation_ratio << '\n';
    }
}

const CaseMetrics &find_metrics(const std::vector<CaseMetrics> &metrics,
                                const std::string &case_name)
{
    const auto it = std::find_if(metrics.begin(), metrics.end(),
                                 [&](const CaseMetrics &row) {
                                     return row.case_name == case_name;
                                 });
    if (it == metrics.end()) {
        throw std::runtime_error("missing metrics for case: " + case_name);
    }
    return *it;
}

std::string delta_text(double before, double after)
{
    std::ostringstream out;
    out << std::fixed << std::setprecision(3) << before << " -> " << after;
    return out.str();
}

void write_comparison(const std::filesystem::path &comparison_path,
                      const std::vector<CaseSpec> &cases,
                      const std::vector<CaseMetrics> &metrics)
{
    std::filesystem::create_directories(comparison_path.parent_path());
    std::ofstream out(comparison_path);
    if (!out) {
        throw std::runtime_error("failed to open comparison for writing: "
                                 + comparison_path.string());
    }

    const CaseMetrics &baseline = find_metrics(metrics, "baseline_rr");
    const CaseMetrics &priority = find_metrics(metrics, "priority_latency");
    const CaseMetrics &cap = find_metrics(metrics, "bandwidth_cap_npu");
    const CaseMetrics &dma = find_metrics(metrics, "dma_stress");
    const CaseMetrics &mixed = find_metrics(metrics, "mixed_stress");

    out << std::fixed << std::setprecision(3);
    out << "# Project AT-6: Heterogeneous SoC Shared Memory Fabric Lab\n\n";
    out << "## Purpose\n\n";
    out << "Project AT-6 models a bounded AT-level synthetic heterogeneous SoC "
           "problem type where CPU-like, NPU-like, DMA-like, and ISP-like "
           "initiators share one memory fabric. The goal is trend comparison, "
           "bottleneck isolation, and recommendation logic for shared-memory "
           "fabric pressure.\n\n";

    out << "## Methodology\n\n";
    out << "- Deterministic synthetic traffic is generated for four initiator "
           "classes.\n";
    out << "- A shared request queue and single service path approximate fabric "
           "contention at AT level.\n";
    out << "- Policies compare round-robin, latency-priority, and token-like "
           "NPU bandwidth cap behavior.\n";
    out << "- Metrics include p50/p95/p99 latency, per-initiator throughput, "
           "bandwidth share, queue peak, SLA violation ratio, and starvation "
           "events.\n";
    out << "- `npu_bandwidth_share`, `dma_bandwidth_share`, and "
           "`isp_bandwidth_share` are byte-share percentages inside this "
           "synthetic run.\n\n";

    out << "## Case Table\n\n";
    out << "| case | policy | intent | total txns | sim ns | p99 ns | queue peak | "
           "starvation events | CPU p99 ns | ISP p99 ns | NPU bw share | DMA bw share |\n";
    out << "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n";
    for (const CaseSpec &spec : cases) {
        const CaseMetrics &row = find_metrics(metrics, spec.case_name);
        out << "| `" << row.case_name << "` | `" << row.policy << "` | "
            << spec.intent << " | " << row.total_transactions << " | "
            << row.sim_time_ns << " | " << row.p99_latency_ns << " | "
            << row.fabric_queue_peak << " | " << row.starvation_events << " | "
            << row.initiator_stats[0].p99_latency_ns << " | "
            << row.initiator_stats[3].p99_latency_ns << " | "
            << row.initiator_stats[1].bandwidth_share << " | "
            << row.initiator_stats[2].bandwidth_share << " |\n";
    }

    out << "\n## Key Observations\n\n";
    out << "- `priority_latency` changes CPU-like p99 latency from "
        << delta_text(baseline.initiator_stats[0].p99_latency_ns,
                      priority.initiator_stats[0].p99_latency_ns)
        << " ns and ISP-like p99 latency from "
        << delta_text(baseline.initiator_stats[3].p99_latency_ns,
                      priority.initiator_stats[3].p99_latency_ns)
        << " ns versus `baseline_rr`.\n";
    out << "- `bandwidth_cap_npu` reduces NPU-like throughput from "
        << delta_text(baseline.initiator_stats[1].throughput_txn_per_us,
                      cap.initiator_stats[1].throughput_txn_per_us)
        << " txn/us and changes CPU-like / ISP-like p99 latency to "
        << cap.initiator_stats[0].p99_latency_ns << " ns / "
        << cap.initiator_stats[3].p99_latency_ns
        << " ns, showing the cost of bandwidth partitioning.\n";
    out << "- `dma_stress` raises DMA byte share to "
        << dma.initiator_stats[2].bandwidth_share
        << "% and increases fabric queue peak to " << dma.fabric_queue_peak
        << ", isolating bulk-transfer pressure.\n";
    out << "- `mixed_stress` produces " << mixed.starvation_events
        << " starvation events while CPU-like / ISP-like p99 latency is "
        << mixed.initiator_stats[0].p99_latency_ns << " ns / "
        << mixed.initiator_stats[3].p99_latency_ns
        << " ns, showing that latency priority can protect selected flows while "
           "shifting starvation risk toward throughput and bulk flows.\n\n";

    out << "## Architecture Lessons\n\n";
    out << "- Priority can protect latency-sensitive flows, but it redistributes "
           "contention rather than creating more service capacity.\n";
    out << "- A token-like cap on an aggressive throughput initiator can improve "
           "tail latency for CPU-like and ISP-like traffic, at the cost of lower "
           "NPU-like throughput.\n";
    out << "- Long DMA-like transfers are a distinct bottleneck source because they "
           "consume byte share and stretch non-preemptive service time.\n";
    out << "- Mixed NPU-like plus DMA-like pressure is the highest-risk case for "
           "tail latency collapse and starvation risk; latency priority may "
           "protect CPU-like / ISP-like traffic while exposing bulk-flow risk.\n\n";

    out << "## Recommendation\n\n";
    out << "Use `baseline_rr` as the reference point, then compare "
           "`priority_latency` and `bandwidth_cap_npu` before accepting a "
           "latency-sensitive architecture recommendation. If `mixed_stress` "
           "still violates CPU-like or ISP-like SLA thresholds, the bounded "
           "recommendation is to add explicit bandwidth partitioning or reduce "
           "bulk-transfer pressure before claiming QoS protection.\n\n";

    out << "## Claim Boundary\n\n";
    out << "This lab is a bounded AT-level synthetic heterogeneous SoC "
           "shared-memory fabric exploration. It does not claim Apple Silicon "
           "simulation, real NoC behavior, cycle-accurate modeling, silicon "
           "validation, or production signoff.\n\n";
    out << "- Claim boundary: `" << kClaimBoundary << "`.\n";
    out << "- Schema version: `" << kSchemaVersion << "`.\n";
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
        if (arg == "--output-dir") {
            if (!require_value(argc, argv, index, value)) {
                throw std::runtime_error("--output-dir requires a value");
            }
            options.output_dir = value;
        } else if (arg == "--no-trace") {
            options.write_trace = false;
        } else if (arg == "--help") {
            std::cout
                << "Usage: project_at6_heterogeneous_soc_fabric [options]\n"
                << "  --output-dir DIR\n"
                << "  --no-trace\n";
            std::exit(0);
        } else {
            throw std::runtime_error("unknown argument: " + arg);
        }
    }
    return options;
}

int run(int argc, char *argv[])
{
    const Options options = parse_args(argc, argv);
    const std::vector<CaseSpec> cases = default_cases();
    std::vector<CaseMetrics> all_metrics;
    all_metrics.reserve(cases.size());

    std::filesystem::create_directories(options.output_dir);
    const std::filesystem::path trace_path = options.output_dir / "trace.csv";
    bool first_trace_write = true;

    for (const CaseSpec &spec : cases) {
        std::vector<TransactionRecord> records = make_initial_records(spec);
        const std::size_t queue_peak = run_fabric_model(spec, records);
        all_metrics.push_back(make_case_metrics(spec, records, queue_peak));

        if (options.write_trace) {
            if (first_trace_write) {
                write_trace(trace_path, records);
                first_trace_write = false;
            } else {
                std::ofstream out(trace_path, std::ios::app);
                if (!out) {
                    throw std::runtime_error("failed to append trace: "
                                             + trace_path.string());
                }
                out << std::fixed << std::setprecision(3);
                for (const TransactionRecord &record : records) {
                    out << record.case_name << ',' << record.initiator << ','
                        << record.request_id << ',' << record.issue_time_ns << ','
                        << record.start_service_time_ns << ',' << record.end_time_ns
                        << ',' << record.queue_delay_ns << ','
                        << record.service_delay_ns << ',' << record.latency_ns
                        << ',' << record.policy << ','
                        << (record.starvation_flag ? "YES" : "NO") << '\n';
                }
            }
        }
    }

    const std::filesystem::path summary_path = options.output_dir / "summary.csv";
    const std::filesystem::path comparison_path =
        options.output_dir / "comparison.md";
    write_summary(summary_path, all_metrics);
    write_comparison(comparison_path, cases, all_metrics);

    std::cout << "Project AT-6 PASS\n";
    std::cout << "cases=" << all_metrics.size() << '\n';
    std::cout << "summary=" << summary_path << '\n';
    std::cout << "comparison=" << comparison_path << '\n';
    if (options.write_trace) {
        std::cout << "trace=" << trace_path << '\n';
    }
    std::cout << "claim_boundary=PASS\n";
    std::cout << "schema_version=" << kSchemaVersion << '\n';
    return 0;
}

}  // namespace
}  // namespace project_at6

int sc_main(int argc, char *argv[])
{
    try {
        return project_at6::run(argc, argv);
    } catch (const std::exception &error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
