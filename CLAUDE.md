# meta-vengine

Self-improving routing engine. Routes queries to optimal AI providers via DQ scoring, learns from sessions, evolves its own configuration.

**Stack:** Python 3.8+ / Node.js 18+ / Bash · SQLite3 + JSONL · Zero external frameworks

## Architecture

```
Query → DQ Scorer + HSRGS → Active Inference → Model Selection → Telemetry → Co-evolution Loop
```

**Kernel (JS):** `dq-scorer.js` (DQ scoring), `pattern-detector.js` (8 session types), `bandit-engine.js` (Thompson Sampling), `param-registry.js` (48 learnable params)

**Kernel (Python):** `cognitive-os.py` (energy routing), `hsrgs.py` (emergent routing), `weight-safety.py` (drift clamp + rollback), `lrf-clustering.py` (contextual LRF), `bayesian_optimizer.py` (monthly BO), `active-inference.py` (free energy model selection), `pareto.py` (multi-objective Pareto front), `behavioral-outcome.py`, `dq-calibrator.py`, `graph-confidence-daemon.py`

**Daemons:** `weight-snapshot-daemon.py` (daily), `lrf-update-daemon.py` (weekly), `bo-monthly-daemon.py` (1st of month) — scheduled via macOS LaunchAgent (`daemons/`)

**Automation:** `preflight.py` (activation gate), `bootstrap.py` (warm-start), `daemon-health.py` (health monitor), `ab-runner.py` (A/B pipeline), `coevo-update.py` (self-documentation), `session-volume-gate.py`, `stability-monitor.py`

**Dashboard:** `kernel/dashboard/serve.py` — localhost:8420, 4 tabs (Overview, Weights, Clusters, Timeline), Canvas charts, JSON API

**Coordination:** `coordinator/orchestrator.py` — parallel_research, parallel_implement, review_build, full strategies

## Commands

```bash
uni-ai "query"           # Auto-routed query
routing-dash             # Performance dashboard
coevo-analyze            # Co-evolution analysis
coord research|implement|review|full|team "task"
cos state|flow|fate|route "task"
obs N                    # N-day report
ccc                      # Command Center dashboard
python3 kernel/dashboard/serve.py   # Observatory dashboard on :8420
python3 kernel/preflight.py         # Activation gate check
python3 kernel/daemon-health.py     # Daemon health report
```

## Testing

```bash
pytest kernel/tests/ -v                           # All 105 tests (< 1s)
pytest kernel/tests/test_learning_loop.py         # Sprint 2: bandit + safety + LRF
pytest kernel/tests/test_prometheus.py            # Sprint 3: 12 end-to-end assertions
pytest kernel/tests/test_athena.py                # Sprint 4: 12 end-to-end assertions
pytest scripts/observatory/qa-test-suite.py       # Observatory
python3 scripts/ab-test-analyzer.py --detailed    # A/B test analysis
```

**Note:** `kernel/tests/test_dq_calibrator.py` uses `sys.exit()` at module level — run standalone (`python3 kernel/tests/test_dq_calibrator.py`), not via pytest.

## Design Principles

1. Bidirectional co-evolution — reads own patterns, modifies own config
2. Sovereignty by design — all data local, human approval for changes
3. Zero dependencies — vanilla JS + stdlib Python
4. Append-only telemetry — JSONL never overwritten
5. Model ID sovereignty — `config/pricing.json` is canonical, never inline model strings

## Learnable Weight System

48 params in `config/learnable-params.json` across 9 groups. Thompson Sampling bandit perturbs weights, outcome reward function (learnable DQ/cost/behavioral split) updates beliefs. Safety: max 5% drift/epoch, 8% reward drop triggers rollback. `banditEnabled: true`.

| Group | Params | Constraint |
|-------|--------|------------|
| Graph Signal | 4 | sumMustEqual 1.0 |
| DQ Weights | 3 | sumMustEqual 1.0 |
| Agent Thresholds | 5 | monotonic ascending |
| Free-MAD | 3 | independent |
| Behavioral | 4 | sumMustEqual 0.9 (implicit remainder) |
| Reward Composition | 3 | sumMustEqual 1.0 |
| LRF Topology | 1 | independent (integer) |
| Exploration Schedule | 1 | independent |
| Session Multipliers | 24 | independent (8 types x 3, volume-gated) |

## Sprint History

**Sprint 2 — Optimas LRF Auto-Optimization** (72687d4): 19 initial params, Thompson Sampling bandit, weight safety, LRF clustering, Bayesian optimizer. Feature-flagged `banditEnabled`.

