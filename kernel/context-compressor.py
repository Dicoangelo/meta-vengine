#!/usr/bin/env python3
"""
Meta-Vengine Smart Context Compressor

Intelligent context compression to fit within token budgets while
preserving the most important information.

Features:
- Priority-based content selection
- Extractive summarization for long content
- Recency and relevance weighting
- Error context preservation
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import Counter

# Approximate tokens per character (conservative estimate)
CHARS_PER_TOKEN = 4


class ContextCompressor:
    """
    Intelligent context compression using priority weights and extractive summarization.
    """

    def __init__(self, target_tokens: int = 50000):
        """
        Initialize compressor with target token budget.

        Args:
            target_tokens: Maximum tokens to target (default 50K for headroom)
        """
        self.target_tokens = target_tokens
        self.target_chars = target_tokens * CHARS_PER_TOKEN

        # Priority weights for different content types
        self.priority_weights = {
            'active_errors': 1.0,      # Always include errors
            'recent_code': 0.95,       # Recent changes are critical
            'current_task': 0.90,      # What we're working on
            'relevant_memory': 0.80,   # Semantically relevant knowledge
            'project_context': 0.70,   # Project-specific info
            'session_history': 0.60,   # Previous session context
            'background_context': 0.40, # General background
            'historical_patterns': 0.30 # Historical info
        }

    def compress(self, context: Dict[str, str], priorities: Optional[Dict[str, float]] = None) -> str:
        """
        Compress context to fit token budget.

        Args:
            context: Dict mapping section names to content
            priorities: Optional custom priority overrides

        Returns:
            Compressed context as markdown string
        """
        if priorities:
            self.priority_weights.update(priorities)

        # Build segments with priority scores
        segments = []
        for key, content in context.items():
            if not content or not content.strip():
                continue

            priority = self._get_priority(key)
            relevance = self._calculate_relevance(content, context)
            recency = self._calculate_recency(content)

            # Combined score
            score = priority * 0.5 + relevance * 0.3 + recency * 0.2

            segments.append({
                'key': key,
                'content': content,
                'priority': priority,
                'relevance': relevance,
                'recency': recency,
                'score': score,
                'chars': len(content)
            })

        # Sort by score (highest first)
        segments.sort(key=lambda x: x['score'], reverse=True)

        # Build compressed output within budget
        compressed_parts = []
        current_chars = 0
        included_keys = []
        summarized_keys = []

        for seg in segments:
            content = seg['content']
            seg_chars = seg['chars']

            if current_chars + seg_chars <= self.target_chars:
                # Include full content
                compressed_parts.append(self._format_section(seg['key'], content))
                current_chars += seg_chars
                included_keys.append(seg['key'])
            elif current_chars < self.target_chars * 0.9:
                # Try to summarize to fit remaining budget
                remaining = self.target_chars - current_chars
                summary = self._summarize(content, max_chars=int(remaining * 0.8))

                if summary:
                    compressed_parts.append(
                        self._format_section(seg['key'], summary, summarized=True)
                    )
                    current_chars += len(summary)
                    summarized_keys.append(seg['key'])
            else:
                # Budget exhausted
                break

        # Add compression stats header
        stats_header = self._format_stats(
            total_sections=len(context),
            included=len(included_keys),
            summarized=len(summarized_keys),
            total_chars=current_chars,
            budget_chars=self.target_chars
        )

        return stats_header + '\n\n' + '\n\n'.join(compressed_parts)

    def _get_priority(self, key: str) -> float:
        """Get priority weight for a content key."""
        key_lower = key.lower().replace('_', ' ').replace('-', ' ')

        # Direct match
        if key_lower in self.priority_weights:
            return self.priority_weights[key_lower]

        # Partial match
        for priority_key, weight in self.priority_weights.items():
            if priority_key.replace('_', ' ') in key_lower or key_lower in priority_key.replace('_', ' '):
                return weight

        # Default priority
        return 0.5

    def _calculate_relevance(self, content: str, all_context: Dict[str, str]) -> float:
        """Calculate relevance based on keyword overlap with other content."""
        if not content or not all_context:
            return 0.5

        # Extract significant words from this content
        content_words = set(self._extract_keywords(content))

        if not content_words:
            return 0.5

        # Check overlap with other sections
        other_words = set()
        for key, other_content in all_context.items():
            if other_content != content:
                other_words.update(self._extract_keywords(other_content))

        if not other_words:
            return 0.5

        # Calculate Jaccard similarity
        intersection = len(content_words & other_words)
        union = len(content_words | other_words)

        return intersection / union if union > 0 else 0.5

    def _calculate_recency(self, content: str) -> float:
        """Estimate recency based on timestamps in content."""
        # Look for ISO timestamps
        timestamp_pattern = r'\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2})?'
        matches = re.findall(timestamp_pattern, content)

        if not matches:
            return 0.5  # Default if no timestamps

        try:
            # Parse most recent timestamp
            latest = max(
                datetime.fromisoformat(ts.replace('Z', ''))
                for ts in matches
            )

            # Calculate age in days
            age_days = (datetime.now() - latest).days

            # Exponential decay: recent = 1.0, old = approaches 0
            if age_days <= 1:
                return 1.0
            elif age_days <= 7:
                return 0.8
            elif age_days <= 30:
                return 0.5
            else:
                return 0.3
        except Exception:
            return 0.5

    def _extract_keywords(self, text: str, min_length: int = 4) -> List[str]:
        """Extract significant keywords from text."""
        # Remove common markdown/code artifacts
        text = re.sub(r'```[\s\S]*?```', '', text)  # Code blocks
        text = re.sub(r'`[^`]+`', '', text)  # Inline code
        text = re.sub(r'\[.*?\]\(.*?\)', '', text)  # Links
        text = re.sub(r'[#*_~>\-=]', ' ', text)  # Markdown syntax

        # Extract words
        words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9]*\b', text.lower())

        # Filter stopwords and short words
        stopwords = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can',
            'has', 'have', 'had', 'her', 'was', 'one', 'our', 'out', 'day',
            'get', 'use', 'been', 'call', 'come', 'make', 'than', 'that',
            'their', 'this', 'what', 'when', 'will', 'with', 'would', 'from',
            'about', 'which', 'were', 'they', 'into', 'some', 'could', 'them',
            'other', 'than', 'then', 'these', 'only', 'also', 'more'
        }

        return [w for w in words if len(w) >= min_length and w not in stopwords]

    def _summarize(self, content: str, max_chars: int) -> Optional[str]:
        """
        Extract key sentences to create summary.

        Uses extractive summarization based on sentence importance.
        """
        if len(content) <= max_chars:
            return content

        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', content)

        if not sentences:
            return content[:max_chars] + '...'

        # Score sentences by importance
        word_freq = Counter(self._extract_keywords(content))
        scored_sentences = []

        for i, sentence in enumerate(sentences):
            if len(sentence) < 20:
                continue

            # Score based on:
            # 1. Word importance (TF)
            words = self._extract_keywords(sentence)
            word_score = sum(word_freq.get(w, 0) for w in words) / (len(words) + 1)

            # 2. Position (first sentences often more important)
            position_score = 1.0 - (i / len(sentences)) * 0.3

            # 3. Length (prefer medium-length sentences)
            length_score = min(1.0, 50 / len(sentence)) if len(sentence) > 50 else len(sentence) / 50

            total_score = word_score * 0.5 + position_score * 0.3 + length_score * 0.2
            scored_sentences.append((sentence, total_score, i))

        # Sort by score and select top sentences that fit
        scored_sentences.sort(key=lambda x: x[1], reverse=True)

        selected = []
        current_len = 0

        for sentence, score, original_idx in scored_sentences:
            if current_len + len(sentence) + 2 <= max_chars - 50:  # Leave room for ellipsis
                selected.append((sentence, original_idx))
                current_len += len(sentence) + 2

        if not selected:
            # Just truncate
            return content[:max_chars - 3] + '...'

        # Restore original order
        selected.sort(key=lambda x: x[1])

        summary = ' '.join(s[0] for s in selected)
        if len(summary) < len(content):
            summary += ' [...]'

        return summary

    def _format_section(self, key: str, content: str, summarized: bool = False) -> str:
        """Format a section with header."""
        header = f"## {key.replace('_', ' ').title()}"
        if summarized:
            header += " (summarized)"
        return f"{header}\n{content}"

    def _format_stats(self, total_sections: int, included: int, summarized: int,
                     total_chars: int, budget_chars: int) -> str:
        """Format compression statistics header."""
        utilization = (total_chars / budget_chars) * 100 if budget_chars > 0 else 0
        tokens_used = total_chars // CHARS_PER_TOKEN

        return f"""<!-- Context Compression Stats -->
