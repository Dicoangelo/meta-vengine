# Phase 2: SQLite Migration Plan - Remaining JSONL Files

**Created**: 2026-01-28
**Status**: Ready to implement

---

## Files to Migrate (Priority Order)

### High Priority (Large Data Sets)

1. **routing-metrics.jsonl** - 1,592 lines, 281 KB
   - Tab affected: ROUTING
   - Current usage: Routing performance metrics, accuracy tracking
   - Target table: `routing_metrics_events`

2. **self-heal-outcomes.jsonl** - 1,195 lines, 75 KB
   - Tab affected: INFRASTRUCTURE
   - Current usage: Self-healing event tracking, fix success rates
   - Target table: `self_heal_events`

3. **git-activity.jsonl** - 274 lines, 37 KB
   - Tab affected: TOOL ANALYTICS
   - Current usage: Git commits, pushes, PRs tracking
   - Target table: `git_events`

4. **recovery-outcomes.jsonl** - 150 lines, 21 KB
   - Tab affected: INFRASTRUCTURE
   - Current usage: Error recovery attempts, success tracking
   - Target table: `recovery_events`

### Low Priority (Minimal Data)

5. **coordination-log.jsonl** - 3 lines
   - Tab affected: COORDINATOR (not in main dashboard)
   - Target table: `coordinator_events`

6. **expertise-routing.jsonl** - 1 line
   - Tab affected: NEW CAPABILITIES
   - Target table: `expertise_routing_events`

---

## New Tables Schema

### 1. routing_metrics_events
```sql
CREATE TABLE IF NOT EXISTS routing_metrics_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    query_id TEXT,
    predicted_model TEXT,
    actual_model TEXT,
    dq_score REAL,
    complexity REAL,
    accuracy INTEGER,  -- 1 if correct, 0 if wrong
    cost_saved REAL,
    reasoning TEXT
);
CREATE INDEX idx_routing_metrics_timestamp ON routing_metrics_events(timestamp);
CREATE INDEX idx_routing_metrics_accuracy ON routing_metrics_events(accuracy);
```

### 2. git_events
```sql
CREATE TABLE IF NOT EXISTS git_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    event_type TEXT NOT NULL,  -- commit, push, pr, branch
    repo TEXT,
    branch TEXT,
    commit_hash TEXT,
    message TEXT,
    files_changed INTEGER,
    additions INTEGER,
    deletions INTEGER
);
CREATE INDEX idx_git_timestamp ON git_events(timestamp);
CREATE INDEX idx_git_type ON git_events(event_type);
CREATE INDEX idx_git_repo ON git_events(repo);
```

### 3. self_heal_events
```sql
CREATE TABLE IF NOT EXISTS self_heal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    error_pattern TEXT NOT NULL,
    fix_applied TEXT,
    success INTEGER NOT NULL,  -- 1 if fixed, 0 if failed
    execution_time_ms INTEGER,
    error_message TEXT,
    context TEXT  -- JSON blob with additional data
);
CREATE INDEX idx_self_heal_timestamp ON self_heal_events(timestamp);
CREATE INDEX idx_self_heal_pattern ON self_heal_events(error_pattern);
CREATE INDEX idx_self_heal_success ON self_heal_events(success);
```

### 4. recovery_events
```sql
CREATE TABLE IF NOT EXISTS recovery_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    error_type TEXT NOT NULL,
    recovery_strategy TEXT,
    success INTEGER NOT NULL,
    attempts INTEGER DEFAULT 1,
    time_to_recover_ms INTEGER,
    error_details TEXT
);
CREATE INDEX idx_recovery_timestamp ON recovery_events(timestamp);
CREATE INDEX idx_recovery_type ON recovery_events(error_type);
CREATE INDEX idx_recovery_success ON recovery_events(success);
```

