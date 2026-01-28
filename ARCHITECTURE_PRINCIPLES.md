# Architecture Principles - Antigravity Ecosystem

**Version**: 1.0.0
**Last Updated**: 2026-01-28
**Status**: ✅ Active - Enforce in all code reviews

## Core Principles

### 1. Single Source of Truth (SSOT)

**Rule**: Each data point must exist in EXACTLY ONE authoritative location.

**Examples:**

✅ **Good**:
```
Tool events → antigravity.db (SQLite)
Dashboard reads from: antigravity.db
```

❌ **Bad**:
```
Tool events → antigravity.db (SQLite)
             → tool-usage.jsonl (duplicate!)
Dashboard reads from: JSONL
```

**Violations create:**
- Data inconsistency
- Sync complexity
- Storage waste
- Maintenance burden

### 2. Database First

**Rule**: For structured data, use a database from day one. Don't build a worse database out of text files.

**Decision tree:**

```
Is the data structured? (has fields/columns)
  ├─ YES → Use SQLite
  └─ NO → Consider files

Will you need to query/filter it?
  ├─ YES → Use SQLite
  └─ NO → Consider files

Is it growing over time?
  ├─ YES → Use SQLite
  └─ NO → Consider files

Do you need aggregations (sum/count/avg)?
  ├─ YES → Use SQLite
  └─ NO → Consider files

Will multiple processes access it?
  ├─ YES → Use SQLite
  └─ NO → Consider files
```

**When to use SQLite:**
- ✅ Application state
- ✅ Event logs
- ✅ Time-series data
- ✅ User data
- ✅ Session tracking
- ✅ Metrics/analytics
- ✅ Any data you'll query

**When to use files (JSONL/JSON):**
- ✅ One-time exports for external tools
- ✅ Configuration (rarely changes)
- ✅ Append-only logs with rotation
- ❌ NOT for data you'll query later

### 3. Write Once, Read Many

**Rule**: Don't create sync/bridge scripts unless absolutely necessary. Make consumers read from the source.

**Examples:**

✅ **Good**:
```
Hooks → SQLite
Dashboard → reads SQLite directly
```

❌ **Bad**:
```
Hooks → SQLite
Sync script → duplicates to JSONL
Dashboard → reads JSONL (why?)
```

**Red flags:**
- Script named `*-to-*-sync`
- Script named `*-bridge*`
- Comments like "temporary until migration"
- Multiple sources for same data

**Exceptions** (when sync is OK):
- Replicating to different systems (e.g., SQLite → PostgreSQL)
- Backing up to cloud storage
- Exporting for external tools (not our code)

### 4. Use the Right Tool

**Rule**: Choose tools based on data characteristics, not familiarity.

**Data storage decision matrix:**

| Data Type | Best Tool | Why |
|-----------|-----------|-----|
| Structured, queryable | SQLite | Indexed queries, SQL |
| Unstructured logs | Files | Simple append, rotation |
| Time-series events | SQLite | Efficient querying |
| Configuration | JSON/YAML | Human-editable |
| Binary data | Files + SQLite refs | Store path in DB |
| Large text | Files + SQLite FTS | Full-text search |
| Relational data | SQLite/PostgreSQL | Joins, constraints |
| Key-value pairs | SQLite | Simple table |
| Queue/stream | Redis/RabbitMQ | Designed for it |

**Common mistakes:**
- ❌ Using JSONL for structured data that needs queries
- ❌ Using Redis for persistent application state
- ❌ Using files for data with relationships
- ❌ Using MongoDB when SQLite would work (YAGNI)

### 5. Consolidate, Don't Proliferate

**Rule**: Before adding a new data store, check if existing stores can handle it.

**Questions to ask:**

1. Can this go in an existing SQLite table?
2. Can this be a column in an existing table?
3. Do I really need a separate file for this?
4. Will this create another sync point?

**Example:**

