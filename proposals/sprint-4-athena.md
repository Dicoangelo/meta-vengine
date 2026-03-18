# PRD: Athena — Adaptive Intelligence Dashboard (Sprint 4)

## Overview

Sprint 3 activated the learning loop — banditEnabled is true, 3 daemons are scheduled, 24 params learn autonomously. But the system is a black box: no visibility into what it's learning, no way to watch convergence, no control surface for operator preferences.

Sprint 4 gives the system eyes (observatory dashboard), deeper self-tuning (learnable session multipliers with volume gates), and a fundamentally better decision-making core (active inference for model selection, multi-objective Pareto optimization with operator preference vectors).

The result: an operator can open a browser, see every weight evolving in real-time, watch clusters form, track A/B experiments, and steer the system's optimization priorities — while the engine itself uses free energy minimization to select models and explores a Pareto frontier across quality, cost, and latency.

## Goals

- Provide real-time visual observatory into the learning loop (dashboard with charts, clusters, timelines)
- Serve dashboard via lightweight Python HTTP server on localhost:8420
- Promote session-type multipliers from config-only to bandit-learned with volume gating
- Track multiplier convergence per session type with stability monitoring
- Replace HSRGS pressure-field model selection with active inference (free energy minimization)
- Track multi-objective Pareto front across quality, cost, and latency (model-tier proxy)
- Enable operator preference vectors that bias BO exploration along the Pareto frontier
- Support time-of-day preference scheduling (peak hours: quality, off-peak: cost)
- Validate all components end-to-end in <30 seconds

## Quality Gates

These commands must pass for every user story:
- `python3 kernel/preflight.py` — Activation prerequisites validated
- `pytest kernel/tests/` — All Python test suites pass
- `node kernel/tests/` — All JavaScript test suites pass

For Sprint 4 integration:
- `pytest kernel/tests/test_athena.py` — End-to-end Sprint 4 validation (<30s)

For dashboard stories:
- Open `http://localhost:8420` and verify visual rendering

## User Stories

### Pillar 1: Observatory Dashboard

#### US-301: Live Dashboard Shell & HTTP Server
**Description:** As a system operator, I want a single-page dashboard served on localhost:8420 so that I can see the learning loop's health at a glance.

**Acceptance Criteria:**
- [ ] `kernel/dashboard/serve.py` — Python HTTP server (stdlib `http.server`) on port 8420
- [ ] `kernel/dashboard/index.html` — Single-page dashboard shell with nav tabs: Overview, Weights, Clusters, Timeline
- [ ] `kernel/dashboard/style.css` — Dark theme (matches meta-vengine aesthetic), responsive layout
- [ ] `kernel/dashboard/app.js` — Dashboard application logic, data fetching, tab routing
- [ ] Overview tab shows: banditEnabled status (green/red), daemon health (from daemon-health.py output), last snapshot age, total param count (24→48 after US-305), total decisions (from bandit-state.json sampleCounter), avg reward (last 100 decisions)
- [ ] Server exposes JSON API endpoints: `/api/health`, `/api/params`, `/api/bandit-state`, `/api/history?last=N`
- [ ] API endpoints read directly from data/ files (no database)
- [ ] Auto-refreshes every 60 seconds via JS `setInterval`
- [ ] `python3 kernel/dashboard/serve.py` starts server, prints URL to stdout
- [ ] Vanilla HTML/JS/CSS only — zero npm, zero frameworks, zero external CDN

**Files:** `kernel/dashboard/serve.py`, `kernel/dashboard/index.html`, `kernel/dashboard/style.css`, `kernel/dashboard/app.js`

---

#### US-302: Weight Evolution Charts
**Description:** As a system operator, I want to see how weights evolve over time so that I can verify the bandit is converging.

**Acceptance Criteria:**
- [ ] New API endpoint `/api/weight-history` returns weight snapshots from `data/weight-snapshots/` (sorted by date)
- [ ] New API endpoint `/api/reward-trend` returns last N rewards from `data/bandit-history.jsonl`
- [ ] Weights tab renders line charts using Canvas API (no chart libraries)
- [ ] One chart per param group (DQ Weights, Graph Signal, Agent Thresholds, Free-MAD, Behavioral, Reward Composition, LRF Topology, Exploration Schedule)
- [ ] Each chart shows param values over time with labeled axes
- [ ] Reward sparkline at top of Weights tab showing composite reward trend (last 200 decisions)
- [ ] Charts handle missing data gracefully (empty state message if no snapshots yet)
- [ ] Canvas charts support: line rendering, axis labels, legend, grid lines, hover tooltip showing exact values
- [ ] Chart module in `kernel/dashboard/charts.js` — reusable `drawLineChart(canvas, datasets, options)` function

