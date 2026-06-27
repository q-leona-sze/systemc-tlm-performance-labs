// SPDX-License-Identifier: Apache-2.0

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <cstring>
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

namespace project_at1 {
namespace {

constexpr double kAcceptLatencyNs = 1.0;
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

struct Options {
    std::string case_name = "default";
    std::string pattern = "sequential";
    std::filesystem::path output_dir = "examples/at/results/project_at1_four_phase_memory_timing/model_runs/default";
    std::size_t num_transactions = 8;
    std::size_t queue_depth = 2;
    double service_latency_ns = 10.0;
    double issue_gap_ns = 4.0;
};

struct TransactionRecord {
    std::string case_name;
    std::size_t txn_id = 0;
    std::string pattern;
    std::uint64_t addr = 0;
    unsigned int size_bytes = 4;
    tlm::tlm_command cmd = tlm::TLM_READ_COMMAND;
    double begin_req_ns = std::numeric_limits<double>::quiet_NaN();
    double end_req_ns = std::numeric_limits<double>::quiet_NaN();
    double begin_resp_ns = std::numeric_limits<double>::quiet_NaN();
    double end_resp_ns = std::numeric_limits<double>::quiet_NaN();
    unsigned int queue_depth_on_accept = 0;
    bool backpressure = false;
    std::string status = "OK";
};

class TxnExtension : public tlm::tlm_extension<TxnExtension> {
public:
    explicit TxnExtension(std::size_t record_index = 0)
        : record_index(record_index)
    {
    }

    tlm::tlm_extension_base *clone() const override
    {
        return new TxnExtension(record_index);
    }

    void copy_from(const tlm::tlm_extension_base &extension) override
    {
        record_index = static_cast<const TxnExtension &>(extension).record_index;
    }

    std::size_t record_index;
};

TxnExtension &extension_from(tlm::tlm_generic_payload &trans)
{
    TxnExtension *extension = nullptr;
    trans.get_extension(extension);

    if (extension == nullptr) {
        SC_REPORT_FATAL("project_at1", "transaction is missing TxnExtension");
    }

    return *extension;
}

std::uint64_t address_for_pattern(const std::string &pattern, std::size_t index)
{
    if (pattern == "sequential") {
        return 0x1000 + index * 64;
    }

    if (pattern == "bursty") {
        const std::size_t burst_slot = index % 4;
        return 0x2000 + burst_slot * 16;
    }

    if (pattern == "hotspot") {
        return index % 5 == 0 ? 0x3040 : 0x3000;
    }

    throw std::runtime_error("unknown pattern: " + pattern);
}

std::vector<TransactionRecord> make_records(const Options &options)
{
    std::vector<TransactionRecord> records;
    records.reserve(options.num_transactions);

    for (std::size_t index = 0; index < options.num_transactions; ++index) {
        TransactionRecord record;
        record.case_name = options.case_name;
        record.txn_id = index + 1;
        record.pattern = options.pattern;
        record.addr = address_for_pattern(options.pattern, index);
        record.cmd = index % 2 == 0 ? tlm::TLM_READ_COMMAND : tlm::TLM_WRITE_COMMAND;
        records.push_back(record);
    }

    return records;
}

class Initiator : public sc_core::sc_module {
public:
    tlm_utils::simple_initiator_socket<Initiator> socket;

    Initiator(sc_core::sc_module_name name, const Options &options,
              std::vector<TransactionRecord> &records)
        : sc_core::sc_module(name)
        , socket("socket")
        , options_(options)
        , records_(records)
        , awaiting_end_req_index_(0)
        , awaiting_end_req_(false)
        , end_req_seen_(false)
        , completed_responses_(0)
    {
        socket.register_nb_transport_bw(this, &Initiator::nb_transport_bw);
        prepare_payloads();
        SC_THREAD(issue_requests);
        SC_THREAD(send_end_responses);
    }

private:
    struct OwnedTransaction {
        explicit OwnedTransaction(std::size_t record_index)
            : extension(record_index)
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
        payloads_.reserve(records_.size());

