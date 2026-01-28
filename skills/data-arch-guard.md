---
name: data-arch-guard
description: Prevent data duplication and unnecessary sync scripts by remembering past architectural mistakes
triggers:
  - should I create a jsonl file
  - should I create a new jsonl
  - need to sync data
  - which storage format
  - data architecture decision
  - prevent data duplication
  - use jsonl or sqlite
category: architecture
version: 1.0.0
---

# Data Architecture Guard

**Purpose**: Act as an architectural checkpoint to prevent data duplication, sync script proliferation, and technical debt from "temporary" solutions.

## The Mistake We Made

### What Happened
1. Started with JSONL files (simple, append-only, "good enough")
2. Added SQLite later for better performance and querying
3. **Never migrated existing consumers** (e.g., dashboard still reads JSONL)
4. Created sync scripts as a "temporary bridge" between formats
5. **Result**: 15MB of duplicate data, sync overhead, technical debt

### Why It Happened
- **Incremental growth without refactoring**: Added new tech without migrating old consumers
- **"Temporary" solutions became permanent**: Sync scripts lived for months
- **Path of least resistance**: Easier to add sync than to migrate dashboard
- **No architectural review**: Nobody questioned "why are we storing this in two places?"

### The Cost
- 15MB wasted on duplicate session data
- Sync scripts running on every session end
- Confusion about which data source is canonical
- Migration debt that compounds over time

---

## Decision Tree

### Should I use JSONL?

✅ **YES** if:
- One-time export for external tools (e.g., sharing data with another system)
- Append-only logs with rotation (e.g., activity logs that get archived)
- Configuration that rarely changes and doesn't need queries
- Human-readable audit trail

❌ **NO** if:
- Structured data with fields that you'll query on
- Growing time-series data (sessions, events, metrics)
- Multiple consumers that need different views of the data
- Need aggregations (sum, count, avg, percentiles)
- Data will be updated or deleted

### Should I use SQLite?

✅ **YES** if:
- Structured data with defined schema (has fields/columns)
- Need to query, filter, or search efficiently
- Data grows over time (unbounded)
- Multiple processes or tools access it
- Need aggregations, joins, or analytics
- Need transactions or consistency guarantees

❌ **NO** if:
- One-time export that won't be queried
- Pure append-only log that's never searched
- Config file that's read once at startup

### Should I create a sync script?

❌ **Probably NO**. Stop and ask:

1. **Why can't consumers read from the source directly?**
   - If it's "too slow" → optimize the source query
   - If it's "wrong format" → transform on read, not duplicate on write

2. **Am I creating duplicate data?**
   - If YES → you're violating Single Source of Truth (SSOT)
   - Consider: Can I delete the old source instead?

3. **Will this be "temporary" for 2+ years?**
   - Temporary solutions in infrastructure rarely get cleaned up
   - If you can't commit to migrating consumers in 30 days, don't sync

4. **Can I fix the root cause instead?**
   - Migrate consumers to new source
   - Deprecate old format
   - Make new format the SSOT

✅ **Sync is OK** only if:
- External integration requires specific format you don't control
- Performance: Pre-aggregated data for real-time dashboards
- You have a **committed migration plan** with deadline

---

## Prevention Checklist

Before adding **ANY** new data storage (JSONL, SQLite table, JSON file), answer:

- [ ] **Does this data exist elsewhere?** (Check for duplication)
- [ ] **Can I use an existing database table?** (Check schema with `sqlite3 ~/.claude/data/claude.db .schema`)
- [ ] **Will this need a sync script later?** (Red flag if yes)
- [ ] **Am I violating Single Source of Truth?** (Data should live in ONE place)
- [ ] **Is SQLite available for this use case?** (It usually is)
- [ ] **Have I considered the 10-year view?** (Will this scale? Will consumers multiply?)

### Code Review Questions

When reviewing code that adds data storage:

- [ ] Is this creating a new `.jsonl` file?
- [ ] Will this need a sync script to keep data in sync?
- [ ] Can consumers read from the source instead of duplicating?
- [ ] Is this creating duplicate data that already exists elsewhere?
- [ ] Does this violate the SSOT principle?
- [ ] Is there a migration plan if this "temporary" solution is actually permanent?

---

## Red Flags 🚩

**STOP and rethink** if you see:

🚩 Script named `*-to-*-sync`, `*-bridge-*`, `*-replicate-*`
🚩 Comments like "temporary until migration" or "TODO: consolidate later"
🚩 Same data stored in multiple places (e.g., JSONL + SQLite)
🚩 Creating a new JSONL file when SQLite database exists
🚩 Writing to both database AND files for same logical data
🚩 Transforming data on write instead of on read
🚩 Adding a new table that duplicates columns from another table

### Anti-Patterns to Avoid

```bash
# BAD: Sync script that duplicates data
session-to-db-sync.sh     # Why not write to DB directly?
jsonl-to-sqlite.sh        # Why not migrate consumers?

# BAD: Multiple sources of truth
~/.claude/data/sessions.jsonl
~/.claude/data/claude.db (sessions table)
# ^ Pick ONE

# BAD: "Temporary" bridging logic
# TODO: Remove this once dashboard migrated
sync_to_legacy_format()   # It will never be removed
```

