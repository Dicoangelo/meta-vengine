#!/usr/bin/env python3
"""
SQLite Migration: Backfill JSONL data to SQLite
Purpose: One-time migration of historical JSONL files to claude.db
Created: 2026-01-28
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

DATA_DIR = Path.home() / '.claude/data'
DB_PATH = DATA_DIR / 'claude.db'

class MigrationStats:
    def __init__(self):
        self.stats = defaultdict(lambda: {'inserted': 0, 'skipped': 0, 'errors': 0})
        self.start_time = time.time()

    def record(self, table: str, status: str):
        self.stats[table][status] += 1

    def report(self):
        elapsed = time.time() - self.start_time
        print("\n" + "="*60)
        print("MIGRATION REPORT")
        print("="*60)

        total_inserted = sum(s['inserted'] for s in self.stats.values())
        total_errors = sum(s['errors'] for s in self.stats.values())

        for table, counts in sorted(self.stats.items()):
            print(f"\n{table}:")
            print(f"  ✅ Inserted: {counts['inserted']:,}")
            if counts['skipped'] > 0:
                print(f"  ⏭️  Skipped:  {counts['skipped']:,}")
            if counts['errors'] > 0:
                print(f"  ❌ Errors:   {counts['errors']:,}")

        print(f"\n{'='*60}")
        print(f"Total: {total_inserted:,} records inserted")
        print(f"Errors: {total_errors:,}")
        print(f"Time: {elapsed:.2f}s ({total_inserted/elapsed:.0f} records/sec)")
        print(f"{'='*60}\n")

def backfill_tool_events(conn: sqlite3.Connection, stats: MigrationStats):
    """Migrate tool-usage.jsonl to tool_events table"""
    jsonl_path = DATA_DIR / 'tool-usage.jsonl'

    if not jsonl_path.exists():
        print(f"⚠️  {jsonl_path} not found, skipping...")
        return

    print(f"📂 Migrating {jsonl_path.name}...")

    cursor = conn.cursor()
    batch = []
    batch_size = 1000

    with open(jsonl_path) as f:
        for line_num, line in enumerate(f, 1):
            try:
                event = json.loads(line.strip())

                # Extract fields (handle various formats)
                timestamp = event.get('timestamp', event.get('ts', int(time.time())))
                tool_name = event.get('tool', event.get('tool_name', 'unknown'))
                success = 1 if event.get('success', True) else 0
                duration_ms = event.get('duration', event.get('duration_ms'))
                error_message = event.get('error')
                context = json.dumps(event.get('context', {})) if 'context' in event else None

                batch.append((timestamp, tool_name, success, duration_ms, error_message, context))

                if len(batch) >= batch_size:
                    cursor.executemany("""
                        INSERT INTO tool_events (timestamp, tool_name, success, duration_ms, error_message, context)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, batch)
                    stats.record('tool_events', 'inserted')
                    batch = []

                    if line_num % 10000 == 0:
                        print(f"  ... {line_num:,} lines processed")
                        conn.commit()

            except Exception as e:
                print(f"  ⚠️  Line {line_num}: {e}")
                stats.record('tool_events', 'errors')

        # Insert remaining batch
        if batch:
            cursor.executemany("""
                INSERT INTO tool_events (timestamp, tool_name, success, duration_ms, error_message, context)
                VALUES (?, ?, ?, ?, ?, ?)
            """, batch)
            stats.stats['tool_events']['inserted'] += len(batch)

    conn.commit()
    print(f"✅ tool_events migrated")

