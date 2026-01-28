#!/usr/bin/env python3
"""
Backfill the 70% of data that wasn't auto-captured to SQLite.
Imports from JSONL files to antigravity.db.
"""

import sqlite3
import json
import time
from pathlib import Path
from datetime import datetime

HOME = Path.home()
DB_PATH = HOME / ".agent-core" / "storage" / "antigravity.db"

# Data sources
SOURCES = {
    "git_activity": HOME / ".claude/data/git-activity.jsonl",
    "self_heal_outcomes": HOME / ".claude/data/self-heal-outcomes.jsonl",
    "session_outcomes": HOME / ".claude/data/session-outcomes.jsonl",
    "tool_success": HOME / ".claude/data/tool-success.jsonl",
    "dq_scores": HOME / ".claude/kernel/dq-scores.jsonl",
    "routing_decisions": HOME / ".claude/kernel/cognitive-os/routing-decisions.jsonl",
    "recovery_outcomes": HOME / ".claude/data/recovery-outcomes.jsonl",
}

def get_db():
    """Get database connection with WAL mode."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn

def backfill_git_activity(conn):
    """Backfill git activity from JSONL."""
    source = SOURCES["git_activity"]
    if not source.exists():
        print(f"⚠️  {source.name} not found")
        return 0

    cursor = conn.cursor()
    count = 0

    with open(source) as f:
        for line in f:
            try:
                data = json.loads(line)
                cursor.execute("""
                    INSERT OR IGNORE INTO git_activity (ts, repo, hash, msg, session_pwd)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    data.get("ts"),
                    data.get("repo"),
                    data.get("hash"),
                    data.get("msg"),
                    None  # session_pwd not in JSONL
                ))
                count += cursor.rowcount
            except Exception as e:
                print(f"   Error on line: {e}")
                continue

    conn.commit()
    return count

def backfill_self_heal_outcomes(conn):
    """Backfill self-heal outcomes from JSONL."""
    source = SOURCES["self_heal_outcomes"]
    if not source.exists():
        print(f"⚠️  {source.name} not found")
        return 0

    cursor = conn.cursor()
    count = 0

    with open(source) as f:
        for line in f:
            try:
                data = json.loads(line)
                cursor.execute("""
                    INSERT OR IGNORE INTO self_heal_outcomes (ts, ok, warn, error, fixed, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    data.get("ts"),
                    data.get("ok", 0),
                    data.get("warn", 0),
                    data.get("error", 0),
                    data.get("fixed", 0),
                    None  # Could store full JSON if needed
                ))
                count += cursor.rowcount
            except Exception as e:
                print(f"   Error: {e}")
                continue

    conn.commit()
    return count

def backfill_session_outcomes(conn):
    """Backfill session outcomes from JSONL."""
    source = SOURCES["session_outcomes"]
    if not source.exists():
        print(f"⚠️  {source.name} not found")
        return 0

    cursor = conn.cursor()
    count = 0

    with open(source) as f:
        for line in f:
            try:
                data = json.loads(line)

                # Note: SQLite table uses 'id' as primary key (session_id)
                # Need to insert with session_id as id
                cursor.execute("""
                    INSERT OR IGNORE INTO session_outcomes
                    (id, session_id, intent, outcome, quality, model_efficiency,
                     models_used, date, messages, tools, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get("session_id"),  # Use session_id as primary key
                    data.get("session_id"),
                    data.get("intent"),
                    data.get("outcome"),
                    data.get("quality"),
                    data.get("model_efficiency"),
                    json.dumps(data.get("models_used", {})),
                    data.get("date"),
                    data.get("messages"),
                    data.get("tools"),
                    datetime.now().isoformat()
                ))
                count += cursor.rowcount
            except Exception as e:
                print(f"   Error: {e}")
                continue

    conn.commit()
    return count

