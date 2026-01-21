-- Claude Data Unified Schema
-- Version: 1.0.0
-- Created: 2026-01-21
--
-- This schema consolidates all dashboard data into a single SQLite database,
-- eliminating sync issues between multiple JSON files.

-- ═══════════════════════════════════════════════════════════════════════════
-- CORE TABLES
-- ═══════════════════════════════════════════════════════════════════════════

-- Sessions: One row per Claude session
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,              -- Session UUID
    project_path TEXT,                -- Project directory
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    model TEXT NOT NULL,              -- Primary model used (opus/sonnet/haiku)
    message_count INTEGER DEFAULT 0,
    tool_count INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cache_read_tokens INTEGER DEFAULT 0,
    cache_write_tokens INTEGER DEFAULT 0,
    outcome TEXT,                     -- completed/interrupted/abandoned
    quality_score REAL,               -- 0-1 quality assessment
    dq_score REAL,                    -- Decision quality score
    complexity REAL,                  -- Estimated task complexity
    cost_estimate REAL,               -- Calculated API cost equivalent
    metadata JSON                     -- Additional flexible data
);

CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_path);
CREATE INDEX IF NOT EXISTS idx_sessions_model ON sessions(model);

-- Messages: Aggregated daily message counts by model
-- (We don't store individual messages for privacy, just aggregates)
CREATE TABLE IF NOT EXISTS daily_stats (
    date DATE PRIMARY KEY,
    opus_messages INTEGER DEFAULT 0,
    sonnet_messages INTEGER DEFAULT 0,
    haiku_messages INTEGER DEFAULT 0,
    opus_tokens_in INTEGER DEFAULT 0,
    opus_tokens_out INTEGER DEFAULT 0,
    opus_cache_read INTEGER DEFAULT 0,
    sonnet_tokens_in INTEGER DEFAULT 0,
    sonnet_tokens_out INTEGER DEFAULT 0,
    sonnet_cache_read INTEGER DEFAULT 0,
    haiku_tokens_in INTEGER DEFAULT 0,
    haiku_tokens_out INTEGER DEFAULT 0,
    haiku_cache_read INTEGER DEFAULT 0,
    session_count INTEGER DEFAULT 0,
    tool_calls INTEGER DEFAULT 0,
    cost_estimate REAL DEFAULT 0,     -- Total API cost equivalent for day
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Routing decisions: DQ scorer history
CREATE TABLE IF NOT EXISTS routing_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    query_hash TEXT,                  -- MD5 of query (privacy)
    query_preview TEXT,               -- First 50 chars
    complexity REAL,
    selected_model TEXT,
    dq_score REAL,
    dq_validity REAL,
    dq_specificity REAL,
    dq_correctness REAL,
    cost_estimate REAL,
    success INTEGER,                  -- Feedback: 1=success, 0=failure, NULL=unknown
    feedback_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_routing_timestamp ON routing_decisions(timestamp);
CREATE INDEX IF NOT EXISTS idx_routing_model ON routing_decisions(selected_model);

-- Tool usage: Aggregated tool call statistics
CREATE TABLE IF NOT EXISTS tool_usage (
    tool_name TEXT PRIMARY KEY,
    total_calls INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    last_used DATETIME,
    avg_duration_ms REAL
);

-- Hourly activity pattern (for heatmaps)
CREATE TABLE IF NOT EXISTS hourly_activity (
    date DATE,
    hour INTEGER,                     -- 0-23
    session_count INTEGER DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    PRIMARY KEY (date, hour)
);

-- Projects: Tracked project statistics
CREATE TABLE IF NOT EXISTS projects (
    path TEXT PRIMARY KEY,
    name TEXT,
    description TEXT,
    icon TEXT,
    session_count INTEGER DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    last_active DATETIME,
    git_commits INTEGER DEFAULT 0,
    files_modified INTEGER DEFAULT 0
);

-- ═══════════════════════════════════════════════════════════════════════════
-- SUBSCRIPTION & COST TRACKING
-- ═══════════════════════════════════════════════════════════════════════════

-- Monthly subscription summary
CREATE TABLE IF NOT EXISTS subscription_periods (
    period TEXT PRIMARY KEY,          -- YYYY-MM format
    monthly_rate REAL,
    currency TEXT DEFAULT 'USD',
    total_messages INTEGER DEFAULT 0,
    total_sessions INTEGER DEFAULT 0,
    api_equivalent REAL DEFAULT 0,    -- What it would cost via API
    cache_savings REAL DEFAULT 0,
    roi_multiplier REAL DEFAULT 0
);

-- ═══════════════════════════════════════════════════════════════════════════
-- METADATA & CONFIG
-- ═══════════════════════════════════════════════════════════════════════════

-- Key-value store for misc config and state
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Schema version tracking
INSERT OR REPLACE INTO metadata (key, value, updated_at)
VALUES ('schema_version', '1.0.0', CURRENT_TIMESTAMP);

-- ═══════════════════════════════════════════════════════════════════════════
-- VIEWS FOR COMMON QUERIES
-- ═══════════════════════════════════════════════════════════════════════════

-- Daily cost summary view
CREATE VIEW IF NOT EXISTS v_daily_costs AS
SELECT
    date,
    (opus_tokens_in * 5.0 / 1000000) + (opus_tokens_out * 25.0 / 1000000) +
    (sonnet_tokens_in * 3.0 / 1000000) + (sonnet_tokens_out * 15.0 / 1000000) +
    (haiku_tokens_in * 0.8 / 1000000) + (haiku_tokens_out * 4.0 / 1000000) as api_cost,
    (opus_cache_read + sonnet_cache_read + haiku_cache_read) * 0.5 / 1000000 as cache_savings,
    opus_messages + sonnet_messages + haiku_messages as total_messages,
    session_count
FROM daily_stats;

-- Model distribution view
CREATE VIEW IF NOT EXISTS v_model_distribution AS
SELECT
    SUM(opus_messages) as opus_total,
    SUM(sonnet_messages) as sonnet_total,
    SUM(haiku_messages) as haiku_total,
    SUM(opus_messages + sonnet_messages + haiku_messages) as grand_total,
    ROUND(100.0 * SUM(opus_messages) / SUM(opus_messages + sonnet_messages + haiku_messages), 1) as opus_pct,
    ROUND(100.0 * SUM(sonnet_messages) / SUM(opus_messages + sonnet_messages + haiku_messages), 1) as sonnet_pct,
    ROUND(100.0 * SUM(haiku_messages) / SUM(opus_messages + sonnet_messages + haiku_messages), 1) as haiku_pct
FROM daily_stats;

-- Recent sessions view
CREATE VIEW IF NOT EXISTS v_recent_sessions AS
SELECT
    id,
    project_path,
    started_at,
    model,
    message_count,
    outcome,
    quality_score,
    cost_estimate,
    ROUND((julianday(ended_at) - julianday(started_at)) * 24 * 60, 1) as duration_minutes
FROM sessions
ORDER BY started_at DESC
LIMIT 100;

-- Routing accuracy view
CREATE VIEW IF NOT EXISTS v_routing_accuracy AS
SELECT
    selected_model,
    COUNT(*) as total_decisions,
    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures,
    ROUND(AVG(dq_score), 3) as avg_dq_score,
    ROUND(100.0 * SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) /
          NULLIF(SUM(CASE WHEN success IS NOT NULL THEN 1 ELSE 0 END), 0), 1) as accuracy_pct
FROM routing_decisions
GROUP BY selected_model;