**Sprint 3 — Prometheus: Self-Activating Loop** (proposals/sprint-3-prometheus.md): Activation gate (preflight.py), 3 LaunchAgent daemons, warm-start bootstrap, meta-learnable reward weights, learnable cluster count (k) with silhouette validation, per-cluster exploration annealing, session-type reward multipliers, A/B test pipeline (Welch's t-test), rollback dashboard, co-evolution self-documentation. 12/12 US, `test_prometheus.py` passes.

**Sprint 4 — Athena: Adaptive Intelligence Dashboard** (proposals/sprint-4-athena.md): Observatory dashboard (localhost:8420, Canvas charts, 4 tabs), session multipliers promoted to bandit-learned (24 new params → 48 total), volume gate (100 decisions/type), convergence monitor, active inference router (free energy model selection, feature-flagged `activeInferenceEnabled`), multi-objective Pareto front (quality/cost/latency), preference-aware BO with time-of-day scheduling. 12/12 US, `test_athena.py` passes.

<!-- COEVO-START -->
### Live Weight State (auto-updated by coevo-update.py)

**Last updated:** 2026-03-18T12:24:15Z

#### Current Weights by Group
| Group | Param | Value | Range |
|-------|-------|-------|-------|
| Graph Signal | graph_entropy_weight | 0.3 | [0.05, 0.6] |
| Graph Signal | graph_gini_weight | 0.25 | [0.05, 0.6] |
| Graph Signal | graph_subgraph_density_weight | 0.25 | [0.05, 0.6] |
| Graph Signal | graph_irt_difficulty_weight | 0.2 | [0.05, 0.6] |
| Dq Weights | dq_validity_weight | 0.3912 | [0.1, 0.6] |
| Dq Weights | dq_specificity_weight | 0.2853 | [0.1, 0.6] |
| Dq Weights | dq_correctness_weight | 0.3235 | [0.1, 0.6] |
| Agent Thresholds | agent_trivial_threshold | 0.25 | [0.1, 0.4] |
| Agent Thresholds | agent_simple_threshold | 0.45 | [0.3, 0.6] |
| Agent Thresholds | agent_moderate_threshold | 0.65 | [0.5, 0.8] |
| Agent Thresholds | agent_complex_threshold | 0.85 | [0.7, 0.95] |
| Agent Thresholds | agent_expert_threshold | 1 | [0.9, 1] |
| Free Mad | freemad_stability_decay_rate | 5 | [1, 20] |
| Free Mad | freemad_sycophancy_threshold | 0.05 | [0.01, 0.2] |
| Free Mad | freemad_disagreement_threshold | 0.15 | [0.05, 0.4] |
| Behavioral | behavioral_completion_weight | 0.3 | [0.1, 0.5] |
| Behavioral | behavioral_tool_success_weight | 0.25 | [0.05, 0.5] |
| Behavioral | behavioral_efficiency_weight | 0.2 | [0.05, 0.4] |
| Behavioral | behavioral_no_override_weight | 0.15 | [0.05, 0.4] |
| Reward Composition | rewardWeightDQ | 0.4 | [0.2, 0.6] |
| Reward Composition | rewardWeightCost | 0.3 | [0.1, 0.5] |
| Reward Composition | rewardWeightBehavioral | 0.3 | [0.1, 0.5] |
| Lrf Topology | kClusters | 5 | [3, 10] |
| Exploration Schedule | explorationFloorGlobal | 0.05 | [0.01, 0.15] |

#### LRF Cluster State
- **k:** 5 clusters
- **Silhouette score:** ?

#### Exploration Schedule
- **Global floor:** 0.05
- **Per-cluster overrides:** read from LRF cluster config at runtime

#### Session-Type Multipliers
Active config from `config/session-reward-multipliers.json` (default: `refactoring`)

| Session Type | DQ | Cost | Behavioral | Boosts |
|---|---|---|---|---|
| debugging | 0.8 | 1 | 1.2 | tool_success_boost=1.5 |
| research | 1.2 | 0.8 | 1 | completion_boost=1.3 |
| architecture | 1.3 | 0.7 | 1 | - |
| refactoring | 1 | 1 | 1 | - |
| testing | 0.9 | 1 | 1.1 | tool_success_boost=1.3 |
| docs | 1 | 1.2 | 0.8 | - |
| exploration | 1.1 | 0.9 | 1 | - |
| creative | 1 | 0.8 | 1.2 | - |

#### Last BO Result
- No BO cycles completed yet.
<!-- COEVO-END -->

## DQ Benchmark

100-query benchmark (arXiv:2511.15755). 8/8 passed. SUPERMAX consensus: +12.4% DQ, -95.4% variance vs single-model. Details: `docs/DQ_BENCHMARK_RESULTS.md`
