#!/usr/bin/env python3
"""
Universal Dual-Write Library for Auto-Capture
Provides functions to write events to BOTH JSONL and SQLite simultaneously.

Usage:
    from dual_write_lib import log_git_activity, log_dq_score, etc.
"""

import sqlite3
import json
import time
from pathlib import Path
from datetime import datetime

# Paths
HOME = Path.home()
DB_PATH = HOME / ".agent-core" / "storage" / "antigravity.db"
DATA_DIR = HOME / ".claude" / "data"
KERNEL_DIR = HOME / ".claude" / "kernel"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
KERNEL_DIR.mkdir(parents=True, exist_ok=True)

def get_db():
    """Get database connection with WAL mode for concurrent access."""
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

# ═══════════════════════════════════════════════════════════════
# GIT ACTIVITY
# ═══════════════════════════════════════════════════════════════

def log_git_activity(repo: str, commit_hash: str, message: str):
    """Log git activity to SQLite (JSONL handled by caller)."""
    try:
        ts = int(time.time())

        # Write to SQLite only (caller already wrote to JSONL)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO git_activity (ts, repo, hash, msg, session_pwd)
            VALUES (?, ?, ?, ?, ?)
        """, (ts, repo, commit_hash, message, None))
        conn.commit()
        conn.close()

    except Exception as e:
        # Fail silently to not block operations
        import sys
        sys.stderr.write(f"dual-write error (git_activity): {e}\n")

# ═══════════════════════════════════════════════════════════════
# SELF-HEAL OUTCOMES
# ═══════════════════════════════════════════════════════════════

def log_self_heal_outcome(ok: int = 0, warn: int = 0, error: int = 0, fixed: int = 0):
    """Log self-heal outcome to SQLite (JSONL handled by caller)."""
    try:
        ts = int(time.time())

        # Write to SQLite only (caller already wrote to JSONL)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO self_heal_outcomes (ts, ok, warn, error, fixed, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ts, ok, warn, error, fixed, None))
        conn.commit()
        conn.close()

    except Exception as e:
        import sys
        sys.stderr.write(f"dual-write error (self_heal_outcomes): {e}\n")

# ═══════════════════════════════════════════════════════════════
# SESSION OUTCOMES
# ═══════════════════════════════════════════════════════════════

def log_session_outcome(session_id: str, messages: int, tools: int, title: str,
                        intent: str, outcome: str, model_efficiency: float,
                        models_used: dict, quality: int):
    """Log session outcome to SQLite (JSONL handled by caller)."""
    try:
        ts = int(time.time())
        date = datetime.now().strftime("%Y-%m-%d")

        # Write to SQLite only (caller already wrote to JSONL)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO session_outcomes
            (id, session_id, intent, outcome, quality, model_efficiency,
             models_used, date, messages, tools, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_id, session_id, intent, outcome, quality, model_efficiency,
              json.dumps(models_used), date, messages, tools, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    except Exception as e:
        import sys
        sys.stderr.write(f"dual-write error (session_outcomes): {e}\n")

# ═══════════════════════════════════════════════════════════════
# TOOL SUCCESS
# ═══════════════════════════════════════════════════════════════

def log_tool_success(tool: str, success: int, failure: int, total: int, date: str = None):
    """Log tool success/failure to SQLite (JSONL handled by caller)."""
    try:
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        ts = int(datetime.strptime(date, "%Y-%m-%d").timestamp())

        # Write to SQLite only (caller already wrote to JSONL)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO tool_success (ts, date, tool, success, failure, total)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ts, date, tool, success, failure, total))
        conn.commit()
        conn.close()

    except Exception as e:
        import sys
        sys.stderr.write(f"dual-write error (tool_success): {e}\n")

# ═══════════════════════════════════════════════════════════════
# DQ SCORES
# ═══════════════════════════════════════════════════════════════

def log_dq_score(query: str, complexity: float, model: str, dq_score: float,
                 validity: float, specificity: float, correctness: float,
                 reasoning: str, alternatives: list):
    """Log DQ score to SQLite (JSONL handled by caller)."""
    try:
        ts = int(time.time())

        # Write to SQLite only (caller already wrote to JSONL)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO dq_scores
            (ts, query, complexity, model, dq_score, validity, specificity,
             correctness, reasoning, alternatives)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts, query, complexity, model, dq_score, validity, specificity,
              correctness, reasoning, json.dumps(alternatives)))
        conn.commit()
        conn.close()

    except Exception as e:
        import sys
        sys.stderr.write(f"dual-write error (dq_scores): {e}\n")

# ═══════════════════════════════════════════════════════════════
# ROUTING DECISIONS
# ═══════════════════════════════════════════════════════════════

def log_routing_decision(recommended_model: str, cognitive_mode: str,
                         task_complexity: str, dq_score: float, hour: int,
                         reasoning: str):
    """Log routing decision to SQLite (JSONL handled by caller)."""
    try:
        timestamp = datetime.now().isoformat()
        ts = int(time.time())

        # Write to SQLite only (caller already wrote to JSONL)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO routing_decisions
            (ts, timestamp, recommended_model, cognitive_mode, task_complexity,
             dq_score, hour, reasoning)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts, timestamp, recommended_model, cognitive_mode, task_complexity,
              dq_score, hour, reasoning))
        conn.commit()
        conn.close()

    except Exception as e:
        import sys
        sys.stderr.write(f"dual-write error (routing_decisions): {e}\n")

# ═══════════════════════════════════════════════════════════════
# RECOVERY OUTCOMES
# ═══════════════════════════════════════════════════════════════

def log_recovery_outcome(category: str, action: str, auto: bool, success: bool,
                        error_hash: str = None, details: str = None):
    """Log recovery outcome to SQLite (JSONL handled by caller)."""
    try:
        ts = int(time.time())

        # Write to SQLite only (caller already wrote to JSONL)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO recovery_outcomes
            (ts, category, action, auto, success, error_hash, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ts, category, action, auto, success, error_hash, details))
        conn.commit()
        conn.close()

    except Exception as e:
        import sys
        sys.stderr.write(f"dual-write error (recovery_outcomes): {e}\n")
