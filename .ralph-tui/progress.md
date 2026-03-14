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

