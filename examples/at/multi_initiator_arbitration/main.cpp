// SPDX-License-Identifier: Apache-2.0

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <deque>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "systemc"
#include "tlm.h"
#include "tlm_utils/simple_initiator_socket.h"
#include "tlm_utils/simple_target_socket.h"

namespace project_at2 {
namespace {

constexpr std::size_t kInitiatorCount = 3;
constexpr double kTargetAcceptLatencyNs = 1.0;
constexpr double kEndRespDelayNs = 1.0;

double now_ns()
{
    return sc_core::sc_time_stamp().to_seconds() * 1e9;
}

sc_core::sc_time ns(double value)
{
    return sc_core::sc_time(value, sc_core::SC_NS);
}

std::string command_name(tlm::tlm_command command)
{
    switch (command) {
    case tlm::TLM_READ_COMMAND:
        return "READ";
    case tlm::TLM_WRITE_COMMAND:
        return "WRITE";
    case tlm::TLM_IGNORE_COMMAND:
        return "IGNORE";
    }

    return "UNKNOWN";
}

std::string hex_value(std::uint64_t value)
{
    std::ostringstream out;
    out << "0x" << std::hex << std::nouppercase << std::setw(16)
        << std::setfill('0') << value;
    return out.str();
}

}  // namespace

enum class ArbitrationPolicy {
    RoundRobin,
    FixedPriority,
    WeightedPriority,
};

struct Options {
    std::string case_name = "default";
    ArbitrationPolicy policy = ArbitrationPolicy::RoundRobin;
    std::string policy_name = "round_robin";
    std::filesystem::path output_dir =
        "examples/at/results/project_at2_multi_initiator_arbitration/model_runs/default";
    std::size_t num_transactions_per_initiator = 16;
    std::size_t queue_depth = 2;
    double service_latency_ns = 10.0;
    std::array<double, kInitiatorCount> issue_gap_ns = {4.0, 4.0, 4.0};
};

struct InitiatorSpec {
    std::size_t index;
    const char *name;
};

constexpr std::array<InitiatorSpec, kInitiatorCount> kInitiators = {{
    {0, "cpu0"},
    {1, "dma0"},
    {2, "accel0"},
}};

struct TransactionRecord {
    std::string case_name;
    std::string policy;
    std::size_t txn_id = 0;
    std::size_t initiator_id = 0;
    std::string initiator_name;
    std::uint64_t addr = 0;
    unsigned int size_bytes = 4;
    tlm::tlm_command cmd = tlm::TLM_READ_COMMAND;
    double begin_req_ns = std::numeric_limits<double>::quiet_NaN();
    double arbiter_accept_ns = std::numeric_limits<double>::quiet_NaN();
    double target_begin_req_ns = std::numeric_limits<double>::quiet_NaN();
    double target_end_req_ns = std::numeric_limits<double>::quiet_NaN();
    double begin_resp_ns = std::numeric_limits<double>::quiet_NaN();
    double end_resp_ns = std::numeric_limits<double>::quiet_NaN();
    unsigned int initiator_queue_depth_on_accept = 0;
    unsigned int total_pending_on_accept = 0;
    bool backpressure = false;
    unsigned int winner_order = 0;
    std::string status = "PENDING";
};

class TxnExtension : public tlm::tlm_extension<TxnExtension> {
public:
    TxnExtension(std::size_t record_index = 0, std::size_t initiator_index = 0)
        : record_index(record_index)
        , initiator_index(initiator_index)
    {
    }

    tlm::tlm_extension_base *clone() const override
    {
        return new TxnExtension(record_index, initiator_index);
    }

    void copy_from(const tlm::tlm_extension_base &extension) override
    {
        const auto &typed = static_cast<const TxnExtension &>(extension);
        record_index = typed.record_index;
        initiator_index = typed.initiator_index;
    }

