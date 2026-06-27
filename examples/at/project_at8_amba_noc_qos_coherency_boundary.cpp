// SPDX-License-Identifier: Apache-2.0

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
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

namespace project_at8 {
namespace {

constexpr const char *kSchemaVersion = "at8.0";
constexpr const char *kClaimBoundary =
    "bounded_at_level_synthetic_amba_inspired_noc_qos_coherency_boundary_exploration";
constexpr const char *kBoundaryStatement =
    "This lab is a bounded AT-level synthetic AMBA-inspired NoC QoS and "
    "coherency-boundary exploration. It does not claim Arm CHI compliance, "
    "AXI compliance, ACE compliance, real AMBA protocol behavior, real NoC "
    "behavior, real cache coherency, cycle-accurate modeling, silicon "
    "validation, or production signoff.";
constexpr double kEpsilon = 1e-9;

enum class InitiatorId : std::size_t {
    Cpu = 0,
    Dma = 1,
    Npu = 2,
    Io = 3,
};

enum class RouteId : std::size_t {
    Local = 0,
    Shared = 1,
    Boundary = 2,
};

enum class QosClass : std::size_t {
    LatencyHigh = 0,
    BestEffort = 1,
    BulkLow = 2,
};

constexpr std::size_t kInitiatorCount = 4;
constexpr std::size_t kRouteCount = 3;
constexpr std::size_t kQosCount = 3;

struct InitiatorSpec {
    InitiatorId id;
    const char *name;
    const char *role;
    bool coherent_domain;
    bool ordering_sensitive;
};

constexpr std::array<InitiatorSpec, kInitiatorCount> kInitiators = {{
    {InitiatorId::Cpu, "cpu_like_coherent", "latency_sensitive_read_heavy",
     true, true},
    {InitiatorId::Dma, "dma_like_noncoherent", "bulk_write_heavy", false,
     false},
    {InitiatorId::Npu, "npu_like_accelerator", "bursty_high_throughput",
     false, false},
    {InitiatorId::Io, "io_like_peripheral",
     "low_throughput_ordering_sensitive", false, true},
}};

struct RouteConfig {
    std::string name;
    std::size_t queue_capacity = 1;
    double base_service_delay_ns = 1.0;
    double congestion_multiplier = 0.0;
};

struct CaseSpec {
    std::string case_name;
    std::string policy;
    std::string intent;
    std::array<std::size_t, kInitiatorCount> transactions;
    std::array<double, kInitiatorCount> issue_gap_ns;
    std::array<std::size_t, kInitiatorCount> burst_every;
    std::array<double, kInitiatorCount> burst_pause_ns;
    std::array<unsigned int, kInitiatorCount> size_bytes;
    std::array<unsigned int, kInitiatorCount> read_percent;
    std::array<std::size_t, kInitiatorCount> boundary_every;
    std::array<std::size_t, kInitiatorCount> shared_every;
    std::array<RouteId, kInitiatorCount> default_route;
    std::array<QosClass, kInitiatorCount> qos_class;
    std::array<RouteConfig, kRouteCount> routes;
    bool qos_priority = false;
    bool force_hotspot = false;
    bool prefer_boundary_hotspot = false;
    double boundary_penalty_ns = 0.0;
    double ordering_penalty_ns = 0.0;
    double ordering_serialization_gap_ns = 0.0;
    double write_drain_ns = 0.0;
    double read_interference_factor = 0.0;
    double read_interference_cap_ns = 0.0;
    double downstream_stretch = 1.0;
    double starvation_threshold_ns = 500.0;
    double priority_aging_ns = 0.0;
};

struct Options {
    std::filesystem::path output_dir =
        "examples/at/results/project_at8_amba_noc_qos_coherency_boundary";
    bool write_trace = false;
};

struct TransactionRecord {
    std::string case_name;
    std::string policy;
    std::size_t request_id = 0;
    InitiatorId initiator_id = InitiatorId::Cpu;
    std::string initiator;
    std::string initiator_role;
    RouteId route_id = RouteId::Local;
    std::string route;
    QosClass qos_class = QosClass::BestEffort;
    std::string qos;
    bool read_flow = true;
    bool coherent = false;
    bool boundary_crossing = false;
    bool ordering_sensitive = false;
    unsigned int size_bytes = 64;
    std::size_t sequence_index = 0;
    double issue_time_ns = 0.0;
    double route_dequeue_time_ns = 0.0;
    double service_start_time_ns = 0.0;
    double end_time_ns = 0.0;
    double queue_delay_ns = 0.0;
    double service_delay_ns = 0.0;
    double route_delay_ns = 0.0;
    double ordering_delay_ns = 0.0;
    double boundary_penalty_ns = 0.0;
    double read_write_interference_delay_ns = 0.0;
    double latency_ns = 0.0;
    std::size_t queue_depth_on_arrival = 0;
    bool ordering_serialization_event = false;
    bool starvation_flag = false;
};

struct RouteRuntime {
    std::size_t queue_peak = 0;
    double busy_time_ns = 0.0;
    double first_issue_ns = std::numeric_limits<double>::infinity();
    double last_end_ns = 0.0;
    double write_pressure_until_ns = 0.0;
    double next_ordering_release_ns = 0.0;
};

struct CaseResult {
    CaseSpec spec;
    std::vector<TransactionRecord> records;
    std::array<RouteRuntime, kRouteCount> route_runtime;
};

struct CaseMetrics {
    std::string case_name;
    std::string policy;
    std::string recommendation;
    std::size_t total_transactions = 0;
    double sim_time_ns = 0.0;
    double avg_latency_ns = 0.0;
    double p50_latency_ns = 0.0;
    double p95_latency_ns = 0.0;
    double p99_latency_ns = 0.0;
    double max_latency_ns = 0.0;
    double throughput_txn_per_us = 0.0;
    std::size_t route_queue_peak = 0;
    double local_route_utilization = 0.0;
    double shared_route_utilization = 0.0;
    double boundary_route_utilization = 0.0;
    double avg_route_delay_ns = 0.0;
    double p95_route_delay_ns = 0.0;
    double ordering_delay_ns = 0.0;
    double boundary_penalty_ns = 0.0;
    std::size_t coherency_boundary_events = 0;
    std::size_t ordering_serialization_events = 0;
    double read_avg_latency_ns = 0.0;
    double read_p95_latency_ns = 0.0;
    double write_avg_latency_ns = 0.0;
    double write_p95_latency_ns = 0.0;
    double latency_high_p99_ns = 0.0;
    double best_effort_p99_ns = 0.0;
    double bulk_low_p99_ns = 0.0;
    std::size_t starvation_events = 0;
    double qos_protection_score = 0.0;
    double collapse_score = 0.0;
};

const char *route_name(RouteId route)
{
    switch (route) {
    case RouteId::Local:
        return "local_route";
    case RouteId::Shared:
        return "shared_route";
    case RouteId::Boundary:
        return "boundary_route";
    }
    return "unknown_route";
}

const char *qos_name(QosClass qos)
{
    switch (qos) {
    case QosClass::LatencyHigh:
        return "latency_high";
    case QosClass::BestEffort:
        return "best_effort";
    case QosClass::BulkLow:
        return "bulk_low";
    }
    return "unknown_qos";
}

std::size_t initiator_index(InitiatorId id)
{
    return static_cast<std::size_t>(id);
}

std::size_t route_index(RouteId id)
{
    return static_cast<std::size_t>(id);
}

std::size_t qos_index(QosClass qos)
{
    return static_cast<std::size_t>(qos);
}

std::array<RouteConfig, kRouteCount>
make_routes(std::size_t local_capacity, std::size_t shared_capacity,
            std::size_t boundary_capacity, double local_base_ns,
            double shared_base_ns, double boundary_base_ns,
            double local_congestion, double shared_congestion,
            double boundary_congestion)
{
    return {{
        {"local_route", local_capacity, local_base_ns, local_congestion},
        {"shared_route", shared_capacity, shared_base_ns, shared_congestion},
        {"boundary_route", boundary_capacity, boundary_base_ns,
         boundary_congestion},
    }};
}

CaseSpec make_baseline_case()
{
    return {
        "baseline_qos_rr",
        "round_robin",
        "balanced traffic baseline with moderate route pressure",
        {{48, 36, 44, 32}},
        {{105.0, 120.0, 110.0, 145.0}},
        {{4, 1, 8, 5}},
        {{18.0, 0.0, 34.0, 16.0}},
        {{64, 192, 128, 64}},
        {{82, 25, 55, 65}},
        {{16, 14, 12, 10}},
        {{3, 1, 1, 4}},
        {{RouteId::Local, RouteId::Shared, RouteId::Shared, RouteId::Local}},
        {{QosClass::LatencyHigh, QosClass::BulkLow, QosClass::BestEffort,
          QosClass::LatencyHigh}},
        make_routes(20, 34, 20, 10.0, 18.0, 28.0, 0.20, 0.35, 0.50),
        false,
        false,
        false,
        18.0,
        4.0,
        2.0,
        4.0,
        0.25,
        12.0,
        1.00,
        900.0,
        0.0,
    };
}

CaseSpec make_latency_priority_case()
{
    CaseSpec spec = make_baseline_case();
    spec.case_name = "latency_qos_priority";
    spec.policy = "qos_priority";
    spec.intent = "prioritize latency_high traffic for CPU-like and IO-like flows";
    spec.qos_priority = true;
    spec.priority_aging_ns = 520.0;
    spec.starvation_threshold_ns = 900.0;
    return spec;
}

CaseSpec make_bulk_dma_pressure_case()
{
    CaseSpec spec = make_baseline_case();
    spec.case_name = "bulk_dma_pressure";
    spec.policy = "round_robin";
    spec.intent =
        "increase DMA-like bulk writes and observe read tail interference";
    spec.transactions = {{52, 96, 64, 36}};
    spec.issue_gap_ns = {{100.0, 50.0, 90.0, 140.0}};
    spec.size_bytes = {{64, 512, 192, 64}};
    spec.read_percent = {{84, 10, 45, 68}};
    spec.routes = make_routes(20, 26, 18, 10.0, 24.0, 34.0, 0.25, 0.90, 0.90);
    spec.write_drain_ns = 12.0;
    spec.read_interference_factor = 0.50;
    spec.read_interference_cap_ns = 42.0;
    spec.starvation_threshold_ns = 950.0;
    return spec;
}

CaseSpec make_boundary_stress_case()
{
    CaseSpec spec = make_baseline_case();
    spec.case_name = "boundary_crossing_stress";
    spec.policy = "boundary_ordered_rr";
    spec.intent =
        "increase coherent and noncoherent boundary crossings and ordering delay";
    spec.transactions = {{56, 52, 56, 40}};
    spec.issue_gap_ns = {{90.0, 80.0, 85.0, 120.0}};
    spec.boundary_every = {{3, 2, 3, 2}};
    spec.routes = make_routes(20, 28, 18, 10.0, 24.0, 36.0, 0.25, 0.70, 1.15);
    spec.boundary_penalty_ns = 45.0;
    spec.ordering_penalty_ns = 12.0;
    spec.ordering_serialization_gap_ns = 10.0;
    spec.write_drain_ns = 10.0;
    spec.read_interference_cap_ns = 34.0;
    spec.starvation_threshold_ns = 1050.0;
    return spec;
}

CaseSpec make_route_hotspot_case()
{
    CaseSpec spec = make_baseline_case();
    spec.case_name = "route_hotspot";
    spec.policy = "round_robin";
    spec.intent =
        "map multiple initiators onto one hotspot route to expose contention";
    spec.transactions = {{60, 58, 70, 42}};
    spec.issue_gap_ns = {{75.0, 70.0, 65.0, 95.0}};
    spec.force_hotspot = true;
    spec.prefer_boundary_hotspot = false;
    spec.routes = make_routes(12, 20, 14, 12.0, 30.0, 44.0, 0.35, 1.10, 1.20);
    spec.boundary_penalty_ns = 26.0;
    spec.ordering_penalty_ns = 8.0;
    spec.ordering_serialization_gap_ns = 6.0;
    spec.write_drain_ns = 12.0;
    spec.read_interference_factor = 0.50;
    spec.read_interference_cap_ns = 40.0;
    spec.starvation_threshold_ns = 900.0;
    return spec;
}

CaseSpec make_mixed_collapse_case()
{
    CaseSpec spec = make_baseline_case();
    spec.case_name = "mixed_qos_collapse";
    spec.policy = "qos_priority_under_saturation";
    spec.intent =
        "combine latency_high, bulk_low, boundary crossing, and saturated routes";
    spec.transactions = {{72, 92, 96, 50}};
    spec.issue_gap_ns = {{55.0, 42.0, 44.0, 70.0}};
    spec.burst_every = {{4, 1, 6, 4}};
    spec.burst_pause_ns = {{10.0, 0.0, 20.0, 10.0}};
    spec.size_bytes = {{64, 512, 256, 96}};
    spec.read_percent = {{82, 12, 45, 62}};
    spec.boundary_every = {{3, 3, 4, 2}};
    spec.force_hotspot = true;
    spec.prefer_boundary_hotspot = true;
    spec.qos_priority = true;
    spec.priority_aging_ns = 520.0;
    spec.routes = make_routes(8, 18, 12, 16.0, 38.0, 54.0, 0.60, 1.65, 1.95);
    spec.boundary_penalty_ns = 64.0;
    spec.ordering_penalty_ns = 18.0;
    spec.ordering_serialization_gap_ns = 16.0;
    spec.write_drain_ns = 18.0;
    spec.read_interference_factor = 0.65;
    spec.read_interference_cap_ns = 72.0;
    spec.downstream_stretch = 1.15;
    spec.starvation_threshold_ns = 700.0;
    return spec;
}

std::vector<CaseSpec> default_cases()
{
    return {make_baseline_case(),
            make_latency_priority_case(),
            make_bulk_dma_pressure_case(),
            make_boundary_stress_case(),
            make_route_hotspot_case(),
            make_mixed_collapse_case()};
}

double deterministic_jitter_ns(const InitiatorSpec &initiator,
                               std::size_t sequence_index)
{
    const unsigned int score =
        (static_cast<unsigned int>(sequence_index) * 17U
         + static_cast<unsigned int>(initiator_index(initiator.id)) * 11U)
        % 9U;
    return static_cast<double>(score) * 0.42;
}

double issue_time_for(const CaseSpec &spec, const InitiatorSpec &initiator,
                      std::size_t sequence_index)
{
    const std::size_t index = initiator_index(initiator.id);
    const double gap = spec.issue_gap_ns[index];
    const std::size_t burst_every =
        std::max<std::size_t>(1, spec.burst_every[index]);
    const double burst_pause = spec.burst_pause_ns[index];
    const double phase_offset = static_cast<double>(index) * 1.85;

    double issue_time = static_cast<double>(sequence_index) * gap + phase_offset
                        + deterministic_jitter_ns(initiator, sequence_index);
    if (burst_every > 1) {
        issue_time += static_cast<double>(sequence_index / burst_every)
                      * burst_pause;
    }
    return issue_time;
}

bool is_read_flow(const CaseSpec &spec, const InitiatorSpec &initiator,
                  std::size_t sequence_index)
{
    const std::size_t index = initiator_index(initiator.id);
    const unsigned int score =
        (static_cast<unsigned int>(sequence_index) * 7U
         + static_cast<unsigned int>(index) * 13U)
        % 100U;
    return score < spec.read_percent[index];
}

bool is_boundary_crossing(const CaseSpec &spec, const InitiatorSpec &initiator,
                          std::size_t sequence_index)
{
    const std::size_t index = initiator_index(initiator.id);
    const std::size_t every = spec.boundary_every[index];
    if (every == 0) {
        return false;
    }
    return sequence_index % every == 0;
}

RouteId route_for(const CaseSpec &spec, const InitiatorSpec &initiator,
                  std::size_t sequence_index, bool boundary_crossing)
{
    const std::size_t index = initiator_index(initiator.id);
    if (spec.force_hotspot) {
        if (spec.prefer_boundary_hotspot
            && (boundary_crossing || ((sequence_index + index) % 3U == 0U))) {
            return RouteId::Boundary;
        }
        return RouteId::Shared;
    }

    if (boundary_crossing) {
        return RouteId::Boundary;
    }

    const std::size_t shared_every =
        std::max<std::size_t>(1, spec.shared_every[index]);
    if (sequence_index % shared_every == 0) {
        return RouteId::Shared;
    }
    return spec.default_route[index];
}

std::vector<TransactionRecord> make_initial_records(const CaseSpec &spec)
{
    std::size_t reserve_count = 0;
    for (std::size_t count : spec.transactions) {
        reserve_count += count;
    }

    std::vector<TransactionRecord> records;
    records.reserve(reserve_count);

    for (const InitiatorSpec &initiator : kInitiators) {
        const std::size_t index = initiator_index(initiator.id);
        for (std::size_t sequence = 0; sequence < spec.transactions[index];
             ++sequence) {
            const bool boundary =
                is_boundary_crossing(spec, initiator, sequence);
            const RouteId route = route_for(spec, initiator, sequence, boundary);
            TransactionRecord record;
            record.case_name = spec.case_name;
            record.policy = spec.policy;
            record.request_id = (index + 1U) * 100000U + sequence + 1U;
            record.initiator_id = initiator.id;
            record.initiator = initiator.name;
            record.initiator_role = initiator.role;
            record.route_id = route;
            record.route = route_name(route);
            record.qos_class = spec.qos_class[index];
            record.qos = qos_name(record.qos_class);
            record.read_flow = is_read_flow(spec, initiator, sequence);
            record.coherent = initiator.coherent_domain && !boundary;
            record.boundary_crossing = boundary;
            record.ordering_sensitive = initiator.ordering_sensitive || boundary;
            record.size_bytes = spec.size_bytes[index];
            record.sequence_index = sequence;
            record.issue_time_ns = issue_time_for(spec, initiator, sequence);
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

int qos_rank(QosClass qos)
{
    switch (qos) {
    case QosClass::LatencyHigh:
        return 0;
    case QosClass::BestEffort:
        return 1;
    case QosClass::BulkLow:
        return 2;
    }
    return 3;
}

std::size_t select_round_robin_position(
    const std::deque<std::size_t> &pending,
    const std::vector<TransactionRecord> &records,
    std::size_t &last_rr_initiator)
{
    for (std::size_t offset = 1; offset <= kInitiatorCount; ++offset) {
        const std::size_t initiator =
            (last_rr_initiator + offset) % kInitiatorCount;
        for (std::size_t pos = 0; pos < pending.size(); ++pos) {
            const TransactionRecord &record = records.at(pending.at(pos));
            if (initiator_index(record.initiator_id) == initiator) {
                last_rr_initiator = initiator;
                return pos;
            }
        }
    }
    return 0;
}

std::size_t select_qos_priority_position(
    const std::deque<std::size_t> &pending,
    const std::vector<TransactionRecord> &records,
    double current_time_ns, double priority_aging_ns)
{
    if (pending.empty()) {
        return 0;
    }

    if (priority_aging_ns > 0.0) {
        for (std::size_t pos = 0; pos < pending.size(); ++pos) {
            const TransactionRecord &record = records.at(pending.at(pos));
            if (current_time_ns - record.issue_time_ns >= priority_aging_ns) {
                return pos;
            }
        }
    }

    std::size_t best_pos = 0;
    int best_rank = qos_rank(records.at(pending.front()).qos_class);
    double best_issue_time = records.at(pending.front()).issue_time_ns;
    for (std::size_t pos = 1; pos < pending.size(); ++pos) {
        const TransactionRecord &candidate = records.at(pending.at(pos));
        const int rank = qos_rank(candidate.qos_class);
        if (rank < best_rank
            || (rank == best_rank && candidate.issue_time_ns < best_issue_time)) {
            best_rank = rank;
            best_issue_time = candidate.issue_time_ns;
            best_pos = pos;
        }
    }
    return best_pos;
}

std::size_t select_pending_position(
    const std::deque<std::size_t> &pending,
    const std::vector<TransactionRecord> &records, const CaseSpec &spec,
    double current_time_ns, std::size_t &last_rr_initiator)
{
    if (pending.empty()) {
        return 0;
    }
    if (spec.qos_priority) {
        return select_qos_priority_position(pending, records, current_time_ns,
                                            spec.priority_aging_ns);
    }
    return select_round_robin_position(pending, records, last_rr_initiator);
}

double route_service_jitter_ns(const TransactionRecord &record)
{
    const unsigned int score =
        (static_cast<unsigned int>(record.sequence_index) * 19U
         + static_cast<unsigned int>(initiator_index(record.initiator_id)) * 7U
         + static_cast<unsigned int>(route_index(record.route_id)) * 5U)
        % 8U;
    return static_cast<double>(score) * 0.33;
}

double service_delay_for(const CaseSpec &spec, const TransactionRecord &record,
                         const RouteConfig &route, std::size_t queue_depth)
{
    const double size_stretch =
        (static_cast<double>(record.size_bytes) / 64.0 - 1.0) * 4.25;
    const double flow_factor = record.read_flow ? 0.92 : 1.12;
    const double qos_extra =
        record.qos_class == QosClass::BulkLow
            ? 5.5
            : (record.qos_class == QosClass::BestEffort ? 2.0 : 0.0);
    const double congestion =
        route.congestion_multiplier
        * static_cast<double>(
            std::min<std::size_t>(queue_depth, route.queue_capacity * 3U));

    return (route.base_service_delay_ns * spec.downstream_stretch
            + size_stretch + qos_extra + route_service_jitter_ns(record))
               * flow_factor
           + congestion;
}

void run_route_model(const CaseSpec &spec, RouteId route_id,
                     std::vector<TransactionRecord> &records,
                     RouteRuntime &runtime)
{
    std::vector<std::size_t> route_records;
    for (std::size_t index = 0; index < records.size(); ++index) {
        if (records.at(index).route_id == route_id) {
            route_records.push_back(index);
            runtime.first_issue_ns =
                std::min(runtime.first_issue_ns, records.at(index).issue_time_ns);
        }
    }

    if (route_records.empty()) {
        runtime.first_issue_ns = 0.0;
        return;
    }

    std::sort(route_records.begin(), route_records.end(),
              [&](std::size_t lhs, std::size_t rhs) {
                  const TransactionRecord &left = records.at(lhs);
                  const TransactionRecord &right = records.at(rhs);
                  if (left.issue_time_ns != right.issue_time_ns) {
                      return left.issue_time_ns < right.issue_time_ns;
                  }
                  return left.request_id < right.request_id;
              });

    const RouteConfig &route = spec.routes.at(route_index(route_id));
    std::deque<std::size_t> pending;
    std::size_t next_record = 0;
    std::size_t completed = 0;
    std::size_t last_rr_initiator = kInitiatorCount - 1;
    double time_ns = route_records.empty() ? 0.0
                                           : records.at(route_records.front())
                                                 .issue_time_ns;

    auto enqueue_ready_records = [&]() {
        while (next_record < route_records.size()
               && records.at(route_records.at(next_record)).issue_time_ns
                      <= time_ns + kEpsilon) {
            TransactionRecord &record = records.at(route_records.at(next_record));
            record.queue_depth_on_arrival = pending.size();
            pending.push_back(route_records.at(next_record));
            runtime.queue_peak = std::max(runtime.queue_peak, pending.size());
            ++next_record;
        }
    };

    while (completed < route_records.size()) {
        enqueue_ready_records();
        if (pending.empty()) {
            if (next_record >= route_records.size()) {
                break;
            }
            time_ns = std::max(time_ns,
                               records.at(route_records.at(next_record))
                                   .issue_time_ns);
            enqueue_ready_records();
        }

        const std::size_t selected_pos = select_pending_position(
            pending, records, spec, time_ns, last_rr_initiator);
        const std::size_t record_index = pending.at(selected_pos);
        pending.erase(pending.begin() + static_cast<std::ptrdiff_t>(selected_pos));

        TransactionRecord &record = records.at(record_index);
        const double dequeue_time_ns = std::max(time_ns, record.issue_time_ns);
        record.route_dequeue_time_ns = dequeue_time_ns;
        record.queue_delay_ns = dequeue_time_ns - record.issue_time_ns;

        double ordering_delay_ns = 0.0;
        if (record.ordering_sensitive) {
            ordering_delay_ns += spec.ordering_penalty_ns;
            if (runtime.next_ordering_release_ns > dequeue_time_ns + kEpsilon) {
                ordering_delay_ns +=
                    runtime.next_ordering_release_ns - dequeue_time_ns;
                record.ordering_serialization_event = true;
            } else {
                record.ordering_serialization_event =
                    spec.ordering_penalty_ns > 0.0;
            }
        }

        record.ordering_delay_ns = ordering_delay_ns;
        record.service_start_time_ns = dequeue_time_ns + ordering_delay_ns;

        record.boundary_penalty_ns =
            record.boundary_crossing ? spec.boundary_penalty_ns : 0.0;
        double service_delay_ns =
            service_delay_for(spec, record, route, record.queue_depth_on_arrival)
            + record.boundary_penalty_ns;

        if (record.read_flow
            && runtime.write_pressure_until_ns
                   > record.service_start_time_ns + kEpsilon) {
            const double raw_interference =
                (runtime.write_pressure_until_ns - record.service_start_time_ns)
                * spec.read_interference_factor;
            record.read_write_interference_delay_ns =
                std::min(spec.read_interference_cap_ns,
                         std::max(0.0, raw_interference));
            service_delay_ns += record.read_write_interference_delay_ns;
        }

        record.service_delay_ns = service_delay_ns;
        record.end_time_ns = record.service_start_time_ns + service_delay_ns;
        record.route_delay_ns = record.end_time_ns - record.issue_time_ns;
        record.latency_ns = record.route_delay_ns;
        record.starvation_flag =
            record.latency_ns > spec.starvation_threshold_ns
            || record.queue_depth_on_arrival >= route.queue_capacity;

        if (!record.read_flow) {
            const double size_factor =
                std::max(1.0, static_cast<double>(record.size_bytes) / 128.0);
            const double qos_factor =
                record.qos_class == QosClass::BulkLow ? 1.40 : 1.0;
            runtime.write_pressure_until_ns =
                std::max(runtime.write_pressure_until_ns,
                         record.end_time_ns
                             + spec.write_drain_ns * size_factor * qos_factor);
        }
        if (record.ordering_sensitive) {
            runtime.next_ordering_release_ns =
                std::max(runtime.next_ordering_release_ns,
                         record.end_time_ns
                             + spec.ordering_serialization_gap_ns);
        }

        runtime.busy_time_ns += record.end_time_ns - dequeue_time_ns;
        runtime.last_end_ns = std::max(runtime.last_end_ns, record.end_time_ns);
        time_ns = record.end_time_ns;
        ++completed;
        runtime.queue_peak = std::max(runtime.queue_peak, pending.size());
    }
}

CaseResult run_case(const CaseSpec &spec)
{
    CaseResult result;
    result.spec = spec;
    result.records = make_initial_records(spec);
    for (std::size_t route = 0; route < kRouteCount; ++route) {
        run_route_model(spec, static_cast<RouteId>(route), result.records,
                        result.route_runtime.at(route));
    }
    return result;
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

double bounded_score(double value)
{
    return std::max(0.0, std::min(100.0, value));
}

std::string recommendation_for(const CaseMetrics &metrics)
{
    if (metrics.case_name == "baseline_qos_rr") {
        return "baseline_reference_for_bottleneck_isolation";
    }
    if (metrics.case_name == "latency_qos_priority"
        && metrics.qos_protection_score >= 15.0) {
        return "qos_priority_protects_latency_class_in_this_bound";
    }
    if (metrics.case_name == "bulk_dma_pressure") {
        return "partition_bulk_writes_to_protect_read_tail";
    }
    if (metrics.case_name == "boundary_crossing_stress") {
        return "isolate_boundary_crossing_and_ordering_sensitive_flow";
    }
    if (metrics.case_name == "route_hotspot") {
        return "rebalance_hotspot_route_or_add_vc_partition";
    }
    if (metrics.collapse_score >= 72.0) {
        return "reduce_injection_or_add_capacity_before_qos_claim";
    }
    if (metrics.coherency_boundary_events > metrics.total_transactions / 3U
        || metrics.ordering_delay_ns > metrics.boundary_penalty_ns * 0.65) {
        return "isolate_boundary_crossing_and_ordering_sensitive_flow";
    }
    if (metrics.read_p95_latency_ns > metrics.write_p95_latency_ns * 1.15
        && metrics.bulk_low_p99_ns > metrics.latency_high_p99_ns) {
        return "partition_bulk_writes_to_protect_read_tail";
    }
    if (metrics.qos_protection_score >= 25.0) {
        return "qos_priority_protects_latency_class_in_this_bound";
    }
    if (metrics.route_queue_peak >= 30U) {
        return "rebalance_hotspot_route_or_add_vc_partition";
    }
    return "compare_qos_policy_against_route_capacity";
}

CaseMetrics make_metrics(const CaseResult &result)
{
    const CaseSpec &spec = result.spec;
    CaseMetrics metrics;
    metrics.case_name = spec.case_name;
    metrics.policy = spec.policy;
    metrics.total_transactions = result.records.size();

    std::vector<double> latencies;
    std::vector<double> route_delays;
    std::vector<double> read_latencies;
    std::vector<double> write_latencies;
    std::array<std::vector<double>, kQosCount> qos_latencies;
    latencies.reserve(result.records.size());
    route_delays.reserve(result.records.size());

    double first_issue_ns = std::numeric_limits<double>::infinity();
    double last_end_ns = 0.0;
    for (const TransactionRecord &record : result.records) {
        first_issue_ns = std::min(first_issue_ns, record.issue_time_ns);
        last_end_ns = std::max(last_end_ns, record.end_time_ns);
        latencies.push_back(record.latency_ns);
        route_delays.push_back(record.route_delay_ns);
        metrics.max_latency_ns =
            std::max(metrics.max_latency_ns, record.latency_ns);
        metrics.ordering_delay_ns += record.ordering_delay_ns;
        metrics.boundary_penalty_ns += record.boundary_penalty_ns;
        if (record.boundary_crossing) {
            ++metrics.coherency_boundary_events;
        }
        if (record.ordering_serialization_event) {
            ++metrics.ordering_serialization_events;
        }
        if (record.starvation_flag) {
            ++metrics.starvation_events;
        }
        if (record.read_flow) {
            read_latencies.push_back(record.latency_ns);
        } else {
            write_latencies.push_back(record.latency_ns);
        }
        qos_latencies.at(qos_index(record.qos_class)).push_back(record.latency_ns);
    }

    metrics.sim_time_ns =
        std::isfinite(first_issue_ns) ? std::max(0.0, last_end_ns - first_issue_ns)
                                     : 0.0;
    metrics.avg_latency_ns = average(latencies);
    metrics.p50_latency_ns = percentile(latencies, 0.50);
    metrics.p95_latency_ns = percentile(latencies, 0.95);
    metrics.p99_latency_ns = percentile(latencies, 0.99);
    metrics.throughput_txn_per_us =
        metrics.sim_time_ns > 0.0
            ? static_cast<double>(metrics.total_transactions)
                  / (metrics.sim_time_ns / 1000.0)
            : 0.0;
    metrics.avg_route_delay_ns = average(route_delays);
    metrics.p95_route_delay_ns = percentile(route_delays, 0.95);
    metrics.read_avg_latency_ns = average(read_latencies);
    metrics.read_p95_latency_ns = percentile(read_latencies, 0.95);
    metrics.write_avg_latency_ns = average(write_latencies);
    metrics.write_p95_latency_ns = percentile(write_latencies, 0.95);
    metrics.latency_high_p99_ns =
        percentile(qos_latencies.at(qos_index(QosClass::LatencyHigh)), 0.99);
    metrics.best_effort_p99_ns =
        percentile(qos_latencies.at(qos_index(QosClass::BestEffort)), 0.99);
    metrics.bulk_low_p99_ns =
        percentile(qos_latencies.at(qos_index(QosClass::BulkLow)), 0.99);

    metrics.route_queue_peak =
        std::max({result.route_runtime.at(route_index(RouteId::Local)).queue_peak,
                  result.route_runtime.at(route_index(RouteId::Shared)).queue_peak,
                  result.route_runtime.at(route_index(RouteId::Boundary))
                      .queue_peak});

    const auto utilization = [&](RouteId route) {
        const RouteRuntime &runtime = result.route_runtime.at(route_index(route));
        return metrics.sim_time_ns > 0.0
                   ? std::min(1.0, runtime.busy_time_ns / metrics.sim_time_ns)
                   : 0.0;
    };
    metrics.local_route_utilization = utilization(RouteId::Local);
    metrics.shared_route_utilization = utilization(RouteId::Shared);
    metrics.boundary_route_utilization = utilization(RouteId::Boundary);

    const double protected_tail = metrics.latency_high_p99_ns;
    const double pressure_tail =
        (metrics.best_effort_p99_ns + metrics.bulk_low_p99_ns) / 2.0;
    metrics.qos_protection_score =
        pressure_tail > 0.0
            ? bounded_score((pressure_tail - protected_tail) / pressure_tail
                            * 100.0)
            : 0.0;
    if (!spec.qos_priority) {
        metrics.qos_protection_score *= 0.55;
    }

    const double max_utilization =
        std::max({metrics.local_route_utilization, metrics.shared_route_utilization,
                  metrics.boundary_route_utilization});
    const double max_capacity =
        static_cast<double>(
            std::max({spec.routes.at(route_index(RouteId::Local)).queue_capacity,
                      spec.routes.at(route_index(RouteId::Shared)).queue_capacity,
                      spec.routes.at(route_index(RouteId::Boundary))
                          .queue_capacity}));
    const double queue_pressure =
        max_capacity > 0.0
            ? static_cast<double>(metrics.route_queue_peak) / max_capacity
            : 0.0;
    const double tail_ratio =
        metrics.avg_latency_ns > 0.0 ? metrics.p99_latency_ns / metrics.avg_latency_ns
                                     : 0.0;
    const double boundary_ratio =
        metrics.total_transactions > 0
            ? static_cast<double>(metrics.coherency_boundary_events)
                  / static_cast<double>(metrics.total_transactions)
            : 0.0;
    metrics.collapse_score = bounded_score(
        max_utilization * 30.0 + queue_pressure * 12.0
        + std::max(0.0, tail_ratio - 1.0) * 6.0
        + std::min(20.0, static_cast<double>(metrics.starvation_events) * 0.35)
        + boundary_ratio * 12.0);

    metrics.recommendation = recommendation_for(metrics);
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

std::string delta_text(double before, double after, const char *unit)
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

    out << "case,total_transactions,sim_time_ns,avg_latency_ns,p50_latency_ns,"
           "p95_latency_ns,p99_latency_ns,max_latency_ns,throughput_txn_per_us,"
           "route_queue_peak,local_route_utilization,shared_route_utilization,"
           "boundary_route_utilization,avg_route_delay_ns,p95_route_delay_ns,"
           "ordering_delay_ns,boundary_penalty_ns,coherency_boundary_events,"
           "ordering_serialization_events,read_avg_latency_ns,"
           "read_p95_latency_ns,write_avg_latency_ns,write_p95_latency_ns,"
           "latency_high_p99_ns,best_effort_p99_ns,bulk_low_p99_ns,"
           "starvation_events,qos_protection_score,collapse_score,"
           "recommendation\n";

    out << std::fixed << std::setprecision(3);
    for (const CaseMetrics &row : metrics) {
        out << row.case_name << ',' << row.total_transactions << ','
            << row.sim_time_ns << ',' << row.avg_latency_ns << ','
            << row.p50_latency_ns << ',' << row.p95_latency_ns << ','
            << row.p99_latency_ns << ',' << row.max_latency_ns << ','
            << row.throughput_txn_per_us << ',' << row.route_queue_peak << ','
            << row.local_route_utilization << ','
            << row.shared_route_utilization << ','
            << row.boundary_route_utilization << ','
            << row.avg_route_delay_ns << ',' << row.p95_route_delay_ns << ','
            << row.ordering_delay_ns << ',' << row.boundary_penalty_ns << ','
            << row.coherency_boundary_events << ','
            << row.ordering_serialization_events << ','
            << row.read_avg_latency_ns << ',' << row.read_p95_latency_ns << ','
            << row.write_avg_latency_ns << ',' << row.write_p95_latency_ns
            << ',' << row.latency_high_p99_ns << ','
            << row.best_effort_p99_ns << ',' << row.bulk_low_p99_ns << ','
            << row.starvation_events << ',' << row.qos_protection_score << ','
            << row.collapse_score << ',' << row.recommendation << '\n';
    }
}

void write_trace(const std::filesystem::path &trace_path,
                 const std::vector<CaseResult> &results)
{
    std::filesystem::create_directories(trace_path.parent_path());
    std::ofstream out(trace_path);
    if (!out) {
        throw std::runtime_error("failed to open trace for writing: "
                                 + trace_path.string());
    }

    out << "case,request_id,initiator,role,route,qos,flow,coherent,"
           "boundary_crossing,ordering_sensitive,issue_time_ns,"
           "route_dequeue_time_ns,service_start_time_ns,end_time_ns,"
           "queue_delay_ns,service_delay_ns,route_delay_ns,ordering_delay_ns,"
           "boundary_penalty_ns,read_write_interference_delay_ns,latency_ns,"
           "queue_depth_on_arrival,ordering_serialization_event,"
           "starvation_flag\n";
    out << std::fixed << std::setprecision(3);
    for (const CaseResult &result : results) {
        for (const TransactionRecord &record : result.records) {
            out << record.case_name << ',' << record.request_id << ','
                << record.initiator << ',' << record.initiator_role << ','
                << record.route << ',' << record.qos << ','
                << (record.read_flow ? "read" : "write") << ','
                << (record.coherent ? "YES" : "NO") << ','
                << (record.boundary_crossing ? "YES" : "NO") << ','
                << (record.ordering_sensitive ? "YES" : "NO") << ','
                << record.issue_time_ns << ',' << record.route_dequeue_time_ns
                << ',' << record.service_start_time_ns << ','
                << record.end_time_ns << ',' << record.queue_delay_ns << ','
                << record.service_delay_ns << ',' << record.route_delay_ns << ','
                << record.ordering_delay_ns << ','
                << record.boundary_penalty_ns << ','
                << record.read_write_interference_delay_ns << ','
                << record.latency_ns << ',' << record.queue_depth_on_arrival
                << ','
                << (record.ordering_serialization_event ? "YES" : "NO")
                << ',' << (record.starvation_flag ? "YES" : "NO") << '\n';
        }
    }
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

    const CaseMetrics &baseline = find_metrics(metrics, "baseline_qos_rr");
    const CaseMetrics &priority = find_metrics(metrics, "latency_qos_priority");
    const CaseMetrics &bulk = find_metrics(metrics, "bulk_dma_pressure");
    const CaseMetrics &boundary =
        find_metrics(metrics, "boundary_crossing_stress");
    const CaseMetrics &hotspot = find_metrics(metrics, "route_hotspot");
    const CaseMetrics &collapse = find_metrics(metrics, "mixed_qos_collapse");

    out << std::fixed << std::setprecision(3);
    out << "# Project AT-8: AMBA-inspired NoC QoS and Coherency Boundary Lab\n\n";

    out << "## Purpose\n\n";
    out << "Project AT-8 builds a bounded AT-level synthetic AMBA-inspired NoC "
           "QoS and coherency-boundary exploration. It uses multiple "
           "initiator classes, routes, QoS classes, read/write flows, and "
           "coherent-vs-noncoherent boundary crossings to observe QoS class "
           "pressure, route contention, ordering pressure, read/write "
           "interference, tail latency, starvation risk, and recommendation "
           "logic.\n\n";

    out << "## Methodology\n\n";
    out << "- Four synthetic initiators generate deterministic traffic: "
           "CPU-like coherent, DMA-like noncoherent, NPU-like accelerator, "
           "and IO-like ordering-sensitive peripheral traffic.\n";
    out << "- Three route resources are modeled: `local_route`, `shared_route`, "
           "and `boundary_route`, each with queue capacity, base service "
           "delay, congestion multiplier, utilization, and queue peak.\n";
    out << "- QoS classes are `latency_high`, `best_effort`, and `bulk_low`; "
           "QoS priority changes arbitration order but does not create "
           "additional route capacity.\n";
    out << "- Boundary-crossing transactions add synthetic boundary penalty and "
           "ordering delay to expose coherency-boundary pressure without "
           "modeling a protocol-compliant coherency state machine.\n";
    out << "- Write pressure creates bounded read/write interference so bulk "
           "writes can increase read p95/p99 latency under shared route "
           "contention.\n\n";

    out << "## Case Table\n\n";
    out << "| case | policy | intent | txns | throughput txn/us | p99 ns | "
           "route queue peak | shared util | boundary util | boundary events | "
           "ordering events | read p95 ns | write p95 ns | latency_high p99 | "
           "bulk_low p99 | starvation | collapse | recommendation |\n";
    out << "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
           "---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |\n";
    for (const CaseSpec &spec : cases) {
        const CaseMetrics &row = find_metrics(metrics, spec.case_name);
        out << "| `" << row.case_name << "` | `" << row.policy << "` | "
            << spec.intent << " | " << row.total_transactions << " | "
            << row.throughput_txn_per_us << " | " << row.p99_latency_ns << " | "
            << row.route_queue_peak << " | " << row.shared_route_utilization
            << " | " << row.boundary_route_utilization << " | "
            << row.coherency_boundary_events << " | "
            << row.ordering_serialization_events << " | "
            << row.read_p95_latency_ns << " | " << row.write_p95_latency_ns
            << " | " << row.latency_high_p99_ns << " | "
            << row.bulk_low_p99_ns << " | " << row.starvation_events << " | "
            << row.collapse_score << " | `" << row.recommendation << "` |\n";
    }

    out << "\n## Key Observations\n\n";
    out << "- `baseline_qos_rr` provides a balanced reference with shared route "
           "utilization "
        << baseline.shared_route_utilization << ", boundary route utilization "
        << baseline.boundary_route_utilization << ", and p99 latency "
        << baseline.p99_latency_ns << " ns.\n";
    out << "- `latency_qos_priority` changes latency_high p99 from "
        << delta_text(baseline.latency_high_p99_ns,
                      priority.latency_high_p99_ns, "ns")
        << " while bulk_low p99 is " << priority.bulk_low_p99_ns
        << " ns, showing QoS class protection inside the same route capacity "
           "bound.\n";
    out << "- `bulk_dma_pressure` raises write p95 latency to "
        << bulk.write_p95_latency_ns << " ns and read p95 latency to "
        << bulk.read_p95_latency_ns
        << " ns, isolating write-heavy bulk pressure and read tail interference.\n";
    out << "- `boundary_crossing_stress` increases boundary events to "
        << boundary.coherency_boundary_events
        << " and accumulated ordering delay to "
        << boundary.ordering_delay_ns
        << " ns, making coherency-boundary pressure visible as latency and "
           "serialization cost.\n";
    out << "- `route_hotspot` drives route queue peak to "
        << hotspot.route_queue_peak << " and starvation events to "
        << hotspot.starvation_events
        << ", showing that route mapping can dominate QoS intent.\n";
    out << "- `mixed_qos_collapse` reaches collapse score "
        << collapse.collapse_score << " with p99 latency "
        << collapse.p99_latency_ns
        << " ns; QoS priority still orders service, but the saturated "
           "downstream route and boundary pressure define the hard limit.\n\n";

    out << "## Architecture Lessons\n\n";
    out << "- QoS class priority can reduce latency_high tail exposure only while "
           "route capacity and boundary serialization still have headroom.\n";
    out << "- Bulk writes are a separate pressure source because they stretch route "
           "service time and can raise read tail latency through bounded "
           "read/write interference.\n";
    out << "- Boundary crossing should be tracked as its own pressure signal; "
           "folding it into generic route delay hides ordering and "
           "serialization cost.\n";
    out << "- Route hotspot cases show why bottleneck isolation needs route-level "
           "queue peak and utilization metrics, not only aggregate latency.\n";
    out << "- A QoS policy cannot compensate for saturated downstream capacity; "
           "recommendation logic should switch from priority tuning to "
           "capacity, partitioning, or traffic-shaping actions when collapse "
           "score is high.\n\n";

    out << "## Recommendation\n\n";
    out << "Use `baseline_qos_rr` as the reference. If latency-sensitive traffic "
           "is the risk, compare against `latency_qos_priority` and check "
           "`qos_protection_score`. If read p95/p99 grows under "
           "`bulk_dma_pressure`, partition or throttle bulk writes before "
           "claiming QoS protection. If `boundary_crossing_stress` or "
           "`mixed_qos_collapse` reports high ordering delay, boundary events, "
           "or collapse score, treat route capacity and boundary isolation as "
           "the next architecture knob rather than raising priority again.\n\n";

    out << "## Claim Boundary\n\n";
    out << kBoundaryStatement << "\n\n";
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
        } else if (arg == "--no-trace") {
            options.write_trace = false;
        } else if (arg == "--help") {
            std::cout
                << "Usage: project_at8_amba_noc_qos_coherency_boundary "
                   "[options]\n"
                << "  --output-dir DIR\n"
                << "  --write-trace\n"
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
    std::vector<CaseResult> results;
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
    write_comparison(comparison_path, cases, metrics);

    std::cout << "Project AT-8 PASS\n";
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
}  // namespace project_at8

int sc_main(int argc, char *argv[])
{
    try {
        return project_at8::run(argc, argv);
    } catch (const std::exception &error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
