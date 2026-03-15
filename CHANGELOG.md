# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-15

### Added

- `get_calendars` tool — list all available calendars (#11)
- `create_event` tool with calendar safety guards (#11)
- `get_events` tool using EventKit Swift helper for fast reads (#13)
- `update_event` tool with UID fix and date-ordering handling (#15)
- `delete_events` tool with single and batch support (#17)
- Swift/EventKit helper for sub-second event queries on large calendars (#13)
- Calendar safety system requiring `CALENDAR_TEST_MODE` and `CALENDAR_TEST_NAME` for destructive operations
- CI workflow with unit tests and validation checks (#8)
- Release workflow skill and tag script (#19)
- Reproducible dependency installs via `uv.lock` (#16)
- Integration test conftest with automatic test calendar setup/teardown
