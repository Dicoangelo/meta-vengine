#!/usr/bin/env python3
"""
Universal Hook Handler for Claude Code
Writes all tool events to BOTH SQLite AND JSONL files for immediate availability.

Usage:
    python3 sqlite-hook.py <tool_name> [file_path]

Environment variables used:
    CLAUDE_FILE_PATH - File path for Write/Edit operations
    PWD - Current working directory
"""

import sqlite3
import sys
import os
import json
import time
from pathlib import Path

# Data paths
DB_PATH = Path.home() / ".agent-core" / "storage" / "antigravity.db"
CLAUDE_DB_PATH = Path.home() / ".claude" / "data" / "claude.db"  # For CCC dashboard
SUPERMEMORY_DB_PATH = Path.home() / ".claude" / "memory" / "supermemory.db"  # For 10x dashboard
DATA_DIR = Path.home() / ".claude" / "data"
TOOL_USAGE_JSONL = DATA_DIR / "tool-usage.jsonl"
SESSION_EVENTS_JSONL = DATA_DIR / "session-events.jsonl"
ACTIVITY_EVENTS_JSONL = DATA_DIR / "activity-events.jsonl"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

def get_db():
    """Get database connection with WAL mode for concurrent access."""
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def log_tool_event(tool: str, file_path: str = None, metadata: dict = None):
    """Log a tool event to BOTH SQLite AND JSONL files with full details."""
    try:
        ts = int(time.time())
        session_pwd = os.environ.get("PWD", os.getcwd())
        session_id = session_pwd.split("/")[-1][:8] if session_pwd else "unknown"

        # Extract detailed metadata from environment
        tool_input = os.environ.get("CLAUDE_TOOL_INPUT", "")
        tool_output = os.environ.get("CLAUDE_TOOL_OUTPUT", "")
        exit_code = int(os.environ.get("CLAUDE_TOOL_EXIT_CODE", "0"))

        # Extract command for Bash tools
        command = ""
        if tool == "Bash" and tool_input:
            try:
                # Try to parse JSON input
                input_data = json.loads(tool_input)
                command = input_data.get("command", "")
            except:
                # Fallback: extract from string
                if '"command"' in tool_input:
                    command = tool_input.split('"command":"')[1].split('"')[0][:500]  # Limit to 500 chars

        # Determine success/failure
        success = exit_code == 0 and not any(word in tool_output.lower() for word in ["error", "failed", "exception"])

        # Build metadata
        if metadata is None:
            metadata = {}
        metadata.update({
            "command": command if command else None,
            "success": success,
            "exit_code": exit_code,
            "model": os.environ.get("CLAUDE_MODEL", "sonnet")
        })

        # 1. Write to antigravity.db (agent-core) with full metadata
        conn = get_db()
        cursor = conn.cursor()
        meta_json = json.dumps(metadata)

        cursor.execute("""
            INSERT INTO tool_events (ts, tool, file_path, session_pwd, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (ts, tool, file_path, session_pwd, meta_json))

        conn.commit()
        conn.close()

        # 1b. Write to claude.db (CCC dashboard) with its expected schema
        try:
            claude_conn = sqlite3.connect(str(CLAUDE_DB_PATH), timeout=5.0)
            claude_conn.execute("PRAGMA journal_mode=WAL")
            claude_cursor = claude_conn.cursor()
            claude_cursor.execute("""
                INSERT INTO tool_events (timestamp, tool_name, success, duration_ms, error_message, context)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ts, tool, 1 if success else 0, 0, None if success else "Error detected", session_pwd))
            claude_conn.commit()
            claude_conn.close()
        except Exception:
            pass  # Don't fail if claude.db write fails

        # 1c. Write to supermemory.db (for 10x dashboard)
        try:
            sm_conn = sqlite3.connect(str(SUPERMEMORY_DB_PATH), timeout=5.0)
            sm_conn.execute("PRAGMA journal_mode=WAL")
            sm_conn.execute("PRAGMA busy_timeout=5000")
            sm_cursor = sm_conn.cursor()
            timestamp_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
            project = detect_project(session_pwd)
            sm_cursor.execute("""
                INSERT INTO tool_usage (timestamp, tool_name, success, project)
                VALUES (?, ?, ?, ?)
            """, (timestamp_str, tool, 1 if success else 0, project))
            sm_conn.commit()
            sm_conn.close()
        except Exception:
            pass  # Don't fail if supermemory.db write fails

        # 2. Write to tool-usage.jsonl with details
        tool_usage_entry = {
            "ts": ts,
            "tool": tool,
            "session": session_id,
            "model": metadata.get("model", "sonnet"),
            "source": "hook",
            "file_path": file_path or "",
            "command": command or "",
            "success": success
        }
        with open(TOOL_USAGE_JSONL, "a") as f:
            f.write(json.dumps(tool_usage_entry) + "\n")

        # 3. Write to tool-success.jsonl for analytics
        tool_success_file = DATA_DIR / "tool-success.jsonl"
        success_entry = {
            "ts": ts,
            "tool": tool,
            "success": success,
            "exit_code": exit_code,
            "session": session_id
        }
        with open(tool_success_file, "a") as f:
            f.write(json.dumps(success_entry) + "\n")

        # 4. Write to command-usage.jsonl for Bash commands
        if tool == "Bash" and command:
            cmd_file = DATA_DIR / "command-usage.jsonl"
            base_cmd = command.split()[0] if command else "unknown"
            cmd_entry = {
                "ts": ts,
                "command": base_cmd,
                "full_command": command[:200],  # Limit length
                "success": success,
                "session": session_id
            }
            with open(cmd_file, "a") as f:
                f.write(json.dumps(cmd_entry) + "\n")

        # 5. Write to activity-events.jsonl with full context
        activity_entry = {
            "ts": ts,
            "type": "tool_use",
            "tool": tool,
            "file_path": file_path or "",
            "command": command or "",
            "success": success,
            "pwd": session_pwd
        }
        with open(ACTIVITY_EVENTS_JSONL, "a") as f:
            f.write(json.dumps(activity_entry) + "\n")

        # 4. Write to activity.log for backwards compatibility
        log_file = Path.home() / ".claude" / "activity.log"
        with open(log_file, "a") as f:
            timestamp = time.strftime("%H:%M:%S")
            if file_path:
                f.write(f"{timestamp} {tool} {file_path}\n")
            else:
                f.write(f"{timestamp} {tool}\n")

    except Exception as e:
        # Fail silently to not block Claude operations
        sys.stderr.write(f"hook error: {e}\n")

