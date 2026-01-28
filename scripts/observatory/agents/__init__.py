"""
Session Analysis Agents

Multi-agent system for autonomous Claude Code session analysis.
Uses ACE (Adaptive Consensus Engine) + DQ scoring.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class SessionAnalysisAgent(ABC):
    """
    Base class for session analysis agents.

    Each agent analyzes a specific aspect of a Claude Code session
    and returns DQ-scored results for ACE consensus.
    """

    def __init__(self):
        self.name = self.__class__.__name__
        self.weight = 1.0  # Default ACE weight

    @abstractmethod
    def analyze(self, transcript: Dict) -> Dict:
        """
        Analyze session transcript and return structured results.

        Args:
            transcript: Parsed session data containing:
                - session_id: str
                - events: List[Dict]
                - messages: List[Dict]
                - tools: List[Dict]
                - costs: Dict
                - errors: List[Dict]
                - metadata: Dict

        Returns:
            {
                "summary": "Brief summary",
                "dq_score": {
                    "validity": 0.0-1.0,
                    "specificity": 0.0-1.0,
                    "correctness": 0.0-1.0
                },
                "confidence": 0.0-1.0,
                "data": {...}  # Agent-specific data
            }
        """
        pass

    def _extract_tool_calls(self, transcript: Dict, tool_name: Optional[str] = None) -> List[Dict]:
        """Extract tool calls, optionally filtered by tool name."""
        tools = transcript.get("tools", [])
        if tool_name:
            return [t for t in tools if t.get("name") == tool_name]
        return tools

    def _extract_messages(self, transcript: Dict, role: Optional[str] = None) -> List[Dict]:
        """Extract messages, optionally filtered by role."""
        messages = transcript.get("messages", [])
        if role:
            return [m for m in messages if m.get("role") == role]
        return messages

    def _calculate_dq_score(self, validity: float, specificity: float, correctness: float) -> Dict:
        """Helper to create DQ score dict."""
        return {
            "validity": max(0.0, min(1.0, validity)),
            "specificity": max(0.0, min(1.0, specificity)),
            "correctness": max(0.0, min(1.0, correctness))
        }


from .contrarian_agent import ContrarianAgent

__all__ = ['SessionAnalysisAgent', 'ContrarianAgent']
