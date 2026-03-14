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

### Iterative Bound-Normalize Pattern
When weights must sum to 1.0 AND respect min/max bounds, normalize-then-clamp in a loop (up to 20 iterations). Single-pass normalize→clamp→normalize can violate bounds on the final step.

### Coordinator Module Pattern — sys.path for sibling imports
Coordinator Python modules use `sys.path.insert(0, str(Path(__file__).parent.parent))` to import sibling modules. Tests use the same pattern to import from `coordinator/supermax.py`.

### Exponential Decay for Stability Scoring
`stability = exp(-decay_rate * max_delta)` maps a 0→∞ delta to a 0→1 stability score. Decay rate controls sensitivity (5.0 default: delta=0.1 → stability≈0.61, delta=0.3 → stability≈0.22). Good for any "confidence from change magnitude" pattern.

---

## 2026-03-14 - meta-vengine-omv.8
- **What was implemented:** SUPERMAX v2 — Free-MAD Trajectory Scoring (US-008). Full implementation from scratch.
- **Files changed:**
  - `coordinator/synthesizer.py` (new — ~340 lines, FreeMadSynthesizer, trajectory scoring, sycophancy detection, anonymization, JSONL logging)
  - `coordinator/supermax.py` (updated — added SupermaxV2 orchestrator class integrating PredictiveSpawner + FreeMadSynthesizer)
  - `coordinator/tests/test_free_mad.py` (new — 51 pytest tests, 12 test classes)
  - `config/supermax-v2.json` (updated — added freeMad config section)
- **Learnings:**
  - Coordinator tests use pytest (not vanilla assert pattern). The kernel JS tests use vanilla assert, but Python coordinator tests use `pytest.fixture` + `class Test*` pattern.
  - `sys.exit()` in test files causes pytest `INTERNALERROR`. Tests must use pytest-native assertions.
  - Free-MAD anti-sycophancy: agent labels stripped, replaced with opaque `Evaluator A/B/C`. The CONSENSAGENT paper (ACL 2025) showed that named agents defer to "authority" names.
  - Sycophancy detection needs both conditions: (1) all agents moved AND (2) Round 2 converged tighter than Round 1 spread. Missing either causes false positives.
  - `SupermaxV2` orchestrator uses lazy import (`from coordinator.synthesizer import ...` inside methods) to avoid circular dependencies.
---

## 2026-03-14 - meta-vengine-omv.7
- **What was implemented:** SUPERMAX v2 — Adaptive Agent Count (US-007). Full implementation from scratch.
- **Files changed:**
  - `coordinator/supermax.py` (new — ~250 lines, PredictiveSpawner, difficulty classification, agent selection, cost logging)
  - `coordinator/tests/test_adaptive_agent.py` (new — 39 tests, 7 test classes)
  - `coordinator/tests/__init__.py` (new — empty, package marker)
  - `config/supermax-v2.json` (new — learnable thresholds, agent priority, constraints)
- **Learnings:**
  - No existing `supermax.py` in coordinator — built fresh. The SUPERMAX council was previously only in benchmark scripts (non-existent in filesystem, referenced in docs only).
  - `benchmark-100.js` doesn't exist in the repo — it was a one-time artifact. DQ regression is verified by running the 4 kernel JS test files (153 tests total).
  - The coordinator already has executor, registry, conflict, distribution modules — supermax.py follows the same pattern (dataclasses, CLI entry point, JSON config).
  - Python 3.14 deprecates `datetime.utcnow()` — use `datetime.now(tz=datetime.timezone.utc)` instead.
---

## 2026-03-14 - meta-vengine-omv.6
- **What was implemented:** DQ Calibration — ECE Computation and Weight Adjustment (US-006). Full implementation from scratch.
- **Files changed:**
  - `kernel/dq-calibrator.py` (new — ~340 lines, ECE computation, dimension analysis, weight adjustment, proposal pipeline)
  - `kernel/tests/test_dq_calibrator.py` (new — 73 tests, 12 test sections)
  - `proposals/` directory created for calibration proposals
- **Learnings:**
  - DQ scores in `dq-scores.jsonl` use epoch seconds for `ts`, behavioral outcomes use ISO `started_at`. Matching requires converting ISO to epoch and using a 1-hour proximity window.
  - Weight bound enforcement after normalization is tricky — a single normalize→clamp pass can push renormalized values outside bounds. Solved with iterative converging loop.
  - The Godel engine `propose_mutation` interface in HSRGS expects mutation dicts with `type`, `param`, `old_value`, `new_value`. Calibrator writes proposals as JSON files instead (Godel engine integration point for coevo-apply).
  - Cognitive DQ weights file (`cognitive-dq-weights.json`) includes `dq_weights` nested under energy/mode context — must extract the weights sub-object.
  - ECE with perfectly calibrated scores gives exactly 0.0; overconfident (pred=0.9, actual=0.5) gives 0.4 — validates the formula.
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

