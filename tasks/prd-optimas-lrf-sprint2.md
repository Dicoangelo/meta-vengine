# PRD: Optimas LRF Auto-Optimization — Sprint 2

## Overview

Make Sprint 1's 19 externalized weight parameters actually learn from every routing decision. Implements a 3-phase training loop: real-time Thompson Sampling bandits (every query), weekly contextual LRF clustering, and monthly Bayesian Optimization refinement — all with bounded safety and automatic rollback.

**Research basis:** Optimas (arXiv:2507.03041, Stanford, 11.92% avg improvement), LLM Bandit (arXiv:2502.02743), LD-MOLE (ICLR 2026), BaRP (arXiv:2510.07429), LLAMBO (arXiv:2402.03921).

**Prerequisite:** Sprint 1 complete (all 12 stories shipped, calibration-001 applied, graph confidence daemon running).

## Goals

- Transform static JSON config weights into learnable parameters via Thompson Sampling bandits
- Implement Optimas-style Local Reward Functions: globally aligned, locally adaptive per query context
- Add monthly Bayesian Optimization refinement to escape local optima
- Enforce safety bounds: max 5% drift per epoch, automatic rollback, minimum trial thresholds
- Track all weight experiments in append-only telemetry for auditability

## Quality Gates

These commands must pass for every user story:

- `python3 -m py_compile <file>` — Python syntax check
- `node --check <file>` — Node.js syntax check
- `pytest <test_file> -v` — Unit/integration tests for the story
- `node scripts/benchmark-100.js compare` — DQ benchmark regression (if touching DQ scorer)

## Learnable Parameter Inventory

| Config | Params | File |
|--------|--------|------|
| Graph Signal Weights | 4 (entropy, gini, subgraphDensity, irtDifficulty) | `config/graph-signal-weights.json` |
| DQ Weights | 3 (validity, specificity, correctness) | `kernel/baselines.json` |
| Agent Count Thresholds | 4 (trivial, simple, moderate, complex boundaries) | `config/supermax-v2.json` |
| Free-MAD Tuning | 3 (decayRate, sycophancyThreshold, disagreementThreshold) | `config/supermax-v2.json` |
| Behavioral Outcome Weights | 5 (completion, toolSuccess, efficiency, noOverride, noFollowup) | `kernel/behavioral-outcome.py` |
| **Total** | **19** | |

## User Stories

### US-101: Learnable Weight Schema — Unified Parameter Registry
**Description:** As the optimization system, I want a single registry that describes all 19 learnable parameters with their bounds, learning rates, and safety constraints so that the bandit and BO systems have a canonical source of truth.

**Acceptance Criteria:**
- [ ] New file `config/learnable-params.json` with entry per parameter: `{id, configFile, jsonPath, value, min, max, learnRate, group}`
- [ ] Groups: `graph_signal`, `dq_weights`, `agent_thresholds`, `free_mad`, `behavioral`
- [ ] Constraints per group: `sumMustEqual` (for weight groups), `monotonic` (for threshold groups), `independent` (for free_mad)
- [ ] Loader function in both JS (`kernel/param-registry.js`) and Python (`kernel/param_registry.py`) that reads registry and returns current values
- [ ] Loader validates constraints on read (sum = 1.0, monotonic ordering, bounds)
- [ ] Unit tests: malformed registry raises error, valid registry loads cleanly, constraint violations detected

**Files:** `config/learnable-params.json`, `kernel/param-registry.js`, `kernel/param_registry.py`

---

### US-102: Thompson Sampling Bandit — Core Engine
**Description:** As the routing system, I want a Thompson Sampling bandit that proposes weight perturbations for each routing decision so that the system explores better weight configurations in real time.

**Acceptance Criteria:**
- [ ] New module `kernel/bandit-engine.js` with `ThompsonBandit` class
- [ ] Each learnable parameter has a Beta distribution (alpha, beta) representing belief about optimal value
- [ ] `sample()` returns perturbed weight config: base value + sampled perturbation (bounded by min/max)
- [ ] Perturbation range: ±`learnRate` from current value (default learnRate = 0.02)
- [ ] `update(reward)` updates Beta distributions based on outcome (reward > threshold → success)
- [ ] Bandit state persisted to `data/bandit-state.json` after every update
- [ ] 15% exploration rate: with 15% probability, sample from uniform prior instead of learned posterior
- [ ] Unit tests: sampling stays within bounds, updates shift distribution, state persists and restores

