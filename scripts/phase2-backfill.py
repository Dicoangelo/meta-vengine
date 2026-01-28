#!/usr/bin/env python3
"""
Phase 2: SQLite Backfill - Remaining JSONL Files
Purpose: Migrate routing-metrics, git-activity, self-heal, recovery data
Created: 2026-01-28
"""

import json
import sqlite3
import time
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path.home() / '.claude/data'
KERNEL_DIR = Path.home() / '.claude/kernel'
COORD_DIR = Path.home() / '.claude/coordinator/data'
DB_PATH = DATA_DIR / 'claude.db'

class Phase2Stats:
    def __init__(self):
        self.stats = defaultdict(lambda: {'inserted': 0, 'skipped': 0, 'errors': 0})
        self.start_time = time.time()

    def record(self, table: str, status: str):
        self.stats[table][status] += 1

    def report(self):
        elapsed = time.time() - self.start_time
        print("\n" + "="*60)
        print("PHASE 2 MIGRATION REPORT")
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
        print(f"Time: {elapsed:.2f}s")
        print(f"{'='*60}\n")

def backfill_routing_metrics(conn: sqlite3.Connection, stats: Phase2Stats):
    """Migrate routing-metrics.jsonl to routing_metrics_events"""
    jsonl_path = DATA_DIR / 'routing-metrics.jsonl'

    if not jsonl_path.exists():
        print(f"⚠️  {jsonl_path} not found, skipping...")
        return

    print(f"📂 Migrating {jsonl_path.name}...")

    cursor = conn.cursor()
    batch = []

    with open(jsonl_path) as f:
        for line_num, line in enumerate(f, 1):
            try:
                event = json.loads(line.strip())

                timestamp = event.get('timestamp', event.get('ts', int(time.time())))
                query_id = event.get('query_id', event.get('id'))
                predicted_model = event.get('predicted_model', event.get('predicted'))
                actual_model = event.get('actual_model', event.get('actual'))
                dq_score = event.get('dq_score', event.get('dq'))
                complexity = event.get('complexity')
                accuracy = 1 if event.get('correct', event.get('accuracy', True)) else 0
                cost_saved = event.get('cost_saved', event.get('savings'))
                reasoning = event.get('reasoning')
                query_text = event.get('query', event.get('query_text'))

                batch.append((timestamp, query_id, predicted_model, actual_model,
                             dq_score, complexity, accuracy, cost_saved, reasoning, query_text))

                if len(batch) >= 500:
                    cursor.executemany("""
                        INSERT INTO routing_metrics_events
                        (timestamp, query_id, predicted_model, actual_model, dq_score,
                         complexity, accuracy, cost_saved, reasoning, query_text)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, batch)
                    stats.stats['routing_metrics_events']['inserted'] += len(batch)
                    batch = []

            except Exception as e:
                print(f"  ⚠️  Line {line_num}: {e}")
                stats.record('routing_metrics_events', 'errors')

        if batch:
            cursor.executemany("""
                INSERT INTO routing_metrics_events
                (timestamp, query_id, predicted_model, actual_model, dq_score,
                 complexity, accuracy, cost_saved, reasoning, query_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            stats.stats['routing_metrics_events']['inserted'] += len(batch)

    conn.commit()
    print(f"✅ routing_metrics_events migrated")

def backfill_git_events(conn: sqlite3.Connection, stats: Phase2Stats):
    """Migrate git-activity.jsonl to git_events"""
    jsonl_path = DATA_DIR / 'git-activity.jsonl'

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

                timestamp = event.get('timestamp', event.get('ts', int(time.time())))
                event_type = event.get('type', event.get('event_type', 'commit'))
                repo = event.get('repo', event.get('repository'))
                branch = event.get('branch')
                commit_hash = event.get('commit', event.get('hash', event.get('commit_hash')))
                message = event.get('message', event.get('commit_message'))
                files_changed = event.get('files', event.get('files_changed'))
                additions = event.get('additions', event.get('insertions'))
                deletions = event.get('deletions')
                author = event.get('author', event.get('user'))

                batch.append((timestamp, event_type, repo, branch, commit_hash,
                             message, files_changed, additions, deletions, author))

                if len(batch) >= 500:
                    cursor.executemany("""
                        INSERT INTO git_events
                        (timestamp, event_type, repo, branch, commit_hash, message,
                         files_changed, additions, deletions, author)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, batch)
                    stats.stats['git_events']['inserted'] += len(batch)
                    batch = []

            except Exception as e:
                stats.record('git_events', 'errors')

        if batch:
            cursor.executemany("""
                INSERT INTO git_events
                (timestamp, event_type, repo, branch, commit_hash, message,
                 files_changed, additions, deletions, author)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            stats.stats['git_events']['inserted'] += len(batch)

    conn.commit()
    print(f"✅ git_events migrated")

def backfill_self_heal_events(conn: sqlite3.Connection, stats: Phase2Stats):
    """Migrate self-heal-outcomes.jsonl to self_heal_events"""
    jsonl_path = DATA_DIR / 'self-heal-outcomes.jsonl'

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

                timestamp = event.get('timestamp', event.get('ts', int(time.time())))
                error_pattern = event.get('pattern', event.get('error_pattern', 'unknown'))
                fix_applied = event.get('fix', event.get('fix_applied'))
                success = 1 if event.get('success', event.get('fixed', False)) else 0
                execution_time_ms = event.get('duration', event.get('execution_time_ms'))
                error_message = event.get('error', event.get('error_message'))
                severity = event.get('severity', 'medium')

                # Store remaining data as context JSON
                context = {k: v for k, v in event.items()
                          if k not in ('timestamp', 'ts', 'pattern', 'error_pattern',
                                      'fix', 'fix_applied', 'success', 'fixed',
                                      'duration', 'execution_time_ms', 'error',
                                      'error_message', 'severity')}
                context_json = json.dumps(context) if context else None

                batch.append((timestamp, error_pattern, fix_applied, success,
                             execution_time_ms, error_message, context_json, severity))

                if len(batch) >= 500:
                    cursor.executemany("""
                        INSERT INTO self_heal_events
                        (timestamp, error_pattern, fix_applied, success,
                         execution_time_ms, error_message, context, severity)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, batch)
                    stats.stats['self_heal_events']['inserted'] += len(batch)
                    batch = []

            except Exception as e:
                stats.record('self_heal_events', 'errors')

        if batch:
            cursor.executemany("""
                INSERT INTO self_heal_events
                (timestamp, error_pattern, fix_applied, success,
                 execution_time_ms, error_message, context, severity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            stats.stats['self_heal_events']['inserted'] += len(batch)

    conn.commit()
    print(f"✅ self_heal_events migrated")

def backfill_recovery_events(conn: sqlite3.Connection, stats: Phase2Stats):
    """Migrate recovery-outcomes.jsonl to recovery_events"""
    jsonl_path = DATA_DIR / 'recovery-outcomes.jsonl'

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

                timestamp = event.get('timestamp', event.get('ts', int(time.time())))
                error_type = event.get('error_type', event.get('type', 'unknown'))
                recovery_strategy = event.get('strategy', event.get('recovery_strategy'))
                success = 1 if event.get('success', event.get('recovered', False)) else 0
                attempts = event.get('attempts', 1)
                time_to_recover_ms = event.get('recovery_time', event.get('time_to_recover_ms'))
                error_details = event.get('details', event.get('error_details'))
                recovery_method = event.get('method', event.get('recovery_method', 'auto'))

                batch.append((timestamp, error_type, recovery_strategy, success,
                             attempts, time_to_recover_ms, error_details, recovery_method))

                if len(batch) >= 500:
                    cursor.executemany("""
                        INSERT INTO recovery_events
                        (timestamp, error_type, recovery_strategy, success,
                         attempts, time_to_recover_ms, error_details, recovery_method)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, batch)
                    stats.stats['recovery_events']['inserted'] += len(batch)
                    batch = []

            except Exception as e:
                stats.record('recovery_events', 'errors')

        if batch:
            cursor.executemany("""
                INSERT INTO recovery_events
                (timestamp, error_type, recovery_strategy, success,
                 attempts, time_to_recover_ms, error_details, recovery_method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            stats.stats['recovery_events']['inserted'] += len(batch)

    conn.commit()
    print(f"✅ recovery_events migrated")

def verify_migration(conn: sqlite3.Connection):
    """Verify migration results"""
    print("\n🔍 Verifying Phase 2 migration...")

    cursor = conn.cursor()

    tables = [
        ('routing_metrics_events', 'routing-metrics.jsonl'),
        ('git_events', 'git-activity.jsonl'),
        ('self_heal_events', 'self-heal-outcomes.jsonl'),
        ('recovery_events', 'recovery-outcomes.jsonl')
    ]

    print("\nRow Counts:")
    print("-" * 60)

    for table, jsonl_file in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        db_count = cursor.fetchone()[0]

        jsonl_path = DATA_DIR / jsonl_file
        if jsonl_path.exists():
            with open(jsonl_path) as f:
                jsonl_count = sum(1 for _ in f)

            match = "✅" if db_count == jsonl_count else "⚠️"
            print(f"{match} {table:30} {db_count:>6,} rows (JSONL: {jsonl_count:>6,})")
        else:
            print(f"⏭️  {table:30} {db_count:>6,} rows (JSONL: N/A)")

def main():
    print("="*60)
    print("Phase 2: SQLite Migration - Remaining JSONL Files")
    print("="*60)

    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return 1

    stats = Phase2Stats()
    conn = sqlite3.connect(DB_PATH)

    try:
        # Run backfills (top priority first)
        backfill_routing_metrics(conn, stats)
        backfill_git_events(conn, stats)
        backfill_self_heal_events(conn, stats)
        backfill_recovery_events(conn, stats)

        # Verify
        verify_migration(conn)

        # Report
        stats.report()

        print("✅ Phase 2 migration complete!")
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
