#!/usr/bin/env python3
"""
Daily Memory Log Generator

Aggregates session data from JSONL sources into daily markdown summaries.

Usage:
    python3 daily-memory-log.py              # Generate today's log
    python3 daily-memory-log.py --date 2026-01-20   # Specific date
    python3 daily-memory-log.py --backfill 7        # Last N days
    python3 daily-memory-log.py --all               # All available data
"""

import json
import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import re

# Paths
DATA_DIR = Path.home() / ".claude" / "data"
OUTPUT_DIR = Path.home() / ".claude" / "memory" / "daily"

# JSONL sources
SOURCES = {
    "session_outcomes": DATA_DIR / "session-outcomes.jsonl",
    "cost_tracking": DATA_DIR / "cost-tracking.jsonl",
    "errors": DATA_DIR / "errors.jsonl",
    "git_activity": DATA_DIR / "git-activity.jsonl",
    "session_events": DATA_DIR / "session-events.jsonl",
    "productivity": DATA_DIR / "productivity.jsonl",
    "tool_usage": DATA_DIR / "tool-usage.jsonl",
}

# User notes marker
NOTES_MARKER = "## Notes"
NOTES_START = "<!-- USER_NOTES_START -->"
NOTES_END = "<!-- USER_NOTES_END -->"


def read_jsonl(filepath: Path) -> list[dict]:
    """Read JSONL file and return list of records."""
    records = []
    if not filepath.exists():
        return records

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def get_date_from_ts(ts: int | float) -> str:
    """Convert Unix timestamp to date string YYYY-MM-DD."""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def filter_by_date(records: list[dict], target_date: str) -> list[dict]:
    """Filter records to only include those from target_date."""
    filtered = []
    for r in records:
        # Try ts field first
        if "ts" in r:
            if get_date_from_ts(r["ts"]) == target_date:
                filtered.append(r)
        # Try date field
        elif "date" in r:
            if r["date"] == target_date:
                filtered.append(r)
        # Try timestamp field
        elif "timestamp" in r:
            try:
                dt = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
                if dt.strftime("%Y-%m-%d") == target_date:
                    filtered.append(r)
            except (ValueError, AttributeError):
                pass
    return filtered


def extract_user_notes(existing_content: str) -> str:
    """Extract user notes from existing log to preserve them."""
    if NOTES_START in existing_content and NOTES_END in existing_content:
        start = existing_content.index(NOTES_START) + len(NOTES_START)
        end = existing_content.index(NOTES_END)
        return existing_content[start:end].strip()

    # Legacy format: extract content after ## Notes
    if NOTES_MARKER in existing_content:
        idx = existing_content.index(NOTES_MARKER)
        notes_section = existing_content[idx + len(NOTES_MARKER):].strip()
        # Remove default placeholder if present
        if notes_section == "_User annotations_":
            return ""
        return notes_section

    return ""


