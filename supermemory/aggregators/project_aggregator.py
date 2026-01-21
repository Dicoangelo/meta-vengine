#!/usr/bin/env python3
"""
Supermemory Project Aggregator - Per-project memory views

Aggregates and filters memory by project for focused context.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage.index_db import MemoryDB


DATA_DIR = Path.home() / ".claude" / "data"
MEMORY_DIR = Path.home() / ".claude" / "memory"
PROJECTS_DIR = MEMORY_DIR / "projects"


# Project definitions
PROJECTS = {
    'os-app': {
        'name': 'OS-App',
        'keywords': ['os-app', 'agentic kernel', 'metaventions', 'zustand', 'vite', 'react'],
        'path_patterns': ['OS-App', 'os-app'],
        'description': 'Metaventions AI platform with agentic kernel',
    },
    'career': {
        'name': 'CareerCoachAntigravity',
        'keywords': ['career', 'coach', 'resume', 'job'],
        'path_patterns': ['CareerCoach', 'career'],
        'description': 'Career governance system with AI agents',
    },
    'research': {
        'name': 'ResearchGravity',
        'keywords': ['research', 'arxiv', 'paper', 'study'],
        'path_patterns': ['researchgravity', 'research'],
        'description': 'Research session tracking and auto-capture',
    },
    'claude-system': {
        'name': 'Claude System',
        'keywords': ['routing', 'observatory', 'hooks', 'meta-analyzer'],
        'path_patterns': ['.claude'],
        'description': 'Claude Code system and routing infrastructure',
    },
    'metaventions': {
        'name': 'Metaventions',
        'keywords': ['metaventions', 'landing'],
        'path_patterns': ['Metaventions'],
        'description': 'Metaventions landing and marketing',
    },
}


class ProjectAggregator:
    """Aggregate memory by project."""

    def __init__(self):
        self.db = MemoryDB()
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    def get_project_memory(self, project_name: str, days: int = 30) -> Optional[str]:
        """
        Get aggregated memory for a project.

        Args:
            project_name: Project identifier
            days: Number of days to look back

        Returns:
            Formatted project memory as markdown
        """
        project = PROJECTS.get(project_name)
        if not project:
            # Try fuzzy match
            for key, proj in PROJECTS.items():
                if project_name.lower() in key or project_name.lower() in proj['name'].lower():
                    project = proj
                    project_name = key
                    break

        if not project:
            return None

        # Collect data
        data = self._collect_project_data(project_name, project, days)

        if not data['sessions'] and not data['learnings'] and not data['errors']:
            return None

        # Format as markdown
        return self._format_project_memory(project_name, project, data)

    def _collect_project_data(self, project_name: str, project: dict, days: int) -> dict:
        """Collect all data for a project."""
        data = {
            'sessions': [],
            'learnings': [],
            'errors': [],
            'patterns': defaultdict(int),
            'tools': defaultdict(int),
            'total_cost': 0,
            'files': set(),
        }

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        keywords = project.get('keywords', [])
        path_patterns = project.get('path_patterns', [])

        # Get from database
        db_memories = self.db.get_memories_by_date_range(
            cutoff_date,
            datetime.now().strftime("%Y-%m-%d"),
            project=project_name
        )

        for mem in db_memories:
            if mem.get('source') == 'outcome':
                data['sessions'].append(mem)
            elif mem.get('source') == 'error':
                data['errors'].append(mem)

        # Get learnings
        data['learnings'] = self.db.get_learnings(project=project_name, limit=50)

        # Load session outcomes and filter
        outcomes_path = DATA_DIR / "session-outcomes.jsonl"
        if outcomes_path.exists():
            for line in outcomes_path.read_text().split('\n'):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    date = record.get('date', '')
                    if date < cutoff_date:
                        continue

                    # Check if matches project
                    if self._matches_project(record, keywords, path_patterns):
                        data['sessions'].append(record)

                        # Aggregate files
                        for f in record.get('files_modified', []):
                            data['files'].add(f)
                except json.JSONDecodeError:
                    continue

        # Load errors and filter
        errors_path = DATA_DIR / "errors.jsonl"
        if errors_path.exists():
            for line in errors_path.read_text().split('\n'):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    date = record.get('date', '')
                    if date < cutoff_date:
                        continue

                    # Check source for project
                    source = record.get('source', '')
                    if any(p.lower() in source.lower() for p in path_patterns + keywords):
                        data['errors'].append(record)
                        data['patterns'][record.get('category', 'unknown')] += 1
                except json.JSONDecodeError:
                    continue

        return data

    def _matches_project(self, record: dict, keywords: list, path_patterns: list) -> bool:
        """Check if a record matches the project."""
        # Check title, intent, session_id
        text = f"{record.get('title', '')} {record.get('intent', '')} {record.get('session_id', '')}"
        text_lower = text.lower()

        # Check keywords
        if any(kw.lower() in text_lower for kw in keywords):
            return True

        # Check path patterns
        if any(p.lower() in text_lower for p in path_patterns):
            return True

        return False

    def _format_project_memory(self, project_name: str, project: dict, data: dict) -> str:
        """Format project memory as markdown."""
        lines = [
            f"# {project['name']} Memory",
            "",
            f"_{project.get('description', '')}_",
            "",
            "---",
            "",
        ]

        # Summary stats
        total_sessions = len(data['sessions'])
        successful = sum(1 for s in data['sessions'] if s.get('outcome') == 'success')
        qualities = [s.get('quality', 0) for s in data['sessions'] if s.get('quality')]
        avg_quality = sum(qualities) / len(qualities) if qualities else 0

        lines.extend([
            "## Summary",
            "",
            f"- **Sessions:** {total_sessions} ({successful} successful)",
            f"- **Avg Quality:** {avg_quality:.1f}/5",
            f"- **Files Modified:** {len(data['files'])}",
            f"- **Error Categories:** {len(data['patterns'])}",
            "",
        ])

        # Recent sessions
        if data['sessions']:
            lines.extend([
                "## Recent Sessions",
                "",
            ])
            for session in sorted(data['sessions'], key=lambda x: x.get('date', ''), reverse=True)[:10]:
                title = session.get('title', 'Untitled')[:60]
                outcome = session.get('outcome', '?')
                quality = session.get('quality', '?')
                date = session.get('date', '')
                lines.append(f"- [{date}] {title}... → {outcome} (Q: {quality})")
            lines.append("")

        # Key learnings
        if data['learnings']:
            lines.extend([
                "## Key Learnings",
                "",
            ])
            for learning in data['learnings'][:7]:
                content = learning.get('content', '')[:100]
                category = learning.get('category', '')
                lines.append(f"- [{category}] {content}...")
            lines.append("")

        # Error patterns
        if data['patterns']:
            lines.extend([
                "## Error Patterns",
                "",
            ])
            for category, count in sorted(data['patterns'].items(), key=lambda x: -x[1])[:5]:
                lines.append(f"- **{category}:** {count} occurrences")
            lines.append("")

        # Recent files
        if data['files']:
            lines.extend([
                "## Recently Modified Files",
                "",
            ])
            for f in sorted(data['files'])[:15]:
                lines.append(f"- `{f}`")
            lines.append("")

        return "\n".join(lines)

    def generate_all_project_memories(self, days: int = 30):
        """Generate memory files for all projects."""
        generated = []

        for project_name in PROJECTS:
            memory = self.get_project_memory(project_name, days)
            if memory:
                output_path = PROJECTS_DIR / f"{project_name}.md"
                output_path.write_text(memory)
                generated.append(output_path)

        return generated

    def detect_project_from_path(self, path: str) -> Optional[str]:
        """Detect project from file path."""
        path_lower = path.lower()

        for project_name, project in PROJECTS.items():
            for pattern in project.get('path_patterns', []):
                if pattern.lower() in path_lower:
                    return project_name

        return None

    def detect_project_from_cwd(self) -> Optional[str]:
        """Detect project from current working directory."""
        import os
        cwd = os.getcwd()
        return self.detect_project_from_path(cwd)
