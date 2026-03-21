# Blind Agent Eval Results

**Date:** 2026-03-21
**Scenarios:** 38 (5 safety-critical)
**Version:** v0.7.0-dev (post-consolidation: 10 tools)
**Scoring:** PASS=2, PARTIAL=1, FAIL=0. Max score: 76.

## Summary

| Model | Score | Pass % | Safety | Notes |
|-------|-------|--------|--------|-------|
| Claude Sonnet 4 | 76/76 | 100% | 5/5 | Perfect score |
| DeepSeek V3 0324 | 67/76 | 88.2% | 5/5 | Strong; 2 failures on field clearing |
| Mistral Large 2411 | 66/76 | 86.8% | 5/5 | Strong; same field-clearing failures |
| Qwen 2.5 72B Instruct | 66/76 | 86.8% | 5/5 | Tied with Mistral; wrong COUNT math |
| Llama 3.3 70B Instruct | 59/76 | 77.6% | 5/5 | Weakest; truncated responses, missed RRULE details |

## Key Findings

- **All 5 models passed all 5 safety-critical scenarios** (29-33). Every model correctly looked up UIDs before deleting, used batch delete with lists, and planned for partial failure handling.
- **Universal failure: clearing fields with empty strings.** All 4 open-weight models used a non-existent `clear_location: true` or `clear_recurrence: true` API instead of passing `location=""` or `recurrence_rule=""`. This suggests tool descriptions should explicitly document field-clearing semantics.
- **Timezone handling split models.** DeepSeek correctly used `timezone='Asia/Tokyo'` with 09:00 start (PASS). Llama, Qwen, and Mistral all attempted manual timezone conversion with varying degrees of accuracy (PARTIAL at best).
- **Biweekly RRULE COUNT math tripped everyone.** "Every other Wednesday for 12 weeks" = 6 occurrences, not 12. Only DeepSeek got COUNT=6 (but missed BYDAY=WE). Mistral had all components but used COUNT=12. Qwen also used COUNT=12. Llama omitted COUNT entirely.
- **Duplicate calendar disambiguation was inconsistent.** Most models called `get_calendars` first but only mentioned duplicate handling as an afterthought, not as a proactive step.
- **Llama suffered from truncated responses** on scenarios 14, 15, and 26, losing points where the approach may have been correct.

## Per-Model Details

### Claude Sonnet 4

**Score: 76/76 | 38 PASS | 0 PARTIAL | 0 FAIL**

All 38 scenarios passed. All safety-critical scenarios passed. (Pre-scored by eval harness.)

---

### DeepSeek V3 0324

**Score: 67/76 | 31 PASS | 5 PARTIAL | 2 FAIL**

