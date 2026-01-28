#!/bin/bash
# Phase 2 Verification Script
# Created: 2026-01-28

echo "=================================================================="
echo "Phase 2: SQLite Migration Verification"
echo "=================================================================="

DB_PATH="$HOME/.claude/data/claude.db"

echo -e "\n📊 New Tables Status:"
echo "----------------------------"
sqlite3 "$DB_PATH" << 'SQL'
.mode column
.headers on
SELECT 'routing_metrics_events' as table_name, COUNT(*) as rows FROM routing_metrics_events
UNION ALL
SELECT 'git_events', COUNT(*) FROM git_events
UNION ALL
SELECT 'self_heal_events', COUNT(*) FROM self_heal_events
UNION ALL
SELECT 'recovery_events', COUNT(*) FROM recovery_events
UNION ALL
SELECT 'coordinator_events', COUNT(*) FROM coordinator_events
UNION ALL
SELECT 'expertise_routing_events', COUNT(*) FROM expertise_routing_events
ORDER BY rows DESC;
SQL

echo -e "\n🔍 Row Count Verification:"
echo "----------------------------"

check_file() {
    local file=$1
    local table=$2
    if [ -f "$HOME/.claude/data/$file" ]; then
        jsonl_count=$(wc -l < "$HOME/.claude/data/$file")
        sqlite_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM $table")

        if [ "$jsonl_count" -eq "$sqlite_count" ]; then
            echo "  ✅ $file: $sqlite_count rows (match)"
        else
            echo "  ⚠️  $file: JSONL=$jsonl_count, SQLite=$sqlite_count (mismatch)"
        fi
    fi
}

check_file "routing-metrics.jsonl" "routing_metrics_events"
check_file "git-activity.jsonl" "git_events"
check_file "self-heal-outcomes.jsonl" "self_heal_events"
check_file "recovery-outcomes.jsonl" "recovery_events"

echo -e "\n📈 Sample Data (Top 3 from each table):"
echo "----------------------------"

echo -e "\nRouting Metrics:"
sqlite3 "$DB_PATH" "SELECT datetime(timestamp, 'unixepoch') as time, predicted_model, accuracy FROM routing_metrics_events ORDER BY timestamp DESC LIMIT 3"

echo -e "\nGit Events:"
sqlite3 "$DB_PATH" "SELECT datetime(timestamp, 'unixepoch') as time, event_type, repo FROM git_events ORDER BY timestamp DESC LIMIT 3"

echo -e "\nSelf-Heal Events:"
sqlite3 "$DB_PATH" "SELECT datetime(timestamp, 'unixepoch') as time, error_pattern, success FROM self_heal_events ORDER BY timestamp DESC LIMIT 3"

echo -e "\nRecovery Events:"
sqlite3 "$DB_PATH" "SELECT datetime(timestamp, 'unixepoch') as time, error_type, success FROM recovery_events ORDER BY timestamp DESC LIMIT 3"

echo -e "\n📊 Success Rates:"
echo "----------------------------"

echo "Self-Heal Success Rate:"
sqlite3 "$DB_PATH" "SELECT CAST(SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as success_rate FROM self_heal_events"

echo "Recovery Success Rate:"
sqlite3 "$DB_PATH" "SELECT CAST(SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as success_rate FROM recovery_events"

echo "Routing Accuracy:"
sqlite3 "$DB_PATH" "SELECT CAST(SUM(CASE WHEN accuracy=1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as accuracy FROM routing_metrics_events WHERE accuracy IS NOT NULL"

echo -e "\n✅ Phase 2 Verification Complete"
echo "=================================================================="
