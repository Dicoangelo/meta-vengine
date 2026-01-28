"""
ProductivityAnalyzerAgent - Analyzes session productivity

Measures:
- Read/write ratio (exploration vs implementation)
- LOC velocity (lines per hour)
- Tool efficiency (successful operations per minute)
- Output vs exploration balance
"""

from typing import Dict
from . import SessionAnalysisAgent


class ProductivityAnalyzerAgent(SessionAnalysisAgent):
    """Analyzes session productivity metrics."""

    def analyze(self, transcript: Dict) -> Dict:
        """Calculate productivity metrics."""

        # Extract tool operations
        reads = len(self._extract_tool_calls(transcript, "Read"))
        writes = len(self._extract_tool_calls(transcript, "Write"))
        edits = len(self._extract_tool_calls(transcript, "Edit"))
        greps = len(self._extract_tool_calls(transcript, "Grep"))
        globs = len(self._extract_tool_calls(transcript, "Glob"))
        bash = len(self._extract_tool_calls(transcript, "Bash"))

        # Calculate ratios
        total_ops = reads + writes + edits + greps + globs + bash
        exploration_ops = reads + greps + globs
        implementation_ops = writes + edits

        read_write_ratio = (exploration_ops / max(implementation_ops, 1)
                           if implementation_ops > 0 else float(exploration_ops))

        # Estimate LOC
        loc_changed = self._estimate_loc_changed(transcript)

        # Duration
        duration_minutes = self._estimate_duration(transcript)

        # LOC velocity (lines per hour)
        loc_per_hour = (loc_changed / duration_minutes * 60
                       if duration_minutes > 0 else 0)

        # Tool efficiency (successful ops per minute)
        errors = len(transcript.get("errors", []))
        successful_ops = total_ops - errors
        ops_per_minute = (successful_ops / duration_minutes
                         if duration_minutes > 0 else 0)

        # Productivity score (0-1)
        productivity_score = self._calculate_productivity_score(
            loc_per_hour=loc_per_hour,
            ops_per_minute=ops_per_minute,
            read_write_ratio=read_write_ratio,
            implementation_ops=implementation_ops
        )

        # Determine productivity level
        level = self._determine_productivity_level(productivity_score)

        # DQ components
        validity = 0.75
        specificity = 0.70 + (min(total_ops, 20) / 20 * 0.2)
        correctness = 0.75

        return {
            "summary": f"{level} productivity (LOC: {loc_changed}, velocity: {loc_per_hour:.0f}/hr)",
            "productivity_score": productivity_score,
            "dq_score": self._calculate_dq_score(validity, specificity, correctness),
            "confidence": self._calculate_confidence(total_ops, duration_minutes),
            "data": {
                "productivity_score": productivity_score,
                "level": level,
                "loc_changed": loc_changed,
                "loc_per_hour": loc_per_hour,
                "ops_per_minute": ops_per_minute,
                "read_write_ratio": read_write_ratio,
                "operations": {
                    "total": total_ops,
                    "exploration": exploration_ops,
                    "implementation": implementation_ops,
                    "reads": reads,
                    "writes": writes,
                    "edits": edits,
                    "greps": greps,
                    "globs": globs,
                    "bash": bash
                },
                "duration_minutes": duration_minutes
            }
        }

    def _calculate_productivity_score(
        self,
        loc_per_hour: float,
        ops_per_minute: float,
        read_write_ratio: float,
        implementation_ops: int
    ) -> float:
        """Calculate overall productivity score (0-1)."""

        score = 0.0

        # Component 1: LOC velocity (0-0.4)
        if loc_per_hour >= 200:
            score += 0.4
        elif loc_per_hour >= 100:
            score += 0.3
        elif loc_per_hour >= 50:
            score += 0.2
        elif loc_per_hour >= 20:
            score += 0.1

        # Component 2: Operations per minute (0-0.3)
        if ops_per_minute >= 2.0:
            score += 0.3
        elif ops_per_minute >= 1.0:
            score += 0.2
        elif ops_per_minute >= 0.5:
            score += 0.1

        # Component 3: Implementation activity (0-0.2)
        if implementation_ops >= 5:
            score += 0.2
        elif implementation_ops >= 2:
            score += 0.1

        # Component 4: Balanced exploration/implementation (0-0.1)
        # Ideal ratio is around 2-3 (some exploration, more implementation)
        if 1.5 <= read_write_ratio <= 4.0:
            score += 0.1

        return min(1.0, score)

    def _determine_productivity_level(self, score: float) -> str:
        """Determine productivity level from score."""
        if score >= 0.8:
            return "Very High"
        elif score >= 0.6:
            return "High"
        elif score >= 0.4:
            return "Moderate"
        elif score >= 0.2:
            return "Low"
        else:
            return "Very Low"

    def _estimate_loc_changed(self, transcript: Dict) -> int:
        """Estimate lines of code changed."""

        writes = self._extract_tool_calls(transcript, "Write")
        edits = self._extract_tool_calls(transcript, "Edit")

        loc = 0

        # Writes: count lines in content
        for write in writes:
            content = write.get("input", {}).get("content", "")
            if content:
                loc += len(str(content).split('\n'))

        # Edits: estimate ~10-15 lines per edit
        loc += len(edits) * 12

        return loc

    def _estimate_duration(self, transcript: Dict) -> int:
        """Estimate session duration in minutes."""

        metadata = transcript.get("metadata", {})

        # Try to get from metadata
        if "start_time" in metadata and "end_time" in metadata:
            start = metadata["start_time"]
            end = metadata["end_time"]

            # Ensure they are numeric
            try:
                if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                    return max(1, int((end - start) / 60))
            except (TypeError, ValueError):
                pass

        # Fallback: estimate from message count
        messages = transcript.get("messages", [])
        return max(1, len(messages) // 2 * 2)

    def _calculate_confidence(self, total_ops: int, duration_minutes: int) -> float:
        """Calculate confidence in productivity analysis."""

        confidence = 0.5

        # More operations = higher confidence
        if total_ops >= 15:
            confidence += 0.2
        elif total_ops >= 5:
            confidence += 0.1

        # Longer sessions = higher confidence
        if duration_minutes >= 20:
            confidence += 0.15
        elif duration_minutes >= 10:
            confidence += 0.1

        return min(0.85, confidence)
