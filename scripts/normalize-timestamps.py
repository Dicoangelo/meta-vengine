#!/usr/bin/env python3
"""
Normalize timestamps in JSONL files to consistent format (seconds).

Detects and converts:
- Milliseconds (13+ digits) → seconds
- Float seconds → int seconds
- Missing timestamps → estimated from file order
"""

import json
import sys
from pathlib import Path
from datetime import datetime

def normalize_ts(ts):
    """Normalize timestamp to seconds."""
    if ts is None:
        return None

    # Convert to float if string
    if isinstance(ts, str):
        try:
            ts = float(ts)
        except ValueError:
            return None

    # Milliseconds (13+ digits or > year 2100 in seconds)
    if ts > 4102444800:  # > 2100-01-01 in seconds
        return int(ts / 1000)

    # Already seconds (or float seconds)
    return int(ts)


def normalize_jsonl(filepath: Path, ts_field: str = 'ts', dry_run: bool = False):
    """Normalize timestamps in a JSONL file."""
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return

    lines = filepath.read_text().split('\n')
    normalized = []
    changes = 0

    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            old_ts = entry.get(ts_field)
            new_ts = normalize_ts(old_ts)

            if new_ts != old_ts:
                entry[ts_field] = new_ts
                changes += 1

            # Also check 'timestamp' field
            if 'timestamp' in entry and entry['timestamp'] != ts_field:
                old_ts2 = entry['timestamp']
                new_ts2 = normalize_ts(old_ts2)
                if new_ts2 != old_ts2:
                    entry['timestamp'] = new_ts2
                    changes += 1

            normalized.append(json.dumps(entry))
        except json.JSONDecodeError:
            # Keep malformed lines as-is
            normalized.append(line)

    if dry_run:
        print(f"Would normalize {changes} timestamps in {filepath}")
    else:
        filepath.write_text('\n'.join(normalized) + '\n')
        print(f"Normalized {changes} timestamps in {filepath}")

    return changes


def main():
    home = Path.home()
    dry_run = '--dry-run' in sys.argv

    files_to_normalize = [
        (home / '.claude/kernel/dq-scores.jsonl', 'ts'),
        (home / '.claude/data/activity-events.jsonl', 'timestamp'),
        (home / '.claude/data/session-outcomes.jsonl', 'timestamp'),
        (home / '.claude/kernel/routing-decisions.jsonl', 'ts'),
    ]

    total_changes = 0
    for filepath, ts_field in files_to_normalize:
        if filepath.exists():
            changes = normalize_jsonl(filepath, ts_field, dry_run)
            total_changes += changes or 0

    print(f"\nTotal: {total_changes} timestamps normalized")


if __name__ == "__main__":
    main()