def log_session_event(event_type: str):
    """Log session start/end events to BOTH SQLite AND JSONL."""
    try:
        ts = int(time.time())
        pwd = os.environ.get("PWD", os.getcwd())
        project_id = detect_project(pwd)
        session_id = os.environ.get("CLAUDE_SESSION_ID", str(ts))

        # 1. Write to SQLite
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO tool_events (ts, tool, session_pwd, metadata)
            VALUES (?, ?, ?, ?)
        """, (ts, f"session_{event_type}", pwd, json.dumps({"project": project_id})))

        conn.commit()
        conn.close()

        # 2. Write to session-events.jsonl (for dashboard)
        session_entry = {
            "ts": ts,
            "event": f"session_{event_type}",
            "session_id": session_id,
            "pwd": pwd,
            "project": project_id,
            "model": os.environ.get("CLAUDE_MODEL", "sonnet")
        }
        with open(SESSION_EVENTS_JSONL, "a") as f:
            f.write(json.dumps(session_entry) + "\n")

        # 3. Write to activity-events.jsonl
        activity_entry = {
            "ts": ts,
            "type": f"session_{event_type}",
            "pwd": pwd,
            "project": project_id
        }
        with open(ACTIVITY_EVENTS_JSONL, "a") as f:
            f.write(json.dumps(activity_entry) + "\n")

        # 4. Write to supermemory.db (for 10x dashboard)
        try:
            sm_conn = sqlite3.connect(str(SUPERMEMORY_DB_PATH), timeout=5.0)
            sm_conn.execute("PRAGMA journal_mode=WAL")
            sm_conn.execute("PRAGMA busy_timeout=5000")
            sm_cursor = sm_conn.cursor()
            timestamp_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
            hour = int(time.strftime("%H"))
            model = os.environ.get("CLAUDE_MODEL", "sonnet")

            # Determine cognitive mode based on hour
            if 5 <= hour < 9:
                cog_mode = "morning"
            elif 9 <= hour < 12 or 14 <= hour < 18:
                cog_mode = "peak"
            elif 12 <= hour < 14:
                cog_mode = "dip"
            elif 18 <= hour < 22:
                cog_mode = "evening"
            else:
                cog_mode = "deep_night"

            if event_type == "start":
                sm_cursor.execute("""
                    INSERT INTO sessions (timestamp, project, cognitive_mode, hour, model)
                    VALUES (?, ?, ?, ?, ?)
                """, (timestamp_str, project_id, cog_mode, hour, model))
            else:  # end
                sm_cursor.execute("""
                    INSERT INTO session_ends (timestamp, project)
                    VALUES (?, ?)
                """, (timestamp_str, project_id))

            sm_conn.commit()
            sm_conn.close()
        except Exception:
            pass  # Don't fail if supermemory.db write fails

    except Exception as e:
        sys.stderr.write(f"session hook error: {e}\n")

def detect_project(pwd: str) -> str:
    """Detect project ID from working directory."""
    home = str(Path.home())
    pwd_path = Path(pwd)

    # Known project paths
    project_map = {
        "OS-App": "os-app",
        "CareerCoachAntigravity": "careercoach",
        "researchgravity": "researchgravity",
        "Metaventions-AI-Landing": "metaventions",
        "The-Decosystem": "decosystem",
        ".agent-core": "agent-core",
        ".claude": "claude-config",
    }

    for folder, project_id in project_map.items():
        if folder in pwd_path.parts:
            return project_id

    return "general"

def main():
    if len(sys.argv) < 2:
        print("Usage: sqlite-hook.py <tool_name> [file_path]")
        sys.exit(1)

    tool = sys.argv[1]

    # Handle session events
    if tool in ("session_start", "session_end"):
        log_session_event(tool.replace("session_", ""))
        return

    # Get file path from arg or environment
    file_path = None
    if len(sys.argv) > 2:
        file_path = sys.argv[2]
    elif os.environ.get("CLAUDE_FILE_PATH"):
        file_path = os.environ["CLAUDE_FILE_PATH"]

    log_tool_event(tool, file_path)

if __name__ == "__main__":
    main()
