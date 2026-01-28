#!/usr/bin/env python3
"""
Session Health Agent

Monitors context saturation, checkpoint timing, and overall session health.
Provides DQ-scored analysis of session wellness.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple


class SessionHealthAgent:
    """
    Agent for monitoring session health.

    Weight in ACE consensus: 0.15
    """

    def __init__(self):
        self.kernel_dir = Path.home() / ".claude" / "kernel"
        self.data_dir = Path.home() / ".claude" / "data"
        self.state_file = self.kernel_dir / "session-state.json"
        self.baselines_file = self.kernel_dir / "session-baselines.json"
        self.activity_file = self.data_dir / "activity-events.jsonl"

    def analyze(self, context: Dict = None) -> Dict:
        """
        Analyze session health.

        Returns:
            DQ-scored analysis result
        """
        state = self._load_state()
        baselines = self._load_baselines()

        ctx = state.get("context", {})
        window = state.get("window", {})

        # Calculate health metrics
        saturation = self._calculate_saturation(ctx, baselines)
        checkpoint_status = self._check_checkpoint_timing(ctx, baselines)
        session_quality = self._assess_session_quality(state)
        fatigue_indicators = self._detect_fatigue(state)

        # Overall health score
        health_score = self._calculate_health_score(
            saturation, checkpoint_status, session_quality, fatigue_indicators
        )

        # Generate alerts
        alerts = self._generate_alerts(
            saturation, checkpoint_status, fatigue_indicators
        )

        # Calculate DQ scores
        validity = 0.85 if ctx.get("messages") else 0.4
        specificity = min(0.9, 0.5 + health_score * 0.4)
        correctness = health_score

        return {
            "summary": f"Health: {health_score*100:.0f}% | Saturation: {saturation['level']*100:.0f}% | Checkpoint: {checkpoint_status['status']}",
            "dq_score": {
                "validity": validity,
                "specificity": specificity,
                "correctness": correctness
            },
            "confidence": health_score,
            "data": {
                "healthScore": round(health_score, 2),
                "saturation": saturation,
                "checkpoint": checkpoint_status,
                "sessionQuality": session_quality,
                "fatigueIndicators": fatigue_indicators,
                "alerts": alerts,
                "recommendations": self._generate_recommendations(
                    health_score, saturation, checkpoint_status, fatigue_indicators
                )
            }
        }

    def _calculate_saturation(self, ctx: Dict, baselines: Dict) -> Dict:
        """Calculate context saturation level."""
        messages = ctx.get("messages", 0)
        current_saturation = ctx.get("saturation", 0)

        thresholds = baselines.get("checkpointThresholds", {})
        saturation_threshold = thresholds.get("saturationLevel", 0.70)
        message_threshold = thresholds.get("messageCount", 50)

        # Calculate saturation from messages if not provided
        if current_saturation == 0:
            current_saturation = min(1.0, messages / (message_threshold * 2))

        # Determine status
        if current_saturation > 0.9:
            status = "critical"
        elif current_saturation > saturation_threshold:
            status = "elevated"
        elif current_saturation > 0.5:
            status = "moderate"
        else:
            status = "healthy"

        return {
            "level": current_saturation,
            "status": status,
            "messages": messages,
            "threshold": saturation_threshold,
            "clearRecommended": current_saturation > saturation_threshold
        }

    def _check_checkpoint_timing(self, ctx: Dict, baselines: Dict) -> Dict:
        """Check if checkpoint is recommended."""
        messages = ctx.get("messages", 0)
        next_checkpoint = ctx.get("nextCheckpoint", 50)

        thresholds = baselines.get("checkpointThresholds", {})
        message_threshold = thresholds.get("messageCount", 50)

        messages_until = next_checkpoint - messages

        if messages >= next_checkpoint:
            status = "due"
            urgency = "high"
        elif messages_until <= 10:
            status = "soon"
            urgency = "medium"
        else:
            status = "ok"
            urgency = "low"

        return {
            "status": status,
            "urgency": urgency,
            "messagesUntil": max(0, messages_until),
            "nextCheckpoint": next_checkpoint,
            "recommendation": "Create checkpoint now" if status == "due" else None
        }

    def _assess_session_quality(self, state: Dict) -> Dict:
        """Assess overall session quality."""
        # Load recent activity for quality assessment
        activity = self._load_recent_activity(hours=1)

        if not activity:
            return {
                "score": 0.5,
                "metrics": {},
                "trend": "unknown"
            }

        # Calculate metrics
        total_events = len(activity)
        successful = sum(1 for e in activity if e.get("success", True))
        success_rate = successful / total_events if total_events > 0 else 1.0

        # Check for error patterns
        errors = [e for e in activity if not e.get("success", True)]
        error_rate = len(errors) / total_events if total_events > 0 else 0

        # Calculate quality score
        quality_score = success_rate * 0.6 + (1 - error_rate) * 0.4

        # Determine trend
        if total_events < 5:
            trend = "insufficient_data"
        elif error_rate > 0.2:
            trend = "declining"
        elif success_rate > 0.95:
            trend = "excellent"
        else:
            trend = "stable"

        return {
            "score": round(quality_score, 2),
            "metrics": {
                "totalEvents": total_events,
                "successRate": round(success_rate, 2),
                "errorRate": round(error_rate, 2)
            },
            "trend": trend
        }

    def _detect_fatigue(self, state: Dict) -> Dict:
        """Detect session fatigue indicators."""
        indicators = []
        fatigue_level = 0.0

        ctx = state.get("context", {})
        window = state.get("window", {})

        # High message count
        messages = ctx.get("messages", 0)
        if messages > 100:
            indicators.append("High message count")
            fatigue_level += 0.3
        elif messages > 50:
            indicators.append("Moderate message count")
            fatigue_level += 0.1

        # Late window position
        position = window.get("positionPercent", 0)
        if position > 80:
            indicators.append("Late in session window")
            fatigue_level += 0.2

        # High saturation
        saturation = ctx.get("saturation", 0)
        if saturation > 0.8:
            indicators.append("High context saturation")
            fatigue_level += 0.2

        # Low remaining capacity
        capacity = state.get("capacity", {})
        tier = capacity.get("tier", "COMFORTABLE")
        if tier == "CRITICAL":
            indicators.append("Critical capacity")
            fatigue_level += 0.3
        elif tier == "LOW":
            indicators.append("Low capacity")
            fatigue_level += 0.15

        return {
            "level": min(1.0, fatigue_level),
            "indicators": indicators,
            "breakRecommended": fatigue_level > 0.5
        }

    def _calculate_health_score(
        self,
        saturation: Dict,
        checkpoint: Dict,
        quality: Dict,
        fatigue: Dict
    ) -> float:
        """Calculate overall health score."""
        # Component scores
        saturation_score = 1.0 - saturation["level"]
        checkpoint_score = 1.0 if checkpoint["status"] == "ok" else 0.7 if checkpoint["status"] == "soon" else 0.4
        quality_score = quality.get("score", 0.5)
        fatigue_score = 1.0 - fatigue["level"]

        # Weighted average
        health = (
            saturation_score * 0.3 +
            checkpoint_score * 0.2 +
            quality_score * 0.3 +
            fatigue_score * 0.2
        )

        return round(health, 2)

    def _generate_alerts(
        self,
        saturation: Dict,
        checkpoint: Dict,
        fatigue: Dict
    ) -> List[Dict]:
        """Generate health alerts."""
        alerts = []

        if saturation["status"] == "critical":
            alerts.append({
                "severity": "high",
                "type": "saturation",
                "message": "Context saturation critical - clear recommended"
            })
        elif saturation["status"] == "elevated":
            alerts.append({
                "severity": "medium",
                "type": "saturation",
                "message": "Context saturation elevated - consider clearing soon"
            })

        if checkpoint["status"] == "due":
            alerts.append({
                "severity": "high",
                "type": "checkpoint",
                "message": "Checkpoint overdue - save session state"
            })
        elif checkpoint["status"] == "soon":
            alerts.append({
                "severity": "low",
                "type": "checkpoint",
                "message": f"Checkpoint in {checkpoint['messagesUntil']} messages"
            })

        if fatigue["breakRecommended"]:
            alerts.append({
                "severity": "medium",
                "type": "fatigue",
                "message": "Session fatigue detected - consider taking a break"
            })

        return alerts

    def _generate_recommendations(
        self,
        health: float,
        saturation: Dict,
        checkpoint: Dict,
        fatigue: Dict
    ) -> List[str]:
        """Generate health recommendations."""
        recommendations = []

        if health < 0.5:
            recommendations.append("Session health low - consider fresh start")

        if saturation["clearRecommended"]:
            recommendations.append("Run /clear to reset context")

        if checkpoint["status"] == "due":
            recommendations.append("Run /save to checkpoint session")

        if fatigue["breakRecommended"]:
            recommendations.append("Take a short break before continuing")

        for indicator in fatigue.get("indicators", []):
            if "High message count" in indicator:
                recommendations.append("Batch remaining work or start new session")

        if not recommendations:
            recommendations.append("Session healthy - continue normally")

        return recommendations

    def _load_recent_activity(self, hours: int = 1) -> List[Dict]:
        """Load recent activity events."""
        if not self.activity_file.exists():
            return []

        cutoff = datetime.now() - timedelta(hours=hours)
        events = []

        with open(self.activity_file) as f:
            for line in f:
                try:
                    event = json.loads(line)
                    ts_val = event.get("timestamp", "")
                    if ts_val:
                        # Handle both int (unix timestamp) and string (ISO format)
                        if isinstance(ts_val, (int, float)):
                            ts = datetime.fromtimestamp(ts_val)
                        else:
                            ts = datetime.fromisoformat(str(ts_val).replace("Z", "+00:00"))
                        if ts >= cutoff:
                            events.append(event)
                except (json.JSONDecodeError, ValueError, OSError):
                    continue

        return events

    def _load_state(self) -> Dict:
        """Load session state."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {}

    def _load_baselines(self) -> Dict:
        """Load session baselines."""
        if self.baselines_file.exists():
            with open(self.baselines_file) as f:
                return json.load(f)
        return {}


if __name__ == "__main__":
    agent = SessionHealthAgent()
    result = agent.analyze()
    print(json.dumps(result, indent=2))
