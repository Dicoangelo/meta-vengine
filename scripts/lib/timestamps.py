"""
Timestamp normalization library for Claude infrastructure.

Handles the mismatch between:
- JavaScript: Date.now() returns milliseconds
- Python: time.time() returns seconds

All timestamps are normalized to Unix seconds for consistency.
"""

from datetime import datetime
from typing import Union, Optional

# Year 2100 in Unix seconds - timestamps above this are likely milliseconds
MS_THRESHOLD = 4102444800


def normalize_ts(ts: Union[int, float, str, None]) -> Optional[int]:
    """
    Convert any timestamp format to Unix seconds.

    Handles:
    - Milliseconds (JS Date.now())
    - Seconds (Python time.time())
    - ISO 8601 strings
    - None values

    Args:
        ts: Timestamp in any format

    Returns:
        Unix timestamp in seconds, or None if input is None
    """
    if ts is None:
        return None

    # Handle ISO 8601 strings
    if isinstance(ts, str):
        try:
            # Handle 'Z' suffix and timezone offsets
            ts_clean = ts.replace('Z', '+00:00')
            dt = datetime.fromisoformat(ts_clean)
            return int(dt.timestamp())
        except ValueError:
            # Try parsing as numeric string
            try:
                ts = float(ts)
            except ValueError:
                return None

    # Convert to float for comparison
    ts = float(ts)

    # If timestamp is larger than year 2100 in seconds, it's milliseconds
    if ts > MS_THRESHOLD:
        return int(ts / 1000)

    return int(ts)


def safe_fromtimestamp(ts: Union[int, float, str, None]) -> Optional[datetime]:
    """
    Auto-normalizing version of datetime.fromtimestamp().

    Safely converts any timestamp format to a datetime object.
    Handles the "Year 58034" error caused by millisecond timestamps.

    Args:
        ts: Timestamp in any format (ms, s, or ISO string)

    Returns:
        datetime object, or None if input is None or invalid
    """
    normalized = normalize_ts(ts)
    if normalized is None:
        return None

    try:
        return datetime.fromtimestamp(normalized)
    except (ValueError, OSError):
        # Handle edge cases like negative timestamps
        return None


def now_seconds() -> int:
    """
    Get current time as Unix timestamp in seconds.

    Use this instead of time.time() * 1000 for consistency.

    Returns:
        Current Unix timestamp in seconds
    """
    return int(datetime.now().timestamp())


def to_iso(ts: Union[int, float, str, None]) -> Optional[str]:
    """
    Convert any timestamp to ISO 8601 format.

    Args:
        ts: Timestamp in any format

    Returns:
        ISO 8601 string, or None if input is None/invalid
    """
    dt = safe_fromtimestamp(ts)
    if dt is None:
        return None
    return dt.isoformat()


def is_milliseconds(ts: Union[int, float]) -> bool:
    """
    Check if a timestamp appears to be in milliseconds.

    Args:
        ts: Numeric timestamp

    Returns:
        True if timestamp is likely in milliseconds
    """
    return float(ts) > MS_THRESHOLD
