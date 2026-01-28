# SQLite Quick Reference - Command Center Dashboard

Quick reference for working with the SQLite-backed Command Center dashboard.

---

## Database Location

```bash
~/.claude/data/claude.db  # Main database (34 MB)
```

---

## Tables

### Raw Events (Write to these)
```sql
-- Tool usage events
INSERT INTO tool_events (timestamp, tool_name, success, duration_ms)
VALUES (1706400000, 'Read', 1, 42);

-- Activity events
INSERT INTO activity_events (timestamp, event_type, data, session_id)
VALUES (1706400000, 'tool_use', '{"tool":"Read"}', 'session-123');

-- Routing decisions
INSERT INTO routing_events (timestamp, complexity, dq_score, chosen_model)
VALUES (1706400000, 0.45, 0.72, 'sonnet');
```

### Aggregated (Read from these)
```sql
-- Tool statistics (auto-updated)
SELECT tool_name, total_calls, success_count, avg_duration_ms
FROM tool_usage
ORDER BY total_calls DESC;
```

---

## Common Queries

### Tool Usage
```sql
-- Top 10 tools
SELECT tool_name, COUNT(*) as count
FROM tool_events
GROUP BY tool_name
ORDER BY count DESC
LIMIT 10;

-- Success rate by tool
SELECT
    tool_name,
    CAST(SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as success_rate
FROM tool_events
GROUP BY tool_name
ORDER BY success_rate ASC;

-- Daily usage (last 7 days)
SELECT
    date(timestamp, 'unixepoch') as day,
    COUNT(*) as count
FROM tool_events
WHERE timestamp > unixepoch('now', '-7 days')
GROUP BY day;
```

### Activity Events
```sql
-- Events by type
SELECT event_type, COUNT(*) as count
FROM activity_events
GROUP BY event_type
ORDER BY count DESC;

-- Hourly activity
SELECT
    strftime('%H:00', datetime(timestamp, 'unixepoch')) as hour,
    COUNT(*) as count
FROM activity_events
GROUP BY hour;
```

### Routing
```sql
-- Model distribution
SELECT chosen_model, COUNT(*) as count
FROM routing_events
GROUP BY chosen_model;

-- Average DQ score
SELECT AVG(dq_score) as avg_dq, AVG(complexity) as avg_complexity
FROM routing_events;
```

---

## Python Usage

### Using dashboard-sql-loader.py
```python
from dashboard_sql_loader import DashboardData

with DashboardData() as db:
    # Get tool usage summary
    tools = db.get_tool_usage_summary(days=7)

    # Get activity timeline
    activity = db.get_activity_timeline(limit=100)

    # Get routing decisions
    routing = db.get_routing_decisions(days=7)

    # Full dashboard summary
    summary = db.get_dashboard_summary(days=7)
```

### Direct SQLite
```python
import sqlite3
from pathlib import Path

db_path = Path.home() / '.claude/data/claude.db'
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

cursor = conn.execute("SELECT * FROM tool_events LIMIT 10")
for row in cursor:
    print(dict(row))

conn.close()
```

---

## Bash Helpers

### Log tool event
```bash
log_tool_event() {
    local tool="$1"
    local success="${2:-1}"
    local duration="${3:-NULL}"
    sqlite3 ~/.claude/data/claude.db << SQL
INSERT INTO tool_events (timestamp, tool_name, success, duration_ms)
VALUES ($(date +%s), '$tool', $success, $duration);
SQL
}

# Usage
log_tool_event "Read" 1 42
```

### Query from bash
```bash
# Count events
sqlite3 ~/.claude/data/claude.db "SELECT COUNT(*) FROM tool_events"

# Top tools
sqlite3 ~/.claude/data/claude.db \
    "SELECT tool_name, COUNT(*) FROM tool_events GROUP BY tool_name ORDER BY COUNT(*) DESC LIMIT 10"

# Today's activity
sqlite3 ~/.claude/data/claude.db \
    "SELECT COUNT(*) FROM activity_events WHERE date(timestamp, 'unixepoch') = date('now')"
```

