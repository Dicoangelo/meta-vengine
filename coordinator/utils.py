"""Utility functions for the Claude coordinator."""


def format_duration(seconds):
    """Convert seconds to human readable format (e.g., '2m 34s')."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def truncate_text(text, max_len=40):
    """Truncate text to max_len characters, adding '...' if truncated."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
