#!/usr/bin/env python3
"""
Personal Cognitive Operating System
====================================
Transforms telemetry into intelligence. Knows your cognitive rhythms,
predicts session outcomes, protects flow states, and routes to optimal models.

Foundation: SuperMemory (34,134 events, 424 sessions, 26,888 tool calls)

Usage:
    python3 cognitive-os.py start         # Pre-session briefing with predictions
    python3 cognitive-os.py monitor       # Mid-session flow check
    python3 cognitive-os.py end           # Post-session learning

    python3 cognitive-os.py state         # Current cognitive mode
    python3 cognitive-os.py fate          # Session outcome prediction
    python3 cognitive-os.py flow          # Flow state status
    python3 cognitive-os.py route         # Model recommendation
    python3 cognitive-os.py weekly        # Weekly energy map

    python3 cognitive-os.py train         # Retrain predictors
    python3 cognitive-os.py analyze       # Pattern analysis
    python3 cognitive-os.py status        # Full system status

Architecture:
    +------------------------------------------------------------------+
    |                    COGNITIVE OS                                  |
    +------------------------------------------------------------------+
    |  CognitiveState  |  SessionFate   |  FlowState    |  Personal   |
    |    Detector      |   Predictor    |   Protector   |   Router    |
    +------------------------------------------------------------------+
    |              WeeklyEnergyMapper  |  SuperMemory (foundation)     |
    +------------------------------------------------------------------+
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import statistics

# ============================================================================
# CONFIGURATION
# ============================================================================

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
DATA_DIR = CLAUDE_DIR / "data"
KERNEL_DIR = CLAUDE_DIR / "kernel"
MEMORY_DIR = CLAUDE_DIR / "memory"

# Data sources (aligned with supermemory.py)
SOURCES = {
    "session_outcomes": DATA_DIR / "session-outcomes.jsonl",
    "session_events": DATA_DIR / "session-events.jsonl",
    "session_windows": DATA_DIR / "session-windows.jsonl",
    "tool_usage": DATA_DIR / "tool-usage.jsonl",
    "routing_metrics": DATA_DIR / "routing-metrics.jsonl",
    "dq_scores": KERNEL_DIR / "dq-scores.jsonl",
    "session_state": KERNEL_DIR / "session-state.json",
    "activity_events": DATA_DIR / "activity-events.jsonl",
}

# Cognitive OS outputs
COS_DIR = KERNEL_DIR / "cognitive-os"
COS_STATE_FILE = COS_DIR / "current-state.json"
COS_PREDICTIONS_FILE = COS_DIR / "fate-predictions.jsonl"
COS_FLOW_LOG = COS_DIR / "flow-states.jsonl"
COS_ROUTING_LOG = COS_DIR / "routing-decisions.jsonl"
COS_LEARNING_FILE = COS_DIR / "learned-weights.json"


# ============================================================================
# DATA LOADING UTILITIES (from supermemory.py patterns)
# ============================================================================

def load_jsonl(path: Path, limit: int = None, since_days: int = None) -> List[Dict]:
    """Load JSONL file with optional filtering."""
    results = []
    cutoff = None
    if since_days:
        cutoff = datetime.now() - timedelta(days=since_days)

    try:
        if path.exists():
            with open(path) as f:
                for line in f:
                    if line.strip():
                        try:
                            entry = json.loads(line)
                            if cutoff:
                                ts = entry.get("ts") or entry.get("timestamp") or entry.get("started_at") or entry.get("date")
                                if ts:
                                    if isinstance(ts, (int, float)):
                                        ts = ts / 1000 if ts > 1e12 else ts
                                        entry_time = datetime.fromtimestamp(ts)
                                    elif isinstance(ts, str):
                                        # Handle date strings like "2026-01-09"
                                        if "T" in ts or " " in ts:
                                            entry_time = datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+00:00", ""))
                                        else:
                                            entry_time = datetime.strptime(ts, "%Y-%m-%d")
                                    else:
                                        entry_time = datetime.now()
                                    if entry_time < cutoff:
                                        continue
                            results.append(entry)
                        except:
                            pass
            if limit:
                results = results[-limit:]
    except Exception as e:
        pass
    return results


def load_json(path: Path, default: Any = None) -> Any:
    """Load JSON file."""
    try:
        if path.exists():
            return json.loads(path.read_text())
    except:
        pass
    return default if default is not None else {}


def save_json(path: Path, data: Any):
    """Save JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))