def generate_daily_log(target_date: str) -> str:
    """Generate markdown log for a specific date."""

    # Load all data
    session_outcomes = filter_by_date(read_jsonl(SOURCES["session_outcomes"]), target_date)
    cost_data = filter_by_date(read_jsonl(SOURCES["cost_tracking"]), target_date)
    errors = filter_by_date(read_jsonl(SOURCES["errors"]), target_date)
    git_activity = filter_by_date(read_jsonl(SOURCES["git_activity"]), target_date)
    session_events = filter_by_date(read_jsonl(SOURCES["session_events"]), target_date)
    productivity = filter_by_date(read_jsonl(SOURCES["productivity"]), target_date)
    tool_usage = filter_by_date(read_jsonl(SOURCES["tool_usage"]), target_date)

    # Analyze sessions
    session_starts = [e for e in session_events if e.get("event") == "session_start"]
    session_ends = [e for e in session_events if e.get("event") == "session_end"]

    successful = len([s for s in session_outcomes if s.get("outcome") == "success"])
    partial = len([s for s in session_outcomes if s.get("outcome") == "partial"])
    abandoned = len([s for s in session_outcomes if s.get("outcome") == "abandoned"])
    total_sessions = max(len(session_starts), len(session_outcomes), 1)

    # Calculate quality
    qualities = [s.get("quality", 0) for s in session_outcomes if s.get("quality")]
    avg_quality = sum(qualities) / len(qualities) if qualities else 0

    # Calculate working hours from session events
    hours_set = set()
    for e in session_events:
        if "ts" in e:
            hour = datetime.fromtimestamp(e["ts"]).strftime("%H:00")
            hours_set.add(hour)

    if hours_set:
        sorted_hours = sorted(hours_set)
        working_hours = f"{sorted_hours[0]} - {sorted_hours[-1]}"
    else:
        working_hours = "N/A"

    # Aggregate costs by model
    model_costs = defaultdict(lambda: {"cost": 0, "tokens_in": 0, "tokens_out": 0, "cache_reads": 0})
    for c in cost_data:
        model = c.get("model", "unknown")
        # Simplify model name
        if "opus" in model.lower():
            model_key = "Opus"
        elif "sonnet" in model.lower():
            model_key = "Sonnet"
        elif "haiku" in model.lower():
            model_key = "Haiku"
        else:
            model_key = model

        model_costs[model_key]["cost"] += c.get("cost_usd", 0)
        tokens = c.get("tokens", {})
        model_costs[model_key]["tokens_in"] += tokens.get("input", 0)
        model_costs[model_key]["tokens_out"] += tokens.get("output", 0)
        model_costs[model_key]["cache_reads"] += tokens.get("cache_read", 0)

    # Calculate cache efficiency
    total_input = sum(m["tokens_in"] for m in model_costs.values())
    total_cache = sum(m["cache_reads"] for m in model_costs.values())
    overall_cache_pct = (total_cache / (total_input + total_cache) * 100) if (total_input + total_cache) > 0 else 0

    # Aggregate errors by category
    error_cats = defaultdict(int)
    for e in errors:
        cat = e.get("category", "unknown")
        error_cats[cat] += 1

    # Aggregate git activity by repo
    repo_commits = defaultdict(int)
    for g in git_activity:
        repo = g.get("repo", "unknown")
        repo_commits[repo] += 1

    # Tool usage stats
    tool_counts = defaultdict(int)
    for t in tool_usage:
        tool = t.get("tool", "unknown")
        tool_counts[tool] += 1

    # Get files modified from session outcomes
    all_files = set()
    for s in session_outcomes:
        for f in s.get("files_modified", []):
            all_files.add(f)

    # Build markdown
    lines = [
        f"# Daily Memory Log: {target_date}",
        "",
        "## Session Summary",
    ]

    outcome_parts = []
    if successful:
        outcome_parts.append(f"{successful} successful")
    if partial:
        outcome_parts.append(f"{partial} partial")
    if abandoned:
        outcome_parts.append(f"{abandoned} abandoned")
    outcome_str = ", ".join(outcome_parts) if outcome_parts else "none tracked"

    lines.extend([
        f"- **Sessions:** {total_sessions} ({outcome_str})",
        f"- **Working Hours:** {working_hours}",
        f"- **Avg Quality:** {avg_quality:.1f}/5" if avg_quality else "- **Avg Quality:** N/A",
        "",
    ])

    # Cost section
    if model_costs:
        lines.extend([
            "## Cost & Efficiency",
            "",
            "| Model | Cost | Cache % |",
            "|-------|------|---------|",
        ])

        for model, data in sorted(model_costs.items()):
            input_total = data["tokens_in"] + data["cache_reads"]
            cache_pct = (data["cache_reads"] / input_total * 100) if input_total > 0 else 0
            lines.append(f"| {model} | ${data['cost']:.2f} | {cache_pct:.0f}% |")

        total_cost = sum(m["cost"] for m in model_costs.values())
        lines.extend([
            "",
            f"**Total:** ${total_cost:.2f} | **Overall Cache:** {overall_cache_pct:.0f}%",
            "",
        ])

    # Errors section
    if error_cats:
        lines.extend([
            "## Errors",
            "",
        ])
        error_total = sum(error_cats.values())
        error_breakdown = ", ".join(f"{cat}: {cnt}" for cat, cnt in sorted(error_cats.items()))
        lines.extend([
            f"- **Total:** {error_total} ({error_breakdown})",
            "",
        ])

    # Git activity
    if repo_commits:
        lines.extend([
            "## Git Activity",
            "",
        ])
        commit_total = sum(repo_commits.values())
        repo_breakdown = ", ".join(f"{repo} ({cnt})" for repo, cnt in sorted(repo_commits.items(), key=lambda x: -x[1]))
        lines.extend([
            f"- **Commits:** {commit_total}",
            f"- **Repos:** {repo_breakdown}",
            "",
        ])

    # Tool usage
    if tool_counts:
        lines.extend([
            "## Tool Usage",
            "",
            "| Tool | Count |",
            "|------|-------|",
        ])
        for tool, count in sorted(tool_counts.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"| {tool} | {count} |")
        lines.append("")

    # Files modified
    if all_files:
        lines.extend([
            "## Files Modified",
            "",
            f"**Total:** {len(all_files)} files",
            "",
        ])
        # Group by extension
        ext_counts = defaultdict(int)
        for f in all_files:
            ext = Path(f).suffix or "(no ext)"
            ext_counts[ext] += 1

        ext_breakdown = ", ".join(f"{ext}: {cnt}" for ext, cnt in sorted(ext_counts.items(), key=lambda x: -x[1])[:5])
        lines.append(f"By type: {ext_breakdown}")
        lines.append("")

    # Session details (collapsible)
    if session_outcomes:
        lines.extend([
            "<details>",
            "<summary>Session Details</summary>",
            "",
        ])
        for s in session_outcomes:
            title = s.get("title") or "Untitled"
            title = title[:60]
            outcome = s.get("outcome", "unknown")
            quality = s.get("quality", "?")
            lines.append(f"- **{title}...** → {outcome} (Q: {quality})")
        lines.extend([
            "",
            "</details>",
            "",
        ])

    # Notes section (preserved across regenerations)
    lines.extend([
        NOTES_MARKER,
        "",
        NOTES_START,
        "",
        NOTES_END,
        "",
    ])

    return "\n".join(lines)


