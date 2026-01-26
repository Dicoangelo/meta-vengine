<!-- VERSION: 2.4.0 -->
<!-- LAST_MODIFIED: 2026-01-23T23:00:00Z -->
<!-- CHECKSUM: sha256:capability-invention-update -->

# Session Protocols

## On Session Start

Display this once at the beginning:
```
Cost-aware mode active.
Model: [current model] | /save to log | /clear resets context

━━━ Session Window ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Position: ████████░░ [position]% | [time] remaining
Capacity: [tier] | Opus: [n] | Sonnet: [n] | Haiku: [n]
Budget:   [used]% utilized | Reserve: [n] Opus tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Queue: [n] tasks | Next: [task] @ [schedule]
Prediction: Optimal next window [time] | Pattern: [type]
```

To get current session status, run: `session-status` or check hook output above.

## Cost Efficiency

Track approximate message count. At ~50 messages, suggest `/clear` if context allows. At ~100+, recommend fresh session.

If on Opus doing routine tasks, suggest Sonnet (`cc`). Reserve Opus for complex architecture only.

After major task completions, offer a checkpoint summary:
- What was done
- Files changed
- Next steps

If user sends 3+ small sequential requests, offer to batch them.

## Session End Protocol

When user says "done", "quit", "ending", or similar:
1. Remind them: "Run `/save` to save this session before quitting."

## User Context

- **GitHub: `Dicoangelo`** (ALWAYS use this exact capitalization - never `dicoangelo` or `DICOANGELO`)
- Projects: OS-App, Agentic Kernel, Antigravity ecosystem
- Aliases: `cq` (haiku), `cc` (sonnet), `co` (opus), `cstats`
- Skills: `/cost`, `/save`, `/history`

## Critical Rules (Auto-Enforced)

1. **GitHub Username**: Always `Dicoangelo` - git URL rewriting handles typos automatically
2. **One Session at a Time**: Parallel Claude sessions cause race conditions
3. **Error Tracking**: Errors auto-log to `~/.claude/ERRORS.md`

## Anthropic Products

