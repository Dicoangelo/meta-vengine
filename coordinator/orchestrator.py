#!/usr/bin/env python3
"""
Multi-Agent Orchestrator - Main coordinator for parallel Claude agents.

Orchestrates multiple agents for:
- Parallel research (multiple explore agents)
- Parallel implementation (locked files)
- Review + build (concurrent)
- Full orchestration (research → build → review)
"""

import json
import sys
import uuid
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from registry import AgentRegistry, AgentState, AgentRecord
from conflict import ConflictManager, detect_potential_conflicts, LockType
from distribution import WorkDistributor, TaskAssignment, decompose_task
from executor import AgentExecutor, AgentConfig, AgentResult


@dataclass
class CoordinationResult:
    """Result of a multi-agent coordination."""
    task_id: str
    task: str
    strategy: str
    status: str  # success, partial, failed
    duration_seconds: float
    agent_results: Dict[str, Dict]
    synthesis: Dict
    total_cost: float


class ACESynthesizer:
    """
    Synthesizes results from multiple agents using ACE consensus.

    Adapted from ~/.claude/scripts/observatory/ace_consensus.py
    """

    DQ_WEIGHTS = {
        "validity": 0.4,
        "specificity": 0.3,
        "correctness": 0.3
    }

    def synthesize(self, agent_results: Dict[str, AgentResult], subtasks: List[str]) -> Dict:
        """
        Combine results from multiple agents into a unified response.

        Args:
            agent_results: Dict of agent_id -> AgentResult
            subtasks: Original subtask descriptions

        Returns:
            Synthesized result with confidence
        """
        successful = [r for r in agent_results.values() if r.success]
        failed = [r for r in agent_results.values() if not r.success]

        # Calculate overall success rate
        success_rate = len(successful) / len(agent_results) if agent_results else 0

        # Combine outputs
        combined_output = self._merge_outputs([r.output for r in successful])

        # Calculate confidence
        confidence = self._calculate_confidence(agent_results)

        # Extract files modified across all agents
        all_files = set()
        for r in agent_results.values():
            all_files.update(r.files_modified or [])

        return {
            "status": self._determine_status(success_rate),
            "success_rate": success_rate,
            "confidence": confidence,
            "combined_output": combined_output,
            "files_modified": list(all_files),
            "successful_agents": len(successful),
            "failed_agents": len(failed),
            "errors": [r.error for r in failed if r.error]
        }

    def _merge_outputs(self, outputs: List[str]) -> str:
        """Merge multiple agent outputs intelligently."""
        if not outputs:
            return ""

        if len(outputs) == 1:
            return outputs[0]

        # Simple concatenation with headers
        merged = []
        for i, output in enumerate(outputs, 1):
            if output.strip():
                merged.append(f"## Agent {i} Result\n{output.strip()}")

        return "\n\n".join(merged)

    def _calculate_confidence(self, agent_results: Dict[str, AgentResult]) -> float:
        """Calculate confidence in the combined result."""
        if not agent_results:
            return 0.0

        # Base confidence on success rate
        success_rate = sum(1 for r in agent_results.values() if r.success) / len(agent_results)

        # Adjust for consistency (do outputs agree?)
        consistency = 0.7  # Placeholder - would need semantic analysis

        return round(success_rate * 0.6 + consistency * 0.4, 3)

    def _determine_status(self, success_rate: float) -> str:
        """Determine overall status from success rate."""
        if success_rate >= 0.9:
            return "success"
        elif success_rate >= 0.5:
            return "partial"
        else:
            return "failed"


