"""Performance benchmarks for Apple Calendar MCP operations.

Measures real-world timing of each operation against Calendar.app.
Requires CALENDAR_TEST_MODE=true for write operations.

Usage:
    python tests/benchmarks/performance.py [--read-calendar NAME]

Options:
    --read-calendar NAME   Calendar to use for read benchmarks (default: MCP-Test-Calendar)
"""

import argparse
import sys
import time

from apple_calendar_mcp.calendar_connector import CalendarConnector
from tests.helpers.calendar_setup import create_test_calendar


def benchmark(fn, label, iterations=1):
    """Run a function and report timing."""
    times = []
    result = None
    for _ in range(iterations):
        start = time.perf_counter()
        result = fn()
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    mean = sum(times) / len(times)
    if iterations > 1:
        print(f"  {label}: {mean:.3f}s (mean of {iterations}, min={min(times):.3f}s, max={max(times):.3f}s)")
    else:
        print(f"  {label}: {mean:.3f}s")
    return result


def run_benchmarks(read_calendar: str, test_calendar: str):
    """Run all benchmarks and print results."""
    connector = CalendarConnector(enable_safety_checks=False)

    # Ensure test calendar exists
    create_test_calendar(test_calendar)

    print("=" * 60)
    print("Apple Calendar MCP — Performance Benchmarks")
    print("=" * 60)

    # --- get_calendars ---
    print("\n[get_calendars]")
    calendars = benchmark(connector.get_calendars, "List all calendars", iterations=3)
    cal_names = [c["name"] for c in calendars]
    print(f"  Found {len(calendars)} calendars")

    if read_calendar not in cal_names:
        print(f"\n  WARNING: Calendar '{read_calendar}' not found.")
        print(f"  Available: {', '.join(cal_names)}")
        print(f"  Using '{test_calendar}' for all benchmarks.")
        read_calendar = test_calendar

    # --- get_events (read calendar, various ranges) ---
    print(f"\n[get_events] (calendar: {read_calendar})")

    benchmark(
        lambda: connector.get_events(read_calendar, "2026-03-01", "2026-03-31"),
        "1-month range",
        iterations=3,
    )

    benchmark(
        lambda: connector.get_events(read_calendar, "2026-01-01", "2026-12-31"),
        "1-year range",
        iterations=3,
    )

    events = benchmark(
        lambda: connector.get_events(read_calendar, "2020-01-01", "2030-12-31"),
        "10-year range",
        iterations=3,
    )
    print(f"  Events in 10-year range: {len(events)}")

    # --- get_availability ---
    print(f"\n[get_availability] (calendar: {read_calendar})")

    benchmark(
        lambda: connector.get_availability([read_calendar], "2026-03-01", "2026-03-31"),
        "1-month range",
        iterations=3,
    )

    benchmark(
        lambda: connector.get_availability([read_calendar], "2026-01-01", "2026-12-31"),
        "1-year range",
        iterations=3,
    )

    # --- get_conflicts ---
    print(f"\n[get_conflicts] (calendar: {read_calendar})")

    benchmark(
        lambda: connector.get_conflicts([read_calendar], "2026-03-01", "2026-03-31"),
        "1-month range",
        iterations=3,
    )

    benchmark(
        lambda: connector.get_conflicts([read_calendar], "2026-01-01", "2026-12-31"),
        "1-year range",
        iterations=3,
    )

    # --- search_events ---
    print(f"\n[search_events] (calendar: {read_calendar})")

    benchmark(
        lambda: connector.search_events("Meeting", calendar_names=[read_calendar],
                                         start_date="2026-03-01", end_date="2026-03-31"),
        "1-month range",
        iterations=3,
    )

    benchmark(
        lambda: connector.search_events("Meeting", calendar_names=[read_calendar],
                                         start_date="2026-01-01", end_date="2026-12-31"),
        "1-year range",
        iterations=3,
    )

    # --- Write operations (test calendar only) ---
    print(f"\n[create_events] (calendar: {test_calendar})")

    created_uids = []

    def create_and_track():
        result = connector.create_events(
            calendar_name=test_calendar,
            events=[{"summary": "Benchmark Event", "start_date": "2027-06-15T10:00:00", "end_date": "2027-06-15T11:00:00"}],
        )
        uid = result["created"][0]["uid"]
        created_uids.append(uid)
        return uid

    benchmark(create_and_track, "Create single event", iterations=3)

    # --- update_events ---
    print(f"\n[update_events] (calendar: {test_calendar})")

    if created_uids:
        uid = created_uids[0]
        benchmark(
            lambda: connector.update_events(test_calendar, [{"uid": uid, "summary": "Updated Benchmark"}]),
            "Update summary (single event via batch)",
            iterations=3,
        )

        benchmark(
            lambda: connector.update_events(test_calendar, [{"uid": uid, "location": "Room A"}]),
            "Update location",
            iterations=3,
        )

    # --- delete_events ---
    print(f"\n[delete_events] (calendar: {test_calendar})")

    if len(created_uids) >= 1:
        uid = created_uids.pop()
        benchmark(
            lambda: connector.delete_events(test_calendar, uid),
            "Delete single event",
        )

    # Batch delete remaining
    if created_uids:
        benchmark(
            lambda: connector.delete_events(test_calendar, created_uids),
            f"Batch delete {len(created_uids)} events",
        )
        created_uids.clear()

    # Batch delete benchmark (create 5, delete all)
    batch_events = [
        {"summary": f"Batch Bench {i}", "start_date": "2027-07-01T10:00:00", "end_date": "2027-07-01T11:00:00"}
        for i in range(5)
    ]
    batch_result = connector.create_events(calendar_name=test_calendar, events=batch_events)
    batch_uids = [c["uid"] for c in batch_result["created"]]

    benchmark(
        lambda: connector.delete_events(test_calendar, batch_uids),
        "Batch delete 5 events",
    )

    print("\n" + "=" * 60)
    print("Benchmarks complete.")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Performance benchmarks for Apple Calendar MCP")
    parser.add_argument(
        "--read-calendar",
        default="MCP-Test-Calendar",
        help="Calendar for read benchmarks (default: MCP-Test-Calendar)",
    )
    parser.add_argument(
        "--test-calendar",
        default="MCP-Test-Calendar",
        help="Calendar for write benchmarks (default: MCP-Test-Calendar)",
    )
    args = parser.parse_args()
    run_benchmarks(args.read_calendar, args.test_calendar)


if __name__ == "__main__":
    main()