**Files:** `kernel/dashboard/charts.js`, `kernel/dashboard/app.js` (weights tab), `kernel/dashboard/serve.py` (new endpoints)

---

#### US-303: LRF Cluster Visualization
**Description:** As a system operator, I want to see the cluster topology so that I can verify contexts are well-separated.

**Acceptance Criteria:**
- [ ] New API endpoint `/api/clusters` returns cluster data from `data/lrf-clusters.json`
- [ ] New API endpoint `/api/cluster-projection` returns 2D PCA projection of cluster centroids
- [ ] `kernel/dashboard/pca.py` — Pure Python PCA (covariance matrix → eigendecomposition → project 14-dim centroids to 2D). Called by serve.py, cached until lrf-clusters.json changes
- [ ] Clusters tab renders scatter plot on Canvas showing cluster positions in 2D
- [ ] Each cluster rendered as a circle sized by decision count
- [ ] Color-coded by maturity: red (<50 decisions, sparse), yellow (50-200, moderate), green (>200, mature)
- [ ] Hover/click on cluster shows tooltip: cluster ID, size, avg reward, decision count, exploration rate, top weight configuration
- [ ] Silhouette score displayed as a gauge/badge at top of clusters tab
- [ ] Empty state if no clusters formed yet

**Files:** `kernel/dashboard/pca.py`, `kernel/dashboard/clusters.js`, `kernel/dashboard/serve.py` (new endpoints)

---

#### US-304: Rollback & A/B Report Timeline
**Description:** As a system operator, I want to see rollback events and A/B test results on a timeline so that I can track system stability.

**Acceptance Criteria:**
- [ ] New API endpoint `/api/timeline` returns merged rollback + A/B events sorted by timestamp
- [ ] Reads from `data/rollback-reports/` and `data/ab-reports/` (all JSON files)
- [ ] Timeline tab renders vertical timeline with events as cards
- [ ] Rollback events: red border for critical, yellow for warning. Shows trigger type, affected params, severity
- [ ] A/B events: green for candidate_wins, blue for baseline_wins, gray for inconclusive. Shows verdict, p-value, Cohen's d, effect size
- [ ] Click on event card expands to show full report details (JSON pretty-printed)
- [ ] Timeline supports scrolling through historical events
- [ ] Summary bar at top: total rollbacks (7d/30d), total A/B tests, win rate
- [ ] Empty state message if no events yet

**Files:** `kernel/dashboard/timeline.js`, `kernel/dashboard/serve.py` (new endpoint)

---

### Pillar 2: Learnable Session Multipliers

#### US-305: Multiplier Params in Registry
**Description:** As a routing engine, I want session-type multipliers as learnable params so that the system tunes reward shaping per session type.

**Acceptance Criteria:**
- [ ] 24 new parameters in `config/learnable-params.json` (8 session types × 3 multipliers each):
  - Format: `session_{type}_{component}` e.g., `session_debugging_dq`, `session_debugging_cost`, `session_debugging_behavioral`
  - Defaults match current `config/session-reward-multipliers.json` values
  - Each param: min 0.5, max 2.0, learnRate 0.01
- [ ] New group: "Session Multipliers" with constraint: "independent" (soft averaging via BO, not hard clamp)
- [ ] `param-registry.js` and `param_registry.py` load and validate new 24 params (total: 48 params)
- [ ] `config/session-reward-multipliers.json` updated with comment noting params are now in registry (file kept as documentation/fallback only)
- [ ] Param count in learnable-params.json description updated to 48

**Files:** `config/learnable-params.json`, `config/session-reward-multipliers.json`, `kernel/param-registry.js`, `kernel/param_registry.py`

---

#### US-306: Multiplier Bandit Integration
**Description:** As a routing engine, I want the bandit to perturb session multipliers so that they evolve toward optimal per-session-type reward shaping.

**Acceptance Criteria:**
- [ ] `bandit-engine.js` `computeReward()` reads multipliers from param registry instead of `config/session-reward-multipliers.json`
- [ ] For a given session type (e.g., "debugging"), loads `session_debugging_dq`, `session_debugging_cost`, `session_debugging_behavioral` from registry
- [ ] Bandit `sample()` perturbs multiplier params alongside all other params (same Thompson Sampling process)
- [ ] Multiplier perturbations logged in `data/bandit-history.jsonl` per decision (includes which session-type multipliers were active)
- [ ] Falls back to registry defaults (1.0, 1.0, 1.0) if session type not in registry
- [ ] Backward compatible: if learnable multiplier params don't exist yet, falls back to config file

