"""Multi-agent coordinator package."""
from .constants import DEFAULT_TIMEOUT, MAX_AGENTS, STRATEGIES, STATE_ICONS
from .utils import format_duration, truncate_text
from .status import load_agents, load_locks, get_recent_tasks, format_status

__version__ = "1.0.0"
__all__ = [
    "DEFAULT_TIMEOUT", "MAX_AGENTS", "STRATEGIES", "STATE_ICONS",
    "format_duration", "truncate_text",
    "load_agents", "load_locks", "get_recent_tasks", "format_status"
]
