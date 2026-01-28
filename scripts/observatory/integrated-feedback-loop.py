#!/usr/bin/env python3
"""
Integrated Feedback Loop

Closes the complete meta-learning loop:
1. Session Analysis → Quality Scores
2. Quality Scores → Routing Optimization
3. Session Patterns → Pack Recommendations
4. All insights → CLAUDE.md updates

The self-improving system.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from collections import Counter

# Add observatory to path
sys.path.insert(0, str(Path(__file__).parent))


class IntegratedFeedbackLoop:
    """
    Orchestrates the complete feedback loop.
    """

    def __init__(self):
        self.data_dir = Path.home() / ".claude/data"
        self.kernel_dir = Path.home() / ".claude/kernel"
        self.packs_dir = Path.home() / ".agent-core/context-packs"
        self.claude_md = Path.home() / ".claude/CLAUDE.md"

    def run_full_loop(self, days=30, auto_apply=False):
        """Run the complete integrated feedback loop."""

        print("=" * 70)
        print("  INTEGRATED FEEDBACK LOOP")
        print("=" * 70)
        print()

        results = {
            "timestamp": datetime.now().isoformat(),
            "days_analyzed": days,
            "phases": {}
        }

        # Phase 1: Session Analysis Summary
        print("Phase 1: Session Analysis Summary")
        print("-" * 40)
        phase1 = self._summarize_session_quality(days)
        results["phases"]["session_analysis"] = phase1
        print()

        # Phase 2: Routing Optimization
        print("Phase 2: Routing Optimization")
        print("-" * 40)
        phase2 = self._run_routing_feedback(days, auto_apply)
        results["phases"]["routing"] = phase2
        print()

        # Phase 3: Pack Recommendations
        print("Phase 3: Pack Recommendations")
        print("-" * 40)
        phase3 = self._generate_pack_recommendations(days)
        results["phases"]["packs"] = phase3
        print()

        # Phase 4: Update CLAUDE.md Learned Patterns
        print("Phase 4: Update Learned Patterns")
        print("-" * 40)
        phase4 = self._update_learned_patterns(phase1, phase3)
        results["phases"]["patterns"] = phase4
        print()

        # Summary
        print("=" * 70)
        print("  FEEDBACK LOOP COMPLETE")
        print("=" * 70)
        self._print_summary(results)

        return results

    def _summarize_session_quality(self, days):
        """Summarize session quality from recent analyses."""

        sessions_file = self.data_dir / "session-outcomes.jsonl"
        if not sessions_file.exists():
            print("  No session outcomes found")
            return {"status": "no_data"}

        # Count quality distribution
        quality_dist = Counter()
        outcome_dist = Counter()
        total = 0
        total_quality = 0

        with open(sessions_file) as f:
            for line in f:
                try:
                    s = json.loads(line)
                    # Skip old sessions (simple date filter)
                    quality = s.get("quality", 0)
                    outcome = s.get("outcome", "unknown")

                    if quality:
                        quality_dist[int(quality)] += 1
                        total_quality += quality
                        total += 1
                    outcome_dist[outcome] += 1
                except:
                    pass

        avg_quality = total_quality / total if total else 0

        print(f"  Sessions analyzed: {total}")
        print(f"  Average quality: {avg_quality:.2f}/5")
        print(f"  Quality distribution:")
        for q in sorted(quality_dist.keys(), reverse=True):
            pct = quality_dist[q] / total * 100 if total else 0
            stars = "★" * q + "☆" * (5 - q)
            print(f"    {stars}: {quality_dist[q]} ({pct:.1f}%)")
        print(f"  Outcomes: {dict(outcome_dist)}")

        return {
            "status": "analyzed",
            "total_sessions": total,
            "avg_quality": round(avg_quality, 2),
            "quality_distribution": dict(quality_dist),
            "outcome_distribution": dict(outcome_dist)
        }

    def _run_routing_feedback(self, days, auto_apply):
        """Run routing feedback loop."""

        try:
            # Import from same directory
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "routing_feedback_loop",
                Path(__file__).parent / "routing-feedback-loop.py"
            )
            rfm = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(rfm)
            RoutingFeedbackLoop = rfm.RoutingFeedbackLoop
            loop = RoutingFeedbackLoop()

            patterns = loop.detect_routing_patterns(days)

            if not patterns:
                print("  No routing patterns detected")
                return {"status": "no_patterns", "patterns": []}

            updates = loop.generate_baseline_updates(patterns)

            if auto_apply and updates:
                applied = 0
                for update in updates:
                    if update.get("confidence", 0) >= 0.75:
                        if loop.apply_baseline_update(update, dry_run=False):
                            applied += 1
                print(f"  Applied {applied} routing updates")
                return {"status": "applied", "updates_applied": applied, "patterns": len(patterns)}
            else:
                print(f"  Found {len(updates)} proposed updates (not auto-applied)")
                return {"status": "proposed", "updates_proposed": len(updates), "patterns": len(patterns)}

        except Exception as e:
            print(f"  Routing feedback error: {e}")
            return {"status": "error", "error": str(e)}

    def _generate_pack_recommendations(self, days):
        """Generate pack recommendations based on session patterns."""

        # Load session intents/titles
        sessions_file = self.data_dir / "session-outcomes.jsonl"
        if not sessions_file.exists():
            return {"status": "no_data"}

        # Count keyword frequency
        keywords = Counter()
        with open(sessions_file) as f:
            for line in f:
                try:
                    s = json.loads(line)
                    title = (s.get("title", "") or "").lower()
                    intent = (s.get("intent", "") or "").lower()
                    text = title + " " + intent

                    # Extract keywords
                    if "research" in text or "arxiv" in text:
                        keywords["research-workflow"] += 1
                    if "career" in text or "resume" in text or "job" in text:
                        keywords["career-coaching"] += 1
                    if "session" in text or "analysis" in text:
                        keywords["session-analysis"] += 1
                    if "debug" in text or "fix" in text:
                        keywords["debugging-patterns"] += 1
                    if "os-app" in text or "agentic" in text:
                        keywords["os-app-architecture"] += 1
                    if "multi-agent" in text or "orchestr" in text:
                        keywords["multi-agent-orchestration"] += 1
                except:
                    pass

        # Get top recommended packs
        top_packs = keywords.most_common(5)

        print(f"  Recommended packs by usage:")
        for pack, count in top_packs:
            print(f"    {pack}: {count} sessions")

        return {
            "status": "analyzed",
            "recommended_packs": [{"pack": p, "sessions": c} for p, c in top_packs]
        }

    def _update_learned_patterns(self, session_summary, pack_recs):
        """Update CLAUDE.md with learned patterns."""

        if not self.claude_md.exists():
            print("  CLAUDE.md not found")
            return {"status": "not_found"}

        try:
            content = self.claude_md.read_text()

            # Find the Learned Patterns section
            marker_start = "<!-- AUTO-GENERATED BY META-ANALYZER - DO NOT EDIT MANUALLY -->"
            marker_end = "<!-- END AUTO-GENERATED -->"

            if marker_start not in content:
                print("  Learned Patterns section not found in CLAUDE.md")
                return {"status": "marker_not_found"}

            # Generate new patterns content
            avg_quality = session_summary.get("avg_quality", 0)
            outcomes = session_summary.get("outcome_distribution", {})
            top_packs = pack_recs.get("recommended_packs", [])[:3]

            # Determine dominant session type
            if outcomes:
                dominant = max(outcomes.items(), key=lambda x: x[1])[0]
            else:
                dominant = "unknown"

            # Build new patterns section
            new_patterns = f"""<!-- AUTO-GENERATED BY META-ANALYZER - DO NOT EDIT MANUALLY -->