❌ **Bad** (proliferation):
```
~/.claude/data/
  tool-usage.jsonl
  bash-commands.jsonl      ← Why separate?
  write-operations.jsonl   ← Same data!
  edit-operations.jsonl    ← Fragmented
```

✅ **Good** (consolidated):
```
antigravity.db:
  tool_events table (tool, command, file_path)
```

### 6. Explicit Over Implicit

**Rule**: Make data flow explicit. No magic.

**Examples:**

✅ **Good**:
```python
# Clear data flow
data = load_from_sqlite()
transformed = transform(data)
write_to_dashboard(transformed)
```

❌ **Bad**:
```python
# Where does data come from?
# What happens in between?
render_dashboard()  # Magic inside!
```

**Requirements:**
- Function names describe what they do
- Data sources are explicit
- Transformations are clear
- Side effects are obvious

### 7. Fail Fast, Fail Loud

**Rule**: Errors should be obvious, not silent.

**Examples:**

✅ **Good**:
```python
if not db_path.exists():
    raise FileNotFoundError(f"Database not found: {db_path}")
```

❌ **Bad**:
```python
try:
    data = load_from_db()
except:
    data = []  # Silent failure!
```

**Requirements:**
- No bare `except:` clauses
- Log errors, don't swallow them
- Use specific exceptions
- Fail fast during startup

### 8. Schema Everything

**Rule**: All data structures must have explicit schemas.

**For SQLite:**
```sql
CREATE TABLE tool_events (
    id INTEGER PRIMARY KEY,
    ts INTEGER NOT NULL,
    tool TEXT NOT NULL,
    file_path TEXT,
    metadata TEXT,  -- JSON
    UNIQUE(ts, tool, file_path)
);

CREATE INDEX idx_tool_events_ts ON tool_events(ts);
```

**For JSON:**
```python
from typing import TypedDict

class ToolEvent(TypedDict):
    ts: int
    tool: str
    file_path: str | None
    metadata: dict
```

**Benefits:**
- Self-documenting
- Catches errors early
- Enables validation
- Easier refactoring

### 9. Measure, Don't Guess

**Rule**: Make decisions based on data, not assumptions.

**Examples:**

✅ **Good**:
```bash
# Measure current state
time ccc --no-open  # 2.3s

# Try SQLite
time ccc-sqlite --no-open  # 0.5s

# Decision: Migrate (4.6x faster)
```

❌ **Bad**:
```
"JSONL is probably fine for now"
"SQLite might be overkill"
"We can optimize later"
```

**Metrics to track:**
- Load times
- File sizes
- Query times
- Sync overhead
- Maintenance burden

### 10. Delete Aggressively

**Rule**: If code isn't needed, delete it. Don't comment it out.

**What to delete:**
- Deprecated features
- Unused functions
- Old migrations
- Temporary workarounds
- Commented code
- Sync scripts after migration

**Mark for deletion:**
```python
# DEPRECATED: Use sqlite_loader() instead
# DELETE AFTER: 2026-02-28
def jsonl_loader():
    raise DeprecationWarning("Use sqlite_loader()")
```

## Anti-Patterns to Avoid

### ❌ The "Temporary" Bridge

```python
# "Temporary" sync script (2 years old)
def sync_sqlite_to_jsonl():
    """TODO: Remove when dashboard migrated to SQLite"""
```

**Why bad**: Temporary becomes permanent. Delete or fix the root cause.

### ❌ The File Explosion

```
~/.claude/data/
  tool-usage.jsonl
  tool-usage-backup.jsonl
  tool-usage-old.jsonl
  tool-usage-2025.jsonl
  tool-usage-archive/
    tool-usage-2024.jsonl
```

**Why bad**: Database with rotation solves this. Use `DELETE FROM ... WHERE ts < ?`

### ❌ The Sync Cascade

```
SQLite → Script A → JSONL → Script B → JSON → Script C → Dashboard
```

**Why bad**: Each step adds latency and failure points. Go direct: SQLite → Dashboard