    std::size_t record_index;
    std::size_t initiator_index;
};

TxnExtension &extension_from(tlm::tlm_generic_payload &trans)
{
    TxnExtension *extension = nullptr;
    trans.get_extension(extension);

    if (extension == nullptr) {
        SC_REPORT_FATAL("project_at2", "transaction is missing TxnExtension");
    }

    return *extension;
}

std::uint64_t address_for(std::size_t initiator_index, std::size_t txn_index)
{
    const std::uint64_t base = 0x10000000ULL + initiator_index * 0x00010000ULL;
    const std::uint64_t line = (txn_index % 8) * 64ULL;
    const std::uint64_t stride = (txn_index / 8) * 4ULL;
    return base + line + stride;
}

std::vector<TransactionRecord> make_records(const Options &options)
{
    std::vector<TransactionRecord> records;
    records.reserve(kInitiatorCount * options.num_transactions_per_initiator);

    for (const InitiatorSpec &initiator : kInitiators) {
        for (std::size_t index = 0; index < options.num_transactions_per_initiator;
             ++index) {
            TransactionRecord record;
            record.case_name = options.case_name;
            record.policy = options.policy_name;
            record.txn_id = (initiator.index + 1) * 100000 + index + 1;
            record.initiator_id = initiator.index;
            record.initiator_name = initiator.name;
            record.addr = address_for(initiator.index, index);
            record.cmd = index % 3 == 2 ? tlm::TLM_WRITE_COMMAND
                                         : tlm::TLM_READ_COMMAND;
            records.push_back(record);
        }
    }

    return records;
}

TransactionRecord &record_for(tlm::tlm_generic_payload &trans,
                              std::vector<TransactionRecord> &records)
{
    TxnExtension &extension = extension_from(trans);
    return records.at(extension.record_index);
}

class Initiator : public sc_core::sc_module {
public:
    tlm_utils::simple_initiator_socket<Initiator> socket;

    Initiator(sc_core::sc_module_name name, const Options &options,
              std::size_t initiator_index,
              std::vector<TransactionRecord> &records)
        : sc_core::sc_module(name)
        , socket("socket")
        , options_(options)
        , initiator_index_(initiator_index)
        , records_(records)
        , issued_all_(false)
        , done_(false)
        , completed_responses_(0)
    {
        socket.register_nb_transport_bw(this, &Initiator::nb_transport_bw);
        prepare_payloads();
        SC_THREAD(issue_requests);
        SC_THREAD(send_end_responses);
    }

    bool done() const
    {
        return done_;
    }

    const sc_core::sc_event &done_event() const
    {
        return done_event_;
    }

private:
    struct OwnedTransaction {
        OwnedTransaction(std::size_t record_index, std::size_t initiator_index)
            : extension(record_index, initiator_index)
        {
            data.fill(0);
            payload.set_data_ptr(data.data());
            payload.set_data_length(data.size());
            payload.set_streaming_width(data.size());
            payload.set_byte_enable_ptr(nullptr);
            payload.set_byte_enable_length(0);
            payload.set_dmi_allowed(false);
            payload.set_response_status(tlm::TLM_INCOMPLETE_RESPONSE);
            payload.set_extension(&extension);
        }

        ~OwnedTransaction()
        {
            payload.clear_extension<TxnExtension>();
        }

        tlm::tlm_generic_payload payload;
        TxnExtension extension;
        std::array<unsigned char, 4> data;
    };

    void prepare_payloads()
    {
        for (std::size_t index = 0; index < records_.size(); ++index) {
            if (records_[index].initiator_id != initiator_index_) {
                continue;
            }

            auto owned = std::make_unique<OwnedTransaction>(index, initiator_index_);
            owned->payload.set_command(records_[index].cmd);
            owned->payload.set_address(records_[index].addr);
            payloads_.push_back(std::move(owned));
        }
    }

