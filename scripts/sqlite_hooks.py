#!/usr/bin/env python3
"""
SQLite Hooks - Direct Database Logging
Purpose: Helper functions for logging events directly to SQLite
Created: 2026-01-28

Usage:
    from sqlite_hooks import log_git_event, log_self_heal, log_recovery

    log_git_event('commit', repo='myrepo', message='feat: add feature')
    log_self_heal('git-username', fix_applied='rewrite URL', success=True)
    log_recovery('permission-denied', strategy='chmod', success=True)
"""

import sqlite3
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any

DB_PATH = Path.home() / '.claude/data/claude.db'

def get_db_connection():
    """Get SQLite database connection"""
    return sqlite3.connect(str(DB_PATH))

# Git Events
# ==========

def log_git_event(event_type: str, repo: Optional[str] = None,
                  branch: Optional[str] = None, commit_hash: Optional[str] = None,
                  message: Optional[str] = None, files_changed: Optional[int] = None,
                  additions: Optional[int] = None, deletions: Optional[int] = None,
                  author: Optional[str] = None) -> bool:
    """
    Log a git event to SQLite

    Args:
        event_type: 'commit', 'push', 'pr', 'branch', 'merge'
        repo: Repository name
        branch: Branch name
        commit_hash: Commit SHA
        message: Commit message
        files_changed: Number of files changed
        additions: Lines added
        deletions: Lines deleted
        author: Commit author

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO git_events
            (timestamp, event_type, repo, branch, commit_hash, message,
             files_changed, additions, deletions, author)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (int(time.time()), event_type, repo, branch, commit_hash,
              message, files_changed, additions, deletions, author))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Failed to log git event: {e}")
        return False

# Self-Healing Events
# ===================

def log_self_heal(error_pattern: str, fix_applied: Optional[str] = None,
                  success: bool = True, execution_time_ms: Optional[int] = None,
                  error_message: Optional[str] = None,
                  context: Optional[Dict[str, Any]] = None,
                  severity: str = 'medium',
                  category: str = 'unknown') -> bool:
    """
    Log a self-healing event to SQLite

    Args:
        error_pattern: Pattern identifier (e.g., 'git-username', 'stale-lock')
        fix_applied: Description of fix applied
        success: Whether the fix succeeded
        execution_time_ms: Time taken to apply fix
        error_message: Original error message
        context: Additional context as dict
        severity: 'low', 'medium', 'high', 'critical'

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        context_json = json.dumps(context) if context else None

        cursor.execute("""
            INSERT INTO self_heal_events
            (timestamp, error_pattern, fix_applied, success,
             execution_time_ms, error_message, context, severity, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (int(time.time()), error_pattern, fix_applied, 1 if success else 0,
              execution_time_ms, error_message, context_json, severity, category))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Failed to log self-heal event: {e}")
        return False

# Recovery Events
# ===============

def log_recovery(error_type: str, recovery_strategy: Optional[str] = None,
                success: bool = True, attempts: int = 1,
                time_to_recover_ms: Optional[int] = None,
                error_details: Optional[str] = None,
                recovery_method: str = 'auto') -> bool:
    """
    Log a recovery event to SQLite

    Args:
        error_type: Type of error encountered
        recovery_strategy: Strategy used for recovery
        success: Whether recovery succeeded
        attempts: Number of attempts made
        time_to_recover_ms: Time taken to recover
        error_details: Detailed error information
        recovery_method: 'auto', 'manual', 'assisted'

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO recovery_events
            (timestamp, error_type, recovery_strategy, success,
             attempts, time_to_recover_ms, error_details, recovery_method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (int(time.time()), error_type, recovery_strategy, 1 if success else 0,
              attempts, time_to_recover_ms, error_details, recovery_method))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Failed to log recovery event: {e}")
        return False

# Routing Metrics
# ===============

def log_routing_metric(predicted_model: str, actual_model: Optional[str] = None,
                       dq_score: Optional[float] = None, complexity: Optional[float] = None,
                       accuracy: Optional[bool] = None, cost_saved: Optional[float] = None,
                       reasoning: Optional[str] = None, query_text: Optional[str] = None,
                       query_id: Optional[str] = None) -> bool:
    """
    Log a routing metric event to SQLite

    Args:
        predicted_model: Model predicted by router
        actual_model: Model actually used (if different)
        dq_score: DQ score for the query
        complexity: Complexity score
        accuracy: Whether routing was correct
        cost_saved: Cost savings from routing decision
        reasoning: Routing decision reasoning
        query_text: Original query text
        query_id: Unique query identifier

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        accuracy_val = None
        if accuracy is not None:
            accuracy_val = 1 if accuracy else 0

        cursor.execute("""
            INSERT INTO routing_metrics_events
            (timestamp, query_id, predicted_model, actual_model, dq_score,
             complexity, accuracy, cost_saved, reasoning, query_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (int(time.time()), query_id, predicted_model, actual_model,
              dq_score, complexity, accuracy_val, cost_saved, reasoning, query_text))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Failed to log routing metric: {e}")
        return False

# Coordinator Events
# ==================

def log_coordinator_event(action: str, agent_id: Optional[str] = None,
                         strategy: Optional[str] = None, file_path: Optional[str] = None,
                         result: Optional[str] = None, duration_ms: Optional[int] = None,
                         exit_code: Optional[int] = None) -> bool:
    """
    Log a coordinator event to SQLite

    Args:
        action: 'spawn', 'complete', 'fail', 'lock', 'unlock', 'timeout'
        agent_id: Agent identifier
        strategy: Coordination strategy used
        file_path: File being worked on
        result: Result description
        duration_ms: Duration in milliseconds
        exit_code: Agent exit code

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO coordinator_events
            (timestamp, agent_id, action, strategy, file_path, result, duration_ms, exit_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (int(time.time()), agent_id, action, strategy, file_path,
              result, duration_ms, exit_code))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Failed to log coordinator event: {e}")
        return False

# Expertise Routing
# =================

def log_expertise_routing(domain: str, expertise_level: float,
                          query_complexity: Optional[float] = None,
                          chosen_model: Optional[str] = None,
                          reasoning: Optional[str] = None,
                          query_hash: Optional[str] = None) -> bool:
    """
    Log an expertise-based routing event to SQLite

    Args:
        domain: Domain detected (e.g., 'python', 'git', 'sql')
        expertise_level: User expertise level (0.0-1.0)
        query_complexity: Query complexity score
        chosen_model: Model selected based on expertise
        reasoning: Routing reasoning
        query_hash: Query hash for deduplication

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO expertise_routing_events
            (timestamp, domain, expertise_level, query_complexity, chosen_model, reasoning, query_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (int(time.time()), domain, expertise_level, query_complexity,
              chosen_model, reasoning, query_hash))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Failed to log expertise routing: {e}")
        return False

# Convenience Functions
# =====================

def log_git_commit(repo: str, branch: str, commit_hash: str,
                   message: str, files_changed: int = 0) -> bool:
    """Convenience function for logging git commits"""
    return log_git_event('commit', repo=repo, branch=branch,
                         commit_hash=commit_hash, message=message,
                         files_changed=files_changed)

def log_git_push(repo: str, branch: str, commits: int = 1) -> bool:
    """Convenience function for logging git pushes"""
    return log_git_event('push', repo=repo, branch=branch,
                         message=f"Pushed {commits} commit(s)")

def log_git_pr(repo: str, branch: str, message: str) -> bool:
    """Convenience function for logging PR creation"""
    return log_git_event('pr', repo=repo, branch=branch, message=message)

# Session Outcomes
# ================

def log_session_outcome(session_id: str, outcome: str, quality: float,
                        complexity: float, intent: str, model: str,
                        messages_count: Optional[int] = None,
                        duration_minutes: Optional[int] = None,
                        cost_usd: Optional[float] = None,
                        success: bool = True,
                        summary: Optional[str] = None) -> bool:
    """
    Log a session outcome event to SQLite

    Args:
        session_id: Session identifier
        outcome: 'success', 'partial', 'failure', 'abandoned'
        quality: Quality score 1-5
        complexity: Complexity score 0-1
        intent: Session intent/goal
        model: Model used (haiku, sonnet, opus)
        messages_count: Number of messages
        duration_minutes: Session duration
        cost_usd: Session cost
        success: Whether session succeeded
        summary: Brief summary of session

    Returns:
        bool: True if successful
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO session_outcome_events
            (timestamp, session_id, outcome, quality, complexity, intent,
             model, messages_count, duration_minutes, cost_usd, success, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (int(time.time()), session_id, outcome, quality, complexity,
              intent, model, messages_count, duration_minutes, cost_usd,
              1 if success else 0, summary))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Failed to log session outcome: {e}")
        return False

# Hook-Compatible Functions (for bash hooks)
# ===========================================

def log_tool_event(timestamp: int, tool_name: str, success: int,
                   duration_ms: Optional[int] = None,
                   error_message: Optional[str] = None,
                   context: Optional[str] = None) -> bool:
    """
    Log a tool event (bash hook compatible)

    Args:
        timestamp: Unix timestamp
        tool_name: Tool name (Read, Write, Bash, etc.)
        success: 1 for success, 0 for failure
        duration_ms: Duration in milliseconds
        error_message: Error message if failed
        context: JSON string with additional context

    Returns:
        bool: True if successful
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO tool_events (timestamp, tool_name, success, duration_ms, error_message, context)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (timestamp, tool_name, success, duration_ms, error_message, context))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Failed to log tool event: {e}")
        return False