---

## Maintenance

### Update aggregated tables
```sql
-- Refresh tool_usage from tool_events
DELETE FROM tool_usage;
INSERT INTO tool_usage (tool_name, total_calls, success_count, failure_count, last_used, avg_duration_ms)
SELECT
    tool_name,
    COUNT(*) as total_calls,
    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END),
    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END),
    MAX(datetime(timestamp, 'unixepoch')),
    AVG(duration_ms)
FROM tool_events
GROUP BY tool_name;
```

### Check database size
```bash
du -h ~/.claude/data/claude.db
sqlite3 ~/.claude/data/claude.db "SELECT COUNT(*) FROM tool_events"
```

### Vacuum database (compact)
```bash
sqlite3 ~/.claude/data/claude.db "VACUUM"
```

---

## Indexes

All tables have indexes for fast queries:

```sql
-- Tool events
CREATE INDEX idx_tool_events_timestamp ON tool_events(timestamp);
CREATE INDEX idx_tool_events_tool_name ON tool_events(tool_name);
CREATE INDEX idx_tool_events_success ON tool_events(success);

-- Activity events
CREATE INDEX idx_activity_timestamp ON activity_events(timestamp);
CREATE INDEX idx_activity_type ON activity_events(event_type);

-- Routing events
CREATE INDEX idx_routing_timestamp ON routing_events(timestamp);
CREATE INDEX idx_routing_model ON routing_events(chosen_model);
```

---

## Backup & Restore

### Backup
```bash
# Create backup
cp ~/.claude/data/claude.db ~/.claude/data/claude.db.backup-$(date +%Y%m%d)

# Dump to SQL
sqlite3 ~/.claude/data/claude.db .dump > ~/claude-db-backup.sql
```

### Restore
```bash
# From backup file
cp ~/.claude/data/claude.db.backup-20260128 ~/.claude/data/claude.db

# From SQL dump
sqlite3 ~/.claude/data/claude.db < ~/claude-db-backup.sql
```

---

## Troubleshooting

### Database locked
```bash
# Check for processes using the database
lsof ~/.claude/data/claude.db

# Kill lock (last resort)
rm ~/.claude/data/claude.db-journal
```

### Verify integrity
```bash
sqlite3 ~/.claude/data/claude.db "PRAGMA integrity_check"
```

### Rebuild indexes
```bash
sqlite3 ~/.claude/data/claude.db "REINDEX"
```

---

## Migration Scripts

```bash
# Verify migration
~/.claude/scripts/verify-sqlite-migration.sh

# Backfill data (one-time)
~/.claude/scripts/backfill-jsonl-to-sqlite.py

# Check hooks
~/.claude/scripts/update-hooks-for-sqlite.sh
```

---

## Performance Tips

1. **Use indexes**: All queries should use indexed columns (timestamp, tool_name)
2. **Batch inserts**: Use transactions for multiple inserts
3. **Read-only**: Use `PRAGMA query_only = ON` for dashboard queries
4. **Connection pooling**: Reuse connections instead of opening/closing

### Example: Batch insert
```python
conn = sqlite3.connect('claude.db')
conn.execute("BEGIN TRANSACTION")

for event in events:
    conn.execute("INSERT INTO tool_events (...) VALUES (...)", event)

conn.execute("COMMIT")
```

---

## Related Files

- **Dashboard**: `~/.claude/scripts/ccc-generator.sh`
- **Query Library**: `~/.claude/scripts/dashboard-sql-loader.py`
- **Schema**: `~/.claude/scripts/migration-add-tables.sql`
- **Docs**: `~/.claude/docs/SQLITE_MIGRATION_COMPLETE.md`

---

**Last Updated**: 2026-01-28
