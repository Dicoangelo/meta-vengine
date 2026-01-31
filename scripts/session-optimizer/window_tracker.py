#!/usr/bin/env python3
"""
Window Tracker - Detects and learns window reset patterns

Analyzes activity-events.jsonl to detect:
- Session boundaries (long gaps indicate resets)
- Daily usage patterns
- Optimal start times based on historical data
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

# Import timestamp normalization
sys.path.insert(0, str(Path.home() / ".claude/scripts"))
from lib.timestamps import normalize_ts


class WindowTracker:
    """Tracks and learns window reset patterns."""

    def __init__(self):
        self.data_dir = Path.home() / ".claude" / "data"
        self.kernel_dir = Path.home() / ".claude" / "kernel"
        self.activity_file = self.data_dir / "activity-events.jsonl"
        self.session_events = self.data_dir / "session-events.jsonl"
        self.baselines_file = self.kernel_dir / "session-baselines.json"

    def detect_windows(self, days: int = 30) -> List[Dict]:
        """
        Detect window boundaries from activity patterns.

        A window reset is detected when there's a gap > 2 hours
        followed by renewed activity.
        """
        events = self._load_recent_events(days)
        if not events:
            return []

        windows = []
        current_window = None
        gap_threshold_s = 2 * 60 * 60  # 2 hours in seconds

        for i, event in enumerate(events):
            ts = normalize_ts(event.get("timestamp", 0))
            if ts is None:
                continue

            if current_window is None:
                current_window = {
                    "start": ts,
                    "end": ts,
                    "event_count": 1,
                    "queries": 0,
                    "tools": 0
                }
            else:
                gap = ts - current_window["end"]

                if gap > gap_threshold_s:
                    # Window boundary detected
                    current_window["duration_s"] = current_window["end"] - current_window["start"]
                    windows.append(current_window)

                    current_window = {
                        "start": ts,
                        "end": ts,
                        "event_count": 1,
                        "queries": 0,
                        "tools": 0
                    }
                else:
                    current_window["end"] = ts
                    current_window["event_count"] += 1

            # Count event types
            if event.get("type") == "query":
                current_window["queries"] += 1
            elif event.get("type") == "tool":
                current_window["tools"] += 1

        # Close final window
        if current_window:
            current_window["duration_s"] = current_window["end"] - current_window["start"]
            windows.append(current_window)

        return windows

    def analyze_reset_patterns(self, windows: List[Dict]) -> Dict:
        """
        Analyze window data to find reset patterns.

        Returns hourly reliability scores for reset times.
        """
        if not windows:
            return {"resetTimes": [], "typicalDurationMs": 18000000}

        # Count resets by hour
        hour_counts = defaultdict(int)
        durations = []

        for window in windows:
            start_ts = window["start"]
            start_dt = datetime.fromtimestamp(start_ts / 1000)
            hour_counts[start_dt.hour] += 1
            durations.append(window.get("duration_s", 0))

        # Calculate reliability scores
        total_windows = len(windows)
        reset_times = []

        for hour, count in sorted(hour_counts.items()):
            reliability = count / total_windows
            if reliability >= 0.1:  # At least 10% of windows start at this hour
                reset_times.append({
                    "hour": hour,
                    "reliability": round(reliability, 2),
                    "count": count
                })

        # Sort by reliability
        reset_times.sort(key=lambda x: x["reliability"], reverse=True)

        # Calculate typical duration
        avg_duration = sum(durations) / len(durations) if durations else 18000000

        return {
            "resetTimes": reset_times[:5],  # Top 5 reset times
            "typicalDurationMs": int(avg_duration),
            "totalWindowsAnalyzed": total_windows
        }

    def get_current_window_position(self) -> Dict:
        """
        Estimate current position in the usage window.
        """
        baselines = self._load_baselines()
        windows = self.detect_windows(days=7)

        if not windows:
            return {
                "positionPercent": 0,
                "remainingMinutes": 300,
                "confidence": 0.5
            }

        # Find current window (most recent)
        now = datetime.now().timestamp() * 1000
        typical_duration = baselines.get("windowPatterns", {}).get(
            "typicalDurationMs", 18000000
        )

        # Estimate window start from recent activity
        current_window = windows[-1] if windows else None

        if current_window:
            elapsed = now - current_window["start"]
            position = min(100, (elapsed / typical_duration) * 100)
            remaining = max(0, typical_duration - elapsed) / 60000

            return {
                "positionPercent": round(position),
                "remainingMinutes": round(remaining),
                "confidence": baselines.get("confidence", 0.5),
                "windowStart": current_window["start"]
            }

        return {
            "positionPercent": 0,
            "remainingMinutes": round(typical_duration / 60000),
            "confidence": 0.5
        }

    def predict_next_window(self) -> Optional[str]:
        """
        Predict optimal start time for next window.
        """
        baselines = self._load_baselines()
        reset_times = baselines.get("windowPatterns", {}).get("resetTimes", [])

        if not reset_times:
            return None

        now = datetime.now()
        current_hour = now.hour

        # Find next reset time after current hour
        for reset in sorted(reset_times, key=lambda x: x["hour"]):
            if reset["hour"] > current_hour:
                next_time = now.replace(
                    hour=reset["hour"],
                    minute=15,  # 15 min after reset
                    second=0,
                    microsecond=0
                )
                return next_time.isoformat()

        # Wrap to tomorrow's first reset
        if reset_times:
            first_reset = min(reset_times, key=lambda x: x["hour"])
            next_time = (now + timedelta(days=1)).replace(
                hour=first_reset["hour"],
                minute=15,
                second=0,
                microsecond=0
            )
            return next_time.isoformat()

        return None

    def update_baselines(self, force: bool = False) -> bool:
        """
        Update session-baselines.json with learned patterns.
        """
        baselines = self._load_baselines()
        windows = self.detect_windows(days=30)

        if len(windows) < 10 and not force:
            # Not enough data to update confidently
            return False

        patterns = self.analyze_reset_patterns(windows)

        baselines["windowPatterns"] = {
            "typicalDurationMs": patterns["typicalDurationMs"],
            "resetTimes": patterns["resetTimes"]
        }

        # Update confidence based on data quality
        if patterns["totalWindowsAnalyzed"] >= 30:
            baselines["confidence"] = 0.85
        elif patterns["totalWindowsAnalyzed"] >= 15:
            baselines["confidence"] = 0.70
        else:
            baselines["confidence"] = 0.55

        baselines["lastUpdated"] = datetime.now().isoformat()

        with open(self.baselines_file, "w") as f:
            json.dump(baselines, f, indent=2)

        return True

    def _load_recent_events(self, days: int) -> List[Dict]:
        """Load recent events from activity-events.jsonl."""
        events = []
        cutoff = (datetime.now() - timedelta(days=days)).timestamp() * 1000

        if not self.activity_file.exists():
            return []

        with open(self.activity_file) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    ts = event.get("timestamp", 0)
                    if isinstance(ts, str):
                        ts = int(datetime.fromisoformat(
                            ts.replace("Z", "+00:00")
                        ).timestamp() * 1000)

                    if ts >= cutoff:
                        events.append(event)
                except json.JSONDecodeError:
                    continue

        return sorted(events, key=lambda x: x.get("timestamp", 0))

    def _load_baselines(self) -> Dict:
        """Load session baselines."""
        if self.baselines_file.exists():
            with open(self.baselines_file) as f:
                return json.load(f)
        return {}


if __name__ == "__main__":
    import sys

    tracker = WindowTracker()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "detect":
            windows = tracker.detect_windows()
            print(f"Detected {len(windows)} windows")
            for w in windows[-5:]:
                start = datetime.fromtimestamp(w["start"] / 1000)
                duration = w.get("duration_s", 0) / 60  # seconds to minutes
                print(f"  {start.isoformat()}: {duration:.0f}m, {w['event_count']} events")

        elif cmd == "analyze":
            windows = tracker.detect_windows()
            patterns = tracker.analyze_reset_patterns(windows)
            print(json.dumps(patterns, indent=2))

        elif cmd == "position":
            pos = tracker.get_current_window_position()
            print(json.dumps(pos, indent=2))

        elif cmd == "predict":
            next_window = tracker.predict_next_window()
            print(f"Next optimal window: {next_window}")

        elif cmd == "update":
            if tracker.update_baselines():
                print("Baselines updated")
            else:
                print("Not enough data to update")

    else:
        print("Window Tracker - Session window pattern detection")
        print("")
        print("Commands:")
        print("  detect   - Detect window boundaries")
        print("  analyze  - Analyze reset patterns")
        print("  position - Get current window position")
        print("  predict  - Predict next optimal window")
        print("  update   - Update baselines with learned patterns")
