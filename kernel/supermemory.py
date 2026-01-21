#!/usr/bin/env python3
"""
SuperMemory Intelligence Engine
================================
Transforms disconnected telemetry into compounding cross-session intelligence.

This is the missing layer that connects:
- 132K+ activity events
- 351+ sessions
- 41+ days of memory
- Orphaned paste/file/shell/debug data

Usage:
    python3 supermemory.py briefing          # Pre-session intelligence
    python3 supermemory.py synthesize        # Post-session learning
    python3 supermemory.py weekly            # Weekly knowledge synthesis
    python3 supermemory.py link-context      # Connect orphaned data
    python3 supermemory.py predict <task>    # Predict optimal config
    python3 supermemory.py status            # System status

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                    SUPERMEMORY LAYER                        │
    ├─────────────────────────────────────────────────────────────┤
    │  Session Intelligence → Pattern Correlation → Knowledge     │
    │  Context Linking → Cross-Project Learning → Prediction      │
    └─────────────────────────────────────────────────────────────┘
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import statistics

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
DATA_DIR = CLAUDE_DIR / "data"
KERNEL_DIR = CLAUDE_DIR / "kernel"
MEMORY_DIR = CLAUDE_DIR / "memory"

# Data sources
SOURCES = {
    "activity_events": DATA_DIR / "activity-events.jsonl",
    "session_events": DATA_DIR / "session-events.jsonl",
    "session_outcomes": DATA_DIR / "session-outcomes.jsonl",
    "session_windows": DATA_DIR / "session-windows.jsonl",
    "tool_usage": DATA_DIR / "tool-usage.jsonl",
    "routing_metrics": DATA_DIR / "routing-metrics.jsonl",
    "cost_tracking": DATA_DIR / "cost-tracking.jsonl",
    "errors": DATA_DIR / "errors.jsonl",
    "command_usage": DATA_DIR / "command-usage.jsonl",
    "git_activity": DATA_DIR / "git-activity.jsonl",
    "dq_scores": KERNEL_DIR / "dq-scores.jsonl",
    "modifications": KERNEL_DIR / "modifications.jsonl",
    "knowledge": MEMORY_DIR / "knowledge.json",
    "memory_graph": KERNEL_DIR / "memory-graph.json",
    "identity": KERNEL_DIR / "identity.json",
    "detected_patterns": KERNEL_DIR / "detected-patterns.json",
    "session_state": KERNEL_DIR / "session-state.json",
}

# Orphaned data (to be linked)
ORPHANED = {
    "paste_cache": CLAUDE_DIR / "paste-cache",
    "file_history": CLAUDE_DIR / "file-history",
    "shell_snapshots": CLAUDE_DIR / "shell-snapshots",
    "debug": CLAUDE_DIR / "debug",
    "todos": CLAUDE_DIR / "todos",
}

# Output
SUPERMEMORY_DIR = KERNEL_DIR / "supermemory"
BRIEFING_FILE = SUPERMEMORY_DIR / "current-briefing.json"
SYNTHESIS_FILE = SUPERMEMORY_DIR / "session-synthesis.jsonl"
WEEKLY_FILE = SUPERMEMORY_DIR / "weekly-synthesis.jsonl"
CONTEXT_INDEX = SUPERMEMORY_DIR / "context-index.jsonl"
PREDICTIONS_FILE = SUPERMEMORY_DIR / "predictions.jsonl"


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

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
                                ts = entry.get("ts") or entry.get("timestamp") or entry.get("started_at")
                                if ts:
                                    if isinstance(ts, (int, float)):
                                        ts = ts / 1000 if ts > 1e12 else ts
                                        entry_time = datetime.fromtimestamp(ts)
                                    else:
                                        entry_time = datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+00:00", ""))
                                    if entry_time < cutoff:
                                        continue
                            results.append(entry)
                        except:
                            pass
            if limit:
                results = results[-limit:]
    except Exception as e:
        print(f"Error loading {path}: {e}", file=sys.stderr)
    return results


def load_json(path: Path, default: Any = None) -> Any:
    """Load JSON file."""
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception as e:
        print(f"Error loading {path}: {e}", file=sys.stderr)
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


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION SUCCESS PREDICTOR
# ═══════════════════════════════════════════════════════════════════════════════

class SessionSuccessPredictor:
    """Correlates session outcomes with conditions to predict success."""

    def __init__(self):
        self.outcomes = load_jsonl(SOURCES["session_outcomes"], since_days=30)
        self.windows = load_jsonl(SOURCES["session_windows"], since_days=30)
        self.dq_scores = load_jsonl(SOURCES["dq_scores"], since_days=30)

    def analyze_patterns(self) -> Dict:
        """Analyze patterns in session success."""
        patterns = {
            "by_model": defaultdict(lambda: {"success": 0, "total": 0, "avg_messages": []}),
            "by_hour": defaultdict(lambda: {"success": 0, "total": 0}),
            "by_day": defaultdict(lambda: {"success": 0, "total": 0}),
            "by_task_type": defaultdict(lambda: {"success": 0, "total": 0}),
            "by_window_position": {"early": {"success": 0, "total": 0},
                                   "mid": {"success": 0, "total": 0},
                                   "late": {"success": 0, "total": 0}},
        }

        for outcome in self.outcomes:
            model = outcome.get("model", "unknown")
            success = outcome.get("outcome") in ["completed", "success", "productive"]
            messages = outcome.get("messages", 0)

            # By model
            patterns["by_model"][model]["total"] += 1
            patterns["by_model"][model]["avg_messages"].append(messages)
            if success:
                patterns["by_model"][model]["success"] += 1

            # By hour
            ts = outcome.get("started_at") or outcome.get("ts")
            if ts:
                try:
                    if isinstance(ts, str):
                        dt = datetime.fromisoformat(ts.replace("Z", ""))
                    else:
                        dt = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts)
                    hour = dt.hour
                    day = dt.strftime("%A")

                    patterns["by_hour"][hour]["total"] += 1
                    if success:
                        patterns["by_hour"][hour]["success"] += 1

                    patterns["by_day"][day]["total"] += 1
                    if success:
                        patterns["by_day"][day]["success"] += 1
                except:
                    pass

            # By task type (inferred from tools used)
            tools = outcome.get("tools", 0)
            if tools > 50:
                task_type = "complex"
            elif tools > 20:
                task_type = "moderate"
            else:
                task_type = "simple"

            patterns["by_task_type"][task_type]["total"] += 1
            if success:
                patterns["by_task_type"][task_type]["success"] += 1

        # Calculate success rates
        results = {}
        for category, data in patterns.items():
            if category == "by_window_position":
                results[category] = data
            else:
                results[category] = {}
                for key, stats in data.items():
                    total = stats["total"]
                    if total > 0:
                        success_rate = stats["success"] / total
                        results[category][key] = {
                            "success_rate": round(success_rate, 3),
                            "total_sessions": total,
                            "avg_messages": round(statistics.mean(stats.get("avg_messages", [0])), 1) if "avg_messages" in stats else None
                        }

        return results

    def predict_success(self, task_description: str = None, model: str = None) -> Dict:
        """Predict success probability for a new session."""
        patterns = self.analyze_patterns()

        now = datetime.now()
        hour = now.hour
        day = now.strftime("%A")

        predictions = {
            "timestamp": now.isoformat(),
            "factors": [],
            "recommendations": [],
            "confidence": 0.5
        }

        # Hour factor
        hour_data = patterns["by_hour"].get(hour, {})
        if hour_data.get("success_rate"):
            predictions["factors"].append({
                "factor": "time_of_day",
                "hour": hour,
                "success_rate": hour_data["success_rate"],
                "sample_size": hour_data["total_sessions"]
            })
            if hour_data["success_rate"] > 0.8:
                predictions["recommendations"].append(f"Good time! {hour}:00 has {hour_data['success_rate']*100:.0f}% success rate")
            elif hour_data["success_rate"] < 0.5:
                predictions["recommendations"].append(f"Caution: {hour}:00 historically has lower success ({hour_data['success_rate']*100:.0f}%)")

        # Day factor
        day_data = patterns["by_day"].get(day, {})
        if day_data.get("success_rate"):
            predictions["factors"].append({
                "factor": "day_of_week",
                "day": day,
                "success_rate": day_data["success_rate"],
                "sample_size": day_data["total_sessions"]
            })

        # Model factor
        if model:
            model_data = patterns["by_model"].get(model, {})
            if model_data.get("success_rate"):
                predictions["factors"].append({
                    "factor": "model",
                    "model": model,
                    "success_rate": model_data["success_rate"],
                    "avg_messages": model_data.get("avg_messages")
                })

        # Best model recommendation
        best_model = max(patterns["by_model"].items(),
                        key=lambda x: x[1].get("success_rate", 0) if x[1].get("total_sessions", 0) >= 5 else 0,
                        default=(None, {}))
        if best_model[0] and best_model[1].get("success_rate", 0) > 0.7:
            predictions["recommendations"].append(
                f"Best performing model: {best_model[0]} ({best_model[1]['success_rate']*100:.0f}% success, {best_model[1]['total_sessions']} sessions)"
            )

        # Calculate overall confidence
        if predictions["factors"]:
            avg_success = statistics.mean([f["success_rate"] for f in predictions["factors"] if "success_rate" in f])
            predictions["confidence"] = round(avg_success, 3)

        return predictions


# ═══════════════════════════════════════════════════════════════════════════════
# CROSS-SESSION LEARNING SYNTHESIZER
# ═══════════════════════════════════════════════════════════════════════════════

class LearningsSynthesizer:
    """Synthesizes learnings across sessions."""

    def __init__(self):
        self.outcomes = load_jsonl(SOURCES["session_outcomes"], since_days=7)
        self.dq_scores = load_jsonl(SOURCES["dq_scores"], since_days=7)
        self.tool_usage = load_jsonl(SOURCES["tool_usage"], since_days=7)
        self.errors = load_jsonl(SOURCES["errors"], since_days=7)
        self.knowledge = load_json(SOURCES["knowledge"], {"facts": [], "decisions": [], "patterns": []})

    def synthesize_session(self, session_id: str = None) -> Dict:
        """Synthesize learnings from recent session(s)."""
        synthesis = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "learnings": [],
            "patterns_detected": [],
            "knowledge_updates": [],
            "metrics": {}
        }

        # Aggregate metrics
        total_messages = sum(o.get("messages", 0) for o in self.outcomes)
        total_tools = sum(o.get("tools", 0) for o in self.outcomes)
        total_sessions = len(self.outcomes)

        synthesis["metrics"] = {
            "sessions_analyzed": total_sessions,
            "total_messages": total_messages,
            "total_tools": total_tools,
            "avg_messages_per_session": round(total_messages / max(total_sessions, 1), 1),
            "avg_tools_per_session": round(total_tools / max(total_sessions, 1), 1)
        }

        # Analyze tool patterns
        tool_counts = Counter()
        for entry in self.tool_usage:
            tool = entry.get("tool")
            if tool:
                tool_counts[tool] += 1

        top_tools = tool_counts.most_common(5)
        if top_tools:
            synthesis["patterns_detected"].append({
                "type": "tool_preference",
                "pattern": f"Top tools: {', '.join(t[0] for t in top_tools)}",
                "data": dict(top_tools)
            })

        # Analyze DQ score trends
        if self.dq_scores:
            scores = [d.get("dqScore", d.get("dq", 0)) for d in self.dq_scores if d.get("dqScore") or d.get("dq")]
            if scores:
                avg_dq = statistics.mean(scores)
                synthesis["metrics"]["avg_dq_score"] = round(avg_dq, 3)

                if avg_dq > 0.8:
                    synthesis["learnings"].append({
                        "type": "quality",
                        "insight": f"High query quality maintained (DQ: {avg_dq:.2f})",
                        "confidence": 0.9
                    })
                elif avg_dq < 0.5:
                    synthesis["learnings"].append({
                        "type": "quality",
                        "insight": f"Query quality could improve (DQ: {avg_dq:.2f}) - try more specific questions",
                        "confidence": 0.8
                    })

        # Analyze error patterns
        if self.errors:
            error_types = Counter(e.get("type", "unknown") for e in self.errors)
            if error_types:
                synthesis["patterns_detected"].append({
                    "type": "error_frequency",
                    "pattern": f"Common errors: {dict(error_types.most_common(3))}",
                    "recommendation": "Review error patterns for improvement opportunities"
                })

        # Generate knowledge updates
        existing_facts = {f.get("content", "").lower() for f in self.knowledge.get("facts", [])}

        # Add new fact if significant pattern found
        if synthesis["metrics"]["avg_messages_per_session"] > 100:
            new_fact = f"Average session length: {synthesis['metrics']['avg_messages_per_session']:.0f} messages (intensive usage pattern)"
            if new_fact.lower() not in existing_facts:
                synthesis["knowledge_updates"].append({
                    "type": "fact",
                    "content": new_fact,
                    "tags": ["usage", "patterns"],
                    "source": "supermemory_synthesis"
                })

        return synthesis

    def weekly_synthesis(self) -> Dict:
        """Generate weekly synthesis of all learnings."""
        # Load 7 days of data
        outcomes_7d = load_jsonl(SOURCES["session_outcomes"], since_days=7)
        dq_7d = load_jsonl(SOURCES["dq_scores"], since_days=7)

        # Load daily memory logs
        daily_logs = []
        daily_dir = MEMORY_DIR / "daily"
        if daily_dir.exists():
            for f in sorted(daily_dir.glob("*.md"))[-7:]:
                daily_logs.append(f.read_text())

        synthesis = {
            "timestamp": datetime.now().isoformat(),
            "period": "weekly",
            "week_ending": datetime.now().strftime("%Y-%m-%d"),
            "summary": {},
            "trends": [],
            "insights": [],
            "recommendations": [],
            "knowledge_updates": []
        }

        # Summary stats
        synthesis["summary"] = {
            "total_sessions": len(outcomes_7d),
            "total_messages": sum(o.get("messages", 0) for o in outcomes_7d),
            "total_tools": sum(o.get("tools", 0) for o in outcomes_7d),
            "avg_dq": round(statistics.mean([d.get("dqScore", 0) for d in dq_7d]) if dq_7d else 0, 3),
            "daily_logs_analyzed": len(daily_logs)
        }

        # Detect trends
        if len(outcomes_7d) >= 3:
            # Compare first half vs second half
            mid = len(outcomes_7d) // 2
            first_half = outcomes_7d[:mid]
            second_half = outcomes_7d[mid:]

            first_avg = statistics.mean([o.get("messages", 0) for o in first_half]) if first_half else 0
            second_avg = statistics.mean([o.get("messages", 0) for o in second_half]) if second_half else 0

            if second_avg > first_avg * 1.2:
                synthesis["trends"].append({
                    "type": "increasing_intensity",
                    "description": "Session intensity increasing over the week",
                    "change": f"+{((second_avg/first_avg)-1)*100:.0f}%"
                })
            elif second_avg < first_avg * 0.8:
                synthesis["trends"].append({
                    "type": "decreasing_intensity",
                    "description": "Session intensity decreasing over the week",
                    "change": f"{((second_avg/first_avg)-1)*100:.0f}%"
                })

        # Generate insights from daily logs
        if daily_logs:
            # Look for repeated themes
            all_text = " ".join(daily_logs).lower()
            keywords = ["error", "fixed", "improved", "bug", "feature", "refactor", "test"]
            keyword_counts = {k: all_text.count(k) for k in keywords}

            dominant = max(keyword_counts.items(), key=lambda x: x[1])
            if dominant[1] > 5:
                synthesis["insights"].append({
                    "type": "weekly_focus",
                    "insight": f"Week dominated by '{dominant[0]}' activities ({dominant[1]} mentions)",
                    "confidence": 0.7
                })

        # Generate recommendations
        if synthesis["summary"]["avg_dq"] < 0.6:
            synthesis["recommendations"].append(
                "DQ score below target - focus on query specificity next week"
            )

        if synthesis["summary"]["total_sessions"] > 40:
            synthesis["recommendations"].append(
                f"High session count ({synthesis['summary']['total_sessions']}) - consider batching similar tasks"
            )

        return synthesis


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT LINKER (Connect Orphaned Data)
# ═══════════════════════════════════════════════════════════════════════════════

class ContextLinker:
    """Links orphaned data (paste cache, file history, etc.) to sessions."""

    def __init__(self):
        self.session_events = load_jsonl(SOURCES["session_events"], since_days=30)

    def index_paste_cache(self) -> List[Dict]:
        """Index paste cache entries."""
        indexed = []
        paste_dir = ORPHANED["paste_cache"]

        if paste_dir.exists():
            for f in paste_dir.iterdir():
                if f.is_file():
                    try:
                        mtime = datetime.fromtimestamp(f.stat().st_mtime)
                        size = f.stat().st_size

                        # Find closest session
                        closest_session = self._find_closest_session(mtime)

                        indexed.append({
                            "type": "paste",
                            "file": f.name,
                            "timestamp": mtime.isoformat(),
                            "size_bytes": size,
                            "session_id": closest_session,
                            "indexed_at": datetime.now().isoformat()
                        })
                    except:
                        pass

        return indexed

    def index_file_history(self) -> List[Dict]:
        """Index file history entries."""
        indexed = []
        history_dir = ORPHANED["file_history"]

        if history_dir.exists():
            for f in history_dir.iterdir():
                if f.is_file():
                    try:
                        mtime = datetime.fromtimestamp(f.stat().st_mtime)
                        closest_session = self._find_closest_session(mtime)

                        indexed.append({
                            "type": "file_history",
                            "file": f.name,
                            "timestamp": mtime.isoformat(),
                            "session_id": closest_session,
                            "indexed_at": datetime.now().isoformat()
                        })
                    except:
                        pass

        return indexed

    def index_shell_snapshots(self) -> List[Dict]:
        """Index shell snapshots."""
        indexed = []
        shell_dir = ORPHANED["shell_snapshots"]

        if shell_dir.exists():
            for f in shell_dir.iterdir():
                if f.is_file():
                    try:
                        mtime = datetime.fromtimestamp(f.stat().st_mtime)
                        closest_session = self._find_closest_session(mtime)

                        # Try to extract working directory from snapshot
                        content = f.read_text()[:500]
                        cwd = None
                        if "PWD=" in content:
                            try:
                                cwd = content.split("PWD=")[1].split("\n")[0].strip()
                            except:
                                pass

                        indexed.append({
                            "type": "shell_snapshot",
                            "file": f.name,
                            "timestamp": mtime.isoformat(),
                            "session_id": closest_session,
                            "working_directory": cwd,
                            "indexed_at": datetime.now().isoformat()
                        })
                    except:
                        pass

        return indexed

    def index_debug_dumps(self) -> List[Dict]:
        """Index debug dumps."""
        indexed = []
        debug_dir = ORPHANED["debug"]

        if debug_dir.exists():
            for f in list(debug_dir.iterdir())[:100]:  # Limit to 100
                if f.is_file():
                    try:
                        mtime = datetime.fromtimestamp(f.stat().st_mtime)
                        closest_session = self._find_closest_session(mtime)

                        indexed.append({
                            "type": "debug_dump",
                            "file": f.name,
                            "timestamp": mtime.isoformat(),
                            "size_bytes": f.stat().st_size,
                            "session_id": closest_session,
                            "indexed_at": datetime.now().isoformat()
                        })
                    except:
                        pass

        return indexed

    def _find_closest_session(self, target_time: datetime) -> Optional[str]:
        """Find the session closest to a given time."""
        closest = None
        min_diff = timedelta(hours=24)

        for event in self.session_events:
            ts = event.get("ts")
            if ts:
                try:
                    if isinstance(ts, (int, float)):
                        ts = ts / 1000 if ts > 1e12 else ts
                        event_time = datetime.fromtimestamp(ts)
                    else:
                        event_time = datetime.fromisoformat(ts.replace("Z", ""))

                    diff = abs(event_time - target_time)
                    if diff < min_diff:
                        min_diff = diff
                        closest = event.get("session_id") or event.get("pwd", "unknown")
                except:
                    pass

        return closest

    def build_full_index(self) -> Dict:
        """Build complete context index."""
        print("  Indexing paste cache...")
        paste = self.index_paste_cache()

        print("  Indexing file history...")
        files = self.index_file_history()

        print("  Indexing shell snapshots...")
        shells = self.index_shell_snapshots()

        print("  Indexing debug dumps...")
        debug = self.index_debug_dumps()

        index = {
            "built_at": datetime.now().isoformat(),
            "counts": {
                "paste_cache": len(paste),
                "file_history": len(files),
                "shell_snapshots": len(shells),
                "debug_dumps": len(debug)
            },
            "entries": paste + files + shells + debug
        }

        # Save to index file
        for entry in index["entries"]:
            append_jsonl(CONTEXT_INDEX, entry)

        return index


# ═══════════════════════════════════════════════════════════════════════════════
# PRE-SESSION BRIEFING GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

class BriefingGenerator:
    """Generates intelligent pre-session briefing."""

    def __init__(self):
        self.predictor = SessionSuccessPredictor()
        self.synthesizer = LearningsSynthesizer()

    def generate_briefing(self) -> Dict:
        """Generate comprehensive pre-session briefing."""
        briefing = {
            "generated_at": datetime.now().isoformat(),
            "predictions": {},
            "recent_learnings": [],
            "recommendations": [],
            "context": {},
            "warnings": []
        }

        # Get predictions
        briefing["predictions"] = self.predictor.predict_success()

        # Get recent synthesis
        synthesis = self.synthesizer.synthesize_session()
        briefing["recent_learnings"] = synthesis.get("learnings", [])

        # Load session state
        session_state = load_json(SOURCES["session_state"], {})
        if session_state:
            capacity = session_state.get("capacity", {})
            tier = capacity.get("tier", "UNKNOWN")

            briefing["context"]["capacity_tier"] = tier
            briefing["context"]["opus_remaining"] = capacity.get("opus", 0)
            briefing["context"]["sonnet_remaining"] = capacity.get("sonnet", 0)

            if tier == "CRITICAL":
                briefing["warnings"].append("Capacity CRITICAL - use Haiku only")
            elif tier == "LOW":
                briefing["warnings"].append("Capacity LOW - avoid Opus")

        # Load identity for personalization
        identity = load_json(SOURCES["identity"], {})
        if identity:
            expertise = identity.get("expertise", {})
            if isinstance(expertise, dict):
                briefing["context"]["expertise"] = expertise.get("domains", [])[:5]
            elif isinstance(expertise, list):
                briefing["context"]["expertise"] = expertise[:5]
            else:
                briefing["context"]["expertise"] = []
            briefing["context"]["preferences"] = identity.get("preferences", {})

        # Load recent patterns
        patterns = load_json(SOURCES["detected_patterns"], {})
        if patterns.get("patterns"):
            top_pattern = patterns["patterns"][0] if patterns["patterns"] else {}
            if top_pattern:
                briefing["context"]["detected_pattern"] = top_pattern.get("id", "none")
                briefing["context"]["pattern_confidence"] = top_pattern.get("confidence", 0)

        # Generate recommendations
        if briefing["predictions"].get("recommendations"):
            briefing["recommendations"].extend(briefing["predictions"]["recommendations"])

        # Check if it's been a while since last session
        outcomes = load_jsonl(SOURCES["session_outcomes"], limit=1)
        if outcomes:
            last = outcomes[-1]
            last_ts = last.get("started_at") or last.get("ts")
            if last_ts:
                try:
                    if isinstance(last_ts, str):
                        last_time = datetime.fromisoformat(last_ts.replace("Z", ""))
                    else:
                        last_time = datetime.fromtimestamp(last_ts / 1000 if last_ts > 1e12 else last_ts)

                    hours_since = (datetime.now() - last_time).total_seconds() / 3600
                    if hours_since > 24:
                        briefing["recommendations"].append(
                            f"Welcome back! Last session was {hours_since:.0f}h ago. Consider reviewing recent context."
                        )
                except:
                    pass

        # Save briefing
        save_json(BRIEFING_FILE, briefing)

        return briefing


# ═══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE AUTO-UPDATER
# ═══════════════════════════════════════════════════════════════════════════════

class KnowledgeUpdater:
    """Automatically updates knowledge.json from observed patterns."""

    def __init__(self):
        self.knowledge = load_json(SOURCES["knowledge"], {
            "facts": [], "decisions": [], "patterns": [], "context": {}, "projects": {}
        })

    def update_from_synthesis(self, synthesis: Dict) -> List[Dict]:
        """Update knowledge from synthesis results."""
        updates = []

        for update in synthesis.get("knowledge_updates", []):
            update_type = update.get("type", "fact")
            content = update.get("content")

            if not content:
                continue

            # Check if similar already exists
            existing = self.knowledge.get(f"{update_type}s", [])
            exists = any(
                content.lower() in e.get("content", "").lower() or
                e.get("content", "").lower() in content.lower()
                for e in existing
            )

            if not exists:
                new_entry = {
                    "content": content,
                    "tags": update.get("tags", ["auto-generated"]),
                    "timestamp": datetime.now().isoformat(),
                    "source": update.get("source", "supermemory"),
                    "id": len(existing) + 1
                }
                self.knowledge[f"{update_type}s"].append(new_entry)
                updates.append(new_entry)

        if updates:
            save_json(SOURCES["knowledge"], self.knowledge)

        return updates

    def add_fact(self, content: str, tags: List[str] = None) -> bool:
        """Add a new fact to knowledge base."""
        existing = self.knowledge.get("facts", [])

        # Check for duplicates
        for fact in existing:
            if content.lower() in fact.get("content", "").lower():
                return False

        new_fact = {
            "content": content,
            "tags": tags or ["auto-generated"],
            "timestamp": datetime.now().isoformat(),
            "source": "supermemory",
            "id": len(existing) + 1
        }

        self.knowledge["facts"].append(new_fact)
        save_json(SOURCES["knowledge"], self.knowledge)
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CLI
# ═══════════════════════════════════════════════════════════════════════════════

def print_briefing(briefing: Dict):
    """Pretty print briefing."""
    print("\n" + "=" * 60)
    print("  SUPERMEMORY PRE-SESSION BRIEFING")
    print("=" * 60)

    # Predictions
    pred = briefing.get("predictions", {})
    print(f"\n  Confidence: {pred.get('confidence', 0)*100:.0f}%")

    # Warnings
    if briefing.get("warnings"):
        print("\n  WARNINGS:")
        for w in briefing["warnings"]:
            print(f"    ! {w}")

    # Recommendations
    if briefing.get("recommendations"):
        print("\n  RECOMMENDATIONS:")
        for r in briefing["recommendations"]:
            print(f"    - {r}")

    # Context
    ctx = briefing.get("context", {})
    if ctx:
        print("\n  CONTEXT:")
        if ctx.get("capacity_tier"):
            print(f"    Capacity: {ctx['capacity_tier']}")
        if ctx.get("opus_remaining"):
            print(f"    Opus: {ctx['opus_remaining']} | Sonnet: {ctx.get('sonnet_remaining', '?')}")
        if ctx.get("detected_pattern"):
            print(f"    Pattern: {ctx['detected_pattern']} ({ctx.get('pattern_confidence', 0)*100:.0f}%)")

    print("\n" + "=" * 60 + "\n")


def print_synthesis(synthesis: Dict):
    """Pretty print synthesis."""
    print("\n" + "=" * 60)
    print("  SUPERMEMORY SESSION SYNTHESIS")
    print("=" * 60)

    metrics = synthesis.get("metrics", {})
    print(f"\n  Sessions: {metrics.get('sessions_analyzed', 0)}")
    print(f"  Messages: {metrics.get('total_messages', 0)}")
    print(f"  Avg DQ: {metrics.get('avg_dq_score', 0)}")

    if synthesis.get("learnings"):
        print("\n  LEARNINGS:")
        for l in synthesis["learnings"]:
            print(f"    - {l.get('insight', '')}")

    if synthesis.get("patterns_detected"):
        print("\n  PATTERNS:")
        for p in synthesis["patterns_detected"]:
            print(f"    - {p.get('pattern', '')}")

    if synthesis.get("knowledge_updates"):
        print("\n  KNOWLEDGE UPDATES:")
        for u in synthesis["knowledge_updates"]:
            print(f"    + {u.get('content', '')[:60]}...")

    print("\n" + "=" * 60 + "\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # Check for --quiet flag
    quiet = "--quiet" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--quiet"]
    command = args[0] if args else ""

    if command == "briefing":
        if not quiet:
            print("Generating pre-session briefing...")
        generator = BriefingGenerator()
        briefing = generator.generate_briefing()
        if not quiet:
            print_briefing(briefing)
            print(f"Saved to: {BRIEFING_FILE}")

    elif command == "synthesize":
        if not quiet:
            print("Synthesizing session learnings...")
        synthesizer = LearningsSynthesizer()
        synthesis = synthesizer.synthesize_session()
        if not quiet:
            print_synthesis(synthesis)

        # Auto-update knowledge
        updater = KnowledgeUpdater()
        updates = updater.update_from_synthesis(synthesis)
        if not quiet and updates:
            print(f"Added {len(updates)} new knowledge entries")

        # Save synthesis
        append_jsonl(SYNTHESIS_FILE, synthesis)
        if not quiet:
            print(f"Saved to: {SYNTHESIS_FILE}")

    elif command == "weekly":
        if not quiet:
            print("Generating weekly synthesis...")
        synthesizer = LearningsSynthesizer()
        weekly = synthesizer.weekly_synthesis()

        if not quiet:
            print("\n" + "=" * 60)
            print("  WEEKLY SYNTHESIS")
            print("=" * 60)
            print(f"\n  Period ending: {weekly.get('week_ending')}")
            print(f"  Sessions: {weekly['summary'].get('total_sessions', 0)}")
            print(f"  Messages: {weekly['summary'].get('total_messages', 0)}")
            print(f"  Avg DQ: {weekly['summary'].get('avg_dq', 0)}")

            if weekly.get("trends"):
                print("\n  TRENDS:")
                for t in weekly["trends"]:
                    print(f"    - {t.get('description', '')} ({t.get('change', '')})")

            if weekly.get("insights"):
                print("\n  INSIGHTS:")
                for i in weekly["insights"]:
                    print(f"    - {i.get('insight', '')}")

            if weekly.get("recommendations"):
                print("\n  RECOMMENDATIONS:")
                for r in weekly["recommendations"]:
                    print(f"    - {r}")

            print("\n" + "=" * 60 + "\n")

        append_jsonl(WEEKLY_FILE, weekly)
        if not quiet:
            print(f"Saved to: {WEEKLY_FILE}")

    elif command == "link-context":
        if not quiet:
            print("Linking orphaned context data...")
        linker = ContextLinker()
        index = linker.build_full_index()

        if not quiet:
            print(f"\n  Indexed:")
            for source, count in index["counts"].items():
                print(f"    {source}: {count}")
            print(f"\n  Total: {len(index['entries'])} entries")
            print(f"  Saved to: {CONTEXT_INDEX}")

    elif command == "predict":
        task = args[1] if len(args) > 1 else None
        if not quiet:
            print("Generating prediction...")
        predictor = SessionSuccessPredictor()
        prediction = predictor.predict_success(task)

        if not quiet:
            print(f"\n  Success Confidence: {prediction.get('confidence', 0)*100:.0f}%")
            if prediction.get("recommendations"):
                print("\n  Recommendations:")
                for r in prediction["recommendations"]:
                    print(f"    - {r}")

        append_jsonl(PREDICTIONS_FILE, prediction)

    elif command == "status":
        print("\n" + "=" * 60)
        print("  SUPERMEMORY STATUS")
        print("=" * 60)

        # Check data sources
        print("\n  DATA SOURCES:")
        total_lines = 0
        for name, path in SOURCES.items():
            if path.exists():
                if path.suffix == ".jsonl":
                    lines = sum(1 for _ in open(path))
                    total_lines += lines
                    print(f"    {name}: {lines} entries")
                else:
                    print(f"    {name}: exists")
            else:
                print(f"    {name}: MISSING")

        print(f"\n  Total tracked events: {total_lines:,}")

        # Check orphaned data
        print("\n  ORPHANED DATA:")
        for name, path in ORPHANED.items():
            if path.exists():
                count = len(list(path.iterdir()))
                print(f"    {name}: {count} items")
            else:
                print(f"    {name}: not found")

        # Check supermemory outputs
        print("\n  SUPERMEMORY OUTPUTS:")
        if BRIEFING_FILE.exists():
            print(f"    Last briefing: {BRIEFING_FILE.stat().st_mtime}")
        if SYNTHESIS_FILE.exists():
            lines = sum(1 for _ in open(SYNTHESIS_FILE))
            print(f"    Syntheses: {lines}")
        if CONTEXT_INDEX.exists():
            lines = sum(1 for _ in open(CONTEXT_INDEX))
            print(f"    Context index: {lines} entries")

        print("\n" + "=" * 60 + "\n")

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
