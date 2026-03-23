# Blind Agent Eval Results

**Date:** 2026-03-23
**Scenarios:** 48 (7 safety-critical, 2 under-specified/MANUAL)
**Version:** v0.9.0 (10 tools, structured recurrence + typed alarms)
**Scoring:** PASS=2, PARTIAL=1, FAIL=0, MANUAL=not scored. Max auto-scored: 92 (46 scorable scenarios).
**Method:** Rule-based automated scoring via `score_response()` — checks tool-name presence and key-param mentions. No model self-scoring.

## Summary

| Model | Auto Score | PASS | PARTIAL | FAIL | MANUAL |
|-------|-----------|------|---------|------|--------|
| Claude Sonnet 4.6 | 92/92 | 46 | 0 | 0 | 2 |
| Qwen 2.5 72B Instruct | 89/92 | 43 | 3 | 0 | 2 |
| Llama 3.3 70B Instruct | 83/92 | 39 | 5 | 2 | 2 |
| DeepSeek V3 0324 | 82/92 | 36 | 10 | 0 | 2 |
| Mistral Large 2411 | 81/92 | 35 | 11 | 0 | 2 |

Note: MANUAL scenarios (46, 47 — under-specified requests) excluded from auto-scoring.
Some models scored MANUAL on other scenarios due to automated scorer limitations.

## Changes from v0.8.2 Eval

- **10 new scenarios** (39-48): get_conflicts, search_events, search-vs-get discrimination, create_calendar, delete_calendar (safety), recurring deletion safety, multi-calendar query, under-specified requests (x2), structured recurrence
- **Tool descriptions updated**: structured recurrence input, typed alarm objects, availability enum, recurrence_parsed return field
- **Automated scoring** replaces manual scoring — rule-based, no self-scoring bias

## Key Findings

- **Qwen 2.5 72B jumped to #2** (was #4 in v0.8.2). Strong improvement on new scenarios — correctly used structured recurrence, get_conflicts, and search_events.
- **All models passed new safety scenarios** (43, 44): delete_calendar and recurring-event single-occurrence deletion.
- **Structured recurrence (scenario 48):** All 5 models passed — both RRULE strings and structured objects accepted.
- **Under-specified requests (46, 47):** Models varied in whether they asked for clarification vs. assumed defaults. Scored as MANUAL — requires human judgment.
- **Llama 3.3 still has 2 FAILs** (scenario 17: used wrong tool; other from previous run). Weakest overall but improved on new scenarios.
- **DeepSeek V3 had most PARTIALs** (10) — typically correct tool but missed a parameter or used slightly wrong format.

## Notes

- Claude scored via subagent (not OpenRouter) to reduce cost. Other 4 models via OpenRouter with temperature=0.
- Previous results (v0.8.2, 38 scenarios) in git history for comparison.
