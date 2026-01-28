#!/usr/bin/env python3
"""
Meta-Vengine Background Agent Daemon

Runs autonomous agents while you sleep:
- Daily Brief Agent: Morning summary at 8am
- Research Crawler Agent: Checks arXiv every 6 hours
- Pattern Predictor Agent: Predicts tomorrow's patterns at 11pm
"""

import json
import os
import sys
import time
import signal
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

# Try to import schedule, fallback to simple timing
try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False

# Paths
HOME = Path.home()
CLAUDE_DIR = HOME / '.claude'
BRIEFS_DIR = CLAUDE_DIR / 'briefs'
RESEARCH_DIR = CLAUDE_DIR / 'research'
LOGS_DIR = CLAUDE_DIR / 'logs'
DATA_DIR = CLAUDE_DIR / 'data'


class BackgroundAgentRunner:
    """
    Background agent daemon - runs autonomous agents on schedule.
    """

    def __init__(self):
        # Ensure directories exist
        BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
        RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.running = True
        self.log_file = LOGS_DIR / 'daemon.log'

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle graceful shutdown."""
        self.log("Received shutdown signal, stopping...")
        self.running = False

    def log(self, message: str):
        """Log message to file and stdout."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)

        with open(self.log_file, 'a') as f:
            f.write(log_entry + '\n')

    def _notify(self, title: str, message: str):
        """Send desktop notification (macOS)."""
        try:
            subprocess.run([
                'osascript', '-e',
                f'display notification "{message}" with title "{title}"'
            ], capture_output=True, timeout=5)
        except Exception:
            pass  # Notifications are optional

    def _load_json(self, path: Path, default: Any = None) -> Any:
        """Safely load JSON file."""
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        return default if default is not None else {}

    def _save_json(self, path: Path, data: Any):
        """Save JSON file."""
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    # =========================================================================
    # DAILY BRIEF AGENT
    # =========================================================================

    def daily_brief_agent(self):
        """Generate morning brief with yesterday's summary."""
        self.log("Running Daily Brief Agent...")

        try:
            # Gather yesterday's stats
            stats = self._get_daily_stats(days=1)

            # Get relevant context from memory
            relevant_context = self._get_relevant_memory_context()

            # Get pending tasks
            pending_tasks = self._get_pending_tasks()

            # Generate recommendations
            recommendations = self._generate_recommendations(stats)

            # Create brief
            today = datetime.now().strftime('%Y-%m-%d')
            brief = self._format_daily_brief(today, stats, relevant_context, pending_tasks, recommendations)

            # Save brief
            brief_file = BRIEFS_DIR / f"brief-{today}.md"
            with open(brief_file, 'w') as f:
                f.write(brief)

            self.log(f"Daily brief saved to: {brief_file}")
            self._notify("Daily Brief Ready", f"Check {brief_file.name}")

        except Exception as e:
            self.log(f"Daily Brief Agent error: {e}")

    def _get_daily_stats(self, days: int = 1) -> Dict:
        """Get statistics from recent sessions."""
        stats = {
            "sessions": 0,
            "messages": 0,
            "tools": 0,
            "dominant_pattern": "unknown",
            "quality_avg": 0,
            "cost_estimate": 0
        }

        # Load session outcomes
        outcomes_file = DATA_DIR / 'session-outcomes.jsonl'
        if outcomes_file.exists():
            cutoff = datetime.now() - timedelta(days=days)
            sessions = []

            with open(outcomes_file) as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        ts = entry.get('ts', entry.get('timestamp', 0))
                        if isinstance(ts, str):
                            ts = datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()
                        if ts > cutoff.timestamp():
                            sessions.append(entry)
                    except json.JSONDecodeError:
                        continue

            stats["sessions"] = len(sessions)

            if sessions:
                outcomes = [s.get('outcome', 'unknown') for s in sessions]
                stats["dominant_pattern"] = max(set(outcomes), key=outcomes.count)

                qualities = [s.get('quality', 3) for s in sessions if s.get('quality')]
                if qualities:
                    stats["quality_avg"] = sum(qualities) / len(qualities)

        # Load tool usage
        tool_file = DATA_DIR / 'tool-success.jsonl'
        if tool_file.exists():
            cutoff = datetime.now() - timedelta(days=days)
            tool_count = 0

            with open(tool_file) as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        ts = entry.get('ts', 0)
                        if ts > cutoff.timestamp():
                            tool_count += 1
                    except json.JSONDecodeError:
                        continue

            stats["tools"] = tool_count

        return stats

    def _get_relevant_memory_context(self) -> List[str]:
        """Get relevant context from vector memory."""
        try:
            # Import and query memory API
            sys.path.insert(0, str(CLAUDE_DIR / 'kernel'))
            from memory_api import VectorMemory

            mem = VectorMemory()
            results = mem.query("recent work patterns productivity", limit=5)

            return [r.get('content', '') for r in results]
        except Exception:
            return []

    def _get_pending_tasks(self) -> List[str]:
        """Get pending tasks from task queue."""
        task_file = CLAUDE_DIR / 'kernel/task-queue.json'
        if task_file.exists():
            data = self._load_json(task_file, {"tasks": []})
            pending = [t.get('description', t.get('content', ''))
                      for t in data.get('tasks', [])
                      if t.get('status') == 'pending']
            return pending[:5]  # Top 5
        return []

    def _generate_recommendations(self, stats: Dict) -> List[str]:
        """Generate recommendations based on stats."""
        recommendations = []

        quality = stats.get('quality_avg', 3)
        if quality < 3:
            recommendations.append("Consider using more specific queries to improve session quality")

        sessions = stats.get('sessions', 0)
        if sessions > 10:
            recommendations.append("High activity yesterday - ensure tasks are properly prioritized")
        elif sessions == 0:
            recommendations.append("No sessions yesterday - review pending tasks")

        dominant = stats.get('dominant_pattern', 'unknown')
        if dominant == 'error':
            recommendations.append("Multiple error sessions detected - consider debugging environment setup")
        elif dominant == 'research':
            recommendations.append("Research-heavy day - consider scheduling implementation time")

        if not recommendations:
            recommendations.append("Session patterns look healthy - continue current workflow")

        return recommendations

    def _format_daily_brief(self, date: str, stats: Dict, context: List[str],
                           tasks: List[str], recommendations: List[str]) -> str:
        """Format the daily brief as markdown."""
        brief = f"""# Daily Brief - {date}

## Yesterday's Stats
- Sessions: {stats.get('sessions', 0)}
- Tool Uses: {stats.get('tools', 0)}
- Top Pattern: {stats.get('dominant_pattern', 'unknown')}
- Avg Quality: {stats.get('quality_avg', 0):.1f}/5

## Relevant Context
"""
        if context:
            for item in context:
                brief += f"- {item}\n"
        else:
            brief += "- No specific context loaded\n"

        brief += "\n## Pending Tasks\n"
        if tasks:
            for task in tasks:
                brief += f"- [ ] {task}\n"
        else:
            brief += "- No pending tasks in queue\n"

        brief += "\n## Recommendations\n"
        for rec in recommendations:
            brief += f"- {rec}\n"

        brief += f"\n---\n*Generated at {datetime.now().strftime('%H:%M:%S')} by Meta-Vengine Daemon*\n"

        return brief

    # =========================================================================
    # RESEARCH CRAWLER AGENT
    # =========================================================================

    def research_crawler_agent(self):
        """Check arXiv for relevant papers."""
        self.log("Running Research Crawler Agent...")

        try:
            topics = [
                "multi-agent systems LLM",
                "LLM routing optimization",
                "agentic AI self-improvement",
                "autonomous AI agents"
            ]

            # Use arXiv API if available
            new_papers = self._check_arxiv(topics)

            if new_papers:
                # Save to research queue
                queue_file = RESEARCH_DIR / 'paper-queue.jsonl'
                with open(queue_file, 'a') as f:
                    for paper in new_papers:
                        f.write(json.dumps(paper) + '\n')

                self.log(f"Found {len(new_papers)} new papers")
                self._notify("New Papers Found", f"{len(new_papers)} papers queued for review")
            else:
                self.log("No new papers found")

        except Exception as e:
            self.log(f"Research Crawler Agent error: {e}")

    def _check_arxiv(self, topics: List[str]) -> List[Dict]:
        """Check arXiv for new papers (simplified - returns empty for now)."""
        # In a full implementation, this would query the arXiv API
        # For now, we just log the intent and return empty
        self.log(f"Would search arXiv for: {', '.join(topics[:2])}")

        # Check if we have an arxiv-sync script
        arxiv_sync = HOME / 'researchgravity/arxiv-sync.py'
        if arxiv_sync.exists():
            try:
                result = subprocess.run(
                    ['python3', str(arxiv_sync), '--quiet', '--check-only'],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0 and result.stdout:
                    # Parse output for paper count
                    self.log(f"arXiv sync output: {result.stdout[:100]}")
            except (subprocess.TimeoutExpired, Exception):
                pass

        return []

    # =========================================================================
    # PATTERN PREDICTOR AGENT
    # =========================================================================

    def pattern_predictor_agent(self):
        """Predict tomorrow's likely patterns and pre-cache context."""
        self.log("Running Pattern Predictor Agent...")

        try:
            # Analyze recent patterns
            patterns = self._analyze_recent_patterns()

            # Predict tomorrow
            prediction = self._predict_tomorrow(patterns)

            # Pre-cache relevant context
            self._precache_context(prediction.get('likely_patterns', []))

            # Save prediction
            pred_file = DATA_DIR / 'pattern-prediction.json'
            self._save_json(pred_file, {
                "generated": datetime.now().isoformat(),
                "prediction": prediction
            })

            self.log(f"Prediction saved: {prediction.get('likely_patterns', [])}")

        except Exception as e:
            self.log(f"Pattern Predictor Agent error: {e}")

    def _analyze_recent_patterns(self) -> Dict:
        """Analyze patterns from recent sessions."""
        patterns = {"by_day": {}, "by_hour": {}, "by_type": {}}

        # Load detected patterns
        pattern_file = CLAUDE_DIR / 'kernel/detected-patterns.json'
        if pattern_file.exists():
            data = self._load_json(pattern_file, {})
            patterns.update(data)

        return patterns

    def _predict_tomorrow(self, patterns: Dict) -> Dict:
        """Predict tomorrow's session patterns."""
        tomorrow = datetime.now() + timedelta(days=1)
        day_name = tomorrow.strftime('%A').lower()

        # Simple prediction based on day of week patterns
        by_day = patterns.get('by_day', {})
        predicted_types = by_day.get(day_name, ['general'])

        # Get typical productivity hours
        by_hour = patterns.get('by_hour', {})
        peak_hours = sorted(by_hour.items(), key=lambda x: x[1], reverse=True)[:3]

        return {
            "date": tomorrow.strftime('%Y-%m-%d'),
            "day": day_name,
            "likely_patterns": predicted_types if isinstance(predicted_types, list) else [predicted_types],
            "peak_hours": [h[0] for h in peak_hours] if peak_hours else ["14", "15", "16"]
        }

    def _precache_context(self, patterns: List[str]):
        """Pre-cache context packs for predicted patterns."""
        # Map patterns to context packs
        pack_mapping = {
            "research": "research-workflow",
            "coding": "os-app-architecture",
            "debugging": "debugging",
            "dashboard": "dashboard-development",
            "career": "career-coaching"
        }

        packs_to_load = []
        for pattern in patterns:
            if pattern.lower() in pack_mapping:
                packs_to_load.append(pack_mapping[pattern.lower()])

        if packs_to_load:
            self.log(f"Pre-caching context packs: {packs_to_load}")
            # In full implementation, would actually pre-load these

    # =========================================================================
    # MAIN DAEMON LOOP
    # =========================================================================

    def run_once(self, agent: str):
        """Run a single agent manually."""
        agents = {
            "brief": self.daily_brief_agent,
            "research": self.research_crawler_agent,
            "pattern": self.pattern_predictor_agent
        }

        if agent in agents:
            agents[agent]()
        else:
            print(f"Unknown agent: {agent}")
            print(f"Available agents: {', '.join(agents.keys())}")

    def run(self):
        """Main daemon loop."""
        self.log("Background Agent Daemon starting...")

        if SCHEDULE_AVAILABLE:
            # Schedule agents
            schedule.every().day.at("08:00").do(self.daily_brief_agent)
            schedule.every(6).hours.do(self.research_crawler_agent)
            schedule.every().day.at("23:00").do(self.pattern_predictor_agent)

            self.log("Agents scheduled:")
            self.log("  - Daily Brief: 08:00")
            self.log("  - Research Crawler: every 6 hours")
            self.log("  - Pattern Predictor: 23:00")

            while self.running:
                schedule.run_pending()
                time.sleep(60)

        else:
            # Simple timing fallback
            self.log("Schedule module not available, using simple timing")
            last_brief = None
            last_research = None
            last_pattern = None

            while self.running:
                now = datetime.now()

                # Daily brief at 8am
                if now.hour == 8 and last_brief != now.date():
                    self.daily_brief_agent()
                    last_brief = now.date()

                # Research every 6 hours
                if last_research is None or (now - last_research).seconds >= 21600:
                    self.research_crawler_agent()
                    last_research = now

                # Pattern prediction at 11pm
                if now.hour == 23 and last_pattern != now.date():
                    self.pattern_predictor_agent()
                    last_pattern = now.date()

                time.sleep(60)

        self.log("Background Agent Daemon stopped")


def main():
    if len(sys.argv) < 2:
        print("Meta-Vengine Background Agent Daemon")
        print("")
        print("Usage: agent-runner.py <command>")
        print("")
        print("Commands:")
        print("  start              Start daemon (foreground)")
        print("  run <agent>        Run single agent (brief|research|pattern)")
        print("  test               Test all agents once")
        print("")
        return

    cmd = sys.argv[1]
    runner = BackgroundAgentRunner()

    if cmd == "start":
        runner.run()
    elif cmd == "run" and len(sys.argv) > 2:
        runner.run_once(sys.argv[2])
    elif cmd == "test":
        print("Testing all agents...")
        runner.daily_brief_agent()
        runner.research_crawler_agent()
        runner.pattern_predictor_agent()
        print("Done!")
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
