# Claude Observatory 🔭

> Comprehensive metrics, analytics, and insights for your Claude Code workflow

## Overview

Claude Observatory is a complete observability platform that tracks, analyzes, and provides insights on:
- Session outcomes and quality
- Real-time costs and budget management
- Command and tool usage patterns
- Productivity metrics (read/write ratios, LOC)
- Git activity (commits, PRs, velocity)
- Model routing effectiveness
- And more...

## Quick Start

Observatory is automatically initialized when you source `~/.claude/init.sh`.

```bash
# View unified report (all metrics)
obs

# View specific reports
cost-report 7           # Last 7 days costs
productivity-report 7   # Productivity metrics
tool-stats 7            # Tool success rates
command-stats 7         # Command usage
git-stats 7             # Git activity

# Session management
session-rate 5 "Great session!"   # Rate current session
session-stats                     # View session history

# Daily digest
observatory-digest
```

## Architecture

### Data Collection Layer

**Automated Collectors:**
- `session-tracker.sh` - Session outcomes, quality, duration
- `cost-tracker.py` - Real-time cost tracking from transcripts
- `command-tracker.sh` - Command/alias usage
- `tool-tracker.sh` - Bash exit codes, test results, build success
- `productivity-analyzer.py` - Read/write ratios, LOC changes
- `git-tracker.sh` - Commits, pushes, PR creation

**Data Files** (all in `~/.claude/data/`):
```
session-outcomes.jsonl    - Session events
cost-tracking.jsonl       - Cost breakdown
command-usage.jsonl       - Command invocations
tool-success.jsonl        - Tool results
productivity.jsonl        - Productivity snapshots
git-activity.jsonl        - Git events
```

### Analytics Engine

`analytics-engine.py` - Unified analytics across all data sources:
- Comprehensive metrics calculation
- Insight generation
- Anomaly detection
- Trend analysis

### Reporting

- **CLI Reports** - Text-based reports for terminal
- **JSON Export** - Machine-readable exports
- **Command Center Integration** - Visual dashboard
- **Daily Digest** - Automated summaries

## Usage Guide

### Session Tracking

Track session outcomes for quality improvement:

```bash
# Manual completion
session-complete success "Implemented routing system" 5

# Quick rating (auto-detects outcome from quality)
session-rate 4 "Good progress on refactoring"

# Pre-defined helpers
session-success "Fixed all bugs"
session-error "Couldn't reproduce issue"
session-abandon "Out of scope"

# Auto-detection based on git activity
session-auto-complete

# View statistics
session-stats 30
```

**Session Outcomes:**
- `success` - Task completed successfully
- `partial` - Made progress, not finished
- `error` - Encountered blockers
- `abandoned` - Stopped due to scope/priority
- `research` - Exploration/learning session

**Quality Scale:**
- 1 = Terrible, wasted time
- 2 = Poor, little progress
- 3 = OK, some progress
- 4 = Good, solid progress
- 5 = Excellent, major breakthrough

### Cost Tracking

Monitor API costs and budget utilization:

```bash
# Quick budget check
cost-budget

# Detailed report
cost-report 30

# Process all sessions (bulk import)
cost-process 30

# Export as JSON
python3 ~/.claude/scripts/observatory/collectors/cost-tracker.py export 30
```

**Metrics:**
- Total cost (USD)
- Cost per session
- Monthly projection
- Budget utilization (vs $200/mo subscription)
- ROI multiplier

### Productivity Analytics

Measure coding effectiveness:

```bash
# Generate report
productivity-report 7

# Manual snapshot
productivity-log
```

**Metrics:**
- Read/Write ratio (exploration vs creation)
- Files modified
- Lines of code changed (via git)
- Productivity score (writes/reads)
- Coding velocity (LOC/hour)

**Productivity Assessment:**
- Read/Write > 100:1 → "Read-heavy (exploration mode)"
- Read/Write 20:1-100:1 → "Learning/researching"
- Read/Write 10:1-20:1 → "Balanced productivity"
- Read/Write < 10:1 → "High productivity mode"

### Tool Success Tracking

Monitor command success rates:

```bash
# View tool statistics
tool-stats 7

# Tracked automatically:
# - Bash command exit codes
# - Test results (pytest, jest, vitest)
# - Build outcomes (npm, make, cargo)
```

**Metrics:**
- Overall success rate
- Success by tool type (bash, test, build, git)
- Failure patterns
- Retry detection

### Command Usage Analytics

See which commands you actually use:

```bash
# View command statistics
command-stats 7
```

**Tracked Commands:**
- Model selection: cq, cc, co, claude
- Dashboards: ccc, routing-dash, cterm
- Git: gsave, gsync, cgit
- Routing: routing-report, routing-targets
- Co-evolution: coevo-analyze, coevo-propose
- Feedback: ai-good, ai-bad

### Git Activity Tracking

Monitor code commits and velocity:

```bash
# View git statistics
git-stats 7

# Tracked git commands (use instead of native git)
gcommit -m "message"      # Tracked commit
gpush                     # Tracked push
gsave "message"          # Tracked add + commit
gsync                    # Tracked pull + push
create-tracked-pr "title" "body"  # Tracked PR creation
```

**Metrics:**
- Total commits
- Pushes
- PRs created
- Files changed per commit
- Lines changed per commit
- Commit velocity (commits/day)

### Unified Analytics

Get the complete picture:

```bash
# Quick unified report
obs

# Detailed report (30 days)
obs 30

# Daily digest
observatory-digest

# Export as JSON
observatory-export 7
```

**Unified Metrics:**
- All session, cost, command, tool, git, routing metrics
- Cross-metric insights
- Anomaly detection
- Actionable recommendations

