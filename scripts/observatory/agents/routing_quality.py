"""
RoutingQualityAgent - Analyzes routing decision quality

Evaluates DQ scores from routing decisions (if available).
Determines routing accuracy and decision quality trends.
"""

from typing import Dict, List
from . import SessionAnalysisAgent


class RoutingQualityAgent(SessionAnalysisAgent):
    """Analyzes quality of routing decisions in session."""

    def analyze(self, transcript: Dict) -> Dict:
        """Analyze routing decision quality from DQ scores."""

        # Extract routing decisions from metadata/events
        routing_decisions = self._extract_routing_decisions(transcript)

        if not routing_decisions:
            return self._default_result()

        # Calculate average DQ score
        avg_dq = self._calculate_average_dq(routing_decisions)

        # Analyze routing accuracy
        routing_accuracy = self._analyze_routing_accuracy(routing_decisions, transcript)

        # Check for routing issues
        issues = self._detect_routing_issues(routing_decisions)

        # DQ components
        validity = 0.80
        specificity = 0.75
        correctness = avg_dq  # Use average routing DQ as correctness

        return {
            "summary": f"Avg DQ: {avg_dq:.3f}, Accuracy: {routing_accuracy:.1%}",
            "avg_dq": avg_dq,
            "dq_score": self._calculate_dq_score(validity, specificity, correctness),
            "confidence": self._calculate_confidence(len(routing_decisions)),
            "data": {
                "avg_dq": avg_dq,
                "routing_accuracy": routing_accuracy,
                "decision_count": len(routing_decisions),
                "issues": issues,
                "decisions": routing_decisions
            }
        }

    def _extract_routing_decisions(self, transcript: Dict) -> List[Dict]:
        """Extract routing decisions from transcript."""

        decisions = []

        # Check metadata for routing info
        metadata = transcript.get("metadata", {})
        if "routing_decision" in metadata:
            decisions.append(metadata["routing_decision"])

        # Check events for routing decisions
        events = transcript.get("events", [])
        for event in events:
            if event.get("type") == "routing_decision" or event.get("event") == "routing_decision":
                decision = {
                    "dq_score": event.get("dq_score", 0.5),
                    "complexity": event.get("complexity", 0.5),
                    "model": event.get("model", "unknown"),
                    "timestamp": event.get("timestamp", 0)
                }
                decisions.append(decision)

        # If no explicit routing decisions, try to infer from messages
        if not decisions:
            decisions = self._infer_routing_from_messages(transcript)

        return decisions

    def _infer_routing_from_messages(self, transcript: Dict) -> List[Dict]:
        """Infer routing decisions from message patterns."""

        # Look for routing-related messages in assistant messages
        messages = self._extract_messages(transcript, "assistant")
        decisions = []

        for msg in messages:
            content = str(msg.get("content", ""))

            # Look for DQ score patterns like [DQ:0.75 C:0.45]
            import re
            pattern = r'\[DQ:([\d.]+)\s+C:([\d.]+)\]'
            matches = re.findall(pattern, content)

            for match in matches:
                dq_score = float(match[0])
                complexity = float(match[1])

                # Infer model from DQ score
                if dq_score < 0.3:
                    model = "haiku"
                elif dq_score < 0.7:
                    model = "sonnet"
                else:
                    model = "opus"

                decisions.append({
                    "dq_score": dq_score,
                    "complexity": complexity,
                    "model": model,
                    "inferred": True
                })

        return decisions

    def _calculate_average_dq(self, decisions: List[Dict]) -> float:
        """Calculate average DQ score across all decisions."""

        dq_scores = [d.get("dq_score", 0.5) for d in decisions]

        if not dq_scores:
            return 0.5

        return sum(dq_scores) / len(dq_scores)

    def _analyze_routing_accuracy(self, decisions: List[Dict], transcript: Dict) -> float:
        """Analyze routing accuracy based on outcomes."""

        # If we have outcome information, check if routing was appropriate
        # For now, use a heuristic based on DQ scores

        # High DQ scores generally indicate good routing
        avg_dq = self._calculate_average_dq(decisions)

        # Normalize to accuracy percentage
        # DQ 0.8+ = 90-100% accuracy
        # DQ 0.6-0.8 = 75-90% accuracy
        # DQ 0.4-0.6 = 60-75% accuracy
        # DQ <0.4 = 40-60% accuracy

        if avg_dq >= 0.8:
            accuracy = 0.90 + (avg_dq - 0.8) * 0.5  # 90-100%
        elif avg_dq >= 0.6:
            accuracy = 0.75 + (avg_dq - 0.6) * 0.75  # 75-90%
        elif avg_dq >= 0.4:
            accuracy = 0.60 + (avg_dq - 0.4) * 0.75  # 60-75%
        else:
            accuracy = 0.40 + avg_dq  # 40-60%

        return min(1.0, accuracy)

    def _detect_routing_issues(self, decisions: List[Dict]) -> List[str]:
        """Detect potential routing issues."""

        issues = []

        # Issue 1: Consistently low DQ scores
        low_dq_count = sum(1 for d in decisions if d.get("dq_score", 0.5) < 0.4)
        if low_dq_count > len(decisions) * 0.3:
            issues.append(f"High proportion of low DQ scores ({low_dq_count}/{len(decisions)})")

        # Issue 2: High variance in DQ scores
        dq_scores = [d.get("dq_score", 0.5) for d in decisions]
        if len(dq_scores) >= 3:
            variance = sum((x - sum(dq_scores)/len(dq_scores))**2 for x in dq_scores) / len(dq_scores)
            if variance > 0.1:
                issues.append(f"High DQ variance ({variance:.3f}) - inconsistent routing quality")

        # Issue 3: Model switching (might indicate routing uncertainty)
        models = [d.get("model", "unknown") for d in decisions]
        unique_models = set(models)
        if len(unique_models) > 2 and len(decisions) < 10:
            issues.append(f"Multiple model switches in short session ({len(unique_models)} models)")

        return issues

    def _calculate_confidence(self, decision_count: int) -> float:
        """Calculate confidence based on number of decisions."""

        if decision_count >= 5:
            return 0.85
        elif decision_count >= 2:
            return 0.70
        elif decision_count >= 1:
            return 0.60
        else:
            return 0.40

    def _default_result(self) -> Dict:
        """Return default result when no routing decisions found."""
        return {
            "summary": "No routing decisions found",
            "avg_dq": 0.5,
            "dq_score": self._calculate_dq_score(0.5, 0.5, 0.5),
            "confidence": 0.3,
            "data": {
                "avg_dq": 0.5,
                "routing_accuracy": 0.5,
                "decision_count": 0,
                "issues": ["No routing decisions found in session"],
                "decisions": []
            }
        }
