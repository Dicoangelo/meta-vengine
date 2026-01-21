#!/usr/bin/env python3
"""
Supermemory Session Injector - Memory injection at session start

Injects relevant context into new sessions:
- Project-specific learnings (semantic match)
- Recent error solutions
- Due spaced repetition items
- Relevant knowledge
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage.index_db import MemoryDB
from core.search_engine import SearchEngine
from core.spaced_repetition import SpacedRepetition
from aggregators.project_aggregator import ProjectAggregator


DATA_DIR = Path.home() / ".claude" / "data"
CONTEXT_FILE = DATA_DIR / "session-context.md"


# Project keywords for semantic querying
PROJECT_QUERIES = {
    'os-app': 'agentic kernel react zustand 3D visualization multi-agent',
    'career': 'career coaching AI agents resume job application',
    'research': 'research workflow papers arxiv sessions tracking',
    'claude-system': 'routing system observatory ACE agents hooks meta-analyzer',
    'metaventions': 'metaventions landing page AI platform',
    'general': 'recent work patterns productivity Claude development',
}


class SessionInjector:
    """Inject relevant memory context into sessions."""

    def __init__(self):
        self.db = MemoryDB()
        self.search = SearchEngine()
        self.sr = SpacedRepetition()
        self.aggregator = ProjectAggregator()

    def get_injection_context(self, project: Optional[str] = None) -> str:
        """
        Generate context to inject into session.

        Args:
            project: Override project detection

        Returns:
            Formatted context as markdown
        """
        # Detect project if not provided
        if not project:
            project = self._detect_project()

        sections = []

        # 1. Project-specific learnings
        learnings = self._get_relevant_learnings(project)
        if learnings:
            sections.append(self._format_learnings(learnings))

        # 2. Recent error solutions
        errors = self._get_recent_error_context(project)
        if errors:
            sections.append(self._format_errors(errors))

        # 3. Due spaced repetition items
        reviews = self.sr.get_due_items(limit=3)
        if reviews:
            sections.append(self._format_reviews(reviews))

        # 4. Relevant knowledge snippets
        knowledge = self._get_relevant_knowledge(project)
        if knowledge:
            sections.append(self._format_knowledge(knowledge))

        if not sections:
            return ""

        # Combine sections
        header = f"## Relevant Context (from Memory)\n\n_Project: {project}_\n"
        return header + "\n---\n".join(sections)

    def inject_to_file(self, project: Optional[str] = None) -> Optional[Path]:
        """
        Write injection context to file.

        Args:
            project: Override project detection

        Returns:
            Path to context file if written
        """
        context = self.get_injection_context(project)

        if not context:
            return None

        CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONTEXT_FILE.write_text(context)
        return CONTEXT_FILE

    def _detect_project(self) -> str:
        """Detect project from current working directory."""
        cwd = os.getcwd().lower()

        if 'os-app' in cwd:
            return 'os-app'
        if 'career' in cwd:
            return 'career'
        if 'research' in cwd:
            return 'research'
        if '.claude' in cwd:
            return 'claude-system'
        if 'metaventions' in cwd:
            return 'metaventions'

        return 'general'

    def _get_relevant_learnings(self, project: str) -> list[dict]:
        """Get learnings relevant to the project."""
        learnings = []

        # Get project-specific learnings
        project_learnings = self.db.get_learnings(project=project, limit=5)
        learnings.extend(project_learnings)

        # Also do semantic search for related content
        query = PROJECT_QUERIES.get(project, PROJECT_QUERIES['general'])
        search_results = self.search.search(query, limit=3, source='learning')

        for r in search_results:
            if r['id'] not in [l['id'] for l in learnings]:
                learnings.append({
                    'content': r.get('content', ''),
                    'category': 'related',
                    'date': r.get('date', ''),
                })

        return learnings[:7]

    def _get_recent_error_context(self, project: str) -> list[dict]:
        """Get recent error patterns relevant to project."""
        # Get top error patterns
        patterns = self.db.get_top_error_patterns(limit=10)

        # Filter to relevant ones
        relevant = []
        for p in patterns:
            # Check if has solution
            if p.get('solution'):
                relevant.append(p)
            elif p['count'] >= 3:  # Or common enough
                relevant.append(p)

        return relevant[:5]

    def _get_relevant_knowledge(self, project: str) -> list[dict]:
        """Get relevant knowledge snippets."""
        query = PROJECT_QUERIES.get(project, PROJECT_QUERIES['general'])
        results = self.search.search(query, limit=3, source='knowledge')
        return results

    def _format_learnings(self, learnings: list[dict]) -> str:
        """Format learnings section."""
        lines = ["### Recent Learnings\n"]

        for l in learnings:
            content = l.get('content', '')[:80]
            category = l.get('category', '')
            if category:
                lines.append(f"- [{category}] {content}")
            else:
                lines.append(f"- {content}")

        return "\n".join(lines) + "\n"

    def _format_errors(self, errors: list[dict]) -> str:
        """Format errors section."""
        lines = ["### Common Error Solutions\n"]

        for e in errors:
            category = e.get('category', 'general')
            pattern = e.get('pattern', '')[:40]
            solution = e.get('solution', '')

            if solution:
                lines.append(f"- **{category}** ({pattern}): {solution}")
            else:
                lines.append(f"- **{category}**: {pattern} ({e.get('count', 0)} times)")

        return "\n".join(lines) + "\n"

    def _format_reviews(self, reviews: list[dict]) -> str:
        """Format reviews section."""
        lines = ["### Due for Review\n"]

        for r in reviews:
            content = r.get('content', '')[:60]
            lines.append(f"- {content}...")

        lines.append("\n_Run `supermemory review` to complete review_")
        return "\n".join(lines) + "\n"

    def _format_knowledge(self, knowledge: list[dict]) -> str:
        """Format knowledge section."""
        if not knowledge:
            return ""

        lines = ["### Related Knowledge\n"]

        for k in knowledge:
            content = k.get('content', '')[:100]
            lines.append(f"- {content}")

        return "\n".join(lines) + "\n"

    def get_quick_context(self, project: Optional[str] = None) -> str:
        """Get minimal context for shell display."""
        if not project:
            project = self._detect_project()

        # Get counts
        learnings = self.db.get_learnings(project=project, limit=1)
        reviews = self.sr.get_due_items(limit=10)
        errors = self.db.get_top_error_patterns(limit=1)

        parts = [f"Project: {project}"]

        if learnings:
            parts.append(f"learnings: {len(learnings)}+")

        if reviews:
            parts.append(f"reviews due: {len(reviews)}")

        return " | ".join(parts)
