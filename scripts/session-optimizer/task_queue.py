#!/usr/bin/env python3
"""
Task Queue - DQ-weighted priority queue for tasks

Manages tasks with:
- DQ-weighted prioritization (validity + specificity + correctness)
- Capacity-aware scheduling
- Batch suggestions for efficiency
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import uuid


class TaskQueueManager:
    """Manages DQ-weighted task queue."""

    def __init__(self):
        self.kernel_dir = Path.home() / ".claude" / "kernel"
        self.queue_file = self.kernel_dir / "task-queue.json"
        self.state_file = self.kernel_dir / "session-state.json"
        self.baselines_file = self.kernel_dir / "session-baselines.json"

        # DQ weights (from ACE Framework)
        self.dq_weights = {
            "validity": 0.4,
            "specificity": 0.3,
            "correctness": 0.3
        }

    def add_task(
        self,
        description: str,
        complexity: float = 0.5,
        priority: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Add a task to the queue.

        Args:
            description: Task description
            complexity: Complexity score (0.0-1.0)
            priority: Override priority (0.0-1.0), or calculated from complexity
            metadata: Additional task metadata
        """
        queue = self._load_queue()

        # Calculate DQ-weighted priority if not provided
        if priority is None:
            # Higher complexity gets higher priority
            priority = complexity * 0.7 + 0.3

        task = {
            "id": str(uuid.uuid4())[:8],
            "description": description,
            "complexity": complexity,
            "priority": round(priority, 3),
            "status": "pending",
            "addedAt": datetime.now().isoformat(),
            "completedAt": None,
            "metadata": metadata or {}
        }

        queue["tasks"].append(task)

        # Sort by priority (highest first)
        queue["tasks"].sort(key=lambda t: t["priority"], reverse=True)

        self._save_queue(queue)
        return task

    def get_next_task(self) -> Optional[Dict]:
        """
        Get next task that fits current capacity.
        """
        queue = self._load_queue()
        state = self._load_state()

        capacity = state.get("capacity", {}).get("remaining", {})

        for task in queue["tasks"]:
            if task["status"] != "pending":
                continue

            # Check capacity
            complexity = task["complexity"]

            if complexity >= 0.7:
                if capacity.get("opus", 0) >= 1:
                    return task
            elif complexity >= 0.3:
                if capacity.get("sonnet", 0) >= 1:
                    return task
            else:
                if capacity.get("haiku", 0) >= 1:
                    return task

        return None

    def complete_task(self, task_id: str) -> bool:
        """
        Mark a task as completed.
        """
        queue = self._load_queue()

        for task in queue["tasks"]:
            if task["id"] == task_id:
                task["status"] = "completed"
                task["completedAt"] = datetime.now().isoformat()
                self._save_queue(queue)
                return True

        return False

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.
        """
        queue = self._load_queue()

        for task in queue["tasks"]:
            if task["id"] == task_id:
                task["status"] = "cancelled"
                task["completedAt"] = datetime.now().isoformat()
                self._save_queue(queue)
                return True

        return False

    def list_tasks(self, status: Optional[str] = None) -> List[Dict]:
        """
        List tasks, optionally filtered by status.
        """
        queue = self._load_queue()
        tasks = queue.get("tasks", [])

        if status:
            tasks = [t for t in tasks if t["status"] == status]

        return tasks

    def get_queue_stats(self) -> Dict:
        """
        Get queue statistics.
        """
        queue = self._load_queue()
        tasks = queue.get("tasks", [])

        stats = {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t["status"] == "pending"),
            "completed": sum(1 for t in tasks if t["status"] == "completed"),
            "cancelled": sum(1 for t in tasks if t["status"] == "cancelled"),
            "avgPriority": 0,
            "avgComplexity": 0
        }

        pending = [t for t in tasks if t["status"] == "pending"]
        if pending:
            stats["avgPriority"] = round(sum(t["priority"] for t in pending) / len(pending), 3)
            stats["avgComplexity"] = round(sum(t["complexity"] for t in pending) / len(pending), 3)

        return stats

    def suggest_batches(self) -> List[Dict]:
        """
        Suggest task batches for efficient execution.
        """
        pending = self.list_tasks(status="pending")

        if not pending:
            return []

        # Group by complexity
        batches = {
            "high": [],    # complexity >= 0.7 (Opus)
            "medium": [],  # complexity >= 0.3 (Sonnet)
            "low": []      # complexity < 0.3 (Haiku)
        }

        for task in pending:
            if task["complexity"] >= 0.7:
                batches["high"].append(task)
            elif task["complexity"] >= 0.3:
                batches["medium"].append(task)
            else:
                batches["low"].append(task)

        suggestions = []

        if batches["high"]:
            suggestions.append({
                "name": "High complexity batch",
                "model": "opus",
                "tasks": batches["high"][:3],  # Max 3 Opus tasks
                "recommendation": "Execute during peak hours"
            })

        if batches["medium"]:
            suggestions.append({
                "name": "Medium complexity batch",
                "model": "sonnet",
                "tasks": batches["medium"][:5],  # Max 5 Sonnet tasks
                "recommendation": "Execute now or during peak"
            })

        if batches["low"]:
            suggestions.append({
                "name": "Low complexity batch",
                "model": "haiku",
                "tasks": batches["low"][:10],  # Max 10 Haiku tasks
                "recommendation": "Batch in off-peak window (17:00-19:00)"
            })

        return suggestions

    def reprioritize(self, task_id: str, new_priority: float) -> bool:
        """
        Manually reprioritize a task.
        """
        queue = self._load_queue()

        for task in queue["tasks"]:
            if task["id"] == task_id:
                task["priority"] = new_priority
                task["metadata"]["reprioritizedAt"] = datetime.now().isoformat()

                # Re-sort
                queue["tasks"].sort(key=lambda t: t["priority"], reverse=True)
                self._save_queue(queue)
                return True

        return False

    def clear_completed(self) -> int:
        """
        Remove completed and cancelled tasks from queue.
        """
        queue = self._load_queue()
        original = len(queue["tasks"])
        queue["tasks"] = [t for t in queue["tasks"] if t["status"] == "pending"]
        self._save_queue(queue)
        return original - len(queue["tasks"])

    def _load_queue(self) -> Dict:
        """Load task queue."""
        if self.queue_file.exists():
            with open(self.queue_file) as f:
                return json.load(f)
        return {"version": "1.0.0", "tasks": []}

    def _save_queue(self, queue: Dict):
        """Save task queue."""
        queue["lastUpdated"] = datetime.now().isoformat()
        with open(self.queue_file, "w") as f:
            json.dump(queue, f, indent=2)

    def _load_state(self) -> Dict:
        """Load session state."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {}


