#!/usr/bin/env python3
"""
Apply category column migration to self_heal_events table.

This migration:
1. Adds 'category' column if it doesn't exist
2. Creates an index on the category column
3. Backfills categories from recovery-outcomes.jsonl
"""

import sqlite3
import json
import os
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "data" / "antigravity.db"
RECOVERY_OUTCOMES = Path.home() / ".claude" / "data" / "recovery-outcomes.jsonl"


def column_exists(cursor, table, column):
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def apply_migration():
    """Apply the category column migration."""
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='self_heal_events'
        """)
        if not cursor.fetchone():
            print("Table 'self_heal_events' does not exist, creating it...")
            cursor.execute("""
                CREATE TABLE self_heal_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER,
                    error_pattern TEXT,
                    action TEXT,
                    success INTEGER,
                    category TEXT DEFAULT 'unknown'
                )
            """)
            conn.commit()
            print("Created self_heal_events table with category column")
            return True

        # Check if column already exists
        if column_exists(cursor, "self_heal_events", "category"):
            print("Column 'category' already exists in self_heal_events")
        else:
            # Add the category column
            print("Adding 'category' column to self_heal_events...")
            cursor.execute("""
                ALTER TABLE self_heal_events
                ADD COLUMN category TEXT DEFAULT 'unknown'
            """)
            conn.commit()
            print("Added 'category' column successfully")

        # Check if index exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='idx_self_heal_category'
        """)
        if not cursor.fetchone():
            print("Creating index on category column...")
            cursor.execute("""
                CREATE INDEX idx_self_heal_category
                ON self_heal_events(category)
            """)
            conn.commit()
            print("Created index 'idx_self_heal_category'")
        else:
            print("Index 'idx_self_heal_category' already exists")

        # Backfill categories from recovery-outcomes.jsonl if available
        backfill_count = backfill_categories(cursor)
        if backfill_count > 0:
            conn.commit()
            print(f"Backfilled {backfill_count} categories")

        print("Migration completed successfully!")
        return True

    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def categorize_error(error_pattern):
    """Determine category from error pattern."""
    if not error_pattern:
        return "unknown"

    error_lower = error_pattern.lower()

    # Git-related errors
    if any(x in error_lower for x in ["git", "remote", "push", "pull", "merge", "commit", "branch"]):
        return "git"

    # Permission errors
    if any(x in error_lower for x in ["permission", "denied", "access", "chmod", "chown"]):
        return "permissions"

    # Lock/concurrency errors
    if any(x in error_lower for x in ["lock", "locked", "concurrent", "race", "stale"]):
        return "concurrency"

    # Cache errors
    if any(x in error_lower for x in ["cache", "cached", "invalidate"]):
        return "cache"

    # Path/file errors
    if any(x in error_lower for x in ["path", "file", "directory", "not found", "missing"]):
        return "filesystem"

    # Network errors
    if any(x in error_lower for x in ["network", "connection", "timeout", "socket"]):
        return "network"

    # Database errors
    if any(x in error_lower for x in ["database", "sqlite", "sql", "query"]):
        return "database"

    return "other"


def backfill_categories(cursor):
    """Backfill categories for existing events."""
    # First, update events that have 'unknown' or NULL category
    cursor.execute("""
        SELECT id, error_pattern FROM self_heal_events
        WHERE category IS NULL OR category = 'unknown'
    """)
    rows = cursor.fetchall()

    updated = 0
    for row_id, error_pattern in rows:
        category = categorize_error(error_pattern)
        if category != "unknown":
            cursor.execute("""
                UPDATE self_heal_events
                SET category = ?
                WHERE id = ?
            """, (category, row_id))
            updated += 1

    # Also try to import from recovery-outcomes.jsonl
    if RECOVERY_OUTCOMES.exists():
        try:
            with open(RECOVERY_OUTCOMES, 'r') as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        if 'category' in event and 'error_pattern' in event:
                            # Update matching events with the category from file
                            cursor.execute("""
                                UPDATE self_heal_events
                                SET category = ?
                                WHERE error_pattern = ? AND (category IS NULL OR category = 'unknown')
                            """, (event['category'], event['error_pattern']))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Warning: Could not read recovery-outcomes.jsonl: {e}")

    return updated


if __name__ == "__main__":
    success = apply_migration()
    exit(0 if success else 1)