- **Claude Code**: CLI agent for coding tasks (this tool)
- **Cowork**: Agent for non-coding tasks (research preview, Claude Max, macOS app)
  - Built-in VM isolation, browser automation, claude.ai data connectors
  - Access: Sidebar in Claude desktop app → [claude.com/download](https://claude.com/download)

## Autonomous Routing System

**Status:** ✅ Active | **Version:** 1.0.0 | **Docs:** `~/.claude/ROUTING_SYSTEM_README.md`

### How It Works

The CLI automatically routes queries to the optimal model (Haiku, Sonnet, or Opus) using DQ scoring:
- **Haiku (C: 0.0-0.3):** Simple queries, quick answers, cheap
- **Sonnet (C: 0.3-0.7):** Code generation, analysis, moderate complexity
- **Opus (C: 0.7-1.0):** Architecture, complex reasoning, research

**DQ Score = Validity (40%) + Specificity (30%) + Correctness (30%)**

### Quick Commands

```bash
claude -p "query"              # Auto-routes (let it decide)
routing-dash                   # Performance dashboard
routing-report 7               # Weekly metrics
ai-feedback-enable             # Learn from failures

# Manual override when needed
claude --model opus -p "force opus for complex task"
```

### Key Features

- **Auto-routing:** Transparent decisions shown as `[DQ:0.75 C:0.45] → sonnet`
- **Self-improving:** Learns from feedback, A/B tests optimizations
- **Research-driven:** Weekly arXiv sync updates baselines
- **Auto-update:** Applies validated improvements after 30-day stability

### Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| Routing Accuracy | ≥75% | 🔄 Collecting |
| Cost Reduction | ≥20% vs random | 🔄 Collecting |
| Latency (p95) | <50ms | ✅ ~42ms |

Run `routing-test-suite.py all` to check current performance.

### Documentation

- **Quick Ref:** `~/.claude/ROUTING_QUICK_REFERENCE.md`
- **Full Guide:** `~/.claude/ROUTING_SYSTEM_README.md`
- **Research:** `~/researchgravity/ROUTING_RESEARCH_WORKFLOW.md`

## Multi-Agent Coordinator

**Status:** ✅ Active | **Version:** 1.0.0 | **Docs:** `~/.claude/coordinator/README.md`

### Quick Commands

```bash
# Coordination strategies
coord research "task"     # 3 parallel explore agents
coord implement "task"    # Parallel builders with file locks
coord review "task"       # Build + review concurrent
coord full "task"         # Research → Build → Review pipeline

# Status
coord-summary             # Formatted dashboard
coord status              # JSON output
coord-cleanup             # Clean stale agents
```

### Strategies

| Strategy | Agents | Use Case |
|----------|--------|----------|
| `research` | 3 explore (parallel) | Understanding, investigation |
| `implement` | N builders (parallel/locked) | Multi-file changes |
| `review` | builder + reviewer | Quality-assured implementation |
| `full` | research → build → review | Complete feature development |

### Dashboard

```bash
ccc                       # Open Command Center (auto-refreshes)
```

Dashboard auto-refreshes every 60s via LaunchAgent daemon.

## Cognitive OS

**Status:** ✅ Active | **Docs:** `~/.claude/kernel/cognitive-os/`

Energy-aware task routing based on time-of-day patterns.

```bash
cos state              # Current mode (morning/peak/dip/evening/deep_night)
cos flow               # Flow state detection
cos fate               # Session outcome prediction
cos route "task"       # Cognitive model routing
cos weekly             # Weekly energy map
```

**Your Peak Hours:** 20:00, 12:00, 02:00

## Supermemory

**Status:** ✅ Active | **DB:** `~/.claude/memory/supermemory.db`

Long-term memory with spaced repetition and error pattern tracking.

```bash
sm stats               # Memory statistics
sm context             # Generate session context
sm errors "text"       # Find past error solutions
sm review              # Spaced repetition review
sm project <name>      # Project-specific memory
```

## Observatory

**Status:** ✅ Active | **Docs:** `~/.claude/scripts/observatory/`

Unified analytics engine.

```bash
obs N                  # N-day unified report
tool-stats N           # Tool success rates
productivity-report N  # Productivity metrics
session-analyze-recent # Recent session analysis
```

## Recovery System

**Status:** ✅ Active | **Patterns:** 700+

Auto-fix for common errors (git, locks, permissions). Logs to `~/.claude/ERRORS.md`.

## New Capabilities (2026-01-23)

### Expertise-Aware Routing

Routes based on your tracked expertise. High expertise domains use cheaper models (you need less help), low expertise domains use more capable models.

```bash
exp-detect "query"     # Detect domain and expertise level
exp-route "query" 0.5  # Route with complexity
exp-stats              # Routing statistics
exp-export             # Export expertise state
```

### Pattern Orchestrator

Auto-suggests coordinator strategies based on detected session patterns.

```bash
orchestrate-suggest    # Suggest strategy for current pattern
orchestrate-spawn      # Get spawn command
orchestrate-stats      # Pattern statistics
```

| Pattern | Strategy |
|---------|----------|
| debugging | coord review-build |
| research | coord research |
| architecture | coord full |
| refactoring | coord implement |

### Predictive Error Prevention

Predicts likely errors based on patterns and takes preemptive action at session start.

```bash
predict-run            # Run predictions and prevent
predict-dry            # Dry run (show what would happen)
predict-stats          # Prevention statistics
```

### Learning Hub

Unified aggregation of all learning systems. Weekly sync identifies cross-domain correlations.

```bash
hub-sync               # Run weekly sync
hub-status             # Current hub status
hub-insights           # Cross-domain insights
hub-suggestions        # Improvement suggestions
```

### Flow Shield

Protects deep work by deferring non-critical alerts when flow score > 0.75. Use `/flow-shield` skill.

## Cost Targets

| Metric | Target | Alert |
|--------|--------|-------|
| Daily | $200 | >$300 |
| Cache | >85% | <75% |
| DQ Score | >0.60 | <0.50 |

## Learned Patterns

<!-- AUTO-GENERATED BY META-ANALYZER - DO NOT EDIT MANUALLY -->
<!-- Last Updated: 2026-01-26T01:29:22.235270 -->

### Usage Patterns Observed
- Peak productivity hours: 20:00, 3:00, 2:00
- Dominant session type: architecture (33%)
- Average session length: 141 messages

### Optimized Behaviors
- Use pattern-aware prefetch for faster context loading
- Cache efficiency: 92.92% - maintain by reusing context
- Batch threshold: 3 sequential requests -> suggest batching

<!-- END AUTO-GENERATED -->
