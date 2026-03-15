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

## DQ Benchmark

100-query benchmark (arXiv:2511.15755). 8/8 passed. SUPERMAX consensus: +12.4% DQ, -95.4% variance vs single-model. Details: `docs/DQ_BENCHMARK_RESULTS.md`
