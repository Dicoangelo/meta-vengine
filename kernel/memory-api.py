#!/usr/bin/env python3
"""
Meta-Vengine Vector Memory System

Adds semantic embedding layer to knowledge.json for intelligent retrieval.
Uses sentence-transformers for embeddings with fallback to keyword search.
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import hashlib

# Try to import numpy and sentence-transformers
# Falls back to keyword search if not available
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    SentenceTransformer = None


class VectorMemory:
    """
    Vector memory system with semantic search capabilities.

    Features:
    - Semantic similarity search using embeddings
    - Fallback to keyword search when embeddings unavailable
    - Auto-rebuilds embeddings when knowledge changes
    - Links between knowledge items via memory-graph
    """

    def __init__(self):
        self.memory_dir = Path.home() / '.claude/memory'
        self.knowledge_file = self.memory_dir / 'knowledge.json'
        self.embeddings_file = self.memory_dir / 'embeddings.npz'
        self.graph_file = Path.home() / '.claude/kernel/memory-graph.json'

        self.encoder = None
        self.knowledge = {"facts": [], "decisions": [], "patterns": [], "context": {}, "projects": {}}
        self.embeddings = {}

        self._load()

    def _load(self):
        """Load knowledge and embeddings."""
        # Load knowledge
        if self.knowledge_file.exists():
            try:
                with open(self.knowledge_file) as f:
                    self.knowledge = json.load(f)
            except json.JSONDecodeError:
                print("Warning: Could not parse knowledge.json", file=sys.stderr)

        # Try to load embeddings
        if NUMPY_AVAILABLE and self.embeddings_file.exists():
            try:
                data = np.load(self.embeddings_file, allow_pickle=True)
                self.embeddings = {
                    'facts': data.get('facts', np.array([])),
                    'decisions': data.get('decisions', np.array([])),
                    'patterns': data.get('patterns', np.array([]))
                }
            except Exception as e:
                print(f"Warning: Could not load embeddings: {e}", file=sys.stderr)
                self.embeddings = {}

    def _get_encoder(self):
        """Lazy load the encoder model."""
        if self.encoder is None and EMBEDDINGS_AVAILABLE:
            try:
                # Use a small, fast model
                self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
            except Exception as e:
                print(f"Warning: Could not load encoder: {e}", file=sys.stderr)
        return self.encoder

    def _save_knowledge(self):
        """Save knowledge to file."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        with open(self.knowledge_file, 'w') as f:
            json.dump(self.knowledge, f, indent=2)

    def _save_embeddings(self):
        """Save embeddings to file."""
        if NUMPY_AVAILABLE and self.embeddings:
            np.savez(
                self.embeddings_file,
                facts=self.embeddings.get('facts', np.array([])),
                decisions=self.embeddings.get('decisions', np.array([])),
                patterns=self.embeddings.get('patterns', np.array([]))
            )

    def rebuild_embeddings(self) -> Dict[str, int]:
        """Rebuild all embeddings from scratch."""
        encoder = self._get_encoder()
        if not encoder or not NUMPY_AVAILABLE:
            return {"status": "unavailable", "reason": "sentence-transformers not installed"}

        counts = {}

        for category in ['facts', 'decisions', 'patterns']:
            items = self.knowledge.get(category, [])
            if items:
                contents = [item.get('content', '') for item in items]
                try:
                    self.embeddings[category] = encoder.encode(contents)
                    counts[category] = len(contents)
                except Exception as e:
                    print(f"Warning: Could not encode {category}: {e}", file=sys.stderr)
                    self.embeddings[category] = np.array([])
                    counts[category] = 0
            else:
                self.embeddings[category] = np.array([])
                counts[category] = 0

        self._save_embeddings()
        return {"status": "success", "counts": counts}

    def persist(self, content: str, category: str, tags: List[str],
                confidence: float = 0.7, metadata: Optional[Dict] = None) -> int:
        """
        Add new knowledge item with optional embedding.

        Args:
            content: The knowledge content to store
            category: One of 'facts', 'decisions', 'patterns'
            tags: List of tags for categorization
            confidence: Confidence score (0-1)
            metadata: Optional additional metadata

        Returns:
            ID of the new entry
        """
        if category not in ['facts', 'decisions', 'patterns']:
            raise ValueError(f"Invalid category: {category}")

        # Generate ID
        existing_ids = [item.get('id', 0) for item in self.knowledge.get(category, [])]
        new_id = max(existing_ids, default=-1) + 1

        # Create entry
        entry = {
            "id": new_id,
            "content": content,
            "tags": tags,
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }

        if metadata:
            entry["metadata"] = metadata

        # Add to knowledge
        if category not in self.knowledge:
            self.knowledge[category] = []
        self.knowledge[category].append(entry)

        # Update embedding
        encoder = self._get_encoder()
        if encoder and NUMPY_AVAILABLE:
            try:
                new_vec = encoder.encode([content])
                category_key = category

                if category_key in self.embeddings and len(self.embeddings[category_key]) > 0:
                    self.embeddings[category_key] = np.vstack([
                        self.embeddings[category_key],
                        new_vec
                    ])
                else:
                    self.embeddings[category_key] = new_vec

                self._save_embeddings()
            except Exception as e:
                print(f"Warning: Could not update embedding: {e}", file=sys.stderr)

        self._save_knowledge()
        return new_id

    def query(self, query: str, category: str = 'all', limit: int = 5,
              min_confidence: float = 0.5, min_similarity: float = 0.3) -> List[Dict]:
        """
        Semantic search across knowledge.

        Args:
            query: Search query
            category: Category to search ('all', 'facts', 'decisions', 'patterns')
            limit: Maximum results to return
            min_confidence: Minimum confidence score for results
            min_similarity: Minimum similarity score for results

        Returns:
            List of matching knowledge items with similarity scores
        """
        encoder = self._get_encoder()
        categories = [category] if category != 'all' else ['facts', 'decisions', 'patterns']

        results = []

        # Try semantic search first
        if encoder and NUMPY_AVAILABLE and self.embeddings:
            try:
                query_vec = encoder.encode([query])

                for cat in categories:
                    items = self.knowledge.get(cat, [])
                    vecs = self.embeddings.get(cat)

                    if vecs is None or len(vecs) == 0 or len(items) == 0:
                        continue

                    # Ensure dimensions match
                    if len(vecs) != len(items):
                        continue

                    # Cosine similarity
                    # Normalize vectors
                    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-8)
                    vecs_norm = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-8)

                    similarities = np.dot(vecs_norm, query_norm.T).flatten()

                    for idx, sim in enumerate(similarities):
                        if sim >= min_similarity and idx < len(items):
                            item = items[idx]
                            if item.get('confidence', 1.0) >= min_confidence:
                                results.append({
                                    **item,
                                    'category': cat,
                                    'similarity': float(sim),
                                    'search_type': 'semantic'
                                })

                # Sort by similarity and return top results
                results.sort(key=lambda x: x['similarity'], reverse=True)
                return results[:limit]

            except Exception as e:
                print(f"Semantic search failed, falling back to keyword: {e}", file=sys.stderr)

        # Fallback to keyword search
        return self._keyword_search(query, categories, limit, min_confidence)

    def _keyword_search(self, query: str, categories: List[str],
                        limit: int, min_confidence: float) -> List[Dict]:
        """Keyword-based fallback search."""
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for cat in categories:
            items = self.knowledge.get(cat, [])
            for item in items:
                content = item.get('content', '').lower()
                tags = [t.lower() for t in item.get('tags', [])]

                # Calculate keyword match score
                content_words = set(content.split())
                tag_set = set(tags)

                word_matches = len(query_words & content_words)
                tag_matches = len(query_words & tag_set)

                if word_matches > 0 or tag_matches > 0:
                    # Simple scoring: word matches + weighted tag matches
                    score = (word_matches * 0.1) + (tag_matches * 0.3)
                    score = min(1.0, score)

                    if item.get('confidence', 1.0) >= min_confidence:
                        results.append({
                            **item,
                            'category': cat,
                            'similarity': score,
                            'search_type': 'keyword'
                        })

        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:limit]

    def link(self, from_id: str, to_id: str, relationship: str,
             strength: float = 0.5) -> bool:
        """
        Create semantic link between knowledge items.

        Args:
            from_id: Source item ID (format: "category:id")
            to_id: Target item ID (format: "category:id")
            relationship: Type of relationship
            strength: Link strength (0-1)

        Returns:
            Success status
        """
        # Load or initialize graph
        graph = {"nodes": {}, "edges": []}
        if self.graph_file.exists():
            try:
                with open(self.graph_file) as f:
                    graph = json.load(f)
            except json.JSONDecodeError:
                pass

        # Add edge
        edge = {
            "from": from_id,
            "to": to_id,
            "relationship": relationship,
            "strength": strength,
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }

        # Check for existing edge
        existing = [e for e in graph.get("edges", [])
                   if e["from"] == from_id and e["to"] == to_id]
        if existing:
            # Update existing
            existing[0].update(edge)
        else:
            graph.setdefault("edges", []).append(edge)

        # Save graph
        with open(self.graph_file, 'w') as f:
            json.dump(graph, f, indent=2)

        return True

    def get_linked(self, item_id: str, relationship: Optional[str] = None) -> List[Dict]:
        """Get items linked to the given item."""
        if not self.graph_file.exists():
            return []

        try:
            with open(self.graph_file) as f:
                graph = json.load(f)
        except json.JSONDecodeError:
            return []

        links = []
        for edge in graph.get("edges", []):
            if edge["from"] == item_id or edge["to"] == item_id:
                if relationship is None or edge.get("relationship") == relationship:
                    links.append(edge)

        return links

    def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        stats = {
            "facts": len(self.knowledge.get('facts', [])),
            "decisions": len(self.knowledge.get('decisions', [])),
            "patterns": len(self.knowledge.get('patterns', [])),
            "projects": len(self.knowledge.get('projects', {})),
            "embeddings_available": EMBEDDINGS_AVAILABLE and NUMPY_AVAILABLE,
            "embeddings_loaded": bool(self.embeddings)
        }

        if self.embeddings:
            stats["embedded_facts"] = len(self.embeddings.get('facts', []))
            stats["embedded_decisions"] = len(self.embeddings.get('decisions', []))
            stats["embedded_patterns"] = len(self.embeddings.get('patterns', []))

        return stats


