#!/usr/bin/env python3
"""
Dashboard SQL Loader
Purpose: Reusable SQLite query functions for Command Center dashboard
Created: 2026-01-28
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

DB_PATH = Path.home() / '.claude/data/claude.db'

class DashboardData:
    """Helper class for dashboard SQLite queries"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row  # Dict-like row access

    def close(self):
        """Close database connection"""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # Tool Usage Queries
    # ==================

    def get_tool_usage_summary(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get tool usage summary for last N days"""
        cutoff = int((datetime.now() - timedelta(days=days)).timestamp())

        cursor = self.conn.execute("""
            SELECT
                tool_name,
                COUNT(*) as total_calls,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failure_count,
                AVG(duration_ms) as avg_duration_ms,
                MAX(timestamp) as last_used
            FROM tool_events
            WHERE timestamp > ?
            GROUP BY tool_name
            ORDER BY total_calls DESC
        """, (cutoff,))

        return [dict(row) for row in cursor.fetchall()]

    def get_tool_events(self, tool_name: Optional[str] = None, days: int = 7, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent tool events, optionally filtered by tool name"""
        cutoff = int((datetime.now() - timedelta(days=days)).timestamp())

        if tool_name:
            cursor = self.conn.execute("""
                SELECT * FROM tool_events
                WHERE tool_name = ? AND timestamp > ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (tool_name, cutoff, limit))
        else:
            cursor = self.conn.execute("""
                SELECT * FROM tool_events
                WHERE timestamp > ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (cutoff, limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_tool_success_rate(self, days: int = 7) -> Dict[str, float]:
        """Get success rate by tool for last N days"""
        cutoff = int((datetime.now() - timedelta(days=days)).timestamp())

        cursor = self.conn.execute("""
            SELECT
                tool_name,
                CAST(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as success_rate
            FROM tool_events
            WHERE timestamp > ?
            GROUP BY tool_name
            HAVING COUNT(*) > 5
            ORDER BY success_rate ASC
        """, (cutoff,))

        return {row['tool_name']: row['success_rate'] for row in cursor.fetchall()}

    # Activity Queries
    # ================

    def get_activity_timeline(self, days: int = 7, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent activity events"""
        cutoff = int((datetime.now() - timedelta(days=days)).timestamp())

        cursor = self.conn.execute("""
            SELECT * FROM activity_events
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (cutoff, limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_activity_by_type(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get activity counts by event type"""
        cutoff = int((datetime.now() - timedelta(days=days)).timestamp())

        cursor = self.conn.execute("""
            SELECT
                event_type,
                COUNT(*) as count
            FROM activity_events
            WHERE timestamp > ?
            GROUP BY event_type
            ORDER BY count DESC
        """, (cutoff,))

        return [dict(row) for row in cursor.fetchall()]

    def get_hourly_activity(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get activity grouped by hour"""
        cutoff = int((datetime.now() - timedelta(days=days)).timestamp())

        cursor = self.conn.execute("""
            SELECT
                strftime('%Y-%m-%d %H:00:00', datetime(timestamp, 'unixepoch')) as hour,
                COUNT(*) as event_count
            FROM activity_events
            WHERE timestamp > ?
            GROUP BY hour
            ORDER BY hour DESC
        """, (cutoff,))

        return [dict(row) for row in cursor.fetchall()]

    # Routing Queries
    # ===============

    def get_routing_decisions(self, days: int = 7, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent routing decisions"""
        cutoff = int((datetime.now() - timedelta(days=days)).timestamp())

        cursor = self.conn.execute("""
            SELECT * FROM routing_events
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (cutoff, limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_model_distribution(self, days: int = 7) -> Dict[str, int]:
        """Get model usage distribution"""
        cutoff = int((datetime.now() - timedelta(days=days)).timestamp())

        cursor = self.conn.execute("""
            SELECT
                chosen_model,
                COUNT(*) as count
            FROM routing_events
            WHERE timestamp > ? AND chosen_model IS NOT NULL
            GROUP BY chosen_model
            ORDER BY count DESC
        """, (cutoff,))

        return {row['chosen_model']: row['count'] for row in cursor.fetchall()}

    def get_avg_dq_score(self, days: int = 7) -> Optional[float]:
        """Get average DQ score"""
        cutoff = int((datetime.now() - timedelta(days=days)).timestamp())

        cursor = self.conn.execute("""
            SELECT AVG(dq_score) as avg_dq
            FROM routing_events
            WHERE timestamp > ? AND dq_score IS NOT NULL
        """, (cutoff,))

        result = cursor.fetchone()
        return result['avg_dq'] if result else None

    def get_avg_complexity(self, days: int = 7) -> Optional[float]:
        """Get average complexity score"""
        cutoff = int((datetime.now() - timedelta(days=days)).timestamp())

        cursor = self.conn.execute("""
            SELECT AVG(complexity) as avg_complexity
            FROM routing_events
            WHERE timestamp > ? AND complexity IS NOT NULL
        """, (cutoff,))

        result = cursor.fetchone()
        return result['avg_complexity'] if result else None

    # Session Queries
    # ===============

    def get_session_outcomes(self, days: int = 7, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent session outcomes"""
        cutoff = int((datetime.now() - timedelta(days=days)).timestamp())

        cursor = self.conn.execute("""
            SELECT * FROM session_outcome_events
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (cutoff, limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_avg_session_quality(self, days: int = 7) -> Optional[float]:
        """Get average session quality score"""
        cutoff = int((datetime.now() - timedelta(days=days)).timestamp())

        cursor = self.conn.execute("""
            SELECT AVG(quality_score) as avg_quality
            FROM session_outcome_events
            WHERE timestamp > ? AND quality_score IS NOT NULL
        """, (cutoff,))

        result = cursor.fetchone()
        return result['avg_quality'] if result else None

    def get_session_count(self, days: int = 7) -> int:
        """Get total session count"""
        cutoff = int((datetime.now() - timedelta(days=days)).timestamp())

        cursor = self.conn.execute("""
            SELECT COUNT(DISTINCT session_id) as count
            FROM session_outcome_events
            WHERE timestamp > ? AND session_id IS NOT NULL
        """, (cutoff,))

        result = cursor.fetchone()
        return result['count'] if result else 0

    # Aggregated Queries
    # ==================

    def get_dashboard_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get comprehensive dashboard summary"""
        cutoff_ts = int((datetime.now() - timedelta(days=days)).timestamp())

        # Tool usage stats
        tool_cursor = self.conn.execute("""
            SELECT
                COUNT(DISTINCT tool_name) as unique_tools,
                COUNT(*) as total_tool_calls,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_calls,
                AVG(duration_ms) as avg_duration
            FROM tool_events
            WHERE timestamp > ?
        """, (cutoff_ts,))
        tool_stats = dict(tool_cursor.fetchone())

        # Activity stats
        activity_cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total_events,
                COUNT(DISTINCT event_type) as unique_event_types
            FROM activity_events
            WHERE timestamp > ?
        """, (cutoff_ts,))
        activity_stats = dict(activity_cursor.fetchone())

        # Routing stats
        routing_cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total_decisions,
                AVG(dq_score) as avg_dq_score,
                AVG(complexity) as avg_complexity
            FROM routing_events
            WHERE timestamp > ?
        """, (cutoff_ts,))
        routing_stats = dict(routing_cursor.fetchone())

        # Session stats
        session_cursor = self.conn.execute("""
            SELECT
                COUNT(DISTINCT session_id) as total_sessions,
                AVG(quality_score) as avg_quality,
                AVG(message_count) as avg_messages
            FROM session_outcome_events
            WHERE timestamp > ?
        """, (cutoff_ts,))
        session_stats = dict(session_cursor.fetchone())

        return {
            'period_days': days,
            'tool_stats': tool_stats,
            'activity_stats': activity_stats,
            'routing_stats': routing_stats,
            'session_stats': session_stats,
            'generated_at': datetime.now().isoformat()
        }

# CLI Interface
# =============

def main():
    """CLI interface for testing queries"""
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: dashboard-sql-loader.py <query> [days]")
        print("\nAvailable queries:")
        print("  tool_usage        - Tool usage summary")
        print("  activity          - Activity timeline")
        print("  routing           - Routing decisions")
        print("  sessions          - Session outcomes")
        print("  summary           - Full dashboard summary")
        sys.exit(1)

    query_type = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 7

    with DashboardData() as db:
        if query_type == 'tool_usage':
            data = db.get_tool_usage_summary(days)
        elif query_type == 'activity':
            data = db.get_activity_timeline(days, limit=50)
        elif query_type == 'routing':
            data = db.get_routing_decisions(days, limit=50)
        elif query_type == 'sessions':
            data = db.get_session_outcomes(days, limit=50)
        elif query_type == 'summary':
            data = db.get_dashboard_summary(days)
        else:
            print(f"Unknown query: {query_type}")
            sys.exit(1)

        print(json.dumps(data, indent=2))

if __name__ == '__main__':
    main()
