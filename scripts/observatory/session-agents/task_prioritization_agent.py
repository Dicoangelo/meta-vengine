#!/usr/bin/env python3
"""
Task Prioritization Agent

DQ-scores queued work and suggests optimal execution order.
Provides DQ-scored analysis of task priorities.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class TaskPrioritizationAgent:
    """
    Agent for task prioritization using DQ scoring.

    Weight in ACE consensus: 0.15
    """

    def __init__(self):
        self.kernel_dir = Path.home() / ".claude" / "kernel"
        self.state_file = self.kernel_dir / "session-state.json"
        self.queue_file = self.kernel_dir / "task-queue.json"
        self.baselines_file = self.kernel_dir / "session-baselines.json"

        # DQ weights
        self.dq_weights = {
            "validity": 0.4,
            "specificity": 0.3,
            "correctness": 0.3
        }

    def analyze(self, context: Dict = None) -> Dict:
        """
        Analyze task queue and provide prioritization.

        Returns:
            DQ-scored analysis result
        """
        state = self._load_state()
        queue = self._load_queue()
        baselines = self._load_baselines()

        tasks = queue.get("tasks", [])
        pending = [t for t in tasks if t.get("status") == "pending"]

        # Score each task
        scored_tasks = self._score_tasks(pending, state, baselines)

        # Generate execution order
        execution_order = self._generate_execution_order(scored_tasks, state)

        # Identify batching opportunities
        batches = self._identify_batches(scored_tasks)

        # Calculate queue health metrics
        queue_health = self._assess_queue_health(scored_tasks, state)

        # Calculate DQ scores for this analysis
        validity = 0.85 if pending else 0.4
        specificity = min(0.9, 0.5 + len(pending) * 0.05)
        correctness = queue_health.get("healthScore", 0.5)

        return {
            "summary": f"Queue: {len(pending)} tasks | Health: {queue_health['healthScore']*100:.0f}%",
            "dq_score": {
                "validity": validity,
                "specificity": specificity,
                "correctness": correctness
            },
            "confidence": queue_health.get("healthScore", 0.5),
            "data": {
                "pendingCount": len(pending),
                "scoredTasks": scored_tasks[:10],  # Top 10
                "executionOrder": execution_order[:5],  # Next 5
                "batches": batches,
                "queueHealth": queue_health,
                "recommendations": self._generate_recommendations(
                    queue_health, batches, state
                )
            }
        }

    def _score_tasks(
        self, tasks: List[Dict], state: Dict, baselines: Dict
    ) -> List[Dict]:
        """Score tasks using DQ methodology."""
        scored = []
        capacity = state.get("capacity", {}).get("remaining", {})

        for task in tasks:
            # Calculate DQ components
            validity = self._calculate_validity(task)
            specificity = self._calculate_specificity(task)
            correctness = self._calculate_correctness(task, capacity)

            dq_score = (
                validity * self.dq_weights["validity"] +
                specificity * self.dq_weights["specificity"] +
                correctness * self.dq_weights["correctness"]
            )

            # Recommended model based on complexity
            complexity = task.get("complexity", 0.5)
            if complexity >= 0.7:
                recommended_model = "opus"
            elif complexity >= 0.3:
                recommended_model = "sonnet"
            else:
                recommended_model = "haiku"

            # Check if model is available
            model_available = capacity.get(recommended_model, 0) > 0

            scored.append({
                "id": task.get("id"),
                "description": task.get("description", "")[:50],
                "complexity": complexity,
                "priority": task.get("priority", 0.5),
                "dqScore": round(dq_score, 3),
                "dqComponents": {
                    "validity": round(validity, 3),
                    "specificity": round(specificity, 3),
                    "correctness": round(correctness, 3)
                },
                "recommendedModel": recommended_model,
                "modelAvailable": model_available,
                "addedAt": task.get("addedAt")
            })

        # Sort by DQ score
        scored.sort(key=lambda t: t["dqScore"], reverse=True)
        return scored

    def _calculate_validity(self, task: Dict) -> float:
        """Calculate validity score (is task well-defined?)."""
        description = task.get("description", "")

        # Longer descriptions tend to be more valid
        length_score = min(1.0, len(description) / 100)

        # Check for actionable keywords
        actionable_keywords = ["implement", "fix", "add", "create", "update", "refactor"]
        has_action = any(kw in description.lower() for kw in actionable_keywords)
        action_score = 0.3 if has_action else 0

        return min(1.0, 0.4 + length_score * 0.3 + action_score)

    def _calculate_specificity(self, task: Dict) -> float:
        """Calculate specificity score (is task specific enough?)."""
        # Use complexity as proxy for specificity
        complexity = task.get("complexity", 0.5)

        # Higher complexity tasks tend to be more specific
        specificity = 0.4 + complexity * 0.5

        # Bonus for metadata
        if task.get("metadata"):
            specificity += 0.1

        return min(1.0, specificity)

    def _calculate_correctness(self, task: Dict, capacity: Dict) -> float:
        """Calculate correctness score (can task be completed correctly?)."""
        complexity = task.get("complexity", 0.5)

        # Check if appropriate model is available
        if complexity >= 0.7:
            available = capacity.get("opus", 0) > 0
        elif complexity >= 0.3:
            available = capacity.get("sonnet", 0) > 0
        else:
            available = capacity.get("haiku", 0) > 0

        base_score = 0.7 if available else 0.4

        # Lower complexity tasks have higher correctness likelihood
        complexity_factor = 1.0 - complexity * 0.3

        return min(1.0, base_score * complexity_factor)

    def _generate_execution_order(
        self, scored_tasks: List[Dict], state: Dict
    ) -> List[Dict]:
        """Generate optimal execution order."""
        capacity = state.get("capacity", {}).get("remaining", {})

        # Start with highest DQ score tasks that have available capacity
        available_tasks = [
            t for t in scored_tasks if t.get("modelAvailable", False)
        ]

        # If no capacity, return all tasks by DQ score anyway
        if not available_tasks:
            available_tasks = scored_tasks

        order = []
        for task in available_tasks[:5]:
            order.append({
                "taskId": task["id"],
                "description": task["description"],
                "model": task["recommendedModel"],
                "dqScore": task["dqScore"],
                "reason": f"DQ: {task['dqScore']:.2f}, {task['recommendedModel']} available"
            })

        return order

    def _identify_batches(self, scored_tasks: List[Dict]) -> List[Dict]:
        """Identify task batching opportunities."""
        batches = {
            "opus": [],
            "sonnet": [],
            "haiku": []
        }

        for task in scored_tasks:
            model = task.get("recommendedModel", "sonnet")
            batches[model].append(task)

        result = []
        for model, tasks in batches.items():
            if tasks:
                result.append({
                    "model": model,
                    "count": len(tasks),
                    "avgDqScore": round(
                        sum(t["dqScore"] for t in tasks) / len(tasks), 3
                    ),
                    "taskIds": [t["id"] for t in tasks[:5]]
                })

        return result

    def _assess_queue_health(
        self, scored_tasks: List[Dict], state: Dict
    ) -> Dict:
        """Assess overall queue health."""
        if not scored_tasks:
            return {
                "healthScore": 1.0,
                "status": "empty",
                "issues": []
            }

        issues = []
        health_score = 1.0

        # Check for blocked tasks (no capacity)
        blocked = [t for t in scored_tasks if not t.get("modelAvailable")]
        if blocked:
            issues.append(f"{len(blocked)} tasks blocked by capacity")
            health_score -= 0.1 * min(len(blocked), 5)

        # Check for old tasks
        now = datetime.now()
        old_tasks = 0
        for task in scored_tasks:
            added = task.get("addedAt")
            if added:
                try:
                    # Handle both int (unix timestamp) and string (ISO format)
                    if isinstance(added, (int, float)):
                        added_dt = datetime.fromtimestamp(added)
                    else:
                        added_dt = datetime.fromisoformat(str(added).replace("Z", "+00:00"))
                    age_hours = (now - added_dt.replace(tzinfo=None)).total_seconds() / 3600
                    if age_hours > 24:
                        old_tasks += 1
                except (ValueError, OSError):
                    pass

        if old_tasks > 0:
            issues.append(f"{old_tasks} tasks older than 24h")
            health_score -= 0.05 * old_tasks

        # Check queue size
        if len(scored_tasks) > 20:
            issues.append(f"Large queue: {len(scored_tasks)} tasks")
            health_score -= 0.1

        health_score = max(0.1, health_score)

        status = "healthy" if health_score > 0.7 else "degraded" if health_score > 0.4 else "critical"

        return {
            "healthScore": round(health_score, 2),
            "status": status,
            "issues": issues
        }

    def _generate_recommendations(
        self, health: Dict, batches: List[Dict], state: Dict
    ) -> List[str]:
        """Generate prioritization recommendations."""
        recommendations = []

        if health["status"] == "critical":
            recommendations.append("Clear or prioritize queue - too many pending tasks")

        for issue in health.get("issues", []):
            if "blocked" in issue:
                recommendations.append("Wait for capacity or adjust task complexity")
            elif "older" in issue:
                recommendations.append("Review and potentially cancel stale tasks")

        # Batch recommendations
        for batch in batches:
            if batch["count"] >= 3:
                recommendations.append(
                    f"Batch {batch['count']} {batch['model']} tasks together"
                )

        if not recommendations:
            recommendations.append("Queue healthy - execute in DQ order")

        return recommendations

    def _load_state(self) -> Dict:
        """Load session state."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {}

    def _load_queue(self) -> Dict:
        """Load task queue."""
        if self.queue_file.exists():
            with open(self.queue_file) as f:
                return json.load(f)
        return {"tasks": []}

    def _load_baselines(self) -> Dict:
        """Load session baselines."""
        if self.baselines_file.exists():
            with open(self.baselines_file) as f:
                return json.load(f)
        return {}


if __name__ == "__main__":
    agent = TaskPrioritizationAgent()
    result = agent.analyze()
    print(json.dumps(result, indent=2))
