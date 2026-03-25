# API Critic Review

**Date:** 2026-03-24
**Issue:** #280
**Eval Basis:** 5 models × 48 scenarios × 5 runs = 1,200 evaluations (v0.9.0)

## Executive Summary

The API performs well — Claude (100%), Mistral (0 FAILs), and Qwen/Llama (moderate) handle it cleanly. DeepSeek has 22 FAILs across 5 runs, but ~40% are scorer artifacts rather than genuine model failures. The actionable findings divide into: (1) scoring bugs inflating failure counts, (2) an API naming inconsistency, and (3) documentation density issues.

## Findings

### CR-1 — Scenario key_params use wrong field name for recurrence (HIGH)

Scenarios 25, 26, and 28 check for `recurrence_rule` in key_params, but the actual input parameter is `recurrence`. `recurrence_rule` is an output field from get_events. Mistral's correct responses using `recurrence` score PARTIAL instead of PASS.

**Evidence:** Mistral runs 1/4 on S25 — response contains `"recurrence": {"frequency": "weekly"}` (correct). Scored PARTIAL.

### CR-2 — Scorer doesn't handle plan-then-execute response style (HIGH)

DeepSeek frequently calls `get_calendars()` first, then describes the follow-up tool call. The scorer only detects tool names it sees as completed calls, not planned ones. ~8 of DeepSeek's 22 FAILs are false negatives from this pattern.

**Evidence:** DeepSeek S20 run 2 — includes full `create_events` JSON with `timezone: "America/Los_Angeles"` (exact PASS criterion) but scored FAIL.

### CR-3 — Input `recurrence` vs output `recurrence_rule` naming inconsistency (MEDIUM)

The input field is `recurrence` (create/update). The output field is `recurrence_rule` (get_events). A model that reads `recurrence_rule` from output and passes it as input to update_events will silently fail. Same issue: `update_events` docstring says `alerts (list of minutes)` while `create_events` documents the full typed format.

**Recommendation:** Rename output field to `recurrence` for consistency, or add explicit disambiguation note.

### CR-5 — Dense parameter descriptions hurt weaker models (MEDIUM)

The `create_events` `events` parameter is a single 150-word sentence covering 10+ fields. DeepSeek produces truncated responses (60-97 tokens) on complex scenarios, suggesting context overload.

**Evidence:** DeepSeek S36 run 2 (202 tokens, only get_calendars), S16 run 2 (65 tokens, only get_calendars), S8 run 3 (97 tokens, only get_calendars).

**Recommendation:** Restructure into per-field bullet lists matching the `get_events` Returns format.

### CR-6 — Server instructions contradict scoring expectations (MEDIUM)

Server instructions say "Use search_events when you know the event title." Scenario 23 ("Remove location from dentist appointment") expects get_events + update_events. DeepSeek correctly uses search_events("dentist") per instructions but scores FAIL.

**Evidence:** DeepSeek S23 runs 3/4 — follows server instructions exactly, scored FAIL.

### CR-8 — All-day end date inconsistency (HIGH, already filed as #279)

create_events uses exclusive end-date semantics while update_events and get_events use inclusive. Already being addressed.

## DeepSeek Score Reassessment

| Type | Count |
|------|-------|
| Genuine model failures | ~10-12 |
| Scorer artifacts (plan-then-execute) | ~8-10 |
| Server instruction contradictions | ~2 |

The "high variance" characterization is partially a scoring artifact. DeepSeek is more conservative (safety-positive), frequently inserting verification steps, which the scorer penalizes.

## Fix Categories

**Fix the scorer:** CR-1 (wrong key_params), CR-2 (plan-then-execute), CR-6 (search_events as intermediate step)

**Fix documentation:** CR-3 (recurrence naming note), CR-5 (parameter description structure)

**Fix the API:** CR-3 (optional: rename recurrence_rule → recurrence), CR-8 (#279, allday end dates)
