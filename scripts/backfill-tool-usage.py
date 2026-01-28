#!/usr/bin/env python3
"""
Backfill tool-usage.jsonl and session-events.jsonl from transcripts.
Also creates activity-timeline.json for dashboard.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict

PROJECTS_DIR = Path.home() / ".claude" / "projects"
DATA_DIR = Path.home() / ".claude" / "data"
KERNEL_DIR = Path.home() / ".claude" / "kernel"

TOOL_USAGE_FILE = DATA_DIR / "tool-usage.jsonl"
SESSION_EVENTS_FILE = DATA_DIR / "session-events.jsonl"
COMMAND_USAGE_FILE = DATA_DIR / "command-usage.jsonl"
ACTIVITY_TIMELINE_FILE = KERNEL_DIR / "activity-timeline.json"

def extract_tool_usage(limit=200):
    """Extract tool usage from transcripts."""

    transcripts = sorted(PROJECTS_DIR.glob("**/*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
    print(f"Found {len(transcripts)} transcript files")

    tool_events = []
    session_events = []
    command_events = []
    activity_by_day = defaultdict(lambda: {"tools": 0, "sessions": 0, "messages": 0})

    processed = 0
    for transcript in transcripts[:limit]:
        try:
            session_start = None
            session_end = None
            session_tools = []
            message_count = 0

            with open(transcript) as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        ts = entry.get('timestamp')
                        if ts:
                            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                            day = dt.strftime('%Y-%m-%d')

                            if session_start is None:
                                session_start = ts
                            session_end = ts

                        # Tool usage - check both top-level and nested in message.content
                        if entry.get('type') == 'tool_use':
                            tool_name = entry.get('name', 'unknown')
                            tool_event = {
                                "ts": int(dt.timestamp()) if ts else 0,
                                "tool": tool_name,
                                "session": transcript.stem[:8],
                                "source": "backfill"
                            }
                            tool_events.append(json.dumps(tool_event))
                            session_tools.append(tool_name)
                            if ts:
                                activity_by_day[day]["tools"] += 1

                        # Also check assistant messages for tool_use in content array
                        if entry.get('type') == 'assistant':
                            msg = entry.get('message', {})
                            content = msg.get('content', [])
                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict) and item.get('type') == 'tool_use':
                                        tool_name = item.get('name', 'unknown')
                                        tool_event = {
                                            "ts": int(dt.timestamp()) if ts else 0,
                                            "tool": tool_name,
                                            "session": transcript.stem[:8],
                                            "source": "backfill"
                                        }
                                        tool_events.append(json.dumps(tool_event))
                                        session_tools.append(tool_name)
                                        if ts:
                                            activity_by_day[day]["tools"] += 1

                        # Message counting
                        if entry.get('type') in ['user', 'assistant']:
                            message_count += 1
                            if ts:
                                activity_by_day[day]["messages"] += 1

                        # Extract command hints from user messages
                        if entry.get('type') == 'user':
                            msg = entry.get('message', {})
                            content = msg.get('content', '')
                            if isinstance(content, str):
                                # Detect slash commands
                                if content.startswith('/'):
                                    cmd = content.split()[0][1:]
                                    cmd_event = {
                                        "ts": int(dt.timestamp()) if ts else 0,
                                        "cmd": cmd,
                                        "context": "skill",
                                        "pwd": str(transcript.parent),
                                        "source": "backfill"
                                    }
                                    command_events.append(json.dumps(cmd_event))

                    except (json.JSONDecodeError, KeyError, TypeError):
                        continue

            # Create session event
            if session_start:
                day = datetime.fromisoformat(session_start.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                activity_by_day[day]["sessions"] += 1

                session_event = {
                    "session_id": transcript.stem[:8],
                    "start": session_start,
                    "end": session_end,
                    "messages": message_count,
                    "tools": len(session_tools),
                    "top_tools": list(set(session_tools))[:5],
                    "source": "backfill"
                }
                session_events.append(json.dumps(session_event))

            processed += 1

        except Exception as e:
            continue

    print(f"Processed {processed} transcripts")
    return tool_events, session_events, command_events, dict(activity_by_day)

def write_backfill_data(tool_events, session_events, command_events, activity_by_day):
    """Write backfilled data to files."""

    # Append tool usage
    with open(TOOL_USAGE_FILE, 'a') as f:
        for event in tool_events:
            f.write(event + '\n')
    print(f"Added {len(tool_events)} tool usage events")

    # Append session events
    with open(SESSION_EVENTS_FILE, 'a') as f:
        for event in session_events:
            f.write(event + '\n')
    print(f"Added {len(session_events)} session events")

    # Append command events (avoid duplicates with existing)
    existing_commands = set()
    if COMMAND_USAGE_FILE.exists():
        with open(COMMAND_USAGE_FILE) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    existing_commands.add((entry.get('ts'), entry.get('cmd')))
                except:
                    pass

    new_commands = 0
    with open(COMMAND_USAGE_FILE, 'a') as f:
        for event in command_events:
            entry = json.loads(event)
            if (entry.get('ts'), entry.get('cmd')) not in existing_commands:
                f.write(event + '\n')
                new_commands += 1
    print(f"Added {new_commands} command events")

    # Create activity timeline
    timeline = {
        "generated": datetime.now().isoformat(),
        "days": sorted(activity_by_day.items(), key=lambda x: x[0], reverse=True)[:30],
        "totals": {
            "tools": sum(d["tools"] for d in activity_by_day.values()),
            "sessions": sum(d["sessions"] for d in activity_by_day.values()),
            "messages": sum(d["messages"] for d in activity_by_day.values())
        }
    }

    ACTIVITY_TIMELINE_FILE.write_text(json.dumps(timeline, indent=2))
    print(f"Created activity timeline with {len(timeline['days'])} days")

def main():
    print("=" * 60)
    print("TOOL USAGE & SESSION BACKFILL")
    print("=" * 60)
    print()

    # Ensure directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    KERNEL_DIR.mkdir(parents=True, exist_ok=True)

    # Extract data
    print("Extracting from transcripts...")
    tool_events, session_events, command_events, activity_by_day = extract_tool_usage(limit=200)
    print(f"  Tool events: {len(tool_events)}")
    print(f"  Session events: {len(session_events)}")
    print(f"  Command events: {len(command_events)}")
    print(f"  Days with activity: {len(activity_by_day)}")
    print()

    # Write data
    print("Writing backfill data...")
    write_backfill_data(tool_events, session_events, command_events, activity_by_day)
    print()

    print("=" * 60)
    print("BACKFILL COMPLETE")
    print("=" * 60)

if __name__ == '__main__':
    main()
