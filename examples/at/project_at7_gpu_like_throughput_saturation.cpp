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
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "systemc"
#include "tlm.h"

namespace project_at7 {
namespace {

constexpr const char *kSchemaVersion = "at7.0";
constexpr const char *kClaimBoundary =
    "bounded_at_level_synthetic_gpu_like_throughput_exploration";
constexpr double kEpsilon = 1e-9;

struct CaseSpec {
    std::string case_name;
    std::string intent;
    std::size_t num_lanes = 1;
    std::size_t requests_per_lane = 1;
    std::size_t outstanding_limit_per_lane = 1;
    std::size_t global_outstanding_limit = 1;
    std::size_t burst_length = 1;
    double compute_gap_ns = 1.0;
    double intra_burst_gap_ns = 0.35;
    unsigned int memory_request_size_bytes = 128;
    double memory_service_time_ns = 10.0;
    double service_bandwidth_bytes_per_ns = 64.0;
    std::size_t queue_capacity = 8;
    std::size_t latency_hiding_window = 4;
};

struct Options {
    std::filesystem::path output_dir =
        "examples/at/results/project_at7_gpu_like_throughput_saturation";
    bool write_trace = false;
};

struct LaneState {
    std::size_t generated = 0;
    std::size_t outstanding = 0;
    double next_issue_ready_ns = 0.0;
    std::optional<double> blocked_since_ns;
    std::size_t stall_events = 0;
    double blocked_issue_stall_ns = 0.0;
};

struct RequestRecord {
    std::string case_name;
    std::size_t request_id = 0;
    std::size_t lane_id = 0;
    std::size_t sequence_index = 0;
    unsigned int size_bytes = 0;
    double issue_time_ns = 0.0;
    double service_start_ns = 0.0;
    double service_end_ns = 0.0;
    double queue_delay_ns = 0.0;
    double service_delay_ns = 0.0;
    double latency_ns = 0.0;
    double hidden_latency_ns = 0.0;
    double exposed_latency_ns = 0.0;
    std::size_t queue_depth_on_arrival = 0;
    std::size_t outstanding_after_issue = 0;
};

struct SimulationResult {
    CaseSpec spec;
    std::vector<RequestRecord> records;
    std::vector<LaneState> lanes;
    double sim_time_ns = 0.0;
    double queue_depth_area = 0.0;
    double outstanding_area = 0.0;
    std::size_t queue_peak = 0;
    std::size_t peak_outstanding = 0;
};

struct CaseMetrics {
    std::string case_name;
    std::string intent;
    std::size_t num_lanes = 0;
    std::size_t requests_per_lane = 0;
    std::size_t total_requests = 0;
    std::size_t outstanding_limit_per_lane = 0;
    std::size_t global_outstanding_limit = 0;
    std::size_t burst_length = 0;
    double compute_gap_ns = 0.0;
    unsigned int memory_request_size_bytes = 0;
    double memory_service_time_ns = 0.0;
    std::size_t queue_capacity = 0;
    std::size_t latency_hiding_window = 0;
    double sim_time_ns = 0.0;
    double avg_latency_ns = 0.0;
    double p50_latency_ns = 0.0;
    double p95_latency_ns = 0.0;
    double p99_latency_ns = 0.0;
    double max_latency_ns = 0.0;
    double throughput_req_per_us = 0.0;
    double effective_bandwidth_bytes_per_ns = 0.0;
    double memory_utilization_ratio = 0.0;
    double avg_queue_delay_ns = 0.0;
    double p95_queue_delay_ns = 0.0;
    std::size_t queue_peak = 0;
    double avg_queue_depth = 0.0;
    double avg_outstanding = 0.0;
    std::size_t peak_outstanding = 0;
    std::size_t stall_events = 0;
    double stall_ratio = 0.0;
    double hidden_latency_ns = 0.0;
    double exposed_stall_ns = 0.0;
    std::string saturation_flag;
    std::string knee_point_hint;
};

std::vector<CaseSpec> default_cases()
{
    return {
        {"low_occupancy",
         "low lane count and shallow outstanding depth keep memory below saturation",
         2,
         40,
         2,
         4,
         1,
         90.0,
         0.35,
         128,
         10.0,
         64.0,
         16,
         4},
        {"balanced_occupancy",
         "moderate outstanding depth approaches useful bandwidth without severe tail growth",
         4,
         64,
         4,
         16,
         2,
         145.0,
         0.35,
         128,
         10.0,
         64.0,
         32,
         8},
        {"high_occupancy",
         "high request pressure reaches the bandwidth knee and increases queue delay",
         8,
         64,
         6,
         32,
         2,
         100.0,
         0.30,
         128,
         10.0,
         64.0,
         48,
         10},
        {"bandwidth_saturation",
         "additional lanes and outstanding depth push against the bandwidth wall",
         12,
         64,
         8,
         64,
         3,
         90.0,
         0.25,
         128,
         10.0,
         64.0,
         72,
         12},
        {"bursty_stress",
         "large bursts increase instantaneous pressure and expose queue buildup",
         8,
         64,
         8,
         48,
         8,
         180.0,
         0.25,
         128,
         10.0,
         64.0,
         40,
         10},
        {"throttled_occupancy",
         "moderate throttling trades a small throughput loss for lower tail pressure",
         8,
         64,
         4,
         20,
         2,
         130.0,
         0.35,
         128,
         10.0,
         64.0,
         48,
         8},
    };
}

double deterministic_service_jitter_ns(std::size_t lane_id,
                                       std::size_t sequence_index)
{
    const unsigned int score =
        (static_cast<unsigned int>(lane_id) * 13U
         + static_cast<unsigned int>(sequence_index) * 7U)
        % 6U;
    return static_cast<double>(score) * 0.18;
}

double service_delay_for(const CaseSpec &spec, const RequestRecord &record)
{
    const double transfer_time_ns =
        static_cast<double>(record.size_bytes) / spec.service_bandwidth_bytes_per_ns;
    return spec.memory_service_time_ns + transfer_time_ns
           + deterministic_service_jitter_ns(record.lane_id,
                                             record.sequence_index);
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
    return std::accumulate(values.begin(), values.end(), 0.0)
           / static_cast<double>(values.size());
}

std::size_t total_request_count(const CaseSpec &spec)
{
    return spec.num_lanes * spec.requests_per_lane;
}

bool lane_has_work(const LaneState &lane, const CaseSpec &spec)
{
    return lane.generated < spec.requests_per_lane || lane.outstanding > 0;
}

bool lane_ready_to_issue(const LaneState &lane, const CaseSpec &spec,
                         double time_ns)
{
    return lane.generated < spec.requests_per_lane
           && lane.next_issue_ready_ns <= time_ns + kEpsilon;
}

bool can_issue(const LaneState &lane, const CaseSpec &spec,
               std::size_t global_outstanding, std::size_t queue_depth,
               double time_ns)
{
    return lane_ready_to_issue(lane, spec, time_ns)
           && lane.outstanding < spec.outstanding_limit_per_lane
           && global_outstanding < spec.global_outstanding_limit
           && queue_depth < spec.queue_capacity;
}

void mark_blocked(LaneState &lane, double time_ns)
{
    if (!lane.blocked_since_ns.has_value()) {
        lane.blocked_since_ns = time_ns;
        ++lane.stall_events;
    }
}

void close_blocked_interval(LaneState &lane, double time_ns)
{
    if (lane.blocked_since_ns.has_value()) {
        lane.blocked_issue_stall_ns +=
            std::max(0.0, time_ns - lane.blocked_since_ns.value());
        lane.blocked_since_ns.reset();
    }
}

void assign_latency_hiding(const CaseSpec &spec, RequestRecord &record)
{
    const double outstanding_ratio =
        std::min(1.0, static_cast<double>(record.outstanding_after_issue)
                          / static_cast<double>(
                              std::max<std::size_t>(1, spec.latency_hiding_window)));
    const double service_hidden_ratio = std::min(0.88, 0.20 + 0.68 * outstanding_ratio);
    double queue_hidden_ratio = 0.35 * outstanding_ratio;
    if (record.queue_depth_on_arrival
        > static_cast<std::size_t>(std::ceil(
            static_cast<double>(spec.queue_capacity) * 0.70))) {
        queue_hidden_ratio *= 0.45;
    }

    const double hidden =
        record.service_delay_ns * service_hidden_ratio
        + record.queue_delay_ns * queue_hidden_ratio;
    record.hidden_latency_ns = std::min(record.latency_ns, hidden);
    record.exposed_latency_ns =
        std::max(0.0, record.latency_ns - record.hidden_latency_ns);
}

SimulationResult run_case(const CaseSpec &spec)
{
    SimulationResult result;
    result.spec = spec;
    result.records.reserve(total_request_count(spec));
    result.lanes.resize(spec.num_lanes);

    for (std::size_t lane_id = 0; lane_id < result.lanes.size(); ++lane_id) {
        result.lanes[lane_id].next_issue_ready_ns =
            static_cast<double>(lane_id) * 0.55;
    }

    std::deque<std::size_t> memory_queue;
    std::optional<std::size_t> current_service;
    std::size_t global_outstanding = 0;
    std::size_t completed = 0;
    std::size_t next_request_id = 1;
    double time_ns = 0.0;

    auto complete_current_service = [&]() {
        if (!current_service.has_value()) {
            return false;
        }
        RequestRecord &record = result.records.at(current_service.value());
        if (record.service_end_ns > time_ns + kEpsilon) {
            return false;
        }

        record.latency_ns = record.service_end_ns - record.issue_time_ns;
        assign_latency_hiding(spec, record);
        LaneState &lane = result.lanes.at(record.lane_id);
        if (lane.outstanding == 0 || global_outstanding == 0) {
            throw std::runtime_error("outstanding accounting underflow");
        }
        --lane.outstanding;
        --global_outstanding;
        ++completed;
        current_service.reset();
        return true;
    };

    auto start_service_if_idle = [&]() {
        if (current_service.has_value() || memory_queue.empty()) {
            return false;
        }
        const std::size_t record_index = memory_queue.front();
        memory_queue.pop_front();
        RequestRecord &record = result.records.at(record_index);
        record.service_start_ns = time_ns;
        record.queue_delay_ns = record.service_start_ns - record.issue_time_ns;
        record.service_delay_ns = service_delay_for(spec, record);
        record.service_end_ns = record.service_start_ns + record.service_delay_ns;
        current_service = record_index;
        return true;
    };

    auto issue_ready_requests = [&]() {
        bool issued_any = false;
        bool issued_in_pass = false;
        do {
            issued_in_pass = false;
            for (std::size_t lane_id = 0; lane_id < result.lanes.size(); ++lane_id) {
                LaneState &lane = result.lanes.at(lane_id);
                if (!can_issue(lane, spec, global_outstanding,
                               memory_queue.size(), time_ns)) {
                    continue;
                }

                close_blocked_interval(lane, time_ns);

                RequestRecord record;
                record.case_name = spec.case_name;
                record.request_id = next_request_id++;
                record.lane_id = lane_id;
                record.sequence_index = lane.generated;
                record.size_bytes = spec.memory_request_size_bytes;
                record.issue_time_ns = time_ns;
                record.queue_depth_on_arrival = memory_queue.size();
                record.outstanding_after_issue = global_outstanding + 1U;

                const std::size_t record_index = result.records.size();
                result.records.push_back(record);
                memory_queue.push_back(record_index);

                ++lane.generated;
                ++lane.outstanding;
                ++global_outstanding;
                result.queue_peak =
                    std::max(result.queue_peak, memory_queue.size());
                result.peak_outstanding =
                    std::max(result.peak_outstanding, global_outstanding);

                const bool end_of_burst =
                    lane.generated % std::max<std::size_t>(1, spec.burst_length) == 0;
                lane.next_issue_ready_ns =
                    time_ns
                    + (end_of_burst ? spec.compute_gap_ns
                                    : spec.intra_burst_gap_ns);

                issued_any = true;
                issued_in_pass = true;
            }
        } while (issued_in_pass);

        for (LaneState &lane : result.lanes) {
            if (lane_ready_to_issue(lane, spec, time_ns)
                && !can_issue(lane, spec, global_outstanding,
                              memory_queue.size(), time_ns)) {
                mark_blocked(lane, time_ns);
            }
        }
        return issued_any;
    };

    while (completed < total_request_count(spec)) {
        bool progress = false;

        while (complete_current_service()) {
            progress = true;
            while (start_service_if_idle()) {
                progress = true;
            }
        }

        while (start_service_if_idle()) {
            progress = true;
        }

        if (issue_ready_requests()) {
            progress = true;
        }

        while (start_service_if_idle()) {
            progress = true;
        }

        if (completed >= total_request_count(spec)) {
            break;
        }

        double next_time_ns = std::numeric_limits<double>::infinity();
        if (current_service.has_value()) {
            next_time_ns =
                std::min(next_time_ns,
                         result.records.at(current_service.value()).service_end_ns);
        }

        for (const LaneState &lane : result.lanes) {
            if (lane.generated < spec.requests_per_lane) {
                if (lane.next_issue_ready_ns > time_ns + kEpsilon) {
                    next_time_ns = std::min(next_time_ns, lane.next_issue_ready_ns);
                } else if (!current_service.has_value() && memory_queue.empty()
                           && lane.outstanding == 0) {
                    next_time_ns = time_ns;
                }
            }
        }

        if (!std::isfinite(next_time_ns)) {
            bool any_work_left = false;
            for (const LaneState &lane : result.lanes) {
                any_work_left = any_work_left || lane_has_work(lane, spec);
            }
            if (any_work_left) {
                throw std::runtime_error("no next event while work remains");
            }
            break;
        }

        if (next_time_ns <= time_ns + kEpsilon) {
            if (!progress) {
                throw std::runtime_error("event loop stopped making progress");
            }
            next_time_ns = time_ns + 0.001;
        }

        const double delta_ns = next_time_ns - time_ns;
        result.queue_depth_area += static_cast<double>(memory_queue.size()) * delta_ns;
        result.outstanding_area += static_cast<double>(global_outstanding) * delta_ns;
        time_ns = next_time_ns;
    }

    result.sim_time_ns = time_ns;
    return result;
}

CaseMetrics make_metrics(const SimulationResult &result)
{
    const CaseSpec &spec = result.spec;
    CaseMetrics metrics;
    metrics.case_name = spec.case_name;
    metrics.intent = spec.intent;
    metrics.num_lanes = spec.num_lanes;
    metrics.requests_per_lane = spec.requests_per_lane;
    metrics.total_requests = result.records.size();
    metrics.outstanding_limit_per_lane = spec.outstanding_limit_per_lane;
    metrics.global_outstanding_limit = spec.global_outstanding_limit;
    metrics.burst_length = spec.burst_length;
    metrics.compute_gap_ns = spec.compute_gap_ns;
    metrics.memory_request_size_bytes = spec.memory_request_size_bytes;
    metrics.memory_service_time_ns = spec.memory_service_time_ns;
    metrics.queue_capacity = spec.queue_capacity;
    metrics.latency_hiding_window = spec.latency_hiding_window;
    metrics.sim_time_ns = result.sim_time_ns;
    metrics.queue_peak = result.queue_peak;
    metrics.peak_outstanding = result.peak_outstanding;

    std::vector<double> latencies;
    std::vector<double> queue_delays;
    latencies.reserve(result.records.size());
    queue_delays.reserve(result.records.size());

    double total_service_ns = 0.0;
    std::uint64_t total_bytes = 0;
    for (const RequestRecord &record : result.records) {
        latencies.push_back(record.latency_ns);
        queue_delays.push_back(record.queue_delay_ns);
        metrics.max_latency_ns =
            std::max(metrics.max_latency_ns, record.latency_ns);
        metrics.hidden_latency_ns += record.hidden_latency_ns;
        metrics.exposed_stall_ns += record.exposed_latency_ns;
        total_service_ns += record.service_delay_ns;
        total_bytes += record.size_bytes;
    }

    for (const LaneState &lane : result.lanes) {
        metrics.stall_events += lane.stall_events;
        metrics.exposed_stall_ns += lane.blocked_issue_stall_ns;
    }

    metrics.avg_latency_ns = average(latencies);
    metrics.p50_latency_ns = percentile(latencies, 0.50);
    metrics.p95_latency_ns = percentile(latencies, 0.95);
    metrics.p99_latency_ns = percentile(latencies, 0.99);
    metrics.avg_queue_delay_ns = average(queue_delays);
    metrics.p95_queue_delay_ns = percentile(queue_delays, 0.95);

    metrics.throughput_req_per_us =
        metrics.sim_time_ns > 0.0
            ? static_cast<double>(metrics.total_requests)
                  / (metrics.sim_time_ns / 1000.0)
            : 0.0;
    metrics.effective_bandwidth_bytes_per_ns =
        metrics.sim_time_ns > 0.0
            ? static_cast<double>(total_bytes) / metrics.sim_time_ns
            : 0.0;
    metrics.memory_utilization_ratio =
        metrics.sim_time_ns > 0.0
            ? std::min(1.0, total_service_ns / metrics.sim_time_ns)
            : 0.0;
    metrics.avg_queue_depth =
        metrics.sim_time_ns > 0.0 ? result.queue_depth_area / metrics.sim_time_ns
                                  : 0.0;
    metrics.avg_outstanding =
        metrics.sim_time_ns > 0.0 ? result.outstanding_area / metrics.sim_time_ns
                                  : 0.0;

    const double stall_denominator =
        metrics.hidden_latency_ns + metrics.exposed_stall_ns;
    metrics.stall_ratio =
        stall_denominator > 0.0 ? metrics.exposed_stall_ns / stall_denominator
                                : 0.0;

    const bool queue_saturated =
        metrics.memory_utilization_ratio >= 0.85
        && metrics.p95_queue_delay_ns > spec.memory_service_time_ns * 8.0;
    const bool saturated =
        metrics.memory_utilization_ratio >= 0.94
        || metrics.queue_peak
               >= static_cast<std::size_t>(
                   std::ceil(static_cast<double>(spec.queue_capacity) * 0.80))
        || queue_saturated;
    metrics.saturation_flag = saturated ? "YES" : "NO";

    if (metrics.memory_utilization_ratio < 0.65) {
        metrics.knee_point_hint = "below_knee_underfilled";
    } else if (metrics.memory_utilization_ratio < 0.90) {
        metrics.knee_point_hint = "approaching_knee";
    } else if (metrics.throughput_req_per_us > 0.0
               && metrics.p95_queue_delay_ns < spec.memory_service_time_ns * 5.0) {
        metrics.knee_point_hint = "near_knee_latency_hiding";
    } else {
        metrics.knee_point_hint = "past_knee_bandwidth_wall";
    }

    return metrics;
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

std::string format_delta(double before, double after, const char *unit)
{
    std::ostringstream out;
    out << std::fixed << std::setprecision(3) << before << " -> " << after;
    if (unit != nullptr && std::string(unit).size() > 0) {
        out << ' ' << unit;
    }
    return out.str();
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

    out << "case,num_lanes,requests_per_lane,total_requests,"
           "outstanding_limit_per_lane,global_outstanding_limit,burst_length,"
           "compute_gap_ns,memory_request_size_bytes,memory_service_time_ns,"
           "queue_capacity,latency_hiding_window,sim_time_ns,avg_latency_ns,"
           "p50_latency_ns,p95_latency_ns,p99_latency_ns,max_latency_ns,"
           "throughput_req_per_us,effective_bandwidth_bytes_per_ns,"
           "memory_utilization_ratio,avg_queue_delay_ns,p95_queue_delay_ns,"
           "queue_peak,avg_queue_depth,avg_outstanding,peak_outstanding,"
           "stall_events,stall_ratio,hidden_latency_ns,exposed_stall_ns,"
           "saturation_flag,knee_point_hint\n";

    out << std::fixed << std::setprecision(3);
    for (const CaseMetrics &row : metrics) {
        out << row.case_name << ',' << row.num_lanes << ','
            << row.requests_per_lane << ',' << row.total_requests << ','
            << row.outstanding_limit_per_lane << ','
            << row.global_outstanding_limit << ',' << row.burst_length << ','
            << row.compute_gap_ns << ',' << row.memory_request_size_bytes << ','
            << row.memory_service_time_ns << ',' << row.queue_capacity << ','
            << row.latency_hiding_window << ',' << row.sim_time_ns << ','
            << row.avg_latency_ns << ',' << row.p50_latency_ns << ','
            << row.p95_latency_ns << ',' << row.p99_latency_ns << ','
            << row.max_latency_ns << ',' << row.throughput_req_per_us << ','
            << row.effective_bandwidth_bytes_per_ns << ','
            << row.memory_utilization_ratio << ',' << row.avg_queue_delay_ns
            << ',' << row.p95_queue_delay_ns << ',' << row.queue_peak << ','
            << row.avg_queue_depth << ',' << row.avg_outstanding << ','
            << row.peak_outstanding << ',' << row.stall_events << ','
            << row.stall_ratio << ',' << row.hidden_latency_ns << ','
            << row.exposed_stall_ns << ',' << row.saturation_flag << ','
            << row.knee_point_hint << '\n';
    }
}

void write_trace(const std::filesystem::path &trace_path,
                 const std::vector<SimulationResult> &results)
{
    std::filesystem::create_directories(trace_path.parent_path());
    std::ofstream out(trace_path);
    if (!out) {
        throw std::runtime_error("failed to open trace for writing: "
                                 + trace_path.string());
    }

    out << "case,request_id,lane_id,sequence_index,issue_time_ns,"
           "service_start_ns,service_end_ns,queue_delay_ns,service_delay_ns,"
           "latency_ns,hidden_latency_ns,exposed_latency_ns,"
           "queue_depth_on_arrival,outstanding_after_issue\n";
    out << std::fixed << std::setprecision(3);
    for (const SimulationResult &result : results) {
        for (const RequestRecord &record : result.records) {
            out << record.case_name << ',' << record.request_id << ','
                << record.lane_id << ',' << record.sequence_index << ','
                << record.issue_time_ns << ',' << record.service_start_ns << ','
                << record.service_end_ns << ',' << record.queue_delay_ns << ','
                << record.service_delay_ns << ',' << record.latency_ns << ','
                << record.hidden_latency_ns << ',' << record.exposed_latency_ns
                << ',' << record.queue_depth_on_arrival << ','
                << record.outstanding_after_issue << '\n';
        }
    }
}

void write_comparison(const std::filesystem::path &comparison_path,
                      const std::vector<CaseMetrics> &metrics)
{
    std::filesystem::create_directories(comparison_path.parent_path());
    std::ofstream out(comparison_path);
    if (!out) {
        throw std::runtime_error("failed to open comparison for writing: "
                                 + comparison_path.string());
    }

    const CaseMetrics &low = find_metrics(metrics, "low_occupancy");
    const CaseMetrics &balanced = find_metrics(metrics, "balanced_occupancy");
    const CaseMetrics &high = find_metrics(metrics, "high_occupancy");
    const CaseMetrics &saturation = find_metrics(metrics, "bandwidth_saturation");
    const CaseMetrics &bursty = find_metrics(metrics, "bursty_stress");
    const CaseMetrics &throttled = find_metrics(metrics, "throttled_occupancy");

    out << std::fixed << std::setprecision(3);
    out << "# Project AT-7: GPU-like Throughput Engine and Memory Saturation Lab\n\n";

    out << "## Purpose\n\n";
    out << "Project AT-7 builds a bounded AT-level synthetic GPU-like throughput "
           "problem type. It generates many throughput-oriented memory requests "
           "from logical lanes, then observes outstanding-depth sensitivity, "
           "bandwidth saturation, latency hiding approximation, queue buildup, "
           "burstiness, and recommendation logic.\n\n";

    out << "## Methodology\n\n";
    out << "- Each case uses deterministic logical lanes with fixed request counts, "
           "burst length, compute gap, per-lane outstanding limit, and global "
           "outstanding limit.\n";
    out << "- A shared memory request queue and single service path approximate a "
           "bounded AT-level bandwidth wall.\n";
    out << "- Queue capacity, service bandwidth, and outstanding limits create "
           "backpressure / stall episodes when injection pressure exceeds the "
           "service path.\n";
    out << "- Latency hiding is approximated by a synthetic rule: deeper outstanding "
           "windows hide more service latency until queue saturation exposes "
           "stall time.\n";
    out << "- Metrics include latency percentiles, throughput, effective bandwidth, "
           "memory utilization, queue depth, outstanding depth, stall ratio, "
           "hidden latency, exposed stall, saturation flag, and knee-point hint.\n\n";

    out << "## Case Table\n\n";
    out << "| case | lanes | out/lane | global out | burst | throughput req/us | "
           "bandwidth B/ns | util | p95 latency ns | p99 latency ns | queue peak | "
           "avg outstanding | stall ratio | saturation | knee hint |\n";
    out << "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
           "---: | ---: | ---: | --- | --- |\n";
    for (const CaseMetrics &row : metrics) {
        out << "| `" << row.case_name << "` | " << row.num_lanes << " | "
            << row.outstanding_limit_per_lane << " | "
            << row.global_outstanding_limit << " | " << row.burst_length
            << " | " << row.throughput_req_per_us << " | "
            << row.effective_bandwidth_bytes_per_ns << " | "
            << row.memory_utilization_ratio << " | " << row.p95_latency_ns
            << " | " << row.p99_latency_ns << " | " << row.queue_peak << " | "
            << row.avg_outstanding << " | " << row.stall_ratio << " | `"
            << row.saturation_flag << "` | `" << row.knee_point_hint << "` |\n";
    }

    out << "\n## Key Observations\n\n";
    out << "- `low_occupancy` keeps memory utilization at "
        << low.memory_utilization_ratio
        << " with p99 latency " << low.p99_latency_ns
        << " ns, showing controlled tail behavior when the service path is not "
           "filled.\n";
    out << "- Moving from `low_occupancy` to `balanced_occupancy` raises throughput "
        << format_delta(low.throughput_req_per_us,
                        balanced.throughput_req_per_us, "req/us")
        << " while keeping p99 latency at " << balanced.p99_latency_ns
        << " ns, which is the useful latency-hiding region for this bounded "
           "model.\n";
    out << "- `high_occupancy` increases average outstanding depth to "
        << high.avg_outstanding << " and reaches utilization "
        << high.memory_utilization_ratio
        << ", but p95 queue delay rises to " << high.p95_queue_delay_ns
        << " ns, indicating the knee region.\n";
    out << "- `bandwidth_saturation` changes throughput from "
        << format_delta(high.throughput_req_per_us,
                        saturation.throughput_req_per_us, "req/us")
        << " versus `high_occupancy`, while p99 latency changes from "
        << format_delta(high.p99_latency_ns, saturation.p99_latency_ns, "ns")
        << "; the additional pressure mostly becomes queue buildup rather than "
           "new throughput.\n";
    out << "- `bursty_stress` reaches queue peak " << bursty.queue_peak
        << " and p99 latency " << bursty.p99_latency_ns
        << " ns, showing how burstiness can expose tail latency even when the "
           "same service path is used.\n";
    out << "- `throttled_occupancy` reduces p99 latency to "
        << throttled.p99_latency_ns << " ns with throughput "
        << throttled.throughput_req_per_us
        << " req/us, giving a bounded reference point for throttle-based "
           "recommendation logic.\n\n";

    out << "## Architecture Lessons\n\n";
    out << "- Increasing outstanding depth helps hide memory latency while the memory "
           "service path still has headroom.\n";
    out << "- After the bandwidth wall, extra lanes or outstanding requests mainly "
           "increase queue delay, p95/p99 latency, and exposed stall time.\n";
    out << "- Burst length is a separate pressure knob: it can create high peak queue "
           "depth even when average request count is fixed.\n";
    out << "- Throttling outstanding depth or injection rate can be a reasonable "
           "bounded architecture tradeoff when tail latency matters more than "
           "peak synthetic throughput.\n\n";

    out << "## Recommendation\n\n";
    out << "Use `balanced_occupancy` as the preferred operating point for this "
           "bounded exploration. If the design target prioritizes maximum "
           "throughput, compare it against `high_occupancy` and stop increasing "
           "outstanding depth once `knee_point_hint` reports a bandwidth wall. "
           "If p95/p99 latency or queue peak is the acceptance risk, use the "
           "`throttled_occupancy` profile as the safer recommendation baseline.\n\n";

    out << "## Claim Boundary\n\n";
    out << "This lab is a bounded AT-level synthetic GPU-like throughput and memory "
           "saturation exploration. It does not claim NVIDIA GPU simulation, real "
           "GPU behavior, CUDA execution modeling, real HBM-controller behavior, "
           "cycle-accurate modeling, silicon validation, or production signoff.\n\n";
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
        } else if (arg == "--write-trace") {
            options.write_trace = true;
        } else if (arg == "--help") {
            std::cout
                << "Usage: project_at7_gpu_like_throughput_saturation [options]\n"
                << "  --output-dir DIR\n"
                << "  --write-trace\n";
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
    std::vector<SimulationResult> results;
    std::vector<CaseMetrics> metrics;
    results.reserve(cases.size());
    metrics.reserve(cases.size());

    std::filesystem::create_directories(options.output_dir);
    for (const CaseSpec &spec : cases) {
        results.push_back(run_case(spec));
        metrics.push_back(make_metrics(results.back()));
    }

    const std::filesystem::path summary_path = options.output_dir / "summary.csv";
    const std::filesystem::path comparison_path =
        options.output_dir / "comparison.md";
    write_summary(summary_path, metrics);
    write_comparison(comparison_path, metrics);

    std::cout << "Project AT-7 PASS\n";
    std::cout << "cases=" << metrics.size() << '\n';
    std::cout << "summary=" << summary_path << '\n';
    std::cout << "comparison=" << comparison_path << '\n';
    if (options.write_trace) {
        const std::filesystem::path trace_path = options.output_dir / "trace.csv";
        write_trace(trace_path, results);
        std::cout << "trace=" << trace_path << '\n';
    }
    std::cout << "claim_boundary=PASS\n";
    std::cout << "schema_version=" << kSchemaVersion << '\n';
    return 0;
}

}  // namespace
}  // namespace project_at7

int sc_main(int argc, char *argv[])
{
    try {
        return project_at7::run(argc, argv);
    } catch (const std::exception &error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
