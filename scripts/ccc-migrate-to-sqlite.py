#!/usr/bin/env python3
"""
Dashboard Migration: Replace JSONL with SQLite queries
Purpose: Patch ccc-generator.sh to use SQLite instead of JSONL files
Created: 2026-01-28
"""

import re
from pathlib import Path

CCC_SCRIPT = Path.home() / '.claude/scripts/ccc-generator.sh'
BACKUP_SCRIPT = Path.home() / '.claude/scripts/ccc-generator.sh.pre-sqlite-backup'

# New Python code for tool usage (using SQLite)
# Using single-line SQL to avoid heredoc escaping issues
TOOL_USAGE_SQLITE = r"""python3 << 'TOOLEOF' > "$TOOL_USAGE_TMP"
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict

home = Path.home()
db_path = home / ".claude/data/claude.db"

result = {
    "total": 0,
    "byTool": {},
    "successRates": {},
    "daily": [],
    "topTools": []
}

# Connect to SQLite
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

# Get total tool calls
cursor = conn.execute("SELECT COUNT(*) as count FROM tool_events")
result["total"] = cursor.fetchone()["count"]

# Count by tool (top 20)
cursor = conn.execute("SELECT tool_name, COUNT(*) as count FROM tool_events GROUP BY tool_name ORDER BY count DESC LIMIT 20")
result["byTool"] = {row["tool_name"]: row["count"] for row in cursor.fetchall()}

# Top tools (top 10 for display)
cursor = conn.execute("SELECT tool_name, COUNT(*) as count FROM tool_events GROUP BY tool_name ORDER BY count DESC LIMIT 10")
result["topTools"] = [{"tool": row["tool_name"], "count": row["count"]} for row in cursor.fetchall()]

# Success rates by tool
cursor = conn.execute("SELECT tool_name, COUNT(*) as total, SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count, SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failure_count FROM tool_events GROUP BY tool_name")
success_data = {}
for row in cursor.fetchall():
    tool = row["tool_name"]
    total = row["total"]
    success_count = row["success_count"]
    success_rate = round(success_count / total * 100, 1) if total > 0 else 100
    result["successRates"][tool] = success_rate

# Total failures
cursor = conn.execute("SELECT COUNT(*) as count FROM tool_events WHERE success = 0")
result["totalFailures"] = cursor.fetchone()["count"]

# Daily usage (last 7 days)
now = datetime.now()
week_ago = int((now - timedelta(days=7)).timestamp())
cursor = conn.execute("SELECT date(timestamp, 'unixepoch') as day, COUNT(*) as count FROM tool_events WHERE timestamp > ? GROUP BY day ORDER BY day", (week_ago,))
daily_data = {row["day"]: row["count"] for row in cursor.fetchall()}

result["daily"] = [
    {"date": (now - timedelta(days=i)).strftime("%Y-%m-%d"),
     "count": daily_data.get((now - timedelta(days=i)).strftime("%Y-%m-%d"), 0)}
    for i in range(6, -1, -1)
]

conn.close()
print(json.dumps(result))
TOOLEOF
"""

# New Python code for daily activity (using SQLite)
DAILY_ACTIVITY_SQLITE = r"""python3 << 'DAILYEOF' > "$DAILY_ACTIVITY_TMP"
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

home = Path.home()
db_path = home / ".claude/data/claude.db"

result = {
    "allTime": {"total": 0, "writes": 0, "edits": 0, "bash": 0, "reads": 0},
    "daily": [],  # Last 14 days
    "byTool": {}
}

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

# All-time stats
cursor = conn.execute("SELECT COUNT(*) as total, SUM(CASE WHEN tool_name = 'Write' THEN 1 ELSE 0 END) as writes, SUM(CASE WHEN tool_name = 'Edit' THEN 1 ELSE 0 END) as edits, SUM(CASE WHEN tool_name = 'Bash' THEN 1 ELSE 0 END) as bash, SUM(CASE WHEN tool_name = 'Read' THEN 1 ELSE 0 END) as reads FROM tool_events")
row = cursor.fetchone()
result["allTime"] = {
    "total": row["total"],
    "writes": row["writes"] or 0,
    "edits": row["edits"] or 0,
    "bash": row["bash"] or 0,
    "reads": row["reads"] or 0
}

# By tool
cursor = conn.execute("SELECT tool_name, COUNT(*) as count FROM tool_events GROUP BY tool_name ORDER BY count DESC")
result["byTool"] = {row["tool_name"]: row["count"] for row in cursor.fetchall()}

# Daily stats (last 14 days)
now = datetime.now()
two_weeks_ago = int((now - timedelta(days=14)).timestamp())
cursor = conn.execute("SELECT date(timestamp, 'unixepoch') as day, COUNT(*) as total, SUM(CASE WHEN tool_name = 'Write' THEN 1 ELSE 0 END) as writes, SUM(CASE WHEN tool_name = 'Edit' THEN 1 ELSE 0 END) as edits, SUM(CASE WHEN tool_name = 'Bash' THEN 1 ELSE 0 END) as bash, SUM(CASE WHEN tool_name = 'Read' THEN 1 ELSE 0 END) as reads FROM tool_events WHERE timestamp > ? GROUP BY day ORDER BY day", (two_weeks_ago,))

daily_data = {row["day"]: {
    "date": row["day"],
    "total": row["total"],
    "writes": row["writes"] or 0,
    "edits": row["edits"] or 0,
    "bash": row["bash"] or 0,
    "reads": row["reads"] or 0
} for row in cursor.fetchall()}

result["daily"] = [
    daily_data.get((now - timedelta(days=i)).strftime("%Y-%m-%d"), {
        "date": (now - timedelta(days=i)).strftime("%Y-%m-%d"),
        "total": 0,
        "writes": 0,
        "edits": 0,
        "bash": 0,
        "reads": 0
    })
    for i in range(13, -1, -1)
]

conn.close()
print(json.dumps(result))
DAILYEOF
"""

