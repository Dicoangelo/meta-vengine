#!/usr/bin/env python3
"""
Supermemory Learning Extractor - Extract learnings from session outcomes

Categorizes learnings as:
- breakthrough: Major discoveries or insights
- mistake: Lessons from errors
- blocker_solved: Solutions to blocking issues
- optimization: Performance or efficiency improvements
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage.index_db import MemoryDB


DATA_DIR = Path.home() / ".claude" / "data"


# Learning category detection patterns
CATEGORY_PATTERNS = {
    'breakthrough': [
        r'discover(ed|y)?',
        r'breakthrough',
        r'insight',
        r'realize[d]?',
        r'finally understood',
        r'key (finding|insight)',
        r'major progress',
    ],
    'mistake': [
        r'mistake',
        r'wrong',
        r'error',
        r'shouldn\'?t have',
        r'lesson learned',
        r'next time',
        r'avoid',
    ],
    'blocker_solved': [
        r'fix(ed)?',
        r'resolv(ed|e)',
        r'solved',
        r'unblock(ed)?',
        r'work(s|ed) now',
        r'finally (got|working)',
        r'solution',
    ],
    'optimization': [
        r'optimiz(ed|ation)?',
        r'faster',
        r'efficient',
        r'improv(ed|ement)',
        r'refactor',
        r'clean(ed)? up',
        r'reduced',
    ],
    'feature': [
        r'implement(ed)?',
        r'add(ed)?',
        r'creat(ed|e)',
        r'built',
        r'new feature',
        r'feature complete',
    ],
    'architecture': [
        r'architect(ure)?',
        r'design(ed)?',
        r'pattern',
        r'structure',
        r'system',
        r'refactor',
    ],
}


class LearningExtractor:
    """Extract and categorize learnings from session data."""

    def __init__(self):
        self.db = MemoryDB()

    def extract_from_outcomes(self, min_quality: float = 3.0) -> list[dict]:
        """
        Extract learnings from session outcomes.

        Args:
            min_quality: Minimum quality score to consider

        Returns:
            List of extracted learnings
        """
        learnings = []
        outcomes_path = DATA_DIR / "session-outcomes.jsonl"

        if not outcomes_path.exists():
            return learnings

        for line in outcomes_path.read_text().split('\n'):
            if not line.strip():
                continue

            try:
                record = json.loads(line)

                # Filter by outcome and quality
                if record.get('outcome') not in ['success', 'partial']:
                    continue
                if record.get('quality', 0) < min_quality:
                    continue

                # Extract learning
                learning = self._extract_learning(record)
                if learning:
                    learnings.append(learning)

            except json.JSONDecodeError:
                continue

        return learnings

    def _extract_learning(self, record: dict) -> Optional[dict]:
        """Extract a learning from a session record."""
        title = record.get('title', '')
        intent = record.get('intent', '')

        # Skip warmup sessions
        if 'warmup' in title.lower():
            return None

        # Build content
        content = title[:100]
        if intent and intent != title:
            content = f"{title[:60]} - {intent[:60]}"

        # Detect category
        category = self._detect_category(content)

        # Detect project
        project = self._detect_project(content + ' ' + record.get('session_id', ''))

        learning = {
            'content': content,
            'category': category,
            'project': project,
            'session_id': record.get('session_id'),
            'date': record.get('date'),
            'quality': record.get('quality'),
            'outcome': record.get('outcome'),
        }

        return learning

    def _detect_category(self, text: str) -> str:
        """Detect learning category from text."""
        text_lower = text.lower()

        # Check each category's patterns
        scores = {}
        for category, patterns in CATEGORY_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    score += 1
            if score > 0:
                scores[category] = score

        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]

        return 'general'

    def _detect_project(self, text: str) -> str:
        """Detect project from text."""
        text_lower = text.lower()

        if 'os-app' in text_lower or 'agentic' in text_lower:
            return 'os-app'
        if 'career' in text_lower:
            return 'career'
        if 'research' in text_lower:
            return 'research'
        if 'routing' in text_lower or '.claude' in text_lower:
            return 'claude-system'

        return 'general'

    def save_learnings(self, learnings: list[dict]) -> int:
        """Save extracted learnings to database."""
        count = 0
        for learning in learnings:
            self.db.add_learning(
                content=learning['content'],
                category=learning.get('category'),
                session_id=learning.get('session_id'),
                project=learning.get('project'),
                quality=learning.get('quality'),
                date=learning.get('date'),
            )
            count += 1
        return count

    def extract_and_save(self, min_quality: float = 3.0) -> int:
        """Extract learnings and save to database."""
        learnings = self.extract_from_outcomes(min_quality)
        return self.save_learnings(learnings)

    def get_learnings_by_category(self, category: str, limit: int = 20) -> list[dict]:
        """Get learnings filtered by category."""
        return self.db.get_learnings(category=category, limit=limit)

    def get_project_learnings(self, project: str, limit: int = 20) -> list[dict]:
        """Get learnings for a specific project."""
        return self.db.get_learnings(project=project, limit=limit)

    def extract_from_text(self, text: str) -> list[dict]:
        """
        Extract learnings from arbitrary text (e.g., notes, transcripts).

        Args:
            text: Text to extract from

        Returns:
            List of potential learnings
        """
        learnings = []

        # Look for learning indicators
        indicators = [
            r'learned that',
            r'discovered that',
            r'realized that',
            r'found out',
            r'key insight:?',
            r'important:?',
            r'note:?',
            r'takeaway:?',
        ]

        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            for indicator in indicators:
                if re.search(indicator, line.lower()):
                    # Extract the learning
                    content = re.sub(indicator, '', line, flags=re.IGNORECASE).strip()
                    if len(content) > 10:
                        learnings.append({
                            'content': content[:200],
                            'category': self._detect_category(content),
                            'project': self._detect_project(content),
                        })
                    break

        return learnings
