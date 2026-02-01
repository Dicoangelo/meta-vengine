# Supermemory User Guide

**Long-term memory layer for compounding cross-session intelligence.**

## Overview

Supermemory transforms disconnected telemetry into persistent knowledge. It connects:
- 132K+ activity events
- 351+ sessions
- 41+ days of memory
- Orphaned paste/file/shell/debug data

```
┌─────────────────────────────────────────────────────────────┐
│                    SUPERMEMORY LAYER                        │
├─────────────────────────────────────────────────────────────┤
│  Session Intelligence → Pattern Correlation → Knowledge     │
│  Context Linking → Cross-Project Learning → Prediction      │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Commands

```bash
sm stats               # Memory statistics
sm context             # Generate session context
sm errors "text"       # Find past error solutions
sm review              # Spaced repetition review
sm project <name>      # Project-specific memory
sm sync                # Sync all data sources
sm rollup              # Generate weekly summary
sm-due                 # Check review items due
```

---

## CLI Reference

### Briefing - Pre-Session Intelligence

```bash
python3 kernel/supermemory.py briefing
```

Generates a pre-session intelligence briefing with:
- Recent session patterns
- Active projects context
- Pending tasks from memory
- Predicted optimal configuration

### Synthesize - Post-Session Learning

```bash
python3 kernel/supermemory.py synthesize
```

Extracts learnings from the just-completed session:
- Key decisions made
- Errors encountered and solutions
- New patterns discovered
- Project progress updates

### Weekly - Knowledge Consolidation

```bash
python3 kernel/supermemory.py weekly
```

Generates a weekly synthesis:
- Cross-project insights
- Recurring patterns
- Error trends
- Productivity metrics
- Spaced repetition candidates

### Link Context - Connect Orphaned Data

```bash
python3 kernel/supermemory.py link-context
```

Connects orphaned data to session context:
- Paste cache entries
- File history
- Shell snapshots
- Debug artifacts
- Todo items

### Predict - Task Optimization

```bash
python3 kernel/supermemory.py predict "implement auth system"
```

Predicts optimal configuration for a task:
- Recommended model (Haiku/Sonnet/Opus)
- Estimated time/tokens
- Similar past tasks
- Potential blockers

### Status - System Overview

```bash
python3 kernel/supermemory.py status
```

Shows current system status:
- Data source sizes
- Last sync times
- Memory health metrics
- Index coverage

---

## Data Sources

Supermemory aggregates from multiple sources:

| Source | Path | Description |
|--------|------|-------------|
| Activity Events | `~/.claude/data/activity-events.jsonl` | Tool calls, messages |
| Session Outcomes | `~/.claude/data/session-outcomes.jsonl` | ACE analysis results |
| Tool Usage | `~/.claude/data/tool-usage.jsonl` | Tool success rates |
| DQ Scores | `~/.claude/kernel/dq-scores.jsonl` | Routing decisions |
| Knowledge | `~/.claude/memory/knowledge.json` | Facts, decisions, patterns |
| Identity | `~/.claude/kernel/identity.json` | Expertise tracking |
| Detected Patterns | `~/.claude/kernel/detected-patterns.json` | Session type patterns |

---

## Spaced Repetition

Supermemory implements spaced repetition for learning retention:

```bash
sm review              # Start review session
sm-due                 # Check items due
```

Review intervals: 1 day → 3 days → 7 days → 14 days → 30 days

Items include:
- Error patterns and solutions
- Key decisions and rationale
- Architecture insights
- Project-specific learnings

---

## Error Pattern Tracking

Find solutions to past errors:

```bash
sm errors "git merge conflict"
sm errors "ECONNREFUSED"
sm errors "rate limit"
```

Returns:
- Similar past errors
- Solutions that worked
- Prevention strategies
- Related context

---

## Project-Specific Memory

Get context for a specific project:

```bash
sm project os-app
sm project careercoach
sm project researchgravity
```

Returns:
- Recent sessions on that project
- Key decisions made
- Active tasks
- Dependencies and blockers

---

## Output Files

| File | Description |
|------|-------------|
| `~/.claude/kernel/supermemory/current-briefing.json` | Latest pre-session briefing |
| `~/.claude/kernel/supermemory/session-synthesis.jsonl` | Session-by-session learnings |
| `~/.claude/kernel/supermemory/weekly-synthesis.jsonl` | Weekly consolidations |
| `~/.claude/kernel/supermemory/context-index.jsonl` | Orphaned data linkages |
| `~/.claude/kernel/supermemory/predictions.jsonl` | Task prediction history |

---

## Integration

### With Session Start Hook

Supermemory briefing is auto-injected via session start hook:
```bash
# In ~/.claude/hooks/session-start.sh
python3 ~/.claude/kernel/supermemory.py briefing --inject
```

### With Session End Hook

Synthesis runs automatically on session end:
```bash
# In ~/.claude/hooks/session-stop.sh
python3 ~/.claude/kernel/supermemory.py synthesize
```

### With Meta-Analyzer

Weekly rollup feeds into meta-analyzer for CLAUDE.md evolution:
```bash
# In weekly cron
python3 ~/.claude/kernel/supermemory.py weekly
python3 ~/.claude/scripts/meta-analyzer.py
```

---

## Database

SQLite backend at `~/.claude/memory/supermemory.db`:

```sql
-- Tables
learnings          -- Extracted session learnings
error_patterns     -- Error-solution pairs
review_schedule    -- Spaced repetition queue
project_context    -- Per-project memory
session_links      -- Session-to-data linkages
```

---

## Troubleshooting

### Memory Not Syncing

```bash
sm sync --force
```

### High Database Size

```bash
sm cleanup --older-than 90  # Archive entries >90 days
```

### Missing Linkages

```bash
sm link-context --rebuild
```

---

## Part of Meta-Vengine

Supermemory is a kernel component of the **Meta-Vengine closed-loop system**:
- Telemetry flows up from sessions
- Analysis generates insights
- Modifications flow down to improve next session

[Back to Meta-Vengine README](../README.md)
