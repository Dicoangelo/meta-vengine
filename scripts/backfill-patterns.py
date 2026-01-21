#!/usr/bin/env python3
"""
Pattern Backfill Script
Analyzes historical session data to detect patterns and build trends.

Outputs:
- ~/.claude/kernel/pattern-history.jsonl - Per-session pattern detections
- ~/.claude/kernel/pattern-trends.json - Daily/weekly frequency trends
- Updates detected-patterns.json with historical data
"""

import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter

# Pattern definitions with keywords
PATTERNS = {
    "architecture": {
        "name": "Architecture Design",
        "icon": "🏗️",
        "keywords": ["architect", "design", "structure", "system", "component", "module", "refactor", "pattern", "organize", "plan"],
        "title_patterns": [r"implement.*plan", r"design", r"architect", r"structure", r"refactor"]
    },
    "research": {
        "name": "Research Session",
        "icon": "📚",
        "keywords": ["research", "explore", "investigate", "understand", "analyze", "study", "learn", "find", "search", "discover"],
        "title_patterns": [r"research", r"explore", r"understand", r"how does", r"what is", r"find"]
    },
    "debugging": {
        "name": "Debugging",
        "icon": "🐛",
        "keywords": ["debug", "fix", "bug", "error", "issue", "problem", "broken", "not working", "fails", "crash"],
        "title_patterns": [r"fix", r"bug", r"error", r"debug", r"issue", r"broken", r"not working"]
    },
    "testing": {
        "name": "Testing",
        "icon": "🧪",
        "keywords": ["test", "spec", "coverage", "unit", "integration", "e2e", "assert", "expect", "mock"],
        "title_patterns": [r"test", r"spec", r"coverage", r"vitest", r"jest", r"pytest"]
    },
    "implementation": {
        "name": "Implementation",
        "icon": "⚙️",
        "keywords": ["implement", "build", "create", "add", "feature", "develop", "code", "write"],
        "title_patterns": [r"implement", r"build", r"create", r"add.*feature", r"develop"]
    },
    "deployment": {
        "name": "Deployment",
        "icon": "🚀",
        "keywords": ["deploy", "release", "publish", "production", "ci/cd", "pipeline", "docker", "kubernetes"],
        "title_patterns": [r"deploy", r"release", r"publish", r"production", r"docker", r"k8s"]
    },
    "documentation": {
        "name": "Documentation",
        "icon": "📝",
        "keywords": ["doc", "readme", "comment", "explain", "describe", "document", "markdown"],
        "title_patterns": [r"document", r"readme", r"comment", r"explain", r"\.md"]
    },
    "review": {
        "name": "Code Review",
        "icon": "👀",
        "keywords": ["review", "pr", "pull request", "check", "audit", "inspect", "verify"],
        "title_patterns": [r"review", r"pr", r"pull request", r"audit", r"check"]
    },
    "learning": {
        "name": "Learning",
        "icon": "🎓",
        "keywords": ["learn", "tutorial", "example", "how to", "guide", "teach", "explain"],
        "title_patterns": [r"learn", r"tutorial", r"how to", r"teach me", r"explain"]
    },
    "optimization": {
        "name": "Optimization",
        "icon": "⚡",
        "keywords": ["optimize", "performance", "speed", "fast", "efficient", "improve", "cache"],
        "title_patterns": [r"optim", r"performance", r"speed", r"fast", r"efficien", r"cache"]
    }
}


def detect_pattern(title: str, intent: str, messages: int, tools: int) -> list:
    """Detect patterns from session metadata."""
    text = f"{title} {intent}".lower()
    detected = []

    for pattern_id, config in PATTERNS.items():
        score = 0
        matches = []

        # Check keywords
        for keyword in config["keywords"]:
            if keyword in text:
                score += 1
                matches.append(keyword)

        # Check title patterns
        for regex in config["title_patterns"]:
            if re.search(regex, text, re.IGNORECASE):
                score += 2
                matches.append(f"regex:{regex}")

        # Heuristics based on session characteristics
        if pattern_id == "architecture" and messages > 200:
            score += 1
        if pattern_id == "debugging" and tools > 50:
            score += 1
        if pattern_id == "testing" and "test" in text:
            score += 2

        if score >= 2:
            confidence = min(1.0, score / 5)
            detected.append({
                "id": pattern_id,
                "name": config["name"],
                "icon": config["icon"],
                "confidence": confidence,
                "matches": matches[:5]
            })

    # Sort by confidence
    detected.sort(key=lambda x: x["confidence"], reverse=True)

    # Default to implementation if nothing detected and has significant activity
    if not detected and messages > 10:
        detected.append({
            "id": "implementation",
            "name": "Implementation",
            "icon": "⚙️",
            "confidence": 0.5,
            "matches": ["default"]
        })

    return detected[:3]  # Top 3 patterns