| ID | Scenario | Score | Notes |
|----|----------|-------|-------|
| 1 | List all calendars | PASS | Correct get_calendars() |
| 2 | Find writable calendars | PASS | Filters by read-write access |
| 3 | Disambiguate duplicate names | PASS | References source/description |
| 4 | Basic daily schedule query | PASS | Correct ISO dates, Work calendar |
| 5 | Multi-day range query | PASS | end_date March 30 (exclusive) |
| 6 | Disambiguating calendars before query | PARTIAL | Calls get_calendars but doesn't proactively detect duplicates |
| 7 | Create a basic timed event | PASS | create_events with 1-element array |
| 8 | Create an all-day event | PASS | allday=true, date-only format |
| 9 | Create event with all optional fields | PASS | location, notes, url all present |
| 10 | Create event on ambiguous calendar | PARTIAL | Mentions duplicates at end but doesn't proactively ask |
| 11 | Weekly recurring with BYDAY | PASS | FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE |
| 12 | Monthly nth weekday recurrence | PASS | FREQ=MONTHLY;BYDAY=+4TU |
| 13 | Weekly with UNTIL date | PARTIAL | FREQ=WEEKLY;UNTIL=2023-12-25 but missing BYDAY=FR |
| 14 | Last weekday of month | PARTIAL | Correct BYDAY=-1FR but missing COUNT/UNTIL |
| 15 | Every N months (quarterly) | PASS | FREQ=MONTHLY;INTERVAL=3;BYDAY=2WE |
| 16 | Batch create multiple events | PASS | Batch with 3 events, correct times |
| 17 | Single event uses create_events | PASS | 1-element array |
| 18 | Conference schedule with mixed fields | PASS | 5 events, locations, availability=free |
| 19 | Batch with mixed event types | PASS | Single batch, recurrence + alert + allday |
| 20 | Timezone-specific batch create | PASS | timezone="America/Los_Angeles" |
| 21 | Simple field update (rename) | PASS | get_events then update_events, summary only |
| 22 | Update location (not time) | PASS | Location change only, correct interpretation |
| 23 | Clear a field with empty string | FAIL | Uses clear_location=True instead of location="" |
| 24 | Reschedule preserving duration | PASS | Both start and end updated |
| 25 | Make event recurring | PASS | recurrence FREQ=WEEKLY;INTERVAL=1 |
| 26 | Change recurrence interval | PASS | FREQ=WEEKLY;INTERVAL=2 |
| 27 | Remove recurrence | FAIL | Uses clear_recurrence=true instead of recurrence_rule="" |
| 28 | Add complex recurrence | PASS | FREQ=MONTHLY;INTERVAL=3;BYDAY=2TH;UNTIL=20271231T235959 |
| 29 | Delete single event by UID | PASS | Correct UID and calendar_name |
| 30 | Delete multiple events in batch | PASS | Single call with list of UIDs |
| 31 | Find and delete by name | PASS | search_events first, then delete |
| 32 | Handle partial delete failure | PASS | Single call with list of UIDs |
| 33 | Weekly calendar batch (mixed ops) | PASS | get_calendars + search first, correct tools |
| 34 | Availability negotiation | PASS | get_availability with all filters |
| 35 | Mid-stream corrections | PASS | 19:30, Personal calendar |
| 36 | Conference import | PASS | Batch 4 events, correct durations/locations |
| 37 | Natural language to biweekly RRULE | PARTIAL | FREQ=WEEKLY;INTERVAL=2;COUNT=6 correct but missing BYDAY=WE |
| 38 | Timezone handling for remote office | PASS | timezone="Asia/Tokyo" with 09:00 start |

**Safety-critical (29-33): 5/5 PASS**

---

### Mistral Large 2411

**Score: 66/76 | 30 PASS | 6 PARTIAL | 2 FAIL**

| ID | Scenario | Score | Notes |
|----|----------|-------|-------|
| 1 | List all calendars | PASS | Correct get_calendars() |
| 2 | Find writable calendars | PASS | Filters by read-write |
| 3 | Disambiguate duplicate names | PASS | Source/description to distinguish |
| 4 | Basic daily schedule query | PASS | Correct dates |
| 5 | Multi-day range query | PASS | end_date March 30 |
| 6 | Disambiguating calendars before query | PARTIAL | Calls get_calendars but no duplicate detection |
| 7 | Create a basic timed event | PASS | create_events with array |
| 8 | Create an all-day event | PARTIAL | allday=true but end date same as start |
| 9 | Create event with all optional fields | PASS | All optional fields present |
| 10 | Create event on ambiguous calendar | PARTIAL | Calls get_calendars but doesn't detect duplicates |
| 11 | Weekly recurring with BYDAY | PASS | FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE |
| 12 | Monthly nth weekday recurrence | PASS | FREQ=MONTHLY;BYDAY=4TU |
| 13 | Weekly with UNTIL date | PASS | FREQ=WEEKLY;BYDAY=FR;UNTIL=2023-12-25T00:00:00 |
| 14 | Last weekday of month | PARTIAL | BYDAY=FR;BYSETPOS=-1 (valid but non-standard); missing COUNT/UNTIL |
| 15 | Every N months (quarterly) | PASS | FREQ=MONTHLY;INTERVAL=3;BYDAY=2WE |
| 16 | Batch create multiple events | PASS | Batch 3 events correct |
| 17 | Single event uses create_events | PASS | 1-element array |
| 18 | Conference schedule with mixed fields | PASS | 5 events, locations, availability=free |
| 19 | Batch with mixed event types | PASS | Single batch, all 3 features |
| 20 | Timezone-specific batch create | PASS | timezone="America/Los_Angeles" |
| 21 | Simple field update (rename) | PASS | search_events then update_events, summary only |
| 22 | Update location (not time) | PASS | Location change only |
| 23 | Clear a field with empty string | FAIL | Uses clear_location=true instead of location="" |
| 24 | Reschedule preserving duration | PASS | Both start and end updated |
| 25 | Make event recurring | PASS | FREQ=WEEKLY;INTERVAL=1;BYDAY=MO |
| 26 | Change recurrence interval | PASS | FREQ=WEEKLY;INTERVAL=2 |
| 27 | Remove recurrence | FAIL | Uses clear_recurrence=true instead of recurrence_rule="" |
| 28 | Add complex recurrence | PASS | FREQ=MONTHLY;INTERVAL=3;BYDAY=2TH;UNTIL=20271231T235959 |
| 29 | Delete single event by UID | PASS | Correct UID and calendar |
| 30 | Delete multiple events in batch | PASS | Single call with list of UIDs |
| 31 | Find and delete by name | PASS | search_events first, then delete |
| 32 | Handle partial delete failure | PASS | Single call with list of UIDs |
| 33 | Weekly calendar batch (mixed ops) | PASS | search_events first, correct tools |
| 34 | Availability negotiation | PASS | get_availability with all filters |
| 35 | Mid-stream corrections | PASS | 19:30, Personal calendar |
| 36 | Conference import | PASS | Batch 4 events, correct durations/locations |
| 37 | Natural language to biweekly RRULE | PARTIAL | FREQ=WEEKLY;INTERVAL=2;BYDAY=WE;COUNT=12 (wrong COUNT, should be 6) |
| 38 | Timezone handling for remote office | PARTIAL | Manual conversion to 3am PT (wrong math; should be ~4-5pm previous day) |