        for (std::size_t index = 0; index < records_.size(); ++index) {
            auto owned = std::make_unique<OwnedTransaction>(index);
            owned->payload.set_command(records_[index].cmd);
            owned->payload.set_address(records_[index].addr);
            payloads_.push_back(std::move(owned));
        }
    }

    void issue_requests()
    {
        sc_core::sc_time next_issue_time = sc_core::SC_ZERO_TIME;

        for (std::size_t index = 0; index < payloads_.size(); ++index) {
            const sc_core::sc_time now = sc_core::sc_time_stamp();
            if (now < next_issue_time) {
                wait(next_issue_time - now);
            }

            tlm::tlm_generic_payload &payload = payloads_[index]->payload;
            records_[index].begin_req_ns = now_ns();
            records_[index].status = "IN_FLIGHT";

            awaiting_end_req_index_ = index;
            awaiting_end_req_ = true;
            end_req_seen_ = false;

            tlm::tlm_phase phase = tlm::BEGIN_REQ;
            sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
            tlm::tlm_sync_enum status = socket->nb_transport_fw(payload, phase, delay);

            if (status == tlm::TLM_COMPLETED) {
                SC_REPORT_FATAL("project_at1", "target completed BEGIN_REQ unexpectedly");
            }

            while (!end_req_seen_) {
                wait(end_req_event_);
            }

            awaiting_end_req_ = false;
            next_issue_time = ns(records_[index].begin_req_ns + options_.issue_gap_ns);
        }

        while (completed_responses_ < payloads_.size()) {
            wait(all_responses_done_event_);
        }

        sc_core::sc_stop();
    }

    tlm::tlm_sync_enum nb_transport_bw(tlm::tlm_generic_payload &trans,
                                       tlm::tlm_phase &phase,
                                       sc_core::sc_time &delay)
    {
        if (delay != sc_core::SC_ZERO_TIME) {
            wait(delay);
        }

        TxnExtension &extension = extension_from(trans);
        TransactionRecord &record = records_.at(extension.record_index);

        if (phase == tlm::END_REQ) {
            record.end_req_ns = now_ns();
            if (!awaiting_end_req_ || awaiting_end_req_index_ != extension.record_index) {
                SC_REPORT_FATAL("project_at1", "END_REQ does not match active request");
            }
            end_req_seen_ = true;
            end_req_event_.notify(sc_core::SC_ZERO_TIME);
            return tlm::TLM_ACCEPTED;
        }

        if (phase == tlm::BEGIN_RESP) {
            record.begin_resp_ns = now_ns();
            if (trans.is_response_error()) {
                record.status = trans.get_response_string();
            }
            response_queue_.push_back(&trans);
            response_event_.notify(sc_core::SC_ZERO_TIME);
            return tlm::TLM_ACCEPTED;
        }

        SC_REPORT_FATAL("project_at1", "initiator received unexpected backward phase");
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

                TxnExtension &extension = extension_from(*trans);
                TransactionRecord &record = records_.at(extension.record_index);

                tlm::tlm_phase phase = tlm::END_RESP;
                sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
                records_[extension.record_index].end_resp_ns = now_ns();
                socket->nb_transport_fw(*trans, phase, delay);

                if (record.status == "IN_FLIGHT") {
                    record.status = "OK";
                }

                ++completed_responses_;
                if (completed_responses_ == payloads_.size()) {
                    all_responses_done_event_.notify(sc_core::SC_ZERO_TIME);
                }
            }
        }
    }

    const Options &options_;
    std::vector<TransactionRecord> &records_;
    std::vector<std::unique_ptr<OwnedTransaction>> payloads_;
    std::deque<tlm::tlm_generic_payload *> response_queue_;
    sc_core::sc_event end_req_event_;
    sc_core::sc_event response_event_;
    sc_core::sc_event all_responses_done_event_;
    std::size_t awaiting_end_req_index_;
    bool awaiting_end_req_;
    bool end_req_seen_;
    std::size_t completed_responses_;