    void issue_requests()
    {
        wait(sc_core::SC_ZERO_TIME);

        for (std::unique_ptr<OwnedTransaction> &owned : payloads_) {
            tlm::tlm_generic_payload &payload = owned->payload;
            TransactionRecord &record = record_for(payload, records_);
            record.begin_req_ns = now_ns();
            record.status = "IN_FLIGHT";

            tlm::tlm_phase phase = tlm::BEGIN_REQ;
            sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
            const tlm::tlm_sync_enum status =
                socket->nb_transport_fw(payload, phase, delay);

            if (status == tlm::TLM_COMPLETED) {
                SC_REPORT_FATAL("project_at2", "interconnect completed BEGIN_REQ");
            }

            wait(ns(options_.issue_gap_ns[initiator_index_]));
        }

        issued_all_ = true;
        maybe_mark_done();
    }

    tlm::tlm_sync_enum nb_transport_bw(tlm::tlm_generic_payload &trans,
                                       tlm::tlm_phase &phase,
                                       sc_core::sc_time &delay)
    {
        if (delay != sc_core::SC_ZERO_TIME) {
            wait(delay);
        }

        TransactionRecord &record = record_for(trans, records_);

        if (phase == tlm::END_REQ) {
            return tlm::TLM_ACCEPTED;
        }

        if (phase == tlm::BEGIN_RESP) {
            record.begin_resp_ns = now_ns();
            response_queue_.push_back(&trans);
            response_event_.notify(sc_core::SC_ZERO_TIME);
            return tlm::TLM_ACCEPTED;
        }

        SC_REPORT_FATAL("project_at2", "initiator received unexpected backward phase");
        return tlm::TLM_ACCEPTED;
    }

    void send_end_responses()
    {
        while (true) {
            if (response_queue_.empty()) {
                wait(response_event_);
            }

            while (!response_queue_.empty()) {
                tlm::tlm_generic_payload *trans = response_queue_.front();
                response_queue_.pop_front();

                wait(ns(kEndRespDelayNs));

                TransactionRecord &record = record_for(*trans, records_);
                tlm::tlm_phase phase = tlm::END_RESP;
                sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
                record.end_resp_ns = now_ns();
                socket->nb_transport_fw(*trans, phase, delay);

                record.status = trans->is_response_error() ? trans->get_response_string()
                                                           : "OK";
                ++completed_responses_;
                maybe_mark_done();
            }
        }
    }

    void maybe_mark_done()
    {
        if (!done_ && issued_all_ && completed_responses_ == payloads_.size()) {
            done_ = true;
            done_event_.notify(sc_core::SC_ZERO_TIME);
        }
    }

    const Options &options_;
    std::size_t initiator_index_;
    std::vector<TransactionRecord> &records_;
    std::vector<std::unique_ptr<OwnedTransaction>> payloads_;
    std::deque<tlm::tlm_generic_payload *> response_queue_;
    sc_core::sc_event response_event_;
    sc_core::sc_event done_event_;
    bool issued_all_;
    bool done_;
    std::size_t completed_responses_;

    SC_HAS_PROCESS(Initiator);
};

class SimpleAtInterconnect : public sc_core::sc_module {
public:
    tlm_utils::simple_target_socket<SimpleAtInterconnect> cpu0_socket;
    tlm_utils::simple_target_socket<SimpleAtInterconnect> dma0_socket;
    tlm_utils::simple_target_socket<SimpleAtInterconnect> accel0_socket;
    tlm_utils::simple_initiator_socket<SimpleAtInterconnect> downstream_socket;

