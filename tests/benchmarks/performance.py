"""Performance benchmarks for Apple Calendar MCP operations.

Measures real-world timing of each operation against Calendar.app.
Requires CALENDAR_TEST_MODE=true for write operations.

Usage:
    python tests/benchmarks/performance.py [--read-calendar NAME] [--output FILE]

Options:
    --read-calendar NAME   Calendar to use for read benchmarks (default: MCP-Test-Calendar)
    --output FILE          Write JSON results to FILE for historical comparison
"""

import argparse
import json
import math
import subprocess
import sys
import time
from datetime import date, datetime, timezone

from apple_calendar_mcp.calendar_connector import CalendarConnector
from tests.helpers.calendar_setup import create_test_calendar

# Collect results for JSON output
_results = []


def benchmark(fn, label, iterations=1, section=""):
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
        std = math.sqrt(sum((t - mean) ** 2 for t in times) / len(times))
        print(f"  {label}: {mean:.3f}s (mean of {iterations}, std={std:.3f}s, min={min(times):.3f}s, max={max(times):.3f}s)")
    else:
        std = 0.0
        print(f"  {label}: {mean:.3f}s")

    _results.append({
        "section": section,
        "label": label,
        "mean": round(mean, 4),
        "min": round(min(times), 4),
        "max": round(max(times), 4),
        "std": round(std, 4),
        "iterations": iterations,
    })
    return result


