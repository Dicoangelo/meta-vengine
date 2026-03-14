# PRD: Cognitive Constraint Qualification Engine — Sprint 1

## Overview

Transform three isolated SQLite databases (claude.db telemetry, antigravity.db research, supermemory.db memory) into a reactive intelligence layer where knowledge qualifies routing decisions and routing outcomes refine knowledge — automatically, with every interaction.

This sprint builds the substrate for an active inference routing engine (Sprints 2-4) while delivering immediate value: better routing accuracy, lower cost, faster consensus, and a compounding knowledge graph.

**Research basis:** 30+ papers across 2 research rounds, evaluated by 3-perspective SUPERMAX council (Principal Engineer 0.35, Security Architect 0.30, Product Strategist 0.35). All assumptions stress-tested via Round 2 challenge agents.

## Goals

- Replace single-signal routing (skewness) with multi-feature graph signal (+12.3% accuracy per GraphRouter ICLR 2025)
- Calibrate DQ scores against behavioral outcomes instead of unreliable ACE self-assessment
- Upgrade SUPERMAX from fixed 3-agent averaging to adaptive agent count with Free-MAD trajectory scoring (16% accuracy gain, 50% cost reduction)
- Close the bidirectional loop: routing outcomes update graph confidence, every interaction enriches the graph
- Architect each component as a future Optimas Local Reward Function (learnable weights, not hardcoded)

## Quality Gates

These commands must pass for every user story:

- `python3 -m py_compile <file>` — Python syntax check
- `node --check <file>` — Node.js syntax check
- `pytest <test_file> -v` — Unit/integration tests for the story
- End-to-end data flow verification: producer writes → consumer reads → decision changes

For stories touching the DQ scorer or SUPERMAX:
- `node scripts/benchmark-100.js compare` — DQ benchmark regression check (8/8 must still pass)

## User Stories

### US-001: Multi-Feature Graph Signal — Entropy + Gini Calculator
**Description:** As the DQ scoring system, I want to compute entropy and Gini coefficient from supermemory retrieval score distributions so that routing decisions use calibrated distributional features instead of a single skewness metric.

**Acceptance Criteria:**
- [ ] New function `computeDistributionalFeatures(scores)` in `kernel/dq-scorer.js` returns `{entropy, gini, skewness, sampleSize}`
- [ ] Entropy computed as Shannon entropy: `-Σ(p * log(p))` over normalized score distribution
- [ ] Gini computed as: `1 - Σ(p_i²)` over normalized scores
- [ ] Returns `null` when `scores.length < 5` (minimum sample threshold per Security Architect)
- [ ] Unit tests verify correct computation against known distributions (uniform → max entropy, single-peak → low entropy)
- [ ] Existing DQ scoring behavior unchanged when no retrieval scores available (graceful degradation)

**Files:** `kernel/dq-scorer.js`, `kernel/tests/test-distributional-features.js`

---

### US-002: Multi-Feature Graph Signal — Subgraph Density Feature
**Description:** As the DQ scoring system, I want to measure the density of the retrieved knowledge subgraph so that sparse subgraphs (which cause 30% of KG-RAG errors) trigger routing to stronger models.

**Acceptance Criteria:**
- [ ] New function `computeSubgraphDensity(retrievedNodes, graphLinks)` returns `{density, nodeCount, edgeCount, coverageRate}`
- [ ] Density = actual edges / possible edges among retrieved nodes
- [ ] Coverage rate = retrieved nodes / estimated relevant nodes (using query-topic match count from supermemory)
- [ ] Reads from `supermemory.db` memory_links table (12.15M links)
- [ ] Query completes within 100ms using indexed lookups (not full table scan)
- [ ] Unit tests verify: fully-connected subgraph → density 1.0, isolated nodes → density 0.0

**Files:** `kernel/dq-scorer.js`, `~/.claude/memory/supermemory.db`

---

### US-003: Multi-Feature Graph Signal — IRT Difficulty Integration
**Description:** As the DQ scoring system, I want to consume the IRT difficulty estimate already computed by HSRGS so that historical query difficulty informs routing without redundant computation.

