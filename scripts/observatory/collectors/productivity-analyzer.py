#!/usr/bin/env python3
"""
Claude Observatory - Productivity Metrics Analyzer
Tracks read/write ratios, files modified, LOC changed, and coding velocity
"""

import json
import sys
import glob
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
from collections import Counter, defaultdict

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

HOME = Path.home()
DATA_FILE = HOME / ".claude/data/productivity.jsonl"
SESSIONS_DIR = HOME / ".claude/projects"
ACTIVITY_LOG = HOME / ".claude/activity.log"

# ═══════════════════════════════════════════════════════════════════════════
# ACTIVITY LOG PARSING
# ═══════════════════════════════════════════════════════════════════════════

def parse_activity_log(days: int = 7) -> Dict:
    """Parse activity.log to extract read/write metrics"""
    if not ACTIVITY_LOG.exists():
        return {}

    cutoff = datetime.now() - timedelta(days=days)

    reads = 0
    writes = 0
    edits = 0
    bash_calls = 0

    files_read = set()
    files_written = set()

    with open(ACTIVITY_LOG) as f:
        for line in f:
            line = line.strip()

            # Parse timestamp if present
            if line.startswith('SESSION') or line.startswith('🚀'):
                continue

            # Count tool calls
            if ' READ ' in line or line.endswith('READ'):
                reads += 1
            elif ' WRITE ' in line or line.endswith('WRITE'):
                writes += 1
                # Try to extract filename
                parts = line.split()
                if len(parts) > 2:
                    files_written.add(parts[2])
            elif ' EDIT ' in line or line.endswith('EDIT'):
                edits += 1
                parts = line.split()
                if len(parts) > 2:
                    files_written.add(parts[2])
            elif ' BASH' in line or line.endswith('BASH'):
                bash_calls += 1

    total_modifications = writes + edits
    read_write_ratio = reads / total_modifications if total_modifications > 0 else 0
    productivity_score = total_modifications / reads if reads > 0 else 0

    return {
        "reads": reads,
        "writes": writes,
        "edits": edits,
        "bash_calls": bash_calls,
        "total_modifications": total_modifications,
        "files_written_unique": len(files_written),
        "read_write_ratio": round(read_write_ratio, 2),
        "productivity_score": round(productivity_score, 4)
    }

# ═══════════════════════════════════════════════════════════════════════════
# SESSION-LEVEL PRODUCTIVITY
# ═══════════════════════════════════════════════════════════════════════════

def analyze_session_productivity(session_file: Path) -> Dict:
    """Analyze productivity metrics for a single session"""
    try:
        with open(session_file) as f:
            lines = [json.loads(line) for line in f if line.strip()]
    except:
        return {}

    # Count tool uses
    tool_calls = defaultdict(int)
    files_read = set()
    files_written = set()

    for line in lines:
        if line.get('type') == 'tool_result':
            tool_name = line.get('name', 'unknown')
            tool_calls[tool_name] += 1

            # Track files
            if tool_name == 'Read':
                content = line.get('content', {})
                if isinstance(content, dict):
                    file_path = content.get('file_path', '')
                    if file_path:
                        files_read.add(file_path)

            elif tool_name in ['Write', 'Edit']:
                content = line.get('content', {})
                if isinstance(content, dict):
                    file_path = content.get('file_path', '')
                    if file_path:
                        files_written.add(file_path)

    total_reads = tool_calls.get('Read', 0)
    total_writes = tool_calls.get('Write', 0) + tool_calls.get('Edit', 0)

    return {
        "session_id": session_file.stem,
        "tool_calls": dict(tool_calls),
        "files_read": len(files_read),
        "files_written": len(files_written),
        "total_reads": total_reads,
        "total_writes": total_writes,
        "read_write_ratio": round(total_reads / total_writes, 2) if total_writes > 0 else 0,
        "productivity_score": round(total_writes / total_reads, 4) if total_reads > 0 else 0
    }

# ═══════════════════════════════════════════════════════════════════════════
# GIT-BASED LOC TRACKING
# ═══════════════════════════════════════════════════════════════════════════