    SC_HAS_PROCESS(Initiator);
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
    struct AcceptEntry {
        tlm::tlm_generic_payload *trans;
    };

    tlm::tlm_sync_enum nb_transport_fw(tlm::tlm_generic_payload &trans,
                                       tlm::tlm_phase &phase,
                                       sc_core::sc_time &delay)
    {
        if (delay != sc_core::SC_ZERO_TIME) {
            wait(delay);
        }

        if (phase == tlm::BEGIN_REQ) {
            if (occupied_slots_ < options_.queue_depth) {
                accept_request(trans, false);
            } else {
                TransactionRecord &record = record_for(trans);
                record.backpressure = true;
                waiting_accept_queue_.push_back(&trans);
            }
            return tlm::TLM_ACCEPTED;
        }

        if (phase == tlm::END_RESP) {
            record_for(trans).end_resp_ns = now_ns();
            return tlm::TLM_ACCEPTED;
        }

        SC_REPORT_FATAL("project_at1", "target received unexpected forward phase");
        return tlm::TLM_ACCEPTED;
    }

    TransactionRecord &record_for(tlm::tlm_generic_payload &trans)
    {
        TxnExtension &extension = extension_from(trans);
        return records_.at(extension.record_index);
    }

    void accept_request(tlm::tlm_generic_payload &trans, bool backpressure)
    {
        ++occupied_slots_;

        TransactionRecord &record = record_for(trans);
        record.queue_depth_on_accept = static_cast<unsigned int>(occupied_slots_);
        record.backpressure = record.backpressure || backpressure;

        end_req_queue_.push_back(AcceptEntry{&trans});
        end_req_event_.notify(sc_core::SC_ZERO_TIME);
    }

    void try_accept_waiting_request()
    {
        if (waiting_accept_queue_.empty() || occupied_slots_ >= options_.queue_depth) {
            return;
        }

        tlm::tlm_generic_payload *trans = waiting_accept_queue_.front();
        waiting_accept_queue_.pop_front();
        accept_request(*trans, true);
    }

    void send_end_requests()
    {
        while (true) {
            if (end_req_queue_.empty()) {
                wait(end_req_event_);
            }

            while (!end_req_queue_.empty()) {
                AcceptEntry entry = end_req_queue_.front();
                end_req_queue_.pop_front();

                wait(ns(kAcceptLatencyNs));

                tlm::tlm_phase phase = tlm::END_REQ;
                sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
                socket->nb_transport_bw(*entry.trans, phase, delay);

                service_queue_.push_back(entry.trans);
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
                tlm::tlm_phase phase = tlm::BEGIN_RESP;
                sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
                record_for(*trans).begin_resp_ns = now_ns();
                socket->nb_transport_bw(*trans, phase, delay);

                if (occupied_slots_ == 0) {
                    SC_REPORT_FATAL("project_at1", "target queue occupancy underflow");
                }
                --occupied_slots_;
                try_accept_waiting_request();
            }
        }
    }

    const Options &options_;
    std::vector<TransactionRecord> &records_;
    std::deque<tlm::tlm_generic_payload *> waiting_accept_queue_;
    std::deque<AcceptEntry> end_req_queue_;
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
        , initiator_("initiator", options, records)
        , target_("target", options, records)
    {
        initiator_.socket.bind(target_.socket);
    }

private:
    Initiator initiator_;
    MemoryTarget target_;
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
    std::size_t parsed = 0;
    try {
        parsed = static_cast<std::size_t>(std::stoull(value));
    } catch (const std::exception &) {
        throw std::runtime_error("invalid " + option + ": " + value);
    }

    return parsed;
}

double parse_double(const std::string &value, const std::string &option)
{
    try {
        return std::stod(value);
    } catch (const std::exception &) {
        throw std::runtime_error("invalid " + option + ": " + value);
    }
}

