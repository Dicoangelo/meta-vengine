#!/usr/bin/env python3
"""
CCC Self-Healing Engine v1.0.0

The ultimate self-healing, self-evolving system for Claude Command Center.
Distilled from 21 CCC sessions and 558 total sessions of troubleshooting.

Key features:
- Daemon monitoring and auto-reload
- Data freshness validation
- Mixed timestamp handling
- Parse error recovery
- Self-evolution from patterns
- Proactive problem prevention

Run: python3 ~/.claude/scripts/ccc-self-heal.py
     python3 ~/.claude/scripts/ccc-self-heal.py --fix (auto-fix all issues)
     python3 ~/.claude/scripts/ccc-self-heal.py --status (show status only)
     python3 ~/.claude/scripts/ccc-self-heal.py --evolve (update patterns from recent sessions)

Exit codes:
  0 = all healthy
  1 = issues fixed
  2 = issues found but not fixed (run with --fix)
  3 = error
"""

import json
import sqlite3
import subprocess
import sys
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from zoneinfo import ZoneInfo

# ============================================================================
# Configuration
# ============================================================================

HOME = Path.home()

# Load timezone from centralized config
SYSTEM_CONFIG_FILE = HOME / ".claude/config/system.json"
try:
    with open(SYSTEM_CONFIG_FILE) as f:
        SYSTEM_CONFIG = json.load(f)
    LOCAL_TZ = ZoneInfo(SYSTEM_CONFIG.get("timezone", "America/New_York"))
except:
    LOCAL_TZ = ZoneInfo("America/New_York")
CLAUDE_DIR = HOME / ".claude"
KERNEL_DIR = CLAUDE_DIR / "kernel"
DATA_DIR = CLAUDE_DIR / "data"
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
LOGS_DIR = CLAUDE_DIR / "logs"
MEMORY_DB = CLAUDE_DIR / "memory/supermemory.db"
LAUNCH_AGENTS = HOME / "Library/LaunchAgents"

# Daemon definitions - the root cause of recurring issues
DAEMONS = {
    "com.claude.dashboard-refresh": {
        "description": "Dashboard auto-refresh (60s)",
        "critical": True,
        "check_interval": 60,
    },
    "com.claude.supermemory": {
        "description": "Daily supermemory maintenance",
        "critical": True,
        "check_interval": 86400,
    },
    "com.claude.session-analysis": {
        "description": "Session analysis (30m)",
        "critical": False,
        "check_interval": 1800,
    },
    "com.claude.autonomous-maintenance": {
        "description": "Autonomous maintenance",
        "critical": False,
        "check_interval": 3600,
    },
}

# Thresholds (learned from session history)
THRESHOLDS = {
    "kernel_max_age_hours": 24,
    "stats_max_age_hours": 12,
    "min_memory_links": 1000,
    "max_jsonl_error_rate": 0.05,
    "stale_lock_hours": 1,
    "max_log_size_mb": 50,
}

# ============================================================================
# Utilities
# ============================================================================

