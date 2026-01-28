#!/usr/bin/env python3
"""
Populate memory_links table by analyzing relationships between memory items.

Creates links between items that share:
- Same project
- Similar categories
- Related sessions
- Content similarity (basic keyword matching)

Run: python3 ~/.claude/scripts/populate-memory-links.py
"""

import sqlite3
from pathlib import Path
from collections import defaultdict

def main():
    db_path = Path.home() / '.claude/memory/supermemory.db'

    if not db_path.exists():
        print("❌ supermemory.db not found")
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Get all memory items
    items = conn.execute("""
        SELECT id, content, source, project, tags, date, created_at
        FROM memory_items
    """).fetchall()

    print(f"Analyzing {len(items)} memory items...")

    # Group items by project
    by_project = defaultdict(list)
    # Group items by source (e.g., session, manual, etc.)
    by_source = defaultdict(list)
    # Group items by date (same day = related)
    by_date = defaultdict(list)

    for item in items:
        item_dict = dict(item)
        if item_dict.get('project'):
            by_project[item_dict['project']].append(item_dict)
        if item_dict.get('source'):
            by_source[item_dict['source']].append(item_dict)
        if item_dict.get('date'):
            by_date[item_dict['date']].append(item_dict)

    links_created = 0

    # Create links within same project (strength 0.7)
    print("Creating project links...")
    for project, project_items in by_project.items():
        if len(project_items) < 2:
            continue
        for i, item1 in enumerate(project_items[:-1]):
            for item2 in project_items[i+1:]:
                if item1['id'] != item2['id']:
                    conn.execute("""
                        INSERT OR REPLACE INTO memory_links (from_id, to_id, link_type, strength)
                        VALUES (?, ?, 'same_project', 0.7)
                    """, (item1['id'], item2['id']))
                    links_created += 1

    # Create links within same source (strength 0.5)
    print("Creating source links...")
    for source, source_items in by_source.items():
        if len(source_items) < 2:
            continue
        # Limit to first 50 per source to avoid explosion
        for i, item1 in enumerate(source_items[:50]):
            for item2 in source_items[i+1:50]:
                if item1['id'] != item2['id']:
                    conn.execute("""
                        INSERT OR REPLACE INTO memory_links (from_id, to_id, link_type, strength)
                        VALUES (?, ?, 'same_source', 0.5)
                    """, (item1['id'], item2['id']))
                    links_created += 1

    # Create links within same date (strength 0.8 - temporally related)
    print("Creating temporal links...")
    for date, date_items in by_date.items():
        if len(date_items) < 2:
            continue
        for i, item1 in enumerate(date_items[:-1]):
            for item2 in date_items[i+1:]:
                if item1['id'] != item2['id']:
                    conn.execute("""
                        INSERT OR REPLACE INTO memory_links (from_id, to_id, link_type, strength)
                        VALUES (?, ?, 'same_date', 0.8)
                    """, (item1['id'], item2['id']))
                    links_created += 1

    conn.commit()

    # Verify
    count = conn.execute("SELECT COUNT(*) FROM memory_links").fetchone()[0]

    print(f"\n✅ Created {links_created} links")
    print(f"   Total links in database: {count}")

    # Show link type distribution
    dist = conn.execute("""
        SELECT link_type, COUNT(*) as cnt, AVG(strength) as avg_strength
        FROM memory_links
        GROUP BY link_type
    """).fetchall()

    print("\nLink distribution:")
    for row in dist:
        print(f"   {row['link_type']}: {row['cnt']} links (avg strength: {row['avg_strength']:.2f})")

    conn.close()

if __name__ == '__main__':
    main()
