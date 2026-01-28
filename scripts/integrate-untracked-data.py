#!/usr/bin/env python3
"""
Integrate untracked data sources into dashboard.
Processes the files identified by audit-data-sources.py.
"""

import json
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
KERNEL_DIR = CLAUDE_DIR / "kernel"
DATA_DIR = CLAUDE_DIR / "data"

print("Integrating untracked data sources...")

# ═══════════════════════════════════════════════════════════════
# 1. ERRORS.JSONL - Error patterns
# ═══════════════════════════════════════════════════════════════

errors_file = DATA_DIR / "errors.jsonl"
error_stats = {"total": 0, "by_type": Counter(), "recent": []}

if errors_file.exists():
    with open(errors_file) as f:
        for line in f:
            try:
                err = json.loads(line)
                error_stats["total"] += 1
                # Handle both 'type' and 'category' fields
                error_type = err.get("type") or err.get("category", "unknown")
                error_stats["by_type"][error_type] += 1

                # Keep last 10
                if len(error_stats["recent"]) < 10:
                    error_stats["recent"].append({
                        "type": error_type,
                        "message": err.get("message") or err.get("line", "")[:100],
                        "ts": err.get("ts", 0),
                        "severity": err.get("severity", "unknown")
                    })
            except:
                pass

    # Write error stats
    (KERNEL_DIR / "error-stats.json").write_text(json.dumps({
        "total_errors": error_stats["total"],
        "by_type": dict(error_stats["by_type"].most_common(10)),
        "recent_errors": error_stats["recent"]
    }, indent=2))
    print(f"  ✅ Processed {error_stats['total']} errors")

# ═══════════════════════════════════════════════════════════════
# 2. TOOL-USAGE.JSONL - Comprehensive tool tracking
# ═══════════════════════════════════════════════════════════════

tool_usage_file = DATA_DIR / "tool-usage.jsonl"
tool_stats = {"total": 0, "by_tool": Counter(), "by_model": Counter()}

if tool_usage_file.exists():
    with open(tool_usage_file) as f:
        for line in f:
            try:
                entry = json.loads(line)
                tool_stats["total"] += 1
                tool_stats["by_tool"][entry.get("tool", "unknown")] += 1
                tool_stats["by_model"][entry.get("model", "unknown")] += 1
            except:
                pass

    (KERNEL_DIR / "tool-usage-stats.json").write_text(json.dumps({
        "total_calls": tool_stats["total"],
        "top_tools": dict(tool_stats["by_tool"].most_common(20)),
        "by_model": dict(tool_stats["by_model"])
    }, indent=2))
    print(f"  ✅ Processed {tool_stats['total']} tool calls")

# ═══════════════════════════════════════════════════════════════
# 3. ACTIVITY-EVENTS.JSONL - Real-time activity
# ═══════════════════════════════════════════════════════════════

activity_file = DATA_DIR / "activity-events.jsonl"
activity_stats = {"total": 0, "by_type": Counter(), "daily": defaultdict(int)}

if activity_file.exists():
    with open(activity_file) as f:
        for line in f:
            try:
                event = json.loads(line)
                activity_stats["total"] += 1
                event_type = event.get("type", "unknown")
                activity_stats["by_type"][event_type] += 1

                # Daily aggregation
                ts = event.get("ts", 0)
                if ts:
                    day = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                    activity_stats["daily"][day] += 1
            except:
                pass

    (KERNEL_DIR / "activity-stats.json").write_text(json.dumps({
        "total_events": activity_stats["total"],
        "by_type": dict(activity_stats["by_type"].most_common(10)),
        "daily_activity": dict(sorted(activity_stats["daily"].items(), reverse=True)[:30])
    }, indent=2))
    print(f"  ✅ Processed {activity_stats['total']} activity events")

# ═══════════════════════════════════════════════════════════════
# 4. RECOVERY-OUTCOMES.JSONL - Error recovery tracking
# ═══════════════════════════════════════════════════════════════

recovery_file = DATA_DIR / "recovery-outcomes.jsonl"
recovery_stats = {"total": 0, "success": 0, "failed": 0, "by_pattern": Counter()}