**Files:** `kernel/bandit-engine.js`

---

#### US-307: Session Volume Gate
**Description:** As a routing engine, I want to gate multiplier learning on sufficient data so that rare session types don't learn from noise.

**Acceptance Criteria:**
- [ ] New data file `data/session-type-stats.jsonl` — append-only log of per-session-type decision counts
- [ ] `kernel/session-volume-gate.py` tracks cumulative decisions per session type
- [ ] Threshold: 100 decisions before a session type's multipliers become learnable
- [ ] Below threshold: bandit-engine uses default multipliers (1.0, 1.0, 1.0) for that session type, skips perturbation of those 3 params
- [ ] Above threshold: normal bandit perturbation applies
- [ ] `bandit-engine.js` checks volume gate before perturbing session multiplier params: reads latest counts from `data/session-type-stats.jsonl` (cached, refreshed every 50 decisions)
- [ ] Gate status per session type logged in bandit history: `volumeGated: true/false`
- [ ] API endpoint `/api/session-stats` returns per-type counts and gate status

**Files:** `kernel/session-volume-gate.py`, `kernel/bandit-engine.js`, `data/session-type-stats.jsonl`, `kernel/dashboard/serve.py`

---

#### US-308: Multiplier Stability Monitor
**Description:** As a system operator, I want to see which session types have converged multipliers so that I know when the system is stable.

**Acceptance Criteria:**
- [ ] `kernel/stability-monitor.py` analyzes multiplier drift per session type over last 200 decisions
- [ ] Convergence criteria: all 3 multipliers for a session type changed <1% over 200 consecutive decisions
- [ ] Per-session-type status: "learning" (below volume gate), "converging" (above gate, still drifting), "converged" (<1% drift)
- [ ] Convergence events logged to `data/convergence-events.jsonl` with timestamp, session_type, final multiplier values
- [ ] API endpoint `/api/convergence` returns per-session-type convergence status
- [ ] Dashboard Overview tab shows convergence summary: badge per session type (red=learning, yellow=converging, green=converged)
- [ ] Run by weight-snapshot daemon as a post-step (like daemon-health)

**Files:** `kernel/stability-monitor.py`, `data/convergence-events.jsonl`, `kernel/dashboard/serve.py`, `kernel/dashboard/app.js`

---

### Pillar 3: Active Inference & Multi-Objective

#### US-309: Active Inference Router
**Description:** As a routing engine, I want model selection via free energy minimization so that the system naturally balances exploration and exploitation.

**Acceptance Criteria:**
- [ ] `kernel/active-inference.py` — Pure Python active inference implementation (no pymdp):
  - **Generative model:** P(observation | model, query_type) — beliefs about what each model produces for each query type
  - **Prior preferences:** Desired outcome distribution (high quality, low cost)
  - **Belief updating:** After each routing decision, update beliefs about model capabilities using Bayesian update
  - **Model selection:** Choose model that minimizes expected free energy: `G = E[log Q(s) - log P(o|s) - log P(o)]` (epistemic + pragmatic value)
  - **Query types:** Map to HSRGS IRT difficulty levels (easy/moderate/hard/expert)
  - **Model profiles:** Initialize from existing `config/pricing.json` capability data
- [ ] Beliefs persisted to `data/active-inference-beliefs.json` (updated after each decision)
- [ ] HSRGS `hsrgs.py` updated: `select_model()` calls active inference instead of pressure-field when `activeInferenceEnabled: true` flag is set
- [ ] Pressure-field routing remains as fallback (active inference for model selection only, HSRGS keeps query encoding + IRT)
- [ ] Feature flag `activeInferenceEnabled` in `config/learnable-params.json` (default: false, enable after validation)
- [ ] Logging: each routing decision logs free energy components (epistemic value, pragmatic value, selected model, beliefs snapshot) to `data/active-inference-log.jsonl`

**Files:** `kernel/active-inference.py`, `kernel/hsrgs.py`, `config/learnable-params.json`, `data/active-inference-beliefs.json`, `data/active-inference-log.jsonl`

---

#### US-310: Multi-Objective Reward Surface
**Description:** As a routing engine, I want to track a Pareto front across quality, cost, and latency so that the system explores the full optimal trade-off surface.