<!-- Sections: {included}/{total_sections} included, {summarized} summarized -->
<!-- Tokens: ~{tokens_used:,} / {self.target_tokens:,} ({utilization:.1f}% utilized) -->"""


def estimate_tokens(text: str) -> int:
    """Estimate token count for text."""
    return len(text) // CHARS_PER_TOKEN


def main():
    """CLI interface for context compressor."""
    if len(sys.argv) < 2:
        print("Meta-Vengine Context Compressor")
        print("")
        print("Usage: context-compressor.py <command> [args]")
        print("")
        print("Commands:")
        print("  compress <file>        Compress JSON context file")
        print("  estimate <file>        Estimate tokens in file")
        print("  demo                   Run compression demo")
        return

    cmd = sys.argv[1]

    if cmd == "compress":
        if len(sys.argv) < 3:
            print("Usage: context-compressor.py compress <file.json>")
            return

        filepath = Path(sys.argv[2])
        if not filepath.exists():
            print(f"File not found: {filepath}")
            return

        with open(filepath) as f:
            context = json.load(f)

        compressor = ContextCompressor()
        result = compressor.compress(context)

        print(result)

    elif cmd == "estimate":
        if len(sys.argv) < 3:
            print("Usage: context-compressor.py estimate <file>")
            return

        filepath = Path(sys.argv[2])
        if not filepath.exists():
            print(f"File not found: {filepath}")
            return

        with open(filepath) as f:
            content = f.read()

        tokens = estimate_tokens(content)
        print(f"Estimated tokens: {tokens:,}")
        print(f"Characters: {len(content):,}")

    elif cmd == "demo":
        # Demo with sample context
        sample_context = {
            "active_errors": "TypeError: Cannot read property 'map' of undefined at line 42",
            "recent_code": """
function processData(data) {
    if (!data || !data.items) {
        throw new Error('Invalid data format');
    }
    return data.items.map(item => ({
        id: item.id,
        name: item.name,
        processed: true
    }));
}
""",
            "project_context": """
OS-App is a Vite + React 19 application with Zustand state management.
Key features: Agentic Kernel, 3D visualizations, biometric UI.
Current focus: Multi-agent orchestration and routing optimization.
""",
            "session_history": """
Previous session (2026-01-19): Implemented ContrarianAgent for ACE consensus.
Added semantic search to vector memory system.
Set up background daemon for automated tasks.
""",
            "background_context": """
The Antigravity ecosystem includes multiple interconnected projects:
- OS-App: Main platform
- CareerCoach: Career governance
- ResearchGravity: Research tracking
Historical development started in early 2026.
"""
        }

        compressor = ContextCompressor(target_tokens=1000)  # Small budget for demo
        result = compressor.compress(sample_context)

        print("=== Compression Demo ===")
        print(result)

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