def backfill_activity_events(conn: sqlite3.Connection, stats: MigrationStats):
    """Migrate activity-events.jsonl to activity_events table"""
    jsonl_path = DATA_DIR / 'activity-events.jsonl'

    if not jsonl_path.exists():
        print(f"⚠️  {jsonl_path} not found, skipping...")
        return

    print(f"📂 Migrating {jsonl_path.name}...")

    cursor = conn.cursor()
    batch = []
    batch_size = 1000

    with open(jsonl_path) as f:
        for line_num, line in enumerate(f, 1):
            try:
                event = json.loads(line.strip())

                timestamp = event.get('timestamp', event.get('ts', int(time.time())))
                event_type = event.get('type', event.get('event_type', 'unknown'))
                session_id = event.get('session_id')

                # Store remaining data as JSON
                data = {k: v for k, v in event.items() if k not in ('timestamp', 'ts', 'type', 'event_type', 'session_id')}
                data_json = json.dumps(data) if data else None

                batch.append((timestamp, event_type, data_json, session_id))

                if len(batch) >= batch_size:
                    cursor.executemany("""
                        INSERT INTO activity_events (timestamp, event_type, data, session_id)
                        VALUES (?, ?, ?, ?)
                    """, batch)
                    stats.stats['activity_events']['inserted'] += len(batch)
                    batch = []

                    if line_num % 10000 == 0:
                        print(f"  ... {line_num:,} lines processed")
                        conn.commit()

            except Exception as e:
                print(f"  ⚠️  Line {line_num}: {e}")
                stats.record('activity_events', 'errors')

        if batch:
            cursor.executemany("""
                INSERT INTO activity_events (timestamp, event_type, data, session_id)
                VALUES (?, ?, ?, ?)
            """, batch)
            stats.stats['activity_events']['inserted'] += len(batch)

    conn.commit()
    print(f"✅ activity_events migrated")

def backfill_routing_events(conn: sqlite3.Connection, stats: MigrationStats):
    """Migrate routing-feedback.jsonl to routing_events table"""
    jsonl_path = DATA_DIR / 'routing-feedback.jsonl'

    if not jsonl_path.exists():
        print(f"⚠️  {jsonl_path} not found, skipping...")
        return

    print(f"📂 Migrating {jsonl_path.name}...")

    cursor = conn.cursor()
    batch = []

    with open(jsonl_path) as f:
        for line in f:
            try:
                event = json.loads(line.strip())

                timestamp = event.get('timestamp', int(time.time()))
                query_hash = event.get('query_hash')
                complexity = event.get('complexity')
                dq_score = event.get('dq_score')
                chosen_model = event.get('model', event.get('chosen_model'))
                reasoning = event.get('reasoning')
                feedback = event.get('feedback')

                batch.append((timestamp, query_hash, complexity, dq_score, chosen_model, reasoning, feedback))

                if len(batch) >= 500:
                    cursor.executemany("""
                        INSERT INTO routing_events (timestamp, query_hash, complexity, dq_score, chosen_model, reasoning, feedback)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, batch)
                    stats.stats['routing_events']['inserted'] += len(batch)
                    batch = []

            except Exception as e:
                stats.record('routing_events', 'errors')

        if batch:
            cursor.executemany("""
                INSERT INTO routing_events (timestamp, query_hash, complexity, dq_score, chosen_model, reasoning, feedback)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, batch)
            stats.stats['routing_events']['inserted'] += len(batch)

    conn.commit()
    print(f"✅ routing_events migrated")