**Acceptance Criteria:**
- [ ] `kernel/pareto.py` — Pure Python Pareto front computation:
  - **3 objectives:** DQ quality (higher=better), cost efficiency (lower=better, inverted for maximization), latency (lower=better, proxied by model tier: haiku=1.0, sonnet=0.6, opus=0.3)
  - **Dominance check:** Config A dominates B if A is better on all objectives
  - **Non-dominated sort:** Extract Pareto-optimal configs from history
  - **Front persistence:** Save to `data/pareto-front.json` with configs, objective values, timestamps
  - **Front update:** After each BO cycle, recompute Pareto front from all evaluated configs
- [ ] `data/pareto-front.json` tracks non-dominated configs with their objective vectors
- [ ] Model tier latency mapping in `config/model-latency-tiers.json`: `{"claude-opus-4-6": 0.3, "claude-sonnet-4-6": 0.6, "claude-haiku-4-5": 1.0}` (normalized, higher=faster)
- [ ] Extensible: `pareto.py` accepts N objectives (not hardcoded to 3), start with 3
- [ ] API endpoint `/api/pareto` returns current Pareto front for dashboard visualization
- [ ] Dashboard Weights tab shows Pareto front as a 2D projection (quality vs cost, with latency as point size)

**Files:** `kernel/pareto.py`, `data/pareto-front.json`, `config/model-latency-tiers.json`, `kernel/dashboard/serve.py`, `kernel/dashboard/charts.js`

---

#### US-311: Preference-Aware BO
**Description:** As a system operator, I want to set optimization preferences so that the system biases toward quality or cost based on my needs.

**Acceptance Criteria:**
- [ ] New config file `config/operator-preferences.json`:
  ```json
  {
    "default": {"quality": 0.5, "cost": 0.3, "latency": 0.2},
    "schedules": {
      "peak": {"hours": [9,10,11,12,14,15,16,17], "preferences": {"quality": 0.7, "cost": 0.15, "latency": 0.15}},
      "off_peak": {"hours": [0,1,2,3,4,5,6,7,8,13,18,19,20,21,22,23], "preferences": {"quality": 0.3, "cost": 0.5, "latency": 0.2}}
    }
  }
  ```
- [ ] `kernel/bayesian_optimizer.py` extended:
  - `get_active_preferences()` reads config, checks current hour, returns preference vector
  - EI acquisition function weighted by preference: `weighted_EI = sum(pref_i * EI_i)` across objectives
  - BO proposes candidates biased toward preferred region of Pareto front
- [ ] Preference vector logged in BO reports (`data/bo-reports/`)
- [ ] API endpoint `/api/preferences` returns current active preferences (with schedule context)
- [ ] Dashboard Overview tab shows active preference vector as a radar chart or bar chart
- [ ] Preferences can be updated by editing config file (no restart needed, read on each BO cycle)

**Files:** `config/operator-preferences.json`, `kernel/bayesian_optimizer.py`, `kernel/dashboard/serve.py`, `kernel/dashboard/app.js`

---

#### US-312: Sprint 4 Integration Test Suite
**Description:** As a developer, I want an end-to-end test covering all Sprint 4 components so that the full Athena system is validated.

**Acceptance Criteria:**
- [ ] `kernel/tests/test_athena.py` covers the complete Sprint 4 pipeline:
  1. **Dashboard server:** Start serve.py, verify `/api/health` returns valid JSON with banditEnabled status
  2. **Weight history API:** Verify `/api/weight-history` returns snapshots sorted by date
  3. **PCA projection:** Verify `pca.py` projects 14-dim centroids to 2D, output shape correct
  4. **Timeline API:** Verify `/api/timeline` merges rollback + A/B events chronologically
  5. **Multiplier registry:** Verify 48 params loaded, session multiplier group exists with 24 params
  6. **Multiplier bandit:** Verify computeReward uses registry multipliers, different session types produce different rewards
  7. **Volume gate:** Verify session type with <100 decisions uses default multipliers, >100 uses learned
  8. **Convergence detection:** Inject 200 stable multiplier decisions, verify convergence detected
  9. **Active inference:** Verify free energy computation, model selection, belief updating after outcome
  10. **Pareto front:** Generate 50 synthetic configs with 3 objectives, verify non-dominated sort extracts correct front
  11. **Preference-aware BO:** Verify different preference vectors produce different candidate rankings
  12. **Preference scheduling:** Verify peak vs off-peak hours return different preference vectors
- [ ] All tests use mocked data (no real API calls, no real server, tempdir for all data)
- [ ] Total execution time < 30 seconds
- [ ] Test acts as acceptance gate for Sprint 4 completion

**Files:** `kernel/tests/test_athena.py`

---

## Functional Requirements

