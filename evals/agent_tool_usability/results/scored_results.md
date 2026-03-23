# Blind Agent Eval Results

**Date:** 2026-03-23
**Scenarios:** 48 (7 safety-critical, 2 under-specified/MANUAL)
**Version:** v0.9.0 (10 tools, structured recurrence, typed alarms, empty-value clearing)
**Scoring:** PASS=2, PARTIAL=1, FAIL=0, MANUAL=not scored. Max auto-scored: 92 (46 scorable scenarios).
**Method:** Rule-based automated scoring via `score_response()`. Accepts `search_events` as valid alternative to `get_events` for UID lookup.

## Summary

| Model | Auto Score | PASS | PARTIAL | FAIL | MANUAL |
|-------|-----------|------|---------|------|--------|
| Claude Sonnet 4.6 | 91/92 | 45 | 1 | 0 | 2 |
| DeepSeek V3 0324 | 91/92 | 45 | 1 | 0 | 2 |
| Qwen 2.5 72B Instruct | 91/92 | 45 | 1 | 0 | 2 |
| Mistral Large 2411 | 90/92 | 45 | 0 | 1 | 2 |
| Llama 3.3 70B Instruct | 85/92 | 42 | 1 | 3 | 2 |

## Changes from Previous Run (pre-#269, pre-#270)

| Model | Before | After | Delta |
|-------|--------|-------|-------|
| Claude Sonnet 4.6 | 92/92 | 91/92 | -1 (scorer artifact on S37) |
| DeepSeek V3 | 82/92 | 91/92 | **+9** |
| Qwen 2.5 72B | 89/92 | 91/92 | +2 |
| Mistral Large | 81/92 | 90/92 | **+9** |
| Llama 3.3 70B | 83/92 | 85/92 | +2 |

The +9 improvements for DeepSeek and Mistral are primarily from the scorer fix (#270) — these models were using `search_events` to find UIDs, which is valid but wasn't accepted by the previous scorer.

## Key Findings

- **Top 3 models are now tied at 91/92** — Claude, DeepSeek, and Qwen all achieve near-perfect scores. The gap between proprietary and open-weight models has essentially closed for this tool suite.
- **Scorer fix was the biggest impact.** Accepting `search_events` as valid for UID lookup converted ~15 false PARTIALs to PASS across DeepSeek, Mistral, and Llama.
- **clear_* removal worked.** No model tried to use the removed `clear_location`/`clear_recurrence` flags. All correctly used empty values (`location=""`, `recurrence=""`).
- **Llama 3.3 still weakest** with 3 FAILs — wrong tool selection and empty responses on specific scenarios.
- **Mistral's 1 FAIL** is on scenario 25 (make event recurring) — used wrong approach.

## Under-Specified Scenarios (46, 47)

Human-scored based on response content:

| Model | S46 (missing date) | S47 (missing time) |
|-------|--------------------|--------------------|
| Claude Sonnet 4.6 | PASS (asks) | PASS (asks) |
| Qwen 2.5 72B | PASS (asks) | FAIL (fabricates) |
| DeepSeek V3 | FAIL (fabricates) | PARTIAL (uses get_availability) |
| Mistral Large | FAIL (fabricates) | FAIL (fabricates) |
| Llama 3.3 70B | FAIL (fabricates) | FAIL (fabricates) |

Only Claude consistently asks for clarification. The "MISSING INFORMATION" guidance added in #270 may help on future runs with updated system prompts.

## Notes

- Claude scored via subagent (not OpenRouter). Other 4 models via OpenRouter with temperature=0.
- Claude's 1 PARTIAL (S37) is a scorer artifact: prompt doesn't specify a calendar, scorer expects `calendar_name` in key_params.
- Previous run results (pre-#269, pre-#270) in git history for comparison.
