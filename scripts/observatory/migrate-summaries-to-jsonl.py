#!/usr/bin/env python3
"""
Migrate Summary Data to JSONL

One-time script to add summary fields to existing session-outcomes.jsonl entries
by reading the .summary.md files.
"""

import json
import re
from pathlib import Path
from typing import Dict, Optional


def parse_summary_md(file_path: Path) -> Optional[Dict]:
    """Parse a .summary.md file and extract key fields."""

    if not file_path.exists():
        return None

    try:
        content = file_path.read_text()

        # Extract title
        title_match = re.search(r'\*\*Title:\*\* (.+)', content)
        title = title_match.group(1) if title_match else ""

        # Extract intent
        intent_match = re.search(r'\*\*Intent:\*\* (.+)', content)
        intent = intent_match.group(1) if intent_match else ""

        # Extract summary text
        summary_match = re.search(r'## Summary\n(.+?)\n\n', content, re.DOTALL)
        summary_text = summary_match.group(1).strip() if summary_match else ""

        # Extract achievements
        achievements = []
        achievements_section = re.search(r'## Achievements\n(.+?)\n\n', content, re.DOTALL)
        if achievements_section:
            achievements = [
                line.strip('- ').strip()
                for line in achievements_section.group(1).split('\n')
                if line.strip().startswith('-')
            ]

        # Extract blockers
        blockers = []
        blockers_section = re.search(r'## Blockers\n(.+?)\n\n', content, re.DOTALL)
        if blockers_section:
            blockers = [
                line.strip('- ').strip()
                for line in blockers_section.group(1).split('\n')
                if line.strip().startswith('-')
            ]

        # Extract files modified
        files_modified = []
        files_section = re.search(r'## Files Modified\n(.+?)\n\n', content, re.DOTALL)
        if files_section:
            files_modified = [
                line.strip('- ').strip()
                for line in files_section.group(1).split('\n')
                if line.strip().startswith('-')
            ]

        return {
            "title": title,
            "intent": intent,
            "summary_text": summary_text,
            "achievements": achievements,
            "blockers": blockers,
            "files_modified": files_modified
        }

    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None


def find_summary_file(session_id: str, projects_dir: Path) -> Optional[Path]:
    """Find the .summary.md file for a session."""

    # Search for files containing the session ID
    short_id = session_id[:8]

    for summary_file in projects_dir.rglob("*.summary.md"):
        if short_id in summary_file.name or session_id in summary_file.name:
            return summary_file

    return None


def migrate_summaries():
    """Add summary data to session-outcomes.jsonl entries."""

    outcomes_file = Path.home() / ".claude/data/session-outcomes.jsonl"
    projects_dir = Path.home() / ".claude/projects"

    if not outcomes_file.exists():
        print(f"❌ Outcomes file not found: {outcomes_file}")
        return

    print("🔄 Migrating Summary Data to JSONL")
    print("=" * 70)

    # Read all entries
    entries = []
    with open(outcomes_file) as f:
        for line in f:
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    print(f"📄 Loaded {len(entries)} entries")

    # Filter for session_analysis_complete events without summaries
    to_update = []
    for entry in entries:
        if entry.get("event") == "session_analysis_complete":
            if not entry.get("title") and not entry.get("summary_text"):
                to_update.append(entry)

    print(f"   {len(to_update)} entries need summary data")
    print()

    # Update entries with summary data
    updated_count = 0
    not_found_count = 0

    for i, entry in enumerate(to_update, 1):
        session_id = entry.get("session_id")
        print(f"[{i}/{len(to_update)}] {session_id[:12]}...", end=" ")

        # Find summary file
        summary_file = find_summary_file(session_id, projects_dir)

        if not summary_file:
            print("⚠️  No summary file")
            not_found_count += 1
            continue

        # Parse summary
        summary_data = parse_summary_md(summary_file)

        if not summary_data:
            print("❌ Parse failed")
            continue

        # Update entry
        entry.update(summary_data)
        print("✅ Updated")
        updated_count += 1

    # Write back all entries
    if updated_count > 0:
        print()
        print(f"💾 Writing {len(entries)} entries back to file...")

        with open(outcomes_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + '\n')

        print("✅ File updated")

    print()
    print("=" * 70)
    print(f"✅ Migration complete:")
    print(f"   Updated: {updated_count}")
    print(f"   Not found: {not_found_count}")
    print(f"   Already had summaries: {len(entries) - len(to_update)}")


if __name__ == "__main__":
    migrate_summaries()
