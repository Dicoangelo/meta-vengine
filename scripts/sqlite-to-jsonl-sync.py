#!/usr/bin/env python3
"""
SQLite → JSONL Sync Bridge
Exports real-time hook data from SQLite to JSONL files for dashboard consumption.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

HOME = Path.home()
DB_PATH = HOME / ".agent-core" / "storage" / "antigravity.db"
DATA_DIR = HOME / ".claude" / "data"
STATE_FILE = DATA_DIR / "sqlite-sync-state.json"

# JSONL outputs
TOOL_USAGE_FILE = DATA_DIR / "tool-usage.jsonl"
SESSION_EVENTS_FILE = DATA_DIR / "session-events.jsonl"
ACTIVITY_EVENTS_FILE = DATA_DIR / "activity-events.jsonl"
COMMAND_USAGE_FILE = DATA_DIR / "command-usage.jsonl"
TOOL_SUCCESS_FILE = DATA_DIR / "tool-success.jsonl"

def load_sync_state():
    """Load last sync timestamp."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"last_sync_ts": 0}

def save_sync_state(ts):
    """Save last sync timestamp."""
    with open(STATE_FILE, "w") as f:
        json.dump({"last_sync_ts": ts, "last_sync_date": datetime.now().isoformat()}, f)

def sync_tool_events():
    """Export new tool events from SQLite to JSONL."""
    state = load_sync_state()
    last_ts = state.get("last_sync_ts", 0)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get new tool events since last sync
    cursor.execute("""
        SELECT ts, tool, file_path, session_pwd, metadata
        FROM tool_events
        WHERE ts > ?
        ORDER BY ts ASC
    """, (last_ts,))

    new_events = 0
    max_ts = last_ts

    tool_usage_entries = []
    session_events = []
    activity_events = []
    command_usage_entries = []
    tool_success_entries = []

    for row in cursor.fetchall():
        ts = row["ts"]
        tool = row["tool"]
        file_path = row["file_path"] or ""
        max_ts = max(max_ts, ts)

        # Parse metadata JSON
        metadata = {}
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except:
                pass

        # Session events
        if tool.startswith("session_"):
            session_events.append({
                "ts": ts,
                "event": tool,
                "pwd": row["session_pwd"],
                "metadata": metadata
            })

        # Tool usage with details from metadata
        else:
            session_id = row["session_pwd"].split("/")[-1][:8] if row["session_pwd"] else "unknown"
            command = metadata.get("command", "")
            success = metadata.get("success", True)
            model = metadata.get("model", "sonnet")

            # Tool usage entry
            tool_usage_entries.append({
                "ts": ts,
                "tool": tool,
                "session": session_id,
                "model": model,
                "source": "sqlite",
                "file_path": file_path,
                "command": command or "",
                "success": success
            })

            # Tool success entry
            tool_success_entries.append({
                "ts": ts,
                "tool": tool,
                "success": success,
                "exit_code": metadata.get("exit_code", 0),
                "session": session_id
            })

            # Command usage (for Bash tools)
            if tool == "Bash" and command:
                base_cmd = command.split()[0] if command else "unknown"
                command_usage_entries.append({
                    "ts": ts,
                    "command": base_cmd,
                    "full_command": command[:200],
                    "success": success,
                    "session": session_id
                })

            # Activity events with details
            activity_events.append({
                "ts": ts,
                "type": "tool_use",
                "tool": tool,
                "file_path": file_path,
                "command": command[:200] if command else "",
                "success": success,
                "pwd": row["session_pwd"]
            })

        new_events += 1

    conn.close()

    # Append to JSONL files
    if tool_usage_entries:
        with open(TOOL_USAGE_FILE, "a") as f:
            for entry in tool_usage_entries:
                f.write(json.dumps(entry) + "\n")

    if session_events:
        with open(SESSION_EVENTS_FILE, "a") as f:
            for entry in session_events:
                f.write(json.dumps(entry) + "\n")

    if activity_events:
        with open(ACTIVITY_EVENTS_FILE, "a") as f:
            for entry in activity_events:
                f.write(json.dumps(entry) + "\n")

    if command_usage_entries:
        with open(COMMAND_USAGE_FILE, "a") as f:
            for entry in command_usage_entries:
                f.write(json.dumps(entry) + "\n")

    if tool_success_entries:
        with open(TOOL_SUCCESS_FILE, "a") as f:
            for entry in tool_success_entries:
                f.write(json.dumps(entry) + "\n")

    # Save new sync state
    if new_events > 0:
        save_sync_state(max_ts)

    return new_events

if __name__ == "__main__":
    try:
        count = sync_tool_events()
        print(f"✅ Synced {count} events from SQLite to JSONL")
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        import sys
        sys.exit(1)
