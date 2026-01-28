#!/usr/bin/env python3
"""
Feedback Loop - Pattern detection and baseline updates

Analyzes session history to:
- Detect patterns (window overshoot, opus starvation, etc.)
- Generate optimization proposals
- Auto-apply high-confidence improvements
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict


class FeedbackLoop:
    """Autonomous feedback loop for session optimization."""

    def __init__(self):
        self.kernel_dir = Path.home() / ".claude" / "kernel"
        self.data_dir = Path.home() / ".claude" / "data"
        self.logs_dir = Path.home() / ".claude" / "logs"

        self.baselines_file = self.kernel_dir / "session-baselines.json"
        self.windows_log = self.data_dir / "session-windows.jsonl"
        self.optimizer_log = self.data_dir / "session-optimizer.jsonl"
        self.capacity_log = self.data_dir / "capacity-snapshots.jsonl"
        self.session_outcomes = self.data_dir / "session-outcomes.jsonl"
        self.feedback_log = self.logs_dir / "session-feedback.log"

        # Pattern definitions
        self.patterns = {
            "window_overshoot": {
                "signal": "Capacity exhausted before window end >3x",
                "action": "Decrease budget allocation rate",
                "target": "budgetThresholds.downgradeThreshold"
            },
            "opus_starvation": {
                "signal": "Complex tasks (>0.7) waiting, no Opus budget",
                "action": "Increase opusReservePercent",
                "target": "budgetThresholds.opusReservePercent"
            },
            "checkpoint_miss": {
                "signal": "Context cleared without checkpoint >3x",
                "action": "Lower checkpoint threshold",
                "target": "checkpointThresholds.messageCount"
            },
            "window_drift": {
                "signal": "Predicted vs actual window end >30min off",
                "action": "Update window duration estimate",
                "target": "windowPatterns.typicalDurationMs"
            },
            "quality_decline": {
                "signal": "Session quality trending down",
                "action": "Recommend model upgrade or break",
                "target": "checkpointThresholds.saturationLevel"
            }
        }

    def analyze_sessions(self, days: int = 30) -> Dict:
        """
        Analyze recent sessions for patterns.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        sessions = self._load_session_data(cutoff)

        analysis = {
            "sessionCount": len(sessions),
            "dateRange": {
                "start": (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(),
                "end": datetime.now(timezone.utc).isoformat()
            },
            "patterns": [],
            "metrics": {}
        }

        if not sessions:
            return analysis

        # Analyze window patterns
        window_analysis = self._analyze_window_patterns(sessions)
        analysis["metrics"]["windows"] = window_analysis

        # Analyze budget patterns
        budget_analysis = self._analyze_budget_patterns(sessions)
        analysis["metrics"]["budget"] = budget_analysis

        # Analyze quality patterns
        quality_analysis = self._analyze_quality_patterns(sessions)
        analysis["metrics"]["quality"] = quality_analysis

        # Detect patterns
        detected = self._detect_patterns(analysis["metrics"])
        analysis["patterns"] = detected

        return analysis

    def generate_proposals(self, analysis: Dict) -> List[Dict]:
        """
        Generate optimization proposals from analysis.
        """
        proposals = []
        baselines = self._load_baselines()

        for pattern in analysis.get("patterns", []):
            pattern_def = self.patterns.get(pattern["type"])
            if not pattern_def:
                continue

            proposal = {
                "id": f"prop-{datetime.now().strftime('%Y%m%d%H%M%S')}-{pattern['type'][:4]}",
                "pattern": pattern["type"],
                "signal": pattern_def["signal"],
                "action": pattern_def["action"],
                "target": pattern_def["target"],
                "confidence": pattern["confidence"],
                "evidence": pattern["evidence"],
                "suggestedValue": self._calculate_suggested_value(
                    pattern["type"],
                    pattern,
                    baselines
                ),
                "currentValue": self._get_current_value(pattern_def["target"], baselines),
                "createdAt": datetime.now().isoformat()
            }

            proposals.append(proposal)

        return proposals

    def apply_proposal(self, proposal: Dict, dry_run: bool = False) -> bool:
        """
        Apply a proposal to update baselines.
        """
        if proposal["confidence"] < 0.7:
            self._log(f"Skipped proposal {proposal['id']}: confidence {proposal['confidence']} < 0.7")
            return False

        baselines = self._load_baselines()
        target = proposal["target"]
        new_value = proposal["suggestedValue"]

        if dry_run:
            self._log(f"[DRY RUN] Would update {target} to {new_value}")
            return True

        # Update the target value
        self._set_value(target, new_value, baselines)

        # Add to research lineage
        if "researchLineage" not in baselines:
            baselines["researchLineage"] = []

        baselines["researchLineage"].append({
            "paper": "internal:feedback-loop",
            "title": f"Auto-optimization: {proposal['pattern']}",
            "applied": datetime.now().strftime("%Y-%m-%d"),
            "insight": f"{proposal['action']} based on {proposal['signal']}"
        })

        baselines["lastUpdated"] = datetime.now().isoformat()

        with open(self.baselines_file, "w") as f:
            json.dump(baselines, f, indent=2)

        self._log(f"Applied proposal {proposal['id']}: {target} = {new_value}")

        # Log to optimizer log
        self._log_event("proposal_applied", {
            "proposalId": proposal["id"],
            "pattern": proposal["pattern"],
            "target": target,
            "oldValue": proposal["currentValue"],
            "newValue": new_value
        })

        return True

    def auto_apply(self, min_confidence: float = 0.7, max_per_day: int = 3) -> List[Dict]:
        """
        Automatically apply high-confidence proposals.
        """
        analysis = self.analyze_sessions()
        proposals = self.generate_proposals(analysis)

        # Filter by confidence
        eligible = [p for p in proposals if p["confidence"] >= min_confidence]

        # Check daily limit
        today_applied = self._count_today_applications()
        remaining = max_per_day - today_applied

        applied = []
        for proposal in eligible[:remaining]:
            if self.apply_proposal(proposal):
                applied.append(proposal)

        return applied

    def _analyze_window_patterns(self, sessions: List[Dict]) -> Dict:
        """Analyze window-related patterns."""
        window_ends = []
        early_exhaustions = 0

        for session in sessions:
            window = session.get("window", {})
            budget = session.get("budget", {})

            # Check for early exhaustion
            if window.get("positionPercent", 0) < 80 and budget.get("utilizationPercent", 0) >= 85:
                early_exhaustions += 1

            if window.get("estimatedEndAt") and session.get("endedAt"):
                estimated = datetime.fromisoformat(window["estimatedEndAt"].replace("Z", "+00:00"))
                actual = datetime.fromisoformat(session["endedAt"].replace("Z", "+00:00"))
                drift = abs((actual - estimated).total_seconds() / 60)  # minutes
                window_ends.append(drift)

        return {
            "earlyExhaustions": early_exhaustions,
            "avgWindowDrift": sum(window_ends) / len(window_ends) if window_ends else 0,
            "windowDriftSamples": len(window_ends)
        }

    def _analyze_budget_patterns(self, sessions: List[Dict]) -> Dict:
        """Analyze budget-related patterns."""
        opus_starved = 0
        high_complexity_waiting = 0

        for session in sessions:
            budget = session.get("budget", {})
            queue = session.get("queue", {})

            # Check for Opus starvation
            used = budget.get("used", {})
            if used.get("opus", 0) == 0 and queue.get("highComplexityPending", 0) > 0:
                opus_starved += 1
                high_complexity_waiting += queue.get("highComplexityPending", 0)

        return {
            "opusStarvedSessions": opus_starved,
            "highComplexityWaiting": high_complexity_waiting
        }

    def _analyze_quality_patterns(self, sessions: List[Dict]) -> Dict:
        """Analyze quality patterns from session outcomes."""
        qualities = []
        checkpoint_misses = 0

        outcomes = self._load_session_outcomes()
        for outcome in outcomes[-30:]:  # Last 30 sessions
            if outcome.get("quality"):
                qualities.append(outcome["quality"])

        # Calculate trend
        if len(qualities) >= 10:
            first_half = sum(qualities[:len(qualities)//2]) / (len(qualities)//2)
            second_half = sum(qualities[len(qualities)//2:]) / (len(qualities) - len(qualities)//2)
            trend = second_half - first_half
        else:
            trend = 0

        return {
            "avgQuality": sum(qualities) / len(qualities) if qualities else 0,
            "qualityTrend": trend,
            "samples": len(qualities)
        }

    def _detect_patterns(self, metrics: Dict) -> List[Dict]:
        """Detect patterns from metrics."""
        detected = []

        # Window overshoot
        windows = metrics.get("windows", {})
        if windows.get("earlyExhaustions", 0) >= 3:
            detected.append({
                "type": "window_overshoot",
                "confidence": min(0.9, 0.5 + windows["earlyExhaustions"] * 0.1),
                "evidence": f"{windows['earlyExhaustions']} early exhaustions"
            })

        # Opus starvation
        budget = metrics.get("budget", {})
        if budget.get("opusStarvedSessions", 0) >= 3:
            detected.append({
                "type": "opus_starvation",
                "confidence": min(0.9, 0.5 + budget["opusStarvedSessions"] * 0.1),
                "evidence": f"{budget['opusStarvedSessions']} starved sessions"
            })

        # Window drift
        if windows.get("avgWindowDrift", 0) > 30:
            detected.append({
                "type": "window_drift",
                "confidence": min(0.85, 0.5 + windows["avgWindowDrift"] / 60 * 0.2),
                "evidence": f"Avg drift: {windows['avgWindowDrift']:.0f} minutes"
            })

        # Quality decline
        quality = metrics.get("quality", {})
        if quality.get("qualityTrend", 0) < -0.5:
            detected.append({
                "type": "quality_decline",
                "confidence": min(0.8, 0.5 + abs(quality["qualityTrend"]) * 0.3),
                "evidence": f"Quality trend: {quality['qualityTrend']:.2f}"
            })

        return detected

    def _calculate_suggested_value(self, pattern_type: str, pattern: Dict, baselines: Dict) -> any:
        """Calculate suggested new value for a pattern."""
        if pattern_type == "window_overshoot":
            current = baselines.get("budgetThresholds", {}).get("downgradeThreshold", 0.85)
            return max(0.6, current - 0.05)

        elif pattern_type == "opus_starvation":
            current = baselines.get("budgetThresholds", {}).get("opusReservePercent", 0.20)
            return min(0.35, current + 0.05)

        elif pattern_type == "checkpoint_miss":
            current = baselines.get("checkpointThresholds", {}).get("messageCount", 50)
            return max(30, current - 10)

        elif pattern_type == "window_drift":
            current = baselines.get("windowPatterns", {}).get("typicalDurationMs", 18000000)
            return int(current * 0.9)  # Reduce by 10%

        elif pattern_type == "quality_decline":
            current = baselines.get("checkpointThresholds", {}).get("saturationLevel", 0.70)
            return max(0.50, current - 0.10)

        return None

    def _get_current_value(self, target: str, baselines: Dict) -> any:
        """Get current value from baselines using dot notation."""
        parts = target.split(".")
        value = baselines
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def _set_value(self, target: str, value: any, baselines: Dict):
        """Set value in baselines using dot notation."""
        parts = target.split(".")
        obj = baselines
        for part in parts[:-1]:
            if part not in obj:
                obj[part] = {}
            obj = obj[part]
        obj[parts[-1]] = value

    def _load_baselines(self) -> Dict:
        """Load session baselines."""
        if self.baselines_file.exists():
            with open(self.baselines_file) as f:
                return json.load(f)
        return {}

    def _load_session_data(self, cutoff: datetime) -> List[Dict]:
        """Load session data from logs."""
        sessions = []

        # Load from optimizer log
        if self.optimizer_log.exists():
            with open(self.optimizer_log) as f:
                for line in f:
                    try:
                        event = json.loads(line)
                        ts = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                        if ts >= cutoff:
                            sessions.append(event)
                    except (json.JSONDecodeError, KeyError):
                        continue

        return sessions

    def _load_session_outcomes(self) -> List[Dict]:
        """Load session outcomes."""
        outcomes = []

        if self.session_outcomes.exists():
            with open(self.session_outcomes) as f:
                for line in f:
                    try:
                        outcome = json.loads(line)
                        outcomes.append(outcome)
                    except json.JSONDecodeError:
                        continue

        return outcomes

    def _count_today_applications(self) -> int:
        """Count proposals applied today."""
        if not self.optimizer_log.exists():
            return 0

        today = datetime.now().strftime("%Y-%m-%d")
        count = 0

        with open(self.optimizer_log) as f:
            for line in f:
                try:
                    event = json.loads(line)
                    if event.get("event") == "proposal_applied":
                        if event.get("timestamp", "").startswith(today):
                            count += 1
                except json.JSONDecodeError:
                    continue

        return count

    def _log(self, message: str):
        """Log to feedback log."""
        self.feedback_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.feedback_log, "a") as f:
            f.write(f"{datetime.now().isoformat()} {message}\n")

    def _log_event(self, event_type: str, data: Dict):
        """Log event to optimizer log."""
        event = {
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            **data
        }
        with open(self.optimizer_log, "a") as f:
            f.write(json.dumps(event) + "\n")


if __name__ == "__main__":
    import sys

    loop = FeedbackLoop()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "analyze":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            analysis = loop.analyze_sessions(days)
            print(f"Analyzed {analysis['sessionCount']} sessions")
            print(f"\nPatterns detected: {len(analysis['patterns'])}")
            for pattern in analysis["patterns"]:
                print(f"  - {pattern['type']}: {pattern['evidence']} (conf: {pattern['confidence']})")

        elif cmd == "propose":
            analysis = loop.analyze_sessions()
            proposals = loop.generate_proposals(analysis)
            print(f"Generated {len(proposals)} proposals:")
            for p in proposals:
                print(f"\n{p['id']}:")
                print(f"  Pattern: {p['pattern']}")
                print(f"  Action: {p['action']}")
                print(f"  Confidence: {p['confidence']}")
                print(f"  Current: {p['currentValue']} -> Suggested: {p['suggestedValue']}")

        elif cmd == "apply":
            analysis = loop.analyze_sessions()
            proposals = loop.generate_proposals(analysis)
            for p in proposals:
                if p["confidence"] >= 0.7:
                    loop.apply_proposal(p)
                    print(f"Applied: {p['id']}")

        elif cmd == "auto-apply":
            applied = loop.auto_apply()
            print(f"Auto-applied {len(applied)} proposals")
            for p in applied:
                print(f"  - {p['id']}: {p['pattern']}")

        elif cmd == "dry-run":
            analysis = loop.analyze_sessions()
            proposals = loop.generate_proposals(analysis)
            for p in proposals:
                loop.apply_proposal(p, dry_run=True)

    else:
        print("Feedback Loop - Session optimization feedback")
        print("")
        print("Commands:")
        print("  analyze [days]   - Analyze recent sessions")
        print("  propose          - Generate proposals")
        print("  apply            - Apply eligible proposals")
        print("  auto-apply       - Auto-apply high confidence")
        print("  dry-run          - Preview without applying")
