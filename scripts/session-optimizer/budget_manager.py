#!/usr/bin/env python3
"""
Budget Manager - Token budget allocation and tracking

Integrates with subscription-tracker.js to:
- Track token usage by model
- Allocate budget across models
- Recommend model switches based on budget
- Reserve capacity for high-priority tasks
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Import centralized pricing
sys.path.insert(0, str(Path.home() / ".claude/config"))
from pricing import PRICING


class BudgetManager:
    """Manages token budget allocation and tracking."""

    def __init__(self):
        self.kernel_dir = Path.home() / ".claude" / "kernel"
        self.state_file = self.kernel_dir / "session-state.json"
        self.baselines_file = self.kernel_dir / "session-baselines.json"
        self.stats_cache = Path.home() / ".claude" / "stats-cache.json"
        self.subscription_tracker = self.kernel_dir / "subscription-tracker.js"

        # Model costs from centralized config
        self.model_costs = {
            model: {"input": data["input"], "output": data["output"]}
            for model, data in PRICING.items()
        }

        # Average tokens per task by complexity
        self.task_token_estimates = {
            "opus": 200000,    # ~200k per Opus task
            "sonnet": 50000,   # ~50k per Sonnet task
            "haiku": 10000     # ~10k per Haiku task
        }

    def get_current_usage(self) -> Dict:
        """
        Get current token usage from stats-cache.json.
        """
        if not self.stats_cache.exists():
            return {"opus": 0, "sonnet": 0, "haiku": 0, "total": 0}

        with open(self.stats_cache) as f:
            stats = json.load(f)

        usage = {"opus": 0, "sonnet": 0, "haiku": 0}

        for model, data in stats.get("modelUsage", {}).items():
            tokens = (data.get("inputTokens", 0) + data.get("outputTokens", 0))

            if "opus" in model.lower():
                usage["opus"] += tokens
            elif "sonnet" in model.lower():
                usage["sonnet"] += tokens
            else:
                usage["haiku"] += tokens

        usage["total"] = sum(usage.values())
        return usage

    def get_budget_status(self) -> Dict:
        """
        Get comprehensive budget status.
        """
        state = self._load_state()
        usage = self.get_current_usage()
        baselines = self._load_baselines()

        budget = state.get("budget", {})
        capacity = budget.get("windowCapacity", 5000000)

        # Calculate utilization
        utilization = (usage["total"] / capacity * 100) if capacity > 0 else 0

        # Determine recommended model
        thresholds = baselines.get("budgetThresholds", {})
        downgrade_at = thresholds.get("downgradeThreshold", 0.85)

        if utilization >= downgrade_at * 100:
            recommended = "haiku"
        elif utilization >= 50:
            recommended = "sonnet"
        else:
            recommended = "opus"

        # Calculate remaining tasks
        remaining_budget = capacity - usage["total"]
        remaining_tasks = {
            "opus": max(0, int(remaining_budget / self.task_token_estimates["opus"])),
            "sonnet": max(0, int(remaining_budget / self.task_token_estimates["sonnet"])),
            "haiku": max(0, int(remaining_budget / self.task_token_estimates["haiku"]))
        }

        return {
            "usage": usage,
            "capacity": capacity,
            "utilizationPercent": round(utilization, 1),
            "recommendedModel": recommended,
            "remainingTasks": remaining_tasks,
            "remainingBudget": remaining_budget
        }

    def reserve_opus(self, count: int) -> bool:
        """
        Reserve budget for a specific number of Opus tasks.
        """
        status = self.get_budget_status()
        needed = count * self.task_token_estimates["opus"]

        if status["remainingBudget"] < needed:
            return False

        # Update allocation in state
        state = self._load_state()
        state["budget"]["allocated"]["reserve"] = needed
        self._save_state(state)

        return True

    def simulate_usage(self, tasks: list) -> Dict:
        """
        Simulate budget usage for planned tasks.

        Args:
            tasks: List of {"model": str, "count": int} dicts
        """
        status = self.get_budget_status()
        simulated_usage = status["usage"]["total"]

        task_costs = []
        for task in tasks:
            model = task.get("model", "sonnet")
            count = task.get("count", 1)
            tokens = self.task_token_estimates.get(model, 50000) * count
            simulated_usage += tokens
            task_costs.append({"model": model, "count": count, "tokens": tokens})

        projected_utilization = (simulated_usage / status["capacity"] * 100)

        return {
            "currentUsage": status["usage"]["total"],
            "simulatedUsage": simulated_usage,
            "taskCosts": task_costs,
            "projectedUtilization": round(projected_utilization, 1),
            "wouldExceedBudget": simulated_usage > status["capacity"]
        }

    def get_model_recommendation(self, complexity: float) -> str:
        """
        Recommend model based on task complexity and budget.

        Args:
            complexity: Task complexity score (0.0-1.0)
        """
        status = self.get_budget_status()

        # Complexity-based ideal model
        if complexity >= 0.7:
            ideal = "opus"
        elif complexity >= 0.3:
            ideal = "sonnet"
        else:
            ideal = "haiku"

        # Check if we can afford ideal model
        if status["remainingTasks"][ideal] >= 1:
            return ideal

        # Fall back to cheaper model
        if ideal == "opus" and status["remainingTasks"]["sonnet"] >= 1:
            return "sonnet"

        return "haiku"

    def calculate_api_equivalent(self) -> Dict:
        """
        Calculate API equivalent cost of current usage.
        """
        usage = self.get_current_usage()

        api_cost = 0
        for model, tokens in usage.items():
            if model == "total":
                continue
            if model in self.model_costs:
                # Assume 30% input, 70% output distribution
                input_tokens = tokens * 0.3 / 1_000_000
                output_tokens = tokens * 0.7 / 1_000_000
                api_cost += (
                    input_tokens * self.model_costs[model]["input"] +
                    output_tokens * self.model_costs[model]["output"]
                )

        subscription_rate = 200  # $200/month Claude Max

        return {
            "apiEquivalent": round(api_cost, 2),
            "subscriptionRate": subscription_rate,
            "savings": round(api_cost - subscription_rate, 2) if api_cost > subscription_rate else 0,
            "multiplier": round(api_cost / subscription_rate, 1) if subscription_rate > 0 else 0
        }

    def _load_state(self) -> Dict:
        """Load session state."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {}

    def _save_state(self, state: Dict):
        """Save session state."""
        state["lastUpdated"] = datetime.now().isoformat()
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def _load_baselines(self) -> Dict:
        """Load session baselines."""
        if self.baselines_file.exists():
            with open(self.baselines_file) as f:
                return json.load(f)
        return {}