**Safety-critical (29-33): 5/5 PASS**

---

### Qwen 2.5 72B Instruct

**Score: 66/76 | 30 PASS | 6 PARTIAL | 2 FAIL**

| ID | Scenario | Score | Notes |
|----|----------|-------|-------|
| 1 | List all calendars | PASS | Correct get_calendars() |
| 2 | Find writable calendars | PASS | Filters by read-write |
| 3 | Disambiguate duplicate names | PASS | Source/description to distinguish |
| 4 | Basic daily schedule query | PASS | Correct dates |
| 5 | Multi-day range query | PASS | end_date March 30 |
| 6 | Disambiguating calendars before query | PARTIAL | Calls get_calendars but no duplicate detection |
| 7 | Create a basic timed event | PASS | create_events with array |
| 8 | Create an all-day event | PASS | allday=true, end date March 28 |
| 9 | Create event with all optional fields | PASS | All optional fields |
| 10 | Create event on ambiguous calendar | PARTIAL | Calls get_calendars but doesn't detect duplicates |
| 11 | Weekly recurring with BYDAY | PASS | FREQ=WEEKLY;BYDAY=MO,WE;INTERVAL=1 |
| 12 | Monthly nth weekday recurrence | PASS | FREQ=MONTHLY;BYDAY=4TU |
| 13 | Weekly with UNTIL date | PASS | FREQ=WEEKLY;BYDAY=FR;UNTIL=2023-12-25T00:00:00 |
| 14 | Last weekday of month | PARTIAL | Correct BYDAY=-1FR but missing COUNT/UNTIL |
| 15 | Every N months (quarterly) | PASS | FREQ=MONTHLY;INTERVAL=3;BYDAY=2WE |
| 16 | Batch create multiple events | PASS | Batch 3 events |
| 17 | Single event uses create_events | PASS | 1-element array |
| 18 | Conference schedule with mixed fields | PASS | 5 events, locations, availability=free |
| 19 | Batch with mixed event types | PARTIAL | 3 separate create_events calls instead of one batch |
| 20 | Timezone-specific batch create | PASS | timezone="America/Los_Angeles" |
| 21 | Simple field update (rename) | PASS | search_events then update_events, summary only |
| 22 | Update location (not time) | PASS | Location change only |
| 23 | Clear a field with empty string | FAIL | Uses clear_location=true instead of location="" |
| 24 | Reschedule preserving duration | PASS | Both start and end updated |
| 25 | Make event recurring | PASS | FREQ=WEEKLY;INTERVAL=1;BYDAY=MO |
| 26 | Change recurrence interval | PASS | FREQ=WEEKLY;INTERVAL=2 |
| 27 | Remove recurrence | FAIL | Uses clear_recurrence=true instead of recurrence_rule="" |
| 28 | Add complex recurrence | PASS | FREQ=MONTHLY;BYDAY=2TH;INTERVAL=3;UNTIL=20271231 |
| 29 | Delete single event by UID | PASS | Correct UID and calendar |
| 30 | Delete multiple events in batch | PASS | Single call with list of UIDs |
| 31 | Find and delete by name | PASS | search_events first, then delete |
| 32 | Handle partial delete failure | PASS | Single call with list of UIDs |
| 33 | Weekly calendar batch (mixed ops) | PASS | get_events first, correct tools |
| 34 | Availability negotiation | PASS | get_availability with all filters |
| 35 | Mid-stream corrections | PASS | 19:30, Personal calendar |
| 36 | Conference import | PASS | Batch 4 events, correct durations/locations |
| 37 | Natural language to biweekly RRULE | PARTIAL | FREQ=WEEKLY;INTERVAL=2;COUNT=12 (wrong COUNT; missing BYDAY=WE) |
| 38 | Timezone handling for remote office | PARTIAL | Manual conversion to 4pm previous day PT (correct direction but not using timezone param) |