### ❌ The Magic Parser

```python
def get_data():
    # Tries 5 different sources
    # Falls back silently
    # Returns unknown data
    # Hope for the best!
```

**Why bad**: Debugging nightmares. Be explicit about sources.

### ❌ The Resume-Driven Development

```python
# Using MongoDB because it's on my resume
# Using Kafka because it sounds cool
# Using microservices because Netflix does
```

**Why bad**: YAGNI. Use boring technology. SQLite is fine.

## Code Review Checklist

**For every PR, check:**

- [ ] Is this creating a new .jsonl file?
  - [ ] Why not SQLite?
  - [ ] Will this need a sync script later?

- [ ] Is this creating a sync script?
  - [ ] Can consumers read from source instead?
  - [ ] Is this creating duplicate data?

- [ ] Is this reading from JSONL?
  - [ ] Can it read from SQLite instead?
  - [ ] Is SQLite available with this data?

- [ ] Is there a Single Source of Truth?
  - [ ] Is data stored in multiple places?
  - [ ] Are they synced? Why?

- [ ] Is this using the right tool?
  - [ ] Structured data in database?
  - [ ] Queryable data indexed?

- [ ] Is the data flow explicit?
  - [ ] Clear source?
  - [ ] Clear transformations?
  - [ ] Clear destination?

## Implementation Guide

### Starting a New Feature

1. **Define data structure** (schema)
2. **Choose storage** (use decision tree above)
3. **Create table/file** with schema
4. **Write to SSOT** (one place!)
5. **Read from SSOT** (no sync!)
6. **Add tests** (verify SSOT)

### Refactoring Existing Code

1. **Identify duplication** (find JSONL + SQLite)
2. **Choose SSOT** (usually SQLite)
3. **Migrate readers** (point to SSOT)
4. **Test thoroughly**
5. **Delete duplicates** (old files/scripts)
6. **Update docs**

### Adding a Sync Script

**Stop! Ask yourself:**

1. Why can't consumers read from the source?
2. Is this creating duplicate data?
3. Will this be "temporary" for 2 years?
4. Can I fix the root cause instead?

**If you still need sync:**

1. Document why (in code comments)
2. Add monitoring (sync lag, errors)
3. Set deletion date (when migration done)
4. Create migration plan

## Enforcement

### Code Review

- All PRs must follow these principles
- Violations block merge
- "We'll fix it later" = NO

### Monthly Audit

```bash
# Check for JSONL proliferation
find ~/.claude/data -name "*.jsonl" | wc -l

# Check for duplicate data
./scripts/audit-data-duplication.sh

# Check for sync scripts
find ~/.claude/scripts -name "*sync*" -o -name "*bridge*"
```

### Metrics

Track these monthly:

- Number of JSONL files
- Number of sync scripts
- Dashboard load time
- Data duplication (MB)

**Target**: Decreasing trend, not increasing.

## Exceptions

These principles have exceptions:

1. **Legacy compatibility** - Old data formats for migration
2. **External integrations** - Other tools need specific formats
3. **Performance** - Proven bottleneck (measure first!)
4. **Vendor requirements** - Third-party tools need specific formats

**Document all exceptions:**

```python
# EXCEPTION: Using JSONL for ArXiv export
# REASON: ArXiv pipeline requires newline-delimited JSON
# APPROVED BY: @username
# EXPIRES: 2026-06-01 (remove when ArXiv updates)
```

## Resources

- SQLite when to use: https://www.sqlite.org/whentouse.html
- SQLite performance: https://www.sqlite.org/speed.html
- Data duplication audit: `~/.claude/scripts/audit-data-sources.py`
- Migration plan: `~/.claude/docs/SQLITE_MIGRATION_PLAN.md`

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-28 | Initial principles based on JSONL/SQLite duplication issue |

---

**Remember**: Good architecture is about making the right thing easy and the wrong thing hard.
