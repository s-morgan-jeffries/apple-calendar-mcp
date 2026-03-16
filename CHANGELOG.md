# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-03-16

### Added

- Recurring event support: read recurrence fields from `get_events`, create recurring events with RRULE syntax (#43)
- `create_calendar` and `delete_calendar` tools (#45)
- Comprehensive integration test suite: round-trip, workflow, timezone, error handling tests (#46)
- Production config unit tests verifying safety check behavior (#46)
- Recurring events research documented in gap analysis (#34)

### Fixed

- Safety checks now only enabled during tests (`CALENDAR_TEST_MODE=true`), not in production (#36)
- EventKit store refresh (`refreshSourcesIfNecessary`) for recently-created events (#36)

## [0.2.0] - 2026-03-16

### Added

- `get_availability` tool with multi-calendar support for free/busy lookup (#28)
- Performance benchmark script and module (`scripts/benchmark_performance.sh`) (#29)
- Performance benchmarks documented in gap analysis with timing data (#29)

### Fixed

- UTC-to-local timezone conversion for EventKit dates in availability calculations (#28)

## [0.1.1] - 2026-03-16

### Added

- Project README with setup, usage, tools reference, and architecture overview (#26)
- Bug report issue template (#23)
- Feature request issue template (#24)
- Reusable test calendar setup/teardown module and standalone scripts (#25)

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
