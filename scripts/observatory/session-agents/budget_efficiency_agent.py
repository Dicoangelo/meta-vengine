#!/usr/bin/env python3
"""
Budget Efficiency Agent

Analyzes token utilization and waste patterns.
Provides DQ-scored analysis of budget efficiency.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List


class BudgetEfficiencyAgent:
    """
    Agent for analyzing budget efficiency.

    Weight in ACE consensus: 0.18
    """

    def __init__(self):
        self.data_dir = Path.home() / ".claude" / "data"
        self.kernel_dir = Path.home() / ".claude" / "kernel"
        self.state_file = self.kernel_dir / "session-state.json"
        self.baselines_file = self.kernel_dir / "session-baselines.json"
        self.stats_cache = Path.home() / ".claude" / "stats-cache.json"

    def analyze(self, context: Dict = None) -> Dict:
        """
        Analyze budget efficiency.

        Returns:
            DQ-scored analysis result
        """
        state = self._load_state()
        baselines = self._load_baselines()
        stats = self._load_stats_cache()

        budget = state.get("budget", {})
        used = budget.get("used", {})
        allocated = budget.get("allocated", {})

        # Calculate efficiency metrics
        total_used = sum(used.values())
        total_allocated = sum(v for k, v in allocated.items() if k != "reserve")

        utilization = total_used / total_allocated if total_allocated > 0 else 0

        # Calculate waste (allocated but not used efficiently)
        opus_efficiency = self._calculate_model_efficiency("opus", used, allocated, stats)
        sonnet_efficiency = self._calculate_model_efficiency("sonnet", used, allocated, stats)
        haiku_efficiency = self._calculate_model_efficiency("haiku", used, allocated, stats)

        # Detect waste patterns
        waste_patterns = self._detect_waste_patterns(state, stats)

        # Overall efficiency score
        efficiency_score = (
            opus_efficiency * 0.4 +
            sonnet_efficiency * 0.35 +
            haiku_efficiency * 0.25
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            efficiency_score, waste_patterns, baselines
        )

        # Calculate DQ scores
        validity = 0.85 if total_allocated > 0 else 0.3
        specificity = min(0.9, 0.5 + efficiency_score * 0.4)
        correctness = 0.8 if len(waste_patterns) < 3 else 0.6

        return {
            "summary": f"Budget efficiency: {efficiency_score*100:.0f}% | {len(waste_patterns)} waste patterns",
            "dq_score": {
                "validity": validity,
                "specificity": specificity,
                "correctness": correctness
            },
            "confidence": efficiency_score,
            "data": {
                "utilization": round(utilization, 3),
                "efficiencyScore": round(efficiency_score, 3),
                "modelEfficiency": {
                    "opus": round(opus_efficiency, 3),
                    "sonnet": round(sonnet_efficiency, 3),
                    "haiku": round(haiku_efficiency, 3)
                },
                "wastePatterns": waste_patterns,
                "recommendations": recommendations,
                "used": used,
                "allocated": allocated
            }
        }

    def _calculate_model_efficiency(
        self, model: str, used: Dict, allocated: Dict, stats: Dict
    ) -> float:
        """Calculate efficiency for a specific model."""
        model_used = used.get(model, 0)
        model_allocated = allocated.get(model, 0)

        if model_allocated == 0:
            return 1.0  # No allocation, no waste

        usage_ratio = model_used / model_allocated

        # Check if usage matches complexity requirements
        model_usage = stats.get("modelUsage", {})
        model_stats = model_usage.get(model, {})

        # Efficiency = usage ratio * quality factor
        quality_factor = 1.0
        if model == "opus":
            # Opus should be used for complex tasks
            # If used frequently for simple tasks, lower efficiency
            quality_factor = 0.9  # Default good
        elif model == "sonnet":
            quality_factor = 0.85
        else:
            quality_factor = 0.8

        return min(1.0, usage_ratio * quality_factor)

    def _detect_waste_patterns(self, state: Dict, stats: Dict) -> List[Dict]:
        """Detect budget waste patterns."""
        patterns = []
        budget = state.get("budget", {})

        # Pattern 1: Over-allocation
        utilization = budget.get("utilizationPercent", 0)
        if utilization < 50:
            patterns.append({
                "type": "under_utilization",
                "severity": "medium",
                "description": f"Only {utilization}% of budget utilized",
                "suggestion": "Consider reducing allocations or using more capacity"
            })

        # Pattern 2: Opus for simple tasks
        model_usage = stats.get("modelUsage", {})
        opus_count = model_usage.get("opus", {}).get("count", 0)
        total_count = sum(m.get("count", 0) for m in model_usage.values())

        if total_count > 0 and opus_count / total_count > 0.5:
            patterns.append({
                "type": "opus_overuse",
                "severity": "high",
                "description": f"Opus used for {opus_count/total_count*100:.0f}% of tasks",
                "suggestion": "Route simpler tasks to Sonnet/Haiku"
            })

        # Pattern 3: Reserve not used
        reserve = budget.get("allocated", {}).get("reserve", 0)
        remaining = state.get("capacity", {}).get("remaining", {}).get("opus", 0)

        if reserve > 0 and remaining > reserve * 0.8:
            patterns.append({
                "type": "unused_reserve",
                "severity": "low",
                "description": "Reserve budget largely unused",
                "suggestion": "Consider reallocating reserve to active use"
            })

        return patterns

    def _generate_recommendations(
        self, efficiency: float, patterns: List[Dict], baselines: Dict
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        if efficiency < 0.6:
            recommendations.append("Review task-to-model routing strategy")

        for pattern in patterns:
            if pattern["type"] == "opus_overuse":
                recommendations.append("Increase Sonnet usage for moderate complexity tasks")
            elif pattern["type"] == "under_utilization":
                recommendations.append("Consider batching tasks to improve utilization")
            elif pattern["type"] == "unused_reserve":
                recommendations.append("Use reserve for end-of-window complex tasks")

        if not recommendations:
            recommendations.append("Budget efficiency is healthy - maintain current patterns")

        return recommendations

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

    def _load_stats_cache(self) -> Dict:
        """Load stats cache."""
        if self.stats_cache.exists():
            with open(self.stats_cache) as f:
                return json.load(f)
        return {}


if __name__ == "__main__":
    agent = BudgetEfficiencyAgent()
    result = agent.analyze()
    print(json.dumps(result, indent=2))
