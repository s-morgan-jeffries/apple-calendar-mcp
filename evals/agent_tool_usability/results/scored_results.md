# Blind Agent Eval Results

**Date:** 2026-03-24
**Scenarios:** 48 (7 safety-critical, 2 under-specified/MANUAL)
**Version:** v0.9.0 (10 tools, structured recurrence, typed alarms, empty-value clearing)
**Runs:** 5 per scenario per model (1,200 total evaluations)
**Scoring:** PASS=2, PARTIAL=1, FAIL=0, MANUAL=not scored. Max per run: 92.
**Method:** Rule-based automated scoring. Accepts `search_events` as valid alternative to `get_events`.
**Context:** Models receive server instructions + tool descriptions (realistic MCP context).

## Summary (averaged across 5 runs)

| Model | Avg Score | PASS% | PARTIAL/run | FAIL/run | Variance |
|-------|-----------|-------|-------------|----------|----------|
| Claude Sonnet 4.6 | 92.0/92 | 100% | 0.0 | 0.0 | None |
| Mistral Large 2411 | 90.8/92 | 97.8% | 0.8 | 0.0 | Low |
| Qwen 2.5 72B Instruct | 88.2/92 | 92.6% | 3.0 | 0.4 | Moderate |
| Llama 3.3 70B Instruct | 87.8/92 | 94.8% | 0.6 | 1.8 | Moderate |
| DeepSeek V3 0324 | 81.6/92 | 87.0% | 1.6 | 4.4 | High |

## Aggregate Totals (5 runs × 48 scenarios = 240 per model)

| Model | Total Score | PASS | PARTIAL | FAIL | MANUAL |
|-------|-----------|------|---------|------|--------|
| Claude Sonnet 4.6 | 460/460 | 230 | 0 | 0 | 10 |
| Mistral Large 2411 | 454/460 | 225 | 4 | 0 | 11 |
| Qwen 2.5 72B | 441/460 | 213 | 15 | 2 | 10 |
| Llama 3.3 70B | 439/460 | 218 | 3 | 9 | 10 |
| DeepSeek V3 | 408/460 | 200 | 8 | 22 | 10 |

## Key Findings

- **Claude is perfectly deterministic** — 230/230 PASS across all 5 runs with zero variance. The tool descriptions and server instructions are unambiguous enough for consistent interpretation.
- **Mistral is the most reliable open-weight model** — 0 FAILs across 240 evaluations. Its 4 PARTIALs are minor parameter issues.
- **DeepSeek has the highest variance** — 22 FAILs across 5 runs on different scenarios each time. The longer system prompt (server instructions + tool descriptions) appears to cause inconsistent behavior. This was not observed with tool-descriptions-only prompts.
- **Llama's FAILs are non-deterministic** — fails on different scenarios across runs, suggesting output instability even at temperature=0.
- **Qwen is stable but has consistent PARTIALs** — 15 PARTIALs suggest parameter formatting issues rather than tool selection problems.

## Notes

- Claude scored via subagent (not OpenRouter). Other 4 models via OpenRouter with temperature=0.
- MANUAL scenarios (46, 47) excluded from scoring — 10 per model across 5 runs.
- Some MANUAL scores appeared on non-46/47 scenarios due to auto-scorer edge cases (e.g., empty API responses).