### 5. coordinator_events
```sql
CREATE TABLE IF NOT EXISTS coordinator_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    agent_id TEXT,
    action TEXT NOT NULL,  -- spawn, complete, fail, lock, unlock
    strategy TEXT,
    file_path TEXT,
    result TEXT,
    duration_ms INTEGER
);
CREATE INDEX idx_coordinator_timestamp ON coordinator_events(timestamp);
CREATE INDEX idx_coordinator_agent ON coordinator_events(agent_id);
```

### 6. expertise_routing_events
```sql
CREATE TABLE IF NOT EXISTS expertise_routing_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    domain TEXT NOT NULL,
    expertise_level REAL,  -- 0.0-1.0
    query_complexity REAL,
    chosen_model TEXT,
    reasoning TEXT
);
CREATE INDEX idx_expertise_timestamp ON expertise_routing_events(timestamp);
CREATE INDEX idx_expertise_domain ON expertise_routing_events(domain);
```

---

## Implementation Plan

### Step 1: Create Tables
```bash
sqlite3 ~/.claude/data/claude.db < ~/.claude/scripts/phase2-add-tables.sql
```

### Step 2: Backfill Historical Data
```bash
python3 ~/.claude/scripts/phase2-backfill.py
```

### Step 3: Update Dashboard
```bash
python3 ~/.claude/scripts/phase2-dashboard-migration.py
```

### Step 4: Create SQLite Hooks
Replace JSONL-writing code with SQLite inserts in:
- Git hooks (post-commit, post-push)
- Recovery system scripts
- Self-healing infrastructure
- Routing decision logger
- Coordinator agent tracker

### Step 5: Verify Migration
```bash
bash ~/.claude/scripts/phase2-verify.sh
```

---

## Hook Examples

### Git Activity Hook
```python
# In git-post-commit.sh
import sqlite3
from pathlib import Path

db = sqlite3.connect(str(Path.home() / '.claude/data/claude.db'))
db.execute("""
    INSERT INTO git_events (timestamp, event_type, repo, branch, commit_hash, message, files_changed)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (timestamp, 'commit', repo, branch, commit_hash, message, files_changed))
db.commit()
db.close()
```

### Self-Heal Hook
```python
# In self-heal-attempt.py
db.execute("""
    INSERT INTO self_heal_events (timestamp, error_pattern, fix_applied, success, execution_time_ms)
    VALUES (?, ?, ?, ?, ?)
""", (timestamp, pattern, fix, success, duration))
```

### Routing Metrics Hook
```python
# In routing-logger.py
db.execute("""
    INSERT INTO routing_metrics_events (timestamp, predicted_model, actual_model, dq_score, complexity, accuracy)
    VALUES (?, ?, ?, ?, ?, ?)
""", (timestamp, predicted, actual, dq, complexity, correct))
```

---

## Estimated Impact

### Performance Gain
- Current: 19 JSONL files being scanned
- After Phase 2: 13 JSONL files remaining
- Dashboard tabs affected: 4 (ROUTING, TOOL ANALYTICS, INFRASTRUCTURE, NEW CAPABILITIES)

### Data Migrated
- **Total rows**: ~3,215 events
- **Total size**: ~413 KB
- **Expected speedup**: 3-5x for affected queries

### Timeline
- Schema creation: 15 minutes
- Backfill scripts: 45 minutes
- Dashboard updates: 30 minutes
- Hook updates: 60 minutes
- Testing: 30 minutes
- **Total**: ~3 hours

---

## Priority Recommendation

**Start with these 3 (highest impact):**
1. routing-metrics.jsonl → routing_metrics_events (1,592 rows)
2. self-heal-outcomes.jsonl → self_heal_events (1,195 rows)
3. git-activity.jsonl → git_events (274 rows)

**Defer for later:**
- recovery-outcomes.jsonl (150 rows, similar to self-heal)
- coordination-log.jsonl (3 rows, minimal data)
- expertise-routing.jsonl (1 row, feature in development)

---

## Next Steps

1. Review this plan
2. Run schema creation script
3. Execute backfill for top 3 files
4. Update dashboard sections
5. Create SQLite hooks
6. Verify and commit

**Ready to implement?**