def main():
    """CLI interface for vector memory."""
    if len(sys.argv) < 2:
        print("Usage: memory-api.py <command> [args]")
        print("")
        print("Commands:")
        print("  query <text>           Search knowledge semantically")
        print("  persist <content> <category> <tags...>  Add new knowledge")
        print("  rebuild                Rebuild all embeddings")
        print("  stats                  Show memory statistics")
        print("  link <from> <to> <rel> Create link between items")
        return

    cmd = sys.argv[1]
    mem = VectorMemory()

    if cmd == "query":
        if len(sys.argv) < 3:
            print("Usage: memory-api.py query <text> [category] [limit]")
            return

        query = sys.argv[2]
        category = sys.argv[3] if len(sys.argv) > 3 else 'all'
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 5

        results = mem.query(query, category=category, limit=limit)

        if results:
            print(f"Found {len(results)} results:")
            print("-" * 50)
            for r in results:
                print(f"[{r['category']}] ({r['similarity']:.2f}) {r['content'][:100]}")
                if r.get('tags'):
                    print(f"  Tags: {', '.join(r['tags'])}")
                print()
        else:
            print("No results found")

    elif cmd == "persist":
        if len(sys.argv) < 5:
            print("Usage: memory-api.py persist <content> <category> <tag1> [tag2...]")
            return

        content = sys.argv[2]
        category = sys.argv[3]
        tags = sys.argv[4:]

        new_id = mem.persist(content, category, tags)
        print(f"Persisted to {category} with ID: {new_id}")

    elif cmd == "rebuild":
        print("Rebuilding embeddings...")
        result = mem.rebuild_embeddings()
        print(json.dumps(result, indent=2))

    elif cmd == "stats":
        stats = mem.get_stats()
        print("Vector Memory Statistics")
        print("-" * 30)
        for key, value in stats.items():
            print(f"  {key}: {value}")

    elif cmd == "link":
        if len(sys.argv) < 5:
            print("Usage: memory-api.py link <from_id> <to_id> <relationship>")
            return

        from_id = sys.argv[2]
        to_id = sys.argv[3]
        relationship = sys.argv[4]

        success = mem.link(from_id, to_id, relationship)
        print(f"Link created: {success}")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
