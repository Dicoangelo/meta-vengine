#!/usr/bin/env python3
"""
Batch Process All Sessions

Fastest way to analyze and rename all sessions in order:
1. Finds all UUID-named sessions
2. Sorts by creation date
3. Numbers sequentially (#0003, #0004, etc.)
4. Runs analysis + generates summary (if needed)
5. Renames with context-based names
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# Import analysis system
sys.path.insert(0, str(Path(__file__).parent))

import importlib.util
spec = importlib.util.spec_from_file_location("post_session_analyzer", Path(__file__).parent / "post-session-analyzer.py")
psa_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(psa_module)
PostSessionAnalyzer = psa_module.PostSessionAnalyzer


class BatchSessionProcessor:
    """Process all sessions efficiently in one pass."""

    def __init__(self):
        self.analyzer = PostSessionAnalyzer()
        self.projects_dir = Path.home() / ".claude/projects"

    def find_uuid_sessions(self) -> List[Tuple[Path, float]]:
        """Find all UUID-named sessions with creation times."""

        sessions = []

        # UUID pattern (8-4-4-4-12 hex digits)
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jsonl$')

        for jsonl_file in self.projects_dir.rglob("*.jsonl"):
            # Skip subagents and agent files
            if "/subagents/" in str(jsonl_file) or jsonl_file.name.startswith("agent-"):
                continue

            # Skip already numbered files
            if "#" in jsonl_file.name:
                continue

            # Only process UUID-named files
            if uuid_pattern.match(jsonl_file.name):
                # Get creation time
                ctime = jsonl_file.stat().st_ctime
                sessions.append((jsonl_file, ctime))

        # Sort by creation time
        sessions.sort(key=lambda x: x[1])

        return sessions

    def extract_first_query(self, session_file: Path) -> str:
        """Extract first user query from session."""

        try:
            with open(session_file) as f:
                for line in f:
                    if line.strip():
                        event = json.loads(line)

                        # Look for user message
                        if event.get('type') == 'user':
                            msg = event.get('message', {})
                            content = msg.get('content')
                            if content and len(str(content)) > 5:
                                return str(content)[:200]
        except Exception as e:
            print(f"      ⚠️  Could not extract query: {e}")

        return None

    def generate_context_name(self, query: str) -> str:
        """Generate context-based name from query."""

        if not query:
            return "unknown-task"

        # Clean query
        query = query.lower().strip()

        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                     'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
                     'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                     'would', 'should', 'could', 'may', 'might', 'must', 'can', 'need',
                     'i', 'you', 'we', 'they', 'it', 'this', 'that', 'these', 'those'}

        # Extract words
        words = re.findall(r'\b\w+\b', query)
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        # Take first 4-6 meaningful words
        context = '-'.join(keywords[:6])

        # Limit length
        if len(context) > 60:
            context = context[:60]

        return context or "unknown-task"

    def get_session_date(self, session_file: Path) -> str:
        """Get session date in YYYY-MM-DD format."""
        ctime = session_file.stat().st_ctime
        return datetime.fromtimestamp(ctime).strftime("%Y-%m-%d")

    def process_session(self, session_file: Path, session_number: int, dry_run: bool = False):
        """Process single session: analyze, summarize, rename."""

        session_id = session_file.stem
        short_id = session_id[:8]

        print(f"\n[#{session_number:04d}] {session_id[:16]}...")

        # Step 1: Check if already analyzed
        outcomes_file = Path.home() / ".claude/data/session-outcomes.jsonl"
        already_analyzed = False

        if outcomes_file.exists():
            with open(outcomes_file) as f:
                for line in f:
                    if session_id in line:
                        already_analyzed = True
                        break

        # Step 2: Analyze if needed
        if not already_analyzed:
            print(f"   📊 Running analysis...")
            if not dry_run:
                try:
                    self.analyzer.analyze_session(session_id)
                    print(f"      ✓ Analysis complete")
                except Exception as e:
                    print(f"      ❌ Analysis failed: {e}")
                    return None
        else:
            print(f"   ⏭️  Already analyzed")

        # Step 3: Extract query and generate name
        print(f"   📝 Extracting context...")
        query = self.extract_first_query(session_file)

        if query:
            print(f"      Query: {query[:60]}...")
            context = self.generate_context_name(query)
        else:
            context = "unknown-task"
            print(f"      ⚠️  No query found, using default")

        # Step 4: Generate new name
        date = self.get_session_date(session_file)
        new_name = f"{date}_#{session_number:04d}_{context}_id-{short_id}.jsonl"
        new_path = session_file.parent / new_name

        # Step 5: Rename
        if dry_run:
            print(f"   🔍 [DRY RUN] Would rename to:")
            print(f"      {new_name}")
        else:
            try:
                session_file.rename(new_path)
                print(f"   ✅ Renamed: {new_name}")

                # Also rename summary file if exists
                summary_file = session_file.with_suffix('.summary.md')
                if summary_file.exists():
                    new_summary = new_path.with_suffix('.summary.md')
                    summary_file.rename(new_summary)
                    print(f"      ✓ Summary renamed too")

                return new_path
            except Exception as e:
                print(f"   ❌ Rename failed: {e}")
                return None

        return new_path

    def batch_process(self, limit: int = None, dry_run: bool = False):
        """Process all UUID sessions in order."""

        print("🚀 Batch Session Processor")
        print("=" * 70)
        print("Using full 6-agent ACE consensus system")
        print()

        # Find all UUID sessions
        print("🔍 Finding UUID-named sessions...")
        sessions = self.find_uuid_sessions()
        total = len(sessions)

        print(f"   Found {total} sessions to process")

        if total == 0:
            print("✅ All sessions already processed!")
            return

        # Already have #0001 and #0002
        start_number = 3

        # Apply limit if specified
        if limit:
            sessions = sessions[:limit]
            print(f"   Processing first {limit} sessions")

        if dry_run:
            print()
            print("⚠️  DRY RUN MODE - No changes will be made")

        print()
        print("=" * 70)

        # Process each session
        success_count = 0

        for i, (session_file, _) in enumerate(sessions, start=start_number):
            try:
                result = self.process_session(session_file, i, dry_run)
                if result:
                    success_count += 1
            except Exception as e:
                print(f"\n   ❌ Fatal error: {e}")
                continue

        print()
        print("=" * 70)
        print(f"✅ Batch processing complete:")
        print(f"   Processed: {success_count}/{len(sessions)}")
        print(f"   Failed: {len(sessions) - success_count}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Batch process all sessions with full analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run: see what would happen
  %(prog)s --dry-run

  # Process first 10 sessions
  %(prog)s --limit 10

  # Process all sessions
  %(prog)s
        """
    )

    parser.add_argument("--limit", type=int, help="Only process first N sessions")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without doing it")

    args = parser.parse_args()

    processor = BatchSessionProcessor()
    processor.batch_process(limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
