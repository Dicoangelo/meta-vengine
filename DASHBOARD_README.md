# Claude Command Center - Auto-Refresh Dashboard

## Quick Start

```bash
ccc              # Open dashboard (stays live automatically)
coord-summary    # Quick terminal status
```

## Auto-Refresh System

The dashboard automatically refreshes every 60 seconds:

1. **LaunchAgent Daemon** (`com.claude.dashboard-refresh`)
   - Regenerates dashboard HTML every 60s
   - Runs in background, survives reboots
   - Location: `~/Library/LaunchAgents/`

2. **Browser Auto-Reload**
   - Meta refresh tag reloads page every 60s
   - No manual refresh needed

## Data Collection (Automatic)

All data is collected automatically via session hooks:

| Data | Trigger | File |
|------|---------|------|
| Patterns | Session end | `kernel/pattern-history.jsonl` |
| DQ Scores | Session end | `kernel/dq-scores.jsonl` |
| Session Outcomes | Session end | `data/session-outcomes.jsonl` |
| Activity Events | Tool calls | `data/activity-events.jsonl` |

## Dashboard Tabs

1. **Overview** - Key metrics, activity timeline
2. **Memory** - Knowledge graph, facts, decisions
3. **Stats** - Session statistics, model usage
4. **Cognitive** - Flow state, coordinator status
5. **Projects** - Active projects, file activity
6. **Recovery** - Error tracking, auto-fixes
7. **Routing** - DQ scores, model distribution
8. **Co-Evolution** - Pattern trends, session history

## Commands

```bash
# Dashboard
ccc                    # Open Command Center
ccc-generator.sh       # Regenerate manually
coord-summary          # Terminal status

# Daemon Control
launchctl list | grep dashboard    # Check if running
launchctl unload ~/Library/LaunchAgents/com.claude.dashboard-refresh.plist  # Stop
launchctl load ~/Library/LaunchAgents/com.claude.dashboard-refresh.plist    # Start
```

## Files

| File | Purpose |
|------|---------|
| `scripts/ccc-generator.sh` | Dashboard generator |
| `scripts/command-center.html` | Template |
| `dashboard/claude-command-center.html` | Generated output |
| `~/Library/LaunchAgents/com.claude.dashboard-refresh.plist` | Auto-refresh daemon |

## Troubleshooting

**Dashboard not updating?**
```bash
# Check daemon status
launchctl list | grep claude.dashboard

# Restart daemon
launchctl unload ~/Library/LaunchAgents/com.claude.dashboard-refresh.plist
launchctl load ~/Library/LaunchAgents/com.claude.dashboard-refresh.plist

# Manual regenerate
bash ~/.claude/scripts/ccc-generator.sh
```

**Data not appearing?**
- Check session hooks are running: `cat ~/.claude/logs/session-optimizer.log`
- Run backfill: `python3 ~/.claude/scripts/backfill-patterns.py`
