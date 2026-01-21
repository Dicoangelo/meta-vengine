#!/usr/bin/env python3
"""
Parallel Implementation Strategy - Multiple build agents with file locking.

Pre-checks file conflicts, locks files before spawning, runs builders in parallel.
Falls back to sequential if conflicts detected.
"""

import sys
from pathlib import Path
from typing import Dict, List, TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent.parent))

from executor import AgentConfig, AgentResult, generate_task_prompt
from distribution import TaskAssignment

if TYPE_CHECKING:
    from orchestrator import MultiAgentOrchestrator


def execute_parallel_implement(
    orchestrator: "MultiAgentOrchestrator",
    task_id: str,
    task: str,
    assignments: List[TaskAssignment],
    conflicts: Dict
) -> Dict[str, AgentResult]:
    """
    Execute parallel implementation strategy.
    
    Pre-checks for file conflicts. If conflicts exist, falls back to sequential.
    Otherwise, locks files and runs all builders in parallel.
    """
    print(f"\n{'='*60}")
    print("PARALLEL IMPLEMENTATION STRATEGY")
    print(f"{'='*60}")
    print(f"Task: {task[:80]}...")
    print(f"Agents: {len(assignments)}")
    print(f"Can parallelize: {conflicts.get('can_parallelize', False)}")

    if conflicts.get("has_conflicts"):
        print("\nWARNING: File conflicts detected! Falling back to sequential...")
        return _execute_sequential(orchestrator, task_id, task, assignments)

    configs = []
    for i, assignment in enumerate(assignments, 1):
        prompt = generate_task_prompt(
            subtask=assignment.subtask,
            context=f"Original task: {task}",
            instructions=f"""
You are an implementation agent. Write code for your assigned subtask.
Files assigned (LOCKED): {', '.join(assignment.files) if assignment.files else 'auto'}
- Focus only on your assigned subtask
- Write clean, well-documented code
- Follow existing patterns
"""
        )

        config = AgentConfig(
            subtask=assignment.subtask,
            prompt=prompt,
            agent_type="general-purpose",
            model=assignment.model,
            timeout=300,
            files_to_lock=assignment.files,
            lock_type="write",
            dq_score=assignment.dq_score,
            cost_estimate=assignment.cost_estimate
        )
        configs.append(config)
        print(f"  Agent {i}: {assignment.model} - {assignment.subtask[:40]}...")

    print(f"\nSpawning {len(configs)} implementation agents in parallel...")
    agent_ids = orchestrator.executor.spawn_parallel(configs, task_id, max_workers=len(configs))
    results = orchestrator.executor.wait_for_agents(agent_ids, timeout=600)

    successful = sum(1 for r in results.values() if r.success)
    print(f"\nCompleted: {successful}/{len(results)} successful")

    return results


def _execute_sequential(orchestrator, task_id, task, assignments):
    """Fallback sequential execution."""
    results = {}
    for i, assignment in enumerate(assignments, 1):
        print(f"\n[{i}/{len(assignments)}] {assignment.subtask[:50]}...")
        
        config = AgentConfig(
            subtask=assignment.subtask,
            prompt=generate_task_prompt(assignment.subtask, f"Original: {task}"),
            agent_type="general-purpose",
            model=assignment.model,
            timeout=300,
            files_to_lock=assignment.files,
            lock_type="write"
        )
        
        agent_id = orchestrator.executor.spawn_cli_agent(config, task_id)
        agent = orchestrator.registry.get(agent_id)
        
        results[agent_id] = AgentResult(
            agent_id=agent_id,
            success=agent.state == "completed" if agent else False,
            output=agent.result.get("output", "") if agent and agent.result else "",
            error=agent.error if agent else "Agent not found"
        )
    return results
