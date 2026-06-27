#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional, Tuple


REQUIRED_FIELDS = [
    "txn_id",
    "component",
    "direction",
    "phase",
    "command",
    "address",
    "data",
    "time_ns",
    "delay_ns",
    "response_status",
]

PHASES = ["BEGIN_REQ", "END_REQ", "BEGIN_RESP", "END_RESP"]


@dataclass(frozen=True)
class PhaseEvent:
    row_number: int
    txn_id: str
    component: str
    direction: str
    phase: str
    command: str
    address: str
    data: str
    time_ns: Decimal
    delay_ns: Decimal
    response_status: str


@dataclass
class TransactionSummary:
    txn_id: str
    command: str
    begin_req_ns: Optional[Decimal]
    end_req_ns: Optional[Decimal]
    begin_resp_ns: Optional[Decimal]
    end_resp_ns: Optional[Decimal]
    request_accept_latency_ns: Optional[Decimal]
    response_latency_ns: Optional[Decimal]
    total_transaction_latency_ns: Optional[Decimal]
    response_status: str
    sanity_issues: List[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze a TLM-2.0 AT phase_trace.csv file."
    )
    parser.add_argument(
        "--trace",
        default="phase_trace.csv",
        help="Path to the phase trace CSV file. Default: phase_trace.csv",
    )
    parser.add_argument(
        "--summary-csv-output",
        help="Optional path for one-row run-level summary metrics CSV.",
    )
    parser.add_argument(
        "--timeline-csv-output",
        help="Optional path for a per-transaction timeline CSV.",
    )
    parser.add_argument(
        "--fail-on-sanity",
        action="store_true",
        help="Exit with status 1 if any sanity check fails.",
    )
    return parser.parse_args()


def parse_decimal(value: str, field: str, row_number: int) -> Decimal:
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"row {row_number}: invalid {field}: {value}") from exc

    if not parsed.is_finite():
        raise ValueError(f"row {row_number}: invalid {field}: {value}")

    return parsed


def validate_row(row: dict, row_number: int) -> None:
    if None in row:
        raise ValueError(
            f"malformed CSV row {row_number}: unexpected extra field(s)"
        )

    for field in REQUIRED_FIELDS:
        if field not in row or row[field] in (None, ""):
            raise ValueError(
                f"malformed CSV row {row_number}: missing field {field}"
            )


def load_events(trace_path: Path) -> List[PhaseEvent]:
    with trace_path.open(newline="") as trace_file:
        reader = csv.DictReader(trace_file)
        if reader.fieldnames != REQUIRED_FIELDS:
            raise ValueError(
                "unexpected CSV header: "
                f"{reader.fieldnames}; expected: {REQUIRED_FIELDS}"
            )

        events = []
        for row_number, row in enumerate(reader, start=2):
            validate_row(row, row_number)
            events.append(
                PhaseEvent(
                    row_number=row_number,
                    txn_id=row["txn_id"],
                    component=row["component"],
                    direction=row["direction"],
                    phase=row["phase"],
                    command=row["command"],
                    address=row["address"],
                    data=row["data"],
                    time_ns=parse_decimal(row["time_ns"], "time_ns", row_number),
                    delay_ns=parse_decimal(row["delay_ns"], "delay_ns", row_number),
                    response_status=row["response_status"],
                )
            )
    return events


def decimal_or_na(value: Optional[Decimal]) -> str:
    if value is None:
        return "NA"
    return f"{value:.3f}"


def event_sort_key(event: PhaseEvent) -> Tuple[Decimal, int]:
    return event.time_ns, event.row_number


def phase_event(events: List[PhaseEvent], phase: str) -> Optional[PhaseEvent]:
    for event in events:
        if event.phase == phase:
            return event
    return None


def phase_time(events: List[PhaseEvent], phase: str) -> Optional[Decimal]:
    event = phase_event(events, phase)
    if event is None:
        return None
    return event.time_ns


def latency(
    end_time: Optional[Decimal], start_time: Optional[Decimal]
) -> Optional[Decimal]:
    if start_time is None or end_time is None:
        return None
    return end_time - start_time


def txn_sort_key(txn_id: str) -> Tuple[int, str]:
    try:
        return int(txn_id), txn_id
    except ValueError:
        return sys.maxsize, txn_id


