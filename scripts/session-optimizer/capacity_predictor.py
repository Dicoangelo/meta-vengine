#!/usr/bin/env python3
"""
Capacity Predictor - Predicts remaining capacity and optimal timing

Uses historical data to predict:
- Remaining capacity by model
- Optimal times for different task types
- When to batch low-priority tasks
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict


class CapacityPredictor:
    """Predicts capacity and optimal timing."""

    def __init__(self):
        self.kernel_dir = Path.home() / ".claude" / "kernel"
        self.data_dir = Path.home() / ".claude" / "data"
        self.state_file = self.kernel_dir / "session-state.json"
        self.baselines_file = self.kernel_dir / "session-baselines.json"
        self.activity_file = self.data_dir / "activity-events.jsonl"
        self.capacity_log = self.data_dir / "capacity-snapshots.jsonl"

        # Capacity tiers
        self.tiers = {
            "COMFORTABLE": {"min": 0, "max": 40, "description": "Plenty of budget remaining"},
            "MODERATE": {"min": 40, "max": 70, "description": "Moderate usage, plan carefully"},
            "LOW": {"min": 70, "max": 85, "description": "Low capacity, prioritize"},
            "CRITICAL": {"min": 85, "max": 100, "description": "Near exhaustion, urgent only"}
        }

    def get_capacity_tier(self, utilization_percent: float) -> str:
        """
        Determine capacity tier from utilization percentage.
        """
        for tier, bounds in self.tiers.items():
            if bounds["min"] <= utilization_percent < bounds["max"]:
                return tier
        return "CRITICAL"

    def predict_remaining(self) -> Dict:
        """
        Predict remaining capacity for the current window.
        """
        state = self._load_state()
        baselines = self._load_baselines()

        budget = state.get("budget", {})
        used = budget.get("used", {"opus": 0, "sonnet": 0, "haiku": 0})
        capacity = budget.get("windowCapacity", 5000000)

        total_used = sum(used.values())
        remaining = capacity - total_used
        utilization = (total_used / capacity * 100) if capacity > 0 else 0

        # Estimate remaining tasks
        remaining_tasks = {
            "opus": max(0, int(remaining / 200000)),
            "sonnet": max(0, int(remaining / 50000)),
            "haiku": max(0, int(remaining / 10000))
        }

        # Predict window end based on consumption rate
        window = state.get("window", {})
        start = window.get("startedAt")
        position = window.get("positionPercent", 0)

        projected_end_usage = total_used
        if start and position > 0:
            # Linear projection
            projected_end_usage = int(total_used * (100 / position))

        return {
            "tier": self.get_capacity_tier(utilization),
            "tierDescription": self.tiers.get(self.get_capacity_tier(utilization), {}).get("description", ""),
            "utilizationPercent": round(utilization, 1),
            "remaining": {
                "tokens": remaining,
                "tasks": remaining_tasks
            },
            "projectedWindowEnd": projected_end_usage,
            "exceedsCapacity": projected_end_usage > capacity
        }

    def predict_consumption_rate(self, hours: int = 1) -> Dict:
        """
        Predict token consumption rate based on recent activity.
        """
        # Load recent capacity snapshots
        snapshots = self._load_capacity_snapshots(hours)

        if len(snapshots) < 2:
            return {
                "rate": 0,
                "confidence": 0.3,
                "message": "Insufficient data for prediction"
            }

        # Calculate consumption between snapshots
        first = snapshots[0]
        last = snapshots[-1]

        time_delta = (
            datetime.fromisoformat(last["timestamp"].replace("Z", "+00:00")) -
            datetime.fromisoformat(first["timestamp"].replace("Z", "+00:00"))
        ).total_seconds() / 3600  # hours

        if time_delta <= 0:
            return {"rate": 0, "confidence": 0.3}

        usage_delta = last.get("budgetUtilization", 0) - first.get("budgetUtilization", 0)
        rate = usage_delta / time_delta  # % per hour

        # Confidence based on data points
        confidence = min(0.9, 0.3 + (len(snapshots) * 0.1))

        return {
            "rate": round(rate, 2),
            "unit": "% per hour",
            "samples": len(snapshots),
            "confidence": confidence,
            "timeHorizon": f"{hours}h"
        }

    def get_optimal_times(self) -> Dict:
        """
        Get optimal times for different task types based on patterns.
        """
        baselines = self._load_baselines()
        peak_hours = baselines.get("peakHours", [14, 15, 16])

        now = datetime.now()
        current_hour = now.hour

        # Remaining peak hours today
        remaining_peak = [h for h in peak_hours if h > current_hour]

        # Suggest batch window (evening/off-peak)
        batch_window = None
        if current_hour < 17:
            batch_window = "17:00-19:00"
        elif current_hour < 21:
            batch_window = "21:00-23:00"

        return {
            "peakHours": peak_hours,
            "remainingPeakHours": remaining_peak,
            "currentHour": current_hour,
            "isCurrentlyPeak": current_hour in peak_hours,
            "batchWindow": batch_window,
            "recommendations": {
                "opus_tasks": "Use during peak hours for complex work" if remaining_peak else "Reserve for tomorrow's peak",
                "sonnet_tasks": "Good for current timeframe",
                "haiku_tasks": "Best for batch window or off-peak"
            }
        }

    def should_switch_model(self, current_complexity: float) -> Dict:
        """
        Determine if model should be switched based on capacity.
        """
        capacity = self.predict_remaining()
        baselines = self._load_baselines()

        thresholds = baselines.get("budgetThresholds", {})
        downgrade_at = thresholds.get("downgradeThreshold", 0.85)
        upgrade_at = thresholds.get("upgradeAt", 0.30)

        utilization = capacity["utilizationPercent"] / 100

        # Determine ideal model for complexity
        if current_complexity >= 0.7:
            ideal = "opus"
        elif current_complexity >= 0.3:
            ideal = "sonnet"
        else:
            ideal = "haiku"

        # Check if we should downgrade
        should_downgrade = utilization >= downgrade_at
        should_upgrade = utilization <= upgrade_at

        recommendation = ideal
        if should_downgrade:
            if ideal == "opus":
                recommendation = "sonnet"
            elif ideal == "sonnet":
                recommendation = "haiku"

        return {
            "currentTier": capacity["tier"],
            "utilization": round(utilization * 100, 1),
            "idealModel": ideal,
            "recommendedModel": recommendation,
            "shouldSwitch": recommendation != ideal,
            "reason": f"{'High utilization' if should_downgrade else 'Low utilization' if should_upgrade else 'Normal capacity'}"
        }

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

    def _load_capacity_snapshots(self, hours: int) -> List[Dict]:
        """Load recent capacity snapshots."""
        if not self.capacity_log.exists():
            return []

        cutoff = datetime.now() - timedelta(hours=hours)
        snapshots = []

        with open(self.capacity_log) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    snapshot = json.loads(line)
                    ts = datetime.fromisoformat(
                        snapshot["timestamp"].replace("Z", "+00:00")
                    )
                    if ts >= cutoff:
                        snapshots.append(snapshot)
                except (json.JSONDecodeError, KeyError):
                    continue

        return sorted(snapshots, key=lambda x: x["timestamp"])


if __name__ == "__main__":
    import sys

    predictor = CapacityPredictor()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "remaining":
            result = predictor.predict_remaining()
            print(f"Capacity: {result['tier']} ({result['utilizationPercent']}%)")
            print(f"  {result['tierDescription']}")
            print(f"  Remaining: Opus:{result['remaining']['tasks']['opus']} Sonnet:{result['remaining']['tasks']['sonnet']}")

        elif cmd == "rate":
            hours = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            result = predictor.predict_consumption_rate(hours)
            print(f"Consumption rate: {result['rate']}{result['unit']} (conf: {result['confidence']})")

        elif cmd == "times":
            result = predictor.get_optimal_times()
            print(f"Peak hours: {result['peakHours']}")
            print(f"Remaining today: {result['remainingPeakHours']}")
            print(f"Batch window: {result['batchWindow']}")

        elif cmd == "switch":
            complexity = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
            result = predictor.should_switch_model(complexity)
            print(f"Tier: {result['currentTier']}")
            print(f"Ideal: {result['idealModel']}, Recommended: {result['recommendedModel']}")
            if result['shouldSwitch']:
                print(f"  Switch recommended: {result['reason']}")

    else:
        print("Capacity Predictor - Capacity prediction and timing")
        print("")
        print("Commands:")
        print("  remaining           - Predict remaining capacity")
        print("  rate [hours]        - Consumption rate prediction")
        print("  times               - Optimal times for tasks")
        print("  switch [complexity] - Model switch recommendation")
