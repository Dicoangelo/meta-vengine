# SQLite Migration - Comprehensive Gaps Audit

**Date**: 2026-01-28 05:15
**Status**: 🔴 **CRITICAL GAPS FOUND**

---

## Executive Summary

The user is 100% correct. While we fixed `post-tool-enhanced.sh`, there are **multiple other scripts still writing ONLY to JSONL** and not to SQLite.

**Impact**: Dashboard will show Phase 1+2 backfilled data correctly, but NEW data from these sources will NOT appear:
- ❌ New routing metrics (from routing decisions)
- ❌ New session outcomes (from post-session analysis)
- ❌ New self-heal events (from autonomous brain)
- ❌ New recovery events (from self-heal system)

---

## Gap Analysis

### ✅ FIXED (Writing to SQLite)

| Data Type | Hook/Script | SQLite Write | Status |
|-----------|-------------|--------------|--------|
| Tool events | post-tool-enhanced.sh | ✅ log_tool_event() | FIXED (commit 3a5dd91) |
| Activity events | post-tool-enhanced.sh | ✅ log_activity_event_simple() | FIXED (commit 3a5dd91) |
| Git commits | git-post-commit.sh | ✅ log_git_commit() | Working (Phase 2) |

### ❌ NOT FIXED (Still writing ONLY to JSONL)

| Data Type | Script | JSONL File | SQLite Table | Status |
|-----------|--------|------------|--------------|--------|
| **Routing metrics** | claude-wrapper.sh | routing-metrics.jsonl | routing_metrics_events | ❌ NOT HOOKED |
| **Routing metrics** | routing-feedback.py | routing-metrics.jsonl | routing_metrics_events | ❌ NOT HOOKED |
| **Session outcomes** | observatory/post-session-analyzer.py | session-outcomes.jsonl | session_outcome_events | ❌ NOT HOOKED |
| **Session outcomes** | hooks/session-optimizer-stop.sh | session-outcomes.jsonl | session_outcome_events | ❌ NOT HOOKED |
| **Self-heal** | ccc-autonomous-brain.py | self-heal-outcomes.jsonl | self_heal_events | ❌ NOT HOOKED |
| **Recovery** | ccc-self-heal.py | recovery-outcomes.jsonl | recovery_events | ❌ NOT HOOKED |
| **Recovery** | meta-analyzer.py | recovery-outcomes.jsonl | recovery_events | ❌ NOT HOOKED |

---

## Detailed Findings

### 1. Routing Metrics (❌ NOT WRITING TO SQLITE)

**Scripts writing ONLY to JSONL**:
- `scripts/claude-wrapper.sh` - Line: `METRICS_LOG="$HOME/.claude/data/routing-metrics.jsonl"`
- `scripts/routing-feedback.py` - Line: `ROUTING_FILE = HOME / ".claude/data/routing-metrics.jsonl"`

**SQLite table exists**: `routing_metrics_events` (backfilled with 1,592 rows)

**Hook function available**: `log_routing_metric()` in sqlite_hooks.py

**Impact**: New routing decisions won't appear in dashboard

---

### 2. Session Outcomes (❌ NOT WRITING TO SQLITE)

**Scripts writing ONLY to JSONL**:
- `scripts/observatory/post-session-analyzer.py` - Line 430: `f.write(json.dumps(entry) + '\n')`
- `hooks/session-optimizer-stop.sh` - Writes to session-outcomes.jsonl

**SQLite table exists**: `session_outcome_events` (backfilled with 701 rows)

**Hook function available**: Need to create `log_session_outcome()` in sqlite_hooks.py

**Impact**: New session analyses won't appear in SESSION OUTCOMES tab

---

### 3. Self-Heal Events (❌ NOT WRITING TO SQLITE)

**Scripts writing ONLY to JSONL**:
- `scripts/ccc-autonomous-brain.py` - Writes to self-heal-outcomes.jsonl

**SQLite table exists**: `self_heal_events` (backfilled with 1,195 rows)

**Hook function available**: `log_self_heal()` in sqlite_hooks.py ✅

**Impact**: New self-heal events won't appear in INFRASTRUCTURE tab

---

### 4. Recovery Events (❌ NOT WRITING TO SQLITE)

