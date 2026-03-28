# Post-Streamline Eval Review

**Date:** 2026-03-28
**Issues:** #300, #303
**Context:** Tool descriptions streamlined (#296), end_date made inclusive (#299)
**Eval Basis:** 5 models × 48 scenarios. Claude: 5 runs (240 evals). Open-weight: 1 run each (192 evals).

## Results Summary

| Model | Before | After | Delta |
|-------|--------|-------|-------|
| Claude Sonnet 4.6 | 460/460 (100%) | 436/480 (91%) | **-9%** |
| Mistral Large | 92/96 (96%) | 92/96 (96%) | 0 |
| Llama 3.3 70B | 88/96 (92%) | 88/96 (92%) | 0 |
| Qwen 2.5 72B | 86/96 (90%) | 88/96 (92%) | +2% |
| DeepSeek v3 | 85/96 (89%) | 87/96 (91%) | +2% |

Open-weight models: no regressions, slight improvements. Claude: 7 scenarios regressed.

## Claude Regression Analysis

| # | Scenario | Before | After | Root Cause |
|---|----------|--------|-------|------------|
| #4 | Basic daily schedule | 5/5 PASS | 1P 4PT | **Scorer bug** — model uses same date for start/end, now correct with inclusive semantics |
| #6 | Disambiguate calendars | 5/5 PASS | 0P 5PT | **Doc regression** — removed calendar uniqueness warning from get_calendars |
| #7 | Create basic event | 5/5 PASS | 4P 1PT | Noise (1/5) |
| #10 | Ambiguous calendar create | 5/5 PASS | 4P 1F | Noise (1/5) |
| #31 | Find and delete by name | 5/5 PASS | 2P 3PT | **Doc regression** — model uses search_events (valid) but scorer only accepts get_events→delete pattern |
| #33 | Weekly batch mixed ops | 5/5 PASS | 2P 3F | **Doc regression** — model skips initial get_events to find UIDs |
| #37 | Biweekly RRULE | 5/5 PASS | 2P 3PT | **Doc regression** — missing COUNT in RRULE, may need example |

### Breakdown by cause:
- **Scorer bugs (need rubric update):** #4, #5 rubric text, #31 (search_events is valid)
- **Documentation regressions (need doc fix):** #6, #33
- **Noise (1/5 flaky):** #7, #10
- **Unclear:** #37

## Scorer Issues Found

### S-1: Scenario #4 rubric doesn't account for inclusive end_date
Model correctly uses same date for start and end (e.g., `start_date="2025-07-14", end_date="2025-07-14"`), which is correct with inclusive semantics. Scorer marks PARTIAL ("date range too wide"). The regex scorer may be comparing date ranges rather than checking tool selection.

### S-2: Scenario #5 rubric text is stale
Text says "end_date is day AFTER the last requested day (March 30, exclusive end)" but the API now uses inclusive end_date. Models correctly pass March 29. Scorer happens to PASS due to regex match, but rubric text is misleading for LLM-based scoring.

### S-3: Scenario #31 scorer doesn't accept search_events
Model correctly uses `search_events(query="dentist")` → `delete_events` but scorer expects `get_events` → `delete_events`. Both patterns are valid.

## Documentation Gaps Found

### D-1: Calendar name uniqueness warning removed from get_calendars
**Severity: HIGH** — #6 regressed 5/5.

The get_calendars docstring previously warned about duplicate calendar names. After trimming, the warning is only in server instructions. Claude no longer calls get_calendars before querying a calendar by name.

**Additional context from user:** Calendar names aren't unique even within the same source. Two calendars can share name+source+color — only their events (or internal UIDs) distinguish them. The documentation should clarify this limitation rather than implying source always disambiguates.

**Fix:** Add back a brief note to get_calendars: "Calendar names may not be unique — even within the same source."

### D-2: No guidance on UID discovery before mutations
**Severity: MEDIUM** — #33 regressed 3/5.

The streamlined update_events and delete_events docs don't explicitly say "use get_events or search_events first to find UIDs." Models may guess UIDs or skip the discovery step.

**Fix:** Add directive cross-reference to update_events and delete_events: "Use get_events or search_events first to find UIDs."

### D-3: Calendar sharing/ownership not surfaced
**Severity: LOW** — Not tested in evals, but a gap.

EventKit's `EKCalendar` doesn't expose sharing or ownership info via public API. Agents can't determine who owns a calendar or who it's shared with. The `type` field (subscription, caldav) gives a hint but not the full picture.

**Status:** Platform limitation, document in gap analysis.

### D-4: RRULE examples may be insufficient
**Severity: LOW** — #37 regressed 3/5.

Models sometimes miss COUNT or INTERVAL in recurrence rules. The structured object format (frequency, interval, days_of_week, count, until) may need an explicit example of "every 2 weeks on Wednesday for 6 occurrences."

## Recommendations

1. **Fix scorers** — Update scenarios #4, #5, #31 rubrics for inclusive end_date and search_events as valid alternative
2. **Restore D-1** — Add calendar uniqueness note back to get_calendars
3. **Restore D-2** — Add UID discovery cross-reference to update_events and delete_events
4. **Monitor D-4** — Re-run after fixes to see if #37 stabilizes
5. **Document D-3** — Add sharing limitation to gap analysis
