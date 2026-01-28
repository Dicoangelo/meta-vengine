#!/usr/bin/env python3
"""
Pattern Orchestrator - Auto-suggest coordinator strategies based on session patterns.

Integrates pattern-detector.js with multi-agent coordinator.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple

# Paths
KERNEL_DIR = Path.home() / ".claude" / "kernel"
DATA_DIR = Path.home() / ".claude" / "data"
DETECTED_PATTERNS = KERNEL_DIR / "detected-patterns.json"
ORCHESTRATE_LOG = DATA_DIR / "pattern-orchestrate.jsonl"
ORCHESTRATE_CONFIG = KERNEL_DIR / "pattern-orchestrate-config.json"

# Default pattern to strategy mapping
PATTERN_TO_STRATEGY = {
    "debugging": {
        "strategy": "review-build",
        "description": "Builder + reviewer for bug fixes with verification",
        "agents": "builder + reviewer concurrent"
    },
    "research": {
        "strategy": "research",
        "description": "3 parallel explore agents for understanding",
        "agents": "3 explore (parallel)"
    },
    "architecture": {
        "strategy": "full",
        "description": "Complete pipeline: research → build → review",
        "agents": "research → build → review"
    },
    "refactoring": {
        "strategy": "implement",
        "description": "Parallel builders with file locks",
        "agents": "N builders (file locks)"
    },
    "feature": {
        "strategy": "implement",
        "description": "Parallel builders for new functionality",
        "agents": "N builders (file locks)"
    },
    "testing": {
        "strategy": "review-build",
        "description": "Builder + reviewer for test writing",
        "agents": "builder + reviewer concurrent"
    },
    "documentation": {
        "strategy": "research",
        "description": "Explore agents to gather before writing",
        "agents": "3 explore (parallel)"
    },
    "performance": {
        "strategy": "full",
        "description": "Profile, optimize, verify pipeline",
        "agents": "research → build → review"
    },
    "bugfix": {
        "strategy": "review-build",
        "description": "Fix with verification",
        "agents": "builder + reviewer concurrent"
    },
    "exploration": {
        "strategy": "research",
        "description": "Explore and understand codebase",
        "agents": "3 explore (parallel)"
    }
}

# Thresholds
AUTO_SPAWN_THRESHOLD = 0.8
SUGGEST_THRESHOLD = 0.5


def load_config() -> Dict:
    """Load orchestrator configuration."""
    if ORCHESTRATE_CONFIG.exists():
        return json.loads(ORCHESTRATE_CONFIG.read_text())
    return {
        "auto_spawn_threshold": AUTO_SPAWN_THRESHOLD,
        "suggest_threshold": SUGGEST_THRESHOLD,
        "max_parallel_agents": 5,
        "preload_context": True,
        "patterns": {p: s["strategy"] for p, s in PATTERN_TO_STRATEGY.items()}
    }


def load_patterns() -> Dict:
    """Load current detected patterns."""
    if DETECTED_PATTERNS.exists():
        return json.loads(DETECTED_PATTERNS.read_text())
    return {}


def get_current_pattern() -> Tuple[str, float]:
    """Get current session pattern and confidence."""
    patterns = load_patterns()

    session_type = patterns.get("current_session_type", "unknown")
    confidence = patterns.get("session_type_confidence", 0.5)

    return session_type, confidence


def suggest_strategy(pattern: str = None, confidence: float = None) -> Dict:
    """Suggest a coordination strategy based on detected pattern."""
    if pattern is None or confidence is None:
        pattern, confidence = get_current_pattern()

    config = load_config()

    # Get strategy mapping
    strategy_info = PATTERN_TO_STRATEGY.get(pattern, {
        "strategy": "implement",
        "description": "Default parallel implementation",
        "agents": "N builders"
    })

    # Determine action based on confidence
    if confidence >= config.get("auto_spawn_threshold", AUTO_SPAWN_THRESHOLD):
        action = "auto_spawn"
        message = f"High confidence ({confidence:.0%}) - auto-spawning {strategy_info['strategy']}"
    elif confidence >= config.get("suggest_threshold", SUGGEST_THRESHOLD):
        action = "suggest"
        message = f"Moderate confidence ({confidence:.0%}) - suggesting {strategy_info['strategy']}"
    else:
        action = "ask"
        message = f"Low confidence ({confidence:.0%}) - please specify strategy"

    result = {
        "timestamp": datetime.now().isoformat(),
        "detected_pattern": pattern,
        "confidence": confidence,
        "suggested_strategy": strategy_info["strategy"],
        "strategy_description": strategy_info["description"],
        "agents": strategy_info["agents"],
        "action": action,
        "message": message,
        "command": f"coord {strategy_info['strategy']} \"<task description>\""
    }

    # Log the suggestion
    log_orchestration(result)

    return result


def spawn_strategy(pattern: str = None, task: str = "") -> Dict:
    """Generate spawn command for the optimal strategy."""
    if pattern is None:
        pattern, _ = get_current_pattern()

    strategy_info = PATTERN_TO_STRATEGY.get(pattern, {
        "strategy": "implement",
        "description": "Default parallel implementation"
    })

    return {
        "pattern": pattern,
        "strategy": strategy_info["strategy"],
        "command": f"coord {strategy_info['strategy']} \"{task}\"",
        "description": strategy_info["description"]
    }


def get_context_packs_for_pattern(pattern: str) -> list:
    """Get relevant context packs for a pattern."""
    # Pattern to context pack mapping
    PATTERN_PACKS = {
        "debugging": ["error-patterns", "debugging-guides"],
        "research": ["arxiv-papers", "learnings"],
        "architecture": ["system-design", "patterns"],
        "refactoring": ["code-patterns", "best-practices"],
        "feature": ["api-docs", "component-patterns"],
        "testing": ["test-patterns", "coverage-guides"],
        "performance": ["profiling", "optimization"]
    }

    return PATTERN_PACKS.get(pattern, ["general"])


def log_orchestration(decision: Dict):
    """Log orchestration decision."""
    ORCHESTRATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ORCHESTRATE_LOG, 'a') as f:
        f.write(json.dumps(decision) + '\n')


def get_stats(days: int = 7) -> Dict:
    """Get orchestration statistics."""
    if not ORCHESTRATE_LOG.exists():
        return {"total": 0}

    from datetime import timedelta
    cutoff = datetime.now() - timedelta(days=days)

    decisions = []
    for line in ORCHESTRATE_LOG.read_text().strip().split('\n'):
        if line:
            try:
                d = json.loads(line)
                if datetime.fromisoformat(d['timestamp']) > cutoff:
                    decisions.append(d)
            except:
                pass

    if not decisions:
        return {"total": 0}

    patterns = {}
    strategies = {}
    actions = {"auto_spawn": 0, "suggest": 0, "ask": 0}

    for d in decisions:
        p = d.get('detected_pattern', 'unknown')
        s = d.get('suggested_strategy', 'unknown')
        a = d.get('action', 'unknown')

        patterns[p] = patterns.get(p, 0) + 1
        strategies[s] = strategies.get(s, 0) + 1
        if a in actions:
            actions[a] += 1

    return {
        "total": len(decisions),
        "patterns_detected": patterns,
        "strategies_suggested": strategies,
        "action_breakdown": actions,
        "auto_spawn_rate": round(actions['auto_spawn'] / len(decisions), 2) if decisions else 0
    }


def print_suggestion(result: Dict):
    """Print formatted suggestion."""
    print(f"\n{'='*50}")
    print(f"  Pattern Orchestrator")
    print(f"{'='*50}")
    print(f"  Detected Pattern: {result['detected_pattern']}")
    print(f"  Confidence: {result['confidence']:.0%}")
    print(f"")
    print(f"  Suggested Strategy: {result['suggested_strategy']}")
    print(f"  Description: {result['strategy_description']}")
    print(f"  Agents: {result['agents']}")
    print(f"")
    print(f"  Action: {result['message']}")
    print(f"")
    print(f"  Command:")
    print(f"    {result['command']}")
    print(f"{'='*50}\n")


# CLI Interface
if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print("Pattern Orchestrator")
        print("")
        print("Commands:")
        print("  suggest              - Suggest strategy for current pattern")
        print("  spawn [task]         - Get spawn command for current pattern")
        print("  pattern              - Show current detected pattern")
        print("  stats [days]         - Get orchestration statistics")
        print("  packs                - Show context packs for current pattern")
        sys.exit(0)

    command = args[0]

    if command == 'suggest':
        result = suggest_strategy()
        print_suggestion(result)

    elif command == 'spawn':
        task = ' '.join(args[1:]) if len(args) > 1 else "your task here"
        result = spawn_strategy(task=task)
        print(json.dumps(result, indent=2))

    elif command == 'pattern':
        pattern, confidence = get_current_pattern()
        print(json.dumps({
            "pattern": pattern,
            "confidence": confidence
        }, indent=2))

    elif command == 'stats':
        days = int(args[1]) if len(args) > 1 else 7
        print(json.dumps(get_stats(days), indent=2))

    elif command == 'packs':
        pattern, _ = get_current_pattern()
        packs = get_context_packs_for_pattern(pattern)
        print(json.dumps({
            "pattern": pattern,
            "context_packs": packs
        }, indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
