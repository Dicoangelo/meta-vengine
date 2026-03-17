#!/usr/bin/env python3
"""daemon-health.py — Health monitor for meta-vengine learning daemons.

Checks freshness of daemon outputs and scans logs for errors.
Exit 0 if all healthy/no_data, exit 1 if any stale/error.

Usage:
    python3 kernel/daemon-health.py          # human-readable + JSON
    python3 kernel/daemon-health.py --json   # JSON only (no stderr)
"""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DAEMONS = [
    {
        "name": "weight-snapshot",
        "data_dir": PROJECT_ROOT / "data" / "weight-snapshots",
        "max_age_hours": 25,
        "log_file": PROJECT_ROOT / "data" / "daemon-logs" / "weight-snapshot.log",
    },
    {
        "name": "lrf-update",
        "data_dir": PROJECT_ROOT / "data" / "lrf-reports",
        "max_age_hours": 8 * 24,  # 8 days
        "log_file": PROJECT_ROOT / "data" / "daemon-logs" / "lrf-update.log",
    },
    {
        "name": "bo-monthly",
        "data_dir": PROJECT_ROOT / "data" / "bo-reports",
        "max_age_hours": 32 * 24,  # 32 days
        "log_file": PROJECT_ROOT / "data" / "daemon-logs" / "bo-monthly.log",
    },
]

ERROR_PATTERNS = [
    re.compile(r"Traceback", re.IGNORECASE),
    re.compile(r"Error:", re.IGNORECASE),
    re.compile(r"\bERROR\b"),
    re.compile(r"exit\s+code\s+[1-9]", re.IGNORECASE),
    re.compile(r"\bOOM\b"),
    re.compile(r"MemoryError"),
    re.compile(r"\bkilled\b", re.IGNORECASE),
    re.compile(r"SIGKILL"),
]

HEALTH_LOG = PROJECT_ROOT / "data" / "daemon-health.jsonl"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def newest_file_mtime(directory: Path):
    """Return (mtime_datetime_utc, path) of the most recently modified file,
    or (None, None) if directory missing or empty."""
    if not directory.is_dir():
        return None, None
    newest_time = None
    newest_path = None
    for entry in directory.iterdir():
        if entry.is_file():
            mt = entry.stat().st_mtime
            if newest_time is None or mt > newest_time:
                newest_time = mt
                newest_path = entry
    if newest_time is None:
        return None, None
    return datetime.fromtimestamp(newest_time, tz=timezone.utc), newest_path


def scan_log_errors(log_path: Path, max_errors: int = 3):
    """Return up to *max_errors* most recent error lines from a log file."""
    if not log_path.is_file():
        return []
    errors = []
    try:
        with open(log_path, "r", errors="replace") as fh:
            for line in fh:
                stripped = line.rstrip("\n")
                if any(pat.search(stripped) for pat in ERROR_PATTERNS):
                    errors.append(stripped)
    except OSError:
        return []
    # Return last N errors (most recent)
    return errors[-max_errors:]


def compute_next_expected(last_run, max_age_hours):
    """Compute next expected run timestamp from last_run + max_age."""
    if last_run is None:
        return None
    return last_run + timedelta(hours=max_age_hours)


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------

def check_daemon(cfg: dict) -> dict:
    """Run freshness + error checks for one daemon. Returns result dict."""
    name = cfg["name"]
    data_dir = cfg["data_dir"]
    max_age = cfg["max_age_hours"]
    log_file = cfg["log_file"]

    now = datetime.now(timezone.utc)

    last_mtime, _ = newest_file_mtime(data_dir)
    errors_found = scan_log_errors(log_file)

    # Determine status
    if last_mtime is None:
        status = "no_data"
        age_hours = None
    else:
        age_hours = round((now - last_mtime).total_seconds() / 3600, 2)
        if age_hours > max_age:
            status = "stale"
        else:
            status = "healthy"

    # Errors override to "error" if present
    if errors_found:
        status = "error"

    next_expected = compute_next_expected(last_mtime, max_age)

    return {
        "daemon": name,
        "status": status,
        "last_run": last_mtime.isoformat() if last_mtime else None,
        "next_expected": next_expected.isoformat() if next_expected else None,
        "age_hours": age_hours,
        "max_age_hours": max_age,
        "details": _detail_string(status, age_hours, max_age, errors_found),
        "errors_found": errors_found,
    }


def _detail_string(status, age_hours, max_age, errors_found):
    if status == "no_data":
        return "No output files found — daemon may not have run yet"
    if status == "error":
        return f"Error patterns found in log ({len(errors_found)} recent)"
    if status == "stale":
        return f"Last output is {age_hours}h old, threshold is {max_age}h"
    return None


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_health_log(report: dict):
    """Append report to daemon-health.jsonl."""
    HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(HEALTH_LOG, "a") as fh:
        fh.write(json.dumps(report) + "\n")


def print_human(results: list):
    """Print a human-readable summary to stderr."""
    status_icons = {
        "healthy": "[OK]",
        "no_data": "[--]",
        "stale": "[!!]",
        "error": "[ER]",
    }
    for r in results:
        icon = status_icons.get(r["status"], "[??]")
        age_str = f"{r['age_hours']}h" if r["age_hours"] is not None else "n/a"
        sys.stderr.write(
            f"  {icon} {r['daemon']:<20s} status={r['status']:<8s} "
            f"age={age_str:<10s} max={r['max_age_hours']}h\n"
        )
        if r["details"]:
            sys.stderr.write(f"       {r['details']}\n")
        if r["errors_found"]:
            for err in r["errors_found"]:
                sys.stderr.write(f"       > {err}\n")


def main():
    json_only = "--json" in sys.argv

    now = datetime.now(timezone.utc)
    results = [check_daemon(d) for d in DAEMONS]

    report = {
        "timestamp": now.isoformat(),
        "daemons": results,
        "overall": "healthy",
    }

    # Determine overall status
    for r in results:
        if r["status"] in ("stale", "error"):
            report["overall"] = "unhealthy"
            break

    # Write health log
    write_health_log(report)

    # Output
    if not json_only:
        sys.stderr.write(f"Daemon Health Check — {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        print_human(results)
        sys.stderr.write(f"Overall: {report['overall']}\n")

    # JSON to stdout
    print(json.dumps(report, indent=2))

    # Exit code
    sys.exit(0 if report["overall"] == "healthy" else 1)


if __name__ == "__main__":
    main()
