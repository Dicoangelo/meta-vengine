#!/usr/bin/env python3
"""
Session Summarizer

Generates high-level context summaries for each session based on:
- User queries and intent
- Actions taken and files modified
- Outcome and achievements
- Key blockers or issues
"""

import json
from typing import Dict, List
from pathlib import Path


class SessionSummarizer:
    """Generates comprehensive session summaries."""

    def __init__(self):
        self.max_summary_length = 500

    def generate_summary(self, transcript: Dict, analysis: Dict) -> Dict:
        """
        Generate comprehensive session summary.

        Args:
            transcript: Raw session transcript
            analysis: Analysis results from agents

        Returns:
            {
                "title": "Brief session title",
                "summary": "High-level description",
                "intent": "User's primary intent",
                "achievements": ["List of achievements"],
                "blockers": ["List of blockers if any"],
                "files_modified": ["List of files"],
                "key_actions": ["List of key actions"],
                "outcome_description": "Outcome with context"
            }
        """

        # Extract components
        user_queries = self._extract_user_queries(transcript)
        tools_used = self._analyze_tools_used(transcript)
        files_modified = self._extract_files_modified(transcript)

        # Generate title
        title = self._generate_title(user_queries, analysis)

        # Generate intent
        intent = self._determine_intent(user_queries)

        # Generate achievements based on outcome
        achievements = self._identify_achievements(
            analysis,
            tools_used,
            files_modified
        )

        # Identify blockers
        blockers = self._identify_blockers(transcript, analysis)

        # Generate key actions
        key_actions = self._generate_key_actions(tools_used, files_modified)

        # Generate outcome description
        outcome_desc = self._describe_outcome(analysis, achievements, blockers)

        # Generate full summary
        summary = self._generate_full_summary(
            title=title,
            intent=intent,
            achievements=achievements,
            blockers=blockers,
            outcome=analysis.get("outcome", "unknown")
        )

        return {
            "title": title,
            "summary": summary,
            "intent": intent,
            "achievements": achievements,
            "blockers": blockers,
            "files_modified": files_modified,
            "key_actions": key_actions,
            "outcome_description": outcome_desc
        }

    def _extract_user_queries(self, transcript: Dict) -> List[str]:
        """Extract all user queries from session."""
        queries = []

        for msg in transcript.get("messages", []):
            if msg.get("role") == "user":
                content = str(msg.get("content", "")).strip()
                if content and len(content) > 3:
                    queries.append(content)

        return queries

    def _analyze_tools_used(self, transcript: Dict) -> Dict:
        """Analyze which tools were used and how often."""
        tools = {}

        for tool in transcript.get("tools", []):
            tool_name = tool.get("name", "unknown")
            tools[tool_name] = tools.get(tool_name, 0) + 1

        return tools

    def _extract_files_modified(self, transcript: Dict) -> List[str]:
        """Extract files that were modified (written or edited)."""
        files = set()

        for tool in transcript.get("tools", []):
            tool_name = tool.get("name")
            tool_input = tool.get("input", {})

            if tool_name in ["Write", "Edit"]:
                file_path = tool_input.get("file_path")
                if file_path:
                    # Store just filename or relative path
                    path = Path(file_path)
                    files.add(path.name if path.name else str(file_path))

        return sorted(list(files))

    def _generate_title(self, queries: List[str], analysis: Dict) -> str:
        """Generate brief title for session."""

        if not queries:
            outcome = analysis.get("outcome", "unknown")
            return f"Session ended {outcome}"

        # Use first query as basis for title
        first_query = queries[0]

        # Extract key verbs/actions
        action_words = [
            "implement", "create", "build", "fix", "update",
            "add", "remove", "refactor", "analyze", "debug",
            "explore", "setup", "configure", "deploy"
        ]

        for action in action_words:
            if action in first_query.lower():
                # Find what follows the action
                idx = first_query.lower().find(action)
                remaining = first_query[idx:].split('.')[0].split(',')[0]

                # Truncate to reasonable length
                if len(remaining) > 60:
                    remaining = remaining[:60] + "..."

                return remaining.capitalize()

        # Fallback: use first sentence
        first_sentence = first_query.split('.')[0].split('\n')[0]
        if len(first_sentence) > 60:
            first_sentence = first_sentence[:60] + "..."

        return first_sentence.capitalize()

    def _determine_intent(self, queries: List[str]) -> str:
        """Determine user's primary intent from queries."""

        if not queries:
            return "No clear intent (session abandoned early)"

        combined = " ".join(queries).lower()

        # Intent patterns
        if any(word in combined for word in ["implement", "create", "build", "add new"]):
            return "Implement new feature or component"
        elif any(word in combined for word in ["fix", "bug", "error", "issue"]):
            return "Fix bug or resolve issue"
        elif any(word in combined for word in ["refactor", "restructure", "reorganize"]):
            return "Refactor or improve code structure"
        elif any(word in combined for word in ["analyze", "explore", "understand", "explain"]):
            return "Analyze or understand codebase"
        elif any(word in combined for word in ["update", "modify", "change"]):
            return "Update or modify existing code"
        elif any(word in combined for word in ["setup", "configure", "initialize"]):
            return "Setup or configuration"
        elif any(word in combined for word in ["deploy", "release", "publish"]):
            return "Deploy or release"
        elif any(word in combined for word in ["test", "verify", "validate"]):
            return "Testing or validation"
        else:
            return "General development task"

    def _identify_achievements(
        self,
        analysis: Dict,
        tools: Dict,
        files: List[str]
    ) -> List[str]:
        """Identify what was achieved in the session."""

        achievements = []
        outcome = analysis.get("outcome", "unknown")
        quality = analysis.get("quality", 1)

        # Based on outcome
        if outcome == "success":
            if files:
                achievements.append(f"Modified {len(files)} file(s)")

            writes = tools.get("Write", 0)
            edits = tools.get("Edit", 0)

            if writes > 0:
                achievements.append(f"Created {writes} new file(s)")
            if edits > 0:
                achievements.append(f"Edited {edits} existing file(s)")

            if quality >= 4:
                achievements.append("High quality implementation")

        elif outcome == "partial":
            achievements.append("Made partial progress")
            if files:
                achievements.append(f"Modified {len(files)} file(s)")

        elif outcome == "research":
            reads = tools.get("Read", 0)
            if reads > 0:
                achievements.append(f"Explored {reads} file(s)")

            greps = tools.get("Grep", 0)
            if greps > 0:
                achievements.append(f"Searched codebase ({greps} searches)")

        # Tool-based achievements
        bash = tools.get("Bash", 0)
        if bash > 0 and outcome != "error":
            achievements.append("Executed system commands")

        if not achievements:
            achievements.append("No significant changes made")

        return achievements

    def _identify_blockers(self, transcript: Dict, analysis: Dict) -> List[str]:
        """Identify blockers or issues encountered."""

        blockers = []
        errors = transcript.get("errors", [])
        outcome = analysis.get("outcome", "unknown")

        # Errors encountered
        if len(errors) > 5:
            blockers.append(f"Encountered {len(errors)} errors")
        elif len(errors) > 0:
            blockers.append(f"Hit {len(errors)} error(s)")

        # Outcome-based blockers
        if outcome == "error":
            blockers.append("Session blocked by errors")
        elif outcome == "abandoned":
            blockers.append("Session ended prematurely")

        # Quality-based
        quality = analysis.get("quality", 3)
        if quality <= 2 and outcome != "abandoned":
            blockers.append("Low productivity/quality")

        return blockers

    def _generate_key_actions(self, tools: Dict, files: List[str]) -> List[str]:
        """Generate list of key actions taken."""

        actions = []

        # File operations
        if tools.get("Write", 0) > 0:
            actions.append(f"Created {tools['Write']} file(s)")
        if tools.get("Edit", 0) > 0:
            actions.append(f"Edited {tools['Edit']} file(s)")
        if tools.get("Read", 0) > 0:
            actions.append(f"Read {tools['Read']} file(s)")

        # Search operations
        if tools.get("Grep", 0) > 0:
            actions.append(f"Searched code ({tools['Grep']} searches)")
        if tools.get("Glob", 0) > 0:
            actions.append(f"Found files ({tools['Glob']} patterns)")

        # System operations
        if tools.get("Bash", 0) > 0:
            actions.append(f"Ran {tools['Bash']} command(s)")

        # Task spawning
        if tools.get("Task", 0) > 0:
            actions.append(f"Spawned {tools['Task']} sub-agent(s)")

        if not actions:
            actions.append("No tool operations performed")

        return actions

    def _describe_outcome(
        self,
        analysis: Dict,
        achievements: List[str],
        blockers: List[str]
    ) -> str:
        """Generate descriptive outcome text."""

        outcome = analysis.get("outcome", "unknown")
        quality = analysis.get("quality", 1)

        if outcome == "success":
            desc = f"Session completed successfully with quality {quality}/5. "
            if achievements:
                desc += f"Achievements: {', '.join(achievements)}."

        elif outcome == "partial":
            desc = f"Session partially completed (quality {quality}/5). "
            if achievements:
                desc += f"Progress made: {', '.join(achievements)}. "
            if blockers:
                desc += f"Blockers: {', '.join(blockers)}."

        elif outcome == "error":
            desc = f"Session encountered errors (quality {quality}/5). "
            if blockers:
                desc += f"Issues: {', '.join(blockers)}."

        elif outcome == "research":
            desc = "Research/exploration session. "
            if achievements:
                desc += f"Activity: {', '.join(achievements)}."

        elif outcome == "abandoned":
            desc = "Session ended early with minimal activity. "
            if blockers:
                desc += f"Reason: {', '.join(blockers)}."

        else:
            desc = f"Session outcome: {outcome}."

        return desc

    def _generate_full_summary(
        self,
        title: str,
        intent: str,
        achievements: List[str],
        blockers: List[str],
        outcome: str
    ) -> str:
        """Generate comprehensive summary text."""

        parts = []

        # Title/Intent
        parts.append(f"{title}.")
        parts.append(f"Intent: {intent}.")

        # Outcome
        parts.append(f"Outcome: {outcome.capitalize()}.")

        # Achievements
        if achievements:
            parts.append(f"Achievements: {'; '.join(achievements)}.")

        # Blockers
        if blockers:
            parts.append(f"Blockers: {'; '.join(blockers)}.")

        summary = " ".join(parts)

        # Truncate if too long
        if len(summary) > self.max_summary_length:
            summary = summary[:self.max_summary_length - 3] + "..."

        return summary

    def save_summary_file(self, session_file: Path, summary: Dict):
        """Save summary as .summary.md file alongside session."""

        summary_file = session_file.with_suffix('.summary.md')

        content = f"""# Session Summary

**Title:** {summary['title']}

**Intent:** {summary['intent']}

**Outcome:** {summary['outcome_description']}

## Summary
{summary['summary']}

## Achievements
{chr(10).join(f'- {a}' for a in summary['achievements']) if summary['achievements'] else '- None'}

## Blockers
{chr(10).join(f'- {b}' for b in summary['blockers']) if summary['blockers'] else '- None'}

## Files Modified
{chr(10).join(f'- {f}' for f in summary['files_modified']) if summary['files_modified'] else '- None'}

## Key Actions
{chr(10).join(f'- {a}' for a in summary['key_actions']) if summary['key_actions'] else '- None'}
"""

        with open(summary_file, 'w') as f:
            f.write(content)

        return summary_file


