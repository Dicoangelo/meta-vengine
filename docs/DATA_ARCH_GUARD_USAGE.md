# Data Architecture Guard - Usage Guide

## Quick Start

The Data Architecture Guard skill helps prevent data duplication and unnecessary sync scripts by remembering the JSONL/SQLite duplication mistake we made.

## How to Use

### 1. Manual Invocation

```bash
# Invoke the skill directly
claude -p "/data-arch-guard"

# Or from within a session
/data-arch-guard
```

### 2. Natural Language Triggers

The skill automatically activates when you ask questions like:

```bash
claude -p "should I create a new JSONL file for tool events?"
claude -p "need to sync data between JSONL and SQLite"
claude -p "which storage format should I use for session data?"
claude -p "should I use jsonl or sqlite for this?"
```

### 3. Git Pre-Commit Hook (Optional)

The hook warns you before committing:
- New `.jsonl` files
- New files with "sync", "bridge", or "replicate" in the name
- Code that writes to multiple data sources

**Install** (per repository):
```bash
# Link to your repo's pre-commit hook
cd /path/to/your/repo
ln -s ~/.claude/hooks/pre-commit-data-arch-check.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

**Example output**:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  DATA ARCHITECTURE WARNING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Potential data architecture issues detected:

🚩 New JSONL files:
   - scripts/tool-events.jsonl

   Question: Should this be SQLite instead?
   (Structured data with queries → SQLite)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
See guidance: /data-arch-guard skill
```

## Common Scenarios

### Scenario 1: Logging Tool Events

**Question**: "Should I log tool usage to JSONL or SQLite?"

**Answer from skill**:
- ✅ Use SQLite
- Reason: Structured data, grows over time, need queries/aggregations
- Implementation: Add `tool_events` table to `claude.db`

### Scenario 2: Dashboard Reading Old Format

**Question**: "Dashboard reads JSONL but we moved to SQLite. Should I sync?"

**Answer from skill**:
- ❌ Don't sync
- Reason: Creates duplicate data, violates SSOT principle
- Better solution: Migrate dashboard to read from SQLite directly

### Scenario 3: Activity Timeline

**Question**: "Should I store user activity timeline in SQLite?"

**Answer from skill**:
- JSONL is fine here
- Reason: Append-only log, rotates daily, no queries needed
- Use case: Human-readable debugging, compliance audit trail

## Decision Tree Summary

```
Need to store data?
│
├─ Structured with schema? → SQLite
├─ Grows unbounded? → SQLite
├─ Need to query/filter? → SQLite
├─ Multiple consumers? → SQLite
│
├─ Append-only log with rotation? → JSONL OK
├─ One-time export? → JSONL OK
└─ Simple config read once? → JSON OK

Need to sync data?
└─ WHY? → Fix root cause instead
```

## Red Flags to Watch For

🚩 Script named `*-to-*-sync` or `*-bridge-*`
🚩 Comments like "temporary until migration"
🚩 Same data in JSONL + SQLite
🚩 Writing to both database AND files

## Prevention Checklist

Before adding new data storage:
- [ ] Does this data exist elsewhere?
- [ ] Can I use an existing database table?
- [ ] Will this need a sync script later?
- [ ] Am I violating Single Source of Truth?
- [ ] Is SQLite available for this use case?

## Architecture Principles

From `~/.claude/ARCHITECTURE_PRINCIPLES.md`:

1. **Single Source of Truth (SSOT)**: Data exists in ONE place
2. **Database First**: Use SQLite from day one for structured data
3. **Write Once, Read Many**: No sync scripts unless absolutely necessary
4. **Use the Right Tool**: Structured data → Database, not files
5. **Consolidate, Don't Proliferate**: Check existing stores before adding new ones

See full principles: `~/.claude/ARCHITECTURE_PRINCIPLES.md`

## Integration with Other Systems

### Supermemory
```bash
# Check if similar issue happened before
sm context
sm errors "data duplication"
sm project data-architecture
```

### Observatory
```bash
# Check for sync script usage trends
obs 30

# Monitor data storage growth
tool-stats 7
```

### Current Schema
```bash
# View existing SQLite tables before creating new storage
sqlite3 ~/.claude/data/claude.db .schema
sqlite3 ~/.claude/data/antigravity.db .schema
```

## Migration Guidance

If you discover data duplication:

1. **Identify canonical source** (which format is authoritative?)
2. **Migrate consumers** to read from canonical source
3. **Deprecate duplicate** (stop writing to it)
4. **Remove sync scripts** once migration complete
5. **Delete duplicate data** after verification period

See: `~/.claude/docs/SQLITE_MIGRATION_PLAN.md`

## Files

| File | Purpose |
|------|---------|
| `~/.claude/skills/data-arch-guard.md` | Main skill (9.9KB) |
| `~/.claude/hooks/pre-commit-data-arch-check.sh` | Git hook (optional) |
| `~/.claude/ARCHITECTURE_PRINCIPLES.md` | Full principles (10 rules, 484 lines) |
| `~/.claude/docs/SQLITE_MIGRATION_PLAN.md` | Migration roadmap (337 lines) |
| `~/.claude/docs/DATA_ARCH_GUARD_USAGE.md` | This file |

## Examples

### ✅ Good: Add SQLite Table

```sql
-- Add new table for structured data
CREATE TABLE tool_events (
  id INTEGER PRIMARY KEY,
  tool_name TEXT NOT NULL,
  timestamp INTEGER NOT NULL,
  success INTEGER NOT NULL,
  duration_ms INTEGER
);

-- Consumers read directly
SELECT tool_name, COUNT(*) as uses
FROM tool_events
WHERE success = 1
GROUP BY tool_name;
```

### ❌ Bad: Create Sync Script

```bash
# DON'T DO THIS
# Sync JSONL to SQLite (creates duplication)
cat sessions.jsonl | while read line; do
  sqlite3 claude.db "INSERT INTO sessions ..."
done
```

### ✅ Better: Migrate Consumer

```javascript
// Before (reads JSONL)
const sessions = readJSONL('sessions.jsonl')

// After (reads SQLite directly)
const sessions = db.query('SELECT * FROM sessions ORDER BY timestamp DESC')
```

## Testing the Skill

### Test 1: Manual Invocation
```bash
claude -p "/data-arch-guard"
# Should display full skill guidance
```

### Test 2: Natural Language
```bash
claude -p "should I create a new JSONL file for metrics?"
# Should trigger skill and provide decision guidance
```

### Test 3: Git Hook
```bash
cd /tmp/test-repo
git init
ln -s ~/.claude/hooks/pre-commit-data-arch-check.sh .git/hooks/pre-commit
touch new-sync-script.sh
git add new-sync-script.sh
git commit -m "test"
# Should show warning before commit
```

## Success Metrics

Track effectiveness:
- Fewer new JSONL files created (when SQLite is appropriate)
- Fewer sync scripts added
- Faster identification of data duplication
- Better architectural decisions in code reviews

## Version History

- **v1.0.0** (2026-01-28): Initial implementation
  - Core skill with decision tree
  - Git pre-commit hook
  - Integration with Supermemory/Observatory

## Feedback

If the skill helps prevent an architectural mistake, log it:
```bash
sm add "data-arch-guard prevented JSONL duplication for [use case]"
```

If the skill gives wrong guidance, improve it:
```bash
# Edit the skill
$EDITOR ~/.claude/skills/data-arch-guard.md

# Document the edge case
sm add "data-arch-guard edge case: [description]"
```
