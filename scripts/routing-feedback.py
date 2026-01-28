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

def collect_feedback():
    """Collect routing feedback from last session."""
    session = get_last_session()
    routing = get_last_routing_decision()
    dq = get_last_dq_score()

    if not session:
        return None

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
    success = outcome == "success"

    # Calculate if routing was correct
    routing_correct = predicted_model == actual_model if predicted_model else None

    # Build feedback entry
    feedback = {
        "ts": datetime.now().timestamp(),
        "session_id": session.get("session_id", ""),
        "predicted_model": predicted_model,
        "actual_model": actual_model,
        "routing_correct": routing_correct,
        "session_outcome": outcome,
        "session_success": success,
        "dq_score": dq.get("dqScore") if dq else None,
        "complexity": dq.get("complexity") if dq else None,
        "messages": session.get("messages", 0),
        "tools": session.get("tools", 0),
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
    """Analyze collected feedback for routing accuracy."""
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
    correct = sum(1 for e in entries if e.get("routing_correct") == True)
    success = sum(1 for e in entries if e.get("session_success") == True)

    print(f"Routing Feedback Analysis")
    print(f"=" * 40)
    print(f"Total entries: {total}")
    print(f"Routing accuracy: {correct}/{total} ({correct/total*100:.1f}%)")
    print(f"Session success: {success}/{total} ({success/total*100:.1f}%)")

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
