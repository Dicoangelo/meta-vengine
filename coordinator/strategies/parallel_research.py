#!/usr/bin/env python3
"""
Parallel Research Strategy - Multiple explore agents for research tasks.

All agents are read-only, so no conflict checking needed.
Spawns multiple agents in parallel to explore different aspects of a topic.
"""

import sys
from pathlib import Path
from typing import Dict, List, TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent.parent))

from executor import AgentConfig, AgentResult, generate_task_prompt
from distribution import TaskAssignment

if TYPE_CHECKING:
    from orchestrator import MultiAgentOrchestrator


def execute_parallel_research(
    orchestrator: "MultiAgentOrchestrator",
    task_id: str,
    task: str,
    assignments: List[TaskAssignment]
) -> Dict[str, AgentResult]:
    """
    Execute parallel research strategy.
    
    Spawns multiple explore agents to research different aspects of a topic.
    All agents are read-only so they can run in parallel without conflicts.
    """
    print(f"\n{'='*60}")
    print("PARALLEL RESEARCH STRATEGY")
    print(f"{'='*60}")
    print(f"Task: {task[:80]}...")
    print(f"Agents: {len(assignments)}")

    configs = []
    for i, assignment in enumerate(assignments, 1):
        prompt = generate_task_prompt(
            subtask=assignment.subtask,
            context=f"Original task: {task}",
            instructions="""
You are a research agent. Explore and gather information.
- Use Read, Grep, and Glob tools to explore the codebase
- Focus on understanding, not modifying
- Provide clear, structured findings
- Note relevant file paths and code sections
DO NOT edit or write any files.
"""
        )

        config = AgentConfig(
            subtask=assignment.subtask,
            prompt=prompt,
            agent_type="Explore",
            model=assignment.model,
            timeout=180,
            files_to_lock=[],
            lock_type="read",
            dq_score=assignment.dq_score,
            cost_estimate=assignment.cost_estimate
        )
        configs.append(config)
        print(f"  Agent {i}: {assignment.model} - {assignment.subtask[:50]}...")

    print(f"\nSpawning {len(configs)} research agents in parallel...")
    agent_ids = orchestrator.executor.spawn_parallel(configs, task_id, max_workers=len(configs))
    print(f"Spawned: {agent_ids}")

    results = orchestrator.executor.wait_for_agents(agent_ids, timeout=300)
    successful = sum(1 for r in results.values() if r.success)
    print(f"\nCompleted: {successful}/{len(results)} successful")

    return results


def generate_research_subtasks(task: str, num_agents: int = 3) -> List[Dict]:
    """Generate research subtasks for a given task."""
    angles = [
        ("architecture", "Explore the overall architecture and structure for"),
        ("patterns", "Find similar patterns and implementations for"),
        ("dependencies", "Analyze dependencies and connections for"),
    ]
    
    return [
        {"subtask": f"{prompt}: {task}", "agent_type": "Explore", "lock_type": "read", "priority": i}
        for i, (_, prompt) in enumerate(angles[:num_agents])
    ]
