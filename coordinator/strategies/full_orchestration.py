#!/usr/bin/env python3
"""
Full Orchestration Strategy - Research → Build → Review pipeline.

Phase 1: Parallel research to understand context
Phase 2: Parallel implementation with file locking
Phase 3: Parallel review for quality assurance
"""

import sys
from pathlib import Path
from typing import Dict, List, TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent.parent))

from executor import AgentConfig, AgentResult, generate_task_prompt
from distribution import TaskAssignment

if TYPE_CHECKING:
    from orchestrator import MultiAgentOrchestrator


def execute_full_orchestration(
    orchestrator: "MultiAgentOrchestrator",
    task_id: str,
    task: str,
    assignments: List[TaskAssignment],
    conflicts: Dict
) -> Dict[str, AgentResult]:
    """
    Execute full orchestration: Research → Build → Review.
    """
    print(f"\n{'='*60}")
    print("FULL ORCHESTRATION STRATEGY")
    print(f"{'='*60}")
    print(f"Task: {task[:80]}...")
    print(f"Phases: Research → Implement → Review")

    all_results = {}

    # ═══════════════════════════════════════════════════════════════
    # PHASE 1: RESEARCH
    # ═══════════════════════════════════════════════════════════════
    print(f"\n{'─'*40}")
    print("PHASE 1: RESEARCH")
    print(f"{'─'*40}")

    research_configs = [
        AgentConfig(
            subtask=f"Explore architecture for: {task}",
            prompt=generate_task_prompt(f"Explore architecture for: {task}", instructions="Find relevant files and patterns."),
            agent_type="Explore", model="haiku", timeout=120, lock_type="read"
        ),
        AgentConfig(
            subtask=f"Find similar patterns for: {task}",
            prompt=generate_task_prompt(f"Find similar patterns for: {task}", instructions="Search for existing implementations."),
            agent_type="Explore", model="haiku", timeout=120, lock_type="read"
        ),
    ]

    print(f"Spawning {len(research_configs)} research agents...")
    research_ids = orchestrator.executor.spawn_parallel(research_configs, task_id, max_workers=3)
    research_results = orchestrator.executor.wait_for_agents(research_ids, timeout=180)
    print(f"Research: {sum(1 for r in research_results.values() if r.success)}/{len(research_results)} successful")
    all_results.update(research_results)

    # Synthesize research
    research_context = "\n".join([r.output[:300] for r in research_results.values() if r.success and r.output])

    # ═══════════════════════════════════════════════════════════════
    # PHASE 2: IMPLEMENT
    # ═══════════════════════════════════════════════════════════════
    print(f"\n{'─'*40}")
    print("PHASE 2: IMPLEMENT")
    print(f"{'─'*40}")

    impl_assignments = [a for a in assignments if a.lock_type == "write"]
    if not impl_assignments:
        impl_assignments = [TaskAssignment(
            subtask=f"Implement: {task}", agent_type="general-purpose", model="sonnet",
            files=[], lock_type="write", dq_score=0.6, cost_estimate=0.05, priority=0
        )]

    impl_configs = []
    for a in impl_assignments:
        impl_configs.append(AgentConfig(
            subtask=a.subtask,
            prompt=generate_task_prompt(a.subtask, context=f"Research:\n{research_context[:500]}", instructions="Implement using the research context."),
            agent_type="general-purpose", model=a.model, timeout=300,
            files_to_lock=a.files, lock_type="write"
        ))

    can_parallel = conflicts.get("can_parallelize", True) and not conflicts.get("has_conflicts", False)
    
    if can_parallel and len(impl_configs) > 1:
        print(f"Spawning {len(impl_configs)} agents in parallel...")
        impl_ids = orchestrator.executor.spawn_parallel(impl_configs, task_id, max_workers=len(impl_configs))
    else:
        print(f"Running {len(impl_configs)} agents sequentially...")
        impl_ids = [orchestrator.executor.spawn_cli_agent(c, task_id) for c in impl_configs]

    impl_results = orchestrator.executor.wait_for_agents(impl_ids, timeout=600)
    print(f"Implementation: {sum(1 for r in impl_results.values() if r.success)}/{len(impl_results)} successful")
    all_results.update(impl_results)

    # ═══════════════════════════════════════════════════════════════
    # PHASE 3: REVIEW
    # ═══════════════════════════════════════════════════════════════
    print(f"\n{'─'*40}")
    print("PHASE 3: REVIEW")
    print(f"{'─'*40}")

    review_configs = [
        AgentConfig(
            subtask="Security review",
            prompt=generate_task_prompt(f"Security review for: {task}", instructions="Check for vulnerabilities."),
            agent_type="Explore", model="haiku", timeout=120, lock_type="read"
        ),
        AgentConfig(
            subtask="Quality review",
            prompt=generate_task_prompt(f"Quality review for: {task}", instructions="Review code quality."),
            agent_type="Explore", model="haiku", timeout=120, lock_type="read"
        ),
    ]

    print(f"Spawning {len(review_configs)} review agents...")
    review_ids = orchestrator.executor.spawn_parallel(review_configs, task_id, max_workers=3)
    review_results = orchestrator.executor.wait_for_agents(review_ids, timeout=180)
    print(f"Review: {sum(1 for r in review_results.values() if r.success)}/{len(review_results)} successful")
    all_results.update(review_results)

    # ═══════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("ORCHESTRATION COMPLETE")
    print(f"{'='*60}")
    total = len(all_results)
    success = sum(1 for r in all_results.values() if r.success)
    print(f"Total: {success}/{total} successful ({round(success/total*100) if total else 0}%)")

    return all_results