if recovery_file.exists():
    with open(recovery_file) as f:
        for line in f:
            try:
                outcome = json.loads(line)
                recovery_stats["total"] += 1
                if outcome.get("success"):
                    recovery_stats["success"] += 1
                else:
                    recovery_stats["failed"] += 1
                # Handle both 'pattern' and 'category' fields
                pattern = outcome.get("pattern") or outcome.get("category", "unknown")
                recovery_stats["by_pattern"][pattern] += 1
            except:
                pass

    (KERNEL_DIR / "recovery-stats.json").write_text(json.dumps({
        "total_recoveries": recovery_stats["total"],
        "success_rate": round(recovery_stats["success"] / recovery_stats["total"] * 100, 1) if recovery_stats["total"] > 0 else 0,
        "by_pattern": dict(recovery_stats["by_pattern"].most_common(10))
    }, indent=2))
    print(f"  ✅ Processed {recovery_stats['total']} recovery attempts")

# ═══════════════════════════════════════════════════════════════
# 5. FLOW-HISTORY.JSONL - Cognitive OS flow tracking
# ═══════════════════════════════════════════════════════════════

flow_file = KERNEL_DIR / "cognitive-os" / "flow-history.jsonl"
flow_stats = {"total_measurements": 0, "avg_flow": 0, "peak_hours": Counter()}

if flow_file.exists():
    flow_scores = []
    with open(flow_file) as f:
        for line in f:
            try:
                entry = json.loads(line)
                flow_stats["total_measurements"] += 1
                score = entry.get("flow_score", 0)
                flow_scores.append(score)

                # Track peak hours
                ts = entry.get("ts", 0)
                if ts:
                    hour = datetime.fromtimestamp(ts).hour
                    if score > 0.7:  # High flow
                        flow_stats["peak_hours"][hour] += 1
            except:
                pass

    if flow_scores:
        flow_stats["avg_flow"] = round(sum(flow_scores) / len(flow_scores), 3)

    (KERNEL_DIR / "flow-stats.json").write_text(json.dumps({
        "total_measurements": flow_stats["total_measurements"],
        "average_flow_score": flow_stats["avg_flow"],
        "peak_flow_hours": dict(flow_stats["peak_hours"].most_common(5))
    }, indent=2))
    print(f"  ✅ Processed {flow_stats['total_measurements']} flow measurements")

# ═══════════════════════════════════════════════════════════════
# 6. COMMAND-USAGE.JSONL - Shell command tracking
# ═══════════════════════════════════════════════════════════════

cmd_file = DATA_DIR / "command-usage.jsonl"
cmd_stats = {"total": 0, "by_command": Counter()}

if cmd_file.exists():
    with open(cmd_file) as f:
        for line in f:
            try:
                entry = json.loads(line)
                cmd_stats["total"] += 1
                cmd = entry.get("command", "unknown")
                cmd_stats["by_command"][cmd] += 1
            except:
                pass

    (KERNEL_DIR / "command-stats.json").write_text(json.dumps({
        "total_commands": cmd_stats["total"],
        "top_commands": dict(cmd_stats["by_command"].most_common(15))
    }, indent=2))
    print(f"  ✅ Processed {cmd_stats['total']} commands")

# ═══════════════════════════════════════════════════════════════
# 7. TOOL-SUCCESS.JSONL - Tool success rates
# ═══════════════════════════════════════════════════════════════

success_file = DATA_DIR / "tool-success.jsonl"
success_stats = {"total": 0, "success": 0, "by_tool": defaultdict(lambda: {"total": 0, "success": 0})}

if success_file.exists():
    with open(success_file) as f:
        for line in f:
            try:
                entry = json.loads(line)
                tool = entry.get("tool", "unknown")
                success = entry.get("success", False)

                success_stats["total"] += 1
                success_stats["by_tool"][tool]["total"] += 1

                if success:
                    success_stats["success"] += 1
                    success_stats["by_tool"][tool]["success"] += 1
            except:
                pass

    # Calculate success rates
    tool_success_rates = {}
    for tool, data in success_stats["by_tool"].items():
        rate = round(data["success"] / data["total"] * 100, 1) if data["total"] > 0 else 0
        tool_success_rates[tool] = {"rate": rate, "total": data["total"]}

    (KERNEL_DIR / "tool-success-stats.json").write_text(json.dumps({
        "overall_success_rate": round(success_stats["success"] / success_stats["total"] * 100, 1) if success_stats["total"] > 0 else 0,
        "by_tool": dict(sorted(tool_success_rates.items(), key=lambda x: -x[1]["total"])[:20])
    }, indent=2))
    print(f"  ✅ Processed {success_stats['total']} tool success records")

print("\n✅ All untracked data sources integrated!")
print("New files created in ~/.claude/kernel/:")
print("  - error-stats.json")
print("  - tool-usage-stats.json")
print("  - activity-stats.json")
print("  - recovery-stats.json")
print("  - flow-stats.json")
print("  - command-stats.json")
print("  - tool-success-stats.json")
