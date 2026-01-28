"""
OutcomeDetectorAgent - Detects session outcome

Analyzes git commits, errors, and completion signals to determine:
- success: Task completed successfully
- partial: Some progress but incomplete
- error: Blocked by errors
- research: Exploratory/research session
- abandoned: User quit early
"""

import re
from typing import Dict, List
from . import SessionAnalysisAgent


class OutcomeDetectorAgent(SessionAnalysisAgent):
    """Detects session outcome from git commits, errors, completion signals."""

    def __init__(self):
        super().__init__()
        self.completion_signals = [
            "done", "completed", "finished", "success", "working",
            "deployed", "implemented", "fixed", "resolved", "merged"
        ]
        self.error_signals = [
            "error", "failed", "failure", "exception", "blocked",
            "cannot", "unable to", "doesn't work", "not working"
        ]
        self.research_signals = [
            "exploring", "investigating", "researching", "checking",
            "looking at", "analyzing", "reviewing", "understanding"
        ]

    def analyze(self, transcript: Dict) -> Dict:
        """Detect session outcome from multiple signals."""

        # Count git commits
        commits = self._count_git_commits(transcript)

        # Count errors
        errors = len(transcript.get("errors", []))
        total_tools = len(transcript.get("tools", []))
        error_rate = errors / max(total_tools, 1)

        # Check completion signals
        completion_found = self._find_signals(transcript, self.completion_signals)
        error_found = self._find_signals(transcript, self.error_signals)
        research_found = self._find_signals(transcript, self.research_signals)

        # Check file operations (writes indicate progress)
        writes = len(self._extract_tool_calls(transcript, "Write"))
        edits = len(self._extract_tool_calls(transcript, "Edit"))
        file_changes = writes + edits

        # Check message count (abandoned if very short)
        messages = transcript.get("messages", [])
        message_count = len(messages)

        # Determine outcome
        outcome, validity, specificity, correctness = self._determine_outcome(
            commits=commits,
            error_rate=error_rate,
            completion_found=completion_found,
            error_found=error_found,
            research_found=research_found,
            file_changes=file_changes,
            message_count=message_count
        )

        return {
            "summary": f"Outcome: {outcome}",
            "outcome": outcome,
            "dq_score": self._calculate_dq_score(validity, specificity, correctness),
            "confidence": self._calculate_confidence(commits, error_rate, completion_found),
            "data": {
                "commits": commits,
                "error_rate": error_rate,
                "file_changes": file_changes,
                "message_count": message_count,
                "signals": {
                    "completion": completion_found,
                    "error": error_found,
                    "research": research_found
                }
            }
        }

    def _determine_outcome(
        self,
        commits: int,
        error_rate: float,
        completion_found: bool,
        error_found: bool,
        research_found: bool,
        file_changes: int,
        message_count: int
    ):
        """Determine outcome based on multiple signals."""

        # Abandoned: Very short session with no progress
        if message_count < 5 and commits == 0 and file_changes == 0:
            return "abandoned", 0.85, 0.9, 0.8

        # Success: Commits + low errors + completion signals
        if commits > 0 and error_rate < 0.2 and completion_found:
            return "success", 0.95, 0.9, 0.95

        # Success: Commits + file changes + low errors
        if commits > 0 and file_changes >= 3 and error_rate < 0.3:
            return "success", 0.90, 0.85, 0.90

        # Partial: Some commits but high error rate or no completion
        if commits > 0 and (error_rate >= 0.2 or not completion_found):
            return "partial", 0.80, 0.75, 0.70

        # Partial: File changes but no commits
        if file_changes >= 3 and commits == 0:
            return "partial", 0.75, 0.70, 0.65

        # Error: High error rate and error signals
        if error_rate > 0.5 and error_found:
            return "error", 0.85, 0.80, 0.75

        # Error: High error rate alone
        if error_rate > 0.6:
            return "error", 0.80, 0.75, 0.70

        # Research: Research signals + no commits + decent length
        if research_found and commits == 0 and message_count >= 10:
            return "research", 0.75, 0.70, 0.65

        # Research: Long session with reads but no writes
        reads = file_changes == 0 and message_count >= 15
        if reads:
            return "research", 0.70, 0.65, 0.60

        # Default to partial if unclear
        return "partial", 0.60, 0.55, 0.50

    def _count_git_commits(self, transcript: Dict) -> int:
        """Count git commits from Bash tool calls."""
        git_commits = 0
        bash_calls = self._extract_tool_calls(transcript, "Bash")

        for tool in bash_calls:
            cmd = tool.get("input", {}).get("command", "")
            if isinstance(cmd, str) and "git commit" in cmd and "--amend" not in cmd:
                git_commits += 1

        return git_commits

    def _find_signals(self, transcript: Dict, signal_words: List[str]) -> bool:
        """Look for signal words in assistant messages."""
        messages = self._extract_messages(transcript, "assistant")

        for msg in messages:
            content = str(msg.get("content", "")).lower()
            if any(signal in content for signal in signal_words):
                return True

        return False

    def _calculate_confidence(self, commits: int, error_rate: float, completion_found: bool) -> float:
        """Calculate confidence in outcome detection."""
        # Higher confidence when we have clear signals
        confidence = 0.5

        # Commits are strong signal
        if commits > 0:
            confidence += 0.2

        # Completion signals boost confidence
        if completion_found:
            confidence += 0.15

        # Clear error pattern boosts confidence
        if error_rate > 0.5 or error_rate < 0.1:
            confidence += 0.1

        # Cap at 0.95
        return min(0.95, confidence)