    SimpleAtInterconnect(sc_core::sc_module_name name, const Options &options,
                         std::vector<TransactionRecord> &records)
        : sc_core::sc_module(name)
        , cpu0_socket("cpu0_socket")
        , dma0_socket("dma0_socket")
        , accel0_socket("accel0_socket")
        , downstream_socket("downstream_socket")
        , options_(options)
        , records_(records)
        , downstream_pending_(false)
        , last_rr_index_(kInitiatorCount - 1)
        , weighted_cursor_(0)
        , winner_order_(0)
    {
        cpu0_socket.register_nb_transport_fw(
            this, &SimpleAtInterconnect::nb_transport_fw_cpu0);
        dma0_socket.register_nb_transport_fw(
            this, &SimpleAtInterconnect::nb_transport_fw_dma0);
        accel0_socket.register_nb_transport_fw(
            this, &SimpleAtInterconnect::nb_transport_fw_accel0);
        downstream_socket.register_nb_transport_bw(
            this, &SimpleAtInterconnect::nb_transport_bw);
        SC_THREAD(arbitrate_requests);
    }

private:
    struct PendingRequest {
        tlm::tlm_generic_payload *trans;
    };

    tlm::tlm_sync_enum nb_transport_fw_cpu0(tlm::tlm_generic_payload &trans,
                                            tlm::tlm_phase &phase,
                                            sc_core::sc_time &delay)
    {
        return nb_transport_fw_from(0, trans, phase, delay);
    }

    tlm::tlm_sync_enum nb_transport_fw_dma0(tlm::tlm_generic_payload &trans,
                                            tlm::tlm_phase &phase,
                                            sc_core::sc_time &delay)
    {
        return nb_transport_fw_from(1, trans, phase, delay);
    }

    tlm::tlm_sync_enum nb_transport_fw_accel0(tlm::tlm_generic_payload &trans,
                                              tlm::tlm_phase &phase,
                                              sc_core::sc_time &delay)
    {
        return nb_transport_fw_from(2, trans, phase, delay);
    }

    tlm::tlm_sync_enum nb_transport_fw_from(std::size_t initiator_index,
                                            tlm::tlm_generic_payload &trans,
                                            tlm::tlm_phase &phase,
                                            sc_core::sc_time &delay)
    {
        if (delay != sc_core::SC_ZERO_TIME) {
            wait(delay);
        }

        if (phase == tlm::BEGIN_REQ) {
            TxnExtension &extension = extension_from(trans);
            if (extension.initiator_index != initiator_index) {
                SC_REPORT_FATAL("project_at2", "initiator socket mismatch");
            }
            pending_[initiator_index].push_back(PendingRequest{&trans});
            arbiter_event_.notify(sc_core::SC_ZERO_TIME);
            return tlm::TLM_ACCEPTED;
        }

        if (phase == tlm::END_RESP) {
            return downstream_socket->nb_transport_fw(trans, phase, delay);
        }

        SC_REPORT_FATAL("project_at2", "interconnect received unexpected phase");
        return tlm::TLM_ACCEPTED;
    }

    tlm::tlm_sync_enum nb_transport_bw(tlm::tlm_generic_payload &trans,
                                       tlm::tlm_phase &phase,
                                       sc_core::sc_time &delay)
    {
        if (delay != sc_core::SC_ZERO_TIME) {
            wait(delay);
        }

        if (phase == tlm::END_REQ) {
            downstream_pending_ = false;
            send_bw_to_initiator(trans, phase, delay);
            arbiter_event_.notify(sc_core::SC_ZERO_TIME);
            return tlm::TLM_ACCEPTED;
        }

        if (phase == tlm::BEGIN_RESP) {
            send_bw_to_initiator(trans, phase, delay);
            return tlm::TLM_ACCEPTED;
        }

        SC_REPORT_FATAL("project_at2", "interconnect received unexpected backward phase");
        return tlm::TLM_ACCEPTED;
    }

    void send_bw_to_initiator(tlm::tlm_generic_payload &trans, tlm::tlm_phase &phase,
                              sc_core::sc_time &delay)
    {
        TxnExtension &extension = extension_from(trans);
        switch (extension.initiator_index) {
        case 0:
            cpu0_socket->nb_transport_bw(trans, phase, delay);
            return;
        case 1:
            dma0_socket->nb_transport_bw(trans, phase, delay);
            return;
        case 2:
            accel0_socket->nb_transport_bw(trans, phase, delay);
            return;
        default:
            SC_REPORT_FATAL("project_at2", "unknown initiator index");
        }
    }

