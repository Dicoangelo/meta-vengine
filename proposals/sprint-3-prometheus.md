# PRD: Prometheus — Self-Activating Learning Loop (Sprint 3)

## Overview

Sprint 2 built a complete learnable weight system for meta-vengine: Thompson Sampling bandit, safety bounds, contextual LRF clustering, and Bayesian optimization. But the system has never run in production — `banditEnabled` is false, no daemons are scheduled, and data directories are empty.

Sprint 3 activates the dormant learning infrastructure, adds meta-learning capabilities (learnable reward function, learnable cluster count, per-cluster exploration annealing, session-type reward shaping), and closes every automation loop (A/B testing pipeline, rollback dashboard, co-evolution self-documentation).

The result: a routing engine that not only learns optimal weights, but learns *how* to learn — optimizing its own reward function, cluster topology, and exploration strategy.

## Goals

- Activate the learning loop in production with validated preflight checks
- Schedule and monitor 3 autonomous daemons (weight snapshot, LRF update, BO monthly)
- Make the reward function itself learnable (meta-learning outer loop with frozen inner bandit)
- Make LRF cluster count learnable with silhouette validation
- Implement per-cluster exploration annealing (sparse clusters explore more, mature clusters exploit)
- Shape rewards per session type (debugging vs research vs architecture)
- Automate A/B testing with Welch's t-test, adaptive early stopping, and 100-sample power
- Provide rich rollback reporting and recovery dashboard
- Self-document weight state into CLAUDE.md after each BO cycle
- Validate all components end-to-end in <30 seconds

## Quality Gates

These commands must pass for every user story:
- `python3 kernel/preflight.py` — Activation prerequisites validated
- `pytest kernel/tests/` — All Python test suites pass
- `node kernel/tests/` — All JavaScript test suites pass

For Sprint 3 integration:
- `pytest kernel/tests/test_prometheus.py` — End-to-end Sprint 3 validation (<30s)

## User Stories

### Phase 1: Production Activation

#### US-201: Activation Gate & Preflight Check
**Description:** As a system operator, I want a preflight validation script so that `banditEnabled` is only set to `true` when all prerequisites are verified.

**Acceptance Criteria:**
- [ ] `kernel/preflight.py` checks: test_learning_loop.py passes (subprocess), all data dirs exist and are writable (`data/`, `data/weight-snapshots/`, `data/lrf-reports/`, `data/bo-reports/`, `data/rollback-reports/`, `data/ab-reports/`, `data/daemon-logs/`), `config/learnable-params.json` loads without validation errors, `config/graph-signal-weights.json` exists, `config/supermax-v2.json` exists
- [ ] Outputs structured go/no-go report to stdout (JSON) with per-check status and timing
- [ ] On all-pass: sets `banditEnabled: true` in `config/learnable-params.json`
- [ ] On any failure: prints failing checks, does NOT modify config, exits non-zero
- [ ] Idempotent — safe to run multiple times
- [ ] Logs preflight result to `data/preflight-log.jsonl` (append-only)

**Files:** `kernel/preflight.py`, `data/preflight-log.jsonl`

---

#### US-202: LaunchAgent Daemon Scheduling
**Description:** As a system operator, I want macOS LaunchAgent plists for the 3 learning daemons so that weight snapshots, LRF updates, and BO refinement run autonomously on schedule.

**Acceptance Criteria:**
- [ ] 3 plist files in `daemons/` directory:
  - `com.metavengine.weight-snapshot.plist` — daily at 03:00
  - `com.metavengine.lrf-update.plist` — weekly Sunday at 04:00
  - `com.metavengine.bo-monthly.plist` — 1st of month at 05:00
- [ ] Each plist uses `RunAtLoad: false`, `StartCalendarInterval` for scheduling
- [ ] Each plist points to a wrapper script in `daemons/` that sets PATH, PYTHONPATH, working dir, and logs stdout/stderr to `data/daemon-logs/`
- [ ] `daemons/install.sh` — copies plists to `~/Library/LaunchAgents/`, runs `launchctl load` for each
- [ ] `daemons/uninstall.sh` — runs `launchctl unload`, removes plists from LaunchAgents
- [ ] `launchctl list | grep metavengine` shows 3 agents after install
- [ ] Each daemon wrapper checks `banditEnabled` before executing (no-op if false)
- [ ] Daemon logs include ISO timestamps and daemon name prefix
- [ ] Daemon logs rotate: max 10MB per log file, rotated to `.1` suffix

