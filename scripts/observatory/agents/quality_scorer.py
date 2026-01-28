"""
QualityScorerAgent - Scores session quality 1-5

Analyzes productivity metrics to determine overall session quality:
- 5: Excellent - High LOC, low errors, smooth flow
- 4: Good - Solid progress, minor issues
- 3: Fair - Moderate progress, some friction
- 2: Poor - Limited progress, significant issues
- 1: Very Poor - No meaningful progress
"""

from typing import Dict
from . import SessionAnalysisAgent


class QualityScorerAgent(SessionAnalysisAgent):
    """Scores session quality 1-5 based on productivity metrics."""

    def analyze(self, transcript: Dict) -> Dict:
        """Score session quality based on multiple factors."""

        # Extract metrics
        metrics = self._extract_metrics(transcript)

        # Calculate quality score
        quality, validity, specificity, correctness = self._calculate_quality(metrics)

        return {
            "summary": f"Quality: {quality}/5",
            "quality": quality,
            "dq_score": self._calculate_dq_score(validity, specificity, correctness),
            "confidence": self._calculate_confidence(metrics),
            "data": {
                "quality": quality,
                "metrics": metrics
            }
        }

    def _extract_metrics(self, transcript: Dict) -> Dict:
        """Extract all relevant metrics for quality scoring."""

        # File operations
        writes = len(self._extract_tool_calls(transcript, "Write"))
        edits = len(self._extract_tool_calls(transcript, "Edit"))
        reads = len(self._extract_tool_calls(transcript, "Read"))

        # Tool success rate
        tools = transcript.get("tools", [])
        errors = len(transcript.get("errors", []))
        success_rate = (len(tools) - errors) / max(len(tools), 1)

        # Message flow (smoothness)
        messages = transcript.get("messages", [])
        assistant_msgs = self._extract_messages(transcript, "assistant")

        # Estimate LOC changed (rough heuristic)
        loc_changed = self._estimate_loc_changed(transcript)

        # Session duration (from metadata or message timestamps)
        duration_minutes = self._estimate_duration(transcript)

        # Files modified count
        files_modified = writes + edits

        return {
            "writes": writes,
            "edits": edits,
            "reads": reads,
            "files_modified": files_modified,
            "loc_changed": loc_changed,
            "success_rate": success_rate,
            "total_tools": len(tools),
            "errors": errors,
            "message_count": len(messages),
            "assistant_messages": len(assistant_msgs),
            "duration_minutes": duration_minutes
        }

    def _calculate_quality(self, metrics: Dict):
        """Calculate quality score 1-5 with DQ components."""

        score = 0
        factors = []

        # Factor 1: File changes (0-2 points)
        if metrics["files_modified"] >= 5:
            score += 2
            factors.append("high_file_activity")
        elif metrics["files_modified"] >= 2:
            score += 1
            factors.append("moderate_file_activity")

        # Factor 2: LOC changed (0-1 point)
        if metrics["loc_changed"] >= 100:
            score += 1
            factors.append("high_loc")
        elif metrics["loc_changed"] >= 20:
            score += 0.5

        # Factor 3: Tool success rate (0-1 point)
        if metrics["success_rate"] >= 0.9:
            score += 1
            factors.append("high_success_rate")
        elif metrics["success_rate"] >= 0.7:
            score += 0.5

        # Factor 4: Error count (-1 to 0 points)
        if metrics["errors"] > 10:
            score -= 0.5
            factors.append("high_errors")
        elif metrics["errors"] > 5:
            score -= 0.25

        # Factor 5: Productivity (LOC per hour) (0-0.5 point)
        if metrics["duration_minutes"] > 0:
            loc_per_hour = metrics["loc_changed"] / (metrics["duration_minutes"] / 60)
            if loc_per_hour >= 200:
                score += 0.5
                factors.append("high_productivity")

        # Normalize to 1-5 scale
        # Raw score range is roughly -1 to 4.5
        # Map to 1-5
        quality = max(1, min(5, int(round(score + 1))))

        # DQ components based on quality and factors
        validity = 0.6 + (quality / 5 * 0.3)  # 0.6-0.9
        specificity = 0.7 + (len(factors) / 6 * 0.2)  # More factors = higher specificity
        correctness = 0.65 + (metrics["success_rate"] * 0.3)  # 0.65-0.95

        return quality, validity, specificity, correctness

    def _estimate_loc_changed(self, transcript: Dict) -> int:
        """Estimate lines of code changed (rough heuristic)."""

        # Count Write and Edit operations
        writes = self._extract_tool_calls(transcript, "Write")
        edits = self._extract_tool_calls(transcript, "Edit")

        loc = 0

        # Writes: estimate from content length
        for write in writes:
            content = write.get("input", {}).get("content", "")
            if content:
                loc += len(content.split('\n'))

        # Edits: harder to estimate, use heuristic (avg ~10 lines per edit)
        loc += len(edits) * 10

        return loc

    def _estimate_duration(self, transcript: Dict) -> int:
        """Estimate session duration in minutes."""

        messages = transcript.get("messages", [])
        if len(messages) < 2:
            return 1

        # Try to get timestamps from metadata
        metadata = transcript.get("metadata", {})
        if "start_time" in metadata and "end_time" in metadata:
            start = metadata["start_time"]
            end = metadata["end_time"]

            # Handle both numeric and string timestamps
            if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                # Numeric timestamps in seconds
                return max(1, int((end - start) / 60))
            elif isinstance(start, str) and isinstance(end, str):
                # ISO timestamp strings - try to parse
                try:
                    from datetime import datetime
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                    duration_seconds = (end_dt - start_dt).total_seconds()
                    return max(1, int(duration_seconds / 60))
                except:
                    pass  # Fall through to fallback

        # Fallback: estimate 2 minutes per message pair
        return max(1, len(messages) // 2 * 2)

    def _calculate_confidence(self, metrics: Dict) -> float:
        """Calculate confidence in quality score."""

        confidence = 0.6

        # More data = higher confidence
        if metrics["total_tools"] >= 10:
            confidence += 0.15

        if metrics["files_modified"] >= 2:
            confidence += 0.1

        if metrics["message_count"] >= 10:
            confidence += 0.1

        return min(0.9, confidence)