**Acceptance Criteria:**
- [ ] DQ scorer reads IRT difficulty from HSRGS `predict()` output (already exists in `kernel/hsrgs.py` IRT predictor)
- [ ] IRT difficulty integrated as `IRT_MOD` in the modifier stacking pattern at `dq-scorer.js` lines 131-144
- [ ] High IRT difficulty (> 0.7) biases toward Opus; low (< 0.3) biases toward Haiku
- [ ] Cross-runtime bridge: Python HSRGS IRT output written to shared JSON file or SQLite, read by Node.js DQ scorer
- [ ] Fallback: if IRT unavailable, modifier defaults to 0.0 (no effect)
- [ ] Integration test: query with known high-difficulty topic routes to more capable model

**Files:** `kernel/dq-scorer.js`, `kernel/hsrgs.py`

---

### US-004: Multi-Feature Signal Composition
**Description:** As the DQ scoring system, I want to combine entropy, Gini, subgraph density, and IRT difficulty into a single composite routing signal so that the DQ scorer uses all available graph intelligence.

**Acceptance Criteria:**
- [ ] New `computeGraphSignal()` function composes all 4 features into a single `graphComplexity` score (0.0-1.0)
- [ ] Initial weights: entropy 0.30, Gini 0.25, subgraph density 0.25, IRT difficulty 0.20 (stored in `config/graph-signal-weights.json`, NOT hardcoded)
- [ ] Weights file is the ONLY authority — designed as a future Optimas Local Reward Function (learnable)
- [ ] `graphComplexity` replaces the current keyword-based complexity score in DQ routing thresholds
- [ ] A/B test logging: both old (keyword) and new (graph) complexity scores logged to `dq-scores.jsonl` for comparison
- [ ] Integration test: known-simple query (high entropy, dense subgraph) → lower complexity; known-hard query (low entropy, sparse) → higher complexity

**Files:** `kernel/dq-scorer.js`, `config/graph-signal-weights.json`

---

### US-005: Behavioral Outcome Signal — Composite Score Extractor
**Description:** As the calibration system, I want to extract behavioral outcome signals from existing telemetry so that DQ calibration uses non-circular ground truth instead of unreliable ACE self-assessment.

**Acceptance Criteria:**
- [ ] New script `kernel/behavioral-outcome.py` computes composite outcome score per session from:
  - Session completion (not abandoned): weight 0.30
  - Tool success rate (from tool_events): weight 0.25
  - Efficiency ratio (messages / DQ complexity): weight 0.20
  - No model override by user: weight 0.15
  - No follow-up session on same topic within 24h: weight 0.10
- [ ] Reads from `claude.db` tables: sessions, tool_events, activity_events, command_events
- [ ] Outputs behavioral score (0.0-1.0) per session to `behavioral-outcomes.jsonl` (append-only)
- [ ] Backfill mode: can process all historical sessions (4,806 sessions)
- [ ] ACE quality score preserved as a separate weak signal, NOT used as ground truth
- [ ] Unit tests with mock session data verify each component scoring

**Files:** `kernel/behavioral-outcome.py`, `~/.claude/data/claude.db`

---

### US-006: DQ Calibration — ECE Computation and Weight Adjustment
**Description:** As the routing system, I want to compute Expected Calibration Error between DQ predictions and behavioral outcomes so that DQ dimension weights are adjusted to minimize prediction error.

**Acceptance Criteria:**
- [ ] New script `kernel/dq-calibrator.py` computes ECE by binning DQ scores into 10 deciles and comparing predicted vs actual behavioral outcome
- [ ] Outputs calibration report: per-dimension ECE (validity, specificity, correctness), overall ECE, recommended weight adjustments
- [ ] Weight adjustments bounded: min 0.1, max 0.6 per dimension (Security Architect requirement)
- [ ] Minimum n >= 50 outcomes per dimension before any adjustment (statistical threshold)
- [ ] First calibration cycle writes proposal to `proposals/calibration-001.json` requiring human `coevo-apply` approval
- [ ] Subsequent cycles with bounded adjustments (delta < 0.05 per dimension) can auto-apply
- [ ] Calibration output is a PROPOSAL to the Gödel engine mutation pipeline (single weight authority, no parallel write path)
- [ ] Unit tests verify: perfectly calibrated scores → ECE ≈ 0, systematically overconfident scores → ECE > 0.1