**Scripts writing ONLY to JSONL**:
- `scripts/ccc-self-heal.py` - Writes to recovery-outcomes.jsonl
- `scripts/meta-analyzer.py` - Line: `RECOVERY_OUTCOMES = DATA_DIR / "recovery-outcomes.jsonl"`

**SQLite table exists**: `recovery_events` (backfilled with 150 rows)

**Hook function available**: `log_recovery()` in sqlite_hooks.py ✅

**Impact**: New recovery events won't appear in INFRASTRUCTURE tab

---

## Data Flow Status (Current)

```
┌─────────────────────────────────────┐
│      Data Generation Points         │
└──────────────┬──────────────────────┘
               │
     ┌─────────┼──────────────────────────────────┐
     │         │                                   │
     v         v                                   v
┌────────┐ ┌─────────┐                    ┌─────────────┐
│  Tool  │ │   Git   │                    │  Routing    │
│ Events │ │ Commits │                    │  Metrics    │
└───┬────┘ └────┬────┘                    └──────┬──────┘
    │           │                                 │
    │  ✅       │  ✅                             │  ❌
    │  SQLite   │  SQLite                         │  JSONL ONLY!
    v           v                                 v
┌─────────────────┐                      ┌──────────────┐
│ SQLite Database │                      │ JSONL Files  │
│  (PRIMARY)      │                      │  (NO SYNC!)  │
└────────┬────────┘                      └──────────────┘
         │                                        │
         │                                        │ (stale!)
         v                                        v
    ┌────────────┐                          ┌──────────┐
    │ Dashboard  │                          │ Dashboard│
    │ (Current)  │                          │ (STALE)  │
    └────────────┘                          └──────────┘
```

**Result**:
- Tool usage, activity, git: ✅ Always current
- Routing, sessions, self-heal, recovery: ❌ Frozen at backfill time

---

## Scripts Requiring Updates

### Priority 1: Critical (User-Facing Dashboard Data)

1. **scripts/observatory/post-session-analyzer.py**
   - Function: Line 429-430 (save method)
   - Add: SQLite write using new `log_session_outcome()` function

2. **hooks/session-optimizer-stop.sh**
   - Currently writes to session-outcomes.jsonl
   - Add: SQLite write using `log_session_outcome()` function

3. **scripts/claude-wrapper.sh**
   - Variable: `METRICS_LOG="$HOME/.claude/data/routing-metrics.jsonl"`
   - Add: SQLite write using `log_routing_metric()` function

4. **scripts/routing-feedback.py**
   - Variable: `ROUTING_FILE = HOME / ".claude/data/routing-metrics.jsonl"`
   - Add: SQLite write using `log_routing_metric()` function

### Priority 2: Infrastructure Monitoring

5. **scripts/ccc-autonomous-brain.py**
   - Writes to self-heal-outcomes.jsonl
   - Add: SQLite write using `log_self_heal()` function

6. **scripts/ccc-self-heal.py**
   - Writes to recovery-outcomes.jsonl
   - Add: SQLite write using `log_recovery()` function

7. **scripts/meta-analyzer.py**
   - Variable: `RECOVERY_OUTCOMES = DATA_DIR / "recovery-outcomes.jsonl"`
   - Add: SQLite write using `log_recovery()` function

---

## Required sqlite_hooks.py Updates

### New Function Needed

```python
def log_session_outcome(session_id: str, outcome: str, quality: float,
                        complexity: float, intent: str, model: str,
                        messages_count: Optional[int] = None,
                        duration_minutes: Optional[int] = None,
                        cost_usd: Optional[float] = None,
                        success: bool = True,
                        summary: Optional[str] = None) -> bool:
    """
    Log a session outcome event to SQLite

    Args:
        session_id: Session identifier
        outcome: 'success', 'partial', 'failure', 'abandoned'
        quality: Quality score 1-5
        complexity: Complexity score 0-1
        intent: Session intent/goal
        model: Model used (haiku, sonnet, opus)
        messages_count: Number of messages
        duration_minutes: Session duration
        cost_usd: Session cost
        success: Whether session succeeded
        summary: Brief summary of session

    Returns:
        bool: True if successful
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO session_outcome_events
            (timestamp, session_id, outcome, quality, complexity, intent,
             model, messages_count, duration_minutes, cost_usd, success, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (int(time.time()), session_id, outcome, quality, complexity,
              intent, model, messages_count, duration_minutes, cost_usd,
              1 if success else 0, summary))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Failed to log session outcome: {e}")
        return False
```

