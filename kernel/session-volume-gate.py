#!/usr/bin/env python3
"""
US-307: Session Volume Gate

Gates multiplier learning on sufficient data -- rare session types don't
learn from noise.  Tracks cumulative decisions per session type via
data/session-type-stats.jsonl and exposes a simple is_gated() predicate
consumed by the bandit engine.

Standalone: python3 kernel/session-volume-gate.py  (prints current counts)
"""

import json
import os
import sys
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
STATS_PATH = os.path.join(DATA_DIR, 'session-type-stats.jsonl')

DEFAULT_THRESHOLD = 100


def get_counts():
    """Return dict of session_type -> cumulative_count (latest per type)."""
    counts = {}
    if not os.path.exists(STATS_PATH):
        return counts
    try:
        with open(STATS_PATH, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                st = entry.get('session_type')
                cc = entry.get('cumulative_count')
                if st is not None and cc is not None:
                    counts[st] = cc
    except (IOError, json.JSONDecodeError):
        pass
    return counts


def record_decision(session_type):
    """Append a new entry for *session_type*, return the new cumulative count."""
    counts = get_counts()
    new_count = counts.get(session_type, 0) + 1

    os.makedirs(DATA_DIR, exist_ok=True)

    entry = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'session_type': session_type,
        'cumulative_count': new_count,
    }
    with open(STATS_PATH, 'a') as f:
        f.write(json.dumps(entry) + '\n')

    return new_count


def is_gated(session_type, threshold=DEFAULT_THRESHOLD):
    """True if *session_type* has fewer than *threshold* decisions recorded."""
    counts = get_counts()
    return counts.get(session_type, 0) < threshold


# ---------------------------------------------------------------------------
# Standalone usage
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    counts = get_counts()
    if not counts:
        print('No session-type stats recorded yet.')
        sys.exit(0)

    print('Session Volume Gate — current counts')
    print('=' * 45)
    for st in sorted(counts):
        gated = 'GATED' if counts[st] < DEFAULT_THRESHOLD else 'OK'
        print(f'  {st:20s}  {counts[st]:>6d}  [{gated}]')
