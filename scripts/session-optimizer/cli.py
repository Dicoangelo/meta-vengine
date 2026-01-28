#!/usr/bin/env python3
"""
Session Optimizer CLI - Main entry point

Provides a unified CLI for:
- Window status and prediction
- Budget management
- Capacity tracking
- Task queue
- Feedback loop
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from window_tracker import WindowTracker
from budget_manager import BudgetManager
from capacity_predictor import CapacityPredictor
from task_queue import TaskQueueManager
from feedback_loop import FeedbackLoop


def get_session_engine_status():
    """Get status from session-engine.js."""
    try:
        result = subprocess.run(
            ["node", str(Path.home() / ".claude/kernel/session-engine.js"), "compact"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return None


def cmd_status(args):
    """Show comprehensive session status."""
    window = WindowTracker()
    budget = BudgetManager()
    capacity = CapacityPredictor()

    # Get window position
    pos = window.get_current_window_position()

    # Get budget status
    budget_status = budget.get_budget_status()

    # Get capacity
    cap = capacity.predict_remaining()

    # Build display
    filled = int(pos["positionPercent"] / 10)
    progress = "█" * filled + "░" * (10 - filled)

    hours = pos["remainingMinutes"] // 60
    mins = pos["remainingMinutes"] % 60
    time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

    tier_emoji = {
        "COMFORTABLE": "🟢",
        "MODERATE": "🟡",
        "LOW": "🟠",
        "CRITICAL": "🔴"
    }.get(cap["tier"], "⚪")

    print("")
    print("━━━ Session Window ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Position: {progress} {pos['positionPercent']}% | {time_str} remaining")
    print(f"Capacity: {tier_emoji} {cap['tier']} | Opus: {cap['remaining']['tasks']['opus']} | Sonnet: {cap['remaining']['tasks']['sonnet']} | Haiku: {cap['remaining']['tasks']['haiku']}")
    print(f"Budget:   {budget_status['utilizationPercent']}% utilized | Recommended: {budget_status['recommendedModel']}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Show next window prediction
    next_window = window.predict_next_window()
    if next_window:
        next_time = datetime.fromisoformat(next_window.replace("Z", "+00:00"))
        print(f"Prediction: Optimal next window {next_time.strftime('%H:%M')}")


def cmd_inject_status(args):
    """Inject status into session (for hooks)."""
    # Get compact status from session-engine.js
    status = get_session_engine_status()
    if status:
        print(status)


def cmd_window(args):
    """Window-related commands."""
    tracker = WindowTracker()

    if args.window_cmd == "status":
        pos = tracker.get_current_window_position()
        print(json.dumps(pos, indent=2))

    elif args.window_cmd == "predict":
        next_window = tracker.predict_next_window()
        if next_window:
            print(f"Next optimal window: {next_window}")
        else:
            print("Unable to predict (insufficient data)")

    elif args.window_cmd == "history":
        windows = tracker.detect_windows(days=args.days)
        print(f"Last {args.days} days: {len(windows)} windows")
        for w in windows[-10:]:
            start = datetime.fromtimestamp(w["start"] / 1000)
            duration = w.get("duration_ms", 0) / 60000
            print(f"  {start.strftime('%Y-%m-%d %H:%M')}: {duration:.0f}m")

    elif args.window_cmd == "analyze":
        windows = tracker.detect_windows(days=args.days)
        patterns = tracker.analyze_reset_patterns(windows)
        print("Reset patterns:")
        for reset in patterns.get("resetTimes", []):
            print(f"  {reset['hour']:02d}:00 - {reset['reliability']*100:.0f}% reliability ({reset['count']} occurrences)")


def cmd_budget(args):
    """Budget-related commands."""
    manager = BudgetManager()

    if args.budget_cmd == "status":
        status = manager.get_budget_status()
        print(f"Budget Status:")
        print(f"  Utilization: {status['utilizationPercent']}%")
        print(f"  Recommended: {status['recommendedModel']}")
        print(f"  Remaining:")
        for model, count in status['remainingTasks'].items():
            print(f"    {model}: {count} tasks")

    elif args.budget_cmd == "reserve":
        if manager.reserve_opus(args.count):
            print(f"Reserved {args.count} Opus tasks")
        else:
            print("Insufficient budget")

    elif args.budget_cmd == "simulate":
        # Parse tasks from args
        tasks = []
        if args.tasks:
            for t in args.tasks:
                model, count = t.split(":")
                tasks.append({"model": model, "count": int(count)})
        result = manager.simulate_usage(tasks)
        print(json.dumps(result, indent=2))

    elif args.budget_cmd == "api-value":
        value = manager.calculate_api_equivalent()
        print(f"API Equivalent: ${value['apiEquivalent']}")
        print(f"Savings: ${value['savings']}")
        print(f"Multiplier: {value['multiplier']}x ROI")


def cmd_queue(args):
    """Task queue commands."""
    manager = TaskQueueManager()

    if args.queue_cmd == "add":
        task = manager.add_task(args.description, args.complexity)
        print(f"Added: {task['id']} (priority: {task['priority']})")

    elif args.queue_cmd == "list":
        tasks = manager.list_tasks(args.status)
        for task in tasks:
            print(f"  [{task['status'][:1].upper()}] {task['id']}: {task['description'][:40]}...")

    elif args.queue_cmd == "next":
        task = manager.get_next_task()
        if task:
            print(f"Next: {task['id']} - {task['description']}")
        else:
            print("No tasks available")

    elif args.queue_cmd == "complete":
        if manager.complete_task(args.task_id):
            print("Completed")
        else:
            print("Task not found")

    elif args.queue_cmd == "batch":
        batches = manager.suggest_batches()
        for batch in batches:
            print(f"\n{batch['name']} ({batch['model']}):")
            print(f"  {batch['recommendation']}")
            for task in batch['tasks']:
                print(f"    - {task['description'][:40]}...")


def cmd_optimize(args):
    """Run optimization."""
    loop = FeedbackLoop()

    if args.dry_run:
        print("DRY RUN - No changes will be made")
        print("")

    analysis = loop.analyze_sessions(days=args.days)
    print(f"Analyzed {analysis['sessionCount']} sessions")

    proposals = loop.generate_proposals(analysis)
    print(f"\nProposals: {len(proposals)}")

    for p in proposals:
        print(f"\n  {p['id']}:")
        print(f"    Pattern: {p['pattern']}")
        print(f"    Confidence: {p['confidence']}")
        print(f"    Change: {p['currentValue']} -> {p['suggestedValue']}")

        if args.apply and p['confidence'] >= 0.7:
            if args.dry_run:
                print("    [WOULD APPLY]")
            else:
                loop.apply_proposal(p)
                print("    [APPLIED]")


def cmd_dashboard(args):
    """Full dashboard view."""
    # Call session-engine.js dashboard
    try:
        result = subprocess.run(
            ["node", str(Path.home() / ".claude/kernel/session-engine.js"), "dashboard"],
            capture_output=False,
            timeout=10
        )
    except Exception as e:
        print(f"Error: {e}")
        cmd_status(args)


def main():
    parser = argparse.ArgumentParser(
        description="Session Optimizer - Sovereign session optimization"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show session status")

    # Inject status (for hooks)
    inject_parser = subparsers.add_parser("inject-status", help="Inject status for hooks")

    # Window commands
    window_parser = subparsers.add_parser("window", help="Window operations")
    window_sub = window_parser.add_subparsers(dest="window_cmd")
    window_sub.add_parser("status", help="Current window status")
    window_sub.add_parser("predict", help="Predict next window")
    hist_parser = window_sub.add_parser("history", help="Window history")
    hist_parser.add_argument("--days", type=int, default=7, help="Days to analyze")
    analyze_parser = window_sub.add_parser("analyze", help="Analyze patterns")
    analyze_parser.add_argument("--days", type=int, default=30, help="Days to analyze")

    # Budget commands
    budget_parser = subparsers.add_parser("budget", help="Budget operations")
    budget_sub = budget_parser.add_subparsers(dest="budget_cmd")
    budget_sub.add_parser("status", help="Budget status")
    reserve_parser = budget_sub.add_parser("reserve", help="Reserve Opus tasks")
    reserve_parser.add_argument("count", type=int, help="Number of tasks")
    sim_parser = budget_sub.add_parser("simulate", help="Simulate usage")
    sim_parser.add_argument("--tasks", nargs="*", help="Tasks as model:count")
    budget_sub.add_parser("api-value", help="Calculate API equivalent")

    # Queue commands
    queue_parser = subparsers.add_parser("queue", help="Task queue operations")
    queue_sub = queue_parser.add_subparsers(dest="queue_cmd")
    add_parser = queue_sub.add_parser("add", help="Add task")
    add_parser.add_argument("description", help="Task description")
    add_parser.add_argument("--complexity", type=float, default=0.5)
    list_parser = queue_sub.add_parser("list", help="List tasks")
    list_parser.add_argument("--status", help="Filter by status")
    queue_sub.add_parser("next", help="Get next task")
    complete_parser = queue_sub.add_parser("complete", help="Complete task")
    complete_parser.add_argument("task_id", help="Task ID")
    queue_sub.add_parser("batch", help="Batch suggestions")

    # Optimize command
    opt_parser = subparsers.add_parser("optimize", help="Run optimization")
    opt_parser.add_argument("--days", type=int, default=30, help="Days to analyze")
    opt_parser.add_argument("--apply", action="store_true", help="Apply proposals")
    opt_parser.add_argument("--dry-run", action="store_true", help="Preview only")

    # Dashboard command
    dash_parser = subparsers.add_parser("dashboard", help="Full dashboard")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args)
    elif args.command == "inject-status":
        cmd_inject_status(args)
    elif args.command == "window":
        cmd_window(args)
    elif args.command == "budget":
        cmd_budget(args)
    elif args.command == "queue":
        cmd_queue(args)
    elif args.command == "optimize":
        cmd_optimize(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