**Files:** `daemons/*.plist`, `daemons/run-weight-snapshot.sh`, `daemons/run-lrf-update.sh`, `daemons/run-bo-monthly.sh`, `daemons/install.sh`, `daemons/uninstall.sh`

---

#### US-203: Daemon Health Monitor
**Description:** As a system operator, I want a health check script that verifies daemons ran on schedule so that missed or failed runs are detected within 24 hours.

**Acceptance Criteria:**
- [ ] `kernel/daemon-health.py` checks last-modified timestamps of expected output files:
  - Weight snapshot: `data/weight-snapshots/` most recent file < 25 hours old
  - LRF report: `data/lrf-reports/` most recent file < 8 days old
  - BO report: `data/bo-reports/` most recent file < 32 days old
- [ ] Checks daemon log files in `data/daemon-logs/` for error patterns (Traceback, non-zero exit, OOM)
- [ ] Outputs health report per daemon: `{daemon, status: "healthy"|"stale"|"error", last_run, next_expected, details}`
- [ ] Appends to `data/daemon-health.jsonl` with timestamp
- [ ] Exit code 0 if all healthy, 1 if any stale/error
- [ ] Daily weight-snapshot daemon runs health check as post-step (chains automatically)

**Files:** `kernel/daemon-health.py`, `data/daemon-health.jsonl`

---

#### US-204: Production Telemetry Bootstrap
**Description:** As a system operator, I want a warm-start bootstrap so that the bandit begins with informed beliefs rather than uninformative priors.

**Acceptance Criteria:**
- [ ] `kernel/bootstrap.py` reads existing `data/behavioral-outcomes.jsonl` entries
- [ ] Requires minimum 50 entries; exits with clear message if insufficient
- [ ] Computes aggregate reward statistics from historical outcomes (mean, std, percentiles per dimension)
- [ ] Seeds `data/bandit-state.json` with Beta(alpha, beta) priors derived from historical reward distribution using method of moments (not flat 1,1)
- [ ] Runs LRF clustering on historical data to create initial `data/lrf-clusters.json` with k clusters (from registry)
- [ ] Computes initial silhouette score and stores as baseline in cluster metadata
- [ ] Takes first weight snapshot to `data/weight-snapshots/`
- [ ] Logs bootstrap report to `data/bootstrap-report.json` (entries used, priors computed, cluster sizes, silhouette score)
- [ ] Idempotent — warns and skips if bandit-state.json already exists (use `--force` to override)

**Files:** `kernel/bootstrap.py`, `data/bootstrap-report.json`

---

### Phase 2: Meta-Learning

#### US-205: Meta-Learnable Reward Weights
**Description:** As a routing engine, I want the reward function composition (DQ/cost/behavioral split) to be learnable so that the system optimizes how it evaluates success.

**Acceptance Criteria:**
- [ ] 3 new parameters in `config/learnable-params.json`:
  - `rewardWeightDQ` (default 0.40, min 0.20, max 0.60, learnRate 0.02)
  - `rewardWeightCost` (default 0.30, min 0.10, max 0.50, learnRate 0.02)
  - `rewardWeightBehavioral` (default 0.30, min 0.10, max 0.50, learnRate 0.02)
  - Group: "Reward Composition", constraint: sumMustEqual 1.0
- [ ] `param-registry.js` and `param_registry.py` load and validate new group
- [ ] `bandit-engine.js` `computeReward()` reads weights from registry instead of hardcoded 0.40/0.30/0.30
- [ ] Monthly BO (`bayesian_optimizer.py`) includes reward weights in candidate proposals
- [ ] **Inner bandit frozen during outer-loop BO:** When `data/bo-state.json` contains `boEvaluationActive: true`, bandit-engine skips perturbation and uses current weights as-is
- [ ] BO evaluation: 100 decisions per candidate (adaptive early stop at 50 if p<0.01), reward computed with candidate weights, compared to baseline
- [ ] Safety: reward weights bounded by min/max, rollback if composite reward drops >8%