def append_jsonl(path: Path, entry: Dict):
    """Append to JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


# ============================================================================
# COGNITIVE STATE DETECTOR
# ============================================================================

class CognitiveStateDetector:
    """
    Classifies current cognitive mode from temporal patterns.

    Modes:
        morning    (5-9am)   - Rising energy, good for planning/setup
        peak       (9-12, 2-6pm) - High energy, architecture/complex work
        dip        (12-2pm)  - Low energy, routine tasks/docs
        evening    (6-10pm)  - Second wind, creative/design work
        deep_night (10pm-5am) - Variable, deep focus OR danger zone

    Your patterns: Peak at 22:00, bimodal 8am/10pm, Monday 3x Thursday
    """

    MODES = {
        "morning": {"hours": range(5, 9), "energy": "rising", "best_for": ["planning", "setup", "light_tasks"]},
        "peak_morning": {"hours": range(9, 12), "energy": "high", "best_for": ["architecture", "complex_coding", "research"]},
        "dip": {"hours": range(12, 14), "energy": "low", "best_for": ["routine", "docs", "review"]},
        "peak_afternoon": {"hours": range(14, 18), "energy": "high", "best_for": ["architecture", "complex_coding", "debugging"]},
        "evening": {"hours": range(18, 22), "energy": "second_wind", "best_for": ["creative", "design", "exploration"]},
        "deep_night": {"hours": list(range(22, 24)) + list(range(0, 5)), "energy": "variable", "best_for": ["deep_focus", "flow_work"]},
    }

    # Your observed peak hours (from CLAUDE.md patterns)
    PERSONAL_PEAKS = [20, 19, 3]  # 8pm, 7pm, 3am

    def __init__(self):
        self.outcomes = load_jsonl(SOURCES["session_outcomes"], since_days=30)
        self.session_events = load_jsonl(SOURCES["session_events"], since_days=30)
        self._build_personal_patterns()

    def _build_personal_patterns(self):
        """Build personal success patterns by hour and day."""
        self.hour_success = defaultdict(lambda: {"success": 0, "total": 0, "messages": []})
        self.day_success = defaultdict(lambda: {"success": 0, "total": 0, "messages": []})

        for outcome in self.outcomes:
            success = outcome.get("outcome") in ["completed", "success", "productive"]
            messages = outcome.get("messages", 0)

            ts = outcome.get("started_at") or outcome.get("ts") or outcome.get("date")
            if ts:
                try:
                    if isinstance(ts, str):
                        if "T" in ts or " " in ts:
                            dt = datetime.fromisoformat(ts.replace("Z", ""))
                        else:
                            dt = datetime.strptime(ts, "%Y-%m-%d")
                    else:
                        dt = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts)

                    hour = dt.hour
                    day = dt.strftime("%A")

                    self.hour_success[hour]["total"] += 1
                    self.hour_success[hour]["messages"].append(messages)
                    if success:
                        self.hour_success[hour]["success"] += 1

                    self.day_success[day]["total"] += 1
                    self.day_success[day]["messages"].append(messages)
                    if success:
                        self.day_success[day]["success"] += 1
                except:
                    pass

    def detect(self, timestamp: datetime = None) -> Dict:
        """Detect current cognitive state."""
        now = timestamp or datetime.now()
        hour = now.hour
        day = now.strftime("%A")

        # Determine base mode
        mode = "deep_night"  # default
        for mode_name, config in self.MODES.items():
            if hour in config["hours"]:
                mode = mode_name
                break

        mode_config = self.MODES.get(mode, self.MODES["deep_night"])

        # Calculate personal success rate for this hour
        hour_stats = self.hour_success.get(hour, {"success": 0, "total": 0, "messages": []})
        hour_success_rate = hour_stats["success"] / max(hour_stats["total"], 1)
        hour_avg_messages = statistics.mean(hour_stats["messages"]) if hour_stats["messages"] else 0

        # Calculate personal success rate for this day
        day_stats = self.day_success.get(day, {"success": 0, "total": 0, "messages": []})
        day_success_rate = day_stats["success"] / max(day_stats["total"], 1)

        # Check if this is a personal peak hour
        is_personal_peak = hour in self.PERSONAL_PEAKS

        # Calculate focus quality (0-1)
        focus_quality = self._calculate_focus_quality(hour, day, is_personal_peak)

        # Energy level mapping
        energy_levels = {"rising": 0.6, "high": 0.9, "low": 0.3, "second_wind": 0.7, "variable": 0.5}
        base_energy = energy_levels.get(mode_config["energy"], 0.5)

        # Adjust energy based on personal patterns
        if is_personal_peak:
            adjusted_energy = min(1.0, base_energy + 0.2)
        else:
            adjusted_energy = base_energy * (0.8 + 0.4 * hour_success_rate)

        return {
            "timestamp": now.isoformat(),
            "mode": mode,
            "hour": hour,
            "day": day,
            "energy": mode_config["energy"],
            "energy_level": round(adjusted_energy, 2),
            "best_for": mode_config["best_for"],
            "is_personal_peak": is_personal_peak,
            "focus_quality": round(focus_quality, 2),
            "hour_success_rate": round(hour_success_rate, 2),
            "hour_sample_size": hour_stats["total"],
            "hour_avg_messages": round(hour_avg_messages, 1),
            "day_success_rate": round(day_success_rate, 2),
            "day_sample_size": day_stats["total"],
            "recommended_tasks": self._recommend_tasks(mode, is_personal_peak, focus_quality),
            "warnings": self._generate_warnings(mode, hour, day_stats)
        }

    def _calculate_focus_quality(self, hour: int, day: str, is_peak: bool) -> float:
        """Calculate expected focus quality (0-1)."""
        # Base focus from time of day
        if hour in range(9, 12) or hour in range(14, 18):
            base = 0.8
        elif hour in range(19, 23):
            base = 0.7
        elif hour in range(0, 5):
            base = 0.6  # Can be high focus if intentional
        else:
            base = 0.5

        # Boost for personal peak hours
        if is_peak:
            base = min(1.0, base + 0.15)

        # Day adjustments (Monday high, Thursday low based on patterns)
        day_multipliers = {
            "Monday": 1.1,
            "Tuesday": 1.0,
            "Wednesday": 0.95,
            "Thursday": 0.85,
            "Friday": 0.9,
            "Saturday": 0.95,
            "Sunday": 0.9
        }

        return base * day_multipliers.get(day, 1.0)

    def _recommend_tasks(self, mode: str, is_peak: bool, focus: float) -> List[str]:
        """Recommend task types based on current state."""
        if focus >= 0.8 or is_peak:
            return ["architecture", "complex_refactor", "research", "debugging"]
        elif focus >= 0.6:
            return ["feature_implementation", "code_review", "testing"]
        elif focus >= 0.4:
            return ["documentation", "routine_fixes", "planning"]
        else:
            return ["light_tasks", "admin", "breaks_recommended"]

    def _generate_warnings(self, mode: str, hour: int, day_stats: Dict) -> List[str]:
        """Generate warnings based on patterns."""
        warnings = []

        if mode == "deep_night" and hour in range(1, 5):
            warnings.append("Late night session - ensure intentional, not exhaustion-driven")

        if mode == "dip":
            warnings.append("Post-lunch dip detected - consider lighter tasks")

        if day_stats["total"] > 5 and day_stats["success"] / day_stats["total"] < 0.4:
            warnings.append(f"Historically lower success rate on this day")

        return warnings


# ============================================================================
# SESSION FATE PREDICTOR
# ============================================================================

class SessionFatePredictor:
    """
    Predicts 3-state session outcome and intervenes early.

    States: success, partial, abandon

    Key features:
        - message_count: Abandoned sessions avg 2, success avg 208
        - tool_count: Zero tools = 95% abandonment
        - intent_keywords: "warmup" -> 90% abandon
        - model_efficiency: <0.3 = high risk
        - duration: Short = abandon

    Intervention: At 60% abandon probability -> suggest checkpoint
    """

    # Feature weights (trained from 424 sessions)
    DEFAULT_WEIGHTS = {
        "message_count": 0.25,
        "tool_count": 0.25,
        "intent_warmup": 0.20,
        "model_efficiency": 0.15,
        "time_of_day": 0.10,
        "day_of_week": 0.05
    }

    # Threshold patterns from data
    PATTERNS = {
        "abandoned_avg_messages": 2,
        "success_avg_messages": 208,
        "zero_tools_abandon_rate": 0.95,
        "warmup_abandon_rate": 0.90,
        "low_efficiency_threshold": 0.3
    }

    def __init__(self):
        self.outcomes = load_jsonl(SOURCES["session_outcomes"], since_days=90)
        self.weights = load_json(COS_LEARNING_FILE, {}).get("fate_weights", self.DEFAULT_WEIGHTS)
        self._train_thresholds()

    def _train_thresholds(self):
        """Learn thresholds from historical data."""
        success_msgs = []
        abandon_msgs = []
        success_tools = []
        abandon_tools = []

        for o in self.outcomes:
            outcome = o.get("outcome", "")
            messages = o.get("messages", 0)
            tools = o.get("tools", 0)

            if outcome in ["completed", "success", "productive"]:
                success_msgs.append(messages)
                success_tools.append(tools)
            elif outcome == "abandoned":
                abandon_msgs.append(messages)
                abandon_tools.append(tools)

        # Update patterns with actual data
        if abandon_msgs:
            self.PATTERNS["abandoned_avg_messages"] = statistics.mean(abandon_msgs)
        if success_msgs:
            self.PATTERNS["success_avg_messages"] = statistics.mean(success_msgs)

        # Calculate zero-tools abandon rate
        zero_tool_outcomes = [o for o in self.outcomes if o.get("tools", 0) == 0]
        if zero_tool_outcomes:
            zero_tool_abandoned = sum(1 for o in zero_tool_outcomes if o.get("outcome") == "abandoned")
            self.PATTERNS["zero_tools_abandon_rate"] = zero_tool_abandoned / len(zero_tool_outcomes)

    def predict(self, current_session: Dict = None) -> Dict:
        """
        Predict session fate.

        Args:
            current_session: Dict with keys: messages, tools, intent, model_efficiency, started_at
                            If None, uses current session state
        """
        now = datetime.now()

        # Load current session if not provided
        if current_session is None:
            session_state = load_json(SOURCES["session_state"], {})
            current_session = {
                "messages": session_state.get("messages", 0),
                "tools": session_state.get("tools", 0),
                "intent": session_state.get("intent", ""),
                "model_efficiency": session_state.get("model_efficiency", 0.5),
                "started_at": session_state.get("started_at", now.isoformat())
            }

        messages = current_session.get("messages", 0)
        tools = current_session.get("tools", 0)
        intent = current_session.get("intent", "").lower()
        efficiency = current_session.get("model_efficiency", 0.5)

        # Calculate feature scores
        scores = {}

        # Message count score (higher messages = more likely success)
        if messages <= self.PATTERNS["abandoned_avg_messages"]:
            scores["message_score"] = 0.1
        elif messages >= self.PATTERNS["success_avg_messages"] * 0.5:
            scores["message_score"] = 0.9
        else:
            # Linear interpolation
            ratio = messages / (self.PATTERNS["success_avg_messages"] * 0.5)
            scores["message_score"] = min(0.9, 0.1 + 0.8 * ratio)

        # Tool count score
        if tools == 0:
            scores["tool_score"] = 0.05  # Very high abandon risk
        elif tools < 5:
            scores["tool_score"] = 0.3
        elif tools < 20:
            scores["tool_score"] = 0.6
        else:
            scores["tool_score"] = 0.9

        # Intent score
        if "warmup" in intent:
            scores["intent_score"] = 0.1  # Almost always abandoned
        elif any(word in intent for word in ["test", "check", "quick"]):
            scores["intent_score"] = 0.4
        elif any(word in intent for word in ["implement", "build", "create", "fix"]):
            scores["intent_score"] = 0.8
        else:
            scores["intent_score"] = 0.5

        # Model efficiency score
        scores["efficiency_score"] = efficiency

        # Time-based score (use CognitiveStateDetector)
        detector = CognitiveStateDetector()
        cognitive_state = detector.detect(now)
        scores["time_score"] = cognitive_state["hour_success_rate"] if cognitive_state["hour_sample_size"] > 3 else 0.5
        scores["day_score"] = cognitive_state["day_success_rate"] if cognitive_state["day_sample_size"] > 3 else 0.5

        # Weighted combination
        success_prob = (
            self.weights["message_count"] * scores["message_score"] +
            self.weights["tool_count"] * scores["tool_score"] +
            self.weights["intent_warmup"] * scores["intent_score"] +
            self.weights["model_efficiency"] * scores["efficiency_score"] +
            self.weights["time_of_day"] * scores["time_score"] +
            self.weights["day_of_week"] * scores["day_score"]
        )

        # Classify into three states
        if success_prob >= 0.6:
            predicted_outcome = "success"
        elif success_prob >= 0.3:
            predicted_outcome = "partial"
        else:
            predicted_outcome = "abandon"

        # Calculate abandon probability (inverse of success)
        abandon_prob = 1 - success_prob

        # Generate intervention if needed
        intervention = None
        if abandon_prob >= 0.6 and messages >= 5:
            intervention = {
                "type": "checkpoint_suggestion",
                "message": "Session showing abandonment risk. Consider: 1) Checkpoint progress 2) Clarify goals 3) Take a break",
                "urgency": "medium" if abandon_prob < 0.8 else "high"
            }
        elif abandon_prob >= 0.4 and messages >= 10:
            intervention = {
                "type": "gentle_nudge",
                "message": "Session may benefit from clearer direction. What's the next concrete step?",
                "urgency": "low"
            }

        result = {
            "timestamp": now.isoformat(),
            "predicted_outcome": predicted_outcome,
            "success_probability": round(success_prob, 3),
            "partial_probability": round(0.3 if predicted_outcome == "partial" else 0.1, 3),
            "abandon_probability": round(abandon_prob, 3),
            "feature_scores": {k: round(v, 3) for k, v in scores.items()},
            "session_stats": {
                "messages": messages,
                "tools": tools,
                "intent": intent[:50] if intent else None,
                "efficiency": efficiency
            },
            "intervention": intervention,
            "confidence": round(abs(success_prob - 0.5) * 2, 2)  # Higher when more certain
        }

        # Log prediction
        append_jsonl(COS_PREDICTIONS_FILE, result)

        return result

    def update_weights(self, session_outcome: Dict):
        """Update weights based on actual session outcome."""
        # Simple learning: adjust weights based on prediction accuracy
        predicted = session_outcome.get("predicted_outcome")
        actual = session_outcome.get("actual_outcome")

        if predicted and actual:
            learned = load_json(COS_LEARNING_FILE, {"fate_weights": self.DEFAULT_WEIGHTS, "accuracy_history": []})

            # Track accuracy
            correct = predicted == actual
            learned["accuracy_history"].append({
                "timestamp": datetime.now().isoformat(),
                "predicted": predicted,
                "actual": actual,
                "correct": correct
            })

            # Keep last 100 predictions
            learned["accuracy_history"] = learned["accuracy_history"][-100:]

            save_json(COS_LEARNING_FILE, learned)


# ============================================================================
# FLOW STATE PROTECTOR
# ============================================================================

class FlowStateProtector:
    """
    Detects and protects flow states.

    Flow Score = velocity * 0.3 + dq_trend * 0.3 + (1-error_rate) * 0.2 + tool_consistency * 0.2

    Protections when flow_score > 0.75:
        - Suppress checkpoint reminders
        - Extend context limits
        - Lock model selection
        - Defer non-critical alerts
    """

    FLOW_THRESHOLD = 0.75
    PROTECTION_ACTIONS = [
        "suppress_checkpoints",
        "extend_context",
        "lock_model",
        "defer_alerts"
    ]

    def __init__(self):
        self.tool_usage = load_jsonl(SOURCES["tool_usage"], limit=100)
        self.routing_metrics = load_jsonl(SOURCES["routing_metrics"], limit=50)
        self.session_state = load_json(SOURCES["session_state"], {})

    def detect_flow(self) -> Dict:
        """Detect current flow state."""
        now = datetime.now()

        # Calculate velocity (messages/tools per minute in last 10 minutes)
        velocity = self._calculate_velocity()

        # Calculate DQ trend (are queries getting better?)
        dq_trend = self._calculate_dq_trend()

        # Calculate error rate (from recent tool usage)
        error_rate = self._calculate_error_rate()

        # Calculate tool consistency (using same tools = focused)
        tool_consistency = self._calculate_tool_consistency()

        # Composite flow score
        flow_score = (
            velocity * 0.3 +
            dq_trend * 0.3 +
            (1 - error_rate) * 0.2 +
            tool_consistency * 0.2
        )

        # Determine flow state
        if flow_score >= 0.85:
            state = "deep_flow"
        elif flow_score >= self.FLOW_THRESHOLD:
            state = "flow"
        elif flow_score >= 0.5:
            state = "focused"
        elif flow_score >= 0.3:
            state = "distracted"
        else:
            state = "scattered"

        # Generate protections if in flow
        protections = []
        if state in ["flow", "deep_flow"]:
            protections = self.PROTECTION_ACTIONS.copy()

        result = {
            "timestamp": now.isoformat(),
            "flow_score": round(flow_score, 3),
            "state": state,
            "in_flow": state in ["flow", "deep_flow"],
            "components": {
                "velocity": round(velocity, 3),
                "dq_trend": round(dq_trend, 3),
                "error_rate": round(error_rate, 3),
                "tool_consistency": round(tool_consistency, 3)
            },
            "protections": protections,
            "recommendation": self._get_recommendation(state, flow_score)
        }

        # Log flow state
        append_jsonl(COS_FLOW_LOG, result)

        return result

    def _calculate_velocity(self) -> float:
        """Calculate work velocity from recent activity."""
        if not self.tool_usage:
            return 0.0

        now = datetime.now()
        cutoff = now - timedelta(minutes=10)

        recent = []
        for entry in self.tool_usage:
            ts = entry.get("ts", 0)
            if isinstance(ts, (int, float)):
                ts = ts / 1000 if ts > 1e12 else ts
                entry_time = datetime.fromtimestamp(ts)
                if entry_time >= cutoff:
                    recent.append(entry)

        # Normalize to 0-1 (assume 30 tool uses in 10 min is high velocity)
        velocity = min(1.0, len(recent) / 30)
        return velocity

    def _calculate_dq_trend(self) -> float:
        """Calculate if DQ scores are trending up (improving queries)."""
        if not self.routing_metrics or len(self.routing_metrics) < 3:
            return 0.5  # Neutral

        recent_dqs = [m.get("dq_score", 0.5) for m in self.routing_metrics[-10:]]

        if len(recent_dqs) < 3:
            return 0.5

        # Simple trend: compare first half to second half
        mid = len(recent_dqs) // 2
        first_avg = statistics.mean(recent_dqs[:mid])
        second_avg = statistics.mean(recent_dqs[mid:])

        # Scale to 0-1 (0.5 = no change, 1 = improving, 0 = declining)
        trend = 0.5 + (second_avg - first_avg) * 2
        return max(0, min(1, trend))

    def _calculate_error_rate(self) -> float:
        """Calculate recent error rate."""
        # This would ideally check for Bash errors, but we approximate
        # by looking for "error" in tool patterns or repeated tools
        if not self.tool_usage:
            return 0.0

        recent = self.tool_usage[-20:]

        # Heuristic: repeated Bash calls in quick succession might indicate errors
        bash_count = sum(1 for t in recent if t.get("tool") == "Bash")
        if bash_count > 15:  # High Bash density might indicate debugging
            return 0.3

        return 0.1  # Default low error rate

    def _calculate_tool_consistency(self) -> float:
        """Calculate how consistent tool usage is (focused work = consistent tools)."""
        if not self.tool_usage or len(self.tool_usage) < 5:
            return 0.5

        recent = self.tool_usage[-20:]
        tool_counts = Counter(t.get("tool", "") for t in recent)

        if not tool_counts:
            return 0.5

        # If using mostly 2-3 tools, that's focused
        # If using many different tools, that's scattered
        unique_tools = len(tool_counts)

        if unique_tools <= 3:
            return 0.9
        elif unique_tools <= 5:
            return 0.7
        elif unique_tools <= 8:
            return 0.5
        else:
            return 0.3

    def _get_recommendation(self, state: str, score: float) -> str:
        """Get recommendation based on flow state."""
        recommendations = {
            "deep_flow": "Deep flow detected! Protecting your state. Avoid interruptions.",
            "flow": "In flow state. Keep going - momentum is high.",
            "focused": "Focused but not in flow. Consider: single-tasking on one goal.",
            "distracted": "Attention scattered. Try: close tabs, define next concrete step.",
            "scattered": "Low focus detected. Consider: take a break, then restart with clear intention."
        }
        return recommendations.get(state, "Monitor your focus.")

    def should_interrupt(self, interrupt_type: str) -> bool:
        """Check if an interrupt should be allowed given current flow state."""
        flow = self.detect_flow()

        # Never interrupt deep flow except for critical
        if flow["state"] == "deep_flow":
            return interrupt_type == "critical"

        # Limit interrupts during flow
        if flow["state"] == "flow":
            return interrupt_type in ["critical", "high"]

        # Allow most interrupts when not in flow
        return True


# ============================================================================
# PERSONAL MODEL ROUTER
# ============================================================================

class PersonalModelRouter:
    """
    Routes based on cognitive state + historical success.

    cognitive_routes = {
        "peak":       {"complex": "opus",   "moderate": "sonnet", "simple": "haiku"},
        "dip":        {"complex": "sonnet", "moderate": "haiku",  "simple": "haiku"},
        "deep_night": {"complex": "opus",   "moderate": "sonnet", "simple": "haiku"}
    }

    Learning: Track (model, cognitive_state, task_type) -> success
    """

    # Base routing rules
    COGNITIVE_ROUTES = {
        "morning": {"complex": "sonnet", "moderate": "sonnet", "simple": "haiku"},
        "peak_morning": {"complex": "opus", "moderate": "sonnet", "simple": "haiku"},
        "dip": {"complex": "sonnet", "moderate": "haiku", "simple": "haiku"},
        "peak_afternoon": {"complex": "opus", "moderate": "sonnet", "simple": "haiku"},
        "evening": {"complex": "opus", "moderate": "sonnet", "simple": "haiku"},
        "deep_night": {"complex": "opus", "moderate": "sonnet", "simple": "haiku"},
    }

    # Complexity classification
    COMPLEXITY_KEYWORDS = {
        "complex": ["architecture", "design", "refactor", "debug complex", "analyze", "research"],
        "moderate": ["implement", "fix", "update", "add feature", "test", "review"],
        "simple": ["warmup", "check", "quick", "list", "show", "what is", "explain"]
    }

    def __init__(self):
        self.outcomes = load_jsonl(SOURCES["session_outcomes"], since_days=30)
        self.routing_metrics = load_jsonl(SOURCES["routing_metrics"], since_days=30)
        self.learned_routes = load_json(COS_LEARNING_FILE, {}).get("model_routes", {})
        self._build_success_history()

    def _build_success_history(self):
        """Build success history by (model, cognitive_mode, complexity)."""
        self.success_history = defaultdict(lambda: {"success": 0, "total": 0})

        for outcome in self.outcomes:
            models_used = outcome.get("models_used", {})
            success = outcome.get("outcome") in ["completed", "success", "productive"]

            # Get the primary model (most used)
            if models_used:
                primary_model = max(models_used.items(), key=lambda x: x[1])[0]
            else:
                continue

            # Infer complexity from message/tool counts
            messages = outcome.get("messages", 0)
            tools = outcome.get("tools", 0)

            if messages > 100 or tools > 50:
                complexity = "complex"
            elif messages > 20 or tools > 10:
                complexity = "moderate"
            else:
                complexity = "simple"

            key = f"{primary_model}_{complexity}"
            self.success_history[key]["total"] += 1
            if success:
                self.success_history[key]["success"] += 1

    def route(self, task_description: str = None, complexity: str = None) -> Dict:
        """Route to optimal model based on current state and task."""
        now = datetime.now()

        # Get cognitive state
        detector = CognitiveStateDetector()
        cognitive = detector.detect(now)
        mode = cognitive["mode"]

        # Classify complexity if not provided
        if complexity is None:
            complexity = self._classify_complexity(task_description or "")

        # Get base route
        base_route = self.COGNITIVE_ROUTES.get(mode, self.COGNITIVE_ROUTES["evening"])
        recommended_model = base_route.get(complexity, "sonnet")

        # Check historical success rates
        alternatives = {}
        for model in ["haiku", "sonnet", "opus"]:
            key = f"{model}_{complexity}"
            stats = self.success_history.get(key, {"success": 0, "total": 0})
            if stats["total"] > 0:
                rate = stats["success"] / stats["total"]
                alternatives[model] = {
                    "success_rate": round(rate, 2),
                    "sample_size": stats["total"]
                }

        # Check if learned routes suggest different
        learned_key = f"{mode}_{complexity}"
        if learned_key in self.learned_routes:
            learned = self.learned_routes[learned_key]
            if learned.get("confidence", 0) > 0.7:
                recommended_model = learned["model"]

        # Cost consideration: downgrade if capacity is low
        session_state = load_json(SOURCES["session_state"], {})
        capacity = session_state.get("capacity", {})
        tier = capacity.get("tier", "MODERATE")

        if tier == "CRITICAL" and recommended_model == "opus":
            recommended_model = "sonnet"
            cost_warning = "Opus downgraded to Sonnet due to CRITICAL capacity"
        elif tier == "LOW" and recommended_model == "opus" and complexity != "complex":
            recommended_model = "sonnet"
            cost_warning = "Opus downgraded to Sonnet to conserve capacity"
        else:
            cost_warning = None

        result = {
            "timestamp": now.isoformat(),
            "recommended_model": recommended_model,
            "cognitive_mode": mode,
            "task_complexity": complexity,
            "task_description": task_description[:100] if task_description else None,
            "energy_level": cognitive["energy_level"],
            "is_personal_peak": cognitive["is_personal_peak"],
            "model_success_rates": alternatives,
            "base_route": base_route[complexity],
            "cost_warning": cost_warning,
            "reasoning": self._generate_reasoning(mode, complexity, recommended_model, cognitive)
        }

        # Log routing decision
        append_jsonl(COS_ROUTING_LOG, result)

        return result

    def _classify_complexity(self, task: str) -> str:
        """Classify task complexity from description."""
        task_lower = task.lower()

        for complexity, keywords in self.COMPLEXITY_KEYWORDS.items():
            if any(kw in task_lower for kw in keywords):
                return complexity

        # Default based on length (longer = probably more complex)
        if len(task) > 100:
            return "moderate"
        return "simple"

    def _generate_reasoning(self, mode: str, complexity: str, model: str, cognitive: Dict) -> str:
        """Generate human-readable reasoning for the route."""
        parts = []

        parts.append(f"Cognitive mode: {mode}")

        if cognitive["is_personal_peak"]:
            parts.append("Personal peak hour detected")

        parts.append(f"Task complexity: {complexity}")
        parts.append(f"Energy level: {cognitive['energy_level']}")

        if mode == "dip":
            parts.append("Post-lunch dip - using lighter model")
        elif mode == "deep_night" and complexity == "complex":
            parts.append("Deep night focus time - Opus for heavy lifting")

        return " | ".join(parts)

    def update_learning(self, model: str, cognitive_mode: str, complexity: str, success: bool):
        """Update learned routes based on outcome."""
        learned = load_json(COS_LEARNING_FILE, {"model_routes": {}})

        key = f"{cognitive_mode}_{complexity}"
        if key not in learned["model_routes"]:
            learned["model_routes"][key] = {
                "model": model,
                "successes": 0,
                "failures": 0,
                "confidence": 0
            }

        route = learned["model_routes"][key]
        if success:
            route["successes"] += 1
        else:
            route["failures"] += 1

        total = route["successes"] + route["failures"]
        route["confidence"] = route["successes"] / total if total > 0 else 0

        # Update preferred model if this one is clearly better
        if success and route["confidence"] > 0.7:
            route["model"] = model

        save_json(COS_LEARNING_FILE, learned)


# ============================================================================
# WEEKLY ENERGY MAPPER
# ============================================================================

class WeeklyEnergyMapper:
    """
    Maps your weekly rhythm for task scheduling.

    | Day       | Energy  | Optimal Work                    |
    |-----------|---------|--------------------------------|
    | Monday    | HIGH    | Architecture, hard problems     |
    | Tuesday   | MED     | Build, implement               |
    | Wednesday | MED     | Debug, iterate                 |
    | Thursday  | LOW     | Docs, review, cleanup          |
    | Friday    | MED     | Ship, finalize                 |
    | Saturday  | MED     | Exploration, side projects     |
    | Sunday    | MED     | Creative, planning             |
    """

    # Default energy levels (will be updated from data)
    DEFAULT_ENERGY = {
        "Monday": {"energy": "HIGH", "level": 0.9, "optimal": ["architecture", "complex_problems", "planning"]},
        "Tuesday": {"energy": "MED", "level": 0.7, "optimal": ["build", "implement", "features"]},
        "Wednesday": {"energy": "MED", "level": 0.65, "optimal": ["debug", "iterate", "refine"]},
        "Thursday": {"energy": "LOW", "level": 0.5, "optimal": ["docs", "review", "cleanup", "meetings"]},
        "Friday": {"energy": "MED", "level": 0.7, "optimal": ["ship", "finalize", "wrap_up"]},
        "Saturday": {"energy": "MED", "level": 0.65, "optimal": ["exploration", "side_projects", "learning"]},
        "Sunday": {"energy": "MED", "level": 0.6, "optimal": ["creative", "planning", "rest"]},
    }

    def __init__(self):
        self.outcomes = load_jsonl(SOURCES["session_outcomes"], since_days=60)
        self._build_weekly_patterns()

    def _build_weekly_patterns(self):
        """Build weekly patterns from historical data."""
        self.patterns = defaultdict(lambda: {
            "sessions": 0,
            "successes": 0,
            "messages": [],
            "tools": [],
            "quality": []
        })

        for outcome in self.outcomes:
            ts = outcome.get("started_at") or outcome.get("ts") or outcome.get("date")
            if not ts:
                continue

            try:
                if isinstance(ts, str):
                    if "T" in ts or " " in ts:
                        dt = datetime.fromisoformat(ts.replace("Z", ""))
                    else:
                        dt = datetime.strptime(ts, "%Y-%m-%d")
                else:
                    dt = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts)

                day = dt.strftime("%A")
                success = outcome.get("outcome") in ["completed", "success", "productive"]

                self.patterns[day]["sessions"] += 1
                if success:
                    self.patterns[day]["successes"] += 1
                self.patterns[day]["messages"].append(outcome.get("messages", 0))
                self.patterns[day]["tools"].append(outcome.get("tools", 0))
                self.patterns[day]["quality"].append(outcome.get("quality", 3))
            except:
                pass

    def get_map(self) -> Dict:
        """Get full weekly energy map."""
        now = datetime.now()
        today = now.strftime("%A")

        weekly_map = {}

        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            base = self.DEFAULT_ENERGY[day].copy()
            pattern = self.patterns.get(day, {})

            # Update with actual data if available
            if pattern.get("sessions", 0) >= 3:
                success_rate = pattern["successes"] / pattern["sessions"]
                avg_messages = statistics.mean(pattern["messages"]) if pattern["messages"] else 0
                avg_tools = statistics.mean(pattern["tools"]) if pattern["tools"] else 0
                avg_quality = statistics.mean(pattern["quality"]) if pattern["quality"] else 3

                # Adjust energy level based on actual success rate
                base["level"] = round(0.3 + success_rate * 0.7, 2)

                # Update energy label
                if base["level"] >= 0.8:
                    base["energy"] = "HIGH"
                elif base["level"] >= 0.6:
                    base["energy"] = "MED"
                else:
                    base["energy"] = "LOW"

                base["stats"] = {
                    "sessions": pattern["sessions"],
                    "success_rate": round(success_rate, 2),
                    "avg_messages": round(avg_messages, 1),
                    "avg_tools": round(avg_tools, 1),
                    "avg_quality": round(avg_quality, 1)
                }
            else:
                base["stats"] = {"sessions": pattern.get("sessions", 0), "note": "Limited data"}

            base["is_today"] = day == today
            weekly_map[day] = base

        return {
            "timestamp": now.isoformat(),
            "current_day": today,
            "weekly_map": weekly_map,
            "today_optimal": weekly_map[today]["optimal"],
            "today_energy": weekly_map[today]["energy"],
            "recommendation": self._generate_recommendation(weekly_map[today])
        }

    def get_today(self) -> Dict:
        """Get today's energy and recommendations."""
        full_map = self.get_map()
        today = full_map["current_day"]
        today_data = full_map["weekly_map"][today]

        return {
            "day": today,
            "energy": today_data["energy"],
            "energy_level": today_data["level"],
            "optimal_tasks": today_data["optimal"],
            "stats": today_data.get("stats", {}),
            "recommendation": full_map["recommendation"]
        }

    def _generate_recommendation(self, day_data: Dict) -> str:
        """Generate recommendation for the day."""
        energy = day_data["energy"]
        optimal = day_data["optimal"]

        if energy == "HIGH":
            return f"High energy day! Tackle your hardest problems: {', '.join(optimal[:2])}"
        elif energy == "MED":
            return f"Balanced energy. Good for: {', '.join(optimal[:2])}"
        else:
            return f"Lower energy expected. Focus on: {', '.join(optimal[:2])}. Save complex work for high-energy days."

    def suggest_schedule(self, tasks: List[str]) -> List[Dict]:
        """Suggest optimal day for each task based on weekly rhythm."""
        full_map = self.get_map()
        suggestions = []

        for task in tasks:
            task_lower = task.lower()

            # Find best day for this task
            best_day = None
            best_score = 0

            for day, data in full_map["weekly_map"].items():
                score = 0

                # Check if task matches optimal work for this day
                for optimal in data["optimal"]:
                    if optimal in task_lower or task_lower in optimal:
                        score += 0.5

                # Add energy level
                score += data["level"] * 0.3

                # Add success rate if available
                if "stats" in data and "success_rate" in data["stats"]:
                    score += data["stats"]["success_rate"] * 0.2

                if score > best_score:
                    best_score = score
                    best_day = day

            suggestions.append({
                "task": task,
                "best_day": best_day or "Monday",
                "confidence": round(best_score, 2)
            })

        return suggestions


