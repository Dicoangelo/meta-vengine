#!/usr/bin/env python3
"""
Health Check & Auto-Backfill

Detects stale/missing data and executes appropriate backfills.
Run via cron or manually: python3 ~/.claude/scripts/health-check-backfill.py

Exit codes:
  0 = healthy (no action needed)
  1 = backfill executed
  2 = error
"""

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
KERNEL_DIR = CLAUDE_DIR / "kernel"
DATA_DIR = CLAUDE_DIR / "data"
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
MEMORY_DB = CLAUDE_DIR / "memory/supermemory.db"

# Thresholds
MAX_KERNEL_AGE_HOURS = 24
MAX_STATS_AGE_HOURS = 12
MIN_MEMORY_LINKS = 1000


def log(msg: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def check_file_freshness(filepath: Path, max_age_hours: int) -> tuple[bool, float]:
    """Check if file exists and is fresh. Returns (is_fresh, age_hours)."""
    if not filepath.exists():
        return False, float('inf')

    mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
    age = datetime.now() - mtime
    age_hours = age.total_seconds() / 3600
    return age_hours <= max_age_hours, age_hours


def check_json_updated_field(filepath: Path, max_age_hours: int) -> tuple[bool, float]:
    """Check the 'updated' field inside JSON. Returns (is_fresh, age_hours)."""
    if not filepath.exists():
        return False, float('inf')

    try:
        with open(filepath) as f:
            data = json.load(f)
        updated = data.get('updated') or data.get('lastUpdated') or data.get('generated')
        if not updated:
            return check_file_freshness(filepath, max_age_hours)

        updated_dt = datetime.fromisoformat(updated.replace('Z', '+00:00')).replace(tzinfo=None)
        age = datetime.now() - updated_dt
        age_hours = age.total_seconds() / 3600
        return age_hours <= max_age_hours, age_hours
    except Exception:
        return check_file_freshness(filepath, max_age_hours)


def check_memory_links() -> tuple[bool, int]:
    """Check if memory_links table has sufficient entries."""
    if not MEMORY_DB.exists():
        return False, 0

    try:
        conn = sqlite3.connect(str(MEMORY_DB))
        count = conn.execute("SELECT COUNT(*) FROM memory_links").fetchone()[0]
        conn.close()
        return count >= MIN_MEMORY_LINKS, count
    except Exception:
        return False, 0


def normalize_ts(ts):
    """Normalize timestamp to seconds (handles ms, seconds, floats)."""
    if ts is None:
        return None
    if isinstance(ts, str):
        try:
            ts = float(ts)
        except ValueError:
            return None
    # Milliseconds (> year 2100 in seconds)
    if ts > 4102444800:
        return int(ts / 1000)
    return int(ts)


def check_jsonl_health(filepath: Path) -> tuple[bool, int, int]:
    """Check JSONL file for parse errors. Returns (healthy, valid, invalid)."""
    if not filepath.exists():
        return True, 0, 0

    valid = 0
    invalid = 0
    for line in filepath.read_text().split('\n'):
        if not line.strip():
            continue
        try:
            json.loads(line)
            valid += 1
        except json.JSONDecodeError:
            invalid += 1

    error_rate = invalid / (valid + invalid) if (valid + invalid) > 0 else 0
    return error_rate < 0.05, valid, invalid  # <5% error rate is healthy


def run_backfill(script: str, description: str) -> bool:
    """Run a backfill script."""
    script_path = SCRIPTS_DIR / script
    if not script_path.exists():
        log(f"Script not found: {script_path}", "ERROR")
        return False

    log(f"Running backfill: {description}")
    try:
        result = subprocess.run(
            ["python3", str(script_path)],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            log(f"Backfill complete: {description}")
            return True
        else:
            log(f"Backfill failed: {result.stderr[:200]}", "ERROR")
            return False
    except subprocess.TimeoutExpired:
        log(f"Backfill timeout: {description}", "ERROR")
        return False
    except Exception as e:
        log(f"Backfill error: {e}", "ERROR")
        return False


def main():
    log("Starting health check")
    backfills_needed = []
    backfills_run = 0

    # 1. Check kernel data freshness
    for filename in ['cost-data.json', 'productivity-data.json', 'coevo-data.json']:
        filepath = KERNEL_DIR / filename
        is_fresh, age = check_json_updated_field(filepath, MAX_KERNEL_AGE_HOURS)
        if not is_fresh:
            log(f"Stale: {filename} ({age:.1f}h old)", "WARN")
            if 'regenerate-kernel-data.py' not in [b[0] for b in backfills_needed]:
                backfills_needed.append(('regenerate-kernel-data.py', 'Kernel data regeneration'))

    # 2. Check stats-cache freshness
    stats_fresh, stats_age = check_file_freshness(CLAUDE_DIR / 'stats-cache.json', MAX_STATS_AGE_HOURS)
    if not stats_fresh:
        log(f"Stale: stats-cache.json ({stats_age:.1f}h old)", "WARN")
        # stats-cache is updated by Claude Code itself, can't backfill

    # 3. Check memory links
    links_ok, links_count = check_memory_links()
    if not links_ok:
        log(f"Low memory links: {links_count} (need {MIN_MEMORY_LINKS}+)", "WARN")
        backfills_needed.append(('populate-memory-links.py', 'Memory links population'))

    # 4. Check JSONL health
    for jsonl_file in ['command-usage.jsonl', 'activity-events.jsonl', 'session-outcomes.jsonl']:
        filepath = DATA_DIR / jsonl_file
        healthy, valid, invalid = check_jsonl_health(filepath)
        if not healthy and invalid > 0:
            log(f"Corrupted: {jsonl_file} ({invalid} bad entries)", "WARN")
            backfills_needed.append(('clean-jsonl.py', f'Clean {jsonl_file}'))

    # 5. Check pack metrics
    pack_metrics = DATA_DIR / 'pack-metrics.json'
    pm_fresh, pm_age = check_json_updated_field(pack_metrics, MAX_KERNEL_AGE_HOURS * 2)
    if not pm_fresh:
        log(f"Stale: pack-metrics.json ({pm_age:.1f}h old)", "WARN")
        backfills_needed.append(('generate-pack-metrics.py', 'Pack metrics generation'))

    # Execute backfills
    if backfills_needed:
        log(f"Backfills needed: {len(backfills_needed)}")
        for script, description in backfills_needed:
            if run_backfill(script, description):
                backfills_run += 1
    else:
        log("All systems healthy")

    # Summary
    if backfills_run > 0:
        log(f"Backfills completed: {backfills_run}/{len(backfills_needed)}")
        sys.exit(1)  # Exit 1 = action taken
    elif backfills_needed:
        log(f"Backfills failed: {len(backfills_needed)}", "ERROR")
        sys.exit(2)
    else:
        sys.exit(0)  # Exit 0 = healthy


if __name__ == "__main__":
    main()