**Files:** `config/learnable-params.json`, `kernel/bandit-engine.js`, `kernel/bayesian_optimizer.py`, `kernel/param-registry.js`, `kernel/param_registry.py`, `data/bo-state.json`

---

#### US-206: Learnable LRF Cluster Count
**Description:** As a routing engine, I want the number of LRF clusters to be learnable so that the context topology adapts to actual usage patterns.

**Acceptance Criteria:**
- [ ] New parameter in `config/learnable-params.json`:
  - `kClusters` (default 5, min 3, max 10, learnRate 0.01, integer constraint)
  - Group: "LRF Topology", constraint: independent
- [ ] `param-registry.js` and `param_registry.py` handle integer constraint: round after perturbation, validate integer on load
- [ ] `lrf-clustering.py` reads k from param registry instead of hardcoded 5
- [ ] Pure Python silhouette score implementation (pairwise Euclidean over 14-dim features, no sklearn)
- [ ] Silhouette guard: if score drops >15% from best-known score, reject proposed k, revert to previous, log rejection to `data/lrf-reports/`
- [ ] BO can propose integer k values; proposal rounded to nearest int, clamped to [3,10]
- [ ] Best-known silhouette score persisted in `data/lrf-clusters.json` metadata field `bestSilhouette`

**Files:** `config/learnable-params.json`, `kernel/lrf-clustering.py`, `kernel/param_registry.py`, `kernel/param-registry.js`, `kernel/bayesian_optimizer.py`

---

#### US-207: Per-Cluster Exploration Annealing
**Description:** As a routing engine, I want exploration rates to decay per-cluster so that mature clusters exploit while sparse clusters continue exploring.

**Acceptance Criteria:**
- [ ] New parameter in `config/learnable-params.json`:
  - `explorationFloorGlobal` (default 0.05, min 0.01, max 0.15, learnRate 0.01)
  - Group: "Exploration Schedule", constraint: independent
- [ ] `bandit-engine.js` replaces fixed 15% exploration with per-cluster annealing:
  - Base schedule: decisions 0–100: 50%, 100–500: decay to 10%, 500–2000: decay to floor, 2000+: hold at floor
  - **Per-cluster override:** each cluster in `data/lrf-clusters.json` gets a `clusterExplorationRate` field
  - Clusters with <50 decisions: floor = max(0.15, globalFloor) — forced exploration for sparse clusters
  - Clusters with 50–200 decisions: floor = max(0.08, globalFloor) — moderate exploration
  - Clusters with >200 decisions: floor = globalFloor — mature, exploit
- [ ] Cluster decision counts tracked in `data/lrf-clusters.json` per-cluster `decisionCount` field
- [ ] Current exploration rate (global + cluster override) logged per decision in `data/bandit-history.jsonl`
- [ ] Per-epoch summary includes per-cluster exploration/exploitation ratios
- [ ] `explorationFloorGlobal` learnable by BO (lower floor = faster convergence but risk of local optima)

**Files:** `config/learnable-params.json`, `kernel/bandit-engine.js`, `kernel/lrf-clustering.py`, `data/lrf-clusters.json`

---

#### US-208: Reward Shaping — Session Type Multipliers
**Description:** As a routing engine, I want reward components weighted differently per session type so that debugging sessions value tool success while research sessions value completion.

