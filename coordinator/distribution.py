#!/usr/bin/env python3
"""
Work Distribution - DQ-based task assignment and model selection.

Uses DQ scoring (validity + specificity + correctness) to:
1. Select optimal model for each subtask
2. Estimate costs before execution
3. Prioritize tasks by importance
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


# DQ weights (from ACE Framework)
DQ_WEIGHTS = {
    "validity": 0.4,     # Does the routing make logical sense?
    "specificity": 0.3,  # How precise is the model selection?
    "correctness": 0.3   # Historical accuracy of similar queries
}

# Complexity thresholds for model selection
COMPLEXITY_THRESHOLDS = {
    "haiku": {"min": 0.0, "max": 0.30},
    "sonnet": {"min": 0.30, "max": 0.70},
    "opus": {"min": 0.70, "max": 1.0}
}

# Cost per million tokens (approximate)
COST_PER_MTOK = {
    "haiku": {"input": 0.25, "output": 1.25},
    "sonnet": {"input": 3.0, "output": 15.0},
    "opus": {"input": 5.0, "output": 25.0}
}

# Model capabilities
MODEL_CAPABILITIES = {
    "haiku": {
        "strengths": ["quick answers", "simple tasks", "formatting", "short responses", "read-only exploration"],
        "weaknesses": ["complex reasoning", "long context", "code generation", "architecture"],
        "best_for": ["explore", "read", "search", "simple review"]
    },
    "sonnet": {
        "strengths": ["code generation", "analysis", "moderate reasoning", "balanced tasks"],
        "weaknesses": ["expert-level problems", "novel architecture", "research synthesis"],
        "best_for": ["implement", "refactor", "debug", "test", "review"]
    },
    "opus": {
        "strengths": ["complex reasoning", "novel problems", "architecture", "research", "expert tasks"],
        "weaknesses": ["cost", "latency for simple tasks"],
        "best_for": ["architecture", "research", "complex design", "multi-step planning"]
    }
}


@dataclass
class TaskAssignment:
    """Assignment of a subtask to a model."""
    subtask: str
    model: str
    complexity: float
    dq_score: float
    cost_estimate: float
    priority: int  # Lower is higher priority
    agent_type: str
    files: List[str]
    lock_type: str


class WorkDistributor:
    """
    Distributes work across agents using DQ-based scoring.
    """

    def __init__(self, baselines_path: str = None):
        self.baselines = self._load_baselines(baselines_path)

    def _load_baselines(self, path: str = None) -> Dict:
        """Load baselines configuration."""
        if path is None:
            path = Path.home() / ".claude" / "kernel" / "baselines.json"
        else:
            path = Path(path)

        if path.exists():
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                pass

        return {}

    def estimate_complexity(self, subtask: str, context: str = "") -> float:
        """
        Estimate task complexity (0-1).

        Factors:
        - Task length and structure
        - Keywords indicating complexity
        - File operations (write > read)
        - Number of files involved
        """
        text = f"{subtask} {context}".lower()
        score = 0.3  # Base

        # High complexity indicators
        high_keywords = [
            "architecture", "design", "refactor", "rewrite", "optimize",
            "complex", "system", "framework", "integrate", "migrate",
            "security", "performance", "scalable", "distributed"
        ]
        for kw in high_keywords:
            if kw in text:
                score += 0.1

        # Medium complexity indicators
        medium_keywords = [
            "implement", "create", "build", "add", "modify", "update",
            "fix", "debug", "test", "analyze", "review"
        ]
        for kw in medium_keywords:
            if kw in text:
                score += 0.05

        # Low complexity indicators (reduce score)
        low_keywords = [
            "read", "find", "search", "list", "check", "show",
            "simple", "quick", "basic", "minor"
        ]
        for kw in low_keywords:
            if kw in text:
                score -= 0.05

        # File operation complexity
        if any(op in text for op in ["write", "edit", "create file", "modify"]):
            score += 0.1
        if any(op in text for op in ["multiple files", "several files", "across files"]):
            score += 0.1

        return max(0.0, min(1.0, score))

    def select_model(self, complexity: float, task_type: str = None) -> str:
        """
        Select optimal model based on complexity and task type.

        Args:
            complexity: Task complexity score (0-1)
            task_type: Optional task type hint

        Returns:
            Model name: "haiku", "sonnet", or "opus"
        """
        # Task type overrides
        if task_type:
            for model, caps in MODEL_CAPABILITIES.items():
                if task_type.lower() in caps["best_for"]:
                    # Still consider complexity for upgrades
                    if complexity > COMPLEXITY_THRESHOLDS[model]["max"]:
                        continue
                    return model

        # Complexity-based selection
        for model, thresholds in COMPLEXITY_THRESHOLDS.items():
            if thresholds["min"] <= complexity < thresholds["max"]:
                return model

        return "opus" if complexity >= 0.7 else "sonnet"

    def estimate_cost(self, subtask: str, model: str, estimated_tokens: int = None) -> float:
        """
        Estimate cost for a subtask.

        Args:
            subtask: Task description
            model: Selected model
            estimated_tokens: Optional token estimate

        Returns:
            Estimated cost in dollars
        """
        if estimated_tokens is None:
            # Estimate based on task length
            words = len(subtask.split())
            # Rough estimate: 100 words = 150 tokens input, 500 tokens output
            input_tokens = max(150, words * 1.5) + 1000  # Base context
            output_tokens = max(500, words * 5)
        else:
            input_tokens = estimated_tokens * 0.3
            output_tokens = estimated_tokens * 0.7

        costs = COST_PER_MTOK.get(model, COST_PER_MTOK["sonnet"])

        input_cost = (input_tokens / 1_000_000) * costs["input"]
        output_cost = (output_tokens / 1_000_000) * costs["output"]

        return input_cost + output_cost

    def calculate_dq_score(self, subtask: str, model: str, complexity: float) -> float:
        """
        Calculate DQ score for a task-model assignment.

        DQ = validity (40%) + specificity (30%) + correctness (30%)
        """
        # Validity: Does model match task complexity?
        thresholds = COMPLEXITY_THRESHOLDS[model]
        if thresholds["min"] <= complexity < thresholds["max"]:
            validity = 1.0
        elif abs(complexity - (thresholds["min"] + thresholds["max"]) / 2) < 0.15:
            validity = 0.7  # Close enough
        else:
            validity = 0.4  # Mismatch

        # Specificity: How well-defined is the task?
        specificity = 0.5  # Base
        if len(subtask) > 50:
            specificity += 0.2
        if any(word in subtask.lower() for word in ["specifically", "exactly", "only"]):
            specificity += 0.15
        if any(word in subtask.lower() for word in ["maybe", "perhaps", "might"]):
            specificity -= 0.15
        specificity = max(0.0, min(1.0, specificity))

        # Correctness: Historical accuracy (use baselines if available)
        correctness = self.baselines.get("model_accuracy", {}).get(model, 0.7)

        # Calculate weighted DQ
        dq = (
            validity * DQ_WEIGHTS["validity"] +
            specificity * DQ_WEIGHTS["specificity"] +
            correctness * DQ_WEIGHTS["correctness"]
        )

        return round(dq, 3)

    def assign(self, subtasks: List[Dict]) -> List[TaskAssignment]:
        """
        Assign models to subtasks.

        Args:
            subtasks: List of subtask dicts with:
                - subtask: Description
                - files: Optional list of files
                - lock_type: "read" or "write"
                - agent_type: Optional type hint
                - priority: Optional priority (lower = higher)

        Returns:
            List of TaskAssignment objects
        """
        assignments = []

        for i, task in enumerate(subtasks):
            subtask = task.get("subtask", "")
            files = task.get("files", [])
            lock_type = task.get("lock_type", "read")
            agent_type = task.get("agent_type", "general-purpose")
            priority = task.get("priority", i)

            # Estimate complexity
            complexity = self.estimate_complexity(subtask)

            # Adjust complexity based on lock type
            if lock_type == "write":
                complexity = min(1.0, complexity + 0.1)

            # Select model
            model = self.select_model(complexity, agent_type)

            # Calculate DQ score
            dq_score = self.calculate_dq_score(subtask, model, complexity)

            # Estimate cost
            cost = self.estimate_cost(subtask, model)

            assignments.append(TaskAssignment(
                subtask=subtask,
                model=model,
                complexity=complexity,
                dq_score=dq_score,
                cost_estimate=cost,
                priority=priority,
                agent_type=agent_type,
                files=files,
                lock_type=lock_type
            ))

        # Sort by priority
        assignments.sort(key=lambda a: a.priority)

        return assignments

    def estimate_total_cost(self, assignments: List[TaskAssignment]) -> Dict:
        """
        Calculate total estimated cost for all assignments.

        Returns:
            {
                "total": float,
                "by_model": {"haiku": float, ...},
                "agent_count": int
            }
        """
        total = 0.0
        by_model = {"haiku": 0.0, "sonnet": 0.0, "opus": 0.0}

        for a in assignments:
            total += a.cost_estimate
            by_model[a.model] = by_model.get(a.model, 0.0) + a.cost_estimate

        return {
            "total": round(total, 4),
            "by_model": {k: round(v, 4) for k, v in by_model.items()},
            "agent_count": len(assignments)
        }

    def optimize_for_cost(self, assignments: List[TaskAssignment], budget: float) -> List[TaskAssignment]:
        """
        Optimize assignments to fit within a budget.

        Downgrades models where possible while maintaining quality.
        """
        optimized = []
        remaining_budget = budget

        for a in assignments:
            if a.cost_estimate <= remaining_budget:
                optimized.append(a)
                remaining_budget -= a.cost_estimate
            else:
                # Try downgrading model
                if a.model == "opus":
                    new_cost = self.estimate_cost(a.subtask, "sonnet")
                    if new_cost <= remaining_budget:
                        a.model = "sonnet"
                        a.cost_estimate = new_cost
                        a.dq_score = self.calculate_dq_score(a.subtask, "sonnet", a.complexity)
                        optimized.append(a)
                        remaining_budget -= new_cost
                        continue

                if a.model in ["opus", "sonnet"]:
                    new_cost = self.estimate_cost(a.subtask, "haiku")
                    if new_cost <= remaining_budget:
                        a.model = "haiku"
                        a.cost_estimate = new_cost
                        a.dq_score = self.calculate_dq_score(a.subtask, "haiku", a.complexity)
                        optimized.append(a)
                        remaining_budget -= new_cost

        return optimized


def decompose_task(task: str) -> List[Dict]:
    """
    Decompose a complex task into subtasks.

    This is a simple heuristic decomposition. For better results,
    use an LLM to analyze and decompose the task.
    """
    subtasks = []

    # Look for common patterns
    task_lower = task.lower()

    # Research phase
    if any(kw in task_lower for kw in ["understand", "analyze", "explore", "find", "investigate"]):
        subtasks.append({
            "subtask": f"Research and explore: {task}",
            "agent_type": "Explore",
            "lock_type": "read",
            "priority": 0
        })

    # Implementation
    if any(kw in task_lower for kw in ["implement", "create", "add", "build", "write"]):
        subtasks.append({
            "subtask": f"Implement: {task}",
            "agent_type": "general-purpose",
            "lock_type": "write",
            "priority": 1
        })

    # Testing
    if any(kw in task_lower for kw in ["test", "verify", "check"]):
        subtasks.append({
            "subtask": f"Test and verify: {task}",
            "agent_type": "general-purpose",
            "lock_type": "read",
            "priority": 2
        })

    # Review
    subtasks.append({
        "subtask": f"Review changes for: {task}",
        "agent_type": "Explore",
        "lock_type": "read",
        "priority": 3
    })

    # If no specific subtasks, create a generic one
    if len(subtasks) == 1:  # Only review
        subtasks.insert(0, {
            "subtask": task,
            "agent_type": "general-purpose",
            "lock_type": "read",
            "priority": 0
        })

    return subtasks


# CLI interface
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Work Distribution CLI")
    parser.add_argument("action", choices=["analyze", "decompose", "cost"])
    parser.add_argument("--task", "-t", help="Task description")
    parser.add_argument("--budget", "-b", type=float, default=1.0, help="Cost budget")

    args = parser.parse_args()

    distributor = WorkDistributor()

    if args.action == "analyze" and args.task:
        complexity = distributor.estimate_complexity(args.task)
        model = distributor.select_model(complexity)
        cost = distributor.estimate_cost(args.task, model)
        dq = distributor.calculate_dq_score(args.task, model, complexity)

        print(f"Task: {args.task[:50]}...")
        print(f"Complexity: {complexity:.2f}")
        print(f"Recommended model: {model}")
        print(f"Estimated cost: ${cost:.4f}")
        print(f"DQ Score: {dq:.3f}")

    elif args.action == "decompose" and args.task:
        subtasks = decompose_task(args.task)
        assignments = distributor.assign(subtasks)

        print(f"Decomposed into {len(assignments)} subtasks:")
        for a in assignments:
            print(f"\n  [{a.priority}] {a.subtask[:60]}...")
            print(f"      Model: {a.model} | DQ: {a.dq_score:.3f} | Cost: ${a.cost_estimate:.4f}")

        costs = distributor.estimate_total_cost(assignments)
        print(f"\nTotal estimated cost: ${costs['total']:.4f}")

    elif args.action == "cost" and args.task:
        subtasks = decompose_task(args.task)
        assignments = distributor.assign(subtasks)
        costs = distributor.estimate_total_cost(assignments)

        print(json.dumps(costs, indent=2))

    else:
        print("Usage: distribution.py <analyze|decompose|cost> --task 'your task'")
