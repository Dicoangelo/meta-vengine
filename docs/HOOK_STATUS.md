# Hook Status - What's Tracked in Real-Time

**Last Updated**: 2026-01-28
**Status**: ✅ Hooks active, SQLite sync working

## Summary

Claude Code hooks have limited access to tool details for security reasons. We use a hybrid approach:

1. **Real-Time Hooks** → SQLite (fast, basic info)
2. **SQLite Sync** → JSONL files (enriches with metadata)
3. **Backfill** → Full details from transcripts (runs during `ccc`)

## What IS Hooked (Real-Time) ✅

These are captured immediately via `sqlite-hook.py`:

| Data Point | Source | Status |
|------------|--------|--------|
| Tool name | `CLAUDE_TOOL_NAME` | ✅ Hooked |
| Timestamp | System time | ✅ Hooked |
| Session ID | Derived from PWD | ✅ Hooked |
| Success/Failure | Exit code + output | ✅ Hooked (new!) |
| Model | `CLAUDE_MODEL` env var | ✅ Hooked |
| File path (Write/Edit) | `$CLAUDE_FILE_PATH` arg | ⚠️ Partial |

**Files written to in real-time:**
- `~/.agent-core/storage/antigravity.db` (SQLite - primary)
- `~/.claude/data/tool-usage.jsonl` (via hook)
- `~/.claude/data/tool-success.jsonl` (via hook)
- `~/.claude/data/activity-events.jsonl` (via hook)

## What is NOT Hooked (Backfill Only) ❌

These require transcript parsing and are captured during backfill:

| Data Point | Why Not Hooked | Captured By |
|------------|----------------|-------------|
| Bash command text | `CLAUDE_TOOL_INPUT` not exposed to hooks | Backfill |
| File path details | Arg passing issues | Backfill |
| Tool input parameters | Security restriction | Backfill |
| Tool output content | Security restriction | Backfill |
| Detailed error messages | Security restriction | Backfill |

**When backfill runs:**
- Every time you run `ccc` command
- During session end (session-optimizer-stop.sh)
- During autonomous maintenance (6am, 6pm daily)

## Current Backfill Stats

From last `ccc` run:
```
Integrating untracked data sources...
  ✅ Processed 373 errors
  ✅ Processed 59,766 tool calls  ← These had missing details
  ✅ Processed 69,768 activity events
  ✅ Processed 150 recovery attempts
  ✅ Processed 200 flow measurements
  ✅ Processed 195 commands  ← Bash commands extracted
  ✅ Processed 257 tool success records
```

**Why so many**: Historical data from before hooks were enhanced. New sessions will have much lower backfill counts.

## How It Works

### Real-Time Path (Fast)

```
Claude Code Tool Use
       ↓
sqlite-hook.py (PostToolUse hook)
       ↓
antigravity.db (SQLite)
       ├→ Stores: tool, timestamp, metadata JSON
       └→ Writes: basic info to tool-usage.jsonl
```

### Sync Path (Every minute)

```
antigravity.db
       ↓
sqlite-to-jsonl-sync.py (every minute)
       ↓
Parses metadata JSON
       ├→ tool-usage.jsonl (updated with metadata)
       ├→ tool-success.jsonl (success rates)
       ├→ command-usage.jsonl (bash commands from metadata)
       └→ activity-events.jsonl (enriched events)
```

### Backfill Path (Periodic)

```
~/.claude/history.jsonl (transcripts)
       ↓
integrate-untracked-data.py (during ccc)
       ↓
Extract full tool details
       ├→ tool-usage.jsonl (WITH bash commands)
       ├→ command-usage.jsonl (all bash commands)
       ├→ tool-success.jsonl (from output analysis)
       └→ activity-events.jsonl (full context)
```

## Files Modified Today

### Enhanced for Real-Time Tracking

1. **`hooks/sqlite-hook.py`** - Now captures:
   - Success/failure from exit codes
   - Metadata JSON field for future enrichment
   - Writes to tool-success.jsonl in real-time

2. **`scripts/sqlite-to-jsonl-sync.py`** - Now extracts:
   - Command text from metadata JSON
   - Success status from metadata
   - File paths from metadata
   - Writes to command-usage.jsonl

### Files That Track Data

| File | Size | Purpose | Updated By |
|------|------|---------|------------|
| `antigravity.db` | 1.1MB | Master SQLite database | sqlite-hook.py (real-time) |
| `claude.db` | 404KB | Aggregated stats | backfill/analytics |
| `tool-usage.jsonl` | Growing | Tool usage log | Hook + sync + backfill |
| `command-usage.jsonl` | 195 lines | Bash commands | Hook + sync + backfill |
| `tool-success.jsonl` | 291 lines | Success rates | Hook + sync + backfill |
| `activity-events.jsonl` | Growing | Activity timeline | Hook + sync + backfill |

## Why the Hybrid Approach?

**Real-time hooks are limited** because:
- Claude Code doesn't expose `CLAUDE_TOOL_INPUT` to hooks (security)
- Environment variable passing has issues
- Hooks must be fast (<3s timeout)

**SQLite is fast** but:
- Dashboard reads JSONL files (historical reasons)
- Sync keeps both in sync

**Backfill fills gaps**:
- Extracts full details from transcripts
- Runs periodically (not blocking)
- Catches anything hooks missed

## Monitoring Hook Status

```bash
# Check recent tool events in SQLite
sqlite3 ~/.agent-core/storage/antigravity.db \
  "SELECT tool, file_path, metadata FROM tool_events ORDER BY id DESC LIMIT 5"

# Check sync status
cat ~/.claude/data/sqlite-sync-state.json

# Run sync manually
python3 ~/.claude/scripts/sqlite-to-jsonl-sync.py

# Check backfill age
head -1 ~/.claude/data/tool-usage.jsonl
tail -1 ~/.claude/data/tool-usage.jsonl
```

## Future Improvements

**Possible** if Claude Code exposes more env vars:
- Real-time bash command capture
- Real-time file path capture for all tools
- Real-time tool input/output capture

**Current workaround**:
- Run `ccc` frequently to keep data fresh
- Backfill happens automatically during session end
- SQLite sync runs every minute via LaunchAgent

## Bottom Line

**What works now:**
- ✅ Tool names tracked in real-time
- ✅ Success/failure tracked in real-time
- ✅ Fast SQLite storage
- ✅ Auto-sync to JSONL every minute
- ✅ Backfill fills in missing details

**What requires backfill:**
- ❌ Bash command text
- ❌ Detailed file paths
- ❌ Tool input parameters

**Impact**: Dashboard shows accurate tool counts and success rates in real-time, but bash commands and file details appear after backfill (during `ccc` or session end).