---

## Architecture Principles (Quick Reference)

From `~/.claude/ARCHITECTURE_PRINCIPLES.md`:

1. **Single Source of Truth (SSOT)**: Data exists in ONE place
2. **Database First**: Use SQLite from day one for structured data
3. **Write Once, Read Many**: No sync scripts unless absolutely necessary
4. **Use the Right Tool**: Structured data → Database, not files
5. **Consolidate, Don't Proliferate**: Check existing stores before adding new ones

**Full principles**: See `~/.claude/ARCHITECTURE_PRINCIPLES.md` (484 lines, 10 principles)

---

## When to Use Each Format

| Use Case | Format | Why |
|----------|--------|-----|
| Session outcomes, events, metrics | SQLite | Queryable, aggregatable, grows over time |
| Activity timeline (append-only) | JSONL | Simple append, rotates, no queries |
| Config (read once at startup) | JSON | Simple, no queries |
| One-time export for sharing | JSONL | Human-readable, portable |
| Analytics dashboard data | SQLite | Aggregations, joins, filters |
| External API responses (cache) | SQLite | TTL, queries, size management |
| Audit trail (compliance) | JSONL | Immutable, append-only, line-by-line integrity |

---

## Migration Guidance

If you discover data duplication:

1. **Identify the canonical source** (which format is more complete/authoritative?)
2. **Migrate consumers** to read from canonical source
3. **Deprecate the duplicate** (stop writing to it)
4. **Remove sync scripts** once consumers migrated
5. **Delete the duplicate data** after verification period

**See**: `~/.claude/docs/SQLITE_MIGRATION_PLAN.md` for our JSONL→SQLite migration

---

## Integration with Other Systems

### Supermemory
Architectural decisions tracked in `~/.claude/memory/supermemory.db`:
```bash
sm project data-architecture  # View past decisions
sm context                     # Check if this issue happened before
```

### Observatory
Track data duplication metrics:
```bash
obs 30  # Check for sync script usage trends
```

### Code Review Hooks
Auto-warn on new JSONL files or sync scripts (see implementation below)

---

## References

- **Full principles**: `~/.claude/ARCHITECTURE_PRINCIPLES.md` (10 principles, examples)
- **Migration plan**: `~/.claude/docs/SQLITE_MIGRATION_PLAN.md` (our JSONL consolidation)
- **Hook status**: `~/.claude/docs/HOOK_STATUS.md` (what's tracked in real-time)
- **Current schema**: Run `sqlite3 ~/.claude/data/claude.db .schema` to see tables

---

## Example Scenarios

### ✅ Good: Using SQLite for Tool Events

**Question**: "Should I log tool usage to JSONL or SQLite?"

**Answer**: SQLite. Reasons:
- Structured data (tool name, timestamp, success/failure)
- Will grow over time (unbounded)
- Need to query (success rates, usage patterns)
- Multiple consumers (dashboard, analytics, debugging)

**Implementation**:
```sql
CREATE TABLE tool_events (
  id INTEGER PRIMARY KEY,
  tool_name TEXT NOT NULL,
  timestamp INTEGER NOT NULL,
  success INTEGER NOT NULL,
  duration_ms INTEGER
);
```

### ❌ Bad: Creating Sync Script

**Question**: "Dashboard reads JSONL but we moved to SQLite. Should I sync?"

**Answer**: No, migrate the dashboard. Reasons:
- Sync creates duplicate data (violates SSOT)
- "Temporary" sync will live for years
- Better to fix root cause (update dashboard to read SQLite)

**Better Implementation**:
```javascript
// OLD: Read from JSONL
const sessions = readJSONL('sessions.jsonl')

// NEW: Read from SQLite
const sessions = db.query('SELECT * FROM sessions ORDER BY timestamp DESC LIMIT 100')
```

### ✅ Good: Using JSONL for Activity Log

**Question**: "Should I store user activity timeline in SQLite?"

**Answer**: JSONL is fine here. Reasons:
- Append-only log (no queries, no updates)
- Rotates daily (bounded size per file)
- Human-readable for debugging
- No consumers need to query it

**Implementation**:
```bash
# Append to daily log
echo "$json_event" >> ~/.claude/activity-$(date +%Y%m%d).log

# Rotate old logs
find ~/.claude -name 'activity-*.log' -mtime +30 -delete
```

---

## Quick Decision Guide

```
Need to store data?
│
├─ Is it structured with schema? → YES → Use SQLite
├─ Will it grow unbounded? → YES → Use SQLite
├─ Need to query/filter? → YES → Use SQLite
├─ Multiple consumers? → YES → Use SQLite
│
├─ Append-only log with rotation? → YES → JSONL OK
├─ One-time export? → YES → JSONL OK
└─ Simple config read once? → YES → JSON OK

Need to sync data?
│
└─ WHY? → Fix root cause instead
         - Migrate consumers
         - Deprecate old format
         - Make new format canonical
```

---

**Version**: 1.0.0
**Last Updated**: 2026-01-28
**Maintained by**: Antigravity Infrastructure Team