## Integration

### Automatic Tracking

Observatory hooks into your workflow automatically:

**Session Auto-Start:**
- Detects Claude sessions via `$CLAUDE_SESSION_ID`
- Starts tracking automatically

**Bash Command Tracking:**
- Hooks: `preexec` (capture command) + `precmd` (capture exit code)
- Tracks all bash commands, test runs, builds

**Git Auto-Tracking:**
- Use `gcommit`, `gpush`, `gsave`, `gsync` for tracked operations
- PR creation tracked via `create-tracked-pr` or `/pr` skill

**Daily Snapshots:**
- Runs automatically once per day on shell startup
- Non-blocking background process

### Command Center Integration

All Observatory metrics are displayed in the Command Center dashboard:

```bash
ccc  # Open Command Center

# New tabs:
# - Session Outcomes (success rates, quality trends)
# - Cost Tracking (budget, projections, ROI)
# - Productivity (read/write ratios, velocity)
# - Tool Analytics (success rates by type)
# - Command Usage (top commands, patterns)
```

## Advanced Features

### A/B Testing

Test different workflows and compare metrics:

```bash
# Example: Test different coding approaches
session-rate 5 "Approach A: TDD" && approach="A"
session-rate 3 "Approach B: Quick prototype" && approach="B"

# Compare session outcomes over time
session-stats 30 | grep "success"
```

### Custom Metrics

Add your own tracking:

```python
# In any Python script
import json
from pathlib import Path

def log_custom_metric(event, data):
    log_file = Path.home() / ".claude/data/custom-metrics.jsonl"
    entry = {"ts": int(time.time()), "event": event, **data}
    with open(log_file, 'a') as f:
        f.write(json.dumps(entry) + '\n')

# Usage
log_custom_metric("feature_complete", {"feature": "routing", "loc": 500})
```

### Data Export

Export data for external analysis:

```bash
# Export all data as JSON
observatory-export 30 > ~/observatory-data.json

# Export specific sources
python3 ~/.claude/scripts/observatory/collectors/cost-tracker.py export 30
python3 ~/.claude/scripts/observatory/collectors/productivity-analyzer.py report 30
```

## Insights & Recommendations

Observatory generates actionable insights:

**Session Insights:**
- Low success rate → Break down complex tasks
- Low quality scores → Set clearer objectives
- Long durations → Consider /clear to manage context

**Cost Insights:**
- >80% budget used → Optimize model selection
- <20% budget used → Underutilizing subscription
- High Opus usage → DQ routing could save costs

**Productivity Insights:**
- High read/write ratio → More output needed
- Low LOC velocity → Increase commit frequency
- Few files modified → Scope too narrow?

**Tool Insights:**
- Low success rate → Review error patterns
- Frequent retries → Workflow optimization needed
- Build failures → Add pre-commit checks

**Git Insights:**
- Low commit rate → Create more checkpoints
- High velocity → Great momentum!
- No PRs → Consider code review workflow

## Configuration

Edit `~/.claude/scripts/observatory/config.json`:

```json
{
  "collectors": {
    "session_outcomes": {"enabled": true},
    "cost_tracking": {"enabled": true, "budget": {"monthly": 200}},
    "command_usage": {"enabled": true},
    "tool_success": {"enabled": true},
    "productivity": {"enabled": true},
    "git_activity": {"enabled": true}
  },
  "analysis": {
    "daily_report": true,
    "weekly_digest": true,
    "anomaly_detection": true
  },
  "privacy": {
    "anonymize_queries": false,
    "retain_days": 90
  }
}
```

## Privacy

- **Query content**: Not stored (only hashes for deduplication)
- **File paths**: Stored for productivity analysis
- **Costs**: Stored at session level
- **Retention**: 90 days default, configurable
- **Local-only**: All data stays on your machine

## Troubleshooting

**Observatory not loading:**
```bash
# Check if sourced
echo $OBSERVATORY_SESSION_START

# Manually load
source ~/.claude/scripts/observatory/init.sh
```

**Missing data:**
```bash
# Check data files exist
ls -lh ~/.claude/data/

# Check permissions
chmod +x ~/.claude/scripts/observatory/collectors/*.py
```

**Metrics not updating:**
```bash
# Manual snapshot
productivity-log
cost-process 1

# Check last snapshot
cat ~/.claude/data/.last-snapshot
```

## Help

```bash
# Quick help
obs-help

# Tool-specific help
python3 ~/.claude/scripts/observatory/collectors/cost-tracker.py
python3 ~/.claude/scripts/observatory/collectors/productivity-analyzer.py
python3 ~/.claude/scripts/observatory/analytics-engine.py
```

## Examples

**Daily Workflow:**
```bash
# Morning: Check yesterday's metrics
observatory-digest

# During work: Sessions auto-tracked
# (no manual action needed)

# End of day: Rate session
session-rate 4 "Productive day, implemented 3 features"

# Check budget status
cost-budget
```

**Weekly Review:**
```bash
# Comprehensive review
obs 7

# Specific deep-dives
cost-report 7
productivity-report 7
git-stats 7
```

**Monthly Analysis:**
```bash
# Full month metrics
obs 30

# Export for external analysis
observatory-export 30 > ~/monthly-report.json

# Process all costs
cost-process 30
```

## Roadmap

- [ ] Machine learning session classification
- [ ] Predictive cost modeling
- [ ] Research integration tracking
- [ ] Team collaboration metrics
- [ ] Automated insight notifications
- [ ] Custom metric builders
- [ ] API for external tools

---

**Observatory Version:** 1.0.0
**Last Updated:** 2026-01-19
**Documentation:** [Observatory README](~/.claude/OBSERVATORY_README.md)