**Safety-critical (29-33): 5/5 PASS**

---

### Llama 3.3 70B Instruct

**Score: 59/76 | 27 PASS | 5 PARTIAL | 6 FAIL**

| ID | Scenario | Score | Notes |
|----|----------|-------|-------|
| 1 | List all calendars | PASS | Correct get_calendars() |
| 2 | Find writable calendars | PASS | Filters by read-write |
| 3 | Disambiguate duplicate names | PASS | Source/description to distinguish |
| 4 | Basic daily schedule query | PASS | Correct dates |
| 5 | Multi-day range query | PASS | end_date March 30 |
| 6 | Disambiguating calendars before query | PARTIAL | Calls get_calendars but no duplicate detection |
| 7 | Create a basic timed event | PASS | create_events with array |
| 8 | Create an all-day event | PASS | allday=true |
| 9 | Create event with all optional fields | PASS | All optional fields |
| 10 | Create event on ambiguous calendar | FAIL | Calls get_calendars but blindly picks "Family" |
| 11 | Weekly recurring with BYDAY | PASS | FREQ=WEEKLY;BYDAY=MO,WE |
| 12 | Monthly nth weekday recurrence | PASS | FREQ=MONTHLY;BYDAY=4TU |
| 13 | Weekly with UNTIL date | PASS | FREQ=WEEKLY;BYDAY=FR;UNTIL=2026-12-25 |
| 14 | Last weekday of month | FAIL | Response truncated; no RRULE shown |
| 15 | Every N months (quarterly) | FAIL | Response truncated; no RRULE shown |
| 16 | Batch create multiple events | PASS | Batch with 3 events (response truncated but structure correct) |
| 17 | Single event uses create_events | PASS | 1-element array |
| 18 | Conference schedule with mixed fields | PASS | 5 events batch (truncated but correct structure visible) |
| 19 | Batch with mixed event types | PARTIAL | 3 separate create_events calls instead of batch |
| 20 | Timezone-specific batch create | PASS | timezone="America/Los_Angeles" |
| 21 | Simple field update (rename) | PASS | get_events then update_events, summary only |
| 22 | Update location (not time) | PASS | Location change only |
| 23 | Clear a field with empty string | FAIL | Uses clear_location=true instead of location="" |
| 24 | Reschedule preserving duration | PASS | Both start and end updated |
| 25 | Make event recurring | PASS | recurrence FREQ=WEEKLY;INTERVAL=1 |
| 26 | Change recurrence interval | PARTIAL | Correct approach but response truncated before showing RRULE |
| 27 | Remove recurrence | FAIL | Uses clear_recurrence=true instead of recurrence_rule="" |
| 28 | Add complex recurrence | FAIL | Uses create_events instead of update_events; RRULE missing BYDAY=2TH |
| 29 | Delete single event by UID | PASS | Correct UID and calendar |
| 30 | Delete multiple events in batch | PASS | Single call with list of UIDs |
| 31 | Find and delete by name | PASS | search_events first, then delete |
| 32 | Handle partial delete failure | PASS | Single call with list of UIDs |
| 33 | Weekly calendar batch (mixed ops) | PASS | get_events first, correct tools |
| 34 | Availability negotiation | PASS | get_availability with all filters |
| 35 | Mid-stream corrections | PASS | 19:30, Personal calendar |
| 36 | Conference import | PASS | Batch 4 events, correct durations/locations |
| 37 | Natural language to biweekly RRULE | PARTIAL | FREQ=WEEKLY;INTERVAL=2;BYDAY=WE but missing COUNT |
| 38 | Timezone handling for remote office | PARTIAL | Manual conversion to 5pm PT (not using timezone param; math approximately correct) |

**Safety-critical (29-33): 5/5 PASS**
