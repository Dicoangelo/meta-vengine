#!/usr/bin/env python3
"""
Routing Feedback Collector

Collects feedback on routing decisions to enable self-improvement:
1. Compares predicted model vs actual model used
2. Tracks session outcome (success/fail/partial)
3. Logs to routing-feedback.jsonl for ML training

Run at session end via hook.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

HOME = Path.home()
FEEDBACK_FILE = HOME / ".claude/data/routing-feedback.jsonl"
OUTCOMES_FILE = HOME / ".claude/data/session-outcomes.jsonl"
DQ_FILE = HOME / ".claude/kernel/dq-scores.jsonl"
ROUTING_FILE = HOME / ".claude/data/routing-metrics.jsonl"

# DQ weight constants (sync with baselines.json)
DQ_WEIGHTS = {"validity": 0.35, "specificity": 0.25, "correctness": 0.40}

def get_last_session():
    """Get most recent session outcome."""
    if not OUTCOMES_FILE.exists():
        return None

    try:
        with open(OUTCOMES_FILE) as f:
            lines = f.readlines()
            if lines:
                return json.loads(lines[-1])
    except:
        pass
    return None

def get_last_routing_decision():
    """Get most recent routing decision."""
    if not ROUTING_FILE.exists():
        return None

    try:
        with open(ROUTING_FILE) as f:
            lines = f.readlines()
            if lines:
                return json.loads(lines[-1])
    except:
        pass
    return None

def get_last_dq_score():
    """Get most recent DQ score."""
    if not DQ_FILE.exists():
        return None

    try:
        with open(DQ_FILE) as f:
            lines = f.readlines()
            if lines:
                return json.loads(lines[-1])
    except:
        pass
    return None

def is_agent_session(session_id: str) -> bool:
    """Check if session is a sub-agent (not a user session)."""
    if not session_id:
        return False
    return str(session_id).startswith("agent-")


def calculate_session_quality(session: dict, outcome: str, messages: int, tools: int) -> float:
    """
    Calculate session quality score (0-5) based on multiple signals.
    This provides richer feedback signal for learning.
    """
    score = 2.5  # Neutral starting point

    # Outcome contribution (+/- 1.5)
    if outcome == "success":
        score += 1.5
    elif outcome == "partial":
        score += 0.5
    elif outcome == "abandoned":
        score -= 1.0
    elif outcome == "inconclusive":
        score += 0.0  # Neutral

    # Engagement depth (+/- 0.5)
    if messages >= 10:
        score += 0.5  # Deep engagement
    elif messages >= 5:
        score += 0.25
    elif messages < 3:
        score -= 0.25  # Very shallow

    # Tool usage indicates productive work (+0.5)
    if tools >= 3:
        score += 0.5
    elif tools >= 1:
        score += 0.25

    # Clamp to 0-5 range
    return max(0.0, min(5.0, round(score, 2)))


def enrich_dq_components(dq_entry: dict, complexity: float) -> dict:
    """
    Enrich DQ entry with components if missing.
    Uses heuristics based on model and complexity.
    """
    if dq_entry and "dqComponents" in dq_entry:
        return dq_entry.get("dqComponents")

    # Estimate components if missing
    model = dq_entry.get("model", "sonnet") if dq_entry else "sonnet"
    dq_score = dq_entry.get("dqScore", 0.5) if dq_entry else 0.5

    # Model capability ranges (sync with baselines.json)
    model_ranges = {
        "haiku": (0.0, 0.20),
        "sonnet": (0.15, 0.70),
        "opus": (0.60, 1.0)
    }

    min_c, max_c = model_ranges.get(model, (0.0, 1.0))

    # Validity: is complexity in model's range?
    if complexity <= max_c:
        validity = max(0.6, 1.0 - (max_c - complexity) * 0.2)
    else:
        validity = max(0.0, 1.0 - (complexity - max_c) * 2)

    # Specificity: is this the ideal model for complexity?
    ideal_model = "haiku" if complexity < 0.15 else "sonnet" if complexity < 0.60 else "opus"
    if model == ideal_model:
        specificity = 1.0
    elif abs(["haiku", "sonnet", "opus"].index(model) - ["haiku", "sonnet", "opus"].index(ideal_model)) == 1:
        specificity = 0.6
    else:
        specificity = 0.2

    # Correctness: estimate from DQ score and other components
    # DQ = V*0.35 + S*0.25 + C*0.40, solve for C
    weighted_others = validity * 0.35 + specificity * 0.25
    if DQ_WEIGHTS["correctness"] > 0:
        correctness = (dq_score - weighted_others) / DQ_WEIGHTS["correctness"]
        correctness = max(0.0, min(1.0, correctness))
    else:
        correctness = 0.5

    return {
        "validity": round(validity, 3),
        "specificity": round(specificity, 3),
        "correctness": round(correctness, 3),
        "estimated": True  # Flag that these are estimates
    }


def collect_feedback():
    """Collect routing feedback from last session (user sessions only)."""
    session = get_last_session()
    routing = get_last_routing_decision()
    dq = get_last_dq_score()

    if not session:
        return None

    # Skip agent/sub-agent sessions - only track user sessions
    session_id = session.get("session_id", "")
    if is_agent_session(session_id):
        return None  # Don't pollute user metrics with agent data

    # Determine actual model used
    models_used = session.get("models_used", {})
    if models_used:
        actual_model = max(models_used.keys(), key=lambda m: models_used.get(m, 0))
    else:
        actual_model = "unknown"

    # Get predicted model from routing decision
    predicted_model = None
    if routing:
        predicted_model = routing.get("predicted_model") or routing.get("actual_model")
    if dq:
        predicted_model = predicted_model or dq.get("model")

    # Determine outcome
    outcome = session.get("outcome", "partial")
    messages = session.get("messages", 0)
    tools = session.get("tools", 0)

    # Minimum engagement threshold: sessions with < 3 messages and no tool use
    # are inconclusive (user may have gotten quick answer or just left)
    MIN_MESSAGES = 3
    if messages < MIN_MESSAGES and tools == 0:
        # Inconclusive - don't count as success or failure
        success = None
        outcome = "inconclusive"
    else:
        success = outcome == "success"

    # Calculate if routing was correct
    routing_correct = predicted_model == actual_model if predicted_model else None

    # Get complexity for component enrichment
    complexity = dq.get("complexity", 0.5) if dq else 0.5

    # Enrich DQ components (fill gaps if missing)
    dq_components = enrich_dq_components(dq, complexity)

    # Calculate session quality score
    quality = calculate_session_quality(session, outcome, messages, tools)

    # Build feedback entry
    feedback = {
        "ts": datetime.now().timestamp(),
        "session_id": session.get("session_id", ""),
        "predicted_model": predicted_model,
        "actual_model": actual_model,
        "routing_correct": routing_correct,
        "session_outcome": outcome,
        "session_success": success,
        "inconclusive": outcome == "inconclusive",
        "dq_score": dq.get("dqScore") if dq else None,
        "dq_components": dq_components,
        "complexity": complexity,
        "quality": quality,
        "messages": messages,
        "tools": tools,
    }

    return feedback

def save_feedback(feedback: dict):
    """Save feedback to JSONL."""
    try:
        FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(FEEDBACK_FILE, "a") as f:
            f.write(json.dumps(feedback) + "\n")
        return True
    except:
        return False

def analyze_feedback():
    """Analyze collected feedback for routing accuracy (user sessions only)."""
    if not FEEDBACK_FILE.exists():
        print("No feedback collected yet")
        return

    entries = []
    try:
        with open(FEEDBACK_FILE) as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except:
                        pass
    except:
        pass

    if not entries:
        print("No valid feedback entries")
        return

    total = len(entries)
    inconclusive = sum(1 for e in entries if e.get("inconclusive") == True)
    conclusive = [e for e in entries if not e.get("inconclusive")]
    conclusive_count = len(conclusive)

    correct = sum(1 for e in entries if e.get("routing_correct") == True)
    success = sum(1 for e in conclusive if e.get("session_success") == True)

    print(f"Routing Feedback Analysis (User Sessions Only)")
    print(f"=" * 50)
    print(f"Total user sessions: {total}")
    print(f"Inconclusive (<3 msgs): {inconclusive} (excluded from success rate)")
    print(f"Conclusive sessions: {conclusive_count}")
    print(f"Routing accuracy: {correct}/{total} ({correct/total*100:.1f}%)")
    if conclusive_count > 0:
        print(f"Session success: {success}/{conclusive_count} ({success/conclusive_count*100:.1f}%)")

    # Model breakdown
    by_model = {}
    for e in entries:
        model = e.get("actual_model", "unknown")
        if model not in by_model:
            by_model[model] = {"total": 0, "success": 0}
        by_model[model]["total"] += 1
        if e.get("session_success"):
            by_model[model]["success"] += 1

    print(f"\nBy Model:")
    for model, data in by_model.items():
        rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
        print(f"  {model}: {data['success']}/{data['total']} ({rate:.1f}% success)")

    # Quality analysis
    qualities = [e.get("quality", 0) for e in entries if e.get("quality") is not None]
    if qualities:
        avg_quality = sum(qualities) / len(qualities)
        print(f"\nSession Quality: {avg_quality:.2f}/5.0 (n={len(qualities)})")

    # DQ component analysis
    components_with_data = [e for e in entries if e.get("dq_components")]
    if components_with_data:
        avg_v = sum(e["dq_components"].get("validity", 0) for e in components_with_data) / len(components_with_data)
        avg_s = sum(e["dq_components"].get("specificity", 0) for e in components_with_data) / len(components_with_data)
        avg_c = sum(e["dq_components"].get("correctness", 0) for e in components_with_data) / len(components_with_data)
        estimated = sum(1 for e in components_with_data if e["dq_components"].get("estimated"))
        print(f"\nDQ Components (n={len(components_with_data)}, {estimated} estimated):")
        print(f"  Validity:    {avg_v:.3f}")
        print(f"  Specificity: {avg_s:.3f}")
        print(f"  Correctness: {avg_c:.3f}")

def main():
    if "--collect" in sys.argv or len(sys.argv) == 1:
        feedback = collect_feedback()
        if feedback:
            if save_feedback(feedback):
                print(f"Feedback collected: {feedback.get('actual_model')} -> {feedback.get('session_outcome')}")
            else:
                print("Failed to save feedback")
        else:
            print("No session data to collect")
    elif "--analyze" in sys.argv:
        analyze_feedback()
    elif "--status" in sys.argv:
        if FEEDBACK_FILE.exists():
            count = sum(1 for _ in open(FEEDBACK_FILE))
            print(f"Feedback entries: {count}")
        else:
            print("No feedback file yet")
    else:
        print("Usage: routing-feedback.py [--collect|--analyze|--status]")

if __name__ == "__main__":
    main()
