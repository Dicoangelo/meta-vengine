#!/usr/bin/env python3
"""
Phase 2: Dashboard Update Script
Purpose: Update ccc-generator.sh to use Phase 2 SQLite tables
Created: 2026-01-28
"""

import re
from pathlib import Path

CCC_SCRIPT = Path.home() / '.claude/scripts/ccc-generator.sh'
BACKUP_SCRIPT = Path.home() / '.claude/scripts/ccc-generator.sh.phase2-backup'

# Git Activity SQLite Section
GIT_ACTIVITY_SQLITE = """python3 << 'GITEOF' > "$GIT_ACTIVITY_TMP"
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict

home = Path.home()
db_path = home / ".claude/data/claude.db"

result = {
    "commits": [],
    "stats": {"total": 0, "today": 0, "week": 0, "insertions": 0, "deletions": 0},
    "byRepo": {},
    "byDay": [],
    "topAuthors": []
}

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

# Get all git events
cursor = conn.execute("SELECT * FROM git_events ORDER BY timestamp DESC LIMIT 100")
commits = [dict(row) for row in cursor.fetchall()]

# Calculate stats
now = datetime.now()
today_start = int(datetime(now.year, now.month, now.day).timestamp())
week_start = int((now - timedelta(days=7)).timestamp())

result["stats"]["total"] = len(commits)

for commit in commits:
    ts = commit.get("timestamp", 0)

    if ts >= today_start:
        result["stats"]["today"] += 1
    if ts >= week_start:
        result["stats"]["week"] += 1

    result["stats"]["insertions"] += commit.get("additions", 0) or 0
    result["stats"]["deletions"] += commit.get("deletions", 0) or 0

    repo = commit.get("repo", "unknown")
    result["byRepo"][repo] = result["byRepo"].get(repo, 0) + 1

result["commits"] = commits[:20]

# Daily commits (last 30 days)
thirty_days_ago = int((now - timedelta(days=30)).timestamp())
cursor = conn.execute("SELECT date(timestamp, 'unixepoch') as day, COUNT(*) as count FROM git_events WHERE timestamp > ? GROUP BY day ORDER BY day DESC LIMIT 30", (thirty_days_ago,))
result["byDay"] = [{"date": row["day"], "count": row["count"]} for row in cursor.fetchall()]

# Top authors
cursor = conn.execute("SELECT author, COUNT(*) as count FROM git_events WHERE author IS NOT NULL GROUP BY author ORDER BY count DESC LIMIT 5")
result["topAuthors"] = [{"author": row["author"], "commits": row["count"]} for row in cursor.fetchall()]

conn.close()
print(json.dumps(result))
GITEOF
"""

def backup_script():
    """Create backup before modification"""
    if not BACKUP_SCRIPT.exists():
        print(f"📦 Creating backup: {BACKUP_SCRIPT.name}")
        with open(CCC_SCRIPT) as f:
            content = f.read()
        with open(BACKUP_SCRIPT, 'w') as f:
            f.write(content)
        print("✅ Backup created")
    else:
        print(f"⏭️  Backup already exists: {BACKUP_SCRIPT.name}")

def update_git_activity():
    """Update git activity section to use SQLite"""
    print("\n🔧 Migrating git activity section...")

    with open(CCC_SCRIPT) as f:
        content = f.read()

    # Find git activity section
    pattern = r'python3 << \'GITEOF\' > "\$GIT_ACTIVITY_TMP".*?^GITEOF'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if not match:
        print("⚠️  Could not find GITEOF section")
        return False

    # Replace with SQLite version
    new_content = content[:match.start()] + GIT_ACTIVITY_SQLITE.strip() + content[match.end():]

    with open(CCC_SCRIPT, 'w') as f:
        f.write(new_content)

    print("✅ Git activity section migrated to SQLite")
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
    print("Phase 2: Dashboard SQLite Update")
    print("="*60)

    if not CCC_SCRIPT.exists():
        print(f"❌ Dashboard script not found: {CCC_SCRIPT}")
        return 1

    # Backup
    backup_script()

    # Update git activity
    if not update_git_activity():
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
    print("✅ Phase 2 Dashboard Update Complete!")
    print("="*60)
    print("\nUpdated sections:")
    print("  • Git activity → git_events table")
    print(f"\nBackup saved to: {BACKUP_SCRIPT.name}")
    print("\nNote: Routing metrics and infrastructure sections")
    print("      can be updated in future dashboard refactoring")
    print("="*60)

    return 0

if __name__ == '__main__':
    exit(main())
