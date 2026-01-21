#!/usr/bin/env python3
"""
Unified datastore for Claude dashboard data.
Provides a clean API for reading and writing to the SQLite database.

Usage:
    from datastore import Datastore

    db = Datastore()
    db.log_session(session_id, project_path, model, ...)
    stats = db.get_daily_stats(days=30)
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

DB_PATH = Path.home() / ".claude/data/claude.db"
SCHEMA_PATH = Path.home() / ".claude/data/schema.sql"


class Datastore:
    """Unified datastore for Claude dashboard data."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self):
        """Ensure database exists with schema."""
        if not self.db_path.exists():
            if SCHEMA_PATH.exists():
                with open(SCHEMA_PATH) as f:
                    schema = f.read()
                with self._connect() as conn:
                    conn.executescript(schema)

    @contextmanager
    def _connect(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════════════════════════════
    # SESSION OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def log_session(
        self,
        session_id: str,
        project_path: str,
        model: str,
        started_at: datetime,
        ended_at: Optional[datetime] = None,
        message_count: int = 0,
        tool_count: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        outcome: str = None,
        quality_score: float = None,
        dq_score: float = None,
        complexity: float = None,
        cost_estimate: float = None,
        metadata: Dict = None
    ):
        """Log or update a session."""
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sessions
                (id, project_path, model, started_at, ended_at, message_count, tool_count,
                 input_tokens, output_tokens, cache_read_tokens, outcome, quality_score,
                 dq_score, complexity, cost_estimate, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, project_path, model, started_at.isoformat(),
                ended_at.isoformat() if ended_at else None,
                message_count, tool_count, input_tokens, output_tokens, cache_read_tokens,
                outcome, quality_score, dq_score, complexity, cost_estimate,
                json.dumps(metadata) if metadata else None
            ))

    def get_sessions(self, days: int = 30, project: str = None) -> List[Dict]:
        """Get recent sessions."""
        with self._connect() as conn:
            query = """
                SELECT * FROM sessions
                WHERE started_at >= date('now', ?)
            """
            params = [f'-{days} days']

            if project:
                query += " AND project_path = ?"
                params.append(project)

            query += " ORDER BY started_at DESC"

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_session_outcomes(self) -> Dict[str, int]:
        """Get session outcome counts."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT outcome, COUNT(*) as count
                FROM sessions
                WHERE outcome IS NOT NULL
                GROUP BY outcome
            """).fetchall()
            return {row['outcome']: row['count'] for row in rows}

    # ═══════════════════════════════════════════════════════════════════════════
    # DAILY STATS OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def update_daily_stats(
        self,
        date: str,
        opus_messages: int = 0,
        sonnet_messages: int = 0,
        haiku_messages: int = 0,
        opus_tokens_in: int = 0,
        opus_tokens_out: int = 0,
        opus_cache_read: int = 0,
        sonnet_tokens_in: int = 0,
        sonnet_tokens_out: int = 0,
        sonnet_cache_read: int = 0,
        haiku_tokens_in: int = 0,
        haiku_tokens_out: int = 0,
        haiku_cache_read: int = 0,
        session_count: int = 0,
        tool_calls: int = 0,
        cost_estimate: float = 0
    ):
        """Update or insert daily statistics."""
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO daily_stats
                (date, opus_messages, sonnet_messages, haiku_messages,
                 opus_tokens_in, opus_tokens_out, opus_cache_read,
                 sonnet_tokens_in, sonnet_tokens_out, sonnet_cache_read,
                 haiku_tokens_in, haiku_tokens_out, haiku_cache_read,
                 session_count, tool_calls, cost_estimate, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date, opus_messages, sonnet_messages, haiku_messages,
                opus_tokens_in, opus_tokens_out, opus_cache_read,
                sonnet_tokens_in, sonnet_tokens_out, sonnet_cache_read,
                haiku_tokens_in, haiku_tokens_out, haiku_cache_read,
                session_count, tool_calls, cost_estimate,
                datetime.now().isoformat()
            ))

    def get_daily_stats(self, days: int = 30) -> List[Dict]:
        """Get daily statistics for the last N days."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM daily_stats
                WHERE date >= date('now', ?)
                ORDER BY date DESC
            """, [f'-{days} days']).fetchall()
            return [dict(row) for row in rows]

    def get_totals(self) -> Dict:
        """Get total statistics across all time."""
        with self._connect() as conn:
            row = conn.execute("""
                SELECT
                    SUM(opus_messages + sonnet_messages + haiku_messages) as total_messages,
                    SUM(session_count) as total_sessions,
                    SUM(tool_calls) as total_tools,
                    SUM(opus_messages) as opus_messages,
                    SUM(sonnet_messages) as sonnet_messages,
                    SUM(haiku_messages) as haiku_messages,
                    SUM(cost_estimate) as total_cost
                FROM daily_stats
            """).fetchone()
            return dict(row) if row else {}

    # ═══════════════════════════════════════════════════════════════════════════
    # ROUTING OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def log_routing_decision(
        self,
        query_hash: str,
        query_preview: str,
        complexity: float,
        selected_model: str,
        dq_score: float,
        dq_validity: float = None,
        dq_specificity: float = None,
        dq_correctness: float = None,
        cost_estimate: float = None
    ):
        """Log a routing decision."""
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO routing_decisions
                (timestamp, query_hash, query_preview, complexity, selected_model,
                 dq_score, dq_validity, dq_specificity, dq_correctness, cost_estimate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(), query_hash, query_preview, complexity,
                selected_model, dq_score, dq_validity, dq_specificity, dq_correctness,
                cost_estimate
            ))

    def record_routing_feedback(self, query_hash: str, success: bool):
        """Record feedback on a routing decision."""
        with self._connect() as conn:
            conn.execute("""
                UPDATE routing_decisions
                SET success = ?, feedback_at = ?
                WHERE query_hash = ? AND success IS NULL
                ORDER BY timestamp DESC
                LIMIT 1
            """, (1 if success else 0, datetime.now().isoformat(), query_hash))

    def get_routing_stats(self, days: int = 7) -> Dict:
        """Get routing statistics."""
        with self._connect() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    AVG(dq_score) as avg_dq,
                    SUM(CASE WHEN selected_model = 'opus' THEN 1 ELSE 0 END) as opus_count,
                    SUM(CASE WHEN selected_model = 'sonnet' THEN 1 ELSE 0 END) as sonnet_count,
                    SUM(CASE WHEN selected_model = 'haiku' THEN 1 ELSE 0 END) as haiku_count
                FROM routing_decisions
                WHERE timestamp >= datetime('now', ?)
            """, [f'-{days} days']).fetchone()
            return dict(row) if row else {}

    # ═══════════════════════════════════════════════════════════════════════════
    # TOOL USAGE OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def update_tool_usage(self, tool_name: str, calls: int = 1, success: bool = True):
        """Update tool usage statistics."""
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO tool_usage (tool_name, total_calls, success_count, failure_count, last_used)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tool_name) DO UPDATE SET
                    total_calls = total_calls + ?,
                    success_count = success_count + ?,
                    failure_count = failure_count + ?,
                    last_used = ?
            """, (
                tool_name, calls, calls if success else 0, 0 if success else calls,
                datetime.now().isoformat(),
                calls, calls if success else 0, 0 if success else calls,
                datetime.now().isoformat()
            ))

    def get_tool_stats(self, limit: int = 20) -> List[Dict]:
        """Get top tool usage statistics."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM tool_usage
                ORDER BY total_calls DESC
                LIMIT ?
            """, [limit]).fetchall()
            return [dict(row) for row in rows]

    # ═══════════════════════════════════════════════════════════════════════════
    # HOURLY ACTIVITY
    # ═══════════════════════════════════════════════════════════════════════════

    def update_hourly_activity(self, date: str, hour: int, sessions: int = 0, messages: int = 0):
        """Update hourly activity pattern."""
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO hourly_activity (date, hour, session_count, message_count)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(date, hour) DO UPDATE SET
                    session_count = session_count + ?,
                    message_count = message_count + ?
            """, (date, hour, sessions, messages, sessions, messages))

    def get_hourly_pattern(self) -> Dict[int, int]:
        """Get aggregated hourly activity pattern."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT hour, SUM(session_count) as total
                FROM hourly_activity
                GROUP BY hour
                ORDER BY hour
            """).fetchall()
            return {row['hour']: row['total'] for row in rows}

    # ═══════════════════════════════════════════════════════════════════════════
    # EXPORT FOR DASHBOARD
    # ═══════════════════════════════════════════════════════════════════════════

    def export_stats_cache(self) -> Dict:
        """Export data in stats-cache.json format for backward compatibility."""
        totals = self.get_totals()
        daily = self.get_daily_stats(days=365)
        hourly = self.get_hourly_pattern()

        return {
            "version": 1,
            "lastComputedDate": datetime.now().strftime("%Y-%m-%d"),
            "totalSessions": totals.get('total_sessions', 0) or 0,
            "totalMessages": totals.get('total_messages', 0) or 0,
            "totalTools": totals.get('total_tools', 0) or 0,
            "modelUsage": {
                "opus": {
                    "inputTokens": sum(d.get('opus_tokens_in', 0) or 0 for d in daily),
                    "outputTokens": sum(d.get('opus_tokens_out', 0) or 0 for d in daily),
                    "cacheReadInputTokens": sum(d.get('opus_cache_read', 0) or 0 for d in daily),
                    "messageCount": totals.get('opus_messages', 0) or 0
                }
            },
            "hourCounts": {str(h): c for h, c in hourly.items()},
            "dailyActivity": [
                {
                    "date": d['date'],
                    "messageCount": (d.get('opus_messages', 0) or 0) + (d.get('sonnet_messages', 0) or 0) + (d.get('haiku_messages', 0) or 0),
                    "sessionCount": d.get('session_count', 0) or 0,
                    "toolCallCount": d.get('tool_calls', 0) or 0
                }
                for d in daily
            ],
            "totals": {
                "sessions": totals.get('total_sessions', 0) or 0,
                "messages": totals.get('total_messages', 0) or 0,
                "tools": totals.get('total_tools', 0) or 0
            }
        }


# Singleton instance for easy import
_instance = None

def get_datastore() -> Datastore:
    """Get singleton datastore instance."""
    global _instance
    if _instance is None:
        _instance = Datastore()
    return _instance


if __name__ == "__main__":
    # Test the datastore
    db = Datastore()
    print("Datastore initialized")
    print(f"Database: {db.db_path}")
    print(f"Totals: {db.get_totals()}")
