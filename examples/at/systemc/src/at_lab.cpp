// SPDX-License-Identifier: Apache-2.0

#include "at_lab.h"

#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <sstream>

namespace at_lab {
namespace {

const char *phase_name(const tlm::tlm_phase &phase)
{
    if (phase == tlm::BEGIN_REQ) {
        return "BEGIN_REQ";
    }
    if (phase == tlm::END_REQ) {
        return "END_REQ";
    }
    if (phase == tlm::BEGIN_RESP) {
        return "BEGIN_RESP";
    }
    if (phase == tlm::END_RESP) {
        return "END_RESP";
    }
    return phase.get_name();
}

const char *command_name(tlm::tlm_command command)
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

std::string hex_value(std::uint64_t value, int width)
{
    std::ostringstream out;
    out << "0x" << std::hex << std::nouppercase << std::setw(width)
        << std::setfill('0') << value;
    return out.str();
}

std::uint32_t payload_word(const tlm::tlm_generic_payload &trans)
{
    std::uint32_t value = 0;
    const unsigned char *data = trans.get_data_ptr();

    if (data != nullptr && trans.get_data_length() >= sizeof(value)) {
        std::memcpy(&value, data, sizeof(value));
    }

    return value;
}

unsigned int txn_id(const tlm::tlm_generic_payload &trans)
{
    TxnIdExtension *extension = nullptr;
    trans.get_extension(extension);

    if (extension == nullptr) {
        return 0;
    }

    return extension->id;
}

}  // namespace

TxnIdExtension::TxnIdExtension(unsigned int id)
    : id(id)
{
}

tlm::tlm_extension_base *TxnIdExtension::clone() const
{
    return new TxnIdExtension(id);
}

void TxnIdExtension::copy_from(const tlm::tlm_extension_base &extension)
{
    id = static_cast<const TxnIdExtension &>(extension).id;
}

PhaseTrace::PhaseTrace(const std::string &path)
    : out_(path)
{
    if (!out_) {
        SC_REPORT_FATAL("at_lab", "failed to open phase_trace.csv");
    }

    out_ << "txn_id,component,direction,phase,command,address,data,time_ns,delay_ns,response_status\n";
}

PhaseTrace::~PhaseTrace()
{
    out_.flush();
}

void PhaseTrace::log(const char *component, const char *direction,
                     const tlm::tlm_generic_payload &trans,
                     const tlm::tlm_phase &phase,
                     const sc_core::sc_time &delay)
{
    out_ << txn_id(trans) << ','
         << component << ','
         << direction << ','
         << phase_name(phase) << ','
         << command_name(trans.get_command()) << ','
         << hex_value(trans.get_address(), 16) << ','
         << hex_value(payload_word(trans), 8) << ','
         << std::fixed << std::setprecision(3)
         << sc_core::sc_time_stamp().to_seconds() * 1e9 << ','
         << delay.to_seconds() * 1e9 << ','
         << trans.get_response_string() << '\n';
}

Initiator::Initiator(sc_core::sc_module_name name, unsigned int initiator_id,
                     std::uint64_t address, std::uint32_t write_data)
    : sc_core::sc_module(name)
    , socket("socket")
    , peq_(this, &Initiator::handle_bw_phase)
    , initiator_id_(initiator_id)
    , address_(address)
    , write_data_(write_data)
    , request_in_progress_(nullptr)
    , response_seen_(false)
    , done_(false)
{
    socket.register_nb_transport_bw(this, &Initiator::nb_transport_bw);
    SC_THREAD(run);
}

bool Initiator::done() const
{
    return done_;
}

const sc_core::sc_event &Initiator::done_event() const
{
    return done_event_;
}

void Initiator::run()
{
    wait(sc_core::SC_ZERO_TIME);

    std::uint32_t write_data = write_data_;
    send_transaction(tlm::TLM_WRITE_COMMAND, address_, write_data, make_txn_id(1));

    std::uint32_t read_data = 0;
    send_transaction(tlm::TLM_READ_COMMAND, address_, read_data, make_txn_id(2));

    if (read_data != write_data) {
        SC_REPORT_FATAL("at_lab", "READ did not return the value written by WRITE");
    }

    done_ = true;
    done_event_.notify(sc_core::SC_ZERO_TIME);
}

void Initiator::send_transaction(tlm::tlm_command command, std::uint64_t address,
                                 std::uint32_t &data, unsigned int txn_id)
{
    tlm::tlm_generic_payload trans;
    TxnIdExtension txn_id_extension(txn_id);

    trans.set_extension(&txn_id_extension);
    trans.set_command(command);
    trans.set_address(address);
    trans.set_data_ptr(reinterpret_cast<unsigned char *>(&data));
    trans.set_data_length(sizeof(data));
    trans.set_streaming_width(sizeof(data));
    trans.set_byte_enable_ptr(nullptr);
    trans.set_byte_enable_length(0);
    trans.set_dmi_allowed(false);
    trans.set_response_status(tlm::TLM_INCOMPLETE_RESPONSE);

    tlm::tlm_phase phase = tlm::BEGIN_REQ;
    sc_core::sc_time delay = sc_core::SC_ZERO_TIME;

    request_in_progress_ = &trans;
    response_seen_ = false;

    tlm::tlm_sync_enum status = socket->nb_transport_fw(trans, phase, delay);
    if (status == tlm::TLM_UPDATED) {
        peq_.notify(trans, phase, delay);
    } else if (status == tlm::TLM_COMPLETED) {
        request_in_progress_ = nullptr;
        response_seen_ = true;
        check_response(trans);
    }

    if (!response_seen_) {
        wait(response_done_);
    }

    trans.clear_extension<TxnIdExtension>();
}

unsigned int Initiator::make_txn_id(unsigned int sequence) const
{
    return initiator_id_ * 1000 + sequence;
}

tlm::tlm_sync_enum Initiator::nb_transport_bw(tlm::tlm_generic_payload &trans,
                                              tlm::tlm_phase &phase,
                                              sc_core::sc_time &delay)
{
    peq_.notify(trans, phase, delay);
    return tlm::TLM_ACCEPTED;
}

void Initiator::handle_bw_phase(tlm::tlm_generic_payload &trans,
                                const tlm::tlm_phase &phase)
{
    if (phase == tlm::END_REQ) {
        if (&trans == request_in_progress_) {
            request_in_progress_ = nullptr;
        }
        return;
    }

    if (phase != tlm::BEGIN_RESP) {
        SC_REPORT_FATAL("at_lab", "initiator received an unexpected AT phase");
    }

    if (&trans == request_in_progress_) {
        request_in_progress_ = nullptr;
    }

    check_response(trans);

    tlm::tlm_phase end_phase = tlm::END_RESP;
    sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
    socket->nb_transport_fw(trans, end_phase, delay);

    response_seen_ = true;
    response_done_.notify(sc_core::SC_ZERO_TIME);
}

void Initiator::check_response(const tlm::tlm_generic_payload &trans) const
{
    if (trans.is_response_error()) {
        SC_REPORT_FATAL("at_lab", trans.get_response_string().c_str());
    }
}

SimpleAtBus::SimpleAtBus(sc_core::sc_module_name name, PhaseTrace &trace)
    : sc_core::sc_module(name)
    , upstream_socket_101("upstream_socket_101")
    , upstream_socket_102("upstream_socket_102")
    , downstream_socket("downstream_socket")
    , trace_(trace)
    , active_request_(nullptr)
    , active_initiator_id_(0)
    , arbitration_policy_(arbitration_policy_from_env())
{
    upstream_socket_101.register_nb_transport_fw(
        this, &SimpleAtBus::nb_transport_fw_101);
    upstream_socket_102.register_nb_transport_fw(
        this, &SimpleAtBus::nb_transport_fw_102);
    downstream_socket.register_nb_transport_bw(this, &SimpleAtBus::nb_transport_bw);
    SC_THREAD(service_requests);
}

tlm::tlm_sync_enum SimpleAtBus::nb_transport_fw_101(tlm::tlm_generic_payload &trans,
                                                    tlm::tlm_phase &phase,
                                                    sc_core::sc_time &delay)
{
    return nb_transport_fw(101, trans, phase, delay);
}

tlm::tlm_sync_enum SimpleAtBus::nb_transport_fw_102(tlm::tlm_generic_payload &trans,
                                                    tlm::tlm_phase &phase,
                                                    sc_core::sc_time &delay)
{
    return nb_transport_fw(102, trans, phase, delay);
}

tlm::tlm_sync_enum SimpleAtBus::nb_transport_fw(unsigned int initiator_id,
                                                tlm::tlm_generic_payload &trans,
                                                tlm::tlm_phase &phase,
                                                sc_core::sc_time &delay)
{
    trace_.log("bus", "FW", trans, phase, delay);

    if (phase == tlm::BEGIN_REQ) {
        pending_requests_.push_back(PendingRequest{&trans, initiator_id});
        service_event_.notify(delay);
        return tlm::TLM_ACCEPTED;
    }

    if (phase == tlm::END_RESP) {
        if (&trans != active_request_ || initiator_id != active_initiator_id_) {
            SC_REPORT_FATAL("at_lab",
                            "bus received END_RESP for an unknown transaction");
        }

        tlm::tlm_sync_enum status =
            downstream_socket->nb_transport_fw(trans, phase, delay);
        if (status == tlm::TLM_COMPLETED) {
            SC_REPORT_FATAL("at_lab", "target completed an END_RESP unexpectedly");
        }

        active_request_ = nullptr;
        active_initiator_id_ = 0;
        service_event_.notify(sc_core::SC_ZERO_TIME);
        return tlm::TLM_ACCEPTED;
    }

    SC_REPORT_FATAL("at_lab", "bus received an unexpected forward AT phase");
    return tlm::TLM_ACCEPTED;
}

tlm::tlm_sync_enum SimpleAtBus::nb_transport_bw(tlm::tlm_generic_payload &trans,
                                                tlm::tlm_phase &phase,
                                                sc_core::sc_time &delay)
{
    if (&trans != active_request_) {
        SC_REPORT_FATAL("at_lab",
                        "bus received a backward phase for an unknown transaction");
    }

    trace_.log("bus", "BW", trans, phase, delay);
    return send_bw_to_initiator(active_initiator_id_, trans, phase, delay);
}

tlm::tlm_sync_enum SimpleAtBus::send_bw_to_initiator(unsigned int initiator_id,
                                                     tlm::tlm_generic_payload &trans,
                                                     tlm::tlm_phase &phase,
                                                     sc_core::sc_time &delay)
{
    if (initiator_id == 101) {
        return upstream_socket_101->nb_transport_bw(trans, phase, delay);
    }

    if (initiator_id == 102) {
        return upstream_socket_102->nb_transport_bw(trans, phase, delay);
    }

    SC_REPORT_FATAL("at_lab", "bus cannot route backward phase to initiator");
    return tlm::TLM_ACCEPTED;
}

SimpleAtBus::ArbitrationPolicy SimpleAtBus::arbitration_policy_from_env()
{
    const char *policy = std::getenv("AT_ARBITRATION_POLICY");

    if (policy == nullptr || std::strcmp(policy, "") == 0 ||
        std::strcmp(policy, "fifo") == 0) {
        return ArbitrationPolicy::Fifo;
    }

    if (std::strcmp(policy, "priority_101") == 0) {
        return ArbitrationPolicy::Priority101;
    }

    if (std::strcmp(policy, "priority_102") == 0) {
        return ArbitrationPolicy::Priority102;
    }

    SC_REPORT_FATAL("at_lab",
                    "unknown AT_ARBITRATION_POLICY; expected fifo, "
                    "priority_101, or priority_102");
    return ArbitrationPolicy::Fifo;
}

SimpleAtBus::PendingRequest SimpleAtBus::pop_next_request()
{
    if (arbitration_policy_ == ArbitrationPolicy::Fifo) {
        PendingRequest request = pending_requests_.front();
        pending_requests_.pop_front();
        return request;
    }

    const unsigned int preferred_initiator =
        arbitration_policy_ == ArbitrationPolicy::Priority101 ? 101 : 102;

    for (auto it = pending_requests_.begin(); it != pending_requests_.end(); ++it) {
        if (it->initiator_id == preferred_initiator) {
            PendingRequest request = *it;
            pending_requests_.erase(it);
            return request;
        }
    }

    PendingRequest request = pending_requests_.front();
    pending_requests_.pop_front();
    return request;
}

void SimpleAtBus::service_requests()
{
    while (true) {
        wait(service_event_);

        if (active_request_ != nullptr || pending_requests_.empty()) {
            continue;
        }

        PendingRequest request = pop_next_request();

        active_request_ = request.trans;
        active_initiator_id_ = request.initiator_id;

        tlm::tlm_phase phase = tlm::BEGIN_REQ;
        sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
        tlm::tlm_sync_enum status =
            downstream_socket->nb_transport_fw(*active_request_, phase, delay);

        if (status != tlm::TLM_ACCEPTED) {
            SC_REPORT_FATAL("at_lab", "target did not accept BEGIN_REQ asynchronously");
        }
    }
}

Target::Target(sc_core::sc_module_name name)
    : sc_core::sc_module(name)
    , socket("socket")
    , pending_request_(nullptr)
    , response_in_progress_(nullptr)
    , words_{0, 0}
{
    socket.register_nb_transport_fw(this, &Target::nb_transport_fw);
    SC_THREAD(process_requests);
}

tlm::tlm_sync_enum Target::nb_transport_fw(tlm::tlm_generic_payload &trans,
                                           tlm::tlm_phase &phase,
                                           sc_core::sc_time &delay)
{
    if (phase == tlm::BEGIN_REQ) {
        if (pending_request_ != nullptr) {
            trans.set_response_status(tlm::TLM_GENERIC_ERROR_RESPONSE);
            return tlm::TLM_COMPLETED;
        }

        pending_request_ = &trans;
        request_event_.notify(delay);
        return tlm::TLM_ACCEPTED;
    }

    if (phase == tlm::END_RESP) {
        if (response_in_progress_ != &trans) {
            SC_REPORT_FATAL("at_lab", "target received END_RESP for an unknown transaction");
        }

        response_in_progress_ = nullptr;
        pending_request_ = nullptr;
        end_response_event_.notify(delay);
        return tlm::TLM_ACCEPTED;
    }

    SC_REPORT_FATAL("at_lab", "target received an unexpected AT phase");
    return tlm::TLM_ACCEPTED;
}

void Target::process_requests()
{
    while (true) {
        wait(request_event_);
        tlm::tlm_generic_payload *trans = pending_request_;

        wait(sc_core::sc_time(1, sc_core::SC_NS));
        tlm::tlm_phase phase = tlm::END_REQ;
        sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
        socket->nb_transport_bw(*trans, phase, delay);

        wait(sc_core::sc_time(4, sc_core::SC_NS));
        execute(*trans);

        response_in_progress_ = trans;
        phase = tlm::BEGIN_RESP;
        delay = sc_core::SC_ZERO_TIME;
        socket->nb_transport_bw(*trans, phase, delay);

        wait(end_response_event_);
    }
}

void Target::execute(tlm::tlm_generic_payload &trans)
{
    const std::uint64_t word_index = trans.get_address() / sizeof(std::uint32_t);

    if ((trans.get_address() % sizeof(std::uint32_t)) != 0 ||
        word_index >= words_.size() ||
        trans.get_data_length() != sizeof(std::uint32_t) ||
        trans.get_byte_enable_ptr() != nullptr ||
        trans.get_streaming_width() < sizeof(std::uint32_t)) {
        trans.set_response_status(tlm::TLM_GENERIC_ERROR_RESPONSE);
        return;
    }

    std::uint32_t &word = words_[word_index];

    if (trans.is_write()) {
        std::memcpy(&word, trans.get_data_ptr(), sizeof(word));
    } else if (trans.is_read()) {
        std::memcpy(trans.get_data_ptr(), &word, sizeof(word));
    } else {
        trans.set_response_status(tlm::TLM_COMMAND_ERROR_RESPONSE);
        return;
    }

    trans.set_response_status(tlm::TLM_OK_RESPONSE);
}

Top::Top(sc_core::sc_module_name name, PhaseTrace &trace)
    : sc_core::sc_module(name)
    , initiator101_("initiator101", 101, 0x0, 0x1010abcd)
    , initiator102_("initiator102", 102, 0x4, 0x1020abcd)
    , bus_("bus", trace)
    , target_("target")
{
    initiator101_.socket.bind(bus_.upstream_socket_101);
    initiator102_.socket.bind(bus_.upstream_socket_102);
    bus_.downstream_socket.bind(target_.socket);
    SC_THREAD(stop_when_done);
}

void Top::stop_when_done()
{
    while (!initiator101_.done() || !initiator102_.done()) {
        wait(initiator101_.done_event() | initiator102_.done_event());
    }

    sc_core::sc_stop();
}

}  // namespace at_lab
