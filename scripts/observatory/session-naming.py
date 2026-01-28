#!/usr/bin/env python3
"""
Session Naming System

Extracts context from session transcripts and generates meaningful names.
Renames session files from UUIDs to human-readable names.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


class SessionNamer:
    """Generates meaningful names for sessions based on content."""

    def __init__(self):
        self.sessions_dir = Path.home() / ".claude/projects"
        self.max_name_length = 80

        # Stop words to exclude from names
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'under', 'again',
            'can', 'could', 'should', 'would', 'may', 'might', 'must', 'will',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
            'my', 'your', 'his', 'its', 'our', 'their', 'please', 'help', 'need'
        }

    def extract_session_context(self, session_file: Path) -> Optional[Dict]:
        """Extract context from session transcript."""

        try:
            with open(session_file) as f:
                events = []
                for line in f:
                    if line.strip():
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

            if not events:
                return None

            # Extract first user message
            first_user_message = None
            for event in events:
                if event.get("type") == "message" or event.get("event") == "message":
                    msg_data = event.get("data", event)
                    if msg_data.get("role") == "user":
                        content = msg_data.get("content", "")
                        if content and len(str(content).strip()) > 0:
                            first_user_message = str(content)
                            break

            # Extract session metadata
            timestamp = events[0].get("timestamp", 0)
            if timestamp:
                date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
            else:
                date = datetime.fromtimestamp(session_file.stat().st_mtime).strftime("%Y-%m-%d")

            return {
                "first_message": first_user_message,
                "timestamp": timestamp,
                "date": date,
                "event_count": len(events)
            }

        except Exception as e:
            print(f"  ⚠️  Error extracting context: {e}")
            return None

    def generate_name(self, context: Dict, session_id: str, creation_num: Optional[int] = None) -> str:
        """Generate meaningful name from session context."""

        # Extract key information
        first_msg = context.get("first_message", "")
        date = context.get("date", "unknown")

        # Build name components
        parts = []

        # 1. Date prefix
        parts.append(date)

        # 2. Creation number (if provided)
        if creation_num is not None:
            parts.append(f"#{creation_num:04d}")

        # 3. Context keywords
        if first_msg:
            keywords = self._extract_keywords(first_msg)
            if keywords:
                parts.append(keywords)

        # 4. Session ID (last 8 chars for uniqueness)
        short_id = session_id[:8]
        parts.append(f"id-{short_id}")

        # Join with underscores for clarity
        full_name = "_".join(parts)

        # Ensure unique and within length limits
        return self._sanitize_name(full_name)

    def _extract_keywords(self, text: str) -> str:
        """Extract key words from text for naming."""

        # Remove special characters, keep alphanumeric and spaces
        text = re.sub(r'[^\w\s-]', ' ', text.lower())

        # Split into words
        words = text.split()

        # Filter out stop words and short words
        keywords = [
            w for w in words
            if len(w) > 2 and w not in self.stop_words
        ]

        # Take first 4-6 meaningful words
        keywords = keywords[:6]

        if not keywords:
            return ""

        # Join with hyphens
        name = "-".join(keywords)

        # Limit length
        if len(name) > self.max_name_length:
            name = name[:self.max_name_length]
            # Cut at last hyphen
            if "-" in name:
                name = name[:name.rfind("-")]

        return name

    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for filesystem."""

        # Replace problematic characters
        name = re.sub(r'[^\w\s-]', '', name)
        name = re.sub(r'[\s]+', '-', name)
        name = re.sub(r'-+', '-', name)
        name = name.strip('-')

        # Ensure max length
        if len(name) > self.max_name_length:
            name = name[:self.max_name_length].rstrip('-')

        return name.lower()

    def rename_session(self, session_file: Path, creation_num: Optional[int] = None, dry_run=False) -> Optional[Path]:
        """Rename session file with context-based name."""

        session_id = session_file.stem

        # Extract context
        context = self.extract_session_context(session_file)
        if not context:
            return None

        # Generate new name
        new_name = self.generate_name(context, session_id, creation_num=creation_num)

        # Ensure uniqueness
        new_file = session_file.parent / f"{new_name}.jsonl"
        counter = 1
        while new_file.exists() and new_file != session_file:
            new_file = session_file.parent / f"{new_name}-{counter}.jsonl"
            counter += 1

        if dry_run:
            print(f"  Would rename: {session_file.name}")
            print(f"            to: {new_file.name}")
            return new_file

        try:
            # Rename file
            session_file.rename(new_file)
            print(f"  ✓ Renamed: {session_file.name}")
            print(f"         to: {new_file.name}")
            return new_file

        except Exception as e:
            print(f"  ❌ Error renaming {session_file.name}: {e}")
            return None

    def rename_all_sessions(self, dry_run=False):
        """Rename all session files in projects directory."""

        # Find all main session files (exclude subagents)
        session_files = []
        for project_dir in self.sessions_dir.glob("*"):
            if project_dir.is_dir():
                for session_file in project_dir.glob("*.jsonl"):
                    if "/subagents/" not in str(session_file):
                        # Only rename UUID-named files
                        if self._is_uuid_name(session_file.stem):
                            session_files.append(session_file)

        # Sort by creation time (oldest first)
        session_files.sort(key=lambda f: f.stat().st_ctime)

        print(f"Found {len(session_files)} sessions to rename")
        print("=" * 70)

        renamed_count = 0
        for i, session_file in enumerate(session_files, 1):
            print(f"\n[{i}/{len(session_files)}]")
            # Pass creation number
            new_file = self.rename_session(session_file, creation_num=i, dry_run=dry_run)
            if new_file:
                renamed_count += 1

        print(f"\n{'[DRY RUN] ' if dry_run else ''}Renamed {renamed_count}/{len(session_files)} sessions")

    def _is_uuid_name(self, name: str) -> bool:
        """Check if filename looks like a UUID."""
        # UUID pattern: 8-4-4-4-12 hexadecimal characters
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        return bool(re.match(uuid_pattern, name.lower()))


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Session Naming System - Generate context-based names",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run: see what would be renamed
  %(prog)s --all --dry-run

  # Rename all UUID-named sessions
  %(prog)s --all

  # Rename specific session
  %(prog)s --session-file /path/to/session.jsonl

  # Test name generation
  %(prog)s --test "Implement routing system"
        """
    )

    parser.add_argument("--all", action="store_true",
                       help="Rename all UUID-named sessions")
    parser.add_argument("--session-file", type=Path,
                       help="Rename specific session file")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be renamed without doing it")
    parser.add_argument("--test", type=str,
                       help="Test name generation for given text")

    args = parser.parse_args()

    namer = SessionNamer()

    if args.test:
        # Test name generation
        context = {
            "first_message": args.test,
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        name = namer.generate_name(context, "test-uuid-1234")
        print(f"Generated name: {name}")

    elif args.session_file:
        # Rename specific file
        if not args.session_file.exists():
            print(f"Error: File not found: {args.session_file}")
            sys.exit(1)
        namer.rename_session(args.session_file, dry_run=args.dry_run)

    elif args.all:
        # Rename all sessions
        namer.rename_all_sessions(dry_run=args.dry_run)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