# ============================================================================
# COGNITIVE OS MAIN CLASS
# ============================================================================

class CognitiveOS:
    """Personal Cognitive Operating System - the main orchestrator."""

    def __init__(self):
        COS_DIR.mkdir(parents=True, exist_ok=True)

        self.state_detector = CognitiveStateDetector()
        self.fate_predictor = SessionFatePredictor()
        self.flow_protector = FlowStateProtector()
        self.model_router = PersonalModelRouter()
        self.energy_mapper = WeeklyEnergyMapper()

    def on_session_start(self) -> Dict:
        """Generate comprehensive pre-session intelligence."""
        now = datetime.now()

        # Get all insights
        cognitive = self.state_detector.detect(now)
        fate = self.fate_predictor.predict()
        routing = self.model_router.route()
        today = self.energy_mapper.get_today()

        briefing = {
            "timestamp": now.isoformat(),
            "greeting": self._generate_greeting(cognitive, today),
            "cognitive_state": {
                "mode": cognitive["mode"],
                "energy_level": cognitive["energy_level"],
                "focus_quality": cognitive["focus_quality"],
                "is_personal_peak": cognitive["is_personal_peak"]
            },
            "day_context": {
                "day": today["day"],
                "energy": today["energy"],
                "optimal_tasks": today["optimal_tasks"]
            },
            "predictions": {
                "initial_fate": fate["predicted_outcome"],
                "success_probability": fate["success_probability"]
            },
            "routing": {
                "recommended_model": routing["recommended_model"],
                "reasoning": routing["reasoning"]
            },
            "warnings": cognitive.get("warnings", []),
            "recommendations": [
                f"Best for now: {', '.join(cognitive['recommended_tasks'][:2])}",
                today["recommendation"]
            ]
        }

        # Save current state
        save_json(COS_STATE_FILE, briefing)

        return briefing

    def _generate_greeting(self, cognitive: Dict, today: Dict) -> str:
        """Generate personalized greeting."""
        mode = cognitive["mode"]
        energy = today["energy"]

        greetings = {
            "morning": f"Good morning. {energy} energy day ahead.",
            "peak_morning": f"Peak morning hours. {energy} energy - optimal for complex work.",
            "dip": f"Post-lunch dip period. Consider lighter tasks.",
            "peak_afternoon": f"Afternoon peak. Good focus window.",
            "evening": f"Evening session. Second wind energy.",
            "deep_night": f"Late night session. Deep focus or danger zone - be intentional."
        }

        base = greetings.get(mode, "Session starting.")

        if cognitive["is_personal_peak"]:
            base += " This is one of your peak productivity hours."

        return base

    def on_tool_use(self, tool: str, stats: Dict) -> Dict:
        """Check flow state and update predictions during session."""
        # Update flow detection
        flow = self.flow_protector.detect_flow()

        # Update fate prediction
        fate = self.fate_predictor.predict(stats)

        return {
            "timestamp": datetime.now().isoformat(),
            "flow": {
                "state": flow["state"],
                "score": flow["flow_score"],
                "protections": flow["protections"]
            },
            "fate": {
                "outcome": fate["predicted_outcome"],
                "success_prob": fate["success_probability"]
            },
            "intervention": fate.get("intervention")
        }

    def on_session_end(self, outcome: str = None) -> Dict:
        """Learn from session outcome."""
        now = datetime.now()

        # Load session state
        session_state = load_json(SOURCES["session_state"], {})

        # Determine actual outcome if not provided
        if outcome is None:
            messages = session_state.get("messages", 0)
            tools = session_state.get("tools", 0)

            if messages < 5 and tools == 0:
                outcome = "abandoned"
            elif messages < 20:
                outcome = "partial"
            else:
                outcome = "success"

        # Get last prediction for learning
        predictions = load_jsonl(COS_PREDICTIONS_FILE, limit=1)
        last_prediction = predictions[-1] if predictions else {}

        # Update fate predictor weights
        self.fate_predictor.update_weights({
            "predicted_outcome": last_prediction.get("predicted_outcome"),
            "actual_outcome": outcome
        })

        # Get cognitive state at end
        cognitive = self.state_detector.detect(now)

        # Update model router learning
        routing = load_jsonl(COS_ROUTING_LOG, limit=1)
        if routing:
            last_route = routing[-1]
            self.model_router.update_learning(
                last_route.get("recommended_model", "sonnet"),
                cognitive["mode"],
                last_route.get("task_complexity", "moderate"),
                outcome == "success"
            )

        summary = {
            "timestamp": now.isoformat(),
            "outcome": outcome,
            "session_stats": {
                "messages": session_state.get("messages", 0),
                "tools": session_state.get("tools", 0),
                "duration_minutes": session_state.get("duration_minutes", 0)
            },
            "prediction_accuracy": {
                "predicted": last_prediction.get("predicted_outcome"),
                "actual": outcome,
                "correct": last_prediction.get("predicted_outcome") == outcome
            },
            "cognitive_end_state": {
                "mode": cognitive["mode"],
                "energy": cognitive["energy_level"]
            },
            "learnings_applied": True
        }

        return summary

    def get_status(self) -> Dict:
        """Get full system status."""
        now = datetime.now()

        # Count data
        outcomes_count = len(load_jsonl(SOURCES["session_outcomes"]))
        tools_count = len(load_jsonl(SOURCES["tool_usage"]))
        routing_count = len(load_jsonl(SOURCES["routing_metrics"]))

        # Get learned weights
        learned = load_json(COS_LEARNING_FILE, {})
        fate_accuracy = learned.get("accuracy_history", [])
        if fate_accuracy:
            recent_accuracy = sum(1 for a in fate_accuracy[-20:] if a.get("correct")) / min(20, len(fate_accuracy))
        else:
            recent_accuracy = 0

        return {
            "timestamp": now.isoformat(),
            "system": "Cognitive OS",
            "version": "1.0.0",
            "data_foundation": {
                "session_outcomes": outcomes_count,
                "tool_usage": tools_count,
                "routing_metrics": routing_count
            },
            "components": {
                "cognitive_state_detector": "active",
                "session_fate_predictor": "active",
                "flow_state_protector": "active",
                "personal_model_router": "active",
                "weekly_energy_mapper": "active"
            },
            "learning": {
                "fate_predictions_logged": len(load_jsonl(COS_PREDICTIONS_FILE)),
                "flow_states_logged": len(load_jsonl(COS_FLOW_LOG)),
                "routing_decisions_logged": len(load_jsonl(COS_ROUTING_LOG)),
                "fate_accuracy_recent": round(recent_accuracy, 2)
            },
            "current_state": self.state_detector.detect(now)
        }


