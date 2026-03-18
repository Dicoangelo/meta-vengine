# meta-vengine

Self-improving routing engine. Routes queries to optimal AI providers via DQ scoring, learns from sessions, evolves its own configuration.

**Stack:** Python 3.8+ / Node.js 18+ / Bash · SQLite3 + JSONL · Zero external frameworks

## Architecture

```
Query → DQ Scorer + HSRGS → Model Selection → Telemetry → Co-evolution Loop
```

**Kernel:** `kernel/dq-scorer.js` (DQ scoring), `kernel/pattern-detector.js` (8 session types), `kernel/cognitive-os.py` (energy-aware routing), `kernel/hsrgs.py` (emergent routing), `kernel/bandit-engine.js` (Thompson Sampling weight learning), `kernel/param-registry.js` (19 learnable params), `kernel/weight-safety.py` (drift clamping + rollback), `kernel/lrf-clustering.py` (contextual LRF)

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
```

## Testing

```bash
pytest kernel/tests/test_learning_loop.py        # Learning loop (bandit + safety + LRF)
pytest scripts/observatory/qa-test-suite.py       # Observatory
python3 scripts/ab-test-analyzer.py --detailed    # A/B test analysis
```

## Design Principles

1. Bidirectional co-evolution — reads own patterns, modifies own config
2. Sovereignty by design — all data local, human approval for changes
3. Zero dependencies — vanilla JS + stdlib Python
4. Append-only telemetry — JSONL never overwritten
5. Model ID sovereignty — `config/pricing.json` is canonical, never inline model strings

## Learnable Weight System (Sprint 2)

19 params in `config/learnable-params.json` across 5 groups. Thompson Sampling bandit perturbs weights, outcome reward function (DQ accuracy 40% + cost efficiency 30% + behavioral 30%) updates beliefs. Safety: max 5% drift/epoch, 8% reward drop triggers rollback. Feature-flagged via `banditEnabled`.

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