    bool has_pending() const
    {
        return std::any_of(pending_.begin(), pending_.end(),
                           [](const auto &queue) { return !queue.empty(); });
    }

    unsigned int total_pending() const
    {
        unsigned int total = 0;
        for (const auto &queue : pending_) {
            total += static_cast<unsigned int>(queue.size());
        }
        return total;
    }

    std::size_t choose_next_initiator()
    {
        if (options_.policy == ArbitrationPolicy::RoundRobin) {
            for (std::size_t offset = 1; offset <= kInitiatorCount; ++offset) {
                const std::size_t index = (last_rr_index_ + offset) % kInitiatorCount;
                if (!pending_[index].empty()) {
                    last_rr_index_ = index;
                    return index;
                }
            }
        }

        if (options_.policy == ArbitrationPolicy::FixedPriority) {
            for (std::size_t index : {1U, 0U, 2U}) {
                if (!pending_[index].empty()) {
                    return index;
                }
            }
        }

        const std::array<std::size_t, 5> weighted_order = {2, 2, 2, 0, 1};
        for (std::size_t count = 0; count < weighted_order.size(); ++count) {
            const std::size_t index = weighted_order[weighted_cursor_];
            weighted_cursor_ = (weighted_cursor_ + 1) % weighted_order.size();
            if (!pending_[index].empty()) {
                return index;
            }
        }

        SC_REPORT_FATAL("project_at2", "arbitration called with no pending request");
        return 0;
    }

    void arbitrate_requests()
    {
        while (true) {
            if (downstream_pending_ || !has_pending()) {
                wait(arbiter_event_);
            }

            while (!downstream_pending_ && has_pending()) {
                const std::size_t winner = choose_next_initiator();
                const unsigned int winner_depth =
                    static_cast<unsigned int>(pending_[winner].size());
                const unsigned int total_depth = total_pending();
                PendingRequest request = pending_[winner].front();
                pending_[winner].pop_front();

                TransactionRecord &record = record_for(*request.trans, records_);
                record.arbiter_accept_ns = now_ns();
                record.initiator_queue_depth_on_accept = winner_depth;
                record.total_pending_on_accept = total_depth;
                record.winner_order = ++winner_order_;

                tlm::tlm_phase phase = tlm::BEGIN_REQ;
                sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
                downstream_pending_ = true;
                const tlm::tlm_sync_enum status =
                    downstream_socket->nb_transport_fw(*request.trans, phase, delay);
                if (status == tlm::TLM_COMPLETED) {
                    SC_REPORT_FATAL("project_at2", "target completed BEGIN_REQ");
                }
            }
        }
    }

    const Options &options_;
    std::vector<TransactionRecord> &records_;
    std::array<std::deque<PendingRequest>, kInitiatorCount> pending_;
    sc_core::sc_event arbiter_event_;
    bool downstream_pending_;
    std::size_t last_rr_index_;
    std::size_t weighted_cursor_;
    unsigned int winner_order_;

    SC_HAS_PROCESS(SimpleAtInterconnect);
};

class MemoryTarget : public sc_core::sc_module {
public:
    tlm_utils::simple_target_socket<MemoryTarget> socket;

