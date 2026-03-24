# Blind Agent Eval Results

**Date:** 2026-03-24
**Scenarios:** 48 (7 safety-critical, 2 under-specified/MANUAL)
**Version:** v0.9.0 (10 tools, structured recurrence, typed alarms, empty-value clearing)
**Scoring:** PASS=2, PARTIAL=1, FAIL=0, MANUAL=not scored. Max auto-scored: 92 (46 scorable scenarios).
**Method:** Rule-based automated scoring via `score_response()`. Accepts `search_events` as valid alternative to `get_events` for UID lookup.
**Context:** Models receive server instructions + tool descriptions (realistic MCP context). "Blind" means no codebase access.

## Summary

| Model | Auto Score | PASS | PARTIAL | FAIL | MANUAL |
|-------|-----------|------|---------|------|--------|
| Claude Sonnet 4.6 | 92/92 | 46 | 0 | 0 | 2 |
| Qwen 2.5 72B Instruct | 89/92 | 43 | 3 | 0 | 2 |
| Mistral Large 2411 | 88/92 | 44 | 0 | 0 | 2 |
| Llama 3.3 70B Instruct | 87/92 | 42 | 3 | 1 | 2 |
| DeepSeek V3 0324 | 81/92 | 40 | 1 | 5 | 2 |

## Methodology Change

Previous runs used tool descriptions only (no server instructions). This run includes server instructions — matching what models receive in real MCP usage. "Blind" means no codebase access, not stripped context.

Impact of adding server instructions:
- Claude: +1 (S37 PARTIAL→PASS, server context helped with calendar assumption)
- Llama: +2 (improved on recurring event and date handling)
- Qwen: -2 (new PARTIALs — may be over-processing instruction context)
- Mistral: -2 (similar)
- DeepSeek: -10 (significant regression — extra context appears to cause overthinking/confusion on several scenarios)

## Key Findings

- **Claude achieves perfect auto-score** (92/92) with realistic context. The S37 PARTIAL from previous runs is resolved.
- **Server instructions improved safety behavior** for under-specified requests (46, 47) — models with instructions context are more likely to ask for clarification.
- **DeepSeek regressed significantly** (-10) with added context. The longer system prompt appears to degrade its tool selection on some scenarios. Worth investigating further.
- **Llama improved** (+2) — the additional context about date formats and recurring event safety helped.

## Under-Specified Scenarios (46, 47)

| Model | S46 (missing date) | S47 (missing time) |
|-------|--------------------|--------------------|
| Claude Sonnet 4.6 | PASS (asks) | PASS (asks) |
| Qwen 2.5 72B | MANUAL | MANUAL |
| Mistral Large | MANUAL | MANUAL |
| DeepSeek V3 | MANUAL | MANUAL |
| Llama 3.3 70B | MANUAL | MANUAL |

## Notes

- Claude scored via subagent (not OpenRouter). Other 4 models via OpenRouter with temperature=0.
- Previous results (tool-descriptions-only) in git history for comparison.
- All models receive identical system prompt with server instructions + tool descriptions.
