# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

*Add reusable patterns discovered during development here.*

## Codebase Patterns

- **DQ Scorer pattern**: Functions added to `kernel/dq-scorer.js` and exported via `module.exports`. Uses `parseFloat(value.toFixed(N))` for numeric precision. Existing code loads from `~/.claude/kernel/` paths via `process.env.HOME`.
- **Test pattern**: No test framework — plain Node.js scripts with manual assert helpers, `process.exit(1)` on failure. Tests live in `kernel/tests/`.
- **Append-only principle**: New features are additive — no modification to existing function signatures or behavior. New functions exported alongside existing ones.
- **SQLite from Node.js**: Use `execSync('sqlite3 ...')` for zero-dependency SQLite access. UNION queries are much faster than OR for indexed lookups on different columns. Add `busy_timeout=5000` for WAL-mode DBs.
- **Supermemory indexes**: `memory_links` has auto-index on `(from_id, to_id, link_type)` + custom `idx_memory_links_to_id` on `to_id`. Use UNION of two indexed queries instead of OR for sub-50ms on 12M rows.
- **Cross-runtime bridge pattern**: Python writes JSON to `~/.claude/kernel/hsrgs/irt-bridge.json`, Node.js reads it. Include `timestamp` for staleness check (60s max age) and `query_hash` for identity matching. No IPC/RPC needed.

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

## 2026-03-14 - meta-vengine-omv.2
- Implemented `computeSubgraphDensity(retrievedNodes, queryTopic)` in `kernel/dq-scorer.js`
- Implemented `computeSubgraphDensityFromLinks(retrievedNodes, graphLinks)` for in-memory/testing use
- Returns `{density, nodeCount, edgeCount, coverageRate}` or `null` when < 2 unique nodes
- Density = actual edges / possible edges (undirected), coverage via FTS5 topic match
- Added `idx_memory_links_to_id` index to supermemory.db for fast reverse lookups
- Uses `execSync('sqlite3 ...')` for zero-dependency SQLite access from Node.js
- Created `kernel/tests/test-subgraph-density.js` — 42/42 tests pass (incl. live DB integration)
- Live DB performance: 11ms on 12.15M links (well under 100ms requirement)
- Files changed: `kernel/dq-scorer.js`, `kernel/tests/test-subgraph-density.js` (new)
- **Learnings:**
  - OR queries on different indexed columns are slow in SQLite — use UNION of two indexed queries instead (500ms → 47ms)
  - supermemory.db uses WAL mode — need `busy_timeout` for DDL operations like CREATE INDEX
  - `memory_links` link_types: same_project (11.3M), same_date (808K), same_source (3.7K) — heavily project-correlated
  - Edge deduplication needed: links are directional but density should treat them as undirected (sort + join key)
---

## 2026-03-14 - meta-vengine-omv.3
- Implemented IRT difficulty cross-runtime bridge: Python HSRGS writes `irt-bridge.json`, Node.js DQ scorer reads it
- Added `_write_irt_bridge()` method to `HSRGSRouter` in `kernel/hsrgs.py` — writes after each routing decision
- Added `loadIRTBridge(queryHash?)` in `kernel/dq-scorer.js` — reads bridge with 60s staleness check and optional query hash matching
- Added `computeIRTModifier(irtDifficulty)` — high difficulty (>0.7) → +0.15 bias toward Opus, low (<0.3) → -0.15 bias toward Haiku, mid-range → 0.0
- Integrated `IRT_MOD` into `route()` function: applied after cognitive modifier, before DQ calculation
- IRT data logged in decision records (`irt: {difficulty, modifier, source}`)
- Graceful degradation: if bridge file missing, stale, or invalid → modifier defaults to 0.0
- Created `kernel/tests/test-irt-integration.js` — 35/35 tests pass (modifier math, bridge loading, integration routing)
- Files changed: `kernel/hsrgs.py`, `kernel/dq-scorer.js`, `kernel/tests/test-irt-integration.js` (new)
- **Learnings:**
  - Cross-runtime bridge via shared JSON file is simple and effective — no IPC/RPC needed
  - Staleness check (60s) prevents stale IRT data from affecting routing when HSRGS hasn't run recently
  - Query hash matching ensures the bridge data corresponds to the current query, not a previous one
  - `process.chdir()` doesn't affect `require()` resolution — must use absolute paths in test requires
---