**Files:** `kernel/bandit-engine.js`, `data/bandit-state.json`

---

### US-103: Outcome Reward Function
**Description:** As the bandit system, I want a reward function that converts behavioral outcome scores into bandit rewards so that the bandit learns which weight configs produce better routing.

**Acceptance Criteria:**
- [ ] New function `computeReward(routingDecision, behavioralOutcome)` in `kernel/bandit-engine.js`
- [ ] Reward = weighted composite: DQ score accuracy (0.40) + cost efficiency (0.30) + behavioral outcome (0.30)
- [ ] Cost efficiency = 1.0 - (actual_cost / max_possible_cost) for the query complexity tier
- [ ] Reward normalized to [0, 1]
- [ ] Reward weights stored in `config/learnable-params.json` under `rewardFunction` (meta-learnable in Sprint 3)
- [ ] Reward logged to `data/bandit-history.jsonl`: `{timestamp, routing_id, weight_config_version, reward, reward_components}`
- [ ] Unit tests: perfect routing → reward ~1.0, worst routing → reward ~0.0, components sum correctly

**Files:** `kernel/bandit-engine.js`, `data/bandit-history.jsonl`

---

### US-104: Bandit Integration into DQ Scorer
**Description:** As the DQ scoring system, I want to use bandit-sampled weights at decision time so that every routing query contributes to weight learning.

**Acceptance Criteria:**
- [ ] DQ scorer calls `bandit.sample()` before computing DQ score (gets perturbed weights)
- [ ] Sampled weights replace static config weights for that single decision
- [ ] After behavioral outcome is known (async, via daemon), `bandit.update(reward)` called
- [ ] Decision record in `dq-scores.jsonl` extended with: `weight_config_version`, `bandit_sample_id`, `perturbed_weights`
- [ ] Feature flag: `config/learnable-params.json` has `"banditEnabled": true/false` — when false, uses static weights (safe rollback)
- [ ] Integration test: routing with bandit enabled produces valid DQ scores within normal range

**Files:** `kernel/dq-scorer.js`, `kernel/bandit-engine.js`

---

### US-105: Safety Bounds — Drift Detection and Rollback
**Description:** As the system operator, I want automatic safety bounds that prevent weight drift from degrading routing quality so that the bandit can't silently break the system.

**Acceptance Criteria:**
- [ ] New module `kernel/weight-safety.py` with `WeightSafety` class
- [ ] Max drift per epoch (24h): no parameter moves more than 5% from epoch start value
- [ ] If avg reward drops >8% below rolling 7-day average, trigger automatic rollback to last known good snapshot
- [ ] Minimum trial threshold: don't trust any weight perturbation with < 20 trials
- [ ] Weight snapshots taken daily: `data/weight-snapshots/YYYY-MM-DD.json` with all 19 param values + avg reward
- [ ] Rollback writes to `data/weight-rollbacks.jsonl` with reason, pre/post values, affected params
- [ ] Alert: when rollback triggers, log WARNING to `data/weight-alerts.jsonl`
- [ ] Unit tests: drift beyond 5% triggers clamp, reward drop triggers rollback, snapshot restore works

**Files:** `kernel/weight-safety.py`, `data/weight-snapshots/`, `data/weight-rollbacks.jsonl`

---

### US-106: Weight Snapshot Daemon
**Description:** As the system, I want a daily daemon that snapshots current weight values and computes epoch-level metrics so that rollback has clean restore points.

**Acceptance Criteria:**
- [ ] New daemon `kernel/weight-snapshot-daemon.py` runs daily (LaunchAgent, 24h interval)
- [ ] Snapshots all 19 params from registry + bandit state + avg reward for the epoch
- [ ] Computes epoch metrics: avg reward, reward variance, exploration rate, drift from baseline
- [ ] Compares to previous epoch: if improvement > 3%, mark as "promoted" (new baseline)
- [ ] Prunes snapshots older than 90 days (keep promoted snapshots forever)
- [ ] Integration test: creates snapshot, restores from snapshot, metrics computed correctly

**Files:** `kernel/weight-snapshot-daemon.py`, `data/weight-snapshots/`

---

### US-107: Contextual LRF — Query Context Clustering
**Description:** As the optimization system, I want to cluster routing decisions by context so that each cluster can have locally optimized weights (Optimas Local Reward Functions).

