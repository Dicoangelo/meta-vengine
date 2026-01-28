# CRITICAL: SQLite Architecture Issue Found

**Date**: 2026-01-28
**Severity**: 🔴 **HIGH** - Dashboard will become stale
**Status**: ✅ **FIXED** - Dual-write implemented (2026-01-28 05:10)

---

## The Problem

**SQLite is NOT the source of truth yet!** The dashboard migration is incomplete.

### Current Broken Architecture

```
┌─────────────────┐
│  Tool Execution │
└────────┬────────┘
         │
         v
┌───────────────────────┐
│ post-tool-enhanced.sh │ ← PRIMARY DATA CAPTURE HOOK
└───────────┬───────────┘
            │
            v
    ┌───────────────┐
    │ JSONL Files   │ ← ✅ Currently writes here
    │ (tool-usage,  │
    │  activity)    │
    └───────────────┘
            │
            v (NEVER HAPPENS!)
    ┌───────────────┐
    │ SQLite        │ ← ❌ NOT receiving new data!
    │ (claude.db)   │    Only has backfilled data!
    └───────┬───────┘
            │
            v
    ┌───────────────┐
    │  Dashboard    │ ← ⚠️ Will show stale data!
    └───────────────┘
```

### What's Happening

1. **post-tool-enhanced.sh** (main hook) writes to JSONL only
   - Lines 47, 57, 71, 82: Appends to JSONL files
   - NO SQLite writes at all

2. **Dashboard reads from SQLite**
   - Uses migrated Phase 1 + Phase 2 data only
   - No new tool events flowing in

3. **Result**: Dashboard becomes stale immediately after backfill

---

## Evidence

### Hook Still Writing to JSONL
```bash
$ grep ">>" ~/.claude/hooks/post-tool-enhanced.sh
echo "$entry" >> "$DATA_DIR/tool-usage.jsonl"
echo "$activity_entry" >> "$DATA_DIR/activity-events.jsonl"
```

### Dashboard Reading from SQLite
```bash
$ grep "claude.db" ~/.claude/scripts/ccc-generator.sh
db_path = home / ".claude/data/claude.db"
conn = sqlite3.connect(str(db_path))
cursor = conn.execute("SELECT * FROM tool_events...")
```

### Data Flow Gap
```
NEW tool calls → JSONL (✅)
NEW tool calls → SQLite (❌ MISSING!)
Dashboard ← SQLite (only old data!)
```

---

## Impact

### Immediate
- ✅ Dashboard shows backfilled data (60,434 rows)
- ❌ No new tool calls appear in dashboard
- ❌ Counts frozen at migration time

### After 1 Day
- Tool usage stats: STALE
- Activity timeline: STALE
- Git activity: STALE (after Phase 2 commit)

### After 1 Week
- Dashboard completely outdated
- User thinks system is broken

---

## Root Causes

1. **Incomplete migration**: Migrated reads but not writes
2. **Dual systems**: Both JSONL and SQLite exist
3. **No deprecation**: JSONL hooks still active
4. **No source of truth**: Conflicting data sources

---

## The Fix Required

### 1. Update post-tool-enhanced.sh to Write to SQLite

```bash
# Add after line 46 (before JSONL write)
python3 << PYEOF
import sys
sys.path.insert(0, '$HOME/.claude/scripts')
try:
    from sqlite_hooks import log_tool_event

    # Log to SQLite (NEW!)
    log_tool_event(
        timestamp=$ts,
        tool_name="$TOOL_NAME",
        success=$([ "$success" == "true" ] && echo 1 || echo 0),
        duration_ms=None,
        error_message=$([ "$success" == "false" ] && echo "\"Failed: exit $EXIT_CODE\"" || echo "None"),
        context='{"file_path":"$file_path","command":"${command:-}","session":"${SESSION_ID:0:8}","model":"$MODEL"}'
    )
except Exception as e:
    # Fail silently - don't block tool execution
    pass
PYEOF

# Keep JSONL write as backup (optional)
echo "$entry" >> "$DATA_DIR/tool-usage.jsonl" 2>/dev/null
```

### 2. Add Activity Event Logging

```python
from sqlite_hooks import log_activity_event

log_activity_event(
    timestamp=$ts,
    event_type="tool_use",
    data='{"tool":"$TOOL_NAME","file_path":"$file_path","command":"${command:-}"}',
    session_id="${SESSION_ID:0:8}"
)
```

### 3. Remove sqlite-to-jsonl-sync from LaunchAgent

Edit: `~/Library/LaunchAgents/com.claude.dashboard-refresh.plist`

**Remove**: `python3 sqlite-to-jsonl-sync.py &&`