**Acceptance Criteria:**
- [ ] New config file `config/session-reward-multipliers.json` with 8 session-type multiplier vectors:
  ```json
  {
    "debugging":    {"dq": 0.8, "cost": 1.0, "behavioral": 1.2, "tool_success_boost": 1.5},
    "research":     {"dq": 1.2, "cost": 0.8, "behavioral": 1.0, "completion_boost": 1.3},
    "architecture": {"dq": 1.3, "cost": 0.7, "behavioral": 1.0},
    "refactoring":  {"dq": 1.0, "cost": 1.0, "behavioral": 1.0},
    "testing":      {"dq": 0.9, "cost": 1.0, "behavioral": 1.1, "tool_success_boost": 1.3},
    "docs":         {"dq": 1.0, "cost": 1.2, "behavioral": 0.8},
    "exploration":  {"dq": 1.1, "cost": 0.9, "behavioral": 1.0},
    "creative":     {"dq": 1.0, "cost": 0.8, "behavioral": 1.2}
  }
  ```
- [ ] Multipliers are element-wise: `reward_component *= multiplier` before final normalization to [0,1]
- [ ] `bandit-engine.js` `computeReward()` accepts session type parameter, loads multipliers, applies them
- [ ] Falls back to `refactoring` multipliers (all 1.0) for unknown/missing session types
- [ ] Session type detected via `pattern-detector.js` (existing 8-type classifier) and passed through
- [ ] Applied multipliers logged in `data/bandit-history.jsonl` per decision (`sessionType`, `multipliers` fields)
- [ ] Multiplier vectors are config-only in Sprint 3 (not bandit-learned — deferred to Sprint 4)

**Files:** `config/session-reward-multipliers.json`, `kernel/bandit-engine.js`

---

### Phase 3: Closed-Loop Automation

#### US-209: A/B Test Automation Pipeline
**Description:** As a system operator, I want an automated A/B test runner with statistical rigor so that weight candidates are validated before promotion.

**Acceptance Criteria:**
- [ ] `kernel/ab-runner.py` accepts baseline config, candidate config, and sample size N (default 100)
- [ ] Routes decisions alternating ABAB interleaving (not blocked) to eliminate temporal confounds
- [ ] Collects composite reward for each decision under each config
- [ ] Pure Python Welch's t-test implementation (no scipy): t-statistic via pooled SE, p-value via incomplete beta function approximation, degrees of freedom via Welch-Satterthwaite
- [ ] **Adaptive early stopping:** at N=50, if p<0.01 (large effect), stop and declare winner early
- [ ] At N=100 (or full sample): declares "candidate_wins" (p<0.05, candidate mean > baseline), "baseline_wins" (p<0.05, baseline > candidate), or "inconclusive" (p≥0.05)
- [ ] Effect size: Cohen's d computed and included in report
- [ ] Power analysis: reports achieved statistical power given observed effect size and N
- [ ] Output: structured report to `data/ab-reports/YYYY-MM-DD-HHmmss.json` with means, stds, N, t-statistic, df, p-value, Cohen's d, power, verdict, early_stopped flag
- [ ] BO monthly (`bayesian_optimizer.py`) calls ab-runner for each candidate vs baseline
- [ ] Standalone invocation: `python3 kernel/ab-runner.py --baseline config1.json --candidate config2.json --n 100`

**Files:** `kernel/ab-runner.py`, `data/ab-reports/`

---

#### US-210: Rollback Notification & Recovery Dashboard
**Description:** As a system operator, I want rich rollback reports and a dashboard endpoint so that I understand why rollbacks happen and can track system stability.

**Acceptance Criteria:**
- [ ] `weight-safety.py` rollback generates detailed report to `data/rollback-reports/YYYY-MM-DD-HHmmss.json`:
  - Which params drifted and by how much (absolute delta, relative %)
  - Current vs snapshot values (before/after table)
  - Reward trajectory: last 10 entries showing the decline pattern
  - Trigger type: "drift_exceeded" or "reward_drop"
  - Severity: "warning" (drift clamp applied, no rollback) vs "critical" (full rollback to snapshot)
  - Recovery action: which snapshot was restored, timestamp of snapshot
  - Time-to-detection: how long between drift start and rollback trigger
- [ ] Dashboard endpoint `/api/rollbacks` returns JSON array of all rollback events
- [ ] `/api/rollbacks?last=N` returns N most recent, `/api/rollbacks?severity=critical` filters
- [ ] Rollback count summary available at `/api/rollbacks/summary` (total, by type, by severity, last 7d/30d)

