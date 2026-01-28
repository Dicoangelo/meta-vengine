"""
Session-Specific Observatory Agents

6 specialized agents for session optimization:
1. WindowPatternAgent - Detects window boundaries
2. BudgetEfficiencyAgent - Analyzes token utilization
3. CapacityForecastAgent - Predicts remaining capacity
4. TaskPrioritizationAgent - DQ-scores queued work
5. ModelRecommendationAgent - Suggests optimal model
6. SessionHealthAgent - Context saturation + checkpoint timing

These agents complement the existing 6 analysis agents:
- OutcomeDetectorAgent
- QualityScorerAgent
- ComplexityAnalyzerAgent
- ModelEfficiencyAgent
- ProductivityAnalyzerAgent
- RoutingQualityAgent
"""

from .window_pattern_agent import WindowPatternAgent
from .budget_efficiency_agent import BudgetEfficiencyAgent
from .capacity_forecast_agent import CapacityForecastAgent
from .task_prioritization_agent import TaskPrioritizationAgent
from .model_recommendation_agent import ModelRecommendationAgent
from .session_health_agent import SessionHealthAgent

__all__ = [
    "WindowPatternAgent",
    "BudgetEfficiencyAgent",
    "CapacityForecastAgent",
    "TaskPrioritizationAgent",
    "ModelRecommendationAgent",
    "SessionHealthAgent"
]

# Agent weights for ACE consensus (total = 1.0)
AGENT_WEIGHTS = {
    "window_pattern": 0.20,
    "budget_efficiency": 0.18,
    "capacity_forecast": 0.17,
    "task_prioritization": 0.15,
    "model_recommendation": 0.15,
    "session_health": 0.15
}