<!-- Last Updated: {datetime.now().isoformat()} -->

### Usage Patterns Observed
- Average session quality: {avg_quality:.2f}/5
- Dominant session type: {dominant} ({outcomes.get(dominant, 0)} sessions)
- Success rate: {outcomes.get('success', 0) / sum(outcomes.values()) * 100 if outcomes else 0:.1f}%

### Optimized Behaviors
- For {dominant}: Use relevant context packs
- Top packs: {', '.join([p['pack'] for p in top_packs]) if top_packs else 'None detected'}
- Quality target: Maintain avg >= 3.5/5

### Recommended Packs
{chr(10).join([f'- {p["pack"]} ({p["sessions"]} sessions)' for p in top_packs]) if top_packs else '- No strong patterns detected'}

<!-- END AUTO-GENERATED -->"""

            # Replace the section
            start_idx = content.find(marker_start)
            end_idx = content.find(marker_end) + len(marker_end)

            if start_idx != -1 and end_idx != -1:
                new_content = content[:start_idx] + new_patterns + content[end_idx:]
                self.claude_md.write_text(new_content)
                print("  Updated CLAUDE.md Learned Patterns")
                return {"status": "updated"}
            else:
                print("  Could not find pattern markers")
                return {"status": "marker_error"}

        except Exception as e:
            print(f"  Error updating patterns: {e}")
            return {"status": "error", "error": str(e)}

    def _print_summary(self, results):
        """Print final summary."""

        print()
        phase1 = results["phases"].get("session_analysis", {})
        phase2 = results["phases"].get("routing", {})
        phase3 = results["phases"].get("packs", {})
        phase4 = results["phases"].get("patterns", {})

        print(f"  Sessions analyzed: {phase1.get('total_sessions', 0)}")
        print(f"  Avg quality: {phase1.get('avg_quality', 0)}/5")
        print(f"  Routing patterns: {phase2.get('patterns', 0)}")
        print(f"  CLAUDE.md: {phase4.get('status', 'unknown')}")
        print()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Integrated Feedback Loop")
    parser.add_argument("--days", type=int, default=30, help="Days to analyze")
    parser.add_argument("--auto-apply", action="store_true", help="Auto-apply routing updates")
    parser.add_argument("--output", help="Save results to JSON")

    args = parser.parse_args()

    loop = IntegratedFeedbackLoop()
    results = loop.run_full_loop(args.days, args.auto_apply)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