def get_loc_changes(since_hours: int = 24) -> Dict:
    """Get lines of code changed from git"""
    import subprocess

    try:
        # Get git stats for recent commits
        since_time = f"{since_hours} hours ago"
        result = subprocess.run(
            ['git', 'log', f'--since={since_time}', '--numstat', '--pretty=format:'],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )

        if result.returncode != 0:
            return {}

        # Parse numstat output
        lines_added = 0
        lines_removed = 0
        files_changed = set()

        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 3:
                added, removed, filename = parts[0], parts[1], parts[2]
                if added != '-' and removed != '-':
                    lines_added += int(added)
                    lines_removed += int(removed)
                    files_changed.add(filename)

        return {
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "net_loc": lines_added - lines_removed,
            "files_changed": len(files_changed),
            "productivity_velocity": round((lines_added + lines_removed) / since_hours, 2)
        }
    except Exception as e:
        return {"error": str(e)}

# ═══════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════

def log_productivity_snapshot():
    """Log current productivity metrics"""
    activity_metrics = parse_activity_log(days=1)
    loc_metrics = get_loc_changes(since_hours=24)

    entry = {
        "ts": int(datetime.now().timestamp()),
        "event": "daily_snapshot",
        **activity_metrics,
        **loc_metrics
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')

    print("✅ Productivity snapshot logged")

# ═══════════════════════════════════════════════════════════════════════════
# REPORTING
# ═══════════════════════════════════════════════════════════════════════════

def generate_productivity_report(days: int = 7):
    """Generate comprehensive productivity report"""
    activity_metrics = parse_activity_log(days=days)
    loc_metrics = get_loc_changes(since_hours=days * 24)

    print("═══════════════════════════════════════════════════════════════")
    print(f"  📈 PRODUCTIVITY REPORT - Last {days} Days")
    print("═══════════════════════════════════════════════════════════════")
    print()

    # Activity metrics
    print("  Tool Usage:")
    print(f"    Reads:         {activity_metrics.get('reads', 0):5d}")
    print(f"    Writes:        {activity_metrics.get('writes', 0):5d}")
    print(f"    Edits:         {activity_metrics.get('edits', 0):5d}")
    print(f"    Bash calls:    {activity_metrics.get('bash_calls', 0):5d}")
    print()

    # Productivity metrics
    total_mods = activity_metrics.get('total_modifications', 0)
    print("  Productivity:")
    print(f"    Total Modifications:  {total_mods}")
    print(f"    Unique Files Changed: {activity_metrics.get('files_written_unique', 0)}")
    print(f"    Read/Write Ratio:     {activity_metrics.get('read_write_ratio', 0):.2f}:1")
    print(f"    Productivity Score:   {activity_metrics.get('productivity_score', 0):.4f}")
    print()

    # Code metrics
    if loc_metrics and 'error' not in loc_metrics:
        print("  Code Changes (Git):")
        print(f"    Lines Added:     {loc_metrics.get('lines_added', 0):6d}")
        print(f"    Lines Removed:   {loc_metrics.get('lines_removed', 0):6d}")
        print(f"    Net LOC:         {loc_metrics.get('net_loc', 0):+6d}")
        print(f"    Files Changed:   {loc_metrics.get('files_changed', 0):6d}")
        print(f"    Velocity (LOC/h):{loc_metrics.get('productivity_velocity', 0):6.1f}")
        print()

    # Productivity assessment
    prod_score = activity_metrics.get('productivity_score', 0)
    if prod_score < 0.01:
        status = "🔴 Read-heavy (exploration mode)"
    elif prod_score < 0.05:
        status = "🟡 Learning/researching"
    elif prod_score < 0.1:
        status = "🟢 Balanced productivity"
    else:
        status = "✨ High productivity mode"

    print(f"  Status: {status}")
    print()

    # Recommendations
    print("  Recommendations:")
    if prod_score < 0.01:
        print("    • You're reading 100x more than writing")
        print("    • Consider: What can you build with this knowledge?")
    elif total_mods < 5:
        print("    • Low modification count detected")
        print("    • Try using Write/Edit tools to apply learnings")
    else:
        print("    • Good balance of exploration and creation")
        print("    • Keep up the productive flow!")
    print()

# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  productivity-analyzer.py log              - Log daily snapshot")
        print("  productivity-analyzer.py report [days]    - Generate report")
        print("  productivity-analyzer.py session <file>   - Analyze session")
        return

    command = sys.argv[1]

    if command == "log":
        log_productivity_snapshot()
    elif command == "report":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        generate_productivity_report(days)
    elif command == "session" and len(sys.argv) > 2:
        result = analyze_session_productivity(Path(sys.argv[2]))
        print(json.dumps(result, indent=2))
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
