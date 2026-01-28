#!/usr/bin/env python3
"""
Model Recommendation Agent

Suggests optimal model selection based on task complexity, budget, and baselines.
Provides DQ-scored analysis for model routing decisions.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


class ModelRecommendationAgent:
    """
    Agent for model selection recommendations.

    Weight in ACE consensus: 0.15
    """

    def __init__(self):
        self.kernel_dir = Path.home() / ".claude" / "kernel"
        self.state_file = self.kernel_dir / "session-state.json"
        self.baselines_file = self.kernel_dir / "session-baselines.json"
        self.stats_cache = Path.home() / ".claude" / "stats-cache.json"

        # Model characteristics
        self.models = {
            "opus": {
                "complexity_range": (0.7, 1.0),
                "cost_weight": 1.0,
                "quality_weight": 1.0,
                "speed_weight": 0.6
            },
            "sonnet": {
                "complexity_range": (0.3, 0.7),
                "cost_weight": 0.3,
                "quality_weight": 0.85,
                "speed_weight": 0.9
            },
            "haiku": {
                "complexity_range": (0.0, 0.3),
                "cost_weight": 0.1,
                "quality_weight": 0.7,
                "speed_weight": 1.0
            }
        }

    def analyze(self, context: Dict = None) -> Dict:
        """
        Analyze and recommend optimal model.

        Returns:
            DQ-scored analysis result
        """
        state = self._load_state()
        baselines = self._load_baselines()
        stats = self._load_stats_cache()

        # Get current context
        budget = state.get("budget", {})
        capacity = state.get("capacity", {})
        window = state.get("window", {})

        # Determine current task complexity (from context or default)
        task_complexity = context.get("complexity", 0.5) if context else 0.5

        # Calculate recommendation
        recommendation, confidence = self._recommend_model(
            task_complexity, budget, capacity, window, baselines
        )

        # Check for switch recommendations
        current_model = context.get("currentModel", "sonnet") if context else "sonnet"
        switch_rec = self._should_switch(current_model, recommendation, capacity)

        # Historical performance
        performance = self._analyze_model_performance(stats)

        # Cost optimization opportunities
        cost_savings = self._calculate_cost_savings(stats, baselines)

        # Calculate DQ scores
        validity = 0.85 if budget.get("utilized") else 0.5
        specificity = confidence
        correctness = 0.8 if recommendation != "unknown" else 0.4

        return {
            "summary": f"Recommended: {recommendation} (conf: {confidence:.0%}) | Switch: {switch_rec['action']}",
            "dq_score": {
                "validity": validity,
                "specificity": specificity,
                "correctness": correctness
            },
            "confidence": confidence,
            "data": {
                "recommendation": recommendation,
                "recommendationConfidence": confidence,
                "taskComplexity": task_complexity,
                "switchRecommendation": switch_rec,
                "modelPerformance": performance,
                "costSavings": cost_savings,
                "capacityStatus": {
                    "opus": capacity.get("remaining", {}).get("opus", 0),
                    "sonnet": capacity.get("remaining", {}).get("sonnet", 0),
                    "haiku": capacity.get("remaining", {}).get("haiku", 0)
                },
                "recommendations": self._generate_recommendations(
                    recommendation, switch_rec, performance, cost_savings
                )
            }
        }

    def _recommend_model(
        self,
        complexity: float,
        budget: Dict,
        capacity: Dict,
        window: Dict,
        baselines: Dict
    ) -> Tuple[str, float]:
        """Recommend optimal model for given context."""
        remaining = capacity.get("remaining", {})
        thresholds = baselines.get("budgetThresholds", {})

        # Base recommendation from complexity
        if complexity >= 0.7:
            base_rec = "opus"
        elif complexity >= 0.3:
            base_rec = "sonnet"
        else:
            base_rec = "haiku"

        # Check capacity constraints
        if base_rec == "opus" and remaining.get("opus", 0) <= 0:
            # Downgrade if no Opus capacity
            base_rec = "sonnet"

        if base_rec == "sonnet" and remaining.get("sonnet", 0) <= 0:
            base_rec = "haiku"

        # Check budget utilization
        utilization = budget.get("utilizationPercent", 0) / 100
        downgrade_threshold = thresholds.get("downgradeThreshold", 0.85)

        if utilization > downgrade_threshold:
            # Budget pressure - recommend cheaper model
            if base_rec == "opus":
                base_rec = "sonnet"
            elif base_rec == "sonnet":
                base_rec = "haiku"

        # Check window position (late in window = cheaper models)
        position = window.get("positionPercent", 0)
        if position > 80 and base_rec == "opus":
            base_rec = "sonnet"

        # Calculate confidence
        confidence = self._calculate_confidence(
            base_rec, complexity, remaining, utilization
        )

        return base_rec, confidence

    def _calculate_confidence(
        self,
        model: str,
        complexity: float,
        remaining: Dict,
        utilization: float
    ) -> float:
        """Calculate confidence in recommendation."""
        model_info = self.models.get(model, {})
        comp_range = model_info.get("complexity_range", (0, 1))

        # Check if complexity matches model's sweet spot
        if comp_range[0] <= complexity <= comp_range[1]:
            complexity_fit = 0.9
        else:
            complexity_fit = 0.6

        # Check capacity availability
        model_capacity = remaining.get(model, 0)
        if model_capacity > 5:
            capacity_confidence = 0.9
        elif model_capacity > 0:
            capacity_confidence = 0.7
        else:
            capacity_confidence = 0.3

        # Budget pressure factor
        budget_confidence = 1.0 - utilization * 0.3

        return round(
            complexity_fit * 0.4 +
            capacity_confidence * 0.4 +
            budget_confidence * 0.2,
            2
        )

    def _should_switch(
        self, current: str, recommended: str, capacity: Dict
    ) -> Dict:
        """Determine if model switch is recommended."""
        if current == recommended:
            return {
                "action": "maintain",
                "reason": "Current model is optimal"
            }

        remaining = capacity.get("remaining", {})

        # Check if switch is possible
        rec_capacity = remaining.get(recommended, 0)
        if rec_capacity <= 0:
            return {
                "action": "wait",
                "reason": f"No {recommended} capacity available"
            }

        # Determine urgency
        current_tier = {"opus": 3, "sonnet": 2, "haiku": 1}.get(current, 2)
        rec_tier = {"opus": 3, "sonnet": 2, "haiku": 1}.get(recommended, 2)

        if rec_tier > current_tier:
            return {
                "action": "upgrade",
                "from": current,
                "to": recommended,
                "reason": "Task complexity warrants upgrade"
            }
        else:
            return {
                "action": "downgrade",
                "from": current,
                "to": recommended,
                "reason": "Cost optimization opportunity"
            }

    def _analyze_model_performance(self, stats: Dict) -> Dict:
        """Analyze historical model performance."""
        model_usage = stats.get("modelUsage", {})

        performance = {}
        for model in ["opus", "sonnet", "haiku"]:
            usage = model_usage.get(model, {})
            performance[model] = {
                "count": usage.get("count", 0),
                "avgTokens": usage.get("avgTokens", 0),
                "successRate": usage.get("successRate", 0.95)
            }

        return performance

    def _calculate_cost_savings(self, stats: Dict, baselines: Dict) -> Dict:
        """Calculate potential cost savings from optimal routing."""
        model_usage = stats.get("modelUsage", {})

        # Estimate current cost
        opus_count = model_usage.get("opus", {}).get("count", 0)
        sonnet_count = model_usage.get("sonnet", {}).get("count", 0)
        haiku_count = model_usage.get("haiku", {}).get("count", 0)

        # Cost weights (relative)
        current_cost = opus_count * 1.0 + sonnet_count * 0.3 + haiku_count * 0.1

        # Optimal cost (assuming 20% of Opus could be Sonnet, etc.)
        optimal_opus = opus_count * 0.8
        optimal_sonnet = sonnet_count + opus_count * 0.2
        optimal_cost = optimal_opus * 1.0 + optimal_sonnet * 0.3 + haiku_count * 0.1

        savings_percent = ((current_cost - optimal_cost) / current_cost * 100) if current_cost > 0 else 0

        return {
            "currentCostIndex": round(current_cost, 2),
            "optimalCostIndex": round(optimal_cost, 2),
            "savingsPercent": round(savings_percent, 1),
            "opportunity": savings_percent > 10
        }

    def _generate_recommendations(
        self,
        model: str,
        switch: Dict,
        performance: Dict,
        savings: Dict
    ) -> List[str]:
        """Generate model recommendations."""
        recommendations = []

        # Switch recommendation
        if switch["action"] == "upgrade":
            recommendations.append(
                f"Upgrade to {switch['to']} for current task complexity"
            )
        elif switch["action"] == "downgrade":
            recommendations.append(
                f"Downgrade to {switch['to']} to optimize costs"
            )

        # Savings opportunity
        if savings.get("opportunity"):
            recommendations.append(
                f"Potential {savings['savingsPercent']}% cost savings with better routing"
            )

        # Model-specific advice
        if model == "opus":
            recommendations.append("Reserve Opus for architecture and complex reasoning")
        elif model == "sonnet":
            recommendations.append("Good balance of quality and cost")
        else:
            recommendations.append("Use for quick queries and simple tasks")

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
    agent = ModelRecommendationAgent()
    result = agent.analyze()
    print(json.dumps(result, indent=2))
