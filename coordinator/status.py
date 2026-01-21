"""Status display module for Claude coordinator."""

import json
from pathlib import Path
from typing import Dict, List, Any

from .constants import STATE_ICONS
from .utils import format_duration, truncate_text


DATA_DIR = Path.home() / ".claude" / "coordinator" / "data"
ACTIVE_AGENTS_FILE = DATA_DIR / "active-agents.json"
FILE_LOCKS_FILE = DATA_DIR / "file-locks.json"
COORDINATION_LOG_FILE = DATA_DIR / "coordination-log.jsonl"


def load_agents() -> Dict[str, Any]:
    """Load active agents from active-agents.json.

    Returns:
        dict: Active agents data, or empty dict if file doesn't exist/is empty
    """
    if not ACTIVE_AGENTS_FILE.exists():
        return {}

    try:
        with open(ACTIVE_AGENTS_FILE, 'r') as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, IOError):
        return {}


def load_locks() -> Dict[str, Any]:
    """Load file locks from file-locks.json.

    Returns:
        dict: File locks data, or empty dict if file doesn't exist/is empty
    """
    if not FILE_LOCKS_FILE.exists():
        return {}

    try:
        with open(FILE_LOCKS_FILE, 'r') as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, IOError):
        return {}


def get_recent_tasks(limit: int = 5) -> List[Dict[str, Any]]:
    """Read last N lines from coordination-log.jsonl.

    Args:
        limit: Maximum number of recent tasks to return

    Returns:
        list: List of task dicts (most recent first), or empty list if file doesn't exist
    """
    if not COORDINATION_LOG_FILE.exists():
        return []

    try:
        with open(COORDINATION_LOG_FILE, 'r') as f:
            lines = f.readlines()

        # Get last N lines
        recent_lines = lines[-limit:] if len(lines) > limit else lines

        # Parse JSON, filter out any malformed lines
        tasks = []
        for line in reversed(recent_lines):  # Most recent first
            try:
                tasks.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue

        return tasks
    except IOError:
        return []


def format_status() -> str:
    """Format status display with agent counts, lock counts, and recent tasks.

    Returns:
        str: Formatted status string
    """
    agents = load_agents()
    locks = load_locks()
    recent_tasks = get_recent_tasks(limit=5)

    # Count agents
    agent_count = len(agents)

    # Count locks
    lock_count = len(locks)

    # Build status string
    lines = []
    lines.append("━━━ Claude Coordinator Status ━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    # Agent summary
    lines.append(f"Active Agents: {agent_count}")
    if agents:
        for agent_id, agent_data in agents.items():
            status = agent_data.get("status", "unknown")
            icon = STATE_ICONS.get(status, "❓")
            task = truncate_text(agent_data.get("task", "Unknown task"), max_len=50)
            lines.append(f"  {icon} {agent_id}: {task}")

    lines.append("")

    # Lock summary
    lines.append(f"File Locks: {lock_count}")
    if locks:
        for file_path, lock_data in locks.items():
            agent_id = lock_data.get("agent_id", "unknown")
            truncated_path = truncate_text(file_path, max_len=60)
            lines.append(f"  🔒 {truncated_path} (locked by {agent_id})")

    lines.append("")

    # Recent tasks
    lines.append(f"Recent Tasks ({len(recent_tasks)}):")
    if recent_tasks:
        for task in recent_tasks:
            task_id = task.get("task_id", "unknown")
            status = task.get("status", "unknown")
            icon = STATE_ICONS.get(status, "❓")
            strategy = task.get("strategy", "unknown")
            duration = format_duration(task.get("duration_seconds", 0))
            task_desc = truncate_text(task.get("task", "Unknown task"), max_len=40)
            cost = task.get("total_cost", 0.0)

            lines.append(f"  {icon} {task_id} [{strategy}] {duration} ${cost:.4f}")
            lines.append(f"     {task_desc}")
    else:
        lines.append("  No recent tasks")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


if __name__ == "__main__":
    # Simple test when run directly
    print(format_status())
