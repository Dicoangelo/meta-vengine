#!/usr/bin/env python3
"""
Routing Backfill Script
Analyzes all historical sessions to backfill DQ scores and routing metrics.

This script:
1. Analyzes session-outcomes.jsonl for all historical sessions
2. Estimates DQ scores based on session characteristics
3. Infers model routing from models_used data
4. Creates/updates dq-scores.jsonl with historical entries
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from collections import Counter

# Complexity estimation keywords
COMPLEXITY_SIGNALS = {
    "high": ["architect", "design", "system", "complex", "refactor", "implement", "build", "create", "optimize", "debug"],
    "medium": ["fix", "update", "add", "modify", "change", "test", "review", "check"],
    "low": ["list", "show", "what", "how", "explain", "help", "simple", "quick"]
}


def estimate_complexity(title: str, intent: str, messages: int, tools: int) -> float:
    """Estimate query complexity from session data."""
    text = f"{title} {intent}".lower()

    # Base complexity from signals
    high_signals = sum(1 for kw in COMPLEXITY_SIGNALS["high"] if kw in text)
    med_signals = sum(1 for kw in COMPLEXITY_SIGNALS["medium"] if kw in text)
    low_signals = sum(1 for kw in COMPLEXITY_SIGNALS["low"] if kw in text)

    # Weight: high=0.3, medium=0.2, low=-0.1
    signal_score = (high_signals * 0.3 + med_signals * 0.2 - low_signals * 0.1)

    # Normalize based on session characteristics
    # More messages = more complex
    msg_factor = min(1.0, messages / 200) * 0.3

    # More tools = more complex
    tool_factor = min(1.0, tools / 100) * 0.2

    # Combine
    complexity = 0.3 + signal_score + msg_factor + tool_factor
    return max(0.0, min(1.0, complexity))


def estimate_dq_score(complexity: float, outcome: str, messages: int) -> float:
    """Estimate DQ score based on session data."""
    # Base DQ from complexity
    base_dq = 0.4 + (complexity * 0.4)

    # Adjust based on outcome
    outcome_adj = {
        "success": 0.15,
        "partial": 0.05,
        "abandoned": -0.1,
        "failed": -0.15
    }.get(outcome, 0)

    # Adjust based on message count (more messages might indicate lower initial DQ)
    msg_penalty = 0 if messages < 50 else -0.05 * min(3, (messages - 50) // 100)

    dq = base_dq + outcome_adj + msg_penalty
    return max(0.1, min(1.0, dq))


def infer_model(models_used: dict, complexity: float) -> str:
    """Infer primary model from session data."""
    if not models_used:
        # Estimate from complexity
        if complexity > 0.7:
            return "opus"
        elif complexity > 0.4:
            return "sonnet"
        return "haiku"

    # Return model with highest usage
    return max(models_used.keys(), key=lambda m: models_used.get(m, 0))


def main():
    home = Path.home()
    outcomes_file = home / ".claude/data/session-outcomes.jsonl"
    dq_file = home / ".claude/kernel/dq-scores.jsonl"

    if not outcomes_file.exists():
        print("No session-outcomes.jsonl found")
        return

    # Load existing DQ scores to avoid duplicates
    existing_hashes = set()
    if dq_file.exists():
        with open(dq_file) as f:
            for line in f:
                try:
                    d = json.loads(line)
                    if 'query_hash' in d:
                        existing_hashes.add(d['query_hash'])
                    elif 'session_id' in d:
                        existing_hashes.add(d['session_id'])
                except:
                    pass

    print(f"Existing DQ entries: {len(existing_hashes)}")

    # Load sessions
    sessions = []
    with open(outcomes_file) as f:
        for line in f:
            if line.strip():
                try:
                    sessions.append(json.loads(line))
                except:
                    pass

    print(f"Sessions to process: {len(sessions)}")

    # Process sessions
    new_entries = []
    model_counts = Counter()

    for session in sessions:
        session_id = session.get('session_id', '')
        title = session.get('title', '') or ''
        intent = session.get('intent', '') or ''
        messages = session.get('messages', 0) or 0
        tools = session.get('tools', 0) or 0
        outcome = session.get('outcome', '')
        models_used = session.get('models_used', {})
        date = session.get('date', '')

        # Skip if already processed
        query_hash = hashlib.md5(f"{session_id}{title}".encode()).hexdigest()
        if query_hash in existing_hashes or session_id in existing_hashes:
            continue

        # Skip warmups and trivial sessions
        if messages < 3 or 'warmup' in title.lower():
            continue

        # Estimate metrics
        complexity = estimate_complexity(title, intent, messages, tools)
        dq_score = estimate_dq_score(complexity, outcome, messages)
        model = infer_model(models_used, complexity)

        # Create entry
        entry = {
            "ts": datetime.strptime(date, "%Y-%m-%d").timestamp() if date else 0,
            "session_id": session_id,
            "query_hash": query_hash,
            "query_preview": title[:80] if title else intent[:80],
            "model": model,
            "dqScore": round(dq_score, 3),
            "complexity": round(complexity, 3),
            "outcome": outcome,
            "messages": messages,
            "tools": tools,
            "source": "backfill"
        }

        new_entries.append(entry)
        model_counts[model] += 1

    print(f"New entries to add: {len(new_entries)}")

    # Append to DQ scores file
    if new_entries:
        with open(dq_file, "a") as f:
            for entry in new_entries:
                f.write(json.dumps(entry) + "\n")

    # Summary
    print("\n" + "="*50)
    print("ROUTING BACKFILL SUMMARY")
    print("="*50)
    print(f"New entries added: {len(new_entries)}")
    print(f"Total DQ entries: {len(existing_hashes) + len(new_entries)}")
    print("\nModel distribution (new entries):")
    for model, count in model_counts.most_common():
        pct = round(count / len(new_entries) * 100, 1) if new_entries else 0
        print(f"  {model}: {count} ({pct}%)")


if __name__ == "__main__":
    main()