- FR-1: Dashboard served on localhost:8420 via stdlib Python HTTP server, no external dependencies
- FR-2: All dashboard charts rendered with Canvas API, no chart libraries
- FR-3: Dashboard auto-refreshes every 60 seconds, all data read from local files
- FR-4: 24 session multiplier params (8 types × 3) learnable via Thompson Sampling bandit
- FR-5: Session types with <100 decisions use default multipliers (volume gate)
- FR-6: Multiplier convergence tracked per session type with <1% drift threshold over 200 decisions
- FR-7: Active inference replaces pressure-field for model selection only, HSRGS retains query encoding + IRT
- FR-8: Active inference feature-flagged, disabled by default, HSRGS pressure-field as fallback
- FR-9: Pareto front computed across N objectives (starting with 3: quality, cost, latency)
- FR-10: Latency proxied by model tier (haiku=fast, opus=slow) until real latency telemetry available
- FR-11: Operator preferences bias BO exploration, with time-of-day scheduling
- FR-12: All Sprint 4 components validated end-to-end in <30 seconds with mocked data

## Non-Goals (Out of Scope)

- **No real-time WebSocket streaming** — polling every 60s is sufficient for Sprint 4
- **No authentication** on dashboard — localhost only, single operator
- **No mobile-responsive dashboard** — desktop browser only
- **No real latency measurement** — model-tier proxy until Sprint 5 adds actual timing
- **No learning of preference vectors** — operator sets manually, auto-learning deferred to Sprint 5
- **No active inference for query routing** — only for model selection; HSRGS keeps full query pipeline
- **No multi-operator support** — single preference config, no user accounts

## Technical Considerations

- **Dashboard architecture:** Python `http.server` subclass with custom `do_GET` handler routing `/api/*` to Python functions and `/*` to static files in `kernel/dashboard/`
- **Canvas chart library:** Build a minimal reusable `drawLineChart()`, `drawScatterPlot()`, `drawBarChart()` in `charts.js`. No external deps.
- **PCA implementation:** Covariance matrix → power iteration for top-2 eigenvectors (no numpy). Cache result until lrf-clusters.json mtime changes.
- **Active inference math:** Variational free energy `F = E_Q[log Q(s) - log P(o,s)]`. Model selection minimizes expected free energy `G`. Beliefs as Dirichlet distributions over model-query outcomes. Update via Bayesian posterior.
- **Pareto dominance:** O(N²) pairwise comparison for non-dominated sort. Acceptable for <1000 configs. If needed, optimize to O(N log N) in Sprint 5.
- **Volume gate caching:** bandit-engine.js reads session-type-stats.jsonl once per 50 decisions, not per-decision (performance).
- **48 params:** Registry validation remains O(N) on load. Bandit perturbation is O(N) per sample — 48 params still well under 1ms.

## Dependencies

- Sprint 3 complete and activated (committed f376ba1)
- `banditEnabled: true` with production telemetry flowing
- Existing telemetry: bandit-history.jsonl, weight-snapshots/, rollback-reports/, ab-reports/, lrf-clusters.json
- `config/pricing.json` for model capability profiles (active inference initialization)

## Success Metrics

- Dashboard loads in <2 seconds, all 4 tabs render with real data
- Weight evolution charts show visible convergence trends over 500+ decisions
- LRF cluster scatter plot shows clear separation with maturity color coding
- At least 3 session types (debugging, research, testing) pass volume gate within 2 weeks
- At least 1 session type reaches "converged" status within 4 weeks
- Active inference selects same or better models than pressure-field (A/B validated, p<0.05)
- Pareto front contains 5+ non-dominated configs after first BO cycle
- Peak-hour preference steering measurably shifts BO proposals toward quality
- `test_athena.py` passes in <30 seconds with 12/12 assertions green

## Resolved Design Decisions

1. **Dashboard serving: Python HTTP server (not static file)** — Live API endpoints enable auto-refresh, computed data (PCA projections), and future WebSocket upgrade path. Stdlib only, no Flask/FastAPI.

2. **Active inference: model selection only (not full routing)** — HSRGS query encoding, IRT difficulty, and latent space representations are battle-tested. Active inference replaces only the final model selection step (pressure-field), where exploration-exploitation balance matters most.

3. **Pareto: extensible N-objective (not hardcoded 3)** — `pareto.py` accepts any number of objectives. Start with 3 (quality, cost, latency-proxy). Sprint 5 can add real latency, user satisfaction, or other objectives without refactoring.

4. **Latency: model-tier proxy (not real measurement)** — Real latency requires timing infrastructure not yet built. Model tier (haiku=fast, opus=slow) is a reasonable proxy. Sprint 5 adds actual request timing.
