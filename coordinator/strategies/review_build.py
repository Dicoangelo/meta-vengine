#!/usr/bin/env python3
"""
Review + Build Strategy - Builder and reviewer run in parallel.

Builder writes code while reviewer analyzes and provides feedback.
Reviewer is read-only, so no conflicts with builder.
"""

import sys
from pathlib import Path
from typing import Dict, List, TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent.parent))

from executor import AgentConfig, AgentResult, generate_task_prompt
from distribution import TaskAssignment

if TYPE_CHECKING:
    from orchestrator import MultiAgentOrchestrator


def execute_review_build(
    orchestrator: "MultiAgentOrchestrator",
    task_id: str,
    task: str,
    assignments: List[TaskAssignment]
) -> Dict[str, AgentResult]:
    """
    Execute review + build strategy.
    
    Spawns a builder agent and a reviewer agent in parallel.
    Builder implements while reviewer analyzes and provides feedback.
    """
    print(f"\n{'='*60}")
    print("REVIEW + BUILD STRATEGY")
    print(f"{'='*60}")
    print(f"Task: {task[:80]}...")

    configs = []

    # Builder agent
    builder_prompt = generate_task_prompt(
        subtask=f"Implement: {task}",
        context="You are the BUILDER agent.",
        instructions="""
Implement the requested feature/fix.
- Write clean, well-documented code
- Follow existing patterns
- Add appropriate error handling
"""
    )

    builder_assignment = next((a for a in assignments if a.lock_type == "write"), assignments[0] if assignments else None)
    
    if builder_assignment:
        configs.append(AgentConfig(
            subtask=f"Build: {task[:50]}",
            prompt=builder_prompt,
            agent_type="general-purpose",
            model=builder_assignment.model,
            timeout=300,
            files_to_lock=builder_assignment.files,
            lock_type="write",
            dq_score=builder_assignment.dq_score,
            cost_estimate=builder_assignment.cost_estimate
        ))
        print(f"  Builder: {builder_assignment.model}")

    # Reviewer agent
    reviewer_prompt = generate_task_prompt(
        subtask=f"Review: {task}",
        context="You are the REVIEWER agent.",
        instructions="""
Review for:
1. SECURITY: Injection vulnerabilities, auth issues
2. PERFORMANCE: N+1 queries, memory leaks
3. CORRECTNESS: Logic errors, edge cases
4. MAINTAINABILITY: Code clarity, documentation
DO NOT modify any files.
"""
    )

    configs.append(AgentConfig(
        subtask=f"Review: {task[:50]}",
        prompt=reviewer_prompt,
        agent_type="Explore",
        model="haiku",
        timeout=180,
        files_to_lock=[],
        lock_type="read"
    ))
    print(f"  Reviewer: haiku")

    print(f"\nSpawning builder + reviewer in parallel...")
    agent_ids = orchestrator.executor.spawn_parallel(configs, task_id, max_workers=2)
    results = orchestrator.executor.wait_for_agents(agent_ids, timeout=400)

    for agent_id, result in results.items():
        agent = orchestrator.registry.get(agent_id)
        agent_type = agent.agent_type if agent else "unknown"
        status = "✓" if result.success else "✗"
        print(f"  {status} {agent_type}: {agent_id}")

    return results
