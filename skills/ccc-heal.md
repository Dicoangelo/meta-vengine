---
name: ccc-heal
description: Always-on self-healing infrastructure for Claude Command Center
---

# CCC Self-Healing Skill

When the user runs `/ccc-heal`, show infrastructure status and offer healing options.

## Immediate Actions

1. **Show current status**:
   ```bash
   bash ~/.claude/scripts/ccc-status.sh
   ```

2. **If issues detected, auto-fix**:
   ```bash
   python3 ~/.claude/scripts/ccc-self-heal.py --fix
   ```

## Always-On Architecture

The CCC now uses a **watchdog architecture** that ensures infrastructure never goes down:

### Protection Layers

| Layer | Component | Function |
|-------|-----------|----------|
| 1 | **Watchdog** | Runs every 60s, reloads any dead daemon |
| 2 | **KeepAlive** | launchd auto-restarts watchdog if it dies |
| 3 | **Bootstrap** | Runs on every login, loads everything |
| 4 | **Wake Hook** | Triggers after sleep, reloads everything |
| 5 | **Self-Heal** | Runs every 6h, deep health check |

### Daemon Status

All daemons should show as loaded:
- `com.claude.watchdog` - Guardian (every 60s)
- `com.claude.dashboard-refresh` - Dashboard updates (60s)
- `com.claude.supermemory` - Memory maintenance (daily)
- `com.claude.session-analysis` - Session analysis (30m)
- `com.claude.autonomous-maintenance` - Auto-maintenance (1h)
- `com.claude.self-heal` - Deep health check (6h)
- `com.claude.bootstrap` - Login loader
- `com.claude.wake-hook` - Sleep recovery

### Self-Healing Loop

```
System Start → Bootstrap loads all daemons
     ↓
Watchdog runs every 60s
     ↓
Daemon down? → Watchdog reloads it immediately
     ↓
Watchdog dies? → KeepAlive restarts it
     ↓
System sleeps → Wake Hook triggers Bootstrap
     ↓
Loop continues...
```

## Quick Commands

```bash
ccc-status        # Show all daemon status
ccc-fix           # Auto-fix all issues
ccc-heal          # Run healing check
ccc-bootstrap     # Reload everything
ccc-watchdog-log  # Watch live watchdog activity
```

## Timezone

All timestamps use **Eastern Time (America/New_York)** - auto-handles EST/EDT transitions.

## What Gets Monitored

### Daemons (Critical)
- Checks every 60 seconds
- Auto-reload on failure
- macOS notification on heal

### Data Freshness
- Dashboard HTML (max 1h stale)
- Kernel data (max 24h stale)
- Stats cache (max 12h stale)

### Database Health
- Memory links count
- JSONL file integrity

### System Health
- Stale lock cleanup
- Log rotation

## Logs

All activity logged to:
- `~/.claude/logs/watchdog.log` - Watchdog activity
- `~/.claude/logs/bootstrap.log` - Startup events
- `~/.claude/logs/self-heal.log` - Deep health checks
- `~/.claude/data/self-heal-outcomes.jsonl` - Historical data

## Recovery Commands

If everything breaks:
```bash
# Nuclear option - reload entire infrastructure
bash ~/.claude/scripts/ccc-bootstrap.sh

# Check what's running
launchctl list | grep com.claude

# Manual daemon load
launchctl load ~/Library/LaunchAgents/com.claude.watchdog.plist
```
