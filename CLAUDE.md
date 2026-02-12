# CLAUDE.md

This file provides guidance to Claude Code when working with the meta-vengine codebase.

## Overview

Meta-vengine is a bidirectional co-evolution system — a self-improving intelligent routing engine that routes queries to optimal AI providers via multi-dimensional DQ scoring, learns from every session, and evolves its own configuration.

**Version:** 1.2.0
**Stack:** Python 3.8+, Node.js 18+, Bash/zsh
**Database:** SQLite3 (primary), JSONL (append-only logs)
**AI Providers:** Claude (Opus/Sonnet/Haiku), OpenAI GPT-4, Google Gemini 2.0, Ollama (local)

## Architecture

```
APPLICATION    → Claude Code CLI, Claude Desktop, ChatGPT
INTERACTION    → Query Router (DQ Score / HSRGS) → Model Selection
DATA           → Real-time telemetry (sessions, DQ scores, patterns, tools)
ANALYSIS       → Meta-Analyzer, Pattern Detector, DQ Scorer, Cognitive OS, Recovery Engine
MODIFICATION   → Auto-generated CLAUDE.md patterns, prefetch rules, DQ weights
EVOLUTION      → Next session starts better — bidirectional co-evolution flywheel
```

## Directory Structure

```
meta-vengine/
├── kernel/              # Core: DQ scorer, pattern detector, cognitive OS, HSRGS
├── coordinator/         # Multi-agent orchestration (4 strategies)
│   └── strategies/      # parallel_research, parallel_implement, review_build, full
├── config/              # Pricing (JS/Python/JSON/Shell), system config, datastore
├── scripts/             # 100+ utilities: routing, observatory, recovery, prefetch
├── docs/                # Architecture docs, co-evolution docs, migration plans
├── daemon/              # Background daemons (LaunchAgents)
├── hooks/               # Git & bash hooks
├── skills/              # Extensible skill system
├── plugins/             # Plugin system
├── memory/              # Long-term memory (supermemory.db)
├── data/                # Analytics (session-outcomes, routing-metrics, tool-usage)
├── init.sh              # Master init script (sourced from .zshrc)
└── settings.json        # Main system settings
```

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| DQ Scorer | `kernel/dq-scorer.js` | Decision Quality: validity (40%) + specificity (30%) + correctness (30%) |
| Pattern Detector | `kernel/pattern-detector.js` | 8 session types: debugging, research, architecture, refactoring, testing, docs, exploration, creative |
| Cognitive OS | `kernel/cognitive-os.py` | Energy-aware routing (morning/peak/dip/evening/deep_night), flow state tracking |
| HSRGS | `kernel/hsrgs.py` | Homeomorphic Self-Routing Godel System — emergent routing via latent space |
| Identity Manager | `kernel/identity-manager.js` | Expertise tracking per domain |
| Recovery Engine | `scripts/recovery-engine.py` | Self-healing (94% coverage, 70% auto-fix, 8 patterns) |
| Meta-Analyzer | `scripts/meta-analyzer.py` | Co-evolution analysis and improvement proposals |
| Coordinator | `coordinator/orchestrator.py` | Multi-agent orchestration (research/implement/review/full) |
| Context Budget | `kernel/context-budget.js` | Token budget management |
| Activity Tracker | `kernel/activity-tracker.js` | Real-time session telemetry |

## Commands

```bash
# Routing
uni-ai "query"                    # Auto-routed via DQ/HSRGS
routing-dash                      # Performance dashboard

# Co-evolution
coevo-analyze                     # Analyze patterns
coevo-propose                     # Generate improvement proposals
coevo-apply <mod_id>              # Apply modifications (--dry-run available)
coevo-dashboard                   # Effectiveness over time

# Multi-agent coordination
coord research "task"             # 3 parallel explore agents
coord implement "task"            # Parallel builders with file locks
coord review "task"               # Build + review concurrent
coord full "task"                 # Research → Build → Review pipeline
coord team "task"                 # Opus 4.6 agent team
coord status                      # Check status

# Cognitive OS
cos state                         # Current cognitive mode and energy
cos flow                          # Flow state (0-1)
cos fate                          # Session outcome prediction
cos route "task"                  # Model routing recommendation

# Observatory
obs N                             # N-day unified report
productivity-report N             # Productivity metrics
tool-stats N                      # Tool success rates

# Memory
sm stats                          # Memory statistics
sm context                        # Generate session context
sm errors "text"                  # Find past error solutions

# Recovery
python3 scripts/recovery-engine.py status    # Recovery stats
python3 scripts/recovery-engine.py test git  # Test git recovery

# Dashboard
ccc                               # Open Command Center (12-tab HTML dashboard)
```

## Testing

```bash
pytest scripts/observatory/qa-test-suite.py     # Observatory tests
python3 scripts/test-dashboard-sqlite.py         # Dashboard data tests
python3 scripts/ab-test-analyzer.py --detailed   # A/B test analysis (HSRGS vs keyword DQ)
```

## Key Data Files

| File | Format | Purpose |
|------|--------|---------|
| `kernel/dq-scores.jsonl` | JSONL | DQ routing decision history |
| `kernel/baselines.json` | JSON | Model performance baselines |
| `data/session-outcomes.jsonl` | JSONL | ACE session quality analysis |
| `data/routing-metrics.jsonl` | JSONL | Routing effectiveness history |
| `data/tool-usage.jsonl` | JSONL | Tool success rates |
| `memory/supermemory.db` | SQLite | Long-term memory with spaced repetition |
| `settings.json` | JSON | Main system config |
| `config/pricing.json` | JSON | Model pricing and capabilities |

## Design Principles

1. **Bidirectional co-evolution** — system reads its own patterns and modifies its own instructions
2. **Sovereignty by design** — all data local, bounded recursion, human approval for changes
3. **No external frameworks** — vanilla JS + stdlib Python (zero dependency risk)
4. **Append-only telemetry** — JSONL logs never overwritten, only appended
5. **Safe-path validation** — recovery engine only touches `~/.claude/`, `~/.agent-core/`

## Current Metrics

- DQ Score average: 0.889 (158 samples)
- Cache efficiency: 99.88%
- Recovery coverage: 94% (655/700 errors)
- Auto-fix rate: 70% (no human intervention)
- Session types tracked: 8
