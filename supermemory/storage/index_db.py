#!/usr/bin/env python3
"""
Supermemory Storage - SQLite unified index

Provides:
- Memory items storage with FTS5 full-text search
- Memory links for connections between items
- Review tracking for spaced repetition
- Error patterns catalog
"""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import hashlib


DB_PATH = Path.home() / ".claude" / "memory" / "supermemory.db"


class MemoryDB:
    """SQLite database for supermemory."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_conn()
        try:
            # Main memory items table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    content TEXT NOT NULL,
                    date DATE,
                    project TEXT,
                    quality REAL DEFAULT 0,
                    embedding_id INTEGER,
                    tags TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Memory links for connections
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_id TEXT NOT NULL,
                    to_id TEXT NOT NULL,
                    link_type TEXT NOT NULL,
                    strength REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (from_id) REFERENCES memory_items(id),
                    FOREIGN KEY (to_id) REFERENCES memory_items(id),
                    UNIQUE(from_id, to_id, link_type)
                )
            """)

            # Full-text search table
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    id,
                    content,
                    tags,
                    source,
                    project,
                    content=memory_items,
                    content_rowid=rowid
                )
            """)

            # Triggers to keep FTS in sync
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_items_ai AFTER INSERT ON memory_items BEGIN
                    INSERT INTO memory_fts(rowid, id, content, tags, source, project)
                    VALUES (new.rowid, new.id, new.content, new.tags, new.source, new.project);
                END
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_items_ad AFTER DELETE ON memory_items BEGIN
                    INSERT INTO memory_fts(memory_fts, rowid, id, content, tags, source, project)
                    VALUES ('delete', old.rowid, old.id, old.content, old.tags, old.source, old.project);
                END
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_items_au AFTER UPDATE ON memory_items BEGIN
                    INSERT INTO memory_fts(memory_fts, rowid, id, content, tags, source, project)
                    VALUES ('delete', old.rowid, old.id, old.content, old.tags, old.source, old.project);
                    INSERT INTO memory_fts(rowid, id, content, tags, source, project)
                    VALUES (new.rowid, new.id, new.content, new.tags, new.source, new.project);
                END
            """)

            # Spaced repetition reviews table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    category TEXT,
                    ease_factor REAL DEFAULT 2.5,
                    interval_days INTEGER DEFAULT 1,
                    repetitions INTEGER DEFAULT 0,
                    next_review DATE,
                    last_review DATE,
                    source_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Error patterns table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS error_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    count INTEGER DEFAULT 1,
                    solution TEXT,
                    last_seen DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(category, pattern)
                )
            """)

            # Learnings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learnings (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    category TEXT,
                    session_id TEXT,
                    project TEXT,
                    quality REAL,
                    date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes for common queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_items_date ON memory_items(date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_items_project ON memory_items(project)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_items_source ON memory_items(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_next ON reviews(next_review)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_learnings_project ON learnings(project)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_learnings_date ON learnings(date)")

            conn.commit()
        finally:
            conn.close()

    def _generate_id(self, content: str, source: str) -> str:
        """Generate unique ID from content hash."""
        hash_input = f"{source}:{content}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    # ═══════════════════════════════════════════════════════════════
    # Memory Items CRUD
    # ═══════════════════════════════════════════════════════════════

    def add_memory(self, source: str, content: str, date: Optional[str] = None,
                   project: Optional[str] = None, quality: float = 0,
                   tags: Optional[list] = None, metadata: Optional[dict] = None) -> str:
        """Add a memory item."""
        item_id = self._generate_id(content, source)
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO memory_items
                (id, source, content, date, project, quality, tags, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                item_id, source, content, date, project, quality,
                json.dumps(tags) if tags else None,
                json.dumps(metadata) if metadata else None
            ))
            conn.commit()
            return item_id
        finally:
            conn.close()

    def get_memory(self, item_id: str) -> Optional[dict]:
        """Get a memory item by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM memory_items WHERE id = ?", (item_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def search_fts(self, query: str, limit: int = 10,
                   source: Optional[str] = None,
                   project: Optional[str] = None) -> list[dict]:
        """Full-text search using FTS5."""
        conn = self._get_conn()
        try:
            # Build query with optional filters
            sql = """
                SELECT m.*, bm25(memory_fts) as score
                FROM memory_fts f
                JOIN memory_items m ON f.id = m.id
                WHERE memory_fts MATCH ?
            """
            params = [query]

            if source:
                sql += " AND m.source = ?"
                params.append(source)
            if project:
                sql += " AND m.project = ?"
                params.append(project)

            sql += " ORDER BY score LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.OperationalError:
            # FTS query syntax error, fall back to LIKE
            return self.search_like(query, limit, source, project)
        finally:
            conn.close()

    def search_like(self, query: str, limit: int = 10,
                    source: Optional[str] = None,
                    project: Optional[str] = None) -> list[dict]:
        """Fallback LIKE search."""
        conn = self._get_conn()
        try:
            sql = "SELECT *, 1.0 as score FROM memory_items WHERE content LIKE ?"
            params = [f"%{query}%"]

            if source:
                sql += " AND source = ?"
                params.append(source)
            if project:
                sql += " AND project = ?"
                params.append(project)

            sql += " ORDER BY date DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_memories_by_date_range(self, start_date: str, end_date: str,
                                   project: Optional[str] = None) -> list[dict]:
        """Get memories in date range."""
        conn = self._get_conn()
        try:
            sql = "SELECT * FROM memory_items WHERE date BETWEEN ? AND ?"
            params = [start_date, end_date]

            if project:
                sql += " AND project = ?"
                params.append(project)

            sql += " ORDER BY date DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════════════════
    # Memory Links
    # ═══════════════════════════════════════════════════════════════

    def add_link(self, from_id: str, to_id: str, link_type: str, strength: float = 1.0):
        """Add a link between memory items."""
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO memory_links (from_id, to_id, link_type, strength)
                VALUES (?, ?, ?, ?)
            """, (from_id, to_id, link_type, strength))
            conn.commit()
        finally:
            conn.close()

    def get_linked_memories(self, item_id: str, link_type: Optional[str] = None) -> list[dict]:
        """Get memories linked to an item."""
        conn = self._get_conn()
        try:
            sql = """
                SELECT m.*, l.link_type, l.strength
                FROM memory_links l
                JOIN memory_items m ON l.to_id = m.id
                WHERE l.from_id = ?
            """
            params = [item_id]

            if link_type:
                sql += " AND l.link_type = ?"
                params.append(link_type)

            sql += " ORDER BY l.strength DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════════════════
    # Reviews (Spaced Repetition)
    # ═══════════════════════════════════════════════════════════════

    def add_review_item(self, content: str, category: Optional[str] = None,
                        source_id: Optional[str] = None) -> str:
        """Add item to spaced repetition queue."""
        item_id = self._generate_id(content, "review")
        today = datetime.now().strftime("%Y-%m-%d")

        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR IGNORE INTO reviews
                (id, content, category, source_id, next_review)
                VALUES (?, ?, ?, ?, ?)
            """, (item_id, content, category, source_id, today))
            conn.commit()
            return item_id
        finally:
            conn.close()

    def get_due_reviews(self, limit: int = 10) -> list[dict]:
        """Get reviews due today or earlier."""
        today = datetime.now().strftime("%Y-%m-%d")
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM reviews
                WHERE next_review <= ?
                ORDER BY next_review ASC, ease_factor ASC
                LIMIT ?
            """, (today, limit)).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def update_review(self, item_id: str, ease_factor: float,
                      interval_days: int, repetitions: int, next_review: str):
        """Update review item after review."""
        today = datetime.now().strftime("%Y-%m-%d")
        conn = self._get_conn()
        try:
            conn.execute("""
                UPDATE reviews
                SET ease_factor = ?, interval_days = ?, repetitions = ?,
                    next_review = ?, last_review = ?
                WHERE id = ?
            """, (ease_factor, interval_days, repetitions, next_review, today, item_id))
            conn.commit()
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════════════════
    # Error Patterns
    # ═══════════════════════════════════════════════════════════════

    def add_error_pattern(self, category: str, pattern: str,
                          solution: Optional[str] = None):
        """Add or update error pattern."""
        today = datetime.now().strftime("%Y-%m-%d")
        conn = self._get_conn()
        try:
            # Try to increment existing
            result = conn.execute("""
                UPDATE error_patterns
                SET count = count + 1, last_seen = ?, solution = COALESCE(?, solution)
                WHERE category = ? AND pattern = ?
            """, (today, solution, category, pattern))

            if result.rowcount == 0:
                # Insert new
                conn.execute("""
                    INSERT INTO error_patterns (category, pattern, solution, last_seen)
                    VALUES (?, ?, ?, ?)
                """, (category, pattern, solution, today))

            conn.commit()
        finally:
            conn.close()

    def find_error_patterns(self, text: str, limit: int = 5) -> list[dict]:
        """Find matching error patterns."""
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM error_patterns
                WHERE ? LIKE '%' || pattern || '%'
                   OR pattern LIKE '%' || ? || '%'
                ORDER BY count DESC
                LIMIT ?
            """, (text, text[:50], limit)).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_top_error_patterns(self, limit: int = 10) -> list[dict]:
        """Get most common error patterns."""
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM error_patterns
                ORDER BY count DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════════════════
    # Learnings
    # ═══════════════════════════════════════════════════════════════

    def add_learning(self, content: str, category: Optional[str] = None,
                     session_id: Optional[str] = None, project: Optional[str] = None,
                     quality: Optional[float] = None, date: Optional[str] = None) -> str:
        """Add a learning entry."""
        item_id = self._generate_id(content, "learning")
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO learnings
                (id, content, category, session_id, project, quality, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (item_id, content, category, session_id, project, quality, date))
            conn.commit()
            return item_id
        finally:
            conn.close()

    def get_learnings(self, project: Optional[str] = None,
                      category: Optional[str] = None,
                      limit: int = 50) -> list[dict]:
        """Get learnings with optional filters."""
        conn = self._get_conn()
        try:
            sql = "SELECT * FROM learnings WHERE 1=1"
            params = []

            if project:
                sql += " AND project = ?"
                params.append(project)
            if category:
                sql += " AND category = ?"
                params.append(category)

            sql += " ORDER BY date DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════════════════
    # Statistics
    # ═══════════════════════════════════════════════════════════════

    def get_stats(self) -> dict:
        """Get database statistics."""
        conn = self._get_conn()
        try:
            stats = {}

            # Counts
            stats['memory_items'] = conn.execute(
                "SELECT COUNT(*) FROM memory_items"
            ).fetchone()[0]

            stats['learnings'] = conn.execute(
                "SELECT COUNT(*) FROM learnings"
            ).fetchone()[0]

            stats['error_patterns'] = conn.execute(
                "SELECT COUNT(*) FROM error_patterns"
            ).fetchone()[0]

            stats['review_items'] = conn.execute(
                "SELECT COUNT(*) FROM reviews"
            ).fetchone()[0]

            stats['memory_links'] = conn.execute(
                "SELECT COUNT(*) FROM memory_links"
            ).fetchone()[0]

            # Project breakdown
            rows = conn.execute("""
                SELECT project, COUNT(*) as cnt
                FROM memory_items
                WHERE project IS NOT NULL
                GROUP BY project
            """).fetchall()
            stats['projects'] = {row['project']: row['cnt'] for row in rows}

            # Database size
            stats['db_size_mb'] = os.path.getsize(self.db_path) / (1024 * 1024)

            return stats
        finally:
            conn.close()

    def clear_all(self):
        """Clear all data (for testing)."""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM memory_links")
            conn.execute("DELETE FROM memory_items")
            conn.execute("DELETE FROM reviews")
            conn.execute("DELETE FROM error_patterns")
            conn.execute("DELETE FROM learnings")
            conn.commit()
        finally:
            conn.close()