def write_log(target_date: str, preserve_notes: bool = True) -> Path:
    """Write log file, preserving user notes if they exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{target_date}.md"

    # Check for existing notes
    existing_notes = ""
    if preserve_notes and output_path.exists():
        existing_notes = extract_user_notes(output_path.read_text())

    # Generate new content
    content = generate_daily_log(target_date)

    # Re-inject user notes
    if existing_notes:
        content = content.replace(
            f"{NOTES_START}\n\n{NOTES_END}",
            f"{NOTES_START}\n{existing_notes}\n{NOTES_END}"
        )

    output_path.write_text(content)
    return output_path


def get_available_dates() -> set[str]:
    """Get all dates that have data in any JSONL file."""
    dates = set()

    for source_path in SOURCES.values():
        if not source_path.exists():
            continue

        for record in read_jsonl(source_path):
            if "ts" in record:
                dates.add(get_date_from_ts(record["ts"]))
            elif "date" in record:
                dates.add(record["date"])
            elif "timestamp" in record:
                try:
                    dt = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
                    dates.add(dt.strftime("%Y-%m-%d"))
                except (ValueError, AttributeError):
                    pass

    return dates


def main():
    parser = argparse.ArgumentParser(description="Generate daily memory logs")
    parser.add_argument("--date", help="Specific date (YYYY-MM-DD)")
    parser.add_argument("--backfill", type=int, help="Generate logs for last N days")
    parser.add_argument("--all", action="store_true", help="Generate logs for all available data")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress output")

    args = parser.parse_args()

    dates_to_process = []

    if args.all:
        dates_to_process = sorted(get_available_dates())
    elif args.backfill:
        today = datetime.now()
        for i in range(args.backfill):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            dates_to_process.append(date)
        dates_to_process.reverse()
    elif args.date:
        dates_to_process = [args.date]
    else:
        # Default: today
        dates_to_process = [datetime.now().strftime("%Y-%m-%d")]

    for date in dates_to_process:
        output_path = write_log(date)
        if not args.quiet:
            print(f"Generated: {output_path}")

    if not args.quiet and len(dates_to_process) > 1:
        print(f"\nTotal: {len(dates_to_process)} logs generated")


if __name__ == "__main__":
    main()
