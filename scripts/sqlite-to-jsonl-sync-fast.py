#!/usr/bin/env python3
"""
Fast SQLite-to-JSONL Sync - Enriches JSONL files from SQLite transcripts
Runs every minute via LaunchAgent to keep JSONL files up-to-date with full details.

This is MUCH faster than full backfill (only processes new entries since last sync).
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
DATA_DIR = CLAUDE_DIR / "data"
DB_PATH = DATA_DIR / "claude.db"
STATE_FILE = DATA_DIR / ".last-sqlite-sync"

# JSONL output files
TOOL_USAGE_JSONL = DATA_DIR / "tool-usage.jsonl"
COMMAND_USAGE_JSONL = DATA_DIR / "command-usage.jsonl"
TOOL_SUCCESS_JSONL = DATA_DIR / "tool-success.jsonl"
ACTIVITY_EVENTS_JSONL = DATA_DIR / "activity-events.jsonl"

def get_last_sync_id():
    """Get the last synced transcript ID."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            return data.get("last_transcript_id", 0)
        except:
            pass
    return 0

def save_sync_state(last_id):
    """Save the last synced transcript ID."""
    STATE_FILE.write_text(json.dumps({
        "last_transcript_id": last_id,
        "last_sync": datetime.now().isoformat()
    }))

def sync_from_sqlite():
    """Sync new tool events from SQLite transcripts to JSONL files."""
    if not DB_PATH.exists():
        print("SQLite database not found, skipping sync")
        return 0

    last_id = get_last_sync_id()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get new tool use events from transcripts
    cursor.execute("""
        SELECT
            id,
            session_id,
            role,
            content,
            created_at
        FROM transcripts
        WHERE id > ?
          AND role = 'assistant'
          AND content LIKE '%tool_use%'
        ORDER BY id ASC
        LIMIT 1000
    """, (last_id,))

    rows = cursor.fetchall()

    synced = 0
    max_id = last_id

    for row in rows:
        try:
            content = json.loads(row["content"])
            ts = int(datetime.fromisoformat(row["created_at"]).timestamp())
            session_id = row["session_id"][:8]

            # Extract tool uses from content blocks
            for block in content:
                if block.get("type") == "tool_use":
                    tool_name = block.get("name", "unknown")
                    tool_input = block.get("input", {})

                    # Extract file path for Write/Edit/Read
                    file_path = tool_input.get("file_path", "")

                    # Extract command for Bash
                    command = tool_input.get("command", "") if tool_name == "Bash" else ""
                    base_cmd = command.split()[0] if command else ""

                    # Write to tool-usage.jsonl with details
                    tool_entry = {
                        "ts": ts,
                        "tool": tool_name,
                        "session": session_id,
                        "model": "sonnet",  # Default, could be extracted from session
                        "source": "sqlite",
                        "file_path": file_path,
                        "command": command[:500] if command else ""
                    }
                    with open(TOOL_USAGE_JSONL, "a") as f:
                        f.write(json.dumps(tool_entry) + "\n")

                    # Write to command-usage.jsonl for Bash
                    if tool_name == "Bash" and command:
                        cmd_entry = {
                            "ts": ts,
                            "command": base_cmd,
                            "full_command": command[:200],
                            "session": session_id
                        }
                        with open(COMMAND_USAGE_JSONL, "a") as f:
                            f.write(json.dumps(cmd_entry) + "\n")

                    # Write to activity-events.jsonl
                    activity_entry = {
                        "ts": ts,
                        "type": "tool_use",
                        "tool": tool_name,
                        "file_path": file_path,
                        "command": command[:200] if command else "",
                        "pwd": ""  # Not available from transcript
                    }
                    with open(ACTIVITY_EVENTS_JSONL, "a") as f:
                        f.write(json.dumps(activity_entry) + "\n")

                    synced += 1

            max_id = max(max_id, row["id"])

        except Exception as e:
            print(f"Error processing transcript {row['id']}: {e}")
            continue

    conn.close()

    # Save progress
    if max_id > last_id:
        save_sync_state(max_id)

    return synced

if __name__ == "__main__":
    synced = sync_from_sqlite()
    if synced > 0:
        print(f"✅ Synced {synced} events from SQLite to JSONL")
    else:
        print("✓ Already up to date")