def run_benchmarks(read_calendar: str, test_calendar: str):
    """Run all benchmarks and print results."""
    connector = CalendarConnector(enable_safety_checks=False)

    # Dynamic year constants for date ranges
    this_year = date.today().year
    read_year = str(this_year)
    write_year = str(this_year + 1)
    past_year = str(this_year - 6)
    future_year = str(this_year + 4)

    # Ensure test calendar exists
    create_test_calendar(test_calendar)

    print("=" * 60)
    print("Apple Calendar MCP — Performance Benchmarks")
    print("=" * 60)

    # Warm-up: trigger Swift compilation caching before timed runs
    print("\n[warm-up]")
    connector.get_calendars()
    print("  Swift helper compiled and cached")

    # --- get_calendars ---
    print("\n[get_calendars]")
    calendars = benchmark(connector.get_calendars, "List all calendars", iterations=3, section="get_calendars")
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
        lambda: connector.get_events(read_calendar, f"{read_year}-03-01", f"{read_year}-03-31"),
        "1-month range",
        iterations=3,
        section="get_events",
    )

    benchmark(
        lambda: connector.get_events(read_calendar, f"{read_year}-01-01", f"{read_year}-12-31"),
        "1-year range",
        iterations=3,
        section="get_events",
    )

    events = benchmark(
        lambda: connector.get_events(read_calendar, f"{past_year}-01-01", f"{future_year}-12-31"),
        "10-year range",
        iterations=3,
        section="get_events",
    )
    print(f"  Events in 10-year range: {len(events)}")

    # --- get_availability ---
    print(f"\n[get_availability] (calendar: {read_calendar})")

    benchmark(
        lambda: connector.get_availability([read_calendar], f"{read_year}-03-01", f"{read_year}-03-31"),
        "1-month range",
        iterations=3,
        section="get_availability",
    )

    benchmark(
        lambda: connector.get_availability([read_calendar], f"{read_year}-01-01", f"{read_year}-12-31"),
        "1-year range",
        iterations=3,
        section="get_availability",
    )

    # --- get_conflicts ---
    print(f"\n[get_conflicts] (calendar: {read_calendar})")

    benchmark(
        lambda: connector.get_conflicts([read_calendar], f"{read_year}-03-01", f"{read_year}-03-31"),
        "1-month range",
        iterations=3,
        section="get_conflicts",
    )

    benchmark(
        lambda: connector.get_conflicts([read_calendar], f"{read_year}-01-01", f"{read_year}-12-31"),
        "1-year range",
        iterations=3,
        section="get_conflicts",
    )

    # --- search_events ---
    print(f"\n[search_events] (calendar: {read_calendar})")

    benchmark(
        lambda: connector.search_events("Meeting", calendar_names=[read_calendar],
                                         start_date=f"{read_year}-03-01", end_date=f"{read_year}-03-31"),
        "1-month range",
        iterations=3,
        section="search_events",
    )

    benchmark(
        lambda: connector.search_events("Meeting", calendar_names=[read_calendar],
                                         start_date=f"{read_year}-01-01", end_date=f"{read_year}-12-31"),
        "1-year range",
        iterations=3,
        section="search_events",
    )

    # --- Write operations (test calendar only) ---
    print(f"\n[create_events] (calendar: {test_calendar})")

    created_uids = []

    def create_and_track():
        result = connector.create_events(
            calendar_name=test_calendar,
            events=[{"summary": "Benchmark Event", "start_date": f"{write_year}-06-15T10:00:00", "end_date": f"{write_year}-06-15T11:00:00"}],
        )
        uid = result["created"][0]["uid"]
        created_uids.append(uid)
        return uid

    benchmark(create_and_track, "Create single event", iterations=3, section="create_events")

    # Batch create scaling
    def batch_create(n):
        events = [
            {"summary": f"Batch {n} Event {i}", "start_date": f"{write_year}-07-15T10:00:00", "end_date": f"{write_year}-07-15T11:00:00"}
            for i in range(n)
        ]
        result = connector.create_events(calendar_name=test_calendar, events=events)
        for c in result["created"]:
            created_uids.append(c["uid"])
        return result

    benchmark(lambda: batch_create(5), f"Batch create 5 events", iterations=3, section="create_events")
    benchmark(lambda: batch_create(10), f"Batch create 10 events", iterations=3, section="create_events")

    # --- update_events ---
    print(f"\n[update_events] (calendar: {test_calendar})")

    if created_uids:
        uid = created_uids[0]
        benchmark(
            lambda: connector.update_events(test_calendar, [{"uid": uid, "summary": "Updated Benchmark"}]),
            "Update summary (single event via batch)",
            iterations=3,
            section="update_events",
        )

        benchmark(
            lambda: connector.update_events(test_calendar, [{"uid": uid, "location": "Room A"}]),
            "Update location",
            iterations=3,
            section="update_events",
        )

    # --- delete_events ---
    print(f"\n[delete_events] (calendar: {test_calendar})")

    # Single delete (3 iterations, create fresh event each time)
    def create_then_delete():
        result = connector.create_events(
            calendar_name=test_calendar,
            events=[{"summary": "Delete Bench", "start_date": f"{write_year}-08-01T10:00:00", "end_date": f"{write_year}-08-01T11:00:00"}],
        )
        uid = result["created"][0]["uid"]
        return connector.delete_events(test_calendar, uid)

    benchmark(create_then_delete, "Create + delete single event", iterations=3, section="delete_events")

    # Batch delete (3 iterations, create batch each time)
    def create_batch_then_delete(n):
        events = [
            {"summary": f"DelBatch {i}", "start_date": f"{write_year}-08-15T10:00:00", "end_date": f"{write_year}-08-15T11:00:00"}
            for i in range(n)
        ]
        result = connector.create_events(calendar_name=test_calendar, events=events)
        uids = [c["uid"] for c in result["created"]]
        return connector.delete_events(test_calendar, uids)

    benchmark(lambda: create_batch_then_delete(5), "Create + batch delete 5 events", iterations=3, section="delete_events")

    # Clean up remaining tracked UIDs
    if created_uids:
        try:
            connector.delete_events(test_calendar, created_uids)
        except Exception:
            pass
        created_uids.clear()

    print("\n" + "=" * 60)
    print("Benchmarks complete.")
    print("=" * 60)


def _get_git_sha():
    """Get current git SHA, or 'unknown' if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


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
    parser.add_argument(
        "--output",
        default=None,
        help="Write JSON results to this file for historical comparison",
    )
    args = parser.parse_args()
    run_benchmarks(args.read_calendar, args.test_calendar)

    if args.output:
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "git_sha": _get_git_sha(),
            "results": _results,
        }
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nResults written to {args.output}")


if __name__ == "__main__":
    main()