class MultiAgentOrchestrator:
    """
    Main orchestrator for multi-agent coordination.

    Workflow:
    1. Decompose task into subtasks
    2. Detect dependencies (parallel vs sequential)
    3. Check file conflicts
    4. Select strategy (research/implement/review/full)
    5. Execute with appropriate strategy
    6. Synthesize results with ACE
    """

    DATA_DIR = Path.home() / ".claude" / "coordinator" / "data"
    LOG_FILE = DATA_DIR / "coordination-log.jsonl"

    # Cost confirmation threshold
    COST_CONFIRM_THRESHOLD = 1.0  # USD

    def __init__(self):
        self.registry = AgentRegistry()
        self.conflict_mgr = ConflictManager()
        self.distributor = WorkDistributor()
        self.executor = AgentExecutor(self.registry, self.conflict_mgr)
        self.synthesizer = ACESynthesizer()
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)

    def coordinate(self, task: str, strategy: str = "auto", confirm_cost: bool = True) -> CoordinationResult:
        """
        Main coordination entry point.

        Args:
            task: High-level task description
            strategy: "auto", "research", "implement", "review-build", "full"
            confirm_cost: Require confirmation for high-cost operations

        Returns:
            CoordinationResult with status and outputs
        """
        task_id = f"coord-{uuid.uuid4().hex[:8]}"
        start_time = time.time()

        # 1. Decompose task
        subtasks = self._decompose_task(task, strategy)

        # 2. Assign models and estimate costs
        assignments = self.distributor.assign(subtasks)

        # 3. Check conflicts and determine parallelization
        conflict_analysis = detect_potential_conflicts([
            {"files": a.files, "lock_type": a.lock_type}
            for a in assignments
        ])

        # 4. Estimate total cost
        cost_estimate = self.distributor.estimate_total_cost(assignments)

        if confirm_cost and cost_estimate["total"] > self.COST_CONFIRM_THRESHOLD:
            print(f"\nEstimated cost: ${cost_estimate['total']:.4f}")
            print(f"Agents: {cost_estimate['agent_count']}")
            print(f"  Haiku: ${cost_estimate['by_model'].get('haiku', 0):.4f}")
            print(f"  Sonnet: ${cost_estimate['by_model'].get('sonnet', 0):.4f}")
            print(f"  Opus: ${cost_estimate['by_model'].get('opus', 0):.4f}")
            response = input("\nProceed? [y/N]: ")
            if response.lower() != 'y':
                return CoordinationResult(
                    task_id=task_id,
                    task=task,
                    strategy=strategy,
                    status="cancelled",
                    duration_seconds=0,
                    agent_results={},
                    synthesis={"status": "cancelled", "reason": "User declined"},
                    total_cost=0
                )

        # 5. Select and execute strategy
        if strategy == "auto":
            strategy = self._detect_strategy(task, assignments, conflict_analysis)

        print(f"\nExecuting strategy: {strategy}")
        print(f"Subtasks: {len(assignments)}")
        print(f"Can parallelize: {conflict_analysis['can_parallelize']}")

        # Import and run strategy
        agent_results = self._execute_strategy(
            strategy, task_id, task, assignments, conflict_analysis
        )

        # 6. Synthesize results
        synthesis = self.synthesizer.synthesize(
            agent_results,
            [a.subtask for a in assignments]
        )

        duration = time.time() - start_time

        # Calculate actual cost (would need token tracking)
        total_cost = sum(a.cost_estimate for a in assignments)

        result = CoordinationResult(
            task_id=task_id,
            task=task,
            strategy=strategy,
            status=synthesis["status"],
            duration_seconds=round(duration, 2),
            agent_results={k: asdict(v) if hasattr(v, '__dataclass_fields__') else v
                          for k, v in agent_results.items()},
            synthesis=synthesis,
            total_cost=total_cost
        )

        # Log result
        self._log_coordination(result)

        return result

    def _decompose_task(self, task: str, strategy: str) -> List[Dict]:
        """Decompose task based on strategy."""
        if strategy == "research":
            # Multiple explore angles
            return [
                {"subtask": f"Explore architecture for: {task}", "agent_type": "Explore", "lock_type": "read", "priority": 0},
                {"subtask": f"Find similar patterns for: {task}", "agent_type": "Explore", "lock_type": "read", "priority": 0},
                {"subtask": f"Analyze dependencies for: {task}", "agent_type": "Explore", "lock_type": "read", "priority": 0},
            ]
        elif strategy == "implement":
            return [
                {"subtask": f"Implement: {task}", "agent_type": "general-purpose", "lock_type": "write", "priority": 0},
            ]
        elif strategy == "review-build":
            return [
                {"subtask": f"Build: {task}", "agent_type": "general-purpose", "lock_type": "write", "priority": 0},
                {"subtask": f"Review implementation for: {task}", "agent_type": "Explore", "lock_type": "read", "priority": 0},
            ]
        else:
            # Auto decomposition
            return decompose_task(task)

    def _detect_strategy(self, task: str, assignments: List[TaskAssignment], conflicts: Dict) -> str:
        """Auto-detect best strategy for task."""
        task_lower = task.lower()

        # Research indicators
        if any(kw in task_lower for kw in ["understand", "explore", "find", "analyze", "investigate", "how does"]):
            return "research"

        # Implementation with review
        if any(kw in task_lower for kw in ["implement", "add", "create", "build"]):
            if len(assignments) > 1 and not conflicts["has_conflicts"]:
                return "full"
            return "review-build"

        # Default to full orchestration
        return "full"

    def _execute_strategy(self, strategy: str, task_id: str, task: str,
                          assignments: List[TaskAssignment], conflicts: Dict) -> Dict[str, AgentResult]:
        """Execute the selected strategy."""
        # Import strategy modules
        strategies_dir = Path(__file__).parent / "strategies"

        if strategy == "research":
            from strategies.parallel_research import execute_parallel_research
            return execute_parallel_research(self, task_id, task, assignments)

        elif strategy == "implement":
            from strategies.parallel_implement import execute_parallel_implement
            return execute_parallel_implement(self, task_id, task, assignments, conflicts)

        elif strategy == "review-build":
            from strategies.review_build import execute_review_build
            return execute_review_build(self, task_id, task, assignments)

        elif strategy == "full":
            from strategies.full_orchestration import execute_full_orchestration
            return execute_full_orchestration(self, task_id, task, assignments, conflicts)

        else:
            # Fallback: sequential execution
            return self._execute_sequential(task_id, assignments)

    def _execute_sequential(self, task_id: str, assignments: List[TaskAssignment]) -> Dict[str, AgentResult]:
        """Fallback: execute assignments sequentially."""
        results = {}

        for assignment in assignments:
            config = AgentConfig(
                subtask=assignment.subtask,
                prompt=assignment.subtask,
                agent_type=assignment.agent_type,
                model=assignment.model,
                files_to_lock=assignment.files,
                lock_type=assignment.lock_type,
                dq_score=assignment.dq_score,
                cost_estimate=assignment.cost_estimate
            )

            agent_id = self.executor.spawn_cli_agent(config, task_id)
            agent = self.registry.get(agent_id)

            results[agent_id] = AgentResult(
                agent_id=agent_id,
                success=agent.state == AgentState.COMPLETED.value if agent else False,
                output=agent.result.get("output", "") if agent and agent.result else "",
                error=agent.error if agent else "Agent not found"
            )

        return results

    def _log_coordination(self, result: CoordinationResult):
        """Log coordination result."""
        with open(self.LOG_FILE, 'a') as f:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "task_id": result.task_id,
                "task": result.task[:100],
                "strategy": result.strategy,
                "status": result.status,
                "duration_seconds": result.duration_seconds,
                "total_cost": result.total_cost,
                "agent_count": len(result.agent_results)
            }
            f.write(json.dumps(log_entry) + "\n")

    def status(self, task_id: str = None) -> Dict:
        """Get status of coordination tasks."""
        if task_id:
            agents = self.registry.get_task_agents(task_id)
            return {
                "task_id": task_id,
                "agents": [asdict(a) for a in agents],
                "stats": self.registry.get_stats()
            }
        else:
            return {
                "registry": self.registry.get_stats(),
                "locks": self.conflict_mgr.get_stats()
            }

    def cancel(self, task_id: str):
        """Cancel a coordination task."""
        self.executor.cancel_task(task_id)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Multi-Agent Coordinator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  coord research "How does the routing system work?"
  coord implement "Add logging to all API endpoints"
  coord review-build "Implement rate limiting middleware"
  coord full "Add user preferences feature"
  coord status
        """
    )

    parser.add_argument("command", nargs="?", default="status",
                        help="Command: research, implement, review-build, full, status, cancel")
    parser.add_argument("task", nargs="?", help="Task description")
    parser.add_argument("--task-id", help="Task ID (for status/cancel)")
    parser.add_argument("--no-confirm", action="store_true", help="Skip cost confirmation")

    args = parser.parse_args()

    orchestrator = MultiAgentOrchestrator()

    if args.command == "status":
        status = orchestrator.status(args.task_id)
        print(json.dumps(status, indent=2))

    elif args.command == "cancel" and args.task_id:
        orchestrator.cancel(args.task_id)
        print(f"Cancelled task: {args.task_id}")

    elif args.command in ["research", "implement", "review-build", "full"] and args.task:
        result = orchestrator.coordinate(
            task=args.task,
            strategy=args.command,
            confirm_cost=not args.no_confirm
        )

        print(f"\n{'='*60}")
        print(f"Task ID: {result.task_id}")
        print(f"Status: {result.status}")
        print(f"Duration: {result.duration_seconds}s")
        print(f"Cost: ${result.total_cost:.4f}")
        print(f"{'='*60}")

        if result.synthesis.get("combined_output"):
            print("\n## Combined Output")
            print(result.synthesis["combined_output"][:2000])

        if result.synthesis.get("errors"):
            print("\n## Errors")
            for err in result.synthesis["errors"]:
                print(f"  - {err}")

    elif args.task:
        # Auto-detect strategy
        result = orchestrator.coordinate(
            task=args.task,
            strategy="auto",
            confirm_cost=not args.no_confirm
        )

        print(f"\nTask ID: {result.task_id}")
        print(f"Strategy: {result.strategy}")
        print(f"Status: {result.status}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