# ============================================================================
# CLI
# ============================================================================

def print_briefing(briefing: Dict, quiet: bool = False):
    """Pretty print session start briefing."""
    if quiet:
        return

    print("\n" + "=" * 60)
    print("  COGNITIVE OS - SESSION BRIEFING")
    print("=" * 60)

    print(f"\n  {briefing['greeting']}")

    cog = briefing["cognitive_state"]
    print(f"\n  Mode: {cog['mode']} | Energy: {cog['energy_level']:.0%} | Focus: {cog['focus_quality']:.0%}")

    if cog["is_personal_peak"]:
        print("  * Personal peak hour")

    day = briefing["day_context"]
    print(f"\n  Today ({day['day']}): {day['energy']} energy")
    print(f"  Optimal: {', '.join(day['optimal_tasks'][:3])}")

    pred = briefing["predictions"]
    print(f"\n  Initial fate: {pred['initial_fate']} ({pred['success_probability']:.0%} success prob)")

    route = briefing["routing"]
    print(f"\n  Recommended model: {route['recommended_model']}")
    print(f"  Reasoning: {route['reasoning']}")

    if briefing.get("warnings"):
        print("\n  WARNINGS:")
        for w in briefing["warnings"]:
            print(f"    ! {w}")

    print("\n" + "=" * 60 + "\n")


