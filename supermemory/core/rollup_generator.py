#!/usr/bin/env python3
"""
Supermemory Rollup Generator - Weekly/Monthly summaries

Aggregates daily logs into:
- Weekly rollups with metrics, patterns, learnings
- Monthly rollups with trends and key decisions
"""

import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage.index_db import MemoryDB


MEMORY_DIR = Path.home() / ".claude" / "memory"
DAILY_DIR = MEMORY_DIR / "daily"
WEEKLY_DIR = MEMORY_DIR / "weekly"
DATA_DIR = Path.home() / ".claude" / "data"


class RollupGenerator:
    """Generate weekly and monthly rollups from daily data."""

    def __init__(self):
        self.db = MemoryDB()
        WEEKLY_DIR.mkdir(parents=True, exist_ok=True)

    def generate_current_week(self) -> Optional[Path]:
        """Generate rollup for the current week."""
        today = datetime.now()
        # Find Monday of current week
        monday = today - timedelta(days=today.weekday())
        week_str = monday.strftime("%Y-W%W")
        return self.generate_weekly(week_str)

    def generate_weekly(self, week_str: str) -> Optional[Path]:
        """
        Generate weekly rollup.

        Args:
            week_str: ISO week format (e.g., "2026-W03")

        Returns:
            Path to generated rollup file
        """
        # Parse week string
        try:
            year, week = week_str.split('-W')
            year = int(year)
            week = int(week)
        except ValueError:
            return None

        # Calculate date range
        first_day = datetime.strptime(f'{year}-W{week:02d}-1', '%Y-W%W-%w')
        last_day = first_day + timedelta(days=6)

        start_date = first_day.strftime("%Y-%m-%d")
        end_date = last_day.strftime("%Y-%m-%d")

        # Collect data
        data = self._collect_week_data(start_date, end_date)

        if not data['has_data']:
            return None

        # Generate markdown
        content = self._format_weekly_rollup(week_str, first_day, last_day, data)

        # Write file
        output_path = WEEKLY_DIR / f"{week_str}.md"
        output_path.write_text(content)

        return output_path

    def generate_monthly(self, month_str: str) -> Optional[Path]:
        """
        Generate monthly rollup.

        Args:
            month_str: Month format (e.g., "2026-01")

        Returns:
            Path to generated rollup file
        """
        try:
            year, month = month_str.split('-')
            year = int(year)
            month = int(month)
        except ValueError:
            return None

        # Calculate date range
        first_day = datetime(year, month, 1)
        if month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)

        start_date = first_day.strftime("%Y-%m-%d")
        end_date = last_day.strftime("%Y-%m-%d")

        # Collect data
        data = self._collect_week_data(start_date, end_date)

        if not data['has_data']:
            return None

        # Generate markdown
        content = self._format_monthly_rollup(month_str, first_day, last_day, data)

        # Write file
        output_path = WEEKLY_DIR / f"{month_str}-monthly.md"
        output_path.write_text(content)

        return output_path

    def _collect_week_data(self, start_date: str, end_date: str) -> dict:
        """Collect all data for date range."""
        data = {
            'has_data': False,
            'sessions': [],
            'costs': defaultdict(lambda: {'cost': 0, 'count': 0}),
            'errors': defaultdict(int),
            'tools': defaultdict(int),
            'projects': defaultdict(int),
            'git_commits': 0,
            'files_modified': set(),
            'qualities': [],
            'daily_logs': [],
            'learnings': [],
            'error_patterns': [],
            'hours': defaultdict(int),
        }

        # Load session outcomes
        outcomes_path = DATA_DIR / "session-outcomes.jsonl"
        if outcomes_path.exists():
            for line in outcomes_path.read_text().split('\n'):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    date = record.get('date', '')
                    if start_date <= date <= end_date:
                        data['has_data'] = True
                        data['sessions'].append(record)

                        # Track quality
                        if record.get('quality'):
                            data['qualities'].append(record['quality'])

                        # Track models
                        for model, count in record.get('models_used', {}).items():
                            data['costs'][model]['count'] += count
                except json.JSONDecodeError:
                    continue

        # Load cost tracking
        cost_path = DATA_DIR / "cost-tracking.jsonl"
        if cost_path.exists():
            for line in cost_path.read_text().split('\n'):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    date = record.get('date', '')
                    if start_date <= date <= end_date:
                        model = record.get('model', 'unknown')
                        if 'opus' in model.lower():
                            model = 'Opus'
                        elif 'sonnet' in model.lower():
                            model = 'Sonnet'
                        elif 'haiku' in model.lower():
                            model = 'Haiku'
                        data['costs'][model]['cost'] += record.get('cost_usd', 0)
                except json.JSONDecodeError:
                    continue

        # Load errors
        errors_path = DATA_DIR / "errors.jsonl"
        if errors_path.exists():
            for line in errors_path.read_text().split('\n'):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    date = record.get('date', '')
                    if start_date <= date <= end_date:
                        data['errors'][record.get('category', 'unknown')] += 1
                except json.JSONDecodeError:
                    continue

        # Load git activity
        git_path = DATA_DIR / "git-activity.jsonl"
        if git_path.exists():
            for line in git_path.read_text().split('\n'):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    ts = record.get('ts', 0)
                    if ts:
                        date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                        if start_date <= date <= end_date:
                            data['git_commits'] += 1
                except json.JSONDecodeError:
                    continue

        # Load tool usage
        tool_path = DATA_DIR / "tool-usage.jsonl"
        if tool_path.exists():
            for line in tool_path.read_text().split('\n'):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    ts = record.get('ts', 0)
                    if ts:
                        date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                        if start_date <= date <= end_date:
                            data['tools'][record.get('tool', 'unknown')] += 1
                            hour = datetime.fromtimestamp(ts).hour
                            data['hours'][hour] += 1
                except json.JSONDecodeError:
                    continue

        # Load daily logs
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            log_path = DAILY_DIR / f"{date_str}.md"
            if log_path.exists():
                data['daily_logs'].append({
                    'date': date_str,
                    'content': log_path.read_text()
                })
            current += timedelta(days=1)

        # Get learnings from database
        learnings = self.db.get_learnings(limit=100)
        for learning in learnings:
            date = learning.get('date', '')
            if date and start_date <= date <= end_date:
                data['learnings'].append(learning)

        return data

    def _format_weekly_rollup(self, week_str: str, start: datetime,
                              end: datetime, data: dict) -> str:
        """Format weekly rollup as markdown."""
        lines = [
            f"# Week {week_str} ({start.strftime('%b %d')} - {end.strftime('%b %d, %Y')})",
            "",
            "## Metrics",
            "",
        ]

        # Session stats
        total = len(data['sessions'])
        successful = len([s for s in data['sessions'] if s.get('outcome') == 'success'])
        partial = len([s for s in data['sessions'] if s.get('outcome') == 'partial'])

        avg_quality = sum(data['qualities']) / len(data['qualities']) if data['qualities'] else 0

        lines.extend([
            f"- **Sessions:** {total} ({successful} successful, {partial} partial)",
            f"- **Avg Quality:** {avg_quality:.1f}/5",
            f"- **Git Commits:** {data['git_commits']}",
            "",
        ])

        # Cost breakdown
        if data['costs']:
            lines.extend([
                "## Cost Breakdown",
                "",
                "| Model | Cost | Sessions |",
                "|-------|------|----------|",
            ])

            total_cost = 0
            for model, stats in sorted(data['costs'].items()):
                lines.append(f"| {model} | ${stats['cost']:.2f} | {stats['count']} |")
                total_cost += stats['cost']

            lines.extend([
                "",
                f"**Total:** ${total_cost:.2f}",
                "",
            ])

        # Error patterns
        if data['errors']:
            lines.extend([
                "## Error Patterns",
                "",
            ])
            error_total = sum(data['errors'].values())
            for cat, count in sorted(data['errors'].items(), key=lambda x: -x[1])[:5]:
                pct = count / error_total * 100
                lines.append(f"- **{cat}:** {count} ({pct:.0f}%)")
            lines.append("")

        # Peak hours
        if data['hours']:
            top_hours = sorted(data['hours'].items(), key=lambda x: -x[1])[:3]
            lines.extend([
                "## Peak Productivity",
                "",
                f"Top hours: {', '.join(f'{h}:00 ({c})' for h, c in top_hours)}",
                "",
            ])

        # Tool usage
        if data['tools']:
            lines.extend([
                "## Top Tools",
                "",
                "| Tool | Count |",
                "|------|-------|",
            ])
            for tool, count in sorted(data['tools'].items(), key=lambda x: -x[1])[:7]:
                lines.append(f"| {tool} | {count} |")
            lines.append("")

        # Learnings
        if data['learnings']:
            lines.extend([
                "## Key Learnings",
                "",
            ])
            for i, learning in enumerate(data['learnings'][:5], 1):
                content = learning.get('content', '')[:100]
                category = learning.get('category', '')
                lines.append(f"{i}. [{category}] {content}...")
            lines.append("")

        # Cross-day patterns
        lines.extend([
            "## Cross-Day Patterns",
            "",
            self._extract_patterns(data),
            "",
        ])

        return "\n".join(lines)

    def _format_monthly_rollup(self, month_str: str, start: datetime,
                               end: datetime, data: dict) -> str:
        """Format monthly rollup as markdown."""
        lines = [
            f"# Monthly Summary: {start.strftime('%B %Y')}",
            "",
            "## Overview",
            "",
        ]

        # High-level stats
        total = len(data['sessions'])
        total_cost = sum(s['cost'] for s in data['costs'].values())
        avg_quality = sum(data['qualities']) / len(data['qualities']) if data['qualities'] else 0

        lines.extend([
            f"- **Total Sessions:** {total}",
            f"- **Total Cost:** ${total_cost:.2f}",
            f"- **Avg Quality:** {avg_quality:.1f}/5",
            f"- **Git Commits:** {data['git_commits']}",
            "",
        ])

        # Cost by model
        if data['costs']:
            lines.extend([
                "## Cost by Model",
                "",
            ])
            for model, stats in sorted(data['costs'].items(), key=lambda x: -x[1]['cost']):
                lines.append(f"- **{model}:** ${stats['cost']:.2f}")
            lines.append("")

        # Top error categories
        if data['errors']:
            lines.extend([
                "## Error Summary",
                "",
            ])
            for cat, count in sorted(data['errors'].items(), key=lambda x: -x[1])[:5]:
                lines.append(f"- {cat}: {count}")
            lines.append("")

        # Key learnings
        if data['learnings']:
            lines.extend([
                "## Top Learnings",
                "",
            ])
            for learning in data['learnings'][:10]:
                content = learning.get('content', '')[:80]
                lines.append(f"- {content}...")
            lines.append("")

        return "\n".join(lines)

    def _extract_patterns(self, data: dict) -> str:
        """Extract cross-day patterns from data."""
        patterns = []

        # Error trends
        if data['errors']:
            total_errors = sum(data['errors'].values())
            top_error = max(data['errors'].items(), key=lambda x: x[1])
            patterns.append(f"- Top error type: **{top_error[0]}** ({top_error[1]} of {total_errors})")

        # Session outcome trends
        outcomes = defaultdict(int)
        for s in data['sessions']:
            outcomes[s.get('outcome', 'unknown')] += 1

        if outcomes:
            success_rate = outcomes.get('success', 0) / len(data['sessions']) * 100
            patterns.append(f"- Success rate: **{success_rate:.0f}%**")

        # Quality trend
        if len(data['qualities']) >= 3:
            first_half = data['qualities'][:len(data['qualities'])//2]
            second_half = data['qualities'][len(data['qualities'])//2:]
            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)
            trend = "↑" if avg_second > avg_first else "↓" if avg_second < avg_first else "→"
            patterns.append(f"- Quality trend: {trend} ({avg_first:.1f} → {avg_second:.1f})")

        return "\n".join(patterns) if patterns else "_No significant patterns detected_"
