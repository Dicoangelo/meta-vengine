#!/usr/bin/env python3
"""
Supermemory Unified Index - Bridges all data sources

Rebuilds and maintains the unified memory index from:
- Daily logs
- Session outcomes
- Errors
- Learnings
- Knowledge base
"""

import json
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage.index_db import MemoryDB


DATA_DIR = Path.home() / ".claude" / "data"
MEMORY_DIR = Path.home() / ".claude" / "memory"
DAILY_DIR = MEMORY_DIR / "daily"


class UnifiedIndex:
    """Unified index builder and maintainer."""

    def __init__(self):
        self.db = MemoryDB()

    def rebuild_all(self) -> dict:
        """Rebuild all indexes from source data."""
        stats = {
            'memory_items': 0,
            'learnings': 0,
            'error_patterns': 0,
            'review_items': 0,
        }

        # Index daily logs
        stats['memory_items'] += self._index_daily_logs()

        # Index session outcomes
        stats['memory_items'] += self._index_session_outcomes()

        # Index errors
        stats['error_patterns'] += self._index_errors()

        # Index from knowledge base
        stats['memory_items'] += self._index_knowledge()

        # Extract and index learnings
        stats['learnings'] += self._extract_learnings()

        # Populate spaced repetition from learnings
        stats['review_items'] = self._populate_reviews()

        return stats

    def _index_daily_logs(self) -> int:
        """Index daily log files."""
        count = 0

        if not DAILY_DIR.exists():
            return count

        for log_file in DAILY_DIR.glob("*.md"):
            try:
                date = log_file.stem  # YYYY-MM-DD
                content = log_file.read_text()

                # Extract sections
                sections = self._parse_daily_log(content)

                for section_name, section_content in sections.items():
                    if section_content.strip():
                        # Detect project from content
                        project = self._detect_project(section_content)

                        self.db.add_memory(
                            source='daily',
                            content=section_content,
                            date=date,
                            project=project,
                            tags=[section_name],
                            metadata={'section': section_name}
                        )
                        count += 1
            except Exception:
                continue

        return count

    def _parse_daily_log(self, content: str) -> dict:
        """Parse daily log into sections."""
        sections = {}
        current_section = 'header'
        current_content = []

        for line in content.split('\n'):
            if line.startswith('## '):
                # Save previous section
                if current_content:
                    sections[current_section] = '\n'.join(current_content)
                current_section = line[3:].strip().lower().replace(' ', '_')
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def _index_session_outcomes(self) -> int:
        """Index session outcomes."""
        count = 0
        outcomes_path = DATA_DIR / "session-outcomes.jsonl"

        if not outcomes_path.exists():
            return count

        for line in outcomes_path.read_text().split('\n'):
            if not line.strip():
                continue

            try:
                record = json.loads(line)

                # Build content from record
                title = (record.get('title') or '')[:100]
                intent = (record.get('intent') or '')[:200]
                outcome = record.get('outcome') or ''
                quality = record.get('quality', 0)

                content = f"Session: {title}\nIntent: {intent}\nOutcome: {outcome}"

                # Detect project
                project = self._detect_project_from_session(record)

                self.db.add_memory(
                    source='outcome',
                    content=content,
                    date=record.get('date'),
                    project=project,
                    quality=quality,
                    metadata={
                        'session_id': record.get('session_id'),
                        'outcome': outcome,
                        'models_used': record.get('models_used', {}),
                    }
                )
                count += 1
            except json.JSONDecodeError:
                continue

        return count

    def _index_errors(self) -> int:
        """Index error patterns."""
        count = 0
        errors_path = DATA_DIR / "errors.jsonl"

        if not errors_path.exists():
            return count

        for line in errors_path.read_text().split('\n'):
            if not line.strip():
                continue

            try:
                record = json.loads(line)

                category = record.get('category', 'unknown')
                pattern = record.get('pattern', '')
                error_line = record.get('line', '')[:200]

                # Add to error patterns table
                self.db.add_error_pattern(
                    category=category,
                    pattern=pattern,
                    solution=None  # Will be populated from solutions
                )

                # Also add to memory items
                self.db.add_memory(
                    source='error',
                    content=f"[{category}] {error_line}",
                    date=record.get('date'),
                    tags=[category, 'error'],
                    metadata={'pattern': pattern, 'severity': record.get('severity')}
                )
                count += 1
            except json.JSONDecodeError:
                continue

        return count

    def _index_knowledge(self) -> int:
        """Index knowledge base."""
        count = 0
        knowledge_path = MEMORY_DIR / "knowledge.json"

        if not knowledge_path.exists():
            return count

        try:
            with open(knowledge_path) as f:
                knowledge = json.load(f)

            for key, value in knowledge.items():
                content = f"{key}: {json.dumps(value) if isinstance(value, (dict, list)) else value}"

                self.db.add_memory(
                    source='knowledge',
                    content=content[:500],
                    tags=['knowledge', key.split(':')[0] if ':' in key else 'general'],
                )
                count += 1
        except Exception:
            pass

        return count

    def _extract_learnings(self) -> int:
        """Extract learnings from session outcomes."""
        count = 0
        outcomes_path = DATA_DIR / "session-outcomes.jsonl"

        if not outcomes_path.exists():
            return count

        for line in outcomes_path.read_text().split('\n'):
            if not line.strip():
                continue

            try:
                record = json.loads(line)

                # Only extract from successful, high-quality sessions
                if record.get('outcome') != 'success':
                    continue
                if record.get('quality', 0) < 3:
                    continue

                # Extract learning from title/intent
                title = record.get('title', '')
                intent = record.get('intent', '')

                # Determine category from keywords
                category = self._categorize_learning(title + ' ' + intent)

                # Create learning entry
                content = f"Completed: {title[:100]}"
                if intent and intent != title:
                    content += f" | Goal: {intent[:100]}"

                self.db.add_learning(
                    content=content,
                    category=category,
                    session_id=record.get('session_id'),
                    project=self._detect_project_from_session(record),
                    quality=record.get('quality'),
                    date=record.get('date'),
                )
                count += 1
            except json.JSONDecodeError:
                continue

        return count

    def _populate_reviews(self) -> int:
        """Populate spaced repetition from high-quality learnings."""
        count = 0
        learnings = self.db.get_learnings(limit=200)

        for learning in learnings:
            # Only add high-quality learnings
            quality = learning.get('quality', 0)
            if quality and quality >= 4:
                self.db.add_review_item(
                    content=learning['content'],
                    category=learning.get('category'),
                    source_id=learning['id']
                )
                count += 1

        return count

    def _detect_project(self, content: str) -> str:
        """Detect project from content."""
        content_lower = content.lower()

        if 'os-app' in content_lower or 'agentic kernel' in content_lower:
            return 'os-app'
        if 'career' in content_lower:
            return 'career'
        if 'research' in content_lower or 'arxiv' in content_lower:
            return 'research'
        if 'routing' in content_lower or 'observatory' in content_lower:
            return 'claude-system'
        if 'metaventions' in content_lower:
            return 'metaventions'

        return 'general'

    def _detect_project_from_session(self, record: dict) -> str:
        """Detect project from session record."""
        title = record.get('title', '')
        intent = record.get('intent', '')
        session_id = record.get('session_id', '')

        combined = f"{title} {intent} {session_id}"
        return self._detect_project(combined)

    def _categorize_learning(self, text: str) -> str:
        """Categorize a learning based on keywords."""
        text_lower = text.lower()

        categories = {
            'architecture': ['architecture', 'design', 'system', 'pattern', 'refactor'],
            'bug_fix': ['fix', 'bug', 'error', 'issue', 'resolve'],
            'feature': ['implement', 'add', 'feature', 'create', 'build'],
            'optimization': ['optimize', 'performance', 'speed', 'cache', 'efficiency'],
            'research': ['research', 'paper', 'arxiv', 'study', 'investigate'],
            'documentation': ['document', 'readme', 'docs', 'comment'],
            'testing': ['test', 'spec', 'coverage', 'validate'],
            'devops': ['deploy', 'ci', 'cd', 'docker', 'kubernetes'],
        }

        for category, keywords in categories.items():
            if any(kw in text_lower for kw in keywords):
                return category

        return 'general'

    def incremental_update(self) -> dict:
        """Perform incremental update (new items only)."""
        # Get last indexed timestamp
        stats = self.db.get_stats()
        # For now, just rebuild - in production, would track last indexed time
        return self.rebuild_all()