**Acceptance Criteria:**
- [ ] New module `kernel/lrf-clustering.py` with `ContextualLRF` class
- [ ] Context features extracted per query: graphComplexity, sessionType (8 types), timeOfDay (5 cognitive modes), domain
- [ ] K-means clustering with k=5 (learnable k in Sprint 3): trivial-morning, complex-peak, research-evening, etc.
- [ ] Per-cluster weight preferences computed: which weight configs produced highest rewards in this cluster?
- [ ] Cluster assignments stored in `data/lrf-clusters.json` with centroids and per-cluster optimal weights
- [ ] At routing time: classify query into cluster → use cluster-specific weight bias + bandit perturbation
- [ ] Weekly update: re-cluster based on last 7 days of decisions (minimum 50 decisions per cluster to trust)
- [ ] Unit tests: clustering produces valid assignments, per-cluster weights differ, empty cluster handled

**Files:** `kernel/lrf-clustering.py`, `data/lrf-clusters.json`

---

### US-108: Weekly LRF Update Daemon
**Description:** As the system, I want a weekly daemon that re-computes LRF clusters and per-cluster optimal weights so that local rewards stay fresh.

**Acceptance Criteria:**
- [ ] New daemon `kernel/lrf-update-daemon.py` runs weekly (LaunchAgent, 7-day interval)
- [ ] Reads last 7 days of routing decisions with outcomes from `dq-scores.jsonl` and `behavioral-outcomes.jsonl`
- [ ] Re-runs clustering, updates `data/lrf-clusters.json`
- [ ] Compares new cluster weights to previous: if any cluster improved >5%, log promotion
- [ ] If total decisions < 200 for the week, skip update (insufficient data)
- [ ] Outputs weekly LRF report to `data/lrf-reports/YYYY-WW.json`
- [ ] Integration test: mock 7 days of decisions → clusters computed → report generated

**Files:** `kernel/lrf-update-daemon.py`, `data/lrf-reports/`

---

### US-109: Bayesian Optimization — Monthly Refinement
**Description:** As the optimization system, I want monthly Bayesian Optimization over the full 19-dimensional weight space so that the system escapes local optima the bandits can't find.

**Acceptance Criteria:**
- [ ] New script `kernel/bayesian-optimizer.py` with `BayesianWeightOptimizer` class
- [ ] Fits Gaussian Process over weight space using last 30 days of (weight_config, reward) pairs
- [ ] Uses Expected Improvement acquisition function to propose next weight config
- [ ] Proposes 3 candidate configs; runs A/B test (50 decisions each) to validate
- [ ] Promotion gate: candidate must beat current baseline by >= 3% avg reward
- [ ] If no candidate beats baseline, retain current weights (conservative)
- [ ] Uses `scipy.optimize.minimize` for GP fitting (no new dependencies — scipy already available)
- [ ] Monthly report: `data/bo-reports/YYYY-MM.json` with GP fit quality, candidates tested, winner
- [ ] Unit tests: GP fits synthetic data, acquisition function proposes valid configs, promotion gate works

**Files:** `kernel/bayesian-optimizer.py`, `data/bo-reports/`

---

### US-110: Monthly BO Trigger + A/B Infrastructure
**Description:** As the system, I want the monthly BO to trigger automatically and run its A/B validation using the existing A/B test framework so that refinement is hands-off.

**Acceptance Criteria:**
- [ ] New daemon `kernel/bo-monthly-daemon.py` runs on 1st of each month (LaunchAgent)
- [ ] Calls `BayesianWeightOptimizer.propose()` to get candidate configs
- [ ] Extends Sprint 1 A/B test framework (`scripts/ab-test-graph-signal.py` pattern) for weight configs
- [ ] A/B split: 70% current weights, 10% each for 3 candidates (deterministic by session ID hash)
- [ ] After 150 decisions (~3 days at 50/day), auto-analyze and promote winner or retain baseline
- [ ] Human override: `coevo-apply bo-YYYY-MM` to manually approve/reject BO proposal
- [ ] Integration test: mock monthly trigger → candidates proposed → A/B split active → analysis runs

**Files:** `kernel/bo-monthly-daemon.py`, `scripts/ab-test-weights.py`

---

### US-111: Ecosystem Dashboard — Learning Metrics Panel
**Description:** As a system operator, I want the ecosystem dashboard to show bandit learning progress, LRF clusters, and BO refinement status so that the auto-optimization is visible and auditable.