**Files:** `kernel/dq-calibrator.py`, `kernel/hsrgs.py`

---

### US-007: SUPERMAX v2 — Adaptive Agent Count
**Description:** As the SUPERMAX consensus system, I want to dynamically select agent count (1-5) based on query difficulty so that simple queries use 1 agent and complex queries get full council evaluation.

**Acceptance Criteria:**
- [ ] Extend `PredictiveSpawner` in `coordinator/supermax.py` with difficulty-aware agent count
- [ ] Agent count mapping: trivial (< 0.25 graphComplexity) → 1 agent, simple (0.25-0.45) → 2, moderate (0.45-0.65) → 3, complex (0.65-0.85) → 4, expert (> 0.85) → 5
- [ ] Thresholds stored in `config/supermax-v2.json` (learnable, not hardcoded)
- [ ] Consumes `graphComplexity` from US-004 as the difficulty signal
- [ ] Agents selected in priority order: Principal Engineer first, then Security Architect, Product Strategist, Contrarian (from ACE), Arbiter (new)
- [ ] Cost tracking: log agent count + cost per query to `data/supermax-costs.jsonl`
- [ ] Integration test: known-trivial query spawns 1 agent; known-complex spawns 5

**Files:** `coordinator/supermax.py`, `config/supermax-v2.json`

---

### US-008: SUPERMAX v2 — Free-MAD Trajectory Scoring
**Description:** As the SUPERMAX consensus system, I want to replace weighted averaging with Free-MAD trajectory scoring so that agent assessment stability (not agreement speed) determines consensus quality.

**Acceptance Criteria:**
- [ ] Replace `DisagreementAwareSynthesizer` averaging with trajectory stability scoring
- [ ] Each agent evaluates independently, then receives anonymized peer reasoning (anti-sycophancy: agent labels stripped)
- [ ] After peer exposure, each agent re-evaluates — the DELTA between original and post-exposure score is the trajectory
- [ ] Stable agents (small delta) get higher weight in final consensus; unstable agents (large delta, shifted toward peers) get lower weight (sycophancy detection)
- [ ] If all agents shift toward each other (unanimous convergence after peer exposure), flag as potential sycophancy and trigger Contrarian agent
- [ ] Log trajectory data per query to `data/supermax-trajectories.jsonl`
- [ ] Integration test: agent that holds position under challenge gets higher weight than agent that capitulates

**Files:** `coordinator/supermax.py`, `coordinator/synthesizer.py`

---

### US-009: SUPERMAX v2 — Disagreement Escalation
**Description:** As the SUPERMAX consensus system, I want to escalate high-disagreement cases to an arbiter agent instead of averaging away the signal so that the 26% disagreement cases get the attention they deserve.

**Acceptance Criteria:**
- [ ] When agent trajectory scores diverge by > 0.15 on any DQ dimension, trigger escalation
- [ ] Arbiter agent receives full reasoning from all evaluating agents + the specific dimensions of disagreement
- [ ] Arbiter makes final call with explicit written reasoning for which perspective prevails and why
- [ ] Disagreement dimensions logged: which DQ components (validity vs specificity vs correctness) diverged
- [ ] Disagreement patterns fed back to difficulty estimator as training data (high disagreement → increase IRT difficulty for similar future queries)
- [ ] Integration test: manufactured disagreement case triggers arbiter; arbiter's reasoning references the specific divergent dimensions

**Files:** `coordinator/supermax.py`, `coordinator/synthesizer.py`

---

### US-010: Graph Confidence Loop — Write Direction
**Description:** As the knowledge graph, I want routing outcomes to update my triple confidence scores so that successful interactions make me denser and more confident while failures flag sparse areas.

**Acceptance Criteria:**
- [ ] After each routing decision with a behavioral outcome score (US-005):
  - DQ outcome >= 0.7: boost confidence of retrieved triples by +0.05 (capped at 1.0)
  - DQ outcome < 0.4: degrade confidence by -0.10 (floored at 0.0)
  - DQ outcome 0.4-0.7: no change
