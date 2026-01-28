#!/usr/bin/env python3
"""
CCC Intelligence Layer - Leverage Points

Connects the autonomous brain to actionable predictions:
1. Predictive Model Routing - Know which model before you ask
2. Proactive Context Loading - Pre-fetch what you'll need
3. Cost Anomaly Prevention - Catch overspend before it happens
4. Session Success Prediction - Know if a session will succeed
5. Optimal Timing Advisor - Best times for different task types
6. Auto-Complexity Detection - Route by actual complexity
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from zoneinfo import ZoneInfo
from typing import Dict, List, Tuple, Optional

LOCAL_TZ = ZoneInfo("America/New_York")
HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
DATA_DIR = CLAUDE_DIR / "data"
KERNEL_DIR = CLAUDE_DIR / "kernel"
MEMORY_DB = CLAUDE_DIR / "memory/supermemory.db"


# ============================================================================
# 1. PREDICTIVE MODEL ROUTING
# ============================================================================

class PredictiveRouter:
    """Predict optimal model based on query characteristics and history."""
    
    def __init__(self):
        self.routing_history = self._load_routing_history()
        self.outcome_correlations = self._compute_correlations()
    
    def _load_routing_history(self) -> List[Dict]:
        """Load routing decisions and their outcomes."""
        routing_file = DATA_DIR / "routing-metrics.jsonl"
        outcomes_file = DATA_DIR / "session-outcomes.jsonl"
        
        routing = []
        if routing_file.exists():
            for line in routing_file.read_text().split('\n')[-1000:]:  # Last 1000
                if line.strip():
                    try:
                        routing.append(json.loads(line))
                    except:
                        pass
        return routing
    
    def _compute_correlations(self) -> Dict:
        """Correlate routing choices with session quality."""
        # Model → average quality score
        model_quality = defaultdict(list)
        
        outcomes_file = DATA_DIR / "session-outcomes.jsonl"
        if outcomes_file.exists():
            for line in outcomes_file.read_text().split('\n')[-500:]:
                if line.strip():
                    try:
                        o = json.loads(line)
                        model = o.get("model", "unknown")
                        quality = o.get("quality", 3)
                        model_quality[model].append(quality)
                    except:
                        pass
        
        return {
            model: sum(scores) / len(scores) if scores else 3.0
            for model, scores in model_quality.items()
        }
    
    def predict_optimal_model(self, query: str, context: Dict = None) -> Dict:
        """Predict best model for a query."""
        # Analyze query complexity
        complexity_signals = {
            "architecture": 0.9,
            "design": 0.8,
            "implement": 0.6,
            "fix": 0.4,
            "simple": 0.2,
            "quick": 0.2,
            "explain": 0.3,
            "refactor": 0.7,
            "debug": 0.5,
        }
        
        query_lower = query.lower()
        detected_complexity = 0.5  # Default
        
        for signal, weight in complexity_signals.items():
            if signal in query_lower:
                detected_complexity = max(detected_complexity, weight)
        
        # Check time of day (your peak hours)
        hour = datetime.now(LOCAL_TZ).hour
        peak_hours = [20, 12, 2]  # Your best hours
        is_peak = hour in peak_hours
        
        # Recommendation
        if detected_complexity >= 0.7:
            model = "opus"
            confidence = 0.85
        elif detected_complexity >= 0.4:
            model = "sonnet"
            confidence = 0.80
        else:
            model = "haiku"
            confidence = 0.75
        
        # Boost confidence during peak hours
        if is_peak:
            confidence = min(confidence + 0.1, 0.95)
        
        return {
            "recommended_model": model,
            "confidence": confidence,
            "detected_complexity": detected_complexity,
            "is_peak_hour": is_peak,
            "model_quality_history": self.outcome_correlations,
        }


# ============================================================================
# 2. PROACTIVE CONTEXT LOADING
# ============================================================================

class ContextPredictor:
    """Predict what context will be needed based on patterns."""
    
    def __init__(self):
        self.tool_patterns = self._analyze_tool_sequences()
    
    def _analyze_tool_sequences(self) -> Dict:
        """Find common tool usage sequences."""
        tool_file = DATA_DIR / "tool-usage.jsonl"
        sequences = defaultdict(lambda: defaultdict(int))
        
        if tool_file.exists():
            prev_tool = None
            for line in tool_file.read_text().split('\n')[-5000:]:
                if line.strip():
                    try:
                        t = json.loads(line)
                        tool = t.get("tool", "unknown")
                        if prev_tool:
                            sequences[prev_tool][tool] += 1
                        prev_tool = tool
                    except:
                        pass
        
        # Convert to probabilities
        patterns = {}
        for tool, nexts in sequences.items():
            total = sum(nexts.values())
            patterns[tool] = {
                next_tool: count / total
                for next_tool, count in sorted(nexts.items(), key=lambda x: -x[1])[:5]
            }
        
        return patterns
    
    def predict_needed_context(self, current_tools: List[str]) -> List[Dict]:
        """Predict what files/context will be needed next."""
        predictions = []
        
        if current_tools:
            last_tool = current_tools[-1]
            if last_tool in self.tool_patterns:
                for next_tool, prob in self.tool_patterns[last_tool].items():
                    if prob > 0.1:  # >10% probability
                        predictions.append({
                            "likely_next_tool": next_tool,
                            "probability": prob,
                            "suggested_prefetch": self._tool_to_context(next_tool)
                        })
        
        return predictions[:3]  # Top 3
    
    def _tool_to_context(self, tool: str) -> str:
        """Map tool to context that should be prefetched."""
        context_map = {
            "Read": "file_contents",
            "Grep": "search_index",
            "Edit": "file_contents",
            "Bash": "command_history",
            "WebFetch": "url_cache",
        }
        return context_map.get(tool, "general")


# ============================================================================
# 3. COST ANOMALY PREVENTION
# ============================================================================

class CostPredictor:
    """Predict and prevent cost anomalies."""
    
    def __init__(self):
        self.daily_baseline = self._compute_baseline()
        self.today_spend = self._get_today_spend()
    
    def _compute_baseline(self) -> float:
        """Compute average daily spend."""
        cost_file = DATA_DIR / "cost-tracking.jsonl"
        daily_costs = defaultdict(float)
        
        if cost_file.exists():
            for line in cost_file.read_text().split('\n')[-1000:]:
                if line.strip():
                    try:
                        c = json.loads(line)
                        ts = c.get("ts", 0)
                        date = datetime.fromtimestamp(ts, tz=LOCAL_TZ).strftime("%Y-%m-%d")
                        daily_costs[date] += c.get("cost_usd", 0)
                    except:
                        pass
        
        if daily_costs:
            return sum(daily_costs.values()) / len(daily_costs)
        return 200  # Default baseline
    
    def _get_today_spend(self) -> float:
        """Get today's spend so far."""
        cost_file = DATA_DIR / "cost-tracking.jsonl"
        today = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
        total = 0
        
        if cost_file.exists():
            for line in cost_file.read_text().split('\n')[-500:]:
                if line.strip():
                    try:
                        c = json.loads(line)
                        ts = c.get("ts", 0)
                        date = datetime.fromtimestamp(ts, tz=LOCAL_TZ).strftime("%Y-%m-%d")
                        if date == today:
                            total += c.get("cost_usd", 0)
                    except:
                        pass
        
        return total
    
    def predict_daily_total(self) -> Dict:
        """Predict end-of-day spend."""
        now = datetime.now(LOCAL_TZ)
        hour = now.hour
        hours_elapsed = hour + now.minute / 60
        hours_remaining = 24 - hours_elapsed
        
        if hours_elapsed > 0:
            hourly_rate = self.today_spend / hours_elapsed
            predicted_total = self.today_spend + (hourly_rate * hours_remaining)
        else:
            predicted_total = self.daily_baseline
        
        return {
            "today_so_far": self.today_spend,
            "predicted_total": predicted_total,
            "baseline": self.daily_baseline,
            "status": "warning" if predicted_total > self.daily_baseline * 1.5 else "ok",
            "recommended_action": self._get_recommendation(predicted_total)
        }
    
    def _get_recommendation(self, predicted: float) -> str:
        if predicted > 300:
            return "Switch to Sonnet/Haiku for remaining tasks"
        elif predicted > self.daily_baseline * 1.3:
            return "Consider batching remaining requests"
        return "On track"


