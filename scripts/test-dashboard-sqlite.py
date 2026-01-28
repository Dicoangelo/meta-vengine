#!/usr/bin/env python3
"""Test dashboard SQLite queries to verify data"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta

db_path = Path.home() / ".claude/data/claude.db"

print("="*60)
print("Dashboard SQLite Data Verification")
print("="*60)

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

# Test 1: Tool Events Count
cursor = conn.execute("SELECT COUNT(*) as count FROM tool_events")
tool_count = cursor.fetchone()["count"]
print(f"\n✅ Tool Events: {tool_count:,} rows")

# Test 2: Top 10 Tools
cursor = conn.execute("""
    SELECT tool_name, COUNT(*) as count
    FROM tool_events
    GROUP BY tool_name
    ORDER BY count DESC
    LIMIT 10
""")
print(f"\n📊 Top 10 Tools:")
for row in cursor.fetchall():
    print(f"  {row['tool_name']:20} {row['count']:>6,} calls")

# Test 3: Activity Events Count
cursor = conn.execute("SELECT COUNT(*) as count FROM activity_events")
activity_count = cursor.fetchone()["count"]
print(f"\n✅ Activity Events: {activity_count:,} rows")

# Test 4: Today's Activity
today = datetime.now().strftime("%Y-%m-%d")
cursor = conn.execute("""
    SELECT COUNT(*) as count
    FROM tool_events
    WHERE date(timestamp, 'unixepoch') = ?
""", (today,))
today_count = cursor.fetchone()["count"]
print(f"\n📅 Today's Tool Calls: {today_count:,}")

# Test 5: Success Rate
cursor = conn.execute("""
    SELECT
        CAST(SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as success_rate
    FROM tool_events
""")
success_rate = cursor.fetchone()["success_rate"]
print(f"\n✅ Overall Success Rate: {success_rate:.1f}%")

# Test 6: Last 7 Days Activity
week_ago = int((datetime.now() - timedelta(days=7)).timestamp())
cursor = conn.execute("""
    SELECT
        date(timestamp, 'unixepoch') as day,
        COUNT(*) as count
    FROM tool_events
    WHERE timestamp > ?
    GROUP BY day
    ORDER BY day DESC
""", (week_ago,))
print(f"\n📈 Last 7 Days Activity:")
for row in cursor.fetchall():
    print(f"  {row['day']}: {row['count']:>5,} calls")

# Test 7: Tool Usage Aggregated Table
cursor = conn.execute("SELECT COUNT(*) as count FROM tool_usage")
aggregated_count = cursor.fetchone()["count"]
print(f"\n📊 Aggregated Tool Usage: {aggregated_count} tools")

cursor = conn.execute("""
    SELECT tool_name, total_calls
    FROM tool_usage
    ORDER BY total_calls DESC
    LIMIT 5
""")
print(f"\n🔝 Top 5 from Aggregated Table:")
for row in cursor.fetchall():
    print(f"  {row['tool_name']:20} {row['total_calls']:>6,} calls")

conn.close()

print("\n" + "="*60)
print("✅ All SQLite queries successful!")
print("="*60)
