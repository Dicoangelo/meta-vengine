#!/usr/bin/env python3
"""
Capacity Forecast Agent

Predicts remaining capacity and consumption rates.
Provides DQ-scored analysis of capacity outlook.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple


class CapacityForecastAgent:
    """
    Agent for forecasting session capacity.

    Weight in ACE consensus: 0.17
    """

    def __init__(self):
        self.data_dir = Path.home() / ".claude" / "data"
        self.kernel_dir = Path.home() / ".claude" / "kernel"
        self.state_file = self.kernel_dir / "session-state.json"
        self.baselines_file = self.kernel_dir / "session-baselines.json"
        self.activity_file = self.data_dir / "activity-events.jsonl"

    def analyze(self, context: Dict = None) -> Dict:
        """
        Analyze and forecast capacity.

        Returns:
            DQ-scored analysis result
        """
        state = self._load_state()
        baselines = self._load_baselines()

        capacity = state.get("capacity", {})
        window = state.get("window", {})
        budget = state.get("budget", {})

        # Calculate consumption rate
        consumption_rate = self._calculate_consumption_rate()

        # Project remaining capacity
        remaining_minutes = window.get("remainingMinutes", 300)
        projected = self._project_capacity(
            consumption_rate, remaining_minutes, capacity
        )

        # Determine capacity tier
        tier, tier_confidence = self._determine_tier(projected, baselines)

        # Calculate runway (time until exhaustion)
        runway = self._calculate_runway(consumption_rate, capacity)

        # Risk assessment
        risk_level, risk_factors = self._assess_risk(
            tier, runway, remaining_minutes, consumption_rate
        )

        # Calculate DQ scores
        samples = len(self._load_recent_activity(hours=1))
        validity = min(0.9, 0.5 + samples * 0.02)
        specificity = tier_confidence
        correctness = 0.8 if risk_level != "critical" else 0.5

        return {
            "summary": f"Capacity: {tier} | Runway: {runway}m | Risk: {risk_level}",
            "dq_score": {
                "validity": validity,
                "specificity": specificity,
                "correctness": correctness
            },
            "confidence": tier_confidence,
            "data": {
                "tier": tier,
                "tierConfidence": tier_confidence,
                "consumptionRate": consumption_rate,
                "runway": runway,
                "projected": projected,
                "remaining": capacity.get("remaining", {}),
                "riskLevel": risk_level,
                "riskFactors": risk_factors,
                "recommendations": self._generate_recommendations(
                    tier, risk_level, runway, remaining_minutes
                )
            }
        }

    def _calculate_consumption_rate(self) -> Dict:
        """Calculate token consumption rate per hour."""
        activity = self._load_recent_activity(hours=2)

        if not activity:
            return {"tokensPerHour": 0, "tasksPerHour": 0, "confidence": 0.3}

        # Count by hour
        hourly_tokens = {}
        hourly_tasks = {}

        for event in activity:
            ts_val = event.get("timestamp", "")
            if isinstance(ts_val, (int, float)):
                ts = datetime.fromtimestamp(ts_val)
            else:
                ts = datetime.fromisoformat(str(ts_val).replace("Z", "+00:00"))
            hour_key = ts.strftime("%Y-%m-%d-%H")

            tokens = event.get("tokens", {})
            total_tokens = tokens.get("input", 0) + tokens.get("output", 0)

            hourly_tokens[hour_key] = hourly_tokens.get(hour_key, 0) + total_tokens
            hourly_tasks[hour_key] = hourly_tasks.get(hour_key, 0) + 1

        if hourly_tokens:
            avg_tokens = sum(hourly_tokens.values()) / len(hourly_tokens)
            avg_tasks = sum(hourly_tasks.values()) / len(hourly_tasks)
            confidence = min(0.9, 0.5 + len(hourly_tokens) * 0.1)
        else:
            avg_tokens = 0
            avg_tasks = 0
            confidence = 0.3

        return {
            "tokensPerHour": round(avg_tokens),
            "tasksPerHour": round(avg_tasks, 1),
            "confidence": confidence
        }

    def _project_capacity(
        self, rate: Dict, remaining_minutes: int, capacity: Dict
    ) -> Dict:
        """Project capacity at window end."""
        remaining = capacity.get("remaining", {})
        hours_remaining = remaining_minutes / 60

        tokens_to_consume = rate.get("tokensPerHour", 0) * hours_remaining
        tasks_to_consume = rate.get("tasksPerHour", 0) * hours_remaining

        # Estimate model distribution (based on current patterns)
        opus_projected = max(0, remaining.get("opus", 0) - tasks_to_consume * 0.1)
        sonnet_projected = max(0, remaining.get("sonnet", 0) - tasks_to_consume * 0.5)
        haiku_projected = max(0, remaining.get("haiku", 0) - tasks_to_consume * 0.4)

        return {
            "opus": round(opus_projected),
            "sonnet": round(sonnet_projected),
            "haiku": round(haiku_projected),
            "tokensConsumed": round(tokens_to_consume),
            "tasksConsumed": round(tasks_to_consume)
        }

    def _determine_tier(self, projected: Dict, baselines: Dict) -> Tuple[str, float]:
        """Determine capacity tier."""
        opus = projected.get("opus", 0)
        sonnet = projected.get("sonnet", 0)
        haiku = projected.get("haiku", 0)

        total = opus + sonnet + haiku

        if total > 100 and opus > 2:
            return "COMFORTABLE", 0.85
        elif total > 50 and (opus > 1 or sonnet > 20):
            return "MODERATE", 0.75
        elif total > 10:
            return "LOW", 0.70
        else:
            return "CRITICAL", 0.65

    def _calculate_runway(self, rate: Dict, capacity: Dict) -> int:
        """Calculate minutes until capacity exhaustion."""
        remaining = capacity.get("remaining", {})
        total_tasks = sum(remaining.values())

        tasks_per_hour = rate.get("tasksPerHour", 0)
        if tasks_per_hour <= 0:
            return 999  # No consumption, infinite runway

        hours_remaining = total_tasks / tasks_per_hour
        return round(hours_remaining * 60)

    def _assess_risk(
        self, tier: str, runway: int, window_remaining: int, rate: Dict
    ) -> Tuple[str, List[str]]:
        """Assess capacity risk."""
        factors = []

        # Check runway vs window
        if runway < window_remaining:
            factors.append(f"Runway ({runway}m) shorter than window ({window_remaining}m)")

        # Check tier
        if tier == "CRITICAL":
            factors.append("Capacity tier is CRITICAL")
        elif tier == "LOW":
            factors.append("Capacity tier is LOW")

        # Check consumption rate
        if rate.get("tasksPerHour", 0) > 30:
            factors.append(f"High consumption rate: {rate['tasksPerHour']} tasks/hour")

        # Determine risk level
        if tier == "CRITICAL" or runway < window_remaining * 0.3:
            return "critical", factors
        elif tier == "LOW" or runway < window_remaining * 0.6:
            return "elevated", factors
        elif factors:
            return "moderate", factors
        else:
            return "low", []

    def _generate_recommendations(
        self, tier: str, risk: str, runway: int, window_remaining: int
    ) -> List[str]:
        """Generate recommendations based on forecast."""
        recommendations = []

        if risk == "critical":
            recommendations.append("Switch to Haiku for remaining tasks")
            recommendations.append("Prioritize only essential work")
            recommendations.append("Consider waiting for next window")
        elif risk == "elevated":
            recommendations.append("Avoid Opus unless critical")
            recommendations.append("Batch remaining tasks for efficiency")
        elif tier == "LOW":
            recommendations.append("Use Sonnet as primary model")
            recommendations.append("Reserve Opus for complex-only tasks")
        else:
            recommendations.append("Capacity healthy - proceed normally")

        return recommendations

    def _load_recent_activity(self, hours: int = 2) -> List[Dict]:
        """Load recent activity events."""
        if not self.activity_file.exists():
            return []

        cutoff = datetime.now() - timedelta(hours=hours)
        events = []

        with open(self.activity_file) as f:
            for line in f:
                try:
                    event = json.loads(line)
                    ts_val = event.get("timestamp", "")
                    if ts_val:
                        # Handle both int (unix timestamp) and string (ISO format)
                        if isinstance(ts_val, (int, float)):
                            ts = datetime.fromtimestamp(ts_val)
                        else:
                            ts = datetime.fromisoformat(str(ts_val).replace("Z", "+00:00"))
                        if ts >= cutoff:
                            events.append(event)
                except (json.JSONDecodeError, ValueError, OSError):
                    continue

        return events

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
    agent = CapacityForecastAgent()
    result = agent.analyze()
    print(json.dumps(result, indent=2))
