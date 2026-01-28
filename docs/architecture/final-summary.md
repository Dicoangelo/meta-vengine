# ROOT CAUSE ANALYSIS: Auto-Capture Failure

## The Problem

You had to backfill **47,199 tool calls**, **373 errors**, **200 flow measurements**, and more - all of which SHOULD have been captured automatically in real-time.

## Root Cause

**Architectural disconnect** between data capture and data consumption:

```
Hooks (working) → SQLite DB → ❌ NO BRIDGE ❌ → JSONL files ← Dashboard
```

### What Was Happening

1. **Hooks WERE firing** - settings.json line 350-590 configured:
   - PostToolUse hooks for every tool (Write, Edit, Bash, Read, etc.)
   - SessionStart hooks (9 scripts running on session start)
   - SessionEnd hooks (14 scripts running on session end)

2. **Data WAS being captured** - 9,398 events in `~/.agent-core/storage/antigravity.db`

3. **Dashboard couldn't see it** - Dashboard reads from:
   - `tool-usage.jsonl`
   - `errors.jsonl`
   - `session-events.jsonl`
   - `activity-events.jsonl`

4. **No sync existed** - SQLite events never made it to JSONL files

## The Fix

Created `sqlite-to-jsonl-sync.py` - a bridge that:
- Reads new events from SQLite (incremental, tracks last sync timestamp)
- Writes to JSONL files the dashboard expects
- Runs every 60 seconds via LaunchAgent
- Added to `ccc` alias for manual refresh

### Results

```
SQLite DB:          9,398 events (real-time capture working!)
tool-usage.jsonl:   56,379 lines (includes historical backfill + live sync)
session-events.jsonl: 815 lines
activity-events.jsonl: 17,011 lines
```

## Now Truly Autonomous

✅ **Real-time capture** - Hooks write to SQLite every tool use  
✅ **Automatic sync** - Daemon exports SQLite → JSONL every 60s  
✅ **Dashboard updates** - LaunchAgent rebuilds dashboard every 60s  
✅ **No backfill needed** - All future data auto-captured

## Files Changed

1. **Created**: `~/.claude/scripts/sqlite-to-jsonl-sync.py`
2. **Updated**: `~/Library/LaunchAgents/com.claude.dashboard-refresh.plist`
3. **Updated**: `~/.zshrc` (ccc alias)

## Pipeline Flow

```
Tool Use
  ↓
Hook fires (PostToolUse)
  ↓
sqlite-hook.py writes to antigravity.db (real-time)
  ↓
sqlite-to-jsonl-sync.py exports (every 60s)
  ↓
tool-usage.jsonl updated
  ↓
integrate-untracked-data.py processes
  ↓
Dashboard displays (ccc)
```

**End-to-end latency: ~60 seconds**  
**Manual refresh: `ccc` (immediate)**
