"""
ModelEfficiencyAgent - Evaluates model selection efficiency

Determines if the optimal model was used based on session complexity.
Compares actual model used vs recommended model for the complexity level.
"""

from typing import Dict, Optional
from . import SessionAnalysisAgent


class ModelEfficiencyAgent(SessionAnalysisAgent):
    """Evaluates if optimal model was used for session complexity."""

    def __init__(self):
        super().__init__()

        # Model complexity thresholds (from baselines.json)
        self.thresholds = {
            "haiku": {"min": 0.0, "max": 0.30},
            "sonnet": {"min": 0.30, "max": 0.70},
            "opus": {"min": 0.70, "max": 1.0}
        }

        # Model hierarchy (for over/under provisioning)
        self.model_rank = {
            "haiku": 1,
            "sonnet": 2,
            "opus": 3
        }

    def analyze(self, transcript: Dict) -> Dict:
        """Evaluate model efficiency."""

        # Get session complexity (from metadata or calculate)
        complexity = self._get_complexity(transcript)

        # Get model used
        model_used = self._get_model_used(transcript)

        # Determine optimal model for this complexity
        optimal_model = self._get_optimal_model(complexity)

        # Calculate efficiency score
        efficiency, status = self._calculate_efficiency(
            complexity, model_used, optimal_model
        )

        # DQ components
        validity = 0.85 if model_used else 0.5
        specificity = 0.80
        correctness = efficiency

        return {
            "summary": f"Efficiency: {efficiency:.1%} ({status})",
            "efficiency": efficiency,
            "dq_score": self._calculate_dq_score(validity, specificity, correctness),
            "confidence": 0.85 if model_used else 0.5,
            "data": {
                "efficiency": efficiency,
                "status": status,
                "complexity": complexity,
                "model_used": model_used,
                "optimal_model": optimal_model,
                "over_provisioned": status == "over_provisioned",
                "under_provisioned": status == "under_provisioned"
            }
        }

    def _get_complexity(self, transcript: Dict) -> float:
        """Get session complexity from metadata or estimate."""

        metadata = transcript.get("metadata", {})

        # Check if complexity already calculated
        if "complexity" in metadata:
            return float(metadata["complexity"])

        # Estimate from user queries
        user_messages = self._extract_messages(transcript, "user")
        if not user_messages:
            return 0.5

        # Simple estimation based on query characteristics
        total_length = sum(len(str(m.get("content", ""))) for m in user_messages)
        avg_length = total_length / len(user_messages)

        # Heuristic: longer queries tend to be more complex
        if avg_length > 500:
            return 0.7
        elif avg_length > 200:
            return 0.5
        else:
            return 0.3

    def _get_model_used(self, transcript: Dict) -> Optional[str]:
        """Extract model name from transcript metadata."""

        metadata = transcript.get("metadata", {})

        # Check common metadata fields
        if "model" in metadata:
            return self._normalize_model_name(metadata["model"])

        # Check events for model info
        events = transcript.get("events", [])
        for event in events:
            if event.get("type") == "session_start" or event.get("event") == "session_start":
                model = event.get("model") or event.get("data", {}).get("model")
                if model:
                    return self._normalize_model_name(model)

        return None

    def _normalize_model_name(self, model: str) -> str:
        """Normalize model name to haiku/sonnet/opus."""
        model_lower = str(model).lower()

        if "haiku" in model_lower:
            return "haiku"
        elif "sonnet" in model_lower:
            return "sonnet"
        elif "opus" in model_lower:
            return "opus"
        else:
            return "unknown"

    def _get_optimal_model(self, complexity: float) -> str:
        """Determine optimal model for given complexity."""

        if complexity < self.thresholds["haiku"]["max"]:
            return "haiku"
        elif complexity < self.thresholds["sonnet"]["max"]:
            return "sonnet"
        else:
            return "opus"

    def _calculate_efficiency(
        self,
        complexity: float,
        model_used: Optional[str],
        optimal_model: str
    ):
        """Calculate efficiency score and status."""

        if not model_used or model_used == "unknown":
            return 0.5, "unknown"

        # Perfect match
        if model_used == optimal_model:
            return 1.0, "optimal"

        # Get model ranks
        used_rank = self.model_rank.get(model_used, 2)
        optimal_rank = self.model_rank.get(optimal_model, 2)

        # Over-provisioned (using more expensive model than needed)
        if used_rank > optimal_rank:
            difference = used_rank - optimal_rank
            # Penalize based on how far over-provisioned
            efficiency = max(0.4, 1.0 - (difference * 0.2))
            return efficiency, "over_provisioned"

        # Under-provisioned (using cheaper model than recommended)
        else:
            difference = optimal_rank - used_rank
            # Penalize more for under-provisioning (could affect quality)
            efficiency = max(0.3, 1.0 - (difference * 0.25))
            return efficiency, "under_provisioned"