**Acceptance Criteria:**
- [ ] New `/api/learning` endpoint returns: bandit state (exploration rate, avg reward trend), LRF cluster stats, BO status, weight drift, rollback history
- [ ] Dashboard panel "Learning Engine" with:
  - Reward trend chart (30 days)
  - Current weight values vs baseline (bar chart)
  - LRF cluster visualization (5 clusters with per-cluster reward)
  - BO status badge (idle / proposing / A/B testing / promoted)
  - Rollback count and last rollback timestamp
- [ ] SSE streaming for learning metrics (poll every 60 seconds)

**Files:** `~/.claude/scripts/ccc-api-server.py`, `~/.claude/dashboard/ecosystem.html`

---

### US-112: End-to-End Learning Validation Test
**Description:** As the system, I want an end-to-end test that verifies the full learning loop works: routing → outcome → bandit update → weight drift → safety check so that we have confidence before enabling in production.

**Acceptance Criteria:**
- [ ] New test `kernel/tests/test_learning_loop.py` with mock routing decisions
- [ ] Test injects 100 mock decisions with known-optimal weights different from current config
- [ ] Verifies bandit shifts weights toward optimal over 100 iterations
- [ ] Verifies safety bounds prevent overshoot (no param moves > 5% per epoch)
- [ ] Verifies rollback triggers when reward deliberately degraded
- [ ] Verifies LRF clustering produces different weights for different context clusters
- [ ] Test runs in < 10 seconds (no real API calls, all mocked)
- [ ] This test is the acceptance gate for enabling `banditEnabled: true` in production

**Files:** `kernel/tests/test_learning_loop.py`

## Functional Requirements

- FR-1: All 19 parameters must be registered in a single canonical registry with bounds and constraints
- FR-2: Thompson Sampling must explore within bounded perturbation ranges, never exceeding min/max
- FR-3: Bandit state must persist across process restarts (JSON file)
- FR-4: Safety bounds must prevent >5% drift per 24h epoch and auto-rollback on >8% reward drop
- FR-5: LRF clusters must have minimum 50 decisions before trusting per-cluster weights
- FR-6: Monthly BO must run A/B validation before promoting any weight change
- FR-7: All weight experiments logged to append-only JSONL (auditability)
- FR-8: Feature flag `banditEnabled` allows instant disable without code change
- FR-9: Existing DQ benchmark tests (8/8) must continue to pass
- FR-10: No new external dependencies (use stdlib + scipy which is already available)

## Non-Goals (Out of Scope)

- Router-R1 reasoning router replacement (Sprint 3)
- Active inference / pymdp integration (Sprint 4)
- Meta-learning the reward function weights (Sprint 3)
- Learnable k for LRF clustering (Sprint 3)
- Multi-objective Pareto optimization (Sprint 4)
- Human preference data collection (not needed — we use behavioral outcomes)

## Technical Considerations

- **Cross-runtime bridge:** Bandit engine is JS (real-time in DQ scorer), safety/LRF/BO are Python (offline). Shared state via JSON files and SQLite — same pattern as Sprint 1 IRT bridge.
- **Daemon scheduling:** Weight snapshot daily, LRF weekly, BO monthly. All follow existing LaunchAgent patterns.
- **Scipy availability:** Already importable via homebrew Python 3.14. No new deps.
- **Bandit cold start:** First 100 decisions use high exploration (50%) to build initial belief. After 100, drop to 15%.

## Success Metrics

- Bandit-enabled routing shows >= 5% reward improvement over static weights within 30 days
- LRF clusters show >= 3% reward improvement for at least 2 of 5 clusters vs global weights
- Monthly BO proposes at least 1 promoted config in first 3 months
- Zero unintended rollbacks in first 30 days (safety bounds work but don't false-positive)
- Weight drift stays within 5% per epoch for all 19 parameters
- All 8 DQ benchmark tests continue to pass

## Research Lineage

| Innovation | Paper | Venue | How Applied |
|---|---|---|---|
| Globally Aligned LRF | Optimas (arXiv:2507.03041) | Stanford 2025 | US-107, US-108 |
| Thompson Sampling routing | LLM Bandit (arXiv:2502.02743) | 2025 | US-102, US-103, US-104 |
| Learnable dynamic routing | LD-MOLE (ICLR 2026) | ICLR 2026 | Architecture pattern |
| Bandit-feedback routing | BaRP (arXiv:2510.07429) | 2025 | US-102 safety design |
| LLM-enhanced BO | LLAMBO (arXiv:2402.03921) | 2024 | US-109 |
| Adaptive budget routing | arXiv:2508.21141 | 2025 | US-105 rollback design |
