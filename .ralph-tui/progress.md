# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

*Add reusable patterns discovered during development here.*

### Test Pattern — Vanilla Node.js Test Runner
All kernel tests use a simple `assert()`/`assertClose()` pattern with pass/fail counters and `process.exit(failed > 0 ? 1 : 0)`. No test framework needed. Import directly from `../dq-scorer`.

### Feature Normalization — Inversion for "good = easy"
When composing signals: features where HIGH = EASY (entropy, gini, density) get inverted (`1 - value`) so that higher composite score always means harder. Direct features (IRT difficulty) stay as-is.

### Weight Normalization — Partial Feature Handling
When not all features are available, divide weighted sum by actual weight used (not total weight). This lets the system degrade gracefully from 4 features to 1.

### Python Test Pattern — importlib for Hyphenated Filenames
Python kernel scripts use hyphenated filenames (e.g., `behavioral-outcome.py`). Tests must use `importlib.import_module("behavioral-outcome")` since hyphens aren't valid in Python import statements.

### Tool Events ↔ Sessions Correlation
`tool_events` has no `session_id` column. Correlate with sessions using timestamp range matching: convert session ISO `started_at`/`ended_at` to unix timestamps, then query `tool_events WHERE timestamp >= start AND timestamp <= end`.

---

## 2026-03-14 - meta-vengine-omv.5
- **What was implemented:** Behavioral Outcome Signal — Composite Score Extractor (US-005). Full implementation from scratch.
- **Files changed:**
  - `kernel/behavioral-outcome.py` (new — ~230 lines, 5 component scorers + pipeline)
  - `kernel/tests/test_behavioral_outcome.py` (new — 30 tests, 7 test classes)
- **Learnings:**
  - `claude.db` sessions use ISO timestamps but `tool_events` uses unix timestamps — need conversion for correlation.
  - `activity_events.session_id` is inconsistent (paths, timestamps, project names) — not reliable for session-to-event mapping. Use timestamp range correlation instead.
  - Session outcomes in prod: success (2448), abandoned (1875), partial (479), completed (15), quick (7). The split between "success" and "completed" matters for scoring.
  - `command_events` stores aggregated commands (e.g., `bash` with `count=972`), not individual invocations. Model override detection looks for command strings containing model names.
  - Smoke test against real claude.db (5 sessions) confirmed correct output format and scoring ranges.
---

## 2026-03-14 - meta-vengine-omv.4
- **What was implemented:** Integration test suite for `computeGraphSignal()` (US-004). The core implementation was already complete from previous iterations (omv.3 log shows it was built alongside US-001/002/003).
- **Files changed:**
  - `kernel/tests/test-graph-signal.js` (new — 42 tests)
- **Learnings:**
  - US-004 was already implemented in `dq-scorer.js` lines 472-573 and integrated into `route()` at lines 706-719 during prior iterations. Only the dedicated test file was missing.
  - The A/B test logic uses `sessionId % 2` (odd/even) for deterministic traffic split — requires `featureCount >= 2` to activate graph signal.
  - All 119 tests across 4 test files pass with zero failures (US-001: 34, US-002: 42, US-003: 35, US-004: 42).
---