def backup_original():
    """Create backup of original script"""
    if not BACKUP_SCRIPT.exists():
        print(f"📦 Creating backup: {BACKUP_SCRIPT.name}")
        with open(CCC_SCRIPT) as f:
            content = f.read()
        with open(BACKUP_SCRIPT, 'w') as f:
            f.write(content)
        print("✅ Backup created")
    else:
        print(f"⏭️  Backup already exists: {BACKUP_SCRIPT.name}")

def migrate_tool_usage():
    """Replace tool usage JSONL code with SQLite version"""
    print("\n🔧 Migrating tool usage section...")

    with open(CCC_SCRIPT) as f:
        content = f.read()

    # Find the tool usage section (from "python3 << 'TOOLEOF'" to "TOOLEOF")
    pattern = r'python3 << \'TOOLEOF\' > "\$TOOL_USAGE_TMP".*?^TOOLEOF'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if not match:
        print("❌ Could not find TOOLEOF section")
        return False

    # Replace with SQLite version
    new_content = content[:match.start()] + TOOL_USAGE_SQLITE.strip() + content[match.end():]

    with open(CCC_SCRIPT, 'w') as f:
        f.write(new_content)

    print("✅ Tool usage section migrated to SQLite")
    return True

def migrate_daily_activity():
    """Replace daily activity JSONL code with SQLite version"""
    print("\n🔧 Migrating daily activity section...")

    with open(CCC_SCRIPT) as f:
        content = f.read()

    # Find the daily activity section
    pattern = r'python3 << \'DAILYEOF\' > "\$DAILY_ACTIVITY_TMP".*?^DAILYEOF'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if not match:
        print("❌ Could not find DAILYEOF section")
        return False

    # Replace with SQLite version
    new_content = content[:match.start()] + DAILY_ACTIVITY_SQLITE.strip() + content[match.end():]

    with open(CCC_SCRIPT, 'w') as f:
        f.write(new_content)

    print("✅ Daily activity section migrated to SQLite")
    return True

def verify_syntax():
    """Verify bash script syntax"""
    print("\n🔍 Verifying script syntax...")
    import subprocess

    result = subprocess.run(
        ['bash', '-n', str(CCC_SCRIPT)],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("✅ Script syntax valid")
        return True
    else:
        print(f"❌ Syntax error:\n{result.stderr}")
        return False

def main():
    print("="*60)
    print("Dashboard Migration: JSONL → SQLite")
    print("="*60)

    if not CCC_SCRIPT.exists():
        print(f"❌ Dashboard script not found: {CCC_SCRIPT}")
        return 1

    # Backup
    backup_original()

    # Migrate sections
    if not migrate_tool_usage():
        return 1

    if not migrate_daily_activity():
        return 1

    # Verify
    if not verify_syntax():
        print("\n⚠️  Restoring from backup due to syntax error...")
        with open(BACKUP_SCRIPT) as f:
            backup_content = f.read()
        with open(CCC_SCRIPT, 'w') as f:
            f.write(backup_content)
        print("✅ Restored from backup")
        return 1

    print("\n" + "="*60)
    print("✅ Migration Complete!")
    print("="*60)
    print("\nMigrated sections:")
    print("  • Tool usage (lines ~1115-1202)")
    print("  • Daily activity (lines ~1013-1044)")
    print(f"\nBackup saved to: {BACKUP_SCRIPT.name}")
    print("\nTest with: ccc")
    print("="*60)

    return 0

if __name__ == '__main__':
    exit(main())