def summarize_transaction(txn_id: str, events: List[PhaseEvent]) -> TransactionSummary:
    command = events[0].command if events else "NA"
    response_status = events[-1].response_status if events else "NA"

    end_resp = phase_event(events, "END_RESP")
    if end_resp is not None:
        response_status = end_resp.response_status

    begin_req_ns = phase_time(events, "BEGIN_REQ")
    end_req_ns = phase_time(events, "END_REQ")
    begin_resp_ns = phase_time(events, "BEGIN_RESP")
    end_resp_ns = phase_time(events, "END_RESP")

    issues = []
    for phase in PHASES:
        matching_events = [event for event in events if event.phase == phase]
        if not matching_events:
            issues.append(f"missing {phase}")
        elif len(matching_events) > 1:
            issues.append(f"duplicate {phase}")

    if len({event.command for event in events}) > 1:
        issues.append("inconsistent command within transaction")

    if len({event.address for event in events}) > 1:
        issues.append("inconsistent address within transaction")

    previous = None
    for event in events:
        if previous is not None and event.time_ns < previous.time_ns:
            issues.append(
                "phase time going backwards within txn "
                f"(row {event.row_number}: {event.phase})"
            )
        previous = event

    begin_resp = phase_event(events, "BEGIN_RESP")
    begin_req = phase_event(events, "BEGIN_REQ")
    end_req = phase_event(events, "END_REQ")

    if end_req is not None and begin_req is not None:
        if event_sort_key(end_req) < event_sort_key(begin_req):
            issues.append("END_REQ before BEGIN_REQ")

    if end_resp is not None and begin_resp is not None:
        if event_sort_key(end_resp) < event_sort_key(begin_resp):
            issues.append("END_RESP before BEGIN_RESP")

    if begin_resp is not None and end_req is not None:
        if event_sort_key(begin_resp) < event_sort_key(end_req):
            issues.append("BEGIN_RESP before END_REQ")

    return TransactionSummary(
        txn_id=txn_id,
        command=command,
        begin_req_ns=begin_req_ns,
        end_req_ns=end_req_ns,
        begin_resp_ns=begin_resp_ns,
        end_resp_ns=end_resp_ns,
        request_accept_latency_ns=latency(end_req_ns, begin_req_ns),
        response_latency_ns=latency(begin_resp_ns, end_req_ns),
        total_transaction_latency_ns=latency(end_resp_ns, begin_req_ns),
        response_status=response_status,
        sanity_issues=issues,
    )


def summarize(events: List[PhaseEvent]) -> List[TransactionSummary]:
    by_txn = defaultdict(list)
    for event in events:
        by_txn[event.txn_id].append(event)

    return [
        summarize_transaction(txn_id, by_txn[txn_id])
        for txn_id in sorted(by_txn, key=txn_sort_key)
    ]


def run_level_sanity_issues(summaries: List[TransactionSummary]) -> List[str]:
    if summaries:
        return []
    return ["no transactions found"]


def sanity_failure_count(summaries: List[TransactionSummary]) -> int:
    return sum(len(summary.sanity_issues) for summary in summaries) + len(
        run_level_sanity_issues(summaries)
    )


def complete_summaries(
    summaries: List[TransactionSummary],
) -> List[TransactionSummary]:
    return [summary for summary in summaries if not summary.sanity_issues]


