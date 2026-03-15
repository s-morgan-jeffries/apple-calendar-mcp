"""Integration test fixtures — manages test calendar lifecycle.

Creates an MCP-Test-Calendar in Calendar.app before the test session
and removes it (with all events) after the session completes.
"""

import os
import subprocess

import pytest

TEST_CALENDAR = os.environ.get("CALENDAR_TEST_NAME", "MCP-Test-Calendar")


def _run_applescript(script: str) -> str:
    """Run an AppleScript and return stripped stdout."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"AppleScript failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _calendar_exists(name: str) -> bool:
    """Check if a calendar with the given name exists."""
    names = _run_applescript('tell application "Calendar" to name of every calendar')
    return name in [n.strip() for n in names.split(",")]


@pytest.fixture(scope="session", autouse=True)
def ensure_test_calendar():
    """Create the test calendar before tests, delete it after."""
    if os.environ.get("CALENDAR_TEST_MODE") != "true":
        yield
        return

    # Create calendar if it doesn't exist
    created = False
    if not _calendar_exists(TEST_CALENDAR):
        _run_applescript(
            f'tell application "Calendar" to make new calendar with properties {{name:"{TEST_CALENDAR}"}}'
        )
        created = True

    yield

    # Teardown: delete the calendar only if we created it
    if created and _calendar_exists(TEST_CALENDAR):
        _run_applescript(
            f'tell application "Calendar" to delete calendar "{TEST_CALENDAR}"'
        )
