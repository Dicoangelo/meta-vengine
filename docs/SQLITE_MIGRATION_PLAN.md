# SQLite Migration Plan - Fixing the JSONL Mistake

**Created**: 2026-01-28
**Status**: 🔴 CRITICAL - Technical debt causing data duplication and sync overhead
**Priority**: HIGH

## The Problem

### Current (Broken) Architecture

```
Hooks → SQLite ────┐
                   ├→ Sync Scripts → JSONL → Dashboard reads JSONL
Backfill → JSONL ──┘
```

**Issues:**
1. ✅ SQLite is hooked up and receiving data in real-time
2. ❌ Dashboard (ccc-generator.sh) reads JSONL files, NOT SQLite
3. ❌ Sync scripts duplicate SQLite → JSONL
4. ❌ Backfill writes to JSONL, then must sync to SQLite
5. ❌ Data exists in TWO places (SQLite + JSONL)
6. ❌ JSONL files are huge (9.9MB activity-events, 4.9MB tool-usage)

### Why This Happened

**Timeline:**
1. **Early 2025**: Command Center built, reads from simple JSONL files
2. **Mid 2025**: SQLite databases added for structured storage
3. **Late 2025**: Sync scripts created to bridge SQLite ↔ JSONL
4. **Jan 2026**: Dashboard still reads JSONL, never migrated to SQLite

**Root cause**: Dashboard was never refactored to read from SQLite.

## Why SQLite is Superior

| Feature | SQLite | JSONL |
|---------|--------|-------|
| Speed | O(log n) indexed queries | O(n) sequential scan |
| Concurrency | Multiple readers | File locking issues |
| Atomicity | ACID transactions | Line-by-line append |
| Queries | SQL (aggregate, join, filter) | Manual parsing |
| Size | Compressed, efficient | Plain text, verbose |
| Corruption | Resilient with WAL mode | One bad line breaks it |

### Real Numbers

```
SQLite databases:
  antigravity.db: 12MB (31 tables, 11,175 tool events)
  supermemory.db: 134MB (11 tables, full knowledge graph)
  claude.db: 404KB (12 tables, aggregated stats)

JSONL files (duplicating SQLite):
  tool-usage.jsonl: 4.9MB (59,880 lines)
  activity-events.jsonl: 9.9MB (69,890 lines)

Wasted space: ~15MB in duplicate JSONL files
Sync overhead: 49 scripts reading JSONL instead of 11 reading SQLite
```

## The Mistake: Why JSONL Was Used

### Valid Initial Reasons

1. **Simplicity**: JSONL is simple, no schema needed
2. **Portability**: Works everywhere, no dependencies
3. **Append-only**: Easy to stream, no transactions needed
4. **Human readable**: Can `cat` and `grep` files

### But These Don't Apply Here

1. ❌ **Simplicity**: We now have complex sync scripts (more complex than SQL!)
2. ❌ **Portability**: We're already using SQLite everywhere
3. ❌ **Append-only**: SQLite with WAL mode is also append-only
4. ❌ **Human readable**: Dashboard is the only consumer, not humans

## Migration Plan

### Phase 1: Audit (DONE TODAY)

✅ Identified all JSONL files
✅ Mapped SQLite tables
✅ Found 49 scripts reading JSONL
✅ Documented the problem

### Phase 2: Dashboard Migration (HIGH PRIORITY)

**Goal**: Make `ccc-generator.sh` read from SQLite instead of JSONL

**Changes needed:**

1. **Replace JSONL readers with SQLite queries**
   ```python
   # OLD (JSONL)
   with open('tool-usage.jsonl') as f:
       for line in f:
           data.append(json.loads(line))

   # NEW (SQLite)
   cursor.execute("SELECT * FROM tool_events ORDER BY ts DESC LIMIT 1000")
   data = cursor.fetchall()
   ```

2. **Consolidate data sources**
   - `stats-cache.json` → `claude.db` (daily_stats, hourly_activity tables)
   - `tool-usage.jsonl` → `antigravity.db` (tool_events table)
   - `session-outcomes.jsonl` → `claude.db` (sessions table)
   - `activity-events.jsonl` → `antigravity.db` (tool_events table)

3. **Create dashboard data loader**
   ```python
   # ~/.claude/scripts/dashboard-data-loader.py
   # Single script that reads ALL data from SQLite
   # Outputs JSON for ccc-generator.sh to embed
   ```

### Phase 3: Deprecate Sync Scripts (MEDIUM PRIORITY)

**Remove these scripts (no longer needed):**
- `sqlite-to-jsonl-sync.py` ← Entire purpose is to duplicate data
- `integrate-untracked-data.py` ← Can write directly to SQLite

**Keep only:**
- `sqlite-hook.py` ← Real-time hook (writes to SQLite)
- `backfill-*.py` ← Writes directly to SQLite, no JSONL middleman

### Phase 4: Archive JSONL Files (LOW PRIORITY)

```bash
# Move to archive
mkdir ~/.claude/data/jsonl-archive
mv ~/.claude/data/*.jsonl ~/.claude/data/jsonl-archive/

# Keep only for historical analysis
# Delete after 30 days if no issues
```

## Preventing This Mistake

### Architectural Principles

**1. Single Source of Truth (SSOT)**

```yaml
RULE: Each data point should exist in EXACTLY ONE place
VIOLATION: tool_events exist in both SQLite AND JSONL
FIX: Choose SQLite, delete JSONL
```

**2. Write Once, Read Many**