    MemoryTarget(sc_core::sc_module_name name, const Options &options,
                 std::vector<TransactionRecord> &records)
        : sc_core::sc_module(name)
        , socket("socket")
        , options_(options)
        , records_(records)
        , occupied_slots_(0)
    {
        socket.register_nb_transport_fw(this, &MemoryTarget::nb_transport_fw);
        SC_THREAD(send_end_requests);
        SC_THREAD(service_requests);
    }

private:
    tlm::tlm_sync_enum nb_transport_fw(tlm::tlm_generic_payload &trans,
                                       tlm::tlm_phase &phase,
                                       sc_core::sc_time &delay)
    {
        if (delay != sc_core::SC_ZERO_TIME) {
            wait(delay);
        }

        if (phase == tlm::BEGIN_REQ) {
            TransactionRecord &record = record_for(trans, records_);
            record.target_begin_req_ns = now_ns();

            if (occupied_slots_ < options_.queue_depth) {
                accept_request(trans);
            } else {
                record.backpressure = true;
                waiting_accept_queue_.push_back(&trans);
            }
            return tlm::TLM_ACCEPTED;
        }

        if (phase == tlm::END_RESP) {
            return tlm::TLM_ACCEPTED;
        }

        SC_REPORT_FATAL("project_at2", "target received unexpected forward phase");
        return tlm::TLM_ACCEPTED;
    }

    void accept_request(tlm::tlm_generic_payload &trans)
    {
        ++occupied_slots_;
        end_req_queue_.push_back(&trans);
        end_req_event_.notify(sc_core::SC_ZERO_TIME);
    }

    void try_accept_waiting_request()
    {
        if (waiting_accept_queue_.empty() || occupied_slots_ >= options_.queue_depth) {
            return;
        }

        tlm::tlm_generic_payload *trans = waiting_accept_queue_.front();
        waiting_accept_queue_.pop_front();
        record_for(*trans, records_).backpressure = true;
        accept_request(*trans);
    }

    void send_end_requests()
    {
        while (true) {
            if (end_req_queue_.empty()) {
                wait(end_req_event_);
            }

            while (!end_req_queue_.empty()) {
                tlm::tlm_generic_payload *trans = end_req_queue_.front();
                end_req_queue_.pop_front();

                wait(ns(kTargetAcceptLatencyNs));

                TransactionRecord &record = record_for(*trans, records_);
                record.target_end_req_ns = now_ns();

                tlm::tlm_phase phase = tlm::END_REQ;
                sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
                socket->nb_transport_bw(*trans, phase, delay);

                service_queue_.push_back(trans);
                service_event_.notify(sc_core::SC_ZERO_TIME);
            }
        }
    }

    void service_requests()
    {
        while (true) {
            if (service_queue_.empty()) {
                wait(service_event_);
            }

            while (!service_queue_.empty()) {
                tlm::tlm_generic_payload *trans = service_queue_.front();
                service_queue_.pop_front();

                wait(ns(options_.service_latency_ns));

                trans->set_response_status(tlm::TLM_OK_RESPONSE);
                TransactionRecord &record = record_for(*trans, records_);
                record.begin_resp_ns = now_ns();

                tlm::tlm_phase phase = tlm::BEGIN_RESP;
                sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
                socket->nb_transport_bw(*trans, phase, delay);

                if (occupied_slots_ == 0) {
                    SC_REPORT_FATAL("project_at2", "target occupancy underflow");
                }
                --occupied_slots_;
                try_accept_waiting_request();
            }
        }
    }

    const Options &options_;
    std::vector<TransactionRecord> &records_;
    std::deque<tlm::tlm_generic_payload *> waiting_accept_queue_;
    std::deque<tlm::tlm_generic_payload *> end_req_queue_;
    std::deque<tlm::tlm_generic_payload *> service_queue_;
    sc_core::sc_event end_req_event_;
    sc_core::sc_event service_event_;
    std::size_t occupied_slots_;

    SC_HAS_PROCESS(MemoryTarget);
};

class Top : public sc_core::sc_module {
public:
    Top(sc_core::sc_module_name name, const Options &options,
        std::vector<TransactionRecord> &records)
        : sc_core::sc_module(name)
        , cpu0_("cpu0", options, 0, records)
        , dma0_("dma0", options, 1, records)
        , accel0_("accel0", options, 2, records)
        , interconnect_("interconnect", options, records)
        , memory_("memory", options, records)
    {
        cpu0_.socket.bind(interconnect_.cpu0_socket);
        dma0_.socket.bind(interconnect_.dma0_socket);
        accel0_.socket.bind(interconnect_.accel0_socket);
        interconnect_.downstream_socket.bind(memory_.socket);
        SC_THREAD(stop_when_done);
    }

private:
    void stop_when_done()
    {
        while (!cpu0_.done()) {
            wait(cpu0_.done_event());
        }
        while (!dma0_.done()) {
            wait(dma0_.done_event());
        }
        while (!accel0_.done()) {
            wait(accel0_.done_event());
        }
        sc_core::sc_stop();
    }

