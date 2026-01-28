#!/usr/bin/env python3
"""
Routing Feedback Loop

Closes the meta-learning loop:
Session Analysis → Pattern Detection → Baseline Updates → Improved Routing

Analyzes session patterns and automatically updates routing baselines.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict


class RoutingFeedbackLoop:
    """
    Closes the meta-learning loop for routing optimization.

    Analyzes session outcomes to detect patterns that suggest
    routing improvements, then proposes/applies baseline updates.
    """

    def __init__(self):
        self.baselines_file = Path.home() / ".claude/kernel/baselines.json"
        self.sessions_file = Path.home() / ".claude/data/session-outcomes.jsonl"
        self.min_samples = 30  # Minimum sessions before proposing changes
        self.confidence_threshold = 0.75  # Min confidence to auto-apply

    def detect_routing_patterns(self, days=30) -> List[Dict]:
        """Detect patterns that suggest routing improvements."""

        # Load recent session analyses
        sessions = self._load_recent_sessions(days)

        if len(sessions) < self.min_samples:
            print(f"⚠️  Only {len(sessions)} sessions - need {self.min_samples} minimum for reliable patterns")
            return []

        print(f"📊 Analyzing {len(sessions)} sessions from last {days} days...")

        patterns = []

        # Pattern 1: Consistent over-provisioning at complexity X
        over_prov = self._detect_overprovisioning(sessions)
        if over_prov:
            patterns.append(over_prov)
            print(f"   ✓ Detected: {over_prov['rationale']}")

        # Pattern 2: High-complexity sessions on Haiku struggling
        haiku_struggles = self._detect_haiku_struggles(sessions)
        if haiku_struggles:
            patterns.append(haiku_struggles)
            print(f"   ✓ Detected: {haiku_struggles['rationale']}")

        # Pattern 3: Opus over-used for moderate complexity
        opus_overuse = self._detect_opus_overuse(sessions)
        if opus_overuse:
            patterns.append(opus_overuse)
            print(f"   ✓ Detected: {opus_overuse['rationale']}")

        # Pattern 4: Low efficiency correlated with specific complexity range
        efficiency_issues = self._detect_efficiency_issues(sessions)
        if efficiency_issues:
            patterns.append(efficiency_issues)
            print(f"   ✓ Detected: {efficiency_issues['rationale']}")

        if not patterns:
            print("   ℹ️  No significant patterns detected")

        return patterns

    def _load_recent_sessions(self, days: int) -> List[Dict]:
        """Load session outcomes from last N days."""

        if not self.sessions_file.exists():
            return []

        cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
        sessions = []

        with open(self.sessions_file) as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                        if entry.get("ts", 0) >= cutoff:
                            sessions.append(entry)
                    except json.JSONDecodeError:
                        continue

        return sessions

    def _detect_overprovisioning(self, sessions: List[Dict]) -> Optional[Dict]:
        """Detect if we're consistently over-provisioning."""

        # Group sessions by complexity bins
        bins = {
            "low": [],      # 0.0-0.3
            "medium": [],   # 0.3-0.7
            "high": []      # 0.7-1.0
        }

        for s in sessions:
            c = s.get("complexity", 0.5)
            # Note: We need to load full session data to check actual model used
            # For now, use efficiency as proxy
            if c < 0.3:
                bins["low"].append(s)
            elif c < 0.7:
                bins["medium"].append(s)
            else:
                bins["high"].append(s)

        # Check if low-complexity sessions have low efficiency (over-provisioned)
        if len(bins["low"]) >= 10:
            low_eff_count = sum(
                1 for s in bins["low"]
                if s.get("model_efficiency", 1.0) < 0.7
            )

            over_prov_rate = low_eff_count / len(bins["low"])

            if over_prov_rate > 0.3:  # >30% over-provisioned
                return {
                    "type": "threshold_increase",
                    "target": "haiku",
                    "current_max": 0.30,
                    "proposed_max": 0.33,  # Increase Haiku threshold
                    "rationale": f"{low_eff_count}/{len(bins['low'])} low-complexity sessions over-provisioned",
                    "confidence": min(0.9, 0.6 + over_prov_rate),
                    "samples": len(bins["low"])
                }

        return None

    def _detect_haiku_struggles(self, sessions: List[Dict]) -> Optional[Dict]:
        """Detect if high-complexity sessions on Haiku are failing."""

        # Find sessions with complexity > 0.5 and low quality
        high_complexity_low_quality = [
            s for s in sessions
            if s.get("complexity", 0.5) > 0.5
            and s.get("quality", 3) < 3
            and s.get("outcome", "") in ["partial", "error"]
        ]

        if len(high_complexity_low_quality) >= 5:
            # Check if model efficiency is low (suggests wrong model)
            low_eff = sum(
                1 for s in high_complexity_low_quality
                if s.get("model_efficiency", 1.0) < 0.6
            )

            if low_eff / len(high_complexity_low_quality) > 0.5:
                return {
                    "type": "threshold_decrease",
                    "target": "haiku",
                    "current_max": 0.30,
                    "proposed_max": 0.27,  # Decrease Haiku threshold
                    "rationale": f"{low_eff}/{len(high_complexity_low_quality)} high-complexity sessions struggled",
                    "confidence": 0.75,
                    "samples": len(high_complexity_low_quality)
                }

        return None

    def _detect_opus_overuse(self, sessions: List[Dict]) -> Optional[Dict]:
        """Detect if Opus is being over-used for moderate complexity."""

        # Sessions with moderate complexity but optimal model is not Opus
        moderate_complexity = [
            s for s in sessions
            if 0.5 < s.get("complexity", 0.5) < 0.75
        ]

        if len(moderate_complexity) >= 10:
            # Check model efficiency
            over_prov = sum(
                1 for s in moderate_complexity
                if s.get("model_efficiency", 1.0) < 0.7
                and s.get("optimal_model", "sonnet") != "opus"
            )

            if over_prov / len(moderate_complexity) > 0.4:
                return {
                    "type": "threshold_increase",
                    "target": "sonnet",
                    "current_max": 0.70,
                    "proposed_max": 0.73,  # Increase Sonnet threshold
                    "rationale": f"{over_prov}/{len(moderate_complexity)} moderate-complexity sessions over-provisioned to Opus",
                    "confidence": 0.70,
                    "samples": len(moderate_complexity)
                }

        return None

    def _detect_efficiency_issues(self, sessions: List[Dict]) -> Optional[Dict]:
        """Detect systematic efficiency issues in specific complexity ranges."""

        # Group by complexity and calculate avg efficiency
        complexity_bins = defaultdict(list)

        for s in sessions:
            c = s.get("complexity", 0.5)
            eff = s.get("model_efficiency", 1.0)

            # Bin to nearest 0.1
            bin_key = round(c, 1)
            complexity_bins[bin_key].append(eff)

        # Find bins with consistently low efficiency
        problem_bins = []
        for bin_key, efficiencies in complexity_bins.items():
            if len(efficiencies) >= 5:
                avg_eff = sum(efficiencies) / len(efficiencies)
                if avg_eff < 0.65:
                    problem_bins.append((bin_key, avg_eff, len(efficiencies)))

        if problem_bins:
            # Take the worst bin
            worst_bin = min(problem_bins, key=lambda x: x[1])
            bin_complexity, avg_eff, count = worst_bin

            # Determine which threshold to adjust
            if bin_complexity < 0.3:
                target = "haiku"
                current = 0.30
                proposed = 0.32
            elif bin_complexity < 0.7:
                target = "sonnet"
                current = 0.70
                proposed = 0.68
            else:
                return None  # Opus threshold shouldn't change

            return {
                "type": "threshold_adjustment",
                "target": target,
                "current_max": current,
                "proposed_max": proposed,
                "rationale": f"Complexity ~{bin_complexity:.1f} has low efficiency ({avg_eff:.1%}, n={count})",
                "confidence": 0.65,
                "samples": count
            }

        return None

    def generate_baseline_updates(self, patterns: List[Dict]) -> List[Dict]:
        """Generate proposed baseline updates from patterns."""

        updates = []

        # Load current baselines
        if not self.baselines_file.exists():
            print(f"⚠️  Baselines file not found: {self.baselines_file}")
            return []

        baselines = json.loads(self.baselines_file.read_text())

        for pattern in patterns:
            model = pattern["target"]
            current = pattern["current_max"]
            proposed = pattern["proposed_max"]

            updates.append({
                "id": f"feedback-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{len(updates)+1:02d}",
                "type": "complexity_threshold",
                "model": model,
                "parameter": f"complexity_thresholds.{model}.range[1]",
                "current_value": current,
                "proposed_value": proposed,
                "change": proposed - current,
                "rationale": pattern["rationale"],
                "confidence": pattern["confidence"],
                "samples": pattern["samples"],
                "source": "session_analysis",
                "timestamp": datetime.now().isoformat()
            })

        return updates

    def apply_update(self, update: Dict, dry_run=False) -> bool:
        """Apply baseline update with lineage tracking."""

        if not self.baselines_file.exists():
            print(f"❌ Baselines file not found: {self.baselines_file}")
            return False

        baselines = json.loads(self.baselines_file.read_text())

        # Parse parameter path
        model = update["model"]

        # Update value
        if not dry_run:
            try:
                # Update the threshold
                if "complexity_thresholds" not in baselines:
                    baselines["complexity_thresholds"] = {}

                if model not in baselines["complexity_thresholds"]:
                    baselines["complexity_thresholds"][model] = {"range": [0.0, 0.3]}

                baselines["complexity_thresholds"][model]["range"][1] = update["proposed_value"]

                # Add to lineage
                if "feedback_lineage" not in baselines:
                    baselines["feedback_lineage"] = []

                baselines["feedback_lineage"].append({
                    "update_id": update["id"],
                    "applied": datetime.now().isoformat(),
                    "parameter": update["parameter"],
                    "old_value": update["current_value"],
                    "new_value": update["proposed_value"],
                    "change": update["change"],
                    "rationale": update["rationale"],
                    "confidence": update["confidence"],
                    "samples": update["samples"],
                    "source": "automated_feedback_loop"
                })

                baselines["last_updated"] = datetime.now().isoformat()
                baselines["version"] = baselines.get("version", "1.0.0")

                # Write back
                self.baselines_file.write_text(json.dumps(baselines, indent=2))

                print(f"✅ Applied update: {update['id']}")
                print(f"   {update['parameter']}: {update['current_value']:.3f} → {update['proposed_value']:.3f} "
                      f"({update['change']:+.3f})")

                return True

            except Exception as e:
                print(f"❌ Error applying update: {e}")
                return False
        else:
            print(f"🔍 [DRY RUN] Would apply: {update['id']}")
            print(f"   {update['parameter']}: {update['current_value']:.3f} → {update['proposed_value']:.3f} "
                  f"({update['change']:+.3f})")
            return True


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Routing Feedback Loop - Autonomous routing optimization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Detect patterns from last 30 days
  %(prog)s --detect --days 30

  # Generate update proposals
  %(prog)s --propose --days 30

  # Auto-apply high-confidence updates (>=75%%)
  %(prog)s --auto-apply --days 30

  # Dry-run mode (show what would happen)
  %(prog)s --auto-apply --dry-run --days 30
        """
    )

    parser.add_argument("--detect", action="store_true",
                       help="Detect routing patterns")
    parser.add_argument("--propose", action="store_true",
                       help="Generate update proposals")
    parser.add_argument("--auto-apply", action="store_true",
                       help="Auto-apply high-confidence updates")
    parser.add_argument("--dry-run", action="store_true",
                       help="Dry run (no changes)")
    parser.add_argument("--days", type=int, default=30,
                       help="Days of data to analyze (default: 30)")
    parser.add_argument("--output", help="Save results to JSON file")

    args = parser.parse_args()

    loop = RoutingFeedbackLoop()

    try:
        if args.detect:
            patterns = loop.detect_routing_patterns(args.days)

            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(patterns, f, indent=2)
                print(f"\n📄 Patterns saved to: {args.output}")

        elif args.propose:
            patterns = loop.detect_routing_patterns(args.days)
            updates = loop.generate_baseline_updates(patterns)

            if updates:
                print(f"\n📋 Generated {len(updates)} proposed updates:\n")
                for update in updates:
                    print(f"  {update['id']}:")
                    print(f"    Rationale: {update['rationale']}")
                    print(f"    Confidence: {update['confidence']:.1%} ({update['samples']} samples)")
                    print(f"    Change: {update['parameter']} = "
                          f"{update['current_value']:.3f} → {update['proposed_value']:.3f} "
                          f"({update['change']:+.3f})")
                    print()
            else:
                print("\n✋ No updates to propose")

            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(updates, f, indent=2)
                print(f"📄 Updates saved to: {args.output}")

        elif args.auto_apply:
            print(f"🤖 Running automated feedback loop...")
            print("=" * 70)

            patterns = loop.detect_routing_patterns(args.days)

            if not patterns:
                print("\n✋ No patterns detected - no updates to apply")
                sys.exit(0)

            updates = loop.generate_baseline_updates(patterns)
            high_conf = [u for u in updates if u["confidence"] >= loop.confidence_threshold]

            if high_conf:
                print(f"\n🤖 Auto-applying {len(high_conf)} high-confidence updates...\n")

                success_count = 0
                for update in high_conf:
                    if loop.apply_update(update, dry_run=args.dry_run):
                        success_count += 1

                print(f"\n✅ Applied {success_count}/{len(high_conf)} updates successfully")

                if args.dry_run:
                    print("   (DRY RUN - no actual changes made)")
            else:
                print(f"\n✋ No high-confidence updates to apply")
                print(f"   (Found {len(updates)} updates below {loop.confidence_threshold:.0%} confidence threshold)")

        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