- [ ] Confidence stored as new column `confidence` in `supermemory.db` `memory_links` table (default 0.5 for existing links)
- [ ] Migration: `ALTER TABLE memory_links ADD COLUMN confidence REAL DEFAULT 0.5`
- [ ] Runs as background daemon (NOT in hook chain — Security Architect requirement), processing outcomes every 60 seconds
- [ ] Batch processing: max 100 link updates per cycle, depth-limited to 2 hops from retrieved nodes
- [ ] Graph snapshot taken before each batch (stored as `data/graph-snapshots/YYYY-MM-DD-HHMMSS.json` with affected link IDs + pre/post confidence)
- [ ] Failed routes flag sparse subgraphs: if subgraph density < 0.1 and outcome < 0.4, log to `data/sparse-subgraph-flags.jsonl`
- [ ] Integration test: mock successful routing → verify confidence boost; mock failure → verify degradation; verify snapshot created

**Files:** `kernel/graph-confidence-daemon.py`, `~/.claude/memory/supermemory.db`

---

### US-011: Ecosystem Dashboard — SUPERMAX v2 + Graph Signal Tabs
**Description:** As a system operator, I want the ecosystem dashboard to display SUPERMAX v2 metrics and graph signal data live so that the unified intelligence layer is visible in one place.

**Acceptance Criteria:**
- [ ] New `/api/supermax` endpoint in `ccc-api-server.py` returns: agent count per query, trajectory scores, disagreement escalations, cost savings vs v1
- [ ] New `/api/graph-signal` endpoint returns: current graph signal weights, subgraph density distribution, confidence heatmap, sparse subgraph flags
- [ ] Ecosystem dashboard (`ecosystem.html`) adds 2 new panels:
  - SUPERMAX v2: adaptive agent count distribution chart, trajectory stability chart, disagreement escalation count
  - Graph Signal: confidence distribution across graph, sparse subgraph flags, write-direction activity (boosts vs degradations)
- [ ] SSE streaming for both new data sources (poll every 30 seconds)
- [ ] Integration test: mock data inserted → verify API returns correct structure → verify dashboard renders

**Files:** `~/.claude/scripts/ccc-api-server.py`, `~/.claude/dashboard/ecosystem.html`

---

### US-012: A/B Test Framework — Graph Signal vs Keyword Complexity
**Description:** As the system, I want to run a controlled A/B test comparing the new multi-feature graph signal against the existing keyword-based complexity estimation so that we have evidence before fully switching.

**Acceptance Criteria:**
- [ ] Both complexity signals (keyword and graph) computed for every query during A/B period
- [ ] 50/50 traffic split: odd session IDs use graph signal, even use keyword (deterministic, reproducible)
- [ ] Both signals + routing decision + behavioral outcome logged to `data/ab-test-graph-signal.jsonl`
- [ ] Analysis script `scripts/ab-test-graph-signal.py` computes: per-group DQ accuracy, cost, behavioral outcome, ECE
- [ ] A/B test runs for minimum 200 routing decisions before analysis
- [ ] Rollback: if graph signal group DQ accuracy is > 5% worse than keyword group, auto-revert to keyword-only with alert
- [ ] Integration test: verify both signals computed and logged; verify analysis script produces valid comparison

**Files:** `kernel/dq-scorer.js`, `scripts/ab-test-graph-signal.py`

## Functional Requirements

- FR-1: Multi-feature graph signal must compose entropy, Gini, subgraph density, and IRT difficulty with configurable weights
- FR-2: All weights must be stored in JSON config files (future Optimas LRF compatibility), never hardcoded
- FR-3: Behavioral outcome scores must be computed from non-circular signals only (no LLM self-assessment as ground truth)
- FR-4: DQ calibration must produce proposals to the existing Gödel engine mutation pipeline (single weight authority)
- FR-5: SUPERMAX v2 agent count must be adaptive based on graph complexity signal
- FR-6: Free-MAD trajectory scoring must anonymize agent responses before peer exposure (anti-sycophancy)
- FR-7: Graph confidence updates must run as a background daemon, never in the hook chain
- FR-8: Graph confidence updates must be depth-limited to 2 hops and batch-limited to 100 per cycle
- FR-9: Graph snapshots must be taken before every confidence update batch
- FR-10: All new JSONL outputs must be append-only (existing design principle)
- FR-11: All existing DQ benchmark tests (8/8) must continue to pass after changes