---

## Fix Strategy

### Approach: Dual-Write (Same as post-tool-enhanced.sh)

**For each script**:
1. Import sqlite_hooks at top
2. Add SQLite write BEFORE JSONL write (PRIMARY)
3. Keep JSONL write as BACKUP
4. Fail silently (don't break existing functionality)

**Example Template**:
```python
# Import at top
import sys
sys.path.insert(0, str(Path.home() / '.claude/scripts'))
from sqlite_hooks import log_session_outcome

# In save method
try:
    # PRIMARY: Write to SQLite
    log_session_outcome(
        session_id=session_id,
        outcome=outcome,
        quality=quality,
        # ... other fields
    )
except Exception:
    pass  # Fail silently

# BACKUP: Write to JSONL (existing code)
with open(output_file, 'a') as f:
    f.write(json.dumps(entry) + '\n')
```

---

## Testing Plan

### Verification Steps

**For each data type**:
1. Count current rows in SQLite table
2. Trigger the event (run the script)
3. Count rows again (should increment by 1)
4. Verify new row has correct data
5. Generate dashboard (should show new data)

**Example for session outcomes**:
```bash
# Before
sqlite3 ~/.claude/data/claude.db "SELECT COUNT(*) FROM session_outcome_events"
# Output: 701

# Trigger (analyze a recent session)
cd ~/.claude/scripts/observatory && python3 post-session-analyzer.py --recent 1

# After
sqlite3 ~/.claude/data/claude.db "SELECT COUNT(*) FROM session_outcome_events"
# Output: 702 ← Should increment!

# Verify
sqlite3 ~/.claude/data/claude.db "SELECT session_id, outcome, quality FROM session_outcome_events ORDER BY timestamp DESC LIMIT 1"
```

---

## Risk Assessment

### Current State (Incomplete Migration)

| Time Period | Impact |
|-------------|--------|
| Now | Routing/sessions/self-heal/recovery frozen at backfill time |
| 1 day | New data accumulating in JSONL but not appearing in dashboard |
| 1 week | Dashboard shows incorrect totals, misleading metrics |
| 1 month | Data divergence (JSONL has 1000s more events than SQLite) |

### After Complete Fix

| Benefit | Impact |
|---------|--------|
| Real-time | All dashboard sections always current |
| Consistent | No data divergence between sources |
| Reliable | SQLite is single source of truth |
| Complete | 100% migration achieved |

---

## Success Criteria

- [ ] Add log_session_outcome() to sqlite_hooks.py
- [ ] Update post-session-analyzer.py to write to SQLite
- [ ] Update session-optimizer-stop.sh to write to SQLite
- [ ] Update claude-wrapper.sh to write to SQLite
- [ ] Update routing-feedback.py to write to SQLite
- [ ] Update ccc-autonomous-brain.py to write to SQLite
- [ ] Update ccc-self-heal.py to write to SQLite
- [ ] Update meta-analyzer.py to write to SQLite
- [ ] Test each data flow (verify row counts increment)
- [ ] Verify dashboard shows new data in all sections

---

## Next Actions

**Immediate** (This Session):
1. Add `log_session_outcome()` to sqlite_hooks.py
2. Update all 7 scripts to dual-write (SQLite + JSONL)
3. Test each data flow
4. Commit all fixes

**Verification** (Next 24 Hours):
- Monitor SQLite database growth
- Check dashboard for real-time updates
- Verify no errors in logs

**Cleanup** (After 30 Days):
- Remove JSONL backup writes
- Remove sqlite-to-jsonl-sync from LaunchAgent
- Archive old JSONL files

---

## Conclusion

The user's instinct was correct: **if one hook wasn't writing to SQLite, others aren't either.**

We found **7 additional scripts** still writing ONLY to JSONL:
- 2 routing scripts
- 2 session outcome scripts
- 1 self-heal script
- 2 recovery scripts

These need immediate fixes to complete the SQLite migration.

**Status**: 🔴 **Migration 60% Complete** (3/10 data sources hooked to SQLite)

---

*Audit Date: 2026-01-28 05:15*
*Found By: User intuition (100% correct)*
*Priority: CRITICAL - Dashboard data will be incomplete*
