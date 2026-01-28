-- SQLite Migration: Add Raw Events Tables
-- Purpose: Store raw event data from JSONL files
-- Created: 2026-01-28

-- Raw tool events (replaces tool-usage.jsonl)
CREATE TABLE IF NOT EXISTS tool_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    tool_name TEXT NOT NULL,
    success INTEGER NOT NULL,
    duration_ms INTEGER,
    error_message TEXT,
    context TEXT
);
CREATE INDEX IF NOT EXISTS idx_tool_events_timestamp ON tool_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_tool_events_tool_name ON tool_events(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_events_success ON tool_events(success);

-- Raw activity events (replaces activity-events.jsonl)
CREATE TABLE IF NOT EXISTS activity_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    data TEXT,
    session_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON activity_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_activity_type ON activity_events(event_type);
CREATE INDEX IF NOT EXISTS idx_activity_session ON activity_events(session_id);

-- Raw routing events (replaces routing-decisions.jsonl/routing-feedback.jsonl)
CREATE TABLE IF NOT EXISTS routing_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    query_hash TEXT,
    complexity REAL,
    dq_score REAL,
    chosen_model TEXT,
    reasoning TEXT,
    feedback TEXT
);
CREATE INDEX IF NOT EXISTS idx_routing_timestamp ON routing_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_routing_model ON routing_events(chosen_model);

-- Session outcomes (replaces session-outcomes.jsonl)
CREATE TABLE IF NOT EXISTS session_outcome_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    session_id TEXT,
    outcome TEXT,
    quality_score REAL,
    complexity REAL,
    model_used TEXT,
    cost REAL,
    message_count INTEGER
);
CREATE INDEX IF NOT EXISTS idx_outcome_timestamp ON session_outcome_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_outcome_session ON session_outcome_events(session_id);

-- Command usage (replaces command-usage.jsonl)
CREATE TABLE IF NOT EXISTS command_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    command TEXT NOT NULL,
    args TEXT,
    success INTEGER,
    execution_time_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_command_timestamp ON command_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_command_name ON command_events(command);
