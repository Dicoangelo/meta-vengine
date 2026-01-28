-- Phase 2: SQLite Migration - Add Remaining Tables
-- Purpose: Migrate routing-metrics, git-activity, self-heal data to SQLite
-- Created: 2026-01-28

-- Routing metrics events (replaces routing-metrics.jsonl)
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
    reasoning TEXT,
    query_text TEXT
);
CREATE INDEX IF NOT EXISTS idx_routing_metrics_timestamp ON routing_metrics_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_routing_metrics_accuracy ON routing_metrics_events(accuracy);
CREATE INDEX IF NOT EXISTS idx_routing_metrics_model ON routing_metrics_events(predicted_model);

-- Git events (replaces git-activity.jsonl)
CREATE TABLE IF NOT EXISTS git_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    event_type TEXT NOT NULL,  -- commit, push, pr, branch, merge
    repo TEXT,
    branch TEXT,
    commit_hash TEXT,
    message TEXT,
    files_changed INTEGER,
    additions INTEGER,
    deletions INTEGER,
    author TEXT
);
CREATE INDEX IF NOT EXISTS idx_git_timestamp ON git_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_git_type ON git_events(event_type);
CREATE INDEX IF NOT EXISTS idx_git_repo ON git_events(repo);
CREATE INDEX IF NOT EXISTS idx_git_branch ON git_events(branch);

-- Self-healing events (replaces self-heal-outcomes.jsonl)
CREATE TABLE IF NOT EXISTS self_heal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    error_pattern TEXT NOT NULL,
    fix_applied TEXT,
    success INTEGER NOT NULL,  -- 1 if fixed, 0 if failed
    execution_time_ms INTEGER,
    error_message TEXT,
    context TEXT,  -- JSON blob
    severity TEXT  -- low, medium, high, critical
);
CREATE INDEX IF NOT EXISTS idx_self_heal_timestamp ON self_heal_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_self_heal_pattern ON self_heal_events(error_pattern);
CREATE INDEX IF NOT EXISTS idx_self_heal_success ON self_heal_events(success);
CREATE INDEX IF NOT EXISTS idx_self_heal_severity ON self_heal_events(severity);

-- Recovery events (replaces recovery-outcomes.jsonl)
CREATE TABLE IF NOT EXISTS recovery_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    error_type TEXT NOT NULL,
    recovery_strategy TEXT,
    success INTEGER NOT NULL,
    attempts INTEGER DEFAULT 1,
    time_to_recover_ms INTEGER,
    error_details TEXT,
    recovery_method TEXT  -- auto, manual, assisted
);
CREATE INDEX IF NOT EXISTS idx_recovery_timestamp ON recovery_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_recovery_type ON recovery_events(error_type);
CREATE INDEX IF NOT EXISTS idx_recovery_success ON recovery_events(success);
CREATE INDEX IF NOT EXISTS idx_recovery_strategy ON recovery_events(recovery_strategy);

-- Coordinator events (replaces coordination-log.jsonl)
CREATE TABLE IF NOT EXISTS coordinator_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    agent_id TEXT,
    action TEXT NOT NULL,  -- spawn, complete, fail, lock, unlock, timeout
    strategy TEXT,
    file_path TEXT,
    result TEXT,
    duration_ms INTEGER,
    exit_code INTEGER
);
CREATE INDEX IF NOT EXISTS idx_coordinator_timestamp ON coordinator_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_coordinator_agent ON coordinator_events(agent_id);
CREATE INDEX IF NOT EXISTS idx_coordinator_action ON coordinator_events(action);

-- Expertise routing events (replaces expertise-routing.jsonl)
CREATE TABLE IF NOT EXISTS expertise_routing_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    domain TEXT NOT NULL,
    expertise_level REAL,  -- 0.0-1.0
    query_complexity REAL,
    chosen_model TEXT,
    reasoning TEXT,
    query_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_expertise_timestamp ON expertise_routing_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_expertise_domain ON expertise_routing_events(domain);
CREATE INDEX IF NOT EXISTS idx_expertise_model ON expertise_routing_events(chosen_model);
