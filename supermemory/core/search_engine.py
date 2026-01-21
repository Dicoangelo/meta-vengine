#!/usr/bin/env python3
"""
Supermemory Search Engine - Hybrid BM25 + Vector Search

Combines:
- BM25 via SQLite FTS5 (keyword matching)
- Vector similarity via embeddings.npz (semantic matching)
- Recency boost (prefer recent items)

Score: 0.4 * bm25 + 0.4 * semantic + 0.2 * recency
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage.index_db import MemoryDB


MEMORY_DIR = Path.home() / ".claude" / "memory"
EMBEDDINGS_PATH = MEMORY_DIR / "embeddings.npz"
KNOWLEDGE_PATH = MEMORY_DIR / "knowledge.json"
DAILY_DIR = MEMORY_DIR / "daily"


class SearchEngine:
    """Hybrid search engine combining BM25 and vector similarity."""

    def __init__(self):
        self.db = MemoryDB()
        self.embeddings = None
        self.embedding_ids = []
        self.knowledge = {}
        self._load_embeddings()
        self._load_knowledge()

    def _load_embeddings(self):
        """Load pre-computed embeddings."""
        if EMBEDDINGS_PATH.exists():
            try:
                data = np.load(EMBEDDINGS_PATH, allow_pickle=True)
                self.embeddings = data.get('embeddings', None)
                self.embedding_ids = list(data.get('ids', []))
                self.embedding_texts = list(data.get('texts', []))
            except Exception:
                pass

    def _load_knowledge(self):
        """Load knowledge base."""
        if KNOWLEDGE_PATH.exists():
            try:
                with open(KNOWLEDGE_PATH) as f:
                    self.knowledge = json.load(f)
            except Exception:
                pass

    def search(self, query: str, limit: int = 10,
               source: Optional[str] = None,
               project: Optional[str] = None,
               weights: Optional[dict] = None) -> list[dict]:
        """
        Perform hybrid search.

        Args:
            query: Search query
            limit: Max results
            source: Filter by source (daily, learning, etc.)
            project: Filter by project
            weights: Custom weights {bm25, semantic, recency}

        Returns:
            List of results with scores
        """
        w = weights or {'bm25': 0.4, 'semantic': 0.4, 'recency': 0.2}

        # Collect results from different sources
        results = {}

        # 1. BM25 search via FTS5
        bm25_results = self._search_bm25(query, limit * 3, source, project)
        for r in bm25_results:
            rid = r['id']
            results[rid] = {
                'id': rid,
                'content': r['content'],
                'source': r['source'],
                'project': r.get('project'),
                'date': r.get('date'),
                'bm25_score': abs(r.get('score', 0)),  # FTS5 returns negative
            }

        # 2. Vector search (semantic)
        semantic_results = self._search_semantic(query, limit * 2)
        for r in semantic_results:
            rid = r['id']
            if rid in results:
                results[rid]['semantic_score'] = r['score']
            else:
                results[rid] = {
                    'id': rid,
                    'content': r['content'],
                    'source': r.get('source', 'embedding'),
                    'project': r.get('project'),
                    'date': r.get('date'),
                    'semantic_score': r['score'],
                }

        # 3. Search knowledge base
        knowledge_results = self._search_knowledge(query, limit)
        for r in knowledge_results:
            rid = r['id']
            if rid not in results:
                results[rid] = {
                    'id': rid,
                    'content': r['content'],
                    'source': 'knowledge',
                    'bm25_score': r.get('score', 0.5),
                }

        # 4. Search daily logs
        daily_results = self._search_daily_logs(query, limit)
        for r in daily_results:
            rid = r['id']
            if rid not in results:
                results[rid] = r
                results[rid]['bm25_score'] = r.get('score', 0.3)

        # Normalize and combine scores
        final_results = self._rank_results(list(results.values()), w)

        # Apply source/project filters if not already applied
        if source:
            final_results = [r for r in final_results if r.get('source') == source]
        if project:
            final_results = [r for r in final_results if r.get('project') == project]

        return final_results[:limit]

    def _search_bm25(self, query: str, limit: int,
                     source: Optional[str], project: Optional[str]) -> list[dict]:
        """Search using SQLite FTS5 BM25."""
        # Clean query for FTS5
        clean_query = ' '.join(
            word for word in query.split()
            if word and not word.startswith('-')
        )

        if not clean_query:
            return []

        return self.db.search_fts(clean_query, limit, source, project)

    def _search_semantic(self, query: str, limit: int) -> list[dict]:
        """Search using vector similarity."""
        if self.embeddings is None or len(self.embeddings) == 0:
            return []

        try:
            # Generate query embedding (simple TF-IDF approximation)
            query_vec = self._text_to_vector(query)
            if query_vec is None:
                return []

            # Compute cosine similarities
            similarities = np.dot(self.embeddings, query_vec) / (
                np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_vec) + 1e-8
            )

            # Get top matches
            top_indices = np.argsort(similarities)[::-1][:limit]

            results = []
            for idx in top_indices:
                if idx < len(self.embedding_ids):
                    score = float(similarities[idx])
                    if score > 0.1:  # Threshold
                        results.append({
                            'id': self.embedding_ids[idx],
                            'content': self.embedding_texts[idx] if idx < len(self.embedding_texts) else '',
                            'score': score,
                        })

            return results
        except Exception:
            return []

    def _text_to_vector(self, text: str) -> Optional[np.ndarray]:
        """Convert text to vector (simple bag-of-words)."""
        if self.embeddings is None:
            return None

        # Use mean of existing embeddings as approximation
        # In production, would use actual embedding model
        words = set(text.lower().split())
        matching_indices = []

        for i, t in enumerate(self.embedding_texts):
            text_words = set(t.lower().split())
            if words & text_words:
                matching_indices.append(i)

        if matching_indices and len(self.embeddings) > 0:
            return np.mean(self.embeddings[matching_indices], axis=0)

        # Fallback: return mean of all embeddings
        return np.mean(self.embeddings, axis=0) if len(self.embeddings) > 0 else None

    def _search_knowledge(self, query: str, limit: int) -> list[dict]:
        """Search knowledge base."""
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for key, value in self.knowledge.items():
            content = str(value) if isinstance(value, (str, int, float)) else json.dumps(value)
            content_lower = content.lower()
            key_lower = key.lower()

            # Check for matches
            score = 0
            if query_lower in key_lower:
                score += 0.8
            if query_lower in content_lower:
                score += 0.5

            # Word overlap
            content_words = set(content_lower.split())
            overlap = len(query_words & content_words)
            score += overlap * 0.1

            if score > 0:
                results.append({
                    'id': f"knowledge:{key}",
                    'content': f"{key}: {content[:200]}",
                    'score': min(score, 1.0),
                })

        results.sort(key=lambda x: -x['score'])
        return results[:limit]

    def _search_daily_logs(self, query: str, limit: int) -> list[dict]:
        """Search daily log files."""
        results = []
        query_lower = query.lower()

        if not DAILY_DIR.exists():
            return results

        # Search recent daily logs (last 30 days)
        today = datetime.now()
        for i in range(30):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            log_path = DAILY_DIR / f"{date}.md"

            if not log_path.exists():
                continue

            try:
                content = log_path.read_text()
                if query_lower in content.lower():
                    # Find matching sections
                    lines = content.split('\n')
                    matching_lines = [
                        line for line in lines
                        if query_lower in line.lower()
                    ]

                    if matching_lines:
                        results.append({
                            'id': f"daily:{date}",
                            'content': '\n'.join(matching_lines[:3]),
                            'source': 'daily',
                            'date': date,
                            'score': 0.5 + (0.01 * (30 - i)),  # Recency boost
                        })
            except Exception:
                continue

            if len(results) >= limit:
                break

        return results

    def _rank_results(self, results: list[dict], weights: dict) -> list[dict]:
        """Combine and rank results using weighted scoring."""
        # Normalize scores within each category
        max_bm25 = max((r.get('bm25_score', 0) for r in results), default=1) or 1
        max_semantic = max((r.get('semantic_score', 0) for r in results), default=1) or 1

        today = datetime.now()

        for r in results:
            # Normalize BM25
            bm25_norm = r.get('bm25_score', 0) / max_bm25

            # Normalize semantic
            semantic_norm = r.get('semantic_score', 0) / max_semantic

            # Calculate recency score (decay over 90 days)
            recency_score = 0.5
            if r.get('date'):
                try:
                    date = datetime.strptime(r['date'], "%Y-%m-%d")
                    days_ago = (today - date).days
                    recency_score = max(0, 1 - (days_ago / 90))
                except ValueError:
                    pass

            # Combined score
            r['score'] = (
                weights['bm25'] * bm25_norm +
                weights['semantic'] * semantic_norm +
                weights['recency'] * recency_score
            )

        # Sort by combined score
        results.sort(key=lambda x: -x['score'])
        return results

    def search_errors(self, error_text: str, limit: int = 5) -> list[dict]:
        """Specialized search for error patterns."""
        # First check error patterns table
        patterns = self.db.find_error_patterns(error_text, limit)

        # Also search general memory for error-related content
        general = self.search(
            error_text,
            limit=limit,
            source='error'
        )

        # Combine and deduplicate
        seen_patterns = set()
        results = []

        for p in patterns:
            key = f"{p['category']}:{p['pattern']}"
            if key not in seen_patterns:
                seen_patterns.add(key)
                results.append({
                    'id': f"pattern:{p['id']}",
                    'category': p['category'],
                    'pattern': p['pattern'],
                    'count': p['count'],
                    'solution': p.get('solution'),
                    'score': p['count'] * 0.1,
                })

        for g in general:
            if g['id'] not in seen_patterns:
                results.append(g)

        return results[:limit]
