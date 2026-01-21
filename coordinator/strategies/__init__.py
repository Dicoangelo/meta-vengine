"""
Multi-Agent Coordination Strategies.

Available strategies:
- parallel_research: Multiple explore agents for research tasks
- parallel_implement: Multiple build agents with file locking
- review_build: Build + review agents in parallel
- full_orchestration: Research → Build → Review pipeline
"""

from .parallel_research import execute_parallel_research
from .parallel_implement import execute_parallel_implement
from .review_build import execute_review_build
from .full_orchestration import execute_full_orchestration

__all__ = [
    "execute_parallel_research",
    "execute_parallel_implement",
    "execute_review_build",
    "execute_full_orchestration"
]