# ============================================================================
# 4. SESSION SUCCESS PREDICTION
# ============================================================================

class SessionPredictor:
    """Predict session success probability."""
    
    def __init__(self):
        self.success_patterns = self._analyze_success_patterns()
    
    def _analyze_success_patterns(self) -> Dict:
        """Analyze what leads to successful sessions."""
        outcomes_file = DATA_DIR / "session-outcomes.jsonl"
        patterns = {
            "by_hour": defaultdict(lambda: {"success": 0, "total": 0}),
            "by_model": defaultdict(lambda: {"success": 0, "total": 0}),
            "by_complexity": defaultdict(lambda: {"success": 0, "total": 0}),
        }
        
        if outcomes_file.exists():
            for line in outcomes_file.read_text().split('\n')[-500:]:
                if line.strip():
                    try:
                        o = json.loads(line)
                        success = o.get("outcome") == "success"
                        ts = o.get("ts", 0)
                        hour = datetime.fromtimestamp(ts, tz=LOCAL_TZ).hour if ts else 12
                        model = o.get("model", "unknown")
                        complexity = "high" if o.get("complexity", 0.5) > 0.6 else "low"
                        
                        patterns["by_hour"][hour]["total"] += 1
                        patterns["by_model"][model]["total"] += 1
                        patterns["by_complexity"][complexity]["total"] += 1
                        
                        if success:
                            patterns["by_hour"][hour]["success"] += 1
                            patterns["by_model"][model]["success"] += 1
                            patterns["by_complexity"][complexity]["success"] += 1
                    except:
                        pass
        
        return patterns
    
    def predict_success(self, model: str, complexity: float) -> Dict:
        """Predict session success probability."""
        hour = datetime.now(LOCAL_TZ).hour
        
        # Get success rates
        hour_data = self.success_patterns["by_hour"].get(hour, {"success": 1, "total": 2})
        model_data = self.success_patterns["by_model"].get(model, {"success": 1, "total": 2})
        comp_key = "high" if complexity > 0.6 else "low"
        comp_data = self.success_patterns["by_complexity"].get(comp_key, {"success": 1, "total": 2})
        
        hour_rate = hour_data["success"] / max(hour_data["total"], 1)
        model_rate = model_data["success"] / max(model_data["total"], 1)
        comp_rate = comp_data["success"] / max(comp_data["total"], 1)
        
        # Weighted average
        overall = (hour_rate * 0.3 + model_rate * 0.4 + comp_rate * 0.3)
        
        return {
            "success_probability": overall,
            "factors": {
                "hour_factor": hour_rate,
                "model_factor": model_rate,
                "complexity_factor": comp_rate,
            },
            "recommendation": self._get_recommendation(overall, hour, model)
        }
    
    def _get_recommendation(self, prob: float, hour: int, model: str) -> str:
        if prob < 0.5:
            return f"Consider waiting for a better hour or using a different model"
        elif prob < 0.7:
            return "Proceed with caution, break into smaller tasks"
        return "Good conditions for this task"


