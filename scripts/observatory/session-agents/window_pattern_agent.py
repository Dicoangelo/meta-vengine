#!/usr/bin/env python3
"""
Window Pattern Agent

Detects window boundaries and reset patterns from activity data.
Provides DQ-scored analysis of window timing and duration.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List


class WindowPatternAgent:
    """
    Agent for detecting and analyzing window patterns.

    Weight in ACE consensus: 0.20
    """

    def __init__(self):
        self.data_dir = Path.home() / ".claude" / "data"
        self.kernel_dir = Path.home() / ".claude" / "kernel"
        self.activity_file = self.data_dir / "activity-events.jsonl"
        self.state_file = self.kernel_dir / "session-state.json"
        self.baselines_file = self.kernel_dir / "session-baselines.json"

    def analyze(self, context: Dict = None) -> Dict:
        """
        Analyze window patterns.

        Returns:
            DQ-scored analysis result
        """
        state = self._load_state()
        baselines = self._load_baselines()

        window = state.get("window", {})

        # Calculate window metrics
        position = window.get("positionPercent", 0)
        remaining = window.get("remainingMinutes", 300)
        confidence = window.get("confidence", 0.5)

        # Detect current phase
        if position < 30:
            phase = "early"
            phase_recommendation = "Good time for complex Opus tasks"
        elif position < 70:
            phase = "mid"
            phase_recommendation = "Balance between Opus and Sonnet"
        else:
            phase = "late"
            phase_recommendation = "Prioritize completion, use Sonnet/Haiku"

        # Check for window drift
        reset_times = baselines.get("windowPatterns", {}).get("resetTimes", [])
        next_reset = self._find_next_reset(reset_times)

        # Calculate DQ scores
        validity = 0.8 if window.get("id") else 0.3
        specificity = min(0.9, confidence + 0.1)
        correctness = 0.7 if remaining > 0 else 0.5

        return {
            "summary": f"Window {phase} phase ({position}%), {remaining}m remaining",
            "dq_score": {
                "validity": validity,
                "specificity": specificity,
                "correctness": correctness
            },
            "confidence": confidence,
            "data": {
                "position": position,
                "remainingMinutes": remaining,
                "phase": phase,
                "phaseRecommendation": phase_recommendation,
                "nextReset": next_reset,
                "windowId": window.get("id")
            }
        }

    def _find_next_reset(self, reset_times: List[Dict]) -> Dict:
        """Find next reset time from patterns."""
        now = datetime.now()
        current_hour = now.hour

        for reset in sorted(reset_times, key=lambda x: x.get("hour", 0)):
            if reset.get("hour", 0) > current_hour:
                reset_time = now.replace(
                    hour=reset["hour"],
                    minute=0,
                    second=0
                )
                return {
                    "hour": reset["hour"],
                    "time": reset_time.strftime("%H:%M"),
                    "reliability": reset.get("reliability", 0.5)
                }

        # Wrap to next day
        if reset_times:
            first = min(reset_times, key=lambda x: x.get("hour", 24))
            return {
                "hour": first["hour"],
                "time": f"Tomorrow {first['hour']:02d}:00",
                "reliability": first.get("reliability", 0.5)
            }

        return None

    def _load_state(self) -> Dict:
        """Load session state."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {}

    def _load_baselines(self) -> Dict:
        """Load session baselines."""
        if self.baselines_file.exists():
            with open(self.baselines_file) as f:
                return json.load(f)
        return {}


if __name__ == "__main__":
    agent = WindowPatternAgent()
    result = agent.analyze()
    print(json.dumps(result, indent=2))