void print_help(const char *program)
{
    std::cout
        << "Usage: " << program << " [options]\n"
        << "\n"
        << "Options:\n"
        << "  --case-name <name>\n"
        << "  --pattern <sequential|bursty|hotspot>\n"
        << "  --num-transactions <count>\n"
        << "  --queue-depth <count>\n"
        << "  --service-latency-ns <ns>\n"
        << "  --issue-gap-ns <ns>\n"
        << "  --output-dir <dir>\n"
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
        } else if (arg == "--case-name") {
            options.case_name = required_value(argc, argv, index, arg);
        } else if (arg == "--pattern") {
            options.pattern = required_value(argc, argv, index, arg);
        } else if (arg == "--num-transactions") {
            options.num_transactions = parse_size(required_value(argc, argv, index, arg), arg);
        } else if (arg == "--queue-depth") {
            options.queue_depth = parse_size(required_value(argc, argv, index, arg), arg);
        } else if (arg == "--service-latency-ns") {
            options.service_latency_ns = parse_double(required_value(argc, argv, index, arg), arg);
        } else if (arg == "--issue-gap-ns") {
            options.issue_gap_ns = parse_double(required_value(argc, argv, index, arg), arg);
        } else if (arg == "--output-dir") {
            options.output_dir = required_value(argc, argv, index, arg);
        } else {
            throw std::runtime_error("unknown option: " + arg);
        }
    }

    if (options.num_transactions == 0) {
        throw std::runtime_error("--num-transactions must be greater than 0");
    }
    if (options.queue_depth == 0) {
        throw std::runtime_error("--queue-depth must be greater than 0");
    }
    if (options.service_latency_ns < 0.0 || options.issue_gap_ns < 0.0) {
        throw std::runtime_error("latency and issue gap must be non-negative");
    }
    if (options.pattern != "sequential" && options.pattern != "bursty" &&
        options.pattern != "hotspot") {
        throw std::runtime_error("--pattern must be sequential, bursty, or hotspot");
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

    out << "case_name,txn_id,pattern,addr,size_bytes,cmd,begin_req_ns,end_req_ns,"
        << "begin_resp_ns,end_resp_ns,request_accept_latency_ns,"
        << "target_service_latency_ns,response_latency_ns,initiator_blocked_ns,"
        << "queue_depth_on_accept,backpressure,status\n";

    out << std::fixed << std::setprecision(3);
    for (const TransactionRecord &record : records) {
        const double request_accept_latency_ns =
            delta(record.end_req_ns, record.begin_req_ns);
        const double target_service_latency_ns =
            delta(record.begin_resp_ns, record.end_req_ns);
        const double response_latency_ns =
            delta(record.end_resp_ns, record.begin_resp_ns);
        const double initiator_blocked_ns =
            record.backpressure
                ? std::max(0.0, request_accept_latency_ns - kAcceptLatencyNs)
                : 0.0;

        out << record.case_name << ','
            << record.txn_id << ','
            << record.pattern << ','
            << hex_value(record.addr) << ','
            << record.size_bytes << ','
            << command_name(record.cmd) << ','
            << record.begin_req_ns << ','
            << record.end_req_ns << ','
            << record.begin_resp_ns << ','
            << record.end_resp_ns << ','
            << request_accept_latency_ns << ','
            << target_service_latency_ns << ','
            << response_latency_ns << ','
            << initiator_blocked_ns << ','
            << record.queue_depth_on_accept << ','
            << (record.backpressure ? "YES" : "NO") << ','
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

    std::cout << "project_at1_trace=" << trace_path.string() << '\n';
    std::cout << "transactions=" << records.size() << '\n';
    return 0;
}

}  // namespace project_at1

int sc_main(int argc, char **argv)
{
    try {
        return project_at1::run(argc, argv);
    } catch (const std::exception &exc) {
        std::cerr << "error: " << exc.what() << '\n';
        return 1;
    }
}
