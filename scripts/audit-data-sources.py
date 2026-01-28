#!/usr/bin/env python3
"""
Audit ALL data sources in .claude and identify orphaned/stale files.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"

# Files that SHOULD be tracked by fix-all-dashboard-data.py
TRACKED_FILES = {
    "stats-cache.json",
    "activity-timeline.json",
    "knowledge.json",
    "identity.json",
    "cost-summary.json",
    "tool-summary.json",
    "subscription-data.json",
    "coevo-config.json",
    "coevo-data.json",
    "pack-metrics.json",
    "session-outcomes.jsonl",
    "routing-metrics.jsonl",
    "dq-scores.jsonl",
    "detected-patterns.json",
    "git-activity.jsonl",
    "modifications.jsonl",
    "cost-tracking.jsonl",
}

def find_all_data_files():
    """Find all JSON/JSONL files in .claude"""
    files = []
    for pattern in ["**/*.json", "**/*.jsonl"]:
        for f in CLAUDE_DIR.glob(pattern):
            # Skip node_modules, venv, project transcripts
            if any(skip in str(f) for skip in ["node_modules", ".venv", "/projects/-Users"]):
                continue
            files.append(f)
    return files

def categorize_files(files):
    """Categorize files by location and tracking status"""
    categorized = {
        "tracked": [],
        "untracked_kernel": [],
        "untracked_data": [],
        "untracked_memory": [],
        "stale": [],  # > 7 days old
    }

    now = datetime.now()
    week_ago = now - timedelta(days=7)

    for f in files:
        name = f.name
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        size = f.stat().st_size

        # Check if tracked
        is_tracked = name in TRACKED_FILES

        # Check if stale
        is_stale = mtime < week_ago and size > 100  # Ignore tiny files

        info = {
            "path": str(f.relative_to(CLAUDE_DIR)),
            "name": name,
            "size": size,
            "mtime": mtime.strftime("%Y-%m-%d %H:%M"),
            "age_days": (now - mtime).days,
        }

        if is_tracked:
            categorized["tracked"].append(info)
        elif "kernel" in str(f):
            categorized["untracked_kernel"].append(info)
        elif "data" in str(f):
            categorized["untracked_data"].append(info)
        elif "memory" in str(f):
            categorized["untracked_memory"].append(info)

        if is_stale:
            categorized["stale"].append(info)

    return categorized

def print_report(categorized):
    """Print audit report"""
    print("\n" + "="*70)
    print("DATA SOURCE AUDIT")
    print("="*70 + "\n")

    print(f"📊 TRACKED FILES ({len(categorized['tracked'])})")
    print("These are actively monitored by fix-all-dashboard-data.py:")
    for f in sorted(categorized['tracked'], key=lambda x: x['age_days'], reverse=True)[:10]:
        print(f"  ✓ {f['name']:40s} {f['mtime']} ({f['age_days']}d)")

    print(f"\n⚠️  UNTRACKED DATA FILES ({len(categorized['untracked_data'])})")
    print("These exist in data/ but aren't being read:")
    for f in sorted(categorized['untracked_data'], key=lambda x: x['age_days'], reverse=True):
        print(f"  ✗ {f['name']:40s} {f['mtime']} ({f['age_days']}d) {f['size']:>8,} bytes")

    print(f"\n⚠️  UNTRACKED KERNEL FILES ({len(categorized['untracked_kernel'])})")
    print("These exist in kernel/ but aren't being read:")
    for f in sorted(categorized['untracked_kernel'], key=lambda x: x['age_days'], reverse=True)[:15]:
        print(f"  ✗ {f['path']:60s} {f['mtime']} ({f['age_days']}d)")

    print(f"\n🕰️  STALE FILES ({len(categorized['stale'])}) - >7 days old")
    for f in sorted(categorized['stale'], key=lambda x: x['age_days'], reverse=True)[:20]:
        print(f"  ⏰ {f['path']:60s} {f['mtime']} ({f['age_days']}d)")

    print("\n" + "="*70)

    # Generate fix suggestions
    print("\n💡 RECOMMENDATIONS:")
    print("="*70)

    critical_untracked = []
    for f in categorized['untracked_data'] + categorized['untracked_kernel']:
        if f['age_days'] > 1 and f['size'] > 1000:  # > 1 day old and > 1KB
            critical_untracked.append(f)

    if critical_untracked:
        print("\nAdd these files to fix-all-dashboard-data.py:")
        for f in critical_untracked:
            print(f"  - {f['path']}")

    print("\nStale files to investigate:")
    for f in categorized['stale'][:10]:
        if f['age_days'] > 14:  # > 2 weeks
            print(f"  - {f['path']} ({f['age_days']} days old)")

if __name__ == "__main__":
    files = find_all_data_files()
    categorized = categorize_files(files)
    print_report(categorized)
