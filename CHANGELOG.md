# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.1] - 2026-03-20

### Added

- `update_events` batch tool for updating multiple events in one operation (#100, #105)
- Smart availability filtering: `min_duration_minutes` and `working_hours_start`/`working_hours_end` on `get_availability` (#101, #107)
- Returns sections in all 11 tool docstrings for agent workflow chaining (#73, #116)
- 9 integration tests from real-world usage patterns: special characters, alerts, search, year-boundary queries, reschedule (#93, #115)
- Automated agent eval framework with 38 scenarios and OpenRouter runner (#114, #117)
- CONTRIBUTING.md (#64, #119)

### Changed

- Renamed `description` to `notes` across the API surface (#108, #109)
- Refactored `create_event` and `_format_event` to reduce cyclomatic complexity (#77, #113)

### Fixed

- `update_event` now returns the correct UID when rescheduling a recurring event occurrence (#63, #120)
- Swift helpers now exit with code 1 on errors, enabling proper subprocess error detection (#63, #120)
- `_parse_alert_minutes` raises descriptive error on invalid input (#63, #120)
- Batch `update_events` now rejects `occurrence_date` with clear error instead of silently ignoring it (#63, #120)
- `timezone` now tracked in `updated_fields` when passed to `update_event` (#63, #120)
- Fragile test calendar cleanup with `fresh_calendar` fixture (#106, #112)
- Documentation accuracy: updated test counts, removed stale "Planned" note (#65, #121)

### Removed

- Dead `_iso_to_applescript_date` method and its unit tests (#63, #120)

## [0.6.0] - 2026-03-18

### Added

- `create_events` batch tool for creating multiple events in one operation via `store.commit()` (#98)
- Event availability status (free/busy/tentative) on `get_events`, `create_event`, `update_event` (#96)
- Timezone parameter on `create_event` and `update_event` for cross-timezone scheduling (#97)
- Calendar `type` field in `get_calendars` output (caldav, subscription, birthday, local, exchange) (#95)
- Event `is_editable` and `is_organizer` fields in `get_events` for permission awareness (#95)
- `stdin_data` support in `run_swift_helper()` for piping structured data to Swift subprocesses (#98)
- Blind eval scenarios for batch create operations (#98)

## [0.5.1] - 2026-03-18

### Fixed

- RRULE parser: nth weekday support (`BYDAY=4MO`, `BYDAY=-1FR`) and `UNTIL` end date (#86)
- Date changes on recurring events: reschedule creates standalone event instead of deleting occurrence (#88)
- Delete specific occurrence of recurring event via `occurrence_date` parameter (#89)

### Added

- `recurrence_rule` parameter on `update_event` for adding, changing, or removing recurrence (#87)
- `occurrence_date` parameter on `delete_events` for targeting specific recurring occurrences (#89)
- Blind eval scenarios for recurrence operations (#86, #87)
- EventKit recurring event save behavior research documented in gap analysis (#85)
- 8 new integration tests for recurring event operations (TDD)

## [0.5.0] - 2026-03-17

### Added

- Read-only attendee information in `get_events` output: name, email, role, status (#68)
- Alert/reminder support: read in `get_events`, create/update via `alert_minutes` parameter (#69)
- `search_events` tool for text search across one or all calendars (#71)
- GitHub Releases for all tags, updated release workflow to create releases (#74)

## [0.4.0] - 2026-03-17

### Changed

- Migrated `get_calendars` from AppleScript to EventKit/Swift — 18x faster (#54)
- Migrated `create_event` from AppleScript to EventKit/Swift — 3x faster (#55)
- Migrated `delete_events` from AppleScript to EventKit/Swift — 6x single, 29x batch (#56)
- Migrated `update_event` from AppleScript to EventKit/Swift — 6x faster (#57)
- Removed `APPLESCRIPT_JSON_HELPERS` and AppleScript date conversion (no longer needed)
- Updated architecture: all event operations now use EventKit/Swift

### Added

- Single-occurrence modify for recurring events via `occurrence_date` + `span` parameters (#58)
- Series delete for recurring events via `span="future_events"` (#58)
- Batch commit support for delete operations via `EKEventStore.commit()` (#56)
- RRULE parsing in Swift for recurring event creation (#55)

## [0.3.1] - 2026-03-16

### Fixed

- Timezone mismatch: Swift helper now returns local time instead of UTC, fixing round-trip query failures (#48)

### Added

- Gap analysis research: attendees, alerts, text search, travel time, attachments, calendar properties (#52)
- Filed #49 (attendees), #50 (alerts), #51 (text search) for v0.5.0

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
