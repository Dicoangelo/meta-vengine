"""
ComplexityAnalyzerAgent - Analyzes session complexity

Calculates average complexity score (0-1) across all user queries in session.
Uses similar logic to dq-scorer.js complexity analyzer.
"""

import re
from typing import Dict, List
from . import SessionAnalysisAgent


class ComplexityAnalyzerAgent(SessionAnalysisAgent):
    """Analyzes session complexity from user queries."""

    def __init__(self):
        super().__init__()

        # Complexity indicators (similar to complexity-analyzer.js)
        self.architecture_keywords = [
            "architecture", "design", "system", "infrastructure", "framework",
            "pattern", "refactor", "restructure", "organize", "modular"
        ]

        self.multi_step_keywords = [
            "implement", "create", "build", "develop", "integrate",
            "migrate", "upgrade", "deploy", "setup", "configure"
        ]

        self.research_keywords = [
            "analyze", "investigate", "explore", "research", "understand",
            "explain", "how does", "why", "compare", "evaluate"
        ]

        self.simple_keywords = [
            "fix", "bug", "error", "typo", "update", "change",
            "add", "remove", "delete", "rename"
        ]

    def analyze(self, transcript: Dict) -> Dict:
        """Calculate average session complexity."""

        # Extract user queries
        user_messages = self._extract_messages(transcript, "user")

        if not user_messages:
            return self._default_result()

        # Calculate complexity for each query
        complexities = []
        for msg in user_messages:
            content = str(msg.get("content", ""))
            if content and len(content.strip()) > 0:
                complexity = self._calculate_query_complexity(content)
                complexities.append(complexity)

        if not complexities:
            return self._default_result()

        # Average complexity
        avg_complexity = sum(complexities) / len(complexities)

        # Complexity distribution
        distribution = {
            "low": sum(1 for c in complexities if c < 0.3),
            "medium": sum(1 for c in complexities if 0.3 <= c < 0.7),
            "high": sum(1 for c in complexities if c >= 0.7)
        }

        # DQ components
        validity = 0.85  # High validity for complexity analysis
        specificity = 0.7 + (len(complexities) / max(len(complexities) + 10, 1) * 0.2)
        correctness = 0.8

        return {
            "summary": f"Complexity: {avg_complexity:.2f}",
            "complexity": avg_complexity,
            "dq_score": self._calculate_dq_score(validity, specificity, correctness),
            "confidence": self._calculate_confidence(len(complexities)),
            "data": {
                "complexity": avg_complexity,
                "query_count": len(complexities),
                "distribution": distribution,
                "min": min(complexities),
                "max": max(complexities)
            }
        }

    def _calculate_query_complexity(self, query: str) -> float:
        """Calculate complexity score for a single query (0-1)."""

        query_lower = query.lower()
        query_len = len(query.split())

        score = 0.0
        factors = []

        # Factor 1: Length (longer queries tend to be more complex)
        if query_len > 100:
            score += 0.2
            factors.append("long_query")
        elif query_len > 50:
            score += 0.1
        elif query_len < 10:
            score -= 0.1  # Very short queries often simple

        # Factor 2: Architecture keywords
        arch_count = sum(1 for kw in self.architecture_keywords if kw in query_lower)
        if arch_count >= 2:
            score += 0.3
            factors.append("architecture")
        elif arch_count >= 1:
            score += 0.15

        # Factor 3: Multi-step indicators
        multi_count = sum(1 for kw in self.multi_step_keywords if kw in query_lower)
        if multi_count >= 2:
            score += 0.2
            factors.append("multi_step")
        elif multi_count >= 1:
            score += 0.1

        # Factor 4: Research/analysis
        research_count = sum(1 for kw in self.research_keywords if kw in query_lower)
        if research_count >= 2:
            score += 0.15
            factors.append("research")
        elif research_count >= 1:
            score += 0.08

        # Factor 5: Simple task indicators (reduce score)
        simple_count = sum(1 for kw in self.simple_keywords if kw in query_lower)
        if simple_count >= 1 and not factors:  # Only if no other factors
            score -= 0.15
            factors.append("simple")

        # Factor 6: Multiple files/components mentioned
        if self._count_file_references(query) >= 3:
            score += 0.15
            factors.append("multi_file")
        elif self._count_file_references(query) >= 2:
            score += 0.08

        # Factor 7: Technical depth (code blocks, technical terms)
        if "```" in query or "function" in query_lower or "class" in query_lower:
            score += 0.1
            factors.append("technical")

        # Factor 8: Question complexity
        question_marks = query.count("?")
        if question_marks >= 2:
            score += 0.1
            factors.append("multi_question")

        # Normalize to 0-1
        normalized = max(0.0, min(1.0, 0.3 + score))  # Base 0.3, adjust from there

        return normalized

    def _count_file_references(self, text: str) -> int:
        """Count file path references in text."""
        # Simple heuristic: look for common file patterns
        patterns = [
            r'\w+\.\w+',  # filename.ext
            r'[\w/]+/[\w/]+',  # path/to/file
            r'\.[\w]+/',  # ./relative/path
        ]

        count = 0
        for pattern in patterns:
            matches = re.findall(pattern, text)
            # Filter out common false positives
            valid = [m for m in matches if not any(x in m for x in ['.com', '.org', 'http', '@'])]
            count += len(valid)

        return min(count, 10)  # Cap at 10 to avoid over-counting

    def _calculate_confidence(self, query_count: int) -> float:
        """Calculate confidence based on sample size."""
        # More queries = higher confidence
        if query_count >= 10:
            return 0.90
        elif query_count >= 5:
            return 0.80
        elif query_count >= 2:
            return 0.70
        else:
            return 0.60

    def _default_result(self) -> Dict:
        """Return default result when no queries found."""
        return {
            "summary": "Complexity: 0.50 (no queries)",
            "complexity": 0.5,
            "dq_score": self._calculate_dq_score(0.5, 0.5, 0.5),
            "confidence": 0.3,
            "data": {
                "complexity": 0.5,
                "query_count": 0,
                "distribution": {"low": 0, "medium": 0, "high": 0}
            }
        }