    Initiator cpu0_;
    Initiator dma0_;
    Initiator accel0_;
    SimpleAtInterconnect interconnect_;
    MemoryTarget memory_;

    SC_HAS_PROCESS(Top);
};

std::string required_value(int argc, char **argv, int &index, const std::string &option)
{
    if (index + 1 >= argc) {
        throw std::runtime_error(option + " requires a value");
    }

    ++index;
    return argv[index];
}

std::size_t parse_size(const std::string &value, const std::string &option)
{
    try {
        return static_cast<std::size_t>(std::stoull(value));
    } catch (const std::exception &) {
        throw std::runtime_error("invalid " + option + ": " + value);
    }
}

double parse_double(const std::string &value, const std::string &option)
{
    try {
        return std::stod(value);
    } catch (const std::exception &) {
        throw std::runtime_error("invalid " + option + ": " + value);
    }
}

ArbitrationPolicy parse_policy(const std::string &value)
{
    if (value == "round_robin") {
        return ArbitrationPolicy::RoundRobin;
    }
    if (value == "fixed_priority") {
        return ArbitrationPolicy::FixedPriority;
    }
    if (value == "weighted_priority") {
        return ArbitrationPolicy::WeightedPriority;
    }
    throw std::runtime_error("--policy must be round_robin, fixed_priority, or weighted_priority");
}

void print_help(const char *program)
{
    std::cout
        << "Usage: " << program << " [options]\n"
        << "\n"
        << "Options:\n"
        << "  --policy <round_robin|fixed_priority|weighted_priority>\n"
        << "  --num-transactions-per-initiator <count>\n"
        << "  --queue-depth <count>\n"
        << "  --service-latency-ns <ns>\n"
        << "  --issue-gap-cpu-ns <ns>\n"
        << "  --issue-gap-dma-ns <ns>\n"
        << "  --issue-gap-accel-ns <ns>\n"
        << "  --output-dir <dir>\n"
        << "  --case-name <name>\n"
        << "  --help\n";
}

Options parse_options(int argc, char **argv)
{
    Options options;

    for (int index = 1; index < argc; ++index) {
        const std::string arg = argv[index];
        if (arg == "--help") {
            print_help(argv[0]);
            std::exit(0);
        } else if (arg == "--policy") {
            options.policy_name = required_value(argc, argv, index, arg);
            options.policy = parse_policy(options.policy_name);
        } else if (arg == "--num-transactions-per-initiator") {
            options.num_transactions_per_initiator =
                parse_size(required_value(argc, argv, index, arg), arg);
        } else if (arg == "--queue-depth") {
            options.queue_depth =
                parse_size(required_value(argc, argv, index, arg), arg);
        } else if (arg == "--service-latency-ns") {
            options.service_latency_ns =
                parse_double(required_value(argc, argv, index, arg), arg);
        } else if (arg == "--issue-gap-cpu-ns") {
            options.issue_gap_ns[0] =
                parse_double(required_value(argc, argv, index, arg), arg);
        } else if (arg == "--issue-gap-dma-ns") {
            options.issue_gap_ns[1] =
                parse_double(required_value(argc, argv, index, arg), arg);
        } else if (arg == "--issue-gap-accel-ns") {
            options.issue_gap_ns[2] =
                parse_double(required_value(argc, argv, index, arg), arg);
        } else if (arg == "--output-dir") {
            options.output_dir = required_value(argc, argv, index, arg);
        } else if (arg == "--case-name") {
            options.case_name = required_value(argc, argv, index, arg);
        } else {
            throw std::runtime_error("unknown option: " + arg);
        }
    }

    if (options.num_transactions_per_initiator == 0) {
        throw std::runtime_error("--num-transactions-per-initiator must be greater than 0");
    }
    if (options.queue_depth == 0) {
        throw std::runtime_error("--queue-depth must be greater than 0");
    }
    if (options.service_latency_ns < 0.0) {
        throw std::runtime_error("--service-latency-ns must be non-negative");
    }
    for (double gap : options.issue_gap_ns) {
        if (gap < 0.0) {
            throw std::runtime_error("issue gaps must be non-negative");
        }
    }

    return options;
}

double delta(double end, double start)
{
    return end - start;
}

void write_trace(const std::filesystem::path &path,
                 const std::vector<TransactionRecord> &records)
{
    std::filesystem::create_directories(path.parent_path());

    std::ofstream out(path);
    if (!out) {
        throw std::runtime_error("failed to open trace CSV: " + path.string());
    }

    out << "case_name,policy,txn_id,initiator_id,initiator_name,addr,size_bytes,cmd,"
        << "begin_req_ns,arbiter_accept_ns,target_begin_req_ns,target_end_req_ns,"
        << "begin_resp_ns,end_resp_ns,arbitration_delay_ns,"
        << "request_accept_latency_ns,target_service_latency_ns,response_latency_ns,"
        << "initiator_blocked_ns,initiator_queue_depth_on_accept,total_pending_on_accept,"
        << "backpressure,winner_order,status\n";

    out << std::fixed << std::setprecision(3);
    for (const TransactionRecord &record : records) {
        const double arbitration_delay_ns =
            delta(record.arbiter_accept_ns, record.begin_req_ns);
        const double request_accept_latency_ns =
            delta(record.target_end_req_ns, record.begin_req_ns);
        const double target_service_latency_ns =
            delta(record.begin_resp_ns, record.target_end_req_ns);
        const double response_latency_ns =
            delta(record.end_resp_ns, record.begin_req_ns);
        const double initiator_blocked_ns =
            std::max(0.0, request_accept_latency_ns - kTargetAcceptLatencyNs);

        out << record.case_name << ','
            << record.policy << ','
            << record.txn_id << ','
            << record.initiator_id << ','
            << record.initiator_name << ','
            << hex_value(record.addr) << ','
            << record.size_bytes << ','
            << command_name(record.cmd) << ','
            << record.begin_req_ns << ','
            << record.arbiter_accept_ns << ','
            << record.target_begin_req_ns << ','
            << record.target_end_req_ns << ','
            << record.begin_resp_ns << ','
            << record.end_resp_ns << ','
            << arbitration_delay_ns << ','
            << request_accept_latency_ns << ','
            << target_service_latency_ns << ','
            << response_latency_ns << ','
            << initiator_blocked_ns << ','
            << record.initiator_queue_depth_on_accept << ','
            << record.total_pending_on_accept << ','
            << (record.backpressure ? "YES" : "NO") << ','
            << record.winner_order << ','
            << record.status << '\n';
    }
}

int run(int argc, char **argv)
{
    Options options = parse_options(argc, argv);
    std::vector<TransactionRecord> records = make_records(options);

    Top top("top", options, records);
    sc_core::sc_start();

    const std::filesystem::path trace_path = options.output_dir / "trace.csv";
    write_trace(trace_path, records);

    std::cout << "project_at2_trace=" << trace_path.string() << '\n';
    std::cout << "transactions=" << records.size() << '\n';
    std::cout << "initiators=" << kInitiatorCount << '\n';
    return 0;
}

}  // namespace project_at2

int sc_main(int argc, char **argv)
{
    try {
        return project_at2::run(argc, argv);
    } catch (const std::exception &exc) {
        std::cerr << "error: " << exc.what() << '\n';
        return 1;
    }
}