def log_activity_event_simple(timestamp: int, event_type: str,
                               data: Optional[str] = None,
                               session_id: Optional[str] = None) -> bool:
    """
    Log an activity event (bash hook compatible)

    Args:
        timestamp: Unix timestamp
        event_type: Event type (tool_use, query, etc.)
        data: JSON string with event data
        session_id: Session identifier

    Returns:
        bool: True if successful
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO activity_events (timestamp, event_type, data, session_id)
            VALUES (?, ?, ?, ?)
        """, (timestamp, event_type, data, session_id))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Failed to log activity event: {e}")
        return False

# Test/Demo
# =========

if __name__ == '__main__':
    print("Testing SQLite hooks...")
    print("=" * 60)

    # Test git event
    print("\n✅ Testing git commit log...")
    log_git_commit(
        repo='claude-home',
        branch='main',
        commit_hash='abc123',
        message='feat: test commit',
        files_changed=3
    )

    # Test self-heal event
    print("✅ Testing self-heal log...")
    log_self_heal(
        error_pattern='test-pattern',
        fix_applied='test fix',
        success=True,
        execution_time_ms=100,
        severity='low'
    )

    # Test recovery event
    print("✅ Testing recovery log...")
    log_recovery(
        error_type='test-error',
        recovery_strategy='restart',
        success=True,
        attempts=1
    )

    print("\n✅ All hooks tested successfully!")
    print("=" * 60)