if __name__ == "__main__":
    import sys

    manager = BudgetManager()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "status":
            status = manager.get_budget_status()
            print(f"Budget Status:")
            print(f"  Utilization: {status['utilizationPercent']}%")
            print(f"  Recommended: {status['recommendedModel']}")
            print(f"  Remaining:")
            for model, count in status['remainingTasks'].items():
                print(f"    {model}: {count} tasks")

        elif cmd == "usage":
            usage = manager.get_current_usage()
            print(json.dumps(usage, indent=2))

        elif cmd == "reserve":
            if len(sys.argv) > 2:
                count = int(sys.argv[2])
                if manager.reserve_opus(count):
                    print(f"Reserved {count} Opus tasks")
                else:
                    print("Insufficient budget")
            else:
                print("Usage: budget_manager.py reserve <count>")

        elif cmd == "simulate":
            # Example: simulate 2 opus + 5 sonnet tasks
            tasks = [
                {"model": "opus", "count": 2},
                {"model": "sonnet", "count": 5}
            ]
            result = manager.simulate_usage(tasks)
            print(json.dumps(result, indent=2))

        elif cmd == "recommend":
            if len(sys.argv) > 2:
                complexity = float(sys.argv[2])
                rec = manager.get_model_recommendation(complexity)
                print(f"Recommended: {rec}")
            else:
                print("Usage: budget_manager.py recommend <complexity>")

        elif cmd == "api-value":
            value = manager.calculate_api_equivalent()
            print(f"API Equivalent: ${value['apiEquivalent']}")
            print(f"Multiplier: {value['multiplier']}x")

    else:
        print("Budget Manager - Token budget allocation")
        print("")
        print("Commands:")
        print("  status              - Current budget status")
        print("  usage               - Token usage by model")
        print("  reserve <count>     - Reserve Opus tasks")
        print("  simulate            - Simulate task costs")
        print("  recommend <complex> - Get model recommendation")
        print("  api-value           - Calculate API equivalent")