```yaml
RULE: Don't create sync scripts unless absolutely necessary
VIOLATION: sqlite-to-jsonl-sync.py duplicates data for no reason
FIX: Make consumers read from the source (SQLite)
```

**3. Use the Right Tool**

```yaml
RULE: Structured data → Database, Unstructured data → Files
VIOLATION: Using JSONL for structured time-series data
FIX: Use SQLite for events, PostgreSQL for bigger deployments
```

**4. Database First**

```yaml
RULE: If you need a database, use it from day one
VIOLATION: Started with JSONL, "added SQLite later"
FIX: SQLite should be the default for ANY persistent data
```

### Decision Checklist

Before using JSONL files, ask:

- [ ] Is this data structured? (columns/fields) → Use SQLite
- [ ] Will I need to query/filter? → Use SQLite
- [ ] Is this data growing over time? → Use SQLite
- [ ] Do I need aggregations (sum, count, avg)? → Use SQLite
- [ ] Will multiple processes access this? → Use SQLite
- [ ] Is this data important (not just logs)? → Use SQLite

**When to use JSONL:**
- ✅ One-time exports for external tools
- ✅ Append-only logs that get rotated
- ✅ Data that will be processed by external tools (not you)

**When to use SQLite:**
- ✅ Application data storage (events, users, sessions)
- ✅ Time-series data
- ✅ Anything you'll query later
- ✅ Structured data with relationships

### Code Review Patterns

**Add to code review checklist:**

```markdown
## Data Storage Review

- [ ] Does this create a new .jsonl file?
  - [ ] Why not SQLite?
  - [ ] Will this need a sync script later?

- [ ] Does this create a sync script?
  - [ ] Can consumers read from source instead?
  - [ ] Is this creating duplicate data?

- [ ] Does this read from JSONL?
  - [ ] Can it read from SQLite instead?
  - [ ] Is SQLite available with this data?
```

## Migration Effort Estimate

### Phase 2: Dashboard Migration
**Time**: 4-6 hours
**Risk**: Medium (dashboard might break temporarily)
**Files**: 5-10 scripts

**Approach:**
1. Create `dashboard-data-loader.py` (reads from SQLite)
2. Test it produces same JSON as current JSONL readers
3. Update `ccc-generator.sh` to use new loader
4. Test dashboard thoroughly
5. Remove old JSONL readers

### Phase 3: Deprecate Sync Scripts
**Time**: 2-3 hours
**Risk**: Low (just deletion)
**Files**: 3-5 scripts

### Phase 4: Archive JSONL
**Time**: 30 minutes
**Risk**: Very low

**Total**: ~8 hours to fully migrate

## Implementation Order

### Immediate (Today)
1. ✅ Document the problem (this file)
2. ✅ Create architectural principles
3. ⬜ Add to CLAUDE.md for future reference

### This Week
1. ⬜ Create `dashboard-data-loader.py` (SQLite → JSON)
2. ⬜ Test data loader produces correct output
3. ⬜ Update `ccc-generator.sh` to use loader
4. ⬜ Test dashboard with SQLite backend

### Next Week
1. ⬜ Remove sync scripts
2. ⬜ Update hooks to write ONLY to SQLite
3. ⬜ Archive JSONL files
4. ⬜ Update documentation

### One Month Later
1. ⬜ Verify no issues
2. ⬜ Delete archived JSONL files
3. ⬜ Remove JSONL-related code
4. ⬜ Celebrate 🎉

## Success Metrics

| Metric | Before | Target | Benefit |
|--------|--------|--------|---------|
| Data duplication | 15MB | 0MB | -100% |
| Sync scripts | 3 | 0 | Simpler |
| Dashboard load time | ~2s | <0.5s | 4x faster |
| Scripts reading data | 49 | 11 | 78% reduction |
| Data sources | 2 (SQLite+JSONL) | 1 (SQLite) | SSOT |

## Monitoring

After migration:

```bash
# Verify no JSONL files are being written
find ~/.claude/data -name "*.jsonl" -mtime -1

# Verify SQLite is being read
lsof | grep "antigravity.db\|claude.db"

# Dashboard load time
time ccc --no-open

# No sync scripts running
ps aux | grep sync
```

## Lessons Learned

### What Went Wrong

1. **Started simple, never refactored**: JSONL was "good enough" initially
2. **SQLite added, never migrated**: Added SQLite without removing JSONL
3. **Sync scripts = band-aid**: Created bridges instead of fixing root cause
4. **No architectural review**: No one questioned "why both?"

### What to Do Differently

1. **Database first**: Use SQLite from day one for structured data
2. **Migrate, don't bridge**: When adding a database, migrate old code
3. **Question duplication**: If data exists twice, something is wrong
4. **Regular arch reviews**: Monthly check for technical debt

### Quote to Remember

> "If you need a database, use a database. Don't build a worse database out of text files."
> — Every experienced developer

## References

- SQLite docs: https://sqlite.org/whentouse.html
- SQLite performance: https://www.sqlite.org/speed.html
- JSONL vs SQLite: https://stackoverflow.com/questions/tagged/sqlite+jsonl

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-28 | Migrate dashboard to SQLite | Eliminate data duplication, improve performance |
| 2026-01-28 | Deprecate JSONL for structured data | SQLite is superior for all our use cases |
| 2026-01-28 | Add architectural principles | Prevent repeating this mistake |

---

**Status**: 📋 Plan approved, awaiting implementation
**Owner**: System architect
**Timeline**: 2 weeks
**Priority**: HIGH - Technical debt is creating maintenance burden
