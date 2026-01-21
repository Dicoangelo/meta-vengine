#!/usr/bin/env python3
"""
Supermemory Error Extractor - Parse and catalog error patterns

Extracts error patterns from:
- errors.jsonl
- Session transcripts
- ERRORS.md

Provides solution lookup for common errors.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage.index_db import MemoryDB


DATA_DIR = Path.home() / ".claude" / "data"
CLAUDE_DIR = Path.home() / ".claude"


# Common error patterns with solutions
KNOWN_SOLUTIONS = {
    'git': {
        'fatal: not a git repository': 'Run `git init` or navigate to a git repository',
        'fatal: tag .* already exists': 'Delete the tag first: `git tag -d <tag>` or use a different version',
        'permission denied': 'Check file permissions or use sudo for system directories',
        'merge conflict': 'Resolve conflicts manually, then `git add` and `git commit`',
    },
    'npm': {
        'ENOENT': 'File or directory not found - check the path exists',
        'EACCES': 'Permission denied - try with sudo or fix permissions',
        'peer dep': 'Install peer dependencies manually: `npm install <package>`',
    },
    'python': {
        'ModuleNotFoundError': 'Install the module: `pip install <module>`',
        'ImportError': 'Check module installation and PYTHONPATH',
        'IndentationError': 'Fix indentation - use consistent spaces/tabs',
    },
    'typescript': {
        'cannot find module': 'Install types: `npm install @types/<package>`',
        'type .* is not assignable': 'Check type compatibility or use type assertion',
    },
    'concurrency': {
        'race condition': 'Use locks, atomic operations, or single-threaded execution',
        'deadlock': 'Review lock ordering, use timeouts',
    },
}


class ErrorExtractor:
    """Extract and catalog error patterns."""

    def __init__(self):
        self.db = MemoryDB()

    def extract_from_errors_jsonl(self) -> int:
        """Extract patterns from errors.jsonl."""
        count = 0
        errors_path = DATA_DIR / "errors.jsonl"

        if not errors_path.exists():
            return count

        patterns_seen = defaultdict(int)

        for line in errors_path.read_text().split('\n'):
            if not line.strip():
                continue

            try:
                record = json.loads(line)

                category = record.get('category', 'unknown')
                pattern = record.get('pattern', '')
                error_line = record.get('line', '')

                # Find matching solution
                solution = self._find_solution(category, error_line)

                # Track pattern
                key = f"{category}:{pattern}"
                patterns_seen[key] += 1

                # Only add if first occurrence or has solution
                if patterns_seen[key] == 1 or solution:
                    self.db.add_error_pattern(
                        category=category,
                        pattern=pattern or error_line[:50],
                        solution=solution
                    )
                    count += 1

            except json.JSONDecodeError:
                continue

        return count

    def extract_from_errors_md(self) -> int:
        """Extract patterns from ERRORS.md."""
        count = 0
        errors_md = CLAUDE_DIR / "ERRORS.md"

        if not errors_md.exists():
            return count

        content = errors_md.read_text()

        # Parse markdown sections
        current_category = 'general'
        current_error = None

        for line in content.split('\n'):
            # Check for category headers
            if line.startswith('## '):
                current_category = line[3:].strip().lower()
            elif line.startswith('### '):
                # Error title
                current_error = line[4:].strip()
            elif line.startswith('- ') and current_error:
                # Possible solution
                solution = line[2:].strip()
                if solution:
                    self.db.add_error_pattern(
                        category=current_category,
                        pattern=current_error[:50],
                        solution=solution
                    )
                    count += 1
                    current_error = None

        return count

    def _find_solution(self, category: str, error_text: str) -> Optional[str]:
        """Find a known solution for an error."""
        error_lower = error_text.lower()

        # Check category-specific solutions
        if category in KNOWN_SOLUTIONS:
            for pattern, solution in KNOWN_SOLUTIONS[category].items():
                if pattern.lower() in error_lower:
                    return solution

        # Check all categories
        for cat, solutions in KNOWN_SOLUTIONS.items():
            for pattern, solution in solutions.items():
                if pattern.lower() in error_lower:
                    return solution

        return None

    def find_solutions(self, error_text: str, limit: int = 5) -> list[dict]:
        """
        Find solutions for a given error.

        Args:
            error_text: Error message or description

        Returns:
            List of matching patterns with solutions
        """
        results = []

        # First check database
        db_results = self.db.find_error_patterns(error_text, limit)
        for r in db_results:
            results.append({
                'category': r['category'],
                'pattern': r['pattern'],
                'count': r['count'],
                'solution': r.get('solution'),
            })

        # Also check known solutions
        error_lower = error_text.lower()
        for category, solutions in KNOWN_SOLUTIONS.items():
            for pattern, solution in solutions.items():
                if pattern.lower() in error_lower:
                    # Check if not already in results
                    if not any(r.get('solution') == solution for r in results):
                        results.append({
                            'category': category,
                            'pattern': pattern,
                            'count': 0,
                            'solution': solution,
                        })

        return results[:limit]

    def categorize_error(self, error_text: str) -> str:
        """Categorize an error based on keywords."""
        error_lower = error_text.lower()

        categories = {
            'git': ['git', 'commit', 'push', 'pull', 'merge', 'branch', 'fatal:'],
            'npm': ['npm', 'node_modules', 'package.json', 'ENOENT', 'EACCES'],
            'python': ['python', 'pip', 'ImportError', 'ModuleNotFound', 'traceback'],
            'typescript': ['typescript', 'ts', 'type', 'interface', 'tsc'],
            'permissions': ['permission', 'denied', 'access', 'sudo'],
            'network': ['network', 'timeout', 'connection', 'socket', 'fetch'],
            'concurrency': ['race', 'deadlock', 'thread', 'lock', 'async'],
            'memory': ['memory', 'heap', 'stack', 'overflow', 'allocation'],
            'syntax': ['syntax', 'parse', 'unexpected', 'token'],
        }

        for category, keywords in categories.items():
            if any(kw in error_lower for kw in keywords):
                return category

        return 'general'

    def extract_error_from_text(self, text: str) -> list[dict]:
        """Extract errors from arbitrary text."""
        errors = []

        # Common error patterns
        error_patterns = [
            r'(Error|ERROR|error):?\s*(.+)',
            r'(Exception|EXCEPTION):?\s*(.+)',
            r'(fatal|FATAL):?\s*(.+)',
            r'(failed|FAILED):?\s*(.+)',
            r'(Traceback|traceback).*',
        ]

        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            for pattern in error_patterns:
                match = re.search(pattern, line)
                if match:
                    error_text = match.group(0)
                    category = self.categorize_error(error_text)
                    solution = self._find_solution(category, error_text)

                    errors.append({
                        'text': error_text[:200],
                        'category': category,
                        'solution': solution,
                    })
                    break

        return errors

    def get_top_errors(self, limit: int = 10) -> list[dict]:
        """Get most common error patterns."""
        return self.db.get_top_error_patterns(limit)

    def add_solution(self, category: str, pattern: str, solution: str):
        """Add a solution for an error pattern."""
        self.db.add_error_pattern(category, pattern, solution)
