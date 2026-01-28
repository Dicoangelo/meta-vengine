#!/usr/bin/env python3
"""
Autonomous Session Analysis System

Uses 6 agents + ACE consensus to analyze Claude Code sessions.
Automatically evaluates session quality, outcome, model efficiency, and more.

The meta-learning loop that closes itself.
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Add agents directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Agent imports
from agents.outcome_detector import OutcomeDetectorAgent
from agents.quality_scorer import QualityScorerAgent
from agents.complexity_analyzer import ComplexityAnalyzerAgent
from agents.model_efficiency import ModelEfficiencyAgent
from agents.productivity_analyzer import ProductivityAnalyzerAgent
from agents.routing_quality import RoutingQualityAgent
from ace_consensus import ACEConsensus
from session_summarizer import SessionSummarizer


class PostSessionAnalyzer:
    """
    Main orchestrator for autonomous session analysis.

    Coordinates 6 analysis agents + ACE consensus to evaluate sessions.
    """

    def __init__(self):
        self.sessions_dir = Path.home() / ".claude/projects"
        self.data_dir = Path.home() / ".claude/data"
        self.kernel_dir = Path.home() / ".claude/kernel"

        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize agents
        self.agents = {
            "outcome": OutcomeDetectorAgent(),
            "quality": QualityScorerAgent(),
            "complexity": ComplexityAnalyzerAgent(),
            "model_efficiency": ModelEfficiencyAgent(),
            "productivity": ProductivityAnalyzerAgent(),
            "routing_quality": RoutingQualityAgent()
        }

        # Initialize ACE
        self.ace = ACEConsensus()

        # Initialize summarizer
        self.summarizer = SessionSummarizer()

    def load_session_transcript(self, session_id: str) -> Dict:
        """Load and parse session JSONL file."""

        # Find session file
        session_file = self._find_session_file(session_id)
        if not session_file:
            raise FileNotFoundError(f"Session {session_id} not found in {self.sessions_dir}")

        # Parse JSONL
        events = []
        with open(session_file) as f:
            for line in f:
                if line.strip():
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue  # Skip malformed lines

        if not events:
            raise ValueError(f"No valid events found in session {session_id}")

        # Extract components
        transcript = {
            "session_id": session_id,
            "events": events,
            "messages": self._extract_messages(events),
            "tools": self._extract_tool_calls(events),
            "costs": self._extract_costs(events),
            "errors": self._extract_errors(events),
            "metadata": self._extract_metadata(events)
        }

        return transcript

    def analyze_session(self, session_id: str) -> Dict:
        """Run full 6-agent analysis with ACE consensus."""

        print(f"🔬 Analyzing session: {session_id}")

        try:
            # Load transcript
            transcript = self.load_session_transcript(session_id)
            print(f"   📄 Loaded transcript: {len(transcript['events'])} events, "
                  f"{len(transcript['messages'])} messages, {len(transcript['tools'])} tools")

            # Run each agent
            agent_results = {}
            for name, agent in self.agents.items():
                try:
                    print(f"   🤖 Running {name} agent...")
                    result = agent.analyze(transcript)
                    agent_results[name] = result
                    print(f"      ✓ {result.get('summary', 'Done')}")
                except Exception as e:
                    print(f"      ❌ Error in {name} agent: {e}")
                    # Use default result
                    agent_results[name] = {
                        "summary": f"Error: {e}",
                        "dq_score": {"validity": 0.5, "specificity": 0.5, "correctness": 0.5},
                        "confidence": 0.3,
                        "data": {}
                    }

            # Apply ACE consensus
            print(f"   🧠 Applying ACE consensus...")
            consensus = self.ace.synthesize(agent_results, transcript)
            print(f"      ✓ Consensus reached (confidence: {consensus['confidence']:.2f})")

            # Generate session summary
            print(f"   📝 Generating session summary...")
            summary = self.summarizer.generate_summary(transcript, consensus)
            print(f"      ✓ Summary: {summary['title'][:60]}...")

            # Save summary file
            session_file = self._find_session_file(session_id)
            if session_file:
                summary_file = self.summarizer.save_summary_file(session_file, summary)
                print(f"      ✓ Saved summary: {summary_file.name}")

            # Build final analysis
            analysis = {
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "outcome": consensus["outcome"],
                "quality": consensus["quality"],
                "complexity": consensus["complexity"],
                "model_efficiency": consensus["model_efficiency"],
                "dq_score": consensus["dq_score"],
                "agent_results": agent_results,
                "consensus_confidence": consensus["confidence"],
                "optimal_model": consensus.get("optimal_model", "unknown"),
                "recommendations": self._generate_recommendations(consensus, transcript, agent_results),
                "summary": summary
            }

            # Write to session-outcomes.jsonl
            self._save_analysis(analysis)

            print(f"   ✅ Analysis complete: {analysis['outcome']} (quality: {analysis['quality']}/5, "
                  f"efficiency: {analysis['model_efficiency']:.1%})")

            return analysis

        except Exception as e:
            print(f"   ❌ Error analyzing session: {e}")
            raise

    def _find_session_file(self, session_id: str) -> Optional[Path]:
        """Find session JSONL file by session ID (handles both old and new naming schemes)."""

        # Extract short session ID (first 8 chars) for renamed files
        short_id = session_id[:8] if len(session_id) > 8 else session_id

        # Direct match (old naming scheme)
        direct = self.sessions_dir / f"{session_id}.jsonl"
        if direct.exists():
            return direct

        # Search in project subdirectories
        for project_dir in self.sessions_dir.glob("*"):
            if project_dir.is_dir():
                # Try exact match
                session_file = project_dir / f"{session_id}.jsonl"
                if session_file.exists():
                    return session_file

                # Try new naming scheme: *_id-{short_id}.jsonl
                pattern = f"*_id-{short_id}.jsonl"
                matches = list(project_dir.glob(pattern))
                if matches:
                    return matches[0]

        # Last resort: search all .jsonl files for session ID in filename
        for jsonl_file in self.sessions_dir.rglob("*.jsonl"):
            if "/subagents/" not in str(jsonl_file) and session_id in jsonl_file.name:
                return jsonl_file

        return None

    def _find_all_sessions(self) -> List[Path]:
        """Find all session JSONL files (excluding subagents)."""

        sessions = []

        # Direct files in sessions_dir
        sessions.extend(self.sessions_dir.glob("*.jsonl"))

        # Files in subdirectories
        for project_dir in self.sessions_dir.glob("*"):
            if project_dir.is_dir():
                sessions.extend(project_dir.glob("*.jsonl"))

        # Filter out subagent files (Task tool spawned agents)
        sessions = [s for s in sessions if "/subagents/" not in str(s)]

        return sorted(sessions, key=lambda p: p.stat().st_mtime, reverse=True)

    def _extract_messages(self, events: List[Dict]) -> List[Dict]:
        """Extract messages from events (handles multiple formats)."""

        messages = []

        for event in events:
            role = None
            content = None
            timestamp = event.get("timestamp", 0)

            # Format 1: type="message" or event="message"
            if event.get("type") == "message" or event.get("event") == "message":
                msg_data = event.get("data", event)
                role = msg_data.get("role")
                content = msg_data.get("content")

            # Format 2: type="user" with message.role and message.content
            elif event.get("type") == "user":
                msg = event.get("message", {})
                role = msg.get("role", "user")
                content = msg.get("content")

            # Format 3: message.role="assistant" directly
            elif "message" in event and event["message"].get("role") == "assistant":
                msg = event["message"]
                role = "assistant"
                content = msg.get("content")

            if role and content:
                # Handle content as list or string
                if isinstance(content, list):
                    # Extract text from content blocks
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            text_parts.append(block)
                    content = "\n".join(text_parts) if text_parts else str(content)

                messages.append({
                    "role": role,
                    "content": content,
                    "timestamp": timestamp
                })

        return messages

    def _extract_tool_calls(self, events: List[Dict]) -> List[Dict]:
        """Extract tool calls from events (handles multiple formats)."""

        tools = []

        for event in events:
            timestamp = event.get("timestamp", 0)

            # Format 1: type="tool_use" or event="tool_use"
            if event.get("type") == "tool_use" or event.get("event") == "tool_use":
                tool_data = event.get("data", event)
                tools.append({
                    "name": tool_data.get("name", tool_data.get("tool")),
                    "input": tool_data.get("input", {}),
                    "timestamp": timestamp
                })

            # Format 2: message.content contains tool_use blocks
            elif "message" in event:
                msg = event["message"]
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tools.append({
                                "name": block.get("name"),
                                "input": block.get("input", {}),
                                "timestamp": timestamp
                            })

        return tools

    def _extract_costs(self, events: List[Dict]) -> Dict:
        """Extract cost information from events."""

        costs = {
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0
        }

        for event in events:
            usage = event.get("usage", event.get("data", {}).get("usage", {}))

            if usage:
                costs["input_tokens"] += usage.get("input_tokens", 0)
                costs["output_tokens"] += usage.get("output_tokens", 0)
                costs["total_tokens"] = costs["input_tokens"] + costs["output_tokens"]

        return costs

    def _extract_errors(self, events: List[Dict]) -> List[Dict]:
        """Extract errors from events."""

        errors = []

        for event in events:
            if event.get("type") == "error" or event.get("event") == "error":
                errors.append({
                    "message": event.get("message", event.get("data", {}).get("message", "Unknown error")),
                    "timestamp": event.get("timestamp", 0)
                })

        return errors

    def _extract_metadata(self, events: List[Dict]) -> Dict:
        """Extract session metadata."""

        metadata = {
            "start_time": None,
            "end_time": None,
            "model": None
        }

        if events:
            # First event timestamp
            metadata["start_time"] = events[0].get("timestamp", 0)
            # Last event timestamp
            metadata["end_time"] = events[-1].get("timestamp", 0)

            # Find model from session_start event
            for event in events:
                if event.get("type") == "session_start" or event.get("event") == "session_start":
                    metadata["model"] = event.get("model", event.get("data", {}).get("model"))
                    break

        return metadata

    def _generate_recommendations(self, consensus: Dict, transcript: Dict, agent_results: Dict) -> List[str]:
        """Generate actionable recommendations."""

        recs = []

        # Model efficiency recommendations
        if consensus["model_efficiency"] < 0.7:
            optimal = consensus.get("optimal_model", "unknown")
            actual = transcript["metadata"].get("model", "unknown")
            if optimal != "unknown" and actual != "unknown":
                recs.append(f"Consider using {optimal} instead of {actual} for similar sessions")

        # Complexity-based routing recommendations
        if consensus["complexity"] > 0.7:
            if "haiku" in str(transcript["metadata"].get("model", "")).lower():
                recs.append("High complexity session on Haiku - consider auto-routing to Sonnet/Opus")

        # Quality improvement recommendations
        if consensus["quality"] < 3:
            error_count = len(transcript.get("errors", []))
            if error_count > 5:
                recs.append(f"Low quality session with {error_count} errors - review error patterns")

        # Productivity recommendations
        if "productivity" in agent_results:
            prod_data = agent_results["productivity"].get("data", {})
            read_write_ratio = prod_data.get("read_write_ratio", 1.0)

            if read_write_ratio > 5.0:
                recs.append("High exploration/implementation ratio - consider more focused queries")

        # Routing quality recommendations
        if "routing_quality" in agent_results:
            routing_data = agent_results["routing_quality"].get("data", {})
            issues = routing_data.get("issues", [])

            for issue in issues:
                recs.append(f"Routing: {issue}")

        return recs

    def _save_analysis(self, analysis: Dict):
        """Save analysis to session-outcomes.jsonl."""

        output_file = self.data_dir / "session-outcomes.jsonl"

        # Create structured entry
        entry = {
            "ts": int(datetime.now().timestamp()),
            "event": "session_analysis_complete",
            "session_id": analysis["session_id"],
            "outcome": analysis["outcome"],
            "quality": analysis["quality"],
            "complexity": analysis["complexity"],
            "model_efficiency": analysis["model_efficiency"],
            "dq_score": analysis["dq_score"],
            "confidence": analysis["consensus_confidence"],
            "optimal_model": analysis.get("optimal_model", "unknown"),
            "auto_analyzed": True
        }

        # Add summary fields if available
        if "summary" in analysis:
            summary = analysis["summary"]
            entry["title"] = summary.get("title", "")
            entry["intent"] = summary.get("intent", "")
            entry["summary_text"] = summary.get("summary", "")
            entry["achievements"] = summary.get("achievements", [])
            entry["blockers"] = summary.get("blockers", [])
            entry["files_modified"] = summary.get("files_modified", [])

        with open(output_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Autonomous Session Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze single session
  %(prog)s --session-id abc123

  # Analyze 10 most recent sessions
  %(prog)s --recent 10

  # Analyze all sessions (use with caution!)
  %(prog)s --all

  # Output to JSON file
  %(prog)s --session-id abc123 --output /tmp/analysis.json
        """
    )

    parser.add_argument("--session-id", help="Specific session ID to analyze")
    parser.add_argument("--all", action="store_true", help="Analyze all sessions")
    parser.add_argument("--recent", type=int, help="Analyze N most recent sessions")
    parser.add_argument("--output", help="Save detailed results to JSON file")

    args = parser.parse_args()

    analyzer = PostSessionAnalyzer()

    try:
        if args.session_id:
            # Single session analysis
            analysis = analyzer.analyze_session(args.session_id)

            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(analysis, f, indent=2)
                print(f"\n📄 Detailed analysis saved to: {args.output}")

        elif args.recent:
            # Analyze N recent sessions
            print(f"🚀 Analyzing {args.recent} most recent sessions...")
            print("=" * 70)

            sessions = analyzer._find_all_sessions()[:args.recent]
            results = []

            for i, session_file in enumerate(sessions, 1):
                session_id = session_file.stem
                print(f"\n[{i}/{len(sessions)}]")

                try:
                    analysis = analyzer.analyze_session(session_id)
                    results.append(analysis)
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    continue

            print(f"\n✅ Analysis complete: {len(results)}/{len(sessions)} sessions analyzed")

            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(results, f, indent=2)
                print(f"📄 Detailed results saved to: {args.output}")

        elif args.all:
            print("⚠️  Analyzing ALL sessions - this may take a while...")
            print("=" * 70)

            sessions = analyzer._find_all_sessions()
            total = len(sessions)
            print(f"🚀 Found {total} sessions to analyze\n")

            results = []

            for i, session_file in enumerate(sessions, 1):
                session_id = session_file.stem
                print(f"\n[{i}/{total}]")

                try:
                    analysis = analyzer.analyze_session(session_id)
                    results.append(analysis)
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    continue

            print(f"\n✅ Bulk analysis complete: {len(results)}/{total} sessions analyzed")

            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(results, f, indent=2)
                print(f"📄 Detailed results saved to: {args.output}")

        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