if __name__ == "__main__":
    import sys

    manager = TaskQueueManager()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "add":
            if len(sys.argv) > 2:
                desc = sys.argv[2]
                comp = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
                task = manager.add_task(desc, comp)
                print(f"Added: {task['id']} - {desc} (priority: {task['priority']})")
            else:
                print("Usage: task_queue.py add <description> [complexity]")

        elif cmd == "next":
            task = manager.get_next_task()
            if task:
                print(f"Next: {task['id']} - {task['description']}")
                print(f"  Complexity: {task['complexity']}, Priority: {task['priority']}")
            else:
                print("No tasks available for current capacity")

        elif cmd == "complete":
            if len(sys.argv) > 2:
                if manager.complete_task(sys.argv[2]):
                    print("Task completed")
                else:
                    print("Task not found")
            else:
                print("Usage: task_queue.py complete <task_id>")

        elif cmd == "list":
            status = sys.argv[2] if len(sys.argv) > 2 else None
            tasks = manager.list_tasks(status)
            for task in tasks:
                print(f"  [{task['status'][:1].upper()}] {task['id']}: {task['description'][:40]}... (p:{task['priority']})")

        elif cmd == "stats":
            stats = manager.get_queue_stats()
            print(f"Queue: {stats['pending']} pending, {stats['completed']} completed")
            print(f"  Avg priority: {stats['avgPriority']}, Avg complexity: {stats['avgComplexity']}")

        elif cmd == "batch":
            batches = manager.suggest_batches()
            for batch in batches:
                print(f"\n{batch['name']} ({batch['model']}):")
                print(f"  {batch['recommendation']}")
                for task in batch['tasks']:
                    print(f"    - {task['description'][:40]}...")

        elif cmd == "clear":
            removed = manager.clear_completed()
            print(f"Cleared {removed} completed tasks")

    else:
        print("Task Queue - DQ-weighted task management")
        print("")
        print("Commands:")
        print("  add <desc> [complexity]  - Add task")
        print("  next                     - Get next task")
        print("  complete <id>            - Complete task")
        print("  list [status]            - List tasks")
        print("  stats                    - Queue statistics")
        print("  batch                    - Batch suggestions")
        print("  clear                    - Clear completed")
