#!/usr/bin/env python3
"""
Batch Summary Generator

Generates summaries for all existing analyzed sessions without re-running full analysis.
Uses existing session-outcomes.jsonl data to load analysis results.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import with proper module loading
import importlib.util
spec = importlib.util.spec_from_file_location("post_session_analyzer", Path(__file__).parent / "post-session-analyzer.py")
psa_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(psa_module)
PostSessionAnalyzer = psa_module.PostSessionAnalyzer

spec2 = importlib.util.spec_from_file_location("session_summarizer", Path(__file__).parent / "session_summarizer.py")
ss_module = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(ss_module)
SessionSummarizer = ss_module.SessionSummarizer


class BatchSummaryGenerator:
    """Generate summaries for all analyzed sessions."""

    def __init__(self):
        self.analyzer = PostSessionAnalyzer()
        self.summarizer = SessionSummarizer()
        self.outcomes_file = Path.home() / ".claude/data/session-outcomes.jsonl"

    def load_analyzed_sessions(self) -> List[Dict]:
        """Load all session analyses from session-outcomes.jsonl."""

        if not self.outcomes_file.exists():
            print(f"❌ No outcomes file found at: {self.outcomes_file}")
            return []

        sessions = []
        with open(self.outcomes_file) as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        if data.get("event") == "session_analysis_complete":
                            sessions.append(data)
                    except json.JSONDecodeError:
                        continue

        return sessions

    def generate_summary_for_session(self, session_id: str, existing_analysis: Dict) -> bool:
        """Generate summary for a single session using existing analysis."""

        try:
            # Load transcript
            transcript = self.analyzer.load_session_transcript(session_id)

            # Build consensus dict from existing analysis
            consensus = {
                "outcome": existing_analysis.get("outcome", "unknown"),
                "quality": existing_analysis.get("quality", 3),
                "complexity": existing_analysis.get("complexity", 0.5),
                "model_efficiency": existing_analysis.get("model_efficiency", 0.5),
                "dq_score": existing_analysis.get("dq_score", 0.5),
                "confidence": existing_analysis.get("confidence", 0.5)
            }

            # Generate summary
            summary = self.summarizer.generate_summary(transcript, consensus)

            # Save summary file
            session_file = self.analyzer._find_session_file(session_id)
            if session_file:
                summary_file = self.summarizer.save_summary_file(session_file, summary)
                return True
            else:
                print(f"      ⚠️  Session file not found: {session_id}")
                return False

        except Exception as e:
            print(f"      ❌ Error: {e}")
            return False

    def batch_generate(self, limit: int = None, skip_existing: bool = True):
        """Generate summaries for all analyzed sessions."""

        print("🔄 Batch Summary Generation")
        print("=" * 70)

        # Load analyzed sessions
        print("📄 Loading analyzed sessions...")
        sessions = self.load_analyzed_sessions()
        total = len(sessions)

        if total == 0:
            print("❌ No analyzed sessions found")
            return

        print(f"   Found {total} analyzed sessions")

        # Apply limit if specified
        if limit:
            sessions = sessions[:limit]
            print(f"   Processing first {limit} sessions")

        print()

        # Generate summaries
        success_count = 0
        skip_count = 0

        for i, session_data in enumerate(sessions, 1):
            session_id = session_data.get("session_id")

            print(f"[{i}/{len(sessions)}] {session_id[:12]}...")

            # Skip if summary already exists (optional)
            if skip_existing:
                session_file = self.analyzer._find_session_file(session_id)
                if session_file:
                    summary_file = session_file.with_suffix('.summary.md')
                    if summary_file.exists():
                        print(f"      ⏭️  Summary already exists, skipping")
                        skip_count += 1
                        continue

            # Generate summary
            if self.generate_summary_for_session(session_id, session_data):
                print(f"      ✅ Summary generated")
                success_count += 1
            else:
                print(f"      ❌ Failed")

        print()
        print("=" * 70)
        print(f"✅ Batch generation complete:")
        print(f"   Success: {success_count}")
        print(f"   Skipped: {skip_count}")
        print(f"   Failed: {len(sessions) - success_count - skip_count}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Batch generate summaries for analyzed sessions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate summaries for all sessions
  %(prog)s

  # Generate for first 10 sessions
  %(prog)s --limit 10

  # Regenerate all (overwrite existing)
  %(prog)s --no-skip

  # Generate for specific session
  %(prog)s --session-id abc123
        """
    )

    parser.add_argument("--limit", type=int, help="Only process N sessions")
    parser.add_argument("--no-skip", action="store_true",
                       help="Regenerate even if summary exists")
    parser.add_argument("--session-id", help="Generate for specific session only")

    args = parser.parse_args()

    generator = BatchSummaryGenerator()

    if args.session_id:
        # Single session mode
        print(f"📝 Generating summary for session: {args.session_id}")

        # Load analysis from outcomes file
        sessions = generator.load_analyzed_sessions()
        analysis = None
        for s in sessions:
            if s.get("session_id") == args.session_id:
                analysis = s
                break

        if not analysis:
            print(f"❌ No analysis found for session: {args.session_id}")
            sys.exit(1)

        success = generator.generate_summary_for_session(args.session_id, analysis)
        if success:
            print("✅ Summary generated successfully")
        else:
            print("❌ Summary generation failed")
            sys.exit(1)

    else:
        # Batch mode
        generator.batch_generate(
            limit=args.limit,
            skip_existing=not args.no_skip
        )


if __name__ == "__main__":
    main()
