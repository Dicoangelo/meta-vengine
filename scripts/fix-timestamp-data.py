#!/usr/bin/env python3
"""
Data Normalization Script

Normalizes timestamps in existing JSONL files from milliseconds to seconds.
This is a one-time migration to fix the "Year 58034" errors.

Files to normalize:
- ~/.claude/kernel/dq-scores.jsonl (ts field)
- ~/.claude/data/activity-events.jsonl (timestamp field)
- ~/.claude/data/session-outcomes.jsonl (timestamp field)

Also backfills categories from recovery-outcomes.jsonl to self_heal_events table.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
import shutil
import sqlite3

# Import timestamp normalization
sys.path.insert(0, str(Path.home() / ".claude/scripts"))
from lib.timestamps import normalize_ts, MS_THRESHOLD

HOME = Path.home()
DATA_DIR = HOME / ".claude" / "data"
KERNEL_DIR = HOME / ".claude" / "kernel"
DB_PATH = DATA_DIR / "antigravity.db"

# Files to process with their timestamp field names
FILES_TO_NORMALIZE = [
    (KERNEL_DIR / "dq-scores.jsonl", "ts"),
    (DATA_DIR / "activity-events.jsonl", "timestamp"),
    (DATA_DIR / "session-outcomes.jsonl", "timestamp"),
]


def backup_file(filepath: Path) -> Path:
    """Create a backup of the file before modifying."""
    backup_path = filepath.with_suffix(filepath.suffix + ".bak")
    if filepath.exists():
        shutil.copy2(filepath, backup_path)
        return backup_path
    return None


def normalize_jsonl_file(filepath: Path, ts_field: str, dry_run: bool = False) -> dict:
    """
    Normalize timestamps in a JSONL file.

    Returns stats about the normalization.
    """
    stats = {
        "file": str(filepath),
        "total": 0,
        "normalized": 0,
        "already_ok": 0,
        "missing_field": 0,
        "errors": 0,
    }

    if not filepath.exists():
        stats["error"] = "File not found"
        return stats

    # Read all lines
    lines = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            stats["total"] += 1
            try:
                record = json.loads(line)
                ts = record.get(ts_field)

                if ts is None:
                    stats["missing_field"] += 1
                    lines.append(record)
                    continue

                # Check if it's in milliseconds (> year 2100 in seconds)
                if isinstance(ts, (int, float)) and ts > MS_THRESHOLD:
                    # Convert to seconds
                    record[ts_field] = int(ts / 1000)
                    stats["normalized"] += 1
                else:
                    stats["already_ok"] += 1

                lines.append(record)

            except json.JSONDecodeError as e:
                stats["errors"] += 1
                # Keep original line
                lines.append(None)  # Will be skipped

    if dry_run:
        return stats

    # Write back normalized data
    with open(filepath, 'w') as f:
        for record in lines:
            if record is not None:
                f.write(json.dumps(record) + '\n')

    return stats


def backfill_categories() -> dict:
    """Backfill categories from recovery-outcomes.jsonl to self_heal_events table."""
    stats = {
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }

    recovery_file = DATA_DIR / "recovery-outcomes.jsonl"
    if not recovery_file.exists():
        stats["error"] = "recovery-outcomes.jsonl not found"
        return stats

    if not DB_PATH.exists():
        stats["error"] = "Database not found"
        return stats

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        with open(recovery_file, 'r') as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    category = event.get('category')
                    error_pattern = event.get('error_pattern')

                    if category and error_pattern:
                        cursor.execute("""
                            UPDATE self_heal_events
                            SET category = ?
                            WHERE error_pattern = ? AND (category IS NULL OR category = 'unknown')
                        """, (category, error_pattern))

                        if cursor.rowcount > 0:
                            stats["updated"] += cursor.rowcount
                        else:
                            stats["skipped"] += 1
                    else:
                        stats["skipped"] += 1

                except json.JSONDecodeError:
                    stats["errors"] += 1
                    continue

        conn.commit()

    except Exception as e:
        stats["error"] = str(e)
        conn.rollback()
    finally:
        conn.close()

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Normalize timestamps in JSONL files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without modifying files")
    parser.add_argument("--backup", action="store_true", help="Create backups before modifying (default: True)")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating backups")
    args = parser.parse_args()

    create_backup = not args.no_backup

    print("=" * 60)
    print("Timestamp Normalization Script")
    print("=" * 60)

    if args.dry_run:
        print("\n[DRY RUN] No files will be modified\n")

    # Process each file
    for filepath, ts_field in FILES_TO_NORMALIZE:
        print(f"\nProcessing: {filepath.name}")
        print(f"  Timestamp field: {ts_field}")

        if create_backup and not args.dry_run and filepath.exists():
            backup_path = backup_file(filepath)
            if backup_path:
                print(f"  Backup created: {backup_path.name}")

        stats = normalize_jsonl_file(filepath, ts_field, dry_run=args.dry_run)

        if "error" in stats:
            print(f"  Error: {stats['error']}")
            continue

        print(f"  Total records: {stats['total']}")
        print(f"  Normalized (ms->s): {stats['normalized']}")
        print(f"  Already OK: {stats['already_ok']}")
        print(f"  Missing timestamp: {stats['missing_field']}")
        if stats['errors']:
            print(f"  Parse errors: {stats['errors']}")

    # Backfill categories
    print("\n" + "-" * 40)
    print("Backfilling categories in self_heal_events...")

    if args.dry_run:
        print("  [DRY RUN] Would update categories from recovery-outcomes.jsonl")
    else:
        cat_stats = backfill_categories()
        if "error" in cat_stats:
            print(f"  Error: {cat_stats['error']}")
        else:
            print(f"  Updated: {cat_stats['updated']}")
            print(f"  Skipped: {cat_stats['skipped']}")
            if cat_stats['errors']:
                print(f"  Errors: {cat_stats['errors']}")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