def main():
    """Test summary generation on a session."""
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python3 session_summarizer.py <session_file.jsonl>")
        sys.exit(1)

    session_file = Path(sys.argv[1])

    if not session_file.exists():
        print(f"Error: File not found: {session_file}")
        sys.exit(1)

    # Load session (simplified)
    with open(session_file) as f:
        events = [json.loads(line) for line in f if line.strip()]

    transcript = {
        "events": events,
        "messages": [],
        "tools": [],
        "errors": []
    }

    # Mock analysis
    analysis = {
        "outcome": "success",
        "quality": 4,
        "complexity": 0.65
    }

    # Generate summary
    summarizer = SessionSummarizer()
    summary = summarizer.generate_summary(transcript, analysis)

    print("=" * 70)
    print(f"Title: {summary['title']}")
    print(f"Intent: {summary['intent']}")
    print()
    print(f"Summary: {summary['summary']}")
    print()
    print("Achievements:")
    for achievement in summary['achievements']:
        print(f"  - {achievement}")
    print()
    if summary['blockers']:
        print("Blockers:")
        for blocker in summary['blockers']:
            print(f"  - {blocker}")

    # Save summary file
    summary_file = summarizer.save_summary_file(session_file, summary)
    print()
    print(f"Summary saved to: {summary_file}")


if __name__ == "__main__":
    main()