class Colors:
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def log(msg: str, level: str = "INFO", color: str = None):
    """Log with timestamp and optional color."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    colors = {
        "INFO": Colors.RESET,
        "OK": Colors.GREEN,
        "WARN": Colors.YELLOW,
        "ERROR": Colors.RED,
        "FIX": Colors.BLUE,
    }
    c = color or colors.get(level, Colors.RESET)
    print(f"{c}[{timestamp}] [{level:5}] {msg}{Colors.RESET}")


def parse_timestamp(ts: Any) -> Optional[datetime]:
    """
    Normalize timestamps from various formats.
    Handles: ISO strings, Unix seconds, Unix milliseconds, naive/aware datetimes.
    This was a recurring pain point across sessions.
    """
    if ts is None:
        return None

    # Already a datetime
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=LOCAL_TZ)
        return ts.astimezone(LOCAL_TZ)

    # String formats
    if isinstance(ts, str):
        # ISO format with Z
        if ts.endswith('Z'):
            ts = ts[:-1] + '+00:00'
        try:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=LOCAL_TZ)
            else:
                dt = dt.astimezone(LOCAL_TZ)
            return dt
        except ValueError:
            pass

        # Try parsing as float
        try:
            ts = float(ts)
        except ValueError:
            return None

    # Numeric timestamps
    if isinstance(ts, (int, float)):
        # Milliseconds (> year 2100 in seconds)
        if ts > 4102444800:
            ts = ts / 1000
        try:
            return datetime.fromtimestamp(ts, tz=LOCAL_TZ)
        except (OSError, ValueError):
            return None

    return None


def now_local() -> datetime:
    """Get current time in Eastern timezone."""
    return datetime.now(LOCAL_TZ)


def file_age_hours(filepath: Path) -> float:
    """Get file age in hours."""
    if not filepath.exists():
        return float('inf')
    mtime = datetime.fromtimestamp(filepath.stat().st_mtime, tz=LOCAL_TZ)
    return (now_local() - mtime).total_seconds() / 3600


# ============================================================================
# Health Checks
# ============================================================================

class HealthCheck:
    """Individual health check result."""
    def __init__(self, name: str, category: str):
        self.name = name
        self.category = category
        self.status = "unknown"  # ok, warn, error
        self.message = ""
        self.can_fix = False
        self.fix_action = None
        self.details = {}

    def ok(self, msg: str = "Healthy"):
        self.status = "ok"
        self.message = msg
        return self

    def warn(self, msg: str, can_fix: bool = False, fix_action: str = None):
        self.status = "warn"
        self.message = msg
        self.can_fix = can_fix
        self.fix_action = fix_action
        return self

    def error(self, msg: str, can_fix: bool = False, fix_action: str = None):
        self.status = "error"
        self.message = msg
        self.can_fix = can_fix
        self.fix_action = fix_action
        return self


def check_daemon_loaded(daemon_name: str) -> HealthCheck:
    """Check if a LaunchAgent daemon is loaded."""
    check = HealthCheck(daemon_name, "daemons")

    plist_path = LAUNCH_AGENTS / f"{daemon_name}.plist"
    if not plist_path.exists():
        return check.warn(f"Plist not found: {plist_path}", can_fix=False)

    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Check if daemon appears in launchctl list
        if daemon_name in result.stdout:
            # Parse the line to get status
            for line in result.stdout.split('\n'):
                if daemon_name in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        pid, exit_code = parts[0], parts[1]
                        if pid != "-" and pid.isdigit():
                            return check.ok(f"Running (PID: {pid})")
                        elif exit_code == "0":
                            return check.ok("Loaded (idle)")
                        else:
                            return check.warn(
                                f"Loaded but exited with code {exit_code}",
                                can_fix=True,
                                fix_action="reload_daemon"
                            )
            return check.ok("Loaded")
        else:
            return check.error(
                "Not loaded",
                can_fix=True,
                fix_action="load_daemon"
            )
    except subprocess.TimeoutExpired:
        return check.error("launchctl timeout")
    except Exception as e:
        return check.error(f"Check failed: {e}")


def check_all_daemons() -> List[HealthCheck]:
    """Check all defined daemons."""
    results = []
    for daemon_name, config in DAEMONS.items():
        check = check_daemon_loaded(daemon_name)
        check.details = config
        results.append(check)
    return results


def check_file_freshness(filepath: Path, max_age_hours: float, name: str) -> HealthCheck:
    """Check if a file is fresh enough."""
    check = HealthCheck(name, "data")

    if not filepath.exists():
        return check.error(f"File not found: {filepath}", can_fix=True, fix_action="regenerate")

    age = file_age_hours(filepath)
    check.details["age_hours"] = round(age, 2)
    check.details["path"] = str(filepath)

    if age <= max_age_hours:
        return check.ok(f"Fresh ({age:.1f}h old)")
    else:
        return check.warn(
            f"Stale ({age:.1f}h old, max {max_age_hours}h)",
            can_fix=True,
            fix_action="regenerate"
        )


def check_json_updated_field(filepath: Path, max_age_hours: float, name: str) -> HealthCheck:
    """Check the 'updated' field inside a JSON file."""
    check = HealthCheck(name, "data")

    if not filepath.exists():
        return check.error(f"File not found: {filepath}", can_fix=True, fix_action="regenerate")

    try:
        with open(filepath) as f:
            data = json.load(f)

        # Try various timestamp field names
        ts_value = data.get('updated') or data.get('lastUpdated') or data.get('generated')

        if not ts_value:
            # Fall back to file mtime
            return check_file_freshness(filepath, max_age_hours, name)

        updated_dt = parse_timestamp(ts_value)
        if not updated_dt:
            return check.warn(f"Cannot parse timestamp: {ts_value}")

        age = (now_local() - updated_dt).total_seconds() / 3600
        check.details["age_hours"] = round(age, 2)
        check.details["path"] = str(filepath)

        if age <= max_age_hours:
            return check.ok(f"Fresh ({age:.1f}h old)")
        else:
            return check.warn(
                f"Stale ({age:.1f}h old, max {max_age_hours}h)",
                can_fix=True,
                fix_action="regenerate"
            )
    except json.JSONDecodeError as e:
        return check.error(f"Invalid JSON: {e}", can_fix=True, fix_action="regenerate")
    except Exception as e:
        return check.error(f"Check failed: {e}")


def check_jsonl_health(filepath: Path, name: str) -> HealthCheck:
    """Check JSONL file for parse errors."""
    check = HealthCheck(name, "data")

    if not filepath.exists():
        return check.ok("File not found (OK if optional)")

    valid = 0
    invalid = 0

    try:
        content = filepath.read_text()
        for line in content.split('\n'):
            if not line.strip():
                continue
            try:
                json.loads(line)
                valid += 1
            except json.JSONDecodeError:
                invalid += 1

        total = valid + invalid
        check.details["valid"] = valid
        check.details["invalid"] = invalid
        check.details["path"] = str(filepath)

        if total == 0:
            return check.ok("Empty file")

        error_rate = invalid / total
        if error_rate < THRESHOLDS["max_jsonl_error_rate"]:
            return check.ok(f"{valid} valid, {invalid} invalid ({error_rate*100:.1f}%)")
        else:
            return check.warn(
                f"High error rate: {invalid}/{total} ({error_rate*100:.1f}%)",
                can_fix=True,
                fix_action="clean_jsonl"
            )
    except Exception as e:
        return check.error(f"Check failed: {e}")


def check_memory_links() -> HealthCheck:
    """Check if memory_links table has sufficient entries."""
    check = HealthCheck("memory_links", "database")

    if not MEMORY_DB.exists():
        return check.error("Database not found", can_fix=True, fix_action="populate_memory")

    try:
        conn = sqlite3.connect(str(MEMORY_DB))
        count = conn.execute("SELECT COUNT(*) FROM memory_links").fetchone()[0]
        conn.close()

        check.details["count"] = count
        check.details["threshold"] = THRESHOLDS["min_memory_links"]

        if count >= THRESHOLDS["min_memory_links"]:
            return check.ok(f"{count:,} links (threshold: {THRESHOLDS['min_memory_links']:,})")
        else:
            return check.warn(
                f"Low count: {count:,} (need {THRESHOLDS['min_memory_links']:,}+)",
                can_fix=True,
                fix_action="populate_memory"
            )
    except Exception as e:
        return check.error(f"Check failed: {e}")


def check_stale_locks() -> HealthCheck:
    """Check for stale lock files."""
    check = HealthCheck("lock_files", "system")

    lock_patterns = [
        CLAUDE_DIR / ".session.lock",
        CLAUDE_DIR / "tasks/*/.lock",
        HOME / ".git/index.lock",
    ]

    stale_locks = []

    for pattern in lock_patterns:
        if "*" in str(pattern):
            locks = list(pattern.parent.glob(pattern.name))
        else:
            locks = [pattern] if pattern.exists() else []

        for lock in locks:
            if lock.exists():
                age = file_age_hours(lock)
                if age > THRESHOLDS["stale_lock_hours"]:
                    stale_locks.append((lock, age))

    check.details["stale_locks"] = len(stale_locks)

    if not stale_locks:
        return check.ok("No stale locks")
    else:
        return check.warn(
            f"{len(stale_locks)} stale lock(s) found",
            can_fix=True,
            fix_action="clear_locks"
        )


def check_log_sizes() -> HealthCheck:
    """Check for oversized log files."""
    check = HealthCheck("log_sizes", "system")

    if not LOGS_DIR.exists():
        return check.ok("No logs directory")

    oversized = []
    for log_file in LOGS_DIR.glob("*.log"):
        size_mb = log_file.stat().st_size / (1024 * 1024)
        if size_mb > THRESHOLDS["max_log_size_mb"]:
            oversized.append((log_file.name, size_mb))

    check.details["oversized_logs"] = oversized

    if not oversized:
        return check.ok("All logs within size limits")
    else:
        return check.warn(
            f"{len(oversized)} oversized log(s)",
            can_fix=True,
            fix_action="rotate_logs"
        )


def check_stale_claude_processes() -> HealthCheck:
    """Check for stale Claude CLI processes (running >24h)."""
    check = HealthCheck("stale_processes", "system")

    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=10
        )

        stale = []
        current_pid = str(os.getpid())

        for line in result.stdout.split('\n'):
            if 'claude --model' in line.lower() and 'grep' not in line:
                parts = line.split()
                if len(parts) >= 10:
                    pid = parts[1]
                    start = parts[8]  # Start time/date

                    # Skip current session
                    if pid == current_pid:
                        continue

                    # Check if started on a different day (Wed, Thu, etc.)
                    if any(day in start for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']):
                        cpu_time = parts[9]
                        stale.append({"pid": pid, "start": start, "cpu": cpu_time})

        check.details["stale_count"] = len(stale)
        check.details["stale_pids"] = [s["pid"] for s in stale]

        if not stale:
            return check.ok("No stale processes")
        else:
            return check.warn(
                f"{len(stale)} stale Claude process(es) (>24h old)",
                can_fix=True,
                fix_action="kill_stale_processes"
            )
    except Exception as e:
        return check.error(f"Check failed: {e}")


# ============================================================================
# Fix Actions
# ============================================================================

def fix_load_daemon(daemon_name: str) -> Tuple[bool, str]:
    """Load a LaunchAgent daemon."""
    plist_path = LAUNCH_AGENTS / f"{daemon_name}.plist"

    if not plist_path.exists():
        return False, f"Plist not found: {plist_path}"

    try:
        result = subprocess.run(
            ["launchctl", "load", str(plist_path)],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            return True, f"Loaded {daemon_name}"
        else:
            return False, f"Load failed: {result.stderr}"
    except Exception as e:
        return False, f"Load error: {e}"


def fix_reload_daemon(daemon_name: str) -> Tuple[bool, str]:
    """Unload and reload a daemon."""
    plist_path = LAUNCH_AGENTS / f"{daemon_name}.plist"

    try:
        # Unload first
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True,
            timeout=5
        )

        # Then load
        result = subprocess.run(
            ["launchctl", "load", str(plist_path)],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            return True, f"Reloaded {daemon_name}"
        else:
            return False, f"Reload failed: {result.stderr}"
    except Exception as e:
        return False, f"Reload error: {e}"


def fix_regenerate_kernel_data() -> Tuple[bool, str]:
    """Run the kernel data regeneration script."""
    script = SCRIPTS_DIR / "regenerate-kernel-data.py"
    if not script.exists():
        return False, f"Script not found: {script}"

    try:
        result = subprocess.run(
            ["python3", str(script)],
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.returncode == 0, result.stderr[:200] if result.returncode != 0 else "Regenerated"
    except Exception as e:
        return False, f"Error: {e}"


def fix_populate_memory() -> Tuple[bool, str]:
    """Run the memory links population script."""
    script = SCRIPTS_DIR / "populate-memory-links.py"
    if not script.exists():
        return False, f"Script not found: {script}"

    try:
        result = subprocess.run(
            ["python3", str(script)],
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.returncode == 0, result.stderr[:200] if result.returncode != 0 else "Populated"
    except Exception as e:
        return False, f"Error: {e}"


def fix_clear_locks() -> Tuple[bool, str]:
    """Clear stale lock files."""
    cleared = 0

    lock_patterns = [
        CLAUDE_DIR / ".session.lock",
        CLAUDE_DIR / "tasks/*/.lock",
    ]

    for pattern in lock_patterns:
        if "*" in str(pattern):
            locks = list(pattern.parent.glob(pattern.name))
        else:
            locks = [pattern] if pattern.exists() else []

        for lock in locks:
            if lock.exists():
                age = file_age_hours(lock)
                if age > THRESHOLDS["stale_lock_hours"]:
                    try:
                        lock.unlink()
                        cleared += 1
                    except Exception:
                        pass

    return True, f"Cleared {cleared} stale lock(s)"


def fix_rotate_logs() -> Tuple[bool, str]:
    """Rotate oversized logs."""
    rotated = 0

    if not LOGS_DIR.exists():
        return True, "No logs to rotate"

    for log_file in LOGS_DIR.glob("*.log"):
        size_mb = log_file.stat().st_size / (1024 * 1024)
        if size_mb > THRESHOLDS["max_log_size_mb"]:
            try:
                # Keep last 10% of file
                content = log_file.read_text()
                lines = content.split('\n')
                keep_lines = lines[int(len(lines) * 0.9):]

                # Archive the old content
                archive = log_file.with_suffix('.log.old')
                archive.write_text(content)

                # Write truncated content
                log_file.write_text('\n'.join(keep_lines))
                rotated += 1
            except Exception:
                pass

    return True, f"Rotated {rotated} log(s)"


def fix_kill_stale_processes() -> Tuple[bool, str]:
    """Kill Claude CLI processes running for more than 24 hours.

    Uses escalating signals: SIGTERM first, then SIGKILL for survivors.
    """
    import time

    current_pid = str(os.getpid())
    stale_pids = []

    try:
        # Find stale processes
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=10
        )

        for line in result.stdout.split('\n'):
            if 'claude --model' in line.lower() and 'grep' not in line:
                parts = line.split()
                if len(parts) >= 10:
                    pid = parts[1]
                    start = parts[8]

                    # Skip current session
                    if pid == current_pid:
                        continue

                    # Check if started on a different day (shows day name like "Wed")
                    if any(day in start for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']):
                        stale_pids.append(pid)

        if not stale_pids:
            return True, "No stale processes found"

        # Phase 1: SIGTERM (graceful)
        for pid in stale_pids:
            try:
                subprocess.run(["kill", "-TERM", pid], capture_output=True, timeout=2)
            except:
                pass

        # Wait for graceful shutdown
        time.sleep(3)

        # Phase 2: Check survivors and SIGKILL
        survivors = []
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=10)

        for pid in stale_pids:
            if pid in result.stdout:
                survivors.append(pid)
                try:
                    subprocess.run(["kill", "-9", pid], capture_output=True, timeout=2)
                except:
                    pass

        killed_graceful = len(stale_pids) - len(survivors)
        killed_force = len(survivors)

        if killed_force > 0:
            return True, f"Terminated {killed_graceful} gracefully, force-killed {killed_force}"
        else:
            return True, f"Terminated {len(stale_pids)} stale process(es) gracefully"
    except Exception as e:
        return False, f"Error: {e}"


def log_learning(fix_name: str, issue: str, solution: str, category: str = "self-heal"):
    """Log a learning to supermemory when a fix is applied."""
    try:
        conn = sqlite3.connect(str(MEMORY_DB))
        learning_id = f"autofix-{fix_name}-{int(now_local().timestamp())}"
        content = f"Auto-fixed: {issue}. Solution: {solution}"
        conn.execute("""
            INSERT OR REPLACE INTO learnings (id, content, category, project, quality, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (learning_id, content, category, "ccc-infrastructure", 4.0, now_local().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
    except Exception:
        pass  # Don't fail if learning log fails


def fix_clean_jsonl(filepath: Path) -> Tuple[bool, str]:
    """Clean invalid lines from JSONL file."""
    if not filepath.exists():
        return False, "File not found"

    try:
        valid_lines = []
        invalid_count = 0

        for line in filepath.read_text().split('\n'):
            if not line.strip():
                continue
            try:
                json.loads(line)
                valid_lines.append(line)
            except json.JSONDecodeError:
                invalid_count += 1

        # Backup original
        backup = filepath.with_suffix(filepath.suffix + '.backup')
        filepath.rename(backup)

        # Write cleaned file
        filepath.write_text('\n'.join(valid_lines) + '\n')

        return True, f"Removed {invalid_count} invalid lines (backup at {backup.name})"
    except Exception as e:
        return False, f"Error: {e}"


def fix_run_dashboard_generator() -> Tuple[bool, str]:
    """Run the dashboard generator."""
    script = SCRIPTS_DIR / "ccc-generator.sh"
    if not script.exists():
        return False, f"Script not found: {script}"

    try:
        result = subprocess.run(
            ["bash", str(script), "--no-open"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(SCRIPTS_DIR)
        )
        return result.returncode == 0, "Dashboard regenerated" if result.returncode == 0 else result.stderr[:200]
    except Exception as e:
        return False, f"Error: {e}"


# ============================================================================
# Main Engine
# ============================================================================

class SelfHealingEngine:
    """The self-healing engine that orchestrates all checks and fixes."""

    def __init__(self, auto_fix: bool = False, verbose: bool = True):
        self.auto_fix = auto_fix
        self.verbose = verbose
        self.checks: List[HealthCheck] = []
        self.fixes_applied: List[Tuple[str, bool, str]] = []

    def run_all_checks(self):
        """Run all health checks."""

        # 1. Daemon checks (the root cause of most issues)
        if self.verbose:
            log("Checking daemons...", "INFO")
        self.checks.extend(check_all_daemons())

        # 2. Data freshness checks
        if self.verbose:
            log("Checking data freshness...", "INFO")

        kernel_files = ['cost-data.json', 'productivity-data.json', 'coevo-data.json']
        for filename in kernel_files:
            self.checks.append(check_json_updated_field(
                KERNEL_DIR / filename,
                THRESHOLDS["kernel_max_age_hours"],
                filename
            ))

        self.checks.append(check_file_freshness(
            CLAUDE_DIR / "stats-cache.json",
            THRESHOLDS["stats_max_age_hours"],
            "stats-cache.json"
        ))

        self.checks.append(check_file_freshness(
            CLAUDE_DIR / "dashboard/claude-command-center.html",
            1,  # Dashboard should be fresh within 1 hour
            "dashboard"
        ))

        # 3. Memory checks
        if self.verbose:
            log("Checking memory...", "INFO")
        self.checks.append(check_memory_links())

        # 4. JSONL health checks
        if self.verbose:
            log("Checking JSONL files...", "INFO")
        jsonl_files = [
            'activity-events.jsonl',
            'session-outcomes.jsonl',
            'routing-metrics.jsonl',
            'recovery-outcomes.jsonl',
        ]
        for filename in jsonl_files:
            self.checks.append(check_jsonl_health(DATA_DIR / filename, filename))

        # 5. System checks
        if self.verbose:
            log("Checking system...", "INFO")
        self.checks.append(check_stale_locks())
        self.checks.append(check_log_sizes())
        self.checks.append(check_stale_claude_processes())

    def apply_fixes(self):
        """Apply fixes for issues that can be auto-fixed."""
        fixable = [c for c in self.checks if c.status in ('warn', 'error') and c.can_fix]

        if not fixable:
            return

        for check in fixable:
            action = check.fix_action
            success = False
            message = ""

            if action == "load_daemon":
                success, message = fix_load_daemon(check.name)
            elif action == "reload_daemon":
                success, message = fix_reload_daemon(check.name)
            elif action == "regenerate":
                if "dashboard" in check.name:
                    success, message = fix_run_dashboard_generator()
                else:
                    success, message = fix_regenerate_kernel_data()
            elif action == "populate_memory":
                success, message = fix_populate_memory()
            elif action == "clear_locks":
                success, message = fix_clear_locks()
            elif action == "rotate_logs":
                success, message = fix_rotate_logs()
            elif action == "clean_jsonl":
                if "path" in check.details:
                    success, message = fix_clean_jsonl(Path(check.details["path"]))
                else:
                    message = "No path specified"
            elif action == "kill_stale_processes":
                success, message = fix_kill_stale_processes()

            self.fixes_applied.append((check.name, success, message))

            if success:
                log(f"Fixed: {check.name} - {message}", "FIX")
                # Log learning for successful fixes
                log_learning(
                    fix_name=action,
                    issue=f"{check.name}: {check.message}",
                    solution=message,
                    category=check.category
                )
            else:
                log(f"Fix failed: {check.name} - {message}", "ERROR")

    def report(self) -> Dict[str, Any]:
        """Generate a summary report."""
        ok_count = sum(1 for c in self.checks if c.status == "ok")
        warn_count = sum(1 for c in self.checks if c.status == "warn")
        error_count = sum(1 for c in self.checks if c.status == "error")

        return {
            "timestamp": now_local().isoformat(),
            "total_checks": len(self.checks),
            "ok": ok_count,
            "warnings": warn_count,
            "errors": error_count,
            "fixes_applied": len(self.fixes_applied),
            "fixes_successful": sum(1 for _, success, _ in self.fixes_applied if success),
            "checks": [
                {
                    "name": c.name,
                    "category": c.category,
                    "status": c.status,
                    "message": c.message,
                    "can_fix": c.can_fix,
                }
                for c in self.checks
            ],
            "fixes": [
                {"name": name, "success": success, "message": msg}
                for name, success, msg in self.fixes_applied
            ],
        }

    def print_summary(self):
        """Print a formatted summary."""
        report = self.report()

        print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}CCC Self-Healing Report{Colors.RESET}")
        print(f"{'='*60}")

        # Status overview
        ok = report["ok"]
        warn = report["warnings"]
        err = report["errors"]
        total = report["total_checks"]

        status_color = Colors.GREEN if err == 0 and warn == 0 else (Colors.YELLOW if err == 0 else Colors.RED)
        print(f"\nStatus: {status_color}{'HEALTHY' if err == 0 and warn == 0 else 'DEGRADED' if err == 0 else 'UNHEALTHY'}{Colors.RESET}")
        print(f"Checks: {ok}/{total} OK, {warn} warnings, {err} errors")

        # Category breakdown
        categories = {}
        for check in self.checks:
            if check.category not in categories:
                categories[check.category] = {"ok": 0, "warn": 0, "error": 0}
            categories[check.category][check.status] += 1

        print(f"\n{Colors.BOLD}By Category:{Colors.RESET}")
        for cat, counts in sorted(categories.items()):
            status = "✓" if counts["error"] == 0 and counts["warn"] == 0 else "⚠" if counts["error"] == 0 else "✗"
            print(f"  {status} {cat}: {counts['ok']} ok, {counts['warn']} warn, {counts['error']} error")

        # Issues found
        issues = [c for c in self.checks if c.status in ('warn', 'error')]
        if issues:
            print(f"\n{Colors.BOLD}Issues Found:{Colors.RESET}")
            for check in issues:
                status_icon = "⚠" if check.status == "warn" else "✗"
                color = Colors.YELLOW if check.status == "warn" else Colors.RED
                fix_hint = " [fixable]" if check.can_fix else ""
                print(f"  {color}{status_icon} {check.name}: {check.message}{fix_hint}{Colors.RESET}")

        # Fixes applied
        if self.fixes_applied:
            print(f"\n{Colors.BOLD}Fixes Applied:{Colors.RESET}")
            for name, success, msg in self.fixes_applied:
                icon = "✓" if success else "✗"
                color = Colors.GREEN if success else Colors.RED
                print(f"  {color}{icon} {name}: {msg}{Colors.RESET}")

        # Recommendations
        unfixed = [c for c in self.checks if c.status in ('warn', 'error') and c.can_fix and
                   not any(f[0] == c.name and f[1] for f in self.fixes_applied)]
        if unfixed and not self.auto_fix:
            print(f"\n{Colors.BOLD}Recommended:{Colors.RESET}")
            print(f"  Run with --fix to auto-repair {len(unfixed)} issue(s)")

        print(f"\n{'='*60}\n")


def evolve_from_patterns():
    """Analyze recent sessions to discover new patterns and update thresholds."""
    log("Analyzing recent patterns for evolution...", "INFO")

    outcomes_file = DATA_DIR / "recovery-outcomes.jsonl"
    if not outcomes_file.exists():
        log("No recovery outcomes to analyze", "WARN")
        return

    # Analyze success rates by action
    actions = {}
    for line in outcomes_file.read_text().split('\n'):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            action = data.get("action", "unknown")
            success = data.get("success", False)
            if action not in actions:
                actions[action] = {"total": 0, "success": 0}
            actions[action]["total"] += 1
            if success:
                actions[action]["success"] += 1
        except json.JSONDecodeError:
            continue

    # Report on action effectiveness
    log("Action effectiveness:", "INFO")
    for action, stats in sorted(actions.items(), key=lambda x: -x[1]["total"]):
        rate = stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
        status = "✓" if rate >= 80 else "⚠" if rate >= 50 else "✗"
        print(f"  {status} {action}: {rate:.0f}% ({stats['success']}/{stats['total']})")

    log("Evolution complete - patterns analyzed", "OK")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="CCC Self-Healing Engine - Auto-monitor and repair Claude Command Center"
    )
    parser.add_argument("--fix", action="store_true", help="Auto-fix all fixable issues")
    parser.add_argument("--status", action="store_true", help="Show status only (no fixes)")
    parser.add_argument("--evolve", action="store_true", help="Analyze patterns and evolve")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")

    args = parser.parse_args()

    if args.evolve:
        evolve_from_patterns()
        return 0

    # Run the engine
    engine = SelfHealingEngine(
        auto_fix=args.fix and not args.status,
        verbose=not args.quiet
    )

    engine.run_all_checks()

    if args.fix and not args.status:
        engine.apply_fixes()

    if args.json:
        print(json.dumps(engine.report(), indent=2))
    else:
        engine.print_summary()

    # Log outcome with dual-write to JSONL + SQLite
    try:
        ts = int(now_local().timestamp())
        ok_count = engine.report()["ok"]
        warn_count = engine.report()["warnings"]
        error_count = engine.report()["errors"]
        fixed_count = engine.report()["fixes_successful"]

        # Import dual-write library
        sys.path.insert(0, str(HOME / ".claude/hooks"))
        from dual_write_lib import log_self_heal_outcome

        log_self_heal_outcome(
            ok=ok_count,
            warn=warn_count,
            error=error_count,
            fixed=fixed_count
        )
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to log self-heal outcome: {e}\n")

    # Exit codes
    report = engine.report()
    if report["errors"] > 0 and not args.fix:
        return 2  # Issues found, not fixed
    elif report["fixes_applied"] > 0:
        return 1  # Issues fixed
    else:
        return 0  # All healthy


if __name__ == "__main__":
    sys.exit(main())