# ============================================================================
# 5. OPTIMAL TIMING ADVISOR
# ============================================================================

class TimingAdvisor:
    """Advise on optimal times for different task types."""
    
    def __init__(self):
        self.hourly_success = self._compute_hourly_success()
    
    def _compute_hourly_success(self) -> Dict[int, Dict]:
        """Compute success rates by hour and task type."""
        outcomes_file = DATA_DIR / "session-outcomes.jsonl"
        hourly = defaultdict(lambda: {"success": 0, "total": 0, "quality_sum": 0})
        
        if outcomes_file.exists():
            for line in outcomes_file.read_text().split('\n')[-1000:]:
                if line.strip():
                    try:
                        o = json.loads(line)
                        ts = o.get("ts", 0)
                        if ts:
                            hour = datetime.fromtimestamp(ts, tz=LOCAL_TZ).hour
                            hourly[hour]["total"] += 1
                            hourly[hour]["quality_sum"] += o.get("quality", 3)
                            if o.get("outcome") == "success":
                                hourly[hour]["success"] += 1
                    except:
                        pass
        
        return dict(hourly)
    
    def get_optimal_hours(self, task_type: str = "general") -> List[Dict]:
        """Get ranked optimal hours for a task type."""
        ranked = []
        
        for hour, data in self.hourly_success.items():
            if data["total"] >= 3:  # Minimum samples
                success_rate = data["success"] / data["total"]
                avg_quality = data["quality_sum"] / data["total"]
                score = (success_rate * 0.6 + avg_quality / 5 * 0.4)
                
                ranked.append({
                    "hour": hour,
                    "score": score,
                    "success_rate": success_rate,
                    "avg_quality": avg_quality,
                    "sample_size": data["total"]
                })
        
        return sorted(ranked, key=lambda x: -x["score"])[:5]
    
    def should_start_now(self, task_complexity: float) -> Dict:
        """Should you start this task now or wait?"""
        current_hour = datetime.now(LOCAL_TZ).hour
        optimal = self.get_optimal_hours()
        
        current_rank = None
        for i, h in enumerate(optimal):
            if h["hour"] == current_hour:
                current_rank = i + 1
                current_score = h["score"]
                break
        
        if current_rank is None:
            current_score = 0.5
            current_rank = len(optimal) + 1
        
        best_hour = optimal[0] if optimal else {"hour": 20, "score": 0.8}
        
        return {
            "current_hour": current_hour,
            "current_rank": current_rank,
            "current_score": current_score,
            "best_hour": best_hour["hour"],
            "best_score": best_hour["score"],
            "recommendation": "Start now" if current_score > 0.6 else f"Consider waiting until {best_hour['hour']}:00"
        }