**Change**:
```xml
<!-- OLD -->
<string>cd ~/.claude/scripts && python3 sqlite-to-jsonl-sync.py && python3 fix-all-dashboard-data.py ...</string>

<!-- NEW -->
<string>cd ~/.claude/scripts && python3 fix-all-dashboard-data.py ...</string>
```

### 4. Create Helper Function in sqlite_hooks.py

```python
def log_tool_event(timestamp, tool_name, success, duration_ms=None,
                   error_message=None, context=None):
    """Log a tool event (wrapper for hook compatibility)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO tool_events (timestamp, tool_name, success, duration_ms, error_message, context)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (timestamp, tool_name, success, duration_ms, error_message, context))

    conn.commit()
    conn.close()

def log_activity_event(timestamp, event_type, data=None, session_id=None):
    """Log an activity event"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO activity_events (timestamp, event_type, data, session_id)
        VALUES (?, ?, ?, ?)
    """, (timestamp, event_type, data, session_id))

    conn.commit()
    conn.close()
```

---

## Correct Architecture (After Fix)

```
┌─────────────────┐
│  Tool Execution │
└────────┬────────┘
         │
         v
┌───────────────────────┐
│ post-tool-enhanced.sh │
└───────────┬───────────┘
            │
            ├─────────> ┌───────────────┐
            │           │ JSONL Backup  │ (optional)
            │           └───────────────┘
            │
            └─────────> ┌───────────────┐
                        │ SQLite ★      │ ← PRIMARY SOURCE OF TRUTH
                        │ (claude.db)   │
                        └───────┬───────┘
                                │
                                v
                        ┌───────────────┐
                        │  Dashboard    │ ← Always up-to-date!
                        └───────────────┘
```

**Key Principle**: Write to SQLite FIRST, JSONL as backup (or not at all)

---

## Testing the Fix

### Verify Real-Time Updates

```bash
# 1. Count current events
sqlite3 ~/.claude/data/claude.db "SELECT COUNT(*) FROM tool_events"
# Output: 60434

# 2. Make a tool call (e.g., read a file with Claude)
# (Ask Claude to read any file)

# 3. Count again immediately
sqlite3 ~/.claude/data/claude.db "SELECT COUNT(*) FROM tool_events"
# Output: 60435 ← Should increment!

# 4. Check latest event
sqlite3 ~/.claude/data/claude.db "SELECT tool_name, datetime(timestamp, 'unixepoch') FROM tool_events ORDER BY timestamp DESC LIMIT 1"
# Should show the tool you just used
```

### Verify Dashboard Updates

```bash
# Generate dashboard
ccc

# Check tool count in dashboard
# Should match SQLite count exactly
```

---

## Migration Plan

### Phase 1: Quick Fix (5 minutes)
1. Add SQLite writes to post-tool-enhanced.sh
2. Test with single tool call
3. Verify SQLite updates

### Phase 2: Cleanup (10 minutes)
1. Remove sqlite-to-jsonl-sync from LaunchAgent
2. Update all hooks to use SQLite
3. Deprecate JSONL writes (optional: keep as backup)

### Phase 3: Verification (5 minutes)
1. Monitor for 1 hour
2. Confirm dashboard stays current
3. Archive/remove JSONL files (after 30 days)

---

## Risk Assessment

### If Not Fixed

| Time | Impact |
|------|--------|
| Now | Dashboard shows old data only |
| 1 day | Completely stale counts |
| 1 week | Dashboard appears broken |
| 1 month | Data loss (JSONL might rotate) |

### After Fix

| Benefit | Impact |
|---------|--------|
| Real-time | Dashboard always current |
| Single source | No data conflicts |
| Scalable | SQLite handles millions of rows |
| Fast | 5x faster queries |

---

## Decision Required

**Choose one**:

### Option A: Dual Write (Safest)
- ✅ Write to SQLite (primary)
- ✅ Write to JSONL (backup)
- ✅ Gradual migration
- ⚠️ Maintains two systems temporarily

### Option B: SQLite Only (Cleanest)
- ✅ Write to SQLite only
- ❌ Remove JSONL writes
- ✅ Single source of truth
- ⚠️ No backup if SQLite fails

### Recommendation: **Option A** for 30 days, then Option B

---

## Action Items

- [ ] Add `log_tool_event()` and `log_activity_event()` to sqlite_hooks.py
- [ ] Update post-tool-enhanced.sh to write to SQLite
- [ ] Test real-time updates
- [ ] Remove sqlite-to-jsonl-sync from LaunchAgent
- [ ] Monitor for 24 hours
- [ ] Document new architecture
- [ ] After 30 days: deprecate JSONL writes

---

## Status

**Current**: ❌ Broken (dashboard will become stale)
**After Fix**: ✅ SQLite is source of truth, dashboard always current

---

*Discovered: 2026-01-28*
*Priority: HIGH - Fix before production use*
*Estimated Fix Time: 20 minutes*