def backfill_tool_success(conn):
    """Backfill tool success/failure rates from JSONL."""
    source = SOURCES["tool_success"]
    if not source.exists():
        print(f"⚠️  {source.name} not found")
        return 0

    cursor = conn.cursor()
    count = 0

    with open(source) as f:
        for line in f:
            try:
                data = json.loads(line)

                # Convert date to timestamp
                date_str = data.get("date")
                if date_str:
                    ts = int(datetime.strptime(date_str, "%Y-%m-%d").timestamp())
                else:
                    ts = int(time.time())

                cursor.execute("""
                    INSERT OR IGNORE INTO tool_success (ts, date, tool, success, failure, total)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    ts,
                    data.get("date"),
                    data.get("tool"),
                    data.get("success", 0),
                    data.get("failure", 0),
                    data.get("total", 0)
                ))
                count += cursor.rowcount
            except Exception as e:
                print(f"   Error: {e}")
                continue

    conn.commit()
    return count

def backfill_dq_scores(conn):
    """Backfill DQ scores from JSONL."""
    source = SOURCES["dq_scores"]
    if not source.exists():
        print(f"⚠️  {source.name} not found")
        return 0

    cursor = conn.cursor()
    count = 0

    with open(source) as f:
        for line in f:
            try:
                data = json.loads(line)
                components = data.get("dqComponents", {})

                cursor.execute("""
                    INSERT OR IGNORE INTO dq_scores
                    (ts, query, complexity, model, dq_score, validity, specificity,
                     correctness, reasoning, alternatives)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get("ts"),
                    data.get("query"),
                    data.get("complexity"),
                    data.get("model"),
                    data.get("dqScore"),
                    components.get("validity"),
                    components.get("specificity"),
                    components.get("correctness"),
                    data.get("reasoning"),
                    json.dumps(data.get("alternatives", []))
                ))
                count += cursor.rowcount
            except Exception as e:
                print(f"   Error: {e}")
                continue

    conn.commit()
    return count

def backfill_routing_decisions(conn):
    """Backfill routing decisions from JSONL."""
    source = SOURCES["routing_decisions"]
    if not source.exists():
        print(f"⚠️  {source.name} not found")
        return 0

    cursor = conn.cursor()
    count = 0

    with open(source) as f:
        for line in f:
            try:
                data = json.loads(line)

                # Parse timestamp to unix ts
                timestamp_str = data.get("timestamp")
                if timestamp_str:
                    ts = int(datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")).timestamp())
                else:
                    ts = int(time.time())

                cursor.execute("""
                    INSERT OR IGNORE INTO routing_decisions
                    (ts, timestamp, recommended_model, cognitive_mode, task_complexity,
                     dq_score, hour, reasoning)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ts,
                    data.get("timestamp"),
                    data.get("recommended_model"),
                    data.get("cognitive_mode"),
                    data.get("task_complexity"),
                    data.get("dq_score"),
                    data.get("hour"),
                    data.get("reasoning")
                ))
                count += cursor.rowcount
            except Exception as e:
                print(f"   Error: {e}")
                continue

    conn.commit()
    return count

def backfill_recovery_outcomes(conn):
    """Backfill recovery outcomes from JSONL."""
    source = SOURCES["recovery_outcomes"]
    if not source.exists():
        print(f"⚠️  {source.name} not found")
        return 0

    cursor = conn.cursor()
    count = 0

    with open(source) as f:
        for line in f:
            try:
                data = json.loads(line)
                cursor.execute("""
                    INSERT OR IGNORE INTO recovery_outcomes
                    (ts, category, action, auto, success, error_hash, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get("ts"),
                    data.get("category"),
                    data.get("action"),
                    data.get("auto"),
                    data.get("success"),
                    data.get("error_hash"),
                    data.get("details")
                ))
                count += cursor.rowcount
            except Exception as e:
                print(f"   Error: {e}")
                continue

    conn.commit()
    return count

def main():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  BACKFILLING 70% UNHOOKED DATA TO SQLITE")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    conn = get_db()

    backfills = [
        ("git_activity", backfill_git_activity),
        ("self_heal_outcomes", backfill_self_heal_outcomes),
        ("session_outcomes", backfill_session_outcomes),
        ("tool_success", backfill_tool_success),
        ("dq_scores", backfill_dq_scores),
        ("routing_decisions", backfill_routing_decisions),
        ("recovery_outcomes", backfill_recovery_outcomes),
    ]

    total_backfilled = 0

    for name, func in backfills:
        print(f"📥 Backfilling {name}...")
        try:
            count = func(conn)
            print(f"   ✅ {count} rows backfilled")
            total_backfilled += count
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        print()

    conn.close()

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  TOTAL: {total_backfilled} rows backfilled")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

if __name__ == "__main__":
    main()
