"""
ContrarianAgent - Devil's Advocate for ACE Consensus

The 7th agent that challenges consensus, identifies hidden assumptions,
proposes alternative interpretations, and flags overconfident conclusions.
Prevents groupthink and catches edge cases other agents miss.
"""

from typing import Dict, List, Optional
from . import SessionAnalysisAgent


class ContrarianAgent(SessionAnalysisAgent):
    """
    Devil's Advocate agent that challenges consensus.
    - Identifies hidden assumptions in other agents
    - Proposes alternative interpretations
    - Flags overconfident conclusions
    - Provides minority opinion when all agents agree
    """

    def __init__(self):
        super().__init__()
        self.name = "ContrarianAgent"
        self.weight = 0.12  # Lower weight, but meaningful voice

        # Thresholds for critique triggers
        self.overconfidence_threshold = 0.9
        self.groupthink_threshold = 0.95  # When agreement is too high
        self.low_evidence_threshold = 0.3

    def analyze(self, transcript: Dict, other_agent_results: Optional[List[Dict]] = None) -> Dict:
        """
        Critiques other agents' conclusions.

        Args:
            transcript: Session transcript data
            other_agent_results: Results from other 6 agents (optional)

        Returns:
            Dict with critiques, minority_opinion, assumption_risks
        """
        critiques = []
        assumption_risks = []

        if other_agent_results:
            # Challenge outcome consensus
            critiques.extend(self._challenge_outcome_consensus(other_agent_results))

            # Flag overconfident scores
            critiques.extend(self._flag_overconfidence(other_agent_results, transcript))

            # Identify hidden assumptions
            assumption_risks.extend(self._identify_assumptions(other_agent_results, transcript))

            # Check for missing considerations
            critiques.extend(self._check_missing_considerations(transcript, other_agent_results))

        # Generate alternative interpretations
        alternatives = self._generate_alternatives(transcript, other_agent_results or [])

        # Synthesize minority view
        minority_opinion = self._synthesize_minority_view(critiques, alternatives, transcript)

        # Calculate DQ score (lower validity since we're contrarian)
        validity, specificity, correctness = self._calculate_critique_dq(critiques, assumption_risks)

        return {
            "summary": f"Identified {len(critiques)} potential issues, {len(assumption_risks)} assumption risks",
            "dq_score": self._calculate_dq_score(validity, specificity, correctness),
            "confidence": self._calculate_confidence(critiques, assumption_risks),
            "data": {
                "critiques": critiques,
                "assumption_risks": assumption_risks,
                "alternatives": alternatives,
                "minority_opinion": minority_opinion,
                "critique_count": len(critiques),
                "risk_count": len(assumption_risks)
            }
        }

    def _challenge_outcome_consensus(self, other_results: List[Dict]) -> List[Dict]:
        """Challenge when all agents agree on outcome."""
        critiques = []

        # Extract outcomes from agents that report them
        outcomes = []
        for result in other_results:
            if isinstance(result, dict):
                outcome = result.get('outcome') or result.get('data', {}).get('outcome')
                if outcome:
                    outcomes.append(outcome)

        if len(outcomes) >= 3:  # Need at least 3 to detect consensus
            unique_outcomes = set(outcomes)
            if len(unique_outcomes) == 1:  # Full agreement
                consensus_outcome = outcomes[0]
                critiques.append({
                    "target": "outcome_consensus",
                    "severity": "medium",
                    "critique": f"Unanimous agreement on '{consensus_outcome}' may indicate groupthink",
                    "alternative": self._suggest_alternative_outcome(consensus_outcome),
                    "evidence": "All agents reporting same outcome without dissent"
                })

        return critiques

    def _flag_overconfidence(self, other_results: List[Dict], transcript: Dict) -> List[Dict]:
        """Flag agents with suspiciously high confidence."""
        critiques = []

        for result in other_results:
            if not isinstance(result, dict):
                continue

            agent_name = result.get('agent', result.get('name', 'unknown'))
            confidence = result.get('confidence', 0)

            if confidence > self.overconfidence_threshold:
                contrary_evidence = self._find_contrary_evidence(transcript, result)
                if contrary_evidence:
                    critiques.append({
                        "target": agent_name,
                        "severity": "low",
                        "critique": f"Confidence {confidence:.2f} may be overestimated",
                        "evidence": contrary_evidence,
                        "suggested_confidence": max(0.5, confidence - 0.15)
                    })

        return critiques

    def _identify_assumptions(self, other_results: List[Dict], transcript: Dict) -> List[Dict]:
        """Identify hidden assumptions in agent analyses."""
        assumptions = []

        # Check for assumptions about session completeness
        messages = transcript.get('messages', [])
        tools = transcript.get('tools', [])

        # Short session might not tell the full story
        if len(messages) < 10:
            assumptions.append({
                "assumption": "Session length indicates scope",
                "risk": "Short sessions may be efficient, not incomplete",
                "impact": "May misclassify as abandoned/partial"
            })

        # No commits doesn't mean no progress
        bash_tools = [t for t in tools if t.get('name') == 'Bash']
        git_commits = sum(1 for t in bash_tools
                        if 'git commit' in str(t.get('input', {}).get('command', '')))

        if git_commits == 0:
            edits = len([t for t in tools if t.get('name') in ['Edit', 'Write']])
            if edits > 0:
                assumptions.append({
                    "assumption": "Commits required for success",
                    "risk": f"Session made {edits} file changes without committing",
                    "impact": "May underestimate progress"
                })

        # Research sessions may have high value despite low visible activity
        reads = len([t for t in tools if t.get('name') == 'Read'])
        if reads > 5 and git_commits == 0 and len([t for t in tools if t.get('name') in ['Edit', 'Write']]) == 0:
            assumptions.append({
                "assumption": "Code changes indicate productivity",
                "risk": "Research/exploration sessions have different value metrics",
                "impact": "May classify valuable research as low productivity"
            })

        return assumptions

    def _check_missing_considerations(self, transcript: Dict, other_results: List[Dict]) -> List[Dict]:
        """Check if agents missed important considerations."""
        critiques = []

        messages = transcript.get('messages', [])
        tools = transcript.get('tools', [])
        errors = transcript.get('errors', [])

        # Check if errors were counted but not contextualized
        if errors:
            error_recovery = self._detect_error_recovery(transcript)
            if error_recovery:
                critiques.append({
                    "target": "error_analysis",
                    "severity": "medium",
                    "critique": "Errors were counted but successful recovery was not weighted",
                    "evidence": f"Recovered from {error_recovery['recovered']} of {error_recovery['total']} errors",
                    "alternative": "Consider error recovery rate, not just error count"
                })

        # Check for iteration patterns (multiple attempts = learning)
        iterations = self._detect_iteration_patterns(transcript)
        if iterations > 2:
            critiques.append({
                "target": "iteration_analysis",
                "severity": "low",
                "critique": f"Detected {iterations} iteration cycles - may indicate challenging but successful problem-solving",
                "evidence": "Multiple edit-test cycles observed",
                "alternative": "High iteration count can indicate thorough work, not struggle"
            })

        return critiques

    def _generate_alternatives(self, transcript: Dict, other_results: List[Dict]) -> List[Dict]:
        """Generate alternative interpretations of the session."""
        alternatives = []

        # Get consensus view
        consensus_outcome = None
        for result in other_results:
            if isinstance(result, dict):
                outcome = result.get('outcome') or result.get('data', {}).get('outcome')
                if outcome:
                    consensus_outcome = outcome
                    break

        if consensus_outcome:
            # Generate counter-interpretation
            alternatives.append({
                "consensus": consensus_outcome,
                "alternative": self._suggest_alternative_outcome(consensus_outcome),
                "reasoning": self._get_alternative_reasoning(consensus_outcome, transcript)
            })

        return alternatives

    def _synthesize_minority_view(self, critiques: List[Dict], alternatives: List[Dict],
                                   transcript: Dict) -> Optional[str]:
        """Synthesize a coherent minority opinion."""
        if not critiques and not alternatives:
            return None

        parts = []

        # Lead with main alternative view
        if alternatives:
            alt = alternatives[0]
            parts.append(f"Alternative view: Session could be '{alt['alternative']}' instead of '{alt['consensus']}'")
            if alt.get('reasoning'):
                parts.append(f"Reasoning: {alt['reasoning']}")

        # Add key critiques
        high_severity = [c for c in critiques if c.get('severity') in ['high', 'medium']]
        if high_severity:
            critique_summary = "; ".join([c['critique'] for c in high_severity[:2]])
            parts.append(f"Key concerns: {critique_summary}")

        return " | ".join(parts) if parts else None

    def _suggest_alternative_outcome(self, outcome: str) -> str:
        """Suggest an alternative outcome interpretation."""
        alternatives = {
            "success": "partial",  # Maybe not fully complete
            "partial": "success",  # Maybe more complete than recognized
            "error": "partial",    # Maybe recovered from errors
            "abandoned": "research",  # Maybe intentionally exploratory
            "research": "partial",  # Maybe had implementation goals
            "unknown": "research"   # Default to research for unclear
        }
        return alternatives.get(outcome, "partial")

    def _get_alternative_reasoning(self, outcome: str, transcript: Dict) -> str:
        """Get reasoning for alternative outcome."""
        messages = len(transcript.get('messages', []))
        tools = len(transcript.get('tools', []))

        reasoning_map = {
            "success": f"With {messages} messages and {tools} tool uses, some edge cases may remain untested",
            "partial": f"The {tools} tool uses suggest more completion than recognized",
            "error": "Errors may have been learning opportunities, not blockers",
            "abandoned": "Brief sessions can be efficient targeted fixes",
            "research": "Research sessions often include untracked implementation planning"
        }
        return reasoning_map.get(outcome, "Consider alternative interpretations")

    def _find_contrary_evidence(self, transcript: Dict, agent_result: Dict) -> Optional[str]:
        """Find evidence that contradicts an agent's conclusion."""
        agent_name = agent_result.get('agent', agent_result.get('name', ''))
        data = agent_result.get('data', {})

        # Look for contrary signals based on agent type
        if 'outcome' in agent_name.lower():
            # For outcome detector, check for mixed signals
            errors = len(transcript.get('errors', []))
            commits = self._count_commits(transcript)
            if commits > 0 and errors > 0:
                return f"Mixed signals: {commits} commits but {errors} errors"

        elif 'quality' in agent_name.lower():
            # For quality scorer, check if complexity was considered
            complexity = self._estimate_complexity(transcript)
            if complexity > 0.7:
                return "High complexity tasks may appear lower quality despite good work"

        elif 'productivity' in agent_name.lower():
            # For productivity, check research value
            reads = len([t for t in transcript.get('tools', []) if t.get('name') == 'Read'])
            if reads > 10:
                return f"High read count ({reads}) suggests valuable research not reflected in productivity"

        return None

    def _detect_error_recovery(self, transcript: Dict) -> Optional[Dict]:
        """Detect if errors were recovered from."""
        tools = transcript.get('tools', [])
        errors = transcript.get('errors', [])

        if not errors:
            return None

        # Simple heuristic: if there are tools after errors, some recovery happened
        error_indices = []
        for i, tool in enumerate(tools):
            if tool.get('error'):
                error_indices.append(i)

        recovered = 0
        for idx in error_indices:
            # Check if successful tools followed the error
            following_tools = tools[idx+1:idx+3]
            if any(not t.get('error') for t in following_tools):
                recovered += 1

        return {
            "total": len(error_indices),
            "recovered": recovered
        }

    def _detect_iteration_patterns(self, transcript: Dict) -> int:
        """Detect edit-test-edit cycles."""
        tools = transcript.get('tools', [])
        iterations = 0
        in_edit_phase = False

        for tool in tools:
            name = tool.get('name', '')
            if name in ['Edit', 'Write']:
                in_edit_phase = True
            elif name == 'Bash' and in_edit_phase:
                # Possible test/run after edit
                cmd = str(tool.get('input', {}).get('command', '')).lower()
                if any(kw in cmd for kw in ['test', 'run', 'build', 'npm', 'python', 'node']):
                    iterations += 1
                    in_edit_phase = False

        return iterations

    def _count_commits(self, transcript: Dict) -> int:
        """Count git commits in session."""
        tools = transcript.get('tools', [])
        commits = 0
        for tool in tools:
            if tool.get('name') == 'Bash':
                cmd = str(tool.get('input', {}).get('command', ''))
                if 'git commit' in cmd and '--amend' not in cmd:
                    commits += 1
        return commits

    def _estimate_complexity(self, transcript: Dict) -> float:
        """Estimate session complexity."""
        tools = transcript.get('tools', [])
        messages = transcript.get('messages', [])

        # Simple complexity heuristic
        tool_count = len(tools)
        message_count = len(messages)
        unique_tools = len(set(t.get('name', '') for t in tools))

        complexity = min(1.0, (tool_count / 50) * 0.4 + (message_count / 100) * 0.3 + (unique_tools / 10) * 0.3)
        return complexity

    def _calculate_critique_dq(self, critiques: List[Dict], assumptions: List[Dict]) -> tuple:
        """Calculate DQ scores for critique quality."""
        critique_count = len(critiques)
        assumption_count = len(assumptions)

        # Validity: Do we have substantive critiques?
        validity = min(0.8, 0.5 + critique_count * 0.1 + assumption_count * 0.1)

        # Specificity: Are critiques targeted and actionable?
        actionable = sum(1 for c in critiques if c.get('alternative') or c.get('suggested_confidence'))
        specificity = min(0.85, 0.5 + actionable * 0.15)

        # Correctness: Hard to verify for contrarian views, keep moderate
        correctness = 0.65

        return validity, specificity, correctness

    def _calculate_confidence(self, critiques: List[Dict], assumptions: List[Dict]) -> float:
        """Calculate confidence in contrarian analysis."""
        # Contrarian agent is deliberately less confident
        base_confidence = 0.55

        # More evidence increases confidence
        high_severity = sum(1 for c in critiques if c.get('severity') in ['high', 'medium'])
        base_confidence += high_severity * 0.05

        # Cap at 0.75 - never overconfident as the contrarian
        return min(0.75, base_confidence)


# Export
__all__ = ['ContrarianAgent']