def average_decimal(values: List[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    return sum(values, Decimal("0")) / Decimal(len(values))


def metric_or_zero(value: Optional[Decimal]) -> Decimal:
    if value is None:
        return Decimal("0")
    return value


def format_decimal(value: Decimal) -> str:
    return f"{value:.3f}"


def summary_metrics(
    summaries: List[TransactionSummary], total_phase_events: int
) -> dict:
    complete = complete_summaries(summaries)
    incomplete = [summary for summary in summaries if summary.sanity_issues]

    request_latencies = [
        metric_or_zero(summary.request_accept_latency_ns) for summary in complete
    ]
    response_latencies = [
        metric_or_zero(summary.response_latency_ns) for summary in complete
    ]
    total_latencies = [
        metric_or_zero(summary.total_transaction_latency_ns) for summary in complete
    ]

    return {
        "total_transactions": len(summaries),
        "complete_transactions": len(complete),
        "incomplete_transactions": len(incomplete),
        "total_phase_events": total_phase_events,
        "sanity_failure_count": sanity_failure_count(summaries),
        "avg_request_accept_latency_ns": format_decimal(
            average_decimal(request_latencies)
        ),
        "avg_response_latency_ns": format_decimal(average_decimal(response_latencies)),
        "avg_total_transaction_latency_ns": format_decimal(
            average_decimal(total_latencies)
        ),
        "max_total_transaction_latency_ns": format_decimal(
            max(total_latencies) if total_latencies else Decimal("0")
        ),
    }


def print_report(summaries: List[TransactionSummary], total_phase_events: int) -> None:
    complete = complete_summaries(summaries)
    incomplete = [summary for summary in summaries if summary.sanity_issues]
    run_issues = run_level_sanity_issues(summaries)

    print("Overview")
    print(f"  total_transactions: {len(summaries)}")
    print(f"  complete_transactions: {len(complete)}")
    print(f"  incomplete_transactions: {len(incomplete)}")
    print(f"  total_phase_events: {total_phase_events}")
    print()

    print("Per Transaction Timeline")
    print(
        "  txn_id command begin_req_ns end_req_ns begin_resp_ns end_resp_ns "
        "request_accept_latency_ns response_latency_ns "
        "total_transaction_latency_ns response_status"
    )
    for summary in summaries:
        print(
            "  "
            f"{summary.txn_id} "
            f"{summary.command} "
            f"{decimal_or_na(summary.begin_req_ns)} "
            f"{decimal_or_na(summary.end_req_ns)} "
            f"{decimal_or_na(summary.begin_resp_ns)} "
            f"{decimal_or_na(summary.end_resp_ns)} "
            f"{decimal_or_na(summary.request_accept_latency_ns)} "
            f"{decimal_or_na(summary.response_latency_ns)} "
            f"{decimal_or_na(summary.total_transaction_latency_ns)} "
            f"{summary.response_status}"
        )
    print()

    print("Sanity Checks")
    if not incomplete and not run_issues:
        print("  OK")
        return

    for issue in run_issues:
        print(f"  {issue}")

    for summary in incomplete:
        for issue in summary.sanity_issues:
            print(f"  txn_id={summary.txn_id}: {issue}")


def write_run_summary_csv(
    path: Path, summaries: List[TransactionSummary], total_phase_events: int
) -> None:
    fields = [
        "total_transactions",
        "complete_transactions",
        "incomplete_transactions",
        "total_phase_events",
        "sanity_failure_count",
        "avg_request_accept_latency_ns",
        "avg_response_latency_ns",
        "avg_total_transaction_latency_ns",
        "max_total_transaction_latency_ns",
    ]
    metrics = summary_metrics(summaries, total_phase_events=total_phase_events)

    with path.open("w", newline="") as summary_file:
        writer = csv.DictWriter(summary_file, fieldnames=fields)
        writer.writeheader()
        writer.writerow(metrics)


def write_timeline_csv(path: Path, summaries: List[TransactionSummary]) -> None:
    fields = [
        "txn_id",
        "command",
        "begin_req_ns",
        "end_req_ns",
        "begin_resp_ns",
        "end_resp_ns",
        "request_accept_latency_ns",
        "response_latency_ns",
        "total_transaction_latency_ns",
        "response_status",
        "sanity_status",
        "sanity_issues",
    ]

    with path.open("w", newline="") as summary_file:
        writer = csv.DictWriter(summary_file, fieldnames=fields)
        writer.writeheader()
        for summary in summaries:
            writer.writerow(
                {
                    "txn_id": summary.txn_id,
                    "command": summary.command,
                    "begin_req_ns": decimal_or_na(summary.begin_req_ns),
                    "end_req_ns": decimal_or_na(summary.end_req_ns),
                    "begin_resp_ns": decimal_or_na(summary.begin_resp_ns),
                    "end_resp_ns": decimal_or_na(summary.end_resp_ns),
                    "request_accept_latency_ns": decimal_or_na(
                        summary.request_accept_latency_ns
                    ),
                    "response_latency_ns": decimal_or_na(summary.response_latency_ns),
                    "total_transaction_latency_ns": decimal_or_na(
                        summary.total_transaction_latency_ns
                    ),
                    "response_status": summary.response_status,
                    "sanity_status": "OK" if not summary.sanity_issues else "FAIL",
                    "sanity_issues": "; ".join(summary.sanity_issues),
                }
            )


def main() -> int:
    args = parse_args()
    trace_path = Path(args.trace)

    try:
        events = load_events(trace_path)
        summaries = summarize(events)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print_report(summaries, len(events))

    if args.summary_csv_output:
        try:
            write_run_summary_csv(Path(args.summary_csv_output), summaries, len(events))
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    if args.timeline_csv_output:
        try:
            write_timeline_csv(Path(args.timeline_csv_output), summaries)
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    if args.fail_on_sanity and sanity_failure_count(summaries) > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
