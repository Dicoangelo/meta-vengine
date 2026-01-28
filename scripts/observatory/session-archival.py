#!/usr/bin/env python3
"""
Session Archival & Backup System

Creates compressed archives of sessions with metadata for long-term storage.
Ensures session data is never lost.
"""

import json
import gzip
import shutil
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List


class SessionArchiver:
    """Manages session archival and backup."""

    def __init__(self):
        self.sessions_dir = Path.home() / ".claude/projects"
        self.archive_dir = Path.home() / ".claude/data/session-archives"
        self.outcomes_file = Path.home() / ".claude/data/session-outcomes.jsonl"

        # Create archive directory
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def create_archive(self, date: str = None) -> Path:
        """Create compressed archive of all sessions."""

        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        archive_name = f"sessions-{date}.tar.gz"
        archive_path = self.archive_dir / archive_name

        print(f"📦 Creating archive: {archive_name}")
        print("=" * 70)

        # Create temporary directory for staging
        temp_dir = self.archive_dir / f"temp-{date}"
        temp_dir.mkdir(exist_ok=True)

        try:
            # Copy session files
            session_count = 0
            for project_dir in self.sessions_dir.glob("*"):
                if project_dir.is_dir():
                    # Create project subdirectory in archive
                    project_name = project_dir.name
                    archive_project_dir = temp_dir / project_name
                    archive_project_dir.mkdir(exist_ok=True)

                    # Copy session files (exclude subagents)
                    for session_file in project_dir.glob("*.jsonl"):
                        if "/subagents/" not in str(session_file):
                            shutil.copy2(session_file, archive_project_dir)
                            session_count += 1

            print(f"   ✓ Copied {session_count} session files")

            # Copy session-outcomes.jsonl
            if self.outcomes_file.exists():
                shutil.copy2(self.outcomes_file, temp_dir / "session-outcomes.jsonl")
                print(f"   ✓ Copied session-outcomes.jsonl")

            # Create metadata file
            metadata = {
                "archive_date": date,
                "created_at": datetime.now().isoformat(),
                "session_count": session_count,
                "source_dir": str(self.sessions_dir),
                "version": "1.0.0"
            }

            with open(temp_dir / "archive-metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)

            print(f"   ✓ Created metadata file")

            # Create compressed archive
            actual_archive = shutil.make_archive(
                str(archive_path.with_suffix('').with_suffix('')),  # Remove .tar.gz
                'gztar',
                temp_dir
            )

            print(f"   ✓ Created compressed archive")

            # Get archive size
            actual_archive_path = Path(actual_archive)
            archive_size = actual_archive_path.stat().st_size / (1024 * 1024)  # MB
            print(f"\n📊 Archive Statistics:")
            print(f"   Location: {actual_archive_path}")
            print(f"   Size: {archive_size:.2f} MB")
            print(f"   Sessions: {session_count}")

            return actual_archive_path

        finally:
            # Clean up temp directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def backup_to_location(self, destination: Path, date: str = None):
        """Backup archive to specific location."""

        archive = self.create_archive(date=date)

        dest_path = Path(destination)
        dest_path.mkdir(parents=True, exist_ok=True)

        backup_path = dest_path / archive.name

        print(f"\n💾 Backing up to: {backup_path}")
        shutil.copy2(archive, backup_path)
        print(f"   ✅ Backup complete")

        return backup_path

    def list_archives(self):
        """List all available archives."""

        archives = sorted(self.archive_dir.glob("sessions-*.tar.gz"))

        if not archives:
            print("No archives found")
            return

        print(f"📦 Session Archives ({len(archives)} total)")
        print("=" * 70)

        for archive in archives:
            size_mb = archive.stat().st_size / (1024 * 1024)
            date = datetime.fromtimestamp(archive.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

            print(f"\n{archive.name}")
            print(f"   Size: {size_mb:.2f} MB")
            print(f"   Created: {date}")

    def extract_archive(self, archive_name: str, destination: Path):
        """Extract archive to destination."""

        archive_path = self.archive_dir / archive_name

        if not archive_path.exists():
            print(f"❌ Archive not found: {archive_name}")
            return

        dest_path = Path(destination)
        dest_path.mkdir(parents=True, exist_ok=True)

        print(f"📂 Extracting: {archive_name}")
        print(f"   To: {destination}")

        shutil.unpack_archive(archive_path, dest_path)

        print(f"   ✅ Extraction complete")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Session Archival & Backup System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create archive of all sessions
  %(prog)s --create

  # Backup to external drive
  %(prog)s --backup /Volumes/Backup/claude-sessions

  # List all archives
  %(prog)s --list

  # Extract archive
  %(prog)s --extract sessions-2026-01-19.tar.gz --destination /tmp/restored

  # Automated daily backup (add to cron)
  0 3 * * * ~/.claude/scripts/observatory/session-archival.py --create
        """
    )

    parser.add_argument("--create", action="store_true",
                       help="Create new archive")
    parser.add_argument("--backup", type=Path,
                       help="Backup archive to destination")
    parser.add_argument("--list", action="store_true",
                       help="List all archives")
    parser.add_argument("--extract", type=str,
                       help="Extract archive by name")
    parser.add_argument("--destination", type=Path,
                       help="Destination for extraction")
    parser.add_argument("--date", type=str,
                       help="Specific date for archive (YYYY-MM-DD)")

    args = parser.parse_args()

    archiver = SessionArchiver()

    if args.create:
        archiver.create_archive(date=args.date)

    elif args.backup:
        archiver.backup_to_location(args.backup, date=args.date)

    elif args.list:
        archiver.list_archives()

    elif args.extract:
        if not args.destination:
            print("Error: --destination required for extraction")
            sys.exit(1)
        archiver.extract_archive(args.extract, args.destination)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