## Non-Goals (Out of Scope)

- Optimas LRF auto-optimization (Sprint 2)
- Router-R1 reasoning router replacement (Sprint 3)
- Active inference / pymdp integration (Sprint 4)
- MAGMA multi-graph architecture (deferred — premature at 1,010 nodes per PE)
- SEAL nested learning loops (security veto — autonomous code modification)
- SQLite ATTACH + TEMP triggers (deferred — WAL locking risk)
- GraphPlanner MDP routing (deferred — insufficient training data)
- Router-R1 multi-round routing (skip — CLI architecture mismatch)
- Human labeling pipeline for calibration anchors (future enhancement, not Sprint 1)

## Technical Considerations

- **Cross-runtime bridge:** DQ scorer is Node.js, HSRGS/calibrator are Python. Use shared JSON files or SQLite for IRT difficulty communication. Do NOT add inter-process RPC.
- **Supermemory query performance:** 12.15M links table. All new queries must use indexed columns. Add indexes on `source_id`, `target_id` if not present.
- **Gödel engine coordination:** DQ calibration weight adjustments must go through `propose_mutation` in HSRGS, not write directly to weight files. One weight authority prevents oscillation (Security Architect finding).
- **Background daemon pattern:** Graph confidence daemon follows existing daemon patterns in `~/.claude/daemon/`. Use LaunchAgent for scheduling.
- **Existing dependency:** HSRGS imports `sentence_transformers` (pre-existing supply chain exposure). No new external dependencies added in this sprint.

## Success Metrics

- Multi-feature graph signal A/B test shows >= 10% improvement in routing accuracy over keyword complexity (GraphRouter paper showed 12.3%)
- DQ ECE (Expected Calibration Error) reduced below 0.10 after behavioral calibration
- SUPERMAX v2 cost per query reduced >= 40% via adaptive agent count (DAAO paper showed 64%)
- Free-MAD trajectory scoring achieves >= 10% accuracy improvement over weighted averaging (paper showed 16%)
- Graph confidence loop processes >= 100 routing outcomes per day with zero hook chain timeouts
- All 8 DQ benchmark tests continue to pass (regression gate)

## Open Questions

- Should the A/B test run for a fixed period (2 weeks) or until statistical significance (p < 0.05)?
- What's the minimum behavioral outcome backfill needed before first calibration? (Proposed: 200 sessions)
- Should SUPERMAX v2 Contrarian agent use a different model (Gemini/GPT-4) or same model with adversarial prompt?
- How often should graph confidence snapshots be pruned? (Proposed: keep 30 days)

## Research Lineage

| Innovation | Paper | Venue | How Applied |
|---|---|---|---|
| Multi-feature routing | GraphRouter (arXiv:2410.03834) | ICLR 2025 | US-001 through US-004 |
| IRT difficulty | IRT-Router | ACL 2025 | US-003 |
| Entropy/Gini signals | SkewRoute (arXiv:2505.23841) | EMNLP 2025 | US-001 |
| Behavioral calibration | arXiv:2601.19862 | 2026 | US-005, US-006 |
| Self-assessment bias | arXiv:2410.21819 | 2024 | US-005 (why NOT to use ACE) |
| Free-MAD | arXiv:2509.11035 | 2025 | US-008 |
| Adaptive agent count | DAAO (arXiv:2509.11079) | 2025 | US-007 |
| Anti-sycophancy | CONSENSAGENT (ACL 2025) | ACL 2025 | US-008 |
| Confidence-annotated KG | arXiv:2601.09720 | 2026 | US-010 |
| Optimas LRF framing | optimas.stanford.edu | Stanford 2025 | All weight configs (future-proofing) |
| Active inference north star | VERSES Genius, pymdp | 2025 | Architectural decisions |