def main():
    home = Path.home()
    outcomes_file = home / ".claude/data/session-outcomes.jsonl"
    history_file = home / ".claude/kernel/pattern-history.jsonl"
    trends_file = home / ".claude/kernel/pattern-trends.json"
    patterns_file = home / ".claude/kernel/detected-patterns.json"

    if not outcomes_file.exists():
        print("No session-outcomes.jsonl found")
        return

    # Load all sessions
    sessions = []
    with open(outcomes_file) as f:
        for line in f:
            if line.strip():
                try:
                    sessions.append(json.loads(line))
                except:
                    pass

    print(f"Loaded {len(sessions)} sessions")

    # Detect patterns for each session
    pattern_history = []
    daily_patterns = defaultdict(lambda: Counter())
    weekly_patterns = defaultdict(lambda: Counter())
    all_time_patterns = Counter()

    for session in sessions:
        date = session.get("date", "") or ""
        title = session.get("title", "") or ""
        intent = session.get("intent", "") or ""
        messages = session.get("messages", 0) or 0
        tools = session.get("tools", 0) or 0

        # Skip warmup/trivial sessions
        if messages < 3 or "warmup" in title.lower():
            continue

        detected = detect_pattern(title, intent, messages, tools)

        if detected:
            # Record in history
            pattern_history.append({
                "date": date,
                "session_id": session.get("session_id", ""),
                "patterns": detected,
                "messages": messages,
                "tools": tools
            })

            # Aggregate counts
            primary = detected[0]["id"]
            daily_patterns[date][primary] += 1

            # Calculate week
            try:
                dt = datetime.strptime(date, "%Y-%m-%d")
                week_start = (dt - timedelta(days=dt.weekday())).strftime("%Y-%m-%d")
                weekly_patterns[week_start][primary] += 1
            except:
                pass

            all_time_patterns[primary] += 1

    print(f"Detected patterns in {len(pattern_history)} sessions")

    # Write pattern history
    with open(history_file, "w") as f:
        for entry in pattern_history:
            f.write(json.dumps(entry) + "\n")
    print(f"Wrote pattern history to {history_file}")

    # Build trends data
    trends = {
        "generated": datetime.now().isoformat(),
        "total_sessions": len(pattern_history),
        "all_time": dict(all_time_patterns),
        "daily": {date: dict(counts) for date, counts in sorted(daily_patterns.items())},
        "weekly": {week: dict(counts) for week, counts in sorted(weekly_patterns.items())},
        "pattern_definitions": {pid: {"name": p["name"], "icon": p["icon"]} for pid, p in PATTERNS.items()}
    }

    # Calculate percentages
    total = sum(all_time_patterns.values())
    trends["percentages"] = {
        pid: round(count / total * 100, 1) if total > 0 else 0
        for pid, count in all_time_patterns.items()
    }

    # Top patterns
    trends["top_patterns"] = [
        {"id": pid, "count": count, "percentage": trends["percentages"].get(pid, 0)}
        for pid, count in all_time_patterns.most_common(10)
    ]

    with open(trends_file, "w") as f:
        json.dump(trends, f, indent=2)
    print(f"Wrote pattern trends to {trends_file}")

    # Update detected-patterns.json with enriched historical data
    existing = {}
    if patterns_file.exists():
        try:
            with open(patterns_file) as f:
                existing = json.load(f)
        except:
            pass

    # Merge with historical stats
    enriched_patterns = []
    for pid, count in all_time_patterns.most_common():
        config = PATTERNS.get(pid, {})
        enriched_patterns.append({
            "id": pid,
            "name": config.get("name", pid),
            "icon": config.get("icon", "📊"),
            "confidence": 1.0 if count >= 10 else 0.5 + (count / 20),
            "totalMatches": count,
            "percentage": trends["percentages"].get(pid, 0),
            "historical": True
        })

    # Preserve recent patterns from live detection
    live_patterns = existing.get("patterns", [])
    for lp in live_patterns:
        if not lp.get("historical"):
            # Check if already in enriched
            found = False
            for ep in enriched_patterns:
                if ep["id"] == lp.get("id"):
                    ep["recentMatches"] = lp.get("totalMatches", 0)
                    found = True
                    break
            if not found:
                enriched_patterns.append(lp)

    updated = {
        "detectedAt": datetime.now().isoformat(),
        "windowMinutes": 9999,  # All time
        "activityCount": len(pattern_history),
        "backfilled": True,
        "patterns": enriched_patterns
    }

    with open(patterns_file, "w") as f:
        json.dump(updated, f, indent=2)
    print(f"Updated detected-patterns.json with historical data")

    # Summary
    print("\n" + "="*50)
    print("PATTERN BACKFILL SUMMARY")
    print("="*50)
    print(f"Sessions analyzed: {len(pattern_history)}")
    print(f"Date range: {min(daily_patterns.keys())} to {max(daily_patterns.keys())}")
    print("\nTop patterns (all time):")
    for pid, count in all_time_patterns.most_common(5):
        pct = trends["percentages"].get(pid, 0)
        icon = PATTERNS.get(pid, {}).get("icon", "📊")
        name = PATTERNS.get(pid, {}).get("name", pid)
        print(f"  {icon} {name}: {count} sessions ({pct}%)")


if __name__ == "__main__":
    main()
