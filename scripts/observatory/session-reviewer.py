#!/usr/bin/env python3
"""
Session-by-Session Reviewer
Interactive tool to review analyzed sessions one at a time
"""

import json
import sys
from pathlib import Path


class SessionReviewer:
    """Interactive session review tool."""

    def __init__(self):
        self.outcomes_file = Path.home() / ".claude/data/session-outcomes.jsonl"
        self.sessions = []
        self.current_index = 0

    def load_sessions(self):
        """Load all analyzed sessions."""
        with open(self.outcomes_file) as f:
            for line in f:
                if line.strip():
                    self.sessions.append(json.loads(line))

        print(f"✅ Loaded {len(self.sessions)} analyzed sessions\n")

    def display_session(self, index: int):
        """Display detailed view of a session."""
        if index < 0 or index >= len(self.sessions):
            print(f"❌ Invalid session index: {index}")
            return

        s = self.sessions[index]

        # Header
        print("\n" + "=" * 100)
        print(f"SESSION {index + 1} of {len(self.sessions)}")
        print("=" * 100)

        # Basic info
        sid = s["session_id"]
        sid_short = sid[:16] if len(sid) > 16 else sid

        print(f"\n📋 SESSION ID:    {sid_short}")
        print(f"    Full ID:      {sid}")

        # Title and intent
        title = s.get("title", "No title")
        intent = s.get("intent", "Unknown intent")

        print(f"\n📝 TITLE:         {title[:80]}")
        if len(title) > 80:
            print(f"                  {title[80:160]}")
        print(f"\n🎯 INTENT:        {intent}")

        # Outcome and metrics
        outcome = s.get("outcome", "unknown")
        quality = s.get("quality", "?")
        complexity = s.get("complexity", 0)
        efficiency = s.get("model_efficiency", 0)
        dq = s.get("dq_score", 0)
        confidence = s.get("confidence", 0)

        outcome_emoji = {
            "success": "✅",
            "abandoned": "⏸️",
            "error": "❌",
            "research": "🔬",
            "partial": "⚠️"
        }.get(outcome, "❓")

        if isinstance(quality, int):
            q_stars = "★" * quality + "☆" * (5 - quality)
        else:
            q_stars = "?"

        print(f"\n{outcome_emoji}  OUTCOME:       {outcome}")
        print(f"⭐ QUALITY:       {q_stars} ({quality}/5)")
        print(f"🧩 COMPLEXITY:    {complexity:.2f}")
        print(f"⚡ EFFICIENCY:    {efficiency:.1%}")
        print(f"📊 DQ SCORE:      {dq:.3f}")
        print(f"🎲 CONFIDENCE:    {confidence:.1%}")

        # Summary text
        summary = s.get("summary_text", "")
        if summary:
            print(f"\n📄 SUMMARY:")
            # Wrap summary to 90 chars
            words = summary.split()
            line = "   "
            for word in words:
                if len(line) + len(word) + 1 > 93:
                    print(line)
                    line = "   " + word
                else:
                    line += " " + word if line != "   " else word
            if line != "   ":
                print(line)

        # Achievements
        achievements = s.get("achievements", [])
        if achievements:
            print(f"\n✅ ACHIEVEMENTS:")
            for ach in achievements:
                print(f"   • {ach}")

        # Blockers
        blockers = s.get("blockers", [])
        if blockers:
            print(f"\n🚫 BLOCKERS:")
            for blocker in blockers:
                print(f"   • {blocker}")

        # Files modified
        files = s.get("files_modified", [])
        if files:
            print(f"\n📁 FILES MODIFIED ({len(files)}):")
            for f in files[:10]:
                print(f"   • {f}")
            if len(files) > 10:
                print(f"   ... and {len(files) - 10} more")

        # Footer
        print("\n" + "=" * 100)

    def review_all(self):
        """Review all sessions interactively."""
        print("\n🔍 SESSION-BY-SESSION REVIEW")
        print("=" * 100)
        print("\nCommands:")
        print("  [Enter]     - Next session")
        print("  [number]    - Jump to session number")
        print("  q / quit    - Exit")
        print("  s / summary - Show summary")
        print("\n" + "=" * 100)

        while self.current_index < len(self.sessions):
            self.display_session(self.current_index)

            # Get user input
            try:
                user_input = input(f"\n>>> [Session {self.current_index + 1}/{len(self.sessions)}] Command: ").strip()

                if not user_input:
                    # Next session
                    self.current_index += 1
                elif user_input.lower() in ['q', 'quit', 'exit']:
                    print("\n✅ Review session ended")
                    break
                elif user_input.lower() in ['s', 'summary']:
                    self.show_summary()
                elif user_input.isdigit():
                    target = int(user_input) - 1
                    if 0 <= target < len(self.sessions):
                        self.current_index = target
                    else:
                        print(f"❌ Invalid session number. Must be 1-{len(self.sessions)}")
                else:
                    print(f"❌ Unknown command: {user_input}")

            except (EOFError, KeyboardInterrupt):
                print("\n\n✅ Review session ended")
                break

        if self.current_index >= len(self.sessions):
            print("\n" + "=" * 100)
            print("🎉 ALL SESSIONS REVIEWED!")
            print("=" * 100)

    def show_summary(self):
        """Show overall summary stats."""
        from collections import defaultdict

        # Calculate stats
        by_outcome = defaultdict(int)
        by_quality = defaultdict(int)

        for s in self.sessions:
            by_outcome[s.get("outcome", "unknown")] += 1
            by_quality[s.get("quality", 0)] += 1

        print("\n" + "=" * 100)
        print("📊 OVERALL SUMMARY")
        print("=" * 100)

        print(f"\nTotal Sessions: {len(self.sessions)}")

        print("\nOutcome Distribution:")
        for outcome, count in sorted(by_outcome.items(), key=lambda x: -x[1]):
            pct = count / len(self.sessions) * 100
            print(f"  {outcome:12s}: {count:3d} ({pct:5.1f}%)")

        print("\nQuality Distribution:")
        for quality in sorted(by_quality.keys(), reverse=True):
            count = by_quality[quality]
            pct = count / len(self.sessions) * 100
            stars = "★" * quality if isinstance(quality, int) and quality > 0 else "☆"
            print(f"  {stars:5s} ({quality}): {count:3d} ({pct:5.1f}%)")

        print("\n" + "=" * 100)


def main():
    reviewer = SessionReviewer()
    reviewer.load_sessions()
    reviewer.review_all()


if __name__ == "__main__":
    main()
