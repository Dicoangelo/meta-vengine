#!/usr/bin/env python3
"""
Lightweight pattern detector for session-end hook.
Detects patterns from recent session and updates trends.
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

PATTERNS = {
    "architecture": ["architect", "design", "structure", "system", "refactor", "plan", "component"],
    "research": ["research", "explore", "investigate", "understand", "analyze", "find", "search", "how does"],
    "debugging": ["debug", "fix", "bug", "error", "issue", "broken", "not working", "fails"],
    "testing": ["test", "spec", "coverage", "vitest", "jest", "pytest", "assert"],
    "implementation": ["implement", "build", "create", "add", "feature", "develop", "write"],
    "deployment": ["deploy", "release", "publish", "production", "docker", "ci/cd"],
    "documentation": ["doc", "readme", "comment", "explain", "markdown"],
    "review": ["review", "pr", "pull request", "audit", "check"],
    "learning": ["learn", "tutorial", "how to", "teach", "example"],
    "optimization": ["optim", "performance", "speed", "efficient", "cache"]
}

ICONS = {
    "architecture": "🏗️", "research": "📚", "debugging": "🐛", "testing": "🧪",
    "implementation": "⚙️", "deployment": "🚀", "documentation": "📝",
    "review": "👀", "learning": "🎓", "optimization": "⚡"
}


def detect_pattern(text: str) -> str:
    """Detect primary pattern from text."""
    text = text.lower()
    scores = {}

    for pid, keywords in PATTERNS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[pid] = score

    if scores:
        return max(scores, key=scores.get)
    return "implementation"  # default


def update_trends(pattern: str, date: str):
    """Update pattern trends file."""
    home = Path.home()
    trends_file = home / ".claude/kernel/pattern-trends.json"

    trends = {"daily": {}, "weekly": {}, "top_patterns": [], "percentages": {}, "all_time": {}, "total_sessions": 0}

    if trends_file.exists():
        try:
            with open(trends_file) as f:
                trends = json.load(f)
        except:
            pass

    # Update daily
    if date not in trends.get("daily", {}):
        trends["daily"][date] = {}
    trends["daily"][date][pattern] = trends["daily"][date].get(pattern, 0) + 1

    # Update weekly
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        week = (dt - timedelta(days=dt.weekday())).strftime("%Y-%m-%d")
        if week not in trends.get("weekly", {}):
            trends["weekly"][week] = {}
        trends["weekly"][week][pattern] = trends["weekly"][week].get(pattern, 0) + 1
    except:
        pass

    # Update all-time
    trends["all_time"][pattern] = trends.get("all_time", {}).get(pattern, 0) + 1
    trends["total_sessions"] = trends.get("total_sessions", 0) + 1

    # Recalculate percentages
    total = sum(trends.get("all_time", {}).values())
    if total > 0:
        trends["percentages"] = {p: round(c / total * 100, 1) for p, c in trends.get("all_time", {}).items()}
        trends["top_patterns"] = [
            {"id": p, "count": c, "percentage": trends["percentages"].get(p, 0)}
            for p, c in sorted(trends.get("all_time", {}).items(), key=lambda x: x[1], reverse=True)
        ]

    trends["generated"] = datetime.now().isoformat()

    with open(trends_file, "w") as f:
        json.dump(trends, f, indent=2)


def log_pattern(session_id: str, pattern: str, date: str, messages: int = 0, tools: int = 0):
    """Log pattern to history file."""
    home = Path.home()
    history_file = home / ".claude/kernel/pattern-history.jsonl"

    entry = {
        "date": date,
        "session_id": session_id,
        "patterns": [{"id": pattern, "icon": ICONS.get(pattern, "📊"), "confidence": 1.0}],
        "messages": messages,
        "tools": tools,
        "detected_at": datetime.now().isoformat()
    }

    with open(history_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main():
    # Get session context from stdin or args
    context = ""
    session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    messages = 0
    tools = 0

    if len(sys.argv) > 1:
        context = " ".join(sys.argv[1:])
    else:
        # Try to read from recent session outcomes
        outcomes_file = Path.home() / ".claude/data/session-outcomes.jsonl"
        if outcomes_file.exists():
            try:
                with open(outcomes_file) as f:
                    lines = f.readlines()
                    if lines:
                        last = json.loads(lines[-1])
                        context = f"{last.get('title', '')} {last.get('intent', '')}"
                        session_id = last.get('session_id', session_id)
                        messages = last.get('messages', 0)
                        tools = last.get('tools', 0)
            except:
                pass

    if not context or len(context) < 5:
        return  # Nothing to detect

    date = datetime.now().strftime("%Y-%m-%d")
    pattern = detect_pattern(context)

    # Log and update
    log_pattern(session_id, pattern, date, messages, tools)
    update_trends(pattern, date)

    print(f"{ICONS.get(pattern, '📊')} Pattern: {pattern}")


if __name__ == "__main__":
    main()