# ============================================================================
# UNIFIED INTELLIGENCE API
# ============================================================================

class CCCIntelligence:
    """Unified interface to all intelligence capabilities."""
    
    def __init__(self):
        self.router = PredictiveRouter()
        self.context = ContextPredictor()
        self.cost = CostPredictor()
        self.session = SessionPredictor()
        self.timing = TimingAdvisor()
    
    def analyze_query(self, query: str) -> Dict:
        """Full intelligence analysis for a query."""
        # Get model recommendation
        routing = self.router.predict_optimal_model(query)
        
        # Get timing advice
        timing = self.timing.should_start_now(routing["detected_complexity"])
        
        # Predict success
        success = self.session.predict_success(
            routing["recommended_model"],
            routing["detected_complexity"]
        )
        
        # Check cost trajectory
        cost = self.cost.predict_daily_total()
        
        return {
            "routing": routing,
            "timing": timing,
            "success_prediction": success,
            "cost_status": cost,
            "overall_recommendation": self._synthesize(routing, timing, success, cost)
        }
    
    def _synthesize(self, routing: Dict, timing: Dict, success: Dict, cost: Dict) -> str:
        """Synthesize all signals into one recommendation."""
        issues = []
        
        if success["success_probability"] < 0.5:
            issues.append("low success probability")
        if cost["status"] == "warning":
            issues.append("cost trending high")
        if timing["current_score"] < 0.5:
            issues.append("suboptimal hour")
        
        if not issues:
            return f"Proceed with {routing['recommended_model']} (confidence: {routing['confidence']:.0%})"
        else:
            return f"Caution: {', '.join(issues)}. Consider: {success['recommendation']}"
    
    def get_dashboard_data(self) -> Dict:
        """Get all intelligence data for dashboard."""
        return {
            "optimal_hours": self.timing.get_optimal_hours()[:3],
            "cost_prediction": self.cost.predict_daily_total(),
            "model_quality": self.router.outcome_correlations,
            "tool_patterns": dict(list(self.context.tool_patterns.items())[:5]),
        }


def main():
    import sys
    
    intel = CCCIntelligence()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--analyze" and len(sys.argv) > 2:
            query = " ".join(sys.argv[2:])
            result = intel.analyze_query(query)
            print(json.dumps(result, indent=2))
        elif sys.argv[1] == "--dashboard":
            print(json.dumps(intel.get_dashboard_data(), indent=2))
        elif sys.argv[1] == "--timing":
            hours = intel.timing.get_optimal_hours()
            print("Optimal Hours for Deep Work:")
            for h in hours:
                print(f"  {h['hour']:02d}:00 - Score: {h['score']:.2f} (n={h['sample_size']})")
        elif sys.argv[1] == "--cost":
            cost = intel.cost.predict_daily_total()
            print(f"Today: ${cost['today_so_far']:.2f}")
            print(f"Predicted: ${cost['predicted_total']:.2f}")
            print(f"Baseline: ${cost['baseline']:.2f}")
            print(f"Status: {cost['status']}")
        else:
            print("Usage: ccc-intelligence-layer.py [--analyze 'query' | --dashboard | --timing | --cost]")
    else:
        # Quick status
        timing = intel.timing.should_start_now(0.5)
        cost = intel.cost.predict_daily_total()
        print(f"Current hour rank: #{timing['current_rank']} (best: {timing['best_hour']}:00)")
        print(f"Cost status: {cost['status']} (${cost['today_so_far']:.2f}/${cost['predicted_total']:.2f})")


if __name__ == "__main__":
    main()