**Files:** `kernel/weight-safety.py`, `data/rollback-reports/`

---

#### US-211: Co-Evolution Feedback Loop
**Description:** As a self-improving system, I want CLAUDE.md automatically updated with live weight state so that documentation evolves with configuration.

**Acceptance Criteria:**
- [ ] `kernel/coevo-update.py` runs after each monthly BO cycle (called by bo-monthly daemon as final step)
- [ ] Reads current live state from: `config/learnable-params.json`, `data/lrf-clusters.json`, `data/bo-reports/` (latest)
- [ ] Patches the section between `<!-- COEVO-START -->` and `<!-- COEVO-END -->` markers in `CLAUDE.md` with:
  - Current best weights per group (DQ, graph signal, agent thresholds, Free-MAD, behavioral, reward composition)
  - Current k clusters, avg silhouette score, per-cluster decision counts
  - Current exploration floor (global + per-cluster overrides)
  - Session-type multipliers active
- [ ] Appends "Last BO Result" subsection:
  - Date, candidates tested, winner or "baseline retained", reward improvement %, promotion decision, early-stopped flag
- [ ] Uses marker-based string replacement (not regex on content) — safe, targeted patching
- [ ] If markers not found on first run, inserts markers + section after "Learnable Weight System" heading
- [ ] Logs update to `data/coevo-updates.jsonl` with diff summary (which values changed, by how much)

**Files:** `kernel/coevo-update.py`, `CLAUDE.md`, `data/coevo-updates.jsonl`

---

#### US-212: Sprint 3 Integration Test Suite
**Description:** As a developer, I want an end-to-end test covering all Sprint 3 components so that the full Prometheus pipeline is validated.

**Acceptance Criteria:**
- [ ] `kernel/tests/test_prometheus.py` covers the complete Sprint 3 pipeline:
  1. **Preflight:** Mocked prerequisites → preflight passes, sets banditEnabled=true
  2. **Bootstrap:** 100 synthetic behavioral entries → warm bandit state created, LRF clusters formed, silhouette computed
  3. **Learning:** 200 simulated decisions with bandit sampling → verify weights drift toward high-reward config (monotonic improvement trend)
  4. **LRF separation:** Verify cluster centroids have inter-cluster distance > intra-cluster distance
  5. **Per-cluster exploration:** Verify sparse clusters (count<50) have exploration rate ≥0.15, mature clusters (count>200) use global floor
  6. **Safety clamp:** Inject 10% drift on one param → verify clamped to 5%
  7. **Rollback:** Inject 8 consecutive low-reward decisions → verify rollback triggers, report generated in `data/rollback-reports/`
  8. **Meta-reward:** Verify reward composition weights loaded from registry, computeReward uses them
  9. **Exploration annealing:** Rate at decision 0 ≈ 0.50, rate at decision 500 ≈ 0.10, rate at decision 2000 ≈ floor
  10. **Session multipliers:** Same raw components produce different composite rewards for "debugging" vs "research" session types
  11. **A/B runner:** Two synthetic configs → Welch's t-test report generated with verdict
  12. **Co-evolution:** Mocked BO result → CLAUDE.md section updated between markers
- [ ] All tests use mocked data (no real API calls, no real claude.db, tempdir for all data files)
- [ ] Total execution time < 30 seconds
- [ ] Test acts as acceptance gate for Sprint 3 completion

**Files:** `kernel/tests/test_prometheus.py`

---

## Functional Requirements

