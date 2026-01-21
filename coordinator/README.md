# Multi-Agent Coordination System

Orchestrate multiple Claude agents for parallel research, implementation, and review.

## Quick Start

```bash
# Research a topic with 3 parallel agents
coord research "How does the authentication system work?"

# Implement with parallel builders (auto file-locking)
coord implement "Add dark mode to all UI components"

# Build + review in parallel
coord review "Implement rate limiting middleware"

# Full pipeline: Research → Build → Review
coord full "Add user preferences feature"

# Check status
coord status
coord-summary  # Formatted dashboard
```

## Architecture

```
USER REQUEST
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                              │
│  1. Decompose task into subtasks                            │
│  2. Detect dependencies (parallel vs sequential)            │
│  3. Check file conflicts                                    │
│  4. Select strategy (research/implement/review/full)        │
└─────────────────────────────────────────────────────────────┘
     │
     ├──────────────┬──────────────┬──────────────┐
     ▼              ▼              ▼              ▼
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ Agent 1 │   │ Agent 2 │   │ Agent 3 │   │ Agent N │
│ haiku   │   │ sonnet  │   │ haiku   │   │ opus    │
│ research│   │ implement│  │ review  │   │ arch    │
└────┬────┘   └────┬────┘   └────┬────┘   └────┬────┘
     │              │              │              │
     └──────────────┴──────────────┴──────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │    ACE CONSENSUS      │
              │  DQ-weighted voting   │
              │  Synthesize results   │
              └───────────────────────┘
```

## Strategies

### 1. Parallel Research (`coord research`)
- Spawns 3 explore agents in parallel
- Each investigates a different angle (architecture, patterns, dependencies)
- All read-only → no conflicts → safe parallel
- Results synthesized via ACE consensus

### 2. Parallel Implementation (`coord implement`)
- Pre-checks file conflicts between agents
- Locks files before spawning builders
- Parallel if no conflicts, sequential fallback if overlap
- Automatic lock release on completion

### 3. Review + Build (`coord review`)
- Builder and reviewer run concurrently
- Builder implements while reviewer analyzes
- Reviewer is read-only → no conflicts
- Combined output with review findings

### 4. Full Orchestration (`coord full`)
```
Phase 1: RESEARCH (parallel)
    └─→ 2-3 explore agents → synthesize context
         │
Phase 2: IMPLEMENT (parallel where possible)
    └─→ N build agents → locked files
         │
Phase 3: REVIEW (parallel)
    └─→ Security + Quality review agents
         │
         ▼
    Final synthesis
```

## Components

| File | Purpose |
|------|---------|
| `orchestrator.py` | Main coordinator - decomposition, strategy, execution |
| `registry.py` | Agent tracking - state, progress, cleanup |
| `distribution.py` | Work assignment - DQ scoring, model selection |
| `conflict.py` | File locking - prevent write conflicts |
| `executor.py` | Agent spawning - CLI subprocess management |
| `coord-summary.sh` | Formatted status dashboard |

### Strategies Directory
| File | Purpose |
|------|---------|
| `strategies/parallel_research.py` | Multiple explore agents |
| `strategies/parallel_implement.py` | Multiple build agents with locks |
| `strategies/review_build.py` | Build + review concurrent |
| `strategies/full_orchestration.py` | Research → Build → Review |

## Data Files

```
~/.claude/coordinator/data/
├── active-agents.json      # Currently running agents
├── file-locks.json         # Active file locks
├── coordination-log.jsonl  # History of coordinations
└── agent-outcomes.jsonl    # Individual agent results
```

## CLI Commands

```bash
# Coordination
coord research "task"     # Parallel exploration
coord implement "task"    # Parallel building
coord review "task"       # Build + review
coord full "task"         # Full pipeline

# Management
coord status              # JSON status output
coord-summary             # Formatted dashboard
coord-cleanup             # Clean stale agents/locks
coord-agents              # List active agents
coord-locks               # Show file locks
```

## Safety Features

| Risk | Mitigation |
|------|------------|
| File conflicts | Pre-spawn conflict detection + file locking |
| Runaway agents | Timeout (300s default) + heartbeat monitoring |
| Token explosion | Cost estimation before spawn |
| Stale locks | Automatic cleanup after 10 min inactivity |
| Agent failures | Graceful degradation + error tracking |

## Integration

### With Claude Code Sessions
Use the native Task tool for in-session multi-agent:
```
# Spawns 3 agents in parallel within current session
Task(subagent_type="Explore", model="haiku", ...)
Task(subagent_type="Explore", model="haiku", ...)
Task(subagent_type="Explore", model="haiku", ...)
```

### With Command Center Dashboard
The coordinator status is displayed in the Cognitive tab:
- Active agents count
- File locks status
- Recent coordinations

## Performance

| Metric | Target |
|--------|--------|
| Parallel speedup | 2-3x for eligible tasks |
| Conflict prevention | 100% (no file overwrites) |
| Agent success rate | >90% |
| Cost efficiency | <15x overhead vs single agent |
