#!/usr/bin/env python3
"""
CCC Watchdog - Always-On Guardian

Runs every 60 seconds. If ANY daemon is down, it reloads it immediately.
This is the meta-daemon that keeps all other daemons alive.

The watchdog itself is protected by:
1. RunAtLoad - starts on login
2. KeepAlive - launchd restarts it if it dies
3. Login hook - backup reload on every login
4. Wake hook - reload after sleep

This creates a self-healing loop that can never fully die.
"""

import subprocess
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/New_York")
HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
LAUNCH_AGENTS = HOME / "Library/LaunchAgents"
LOG_FILE = CLAUDE_DIR / "logs/watchdog.log"

# All daemons that must stay alive (watchdog monitors all except itself)
CRITICAL_DAEMONS = [
    "com.claude.dashboard-refresh",
    "com.claude.supermemory",
    "com.claude.session-analysis",
    "com.claude.autonomous-maintenance",
    "com.claude.self-heal",
    "com.claude.bootstrap",
    "com.claude.wake-hook",
    "com.claude.autonomous-brain",
    "com.claude.capability-sync",
]

def log(msg: str):
    """Append to watchdog log."""
    timestamp = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass

def get_loaded_daemons() -> set:
    """Get set of all loaded daemons (single launchctl call)."""
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return set(result.stdout)
    except:
        return set()

def is_daemon_loaded(name: str, launchctl_output: str = None) -> bool:
    """Check if daemon is loaded. Pass launchctl_output to avoid repeated calls."""
    if launchctl_output is not None:
        return name in launchctl_output
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return name in result.stdout
    except:
        return False

def load_daemon(name: str) -> bool:
    """Load a daemon."""
    plist = LAUNCH_AGENTS / f"{name}.plist"
    if not plist.exists():
        log(f"SKIP {name} - plist not found")
        return False

    try:
        # Unload first (ignore errors)
        subprocess.run(
            ["launchctl", "unload", str(plist)],
            capture_output=True,
            timeout=5
        )
        # Then load
        result = subprocess.run(
            ["launchctl", "load", str(plist)],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            log(f"LOADED {name}")
            return True
        else:
            log(f"FAILED {name}: {result.stderr}")
            return False
    except Exception as e:
        log(f"ERROR {name}: {e}")
        return False

def check_and_heal():
    """Check all daemons, reload any that are down."""
    # Single launchctl call for efficiency and consistency
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )
        launchctl_output = result.stdout
    except:
        launchctl_output = ""

    healed = 0
    healed_daemons = set()  # Track to avoid duplicates

    for daemon in CRITICAL_DAEMONS:
        if daemon not in launchctl_output and daemon not in healed_daemons:
            log(f"DOWN: {daemon}")
            if load_daemon(daemon):
                healed += 1
                healed_daemons.add(daemon)

    return healed

def ensure_data_fresh():
    """Quick check that critical data files exist and are being updated."""
    critical_files = [
        CLAUDE_DIR / "dashboard/claude-command-center.html",
        CLAUDE_DIR / "kernel/session-state.json",
    ]

    for f in critical_files:
        if not f.exists():
            log(f"MISSING: {f.name}")
            # Trigger dashboard regeneration
            try:
                subprocess.run(
                    ["bash", str(CLAUDE_DIR / "scripts/ccc-generator.sh"), "--no-open"],
                    capture_output=True,
                    timeout=60,
                    cwd=str(CLAUDE_DIR / "scripts")
                )
                log("REGENERATED dashboard")
            except:
                pass
            break

def write_heartbeat():
    """Write heartbeat file so other processes know watchdog is alive."""
    heartbeat = CLAUDE_DIR / ".watchdog-heartbeat"
    try:
        heartbeat.write_text(datetime.now(LOCAL_TZ).isoformat())
    except:
        pass

def main():
    """Main watchdog loop - called every 60s by launchd."""
    healed = check_and_heal()
    ensure_data_fresh()
    write_heartbeat()

    if healed > 0:
        log(f"HEALED {healed} daemon(s)")
        # Send notification
        try:
            subprocess.run([
                "osascript", "-e",
                f'display notification "Reloaded {healed} daemon(s)" with title "CCC Watchdog" subtitle "Infrastructure restored"'
            ], capture_output=True, timeout=2)
        except:
            pass

    return 0

if __name__ == "__main__":
    sys.exit(main())
