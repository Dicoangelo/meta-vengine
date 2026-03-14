# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

*Add reusable patterns discovered during development here.*

## Codebase Patterns

- **DQ Scorer pattern**: Functions added to `kernel/dq-scorer.js` and exported via `module.exports`. Uses `parseFloat(value.toFixed(N))` for numeric precision. Existing code loads from `~/.claude/kernel/` paths via `process.env.HOME`.
- **Test pattern**: No test framework — plain Node.js scripts with manual assert helpers, `process.exit(1)` on failure. Tests live in `kernel/tests/`.
- **Append-only principle**: New features are additive — no modification to existing function signatures or behavior. New functions exported alongside existing ones.

---

## 2026-03-14 - meta-vengine-omv.1
- Implemented `computeDistributionalFeatures(scores)` in `kernel/dq-scorer.js`
- Returns `{entropy, gini, skewness, sampleSize}` or `null` when `scores.length < 5`
- Shannon entropy: `-Σ(p * log(p))`, Gini: `1 - Σ(p_i²)`, Fisher-Pearson skewness with sample adjustment
- Created `kernel/tests/test-distributional-features.js` — 34/34 tests pass
- Files changed: `kernel/dq-scorer.js`, `kernel/tests/test-distributional-features.js` (new)
- **Learnings:**
  - `benchmark-100.js` doesn't exist yet in the repo or `~/.claude/scripts/` — skip that quality gate
  - DQ scorer uses `require('./complexity-analyzer')` and `require('~/.claude/config/pricing.js')` — tests need to run from repo root or kernel dir where these resolve
  - No test framework installed — vanilla Node.js assert pattern is the project convention
---

