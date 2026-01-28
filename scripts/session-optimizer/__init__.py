"""
Session Optimizer - Sovereign Session Optimization System

A fully autonomous session optimization system that integrates with the
existing meta-engine, observatory, and coevolution infrastructure.

Components:
- WindowTracker: Learns reset patterns from activity-events
- BudgetManager: Token allocation via subscription-tracker
- CapacityPredictor: ML-lite prediction from stats-cache
- TaskQueue: DQ-weighted priority heap
- FeedbackLoop: Pattern detection -> baseline updates
"""

from .window_tracker import WindowTracker
from .budget_manager import BudgetManager
from .capacity_predictor import CapacityPredictor
from .task_queue import TaskQueueManager
from .feedback_loop import FeedbackLoop

__version__ = "1.0.0"
__all__ = [
    "WindowTracker",
    "BudgetManager",
    "CapacityPredictor",
    "TaskQueueManager",
    "FeedbackLoop"
]