- FR-1: The system must validate all prerequisites via preflight before activating banditEnabled
- FR-2: Three daemons must run autonomously on schedule via macOS LaunchAgent (daily/weekly/monthly)
- FR-3: Daemon health must be monitored with stale-run detection within 24 hours
- FR-4: Bandit must warm-start from historical behavioral data (minimum 50 entries, method-of-moments priors)
- FR-5: Reward function weights (DQ/cost/behavioral) must be learnable via outer-loop BO with inner bandit frozen during evaluation
- FR-6: LRF cluster count must be learnable with silhouette validation (reject if >15% drop from best)
- FR-7: Exploration rate must anneal per-cluster: sparse clusters explore more, mature clusters exploit at global floor
- FR-8: Reward computation must apply session-type-specific multipliers from config
- FR-9: A/B tests must use Welch's t-test (p<0.05) with adaptive early stopping (p<0.01 at N=50) and power reporting
- FR-10: Rollback events must generate detailed reports with param-level drift analysis and severity classification
- FR-11: CLAUDE.md must be auto-patched with live weight state via marker-based replacement after each BO cycle
- FR-12: All Sprint 3 components must be validated end-to-end in <30 seconds with mocked data

## Non-Goals (Out of Scope)

- **Session-type multipliers are NOT bandit-learned in Sprint 3** — config-only; promoted to learnable in Sprint 4
- **No cloud deployment** — all daemons run locally via LaunchAgent
- **No web UI dashboard** — /api endpoints return JSON only; UI deferred to Sprint 4
- **No multi-machine coordination** — single-operator system
- **No real-time streaming** of bandit decisions — batch telemetry only
- **No automatic preflight scheduling** — operator runs preflight.py manually once to activate

## Technical Considerations

- **Cross-runtime bridge:** Meta-reward weights accessible from both JS (bandit-engine) and Python (BO, safety) via shared `config/learnable-params.json` (existing pattern)
- **Outer-loop freeze:** `data/bo-state.json` with `boEvaluationActive: true` flag; bandit-engine checks this and skips perturbation during BO evaluation to prevent confounding inner/outer learning signals
- **Integer parameter handling:** `kClusters` is first integer param in registry; both JS and Python registries must round after perturbation and validate integer constraint
- **Pure Python stats:** Silhouette score (pairwise Euclidean, 14-dim), Welch's t-test (incomplete beta approx), power analysis — all stdlib, no scipy/sklearn
- **CLAUDE.md patching:** HTML comment markers `<!-- COEVO-START -->` / `<!-- COEVO-END -->` for safe replacement
- **LaunchAgent conventions:** `RunAtLoad: false`, `StartCalendarInterval`, `StandardOutPath`/`StandardErrorPath` to `data/daemon-logs/`
- **Per-cluster exploration:** Stored in `lrf-clusters.json` alongside cluster centroids; updated on each LRF re-clustering

## Dependencies

- Sprint 2 complete (✅ committed 72687d4)
- `data/behavioral-outcomes.jsonl` with ≥50 entries for warm-start bootstrap
- `claude.db` accessible for behavioral outcome extraction
- macOS system for LaunchAgent scheduling

## Success Metrics

- `banditEnabled: true` in production with zero manual weight tuning required
- 3 daemons running and healthy for 7+ consecutive days (verified by daemon-health.py)
- Bandit convergence: weight variance decreases >30% over first 500 decisions
- LRF cluster separation: >10% avg reward difference between best and worst cluster
- Meta-reward weights diverge from 40/30/30 default within 2 BO cycles (system finds its own optimal)
- Per-cluster exploration: sparse clusters explore 3x more than mature clusters
- A/B test pipeline: 100% of BO promotions validated with p<0.05
- Zero undetected rollbacks (all caught and reported within 24h)
- CLAUDE.md reflects live state within 1 hour of BO completion
- `test_prometheus.py` passes in <30 seconds with 12/12 assertions green

## Resolved Design Decisions

1. **Exploration floor: per-cluster (not global)** — Sparse clusters keep floor at 0.15, mature clusters drop to global floor (default 0.05). Prevents premature exploitation in under-explored contexts while maximizing convergence speed in well-mapped territory.

2. **Session-type multipliers: config-only in Sprint 3, learnable in Sprint 4** — Establishes human-tuned baseline first. Sprint 4 promotes multiplier vectors to bandit-learned params once we have enough per-session-type decision volume.

3. **BO sample size: 100 per candidate with adaptive early stop at 50** — 80% statistical power at p<0.05 for medium effect sizes (Cohen's d ≥ 0.3). Early stop at p<0.01 catches large effects without wasting budget. Power analysis included in every report.