def backfill_session_outcomes(conn: sqlite3.Connection, stats: MigrationStats):
    """Migrate session-outcomes.jsonl to session_outcome_events table"""
    jsonl_path = DATA_DIR / 'session-outcomes.jsonl'

    if not jsonl_path.exists():
        print(f"⚠️  {jsonl_path} not found, skipping...")
        return

    print(f"📂 Migrating {jsonl_path.name}...")

    cursor = conn.cursor()
    batch = []

    with open(jsonl_path) as f:
        for line in f:
            try:
                event = json.loads(line.strip())

                timestamp = event.get('timestamp', int(time.time()))
                session_id = event.get('session_id')
                outcome = event.get('outcome')
                quality_score = event.get('quality_score', event.get('quality'))
                complexity = event.get('complexity')
                model_used = event.get('model')
                cost = event.get('cost')
                message_count = event.get('message_count', event.get('messages'))

                batch.append((timestamp, session_id, outcome, quality_score, complexity, model_used, cost, message_count))

                if len(batch) >= 500:
                    cursor.executemany("""
                        INSERT INTO session_outcome_events (timestamp, session_id, outcome, quality_score, complexity, model_used, cost, message_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, batch)
                    stats.stats['session_outcome_events']['inserted'] += len(batch)
                    batch = []

            except Exception as e:
                stats.record('session_outcome_events', 'errors')

        if batch:
            cursor.executemany("""
                INSERT INTO session_outcome_events (timestamp, session_id, outcome, quality_score, complexity, model_used, cost, message_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            stats.stats['session_outcome_events']['inserted'] += len(batch)

    conn.commit()
    print(f"✅ session_outcome_events migrated")

def backfill_command_events(conn: sqlite3.Connection, stats: MigrationStats):
    """Migrate command-usage.jsonl to command_events table"""
    jsonl_path = DATA_DIR / 'command-usage.jsonl'

    if not jsonl_path.exists():
        print(f"⚠️  {jsonl_path} not found, skipping...")
        return

    print(f"📂 Migrating {jsonl_path.name}...")

    cursor = conn.cursor()
    batch = []

    with open(jsonl_path) as f:
        for line in f:
            try:
                event = json.loads(line.strip())

                timestamp = event.get('timestamp', int(time.time()))
                command = event.get('command')

                # Skip if command is None
                if not command:
                    stats.record('command_events', 'skipped')
                    continue

                args = json.dumps(event.get('args')) if 'args' in event else None
                success = 1 if event.get('success', True) else 0
                execution_time_ms = event.get('execution_time', event.get('execution_time_ms'))

                batch.append((timestamp, command, args, success, execution_time_ms))

                if len(batch) >= 500:
                    cursor.executemany("""
                        INSERT INTO command_events (timestamp, command, args, success, execution_time_ms)
                        VALUES (?, ?, ?, ?, ?)
                    """, batch)
                    stats.stats['command_events']['inserted'] += len(batch)
                    batch = []

            except Exception as e:
                stats.record('command_events', 'errors')

        if batch:
            cursor.executemany("""
                INSERT INTO command_events (timestamp, command, args, success, execution_time_ms)
                VALUES (?, ?, ?, ?, ?)
            """, batch)
            stats.stats['command_events']['inserted'] += len(batch)

    conn.commit()
    print(f"✅ command_events migrated")

def update_aggregated_tables(conn: sqlite3.Connection):
    """Update aggregated tool_usage table from raw tool_events"""
    print("\n📊 Updating aggregated tables...")

    cursor = conn.cursor()

    # Populate tool_usage from tool_events
    cursor.execute("""
        INSERT OR REPLACE INTO tool_usage (tool_name, total_calls, success_count, failure_count, last_used, avg_duration_ms)
        SELECT
            tool_name,
            COUNT(*) as total_calls,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failure_count,
            MAX(datetime(timestamp, 'unixepoch')) as last_used,
            AVG(duration_ms) as avg_duration_ms
        FROM tool_events
        GROUP BY tool_name
    """)

    rows_updated = cursor.rowcount
    conn.commit()

    print(f"✅ tool_usage updated ({rows_updated} tools)")

def verify_migration(conn: sqlite3.Connection):
    """Verify migration results"""
    print("\n🔍 Verifying migration...")

    cursor = conn.cursor()

    tables = [
        ('tool_events', 'tool-usage.jsonl'),
        ('activity_events', 'activity-events.jsonl'),
        ('routing_events', 'routing-feedback.jsonl'),
        ('session_outcome_events', 'session-outcomes.jsonl'),
        ('command_events', 'command-usage.jsonl')
    ]

    print("\nRow Counts:")
    print("-" * 60)

    for table, jsonl_file in tables:
        # SQLite count
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        db_count = cursor.fetchone()[0]

        # JSONL line count
        jsonl_path = DATA_DIR / jsonl_file
        if jsonl_path.exists():
            with open(jsonl_path) as f:
                jsonl_count = sum(1 for _ in f)

            match = "✅" if db_count == jsonl_count else "⚠️"
            print(f"{match} {table:25} {db_count:>8,} rows (JSONL: {jsonl_count:>8,})")
        else:
            print(f"⏭️  {table:25} {db_count:>8,} rows (JSONL: N/A)")

    # Check tool_usage
    cursor.execute("SELECT COUNT(*) FROM tool_usage")
    tool_usage_count = cursor.fetchone()[0]
    print(f"\n📊 tool_usage (aggregated):    {tool_usage_count:>8,} tools")

def main():
    print("="*60)
    print("SQLite Migration: JSONL → claude.db")
    print("="*60)

    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return 1

    stats = MigrationStats()
    conn = sqlite3.connect(DB_PATH)

    try:
        # Run backfills
        backfill_tool_events(conn, stats)
        backfill_activity_events(conn, stats)
        backfill_routing_events(conn, stats)
        backfill_session_outcomes(conn, stats)
        backfill_command_events(conn, stats)

        # Update aggregated tables
        update_aggregated_tables(conn)

        # Verify
        verify_migration(conn)

        # Report
        stats.report()

        print("✅ Migration complete!")
        return 0

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        conn.close()

if __name__ == '__main__':
    exit(main())