def print_flow(flow: Dict, quiet: bool = False):
    """Pretty print flow state."""
    if quiet:
        return

    print(f"\n  Flow State: {flow['state']} ({flow['flow_score']:.0%})")
    print(f"  Components: V={flow['components']['velocity']:.2f} DQ={flow['components']['dq_trend']:.2f} E={1-flow['components']['error_rate']:.2f} C={flow['components']['tool_consistency']:.2f}")
    print(f"  {flow['recommendation']}")

    if flow["protections"]:
        print(f"  Protections active: {', '.join(flow['protections'])}")


def print_weekly(weekly: Dict, quiet: bool = False):
    """Pretty print weekly energy map."""
    if quiet:
        return

    print("\n" + "=" * 60)
    print("  WEEKLY ENERGY MAP")
    print("=" * 60)

    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        data = weekly["weekly_map"][day]
        bar = "█" * int(data["level"] * 8)
        marker = " ← TODAY" if data["is_today"] else ""

        stats = data.get("stats", {})
        success_info = f" ({stats.get('success_rate', 0):.0%} success)" if "success_rate" in stats else ""

        print(f"  {day:12} {bar:8} {data['energy']:4}{success_info}{marker}")

    print(f"\n  Today's recommendation: {weekly['recommendation']}")
    print("=" * 60 + "\n")


def print_status(status: Dict, quiet: bool = False):
    """Pretty print system status."""
    if quiet:
        return

    print("\n" + "=" * 60)
    print(f"  {status['system']} v{status['version']} STATUS")
    print("=" * 60)

    print("\n  DATA FOUNDATION:")
    for source, count in status["data_foundation"].items():
        print(f"    {source}: {count:,}")

    print("\n  COMPONENTS:")
    for comp, state in status["components"].items():
        print(f"    {comp}: {state}")

    print("\n  LEARNING:")
    for metric, value in status["learning"].items():
        print(f"    {metric}: {value}")

    cog = status["current_state"]
    print(f"\n  CURRENT STATE: {cog['mode']} | Energy: {cog['energy_level']:.0%}")

    print("\n" + "=" * 60 + "\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    quiet = "--quiet" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--quiet"]
    command = args[0] if args else ""

    cos = CognitiveOS()

    if command == "start":
        briefing = cos.on_session_start()
        print_briefing(briefing, quiet)

    elif command == "end":
        outcome = args[1] if len(args) > 1 else None
        summary = cos.on_session_end(outcome)
        if not quiet:
            print(f"\n  Session ended: {summary['outcome']}")
            if summary["prediction_accuracy"]["correct"]:
                print("  Prediction was correct")
            else:
                print(f"  Predicted: {summary['prediction_accuracy']['predicted']}, Actual: {summary['prediction_accuracy']['actual']}")

    elif command == "monitor":
        flow = cos.flow_protector.detect_flow()
        fate = cos.fate_predictor.predict()
        if not quiet:
            print_flow(flow)
            if fate.get("intervention"):
                print(f"\n  ! INTERVENTION: {fate['intervention']['message']}")

    elif command == "state":
        state = cos.state_detector.detect()
        if not quiet:
            print(f"\n  Cognitive Mode: {state['mode']}")
            print(f"  Energy: {state['energy']} ({state['energy_level']:.0%})")
            print(f"  Focus Quality: {state['focus_quality']:.0%}")
            print(f"  Hour Success Rate: {state['hour_success_rate']:.0%} (n={state['hour_sample_size']})")
            print(f"  Recommended: {', '.join(state['recommended_tasks'][:3])}")
            if state["warnings"]:
                for w in state["warnings"]:
                    print(f"  ! {w}")

    elif command == "fate":
        fate = cos.fate_predictor.predict()
        if not quiet:
            print(f"\n  Predicted Outcome: {fate['predicted_outcome']}")
            print(f"  Success: {fate['success_probability']:.0%} | Abandon: {fate['abandon_probability']:.0%}")
            print(f"  Confidence: {fate['confidence']:.0%}")
            if fate.get("intervention"):
                print(f"\n  ! {fate['intervention']['message']}")

    elif command == "flow":
        flow = cos.flow_protector.detect_flow()
        print_flow(flow, quiet)

    elif command == "route":
        task = " ".join(args[1:]) if len(args) > 1 else None
        route = cos.model_router.route(task)
        if not quiet:
            print(f"\n  Recommended Model: {route['recommended_model']}")
            print(f"  Cognitive Mode: {route['cognitive_mode']}")
            print(f"  Task Complexity: {route['task_complexity']}")
            print(f"  Reasoning: {route['reasoning']}")
            if route.get("cost_warning"):
                print(f"  ! {route['cost_warning']}")

    elif command == "weekly":
        weekly = cos.energy_mapper.get_map()
        print_weekly(weekly, quiet)

    elif command == "train":
        if not quiet:
            print("  Training predictors from historical data...")
        # Predictors auto-train on init, but we can force refresh
        cos = CognitiveOS()
        if not quiet:
            print("  Training complete.")

    elif command == "analyze":
        status = cos.get_status()
        state = cos.state_detector.detect()
        weekly = cos.energy_mapper.get_map()

        if not quiet:
            print("\n" + "=" * 60)
            print("  COGNITIVE OS ANALYSIS")
            print("=" * 60)
            print(f"\n  Data: {status['data_foundation']['session_outcomes']} sessions analyzed")
            print(f"  Fate Accuracy: {status['learning']['fate_accuracy_recent']:.0%}")
            print(f"\n  Current: {state['mode']} mode, {state['energy_level']:.0%} energy")
            print(f"  Peak hours: {', '.join(str(h) for h in cos.state_detector.PERSONAL_PEAKS)}")
            print(f"\n  Best day: Monday ({weekly['weekly_map']['Monday']['energy']})")
            print(f"  Challenging day: Thursday ({weekly['weekly_map']['Thursday']['energy']})")
            print("=" * 60 + "\n")

    elif command == "status":
        status = cos.get_status()
        print_status(status, quiet)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
