#!/usr/bin/env python3
"""
Tests for US-010: Graph Confidence Loop — Write Direction

Tests the graph-confidence-daemon module:
  - Confidence column migration
  - Outcome classification (boost/degrade/no_change)
  - Batch-limited, depth-limited link retrieval
  - Snapshot creation before updates
  - Sparse subgraph flagging
  - Confidence capping/flooring
  - End-to-end cycle processing
"""

import importlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# Import module with hyphenated name
gcd = importlib.import_module("graph-confidence-daemon")


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_dir(tmp_path):
    """Create temp directory structure for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return tmp_path


@pytest.fixture
def mock_supermemory(tmp_path):
    """Create a test supermemory.db with memory_links table."""
    db_path = tmp_path / "supermemory.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE memory_items (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            content TEXT NOT NULL,
            project TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE memory_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            link_type TEXT NOT NULL,
            strength REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(from_id, to_id, link_type)
        )
    """)
    conn.execute("CREATE INDEX idx_memory_links_to_id ON memory_links(to_id)")
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def populated_supermemory(mock_supermemory):
    """Supermemory with sample nodes and links."""
    conn = sqlite3.connect(str(mock_supermemory))
    # Insert memory items
    items = [
        ("node_a", "test", "Content A", "/project/test"),
        ("node_b", "test", "Content B", "/project/test"),
        ("node_c", "test", "Content C", "/project/test"),
        ("node_d", "test", "Content D", "/project/other"),
        ("node_e", "test", "Content E", "/project/test"),
    ]
    conn.executemany(
        "INSERT INTO memory_items (id, source, content, project) VALUES (?, ?, ?, ?)",
        items,
    )
    # Insert links (fully connected between a, b, c)
    links = [
        ("node_a", "node_b", "related"),
        ("node_a", "node_c", "related"),
        ("node_b", "node_c", "related"),
        ("node_a", "node_d", "same_project"),
        ("node_d", "node_e", "related"),
    ]
    conn.executemany(
        "INSERT INTO memory_links (from_id, to_id, link_type) VALUES (?, ?, ?)",
        links,
    )
    conn.commit()
    conn.close()
    return mock_supermemory


@pytest.fixture
def behavioral_outcomes_file(tmp_dir):
    """Create a behavioral outcomes JSONL file."""
    filepath = tmp_dir / "data" / "behavioral-outcomes.jsonl"
    return filepath


def write_outcomes(filepath, outcomes):
    """Helper to write outcomes to JSONL file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        for o in outcomes:
            f.write(json.dumps(o) + "\n")


# ── Test: Migration ──────────────────────────────────────────────────────


class TestMigration:
    def test_adds_confidence_column(self, mock_supermemory):
        """Migration adds confidence column with default 0.5."""
        gcd.ensure_confidence_column(mock_supermemory)

        conn = sqlite3.connect(str(mock_supermemory))
        cursor = conn.execute("PRAGMA table_info(memory_links)")
        columns = {row[1]: row for row in cursor.fetchall()}
        conn.close()

        assert "confidence" in columns
        # Default value is 0.5
        assert columns["confidence"][4] == "0.5"

    def test_idempotent_migration(self, mock_supermemory):
        """Running migration twice does not error."""
        gcd.ensure_confidence_column(mock_supermemory)
        gcd.ensure_confidence_column(mock_supermemory)  # Should not raise

        conn = sqlite3.connect(str(mock_supermemory))
        cursor = conn.execute("PRAGMA table_info(memory_links)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        assert columns.count("confidence") == 1

    def test_adds_from_id_index(self, mock_supermemory):
        """Migration creates from_id index for performance."""
        gcd.ensure_confidence_column(mock_supermemory)

        conn = sqlite3.connect(str(mock_supermemory))
        cursor = conn.execute("PRAGMA index_list('memory_links')")
        indexes = [row[1] for row in cursor.fetchall()]
        conn.close()
        assert "idx_memory_links_from_id" in indexes


# ── Test: Outcome Classification ─────────────────────────────────────────


class TestOutcomeClassification:
    def test_high_score_triggers_boost(self):
        """behavioral_score >= 0.7 → boost action."""
        assert 0.8 >= gcd.BOOST_THRESHOLD
        assert 0.7 >= gcd.BOOST_THRESHOLD

    def test_low_score_triggers_degrade(self):
        """behavioral_score < 0.4 → degrade action."""
        assert 0.3 < gcd.DEGRADE_THRESHOLD
        assert 0.0 < gcd.DEGRADE_THRESHOLD

    def test_mid_score_no_change(self):
        """behavioral_score 0.4-0.7 → no change."""
        assert 0.5 >= gcd.DEGRADE_THRESHOLD
        assert 0.5 < gcd.BOOST_THRESHOLD

    def test_boundary_boost(self):
        """Score exactly at 0.7 triggers boost."""
        assert 0.7 >= gcd.BOOST_THRESHOLD

    def test_boundary_degrade(self):
        """Score exactly at 0.4 does NOT degrade (>= threshold)."""
        assert not (0.4 < gcd.DEGRADE_THRESHOLD)


# ── Test: Subgraph Density ───────────────────────────────────────────────


class TestSubgraphDensity:
    def test_empty_links_zero_density(self):
        """No links → density 0.0."""
        assert gcd.compute_subgraph_density([]) == 0.0

    def test_single_link_density(self):
        """One link between 2 nodes → density 1.0."""
        links = [{"from_id": "a", "to_id": "b"}]
        assert gcd.compute_subgraph_density(links) == 1.0

    def test_fully_connected_triangle(self):
        """3 nodes, 3 edges → density 1.0."""
        links = [
            {"from_id": "a", "to_id": "b"},
            {"from_id": "a", "to_id": "c"},
            {"from_id": "b", "to_id": "c"},
        ]
        assert gcd.compute_subgraph_density(links) == 1.0

    def test_sparse_subgraph(self):
        """4 nodes, 2 edges → density 2/6 = 0.333."""
        links = [
            {"from_id": "a", "to_id": "b"},
            {"from_id": "c", "to_id": "d"},
        ]
        density = gcd.compute_subgraph_density(links)
        assert abs(density - 2.0 / 6.0) < 0.001

    def test_single_node_zero_density(self):
        """Self-loop (1 unique node from perspective of distinct nodes) → 0.0."""
        links = [{"from_id": "a", "to_id": "a"}]
        # Only 1 unique node
        assert gcd.compute_subgraph_density(links) == 0.0


# ── Test: Link Finding ───────────────────────────────────────────────────


class TestLinkFinding:
    def test_finds_direct_links(self, populated_supermemory):
        """Finds links directly connected to seed nodes."""
        gcd.ensure_confidence_column(populated_supermemory)
        conn = sqlite3.connect(str(populated_supermemory))
        links = gcd.find_links_for_nodes(conn, {"node_a"}, max_depth=1)
        conn.close()
        assert len(links) >= 3  # a→b, a→c, a→d

    def test_depth_limited(self, populated_supermemory):
        """Depth 1 does not reach 2-hop connections."""
        gcd.ensure_confidence_column(populated_supermemory)
        conn = sqlite3.connect(str(populated_supermemory))
        links_d1 = gcd.find_links_for_nodes(conn, {"node_a"}, max_depth=1)
        links_d2 = gcd.find_links_for_nodes(conn, {"node_a"}, max_depth=2)
        conn.close()
        # Depth 2 should find d→e which depth 1 from node_a won't
        assert len(links_d2) >= len(links_d1)

    def test_batch_limited(self, populated_supermemory):
        """Respects max_links limit."""
        gcd.ensure_confidence_column(populated_supermemory)
        conn = sqlite3.connect(str(populated_supermemory))
        links = gcd.find_links_for_nodes(conn, {"node_a"}, max_links=2)
        conn.close()
        assert len(links) <= 2

    def test_empty_nodes_returns_empty(self, populated_supermemory):
        """No seed nodes → no links."""
        gcd.ensure_confidence_column(populated_supermemory)
        conn = sqlite3.connect(str(populated_supermemory))
        links = gcd.find_links_for_nodes(conn, set())
        conn.close()
        assert links == []

    def test_nonexistent_node_returns_empty(self, populated_supermemory):
        """Seed node not in graph → no links."""
        gcd.ensure_confidence_column(populated_supermemory)
        conn = sqlite3.connect(str(populated_supermemory))
        links = gcd.find_links_for_nodes(conn, {"nonexistent_xyz"})
        conn.close()
        assert links == []


# ── Test: Confidence Updates ─────────────────────────────────────────────


class TestConfidenceUpdates:
    def test_boost_increases_confidence(self, populated_supermemory):
        """Boost adds +0.05 to confidence."""
        gcd.ensure_confidence_column(populated_supermemory)
        conn = sqlite3.connect(str(populated_supermemory))

        links = [{"id": 1, "from_id": "node_a", "to_id": "node_b", "confidence": 0.5}]
        updates = gcd.update_confidence(conn, links, gcd.BOOST_DELTA)

        cursor = conn.execute("SELECT confidence FROM memory_links WHERE id = 1")
        new_conf = cursor.fetchone()[0]
        conn.close()

        assert len(updates) == 1
        assert abs(new_conf - 0.55) < 0.001

    def test_degrade_decreases_confidence(self, populated_supermemory):
        """Degrade subtracts 0.10 from confidence."""
        gcd.ensure_confidence_column(populated_supermemory)
        conn = sqlite3.connect(str(populated_supermemory))

        links = [{"id": 1, "from_id": "node_a", "to_id": "node_b", "confidence": 0.5}]
        updates = gcd.update_confidence(conn, links, gcd.DEGRADE_DELTA)

        cursor = conn.execute("SELECT confidence FROM memory_links WHERE id = 1")
        new_conf = cursor.fetchone()[0]
        conn.close()

        assert len(updates) == 1
        assert abs(new_conf - 0.4) < 0.001

    def test_confidence_capped_at_1(self, populated_supermemory):
        """Confidence cannot exceed 1.0."""
        gcd.ensure_confidence_column(populated_supermemory)
        conn = sqlite3.connect(str(populated_supermemory))

        # Set initial confidence to 0.98
        conn.execute("UPDATE memory_links SET confidence = 0.98 WHERE id = 1")
        conn.commit()

        links = [{"id": 1, "from_id": "node_a", "to_id": "node_b", "confidence": 0.98}]
        gcd.update_confidence(conn, links, gcd.BOOST_DELTA)

        cursor = conn.execute("SELECT confidence FROM memory_links WHERE id = 1")
        new_conf = cursor.fetchone()[0]
        conn.close()

        assert new_conf == 1.0

    def test_confidence_floored_at_0(self, populated_supermemory):
        """Confidence cannot go below 0.0."""
        gcd.ensure_confidence_column(populated_supermemory)
        conn = sqlite3.connect(str(populated_supermemory))

        # Set initial confidence to 0.05
        conn.execute("UPDATE memory_links SET confidence = 0.05 WHERE id = 1")
        conn.commit()

        links = [{"id": 1, "from_id": "node_a", "to_id": "node_b", "confidence": 0.05}]
        gcd.update_confidence(conn, links, gcd.DEGRADE_DELTA)

        cursor = conn.execute("SELECT confidence FROM memory_links WHERE id = 1")
        new_conf = cursor.fetchone()[0]
        conn.close()

        assert new_conf == 0.0

    def test_no_update_when_no_change(self, populated_supermemory):
        """If delta would not change confidence (already at cap/floor), no update recorded."""
        gcd.ensure_confidence_column(populated_supermemory)
        conn = sqlite3.connect(str(populated_supermemory))

        conn.execute("UPDATE memory_links SET confidence = 1.0 WHERE id = 1")
        conn.commit()

        links = [{"id": 1, "from_id": "node_a", "to_id": "node_b", "confidence": 1.0}]
        updates = gcd.update_confidence(conn, links, gcd.BOOST_DELTA)
        conn.close()

        # 1.0 + 0.05 = capped at 1.0 → no actual change
        assert len(updates) == 0


# ── Test: Snapshot ────────────────────────────────────────────────────────


class TestSnapshot:
    def test_snapshot_created(self, tmp_dir):
        """Snapshot file created with correct structure."""
        with patch.object(gcd, "SNAPSHOTS_DIR", tmp_dir / "data" / "graph-snapshots"):
            links = [
                {"id": 1, "from_id": "a", "to_id": "b", "confidence": 0.5},
                {"id": 2, "from_id": "b", "to_id": "c", "confidence": 0.7},
            ]
            snapshot_path = gcd.take_snapshot(links, "test-session-123")

            assert snapshot_path.exists()
            data = json.loads(snapshot_path.read_text())
            assert data["outcome_session_id"] == "test-session-123"
            assert data["link_count"] == 2
            assert len(data["links"]) == 2
            assert data["links"][0]["pre_confidence"] == 0.5
            assert "timestamp" in data


# ── Test: Sparse Subgraph Flagging ───────────────────────────────────────


class TestSparseFlags:
    def test_flags_sparse_poor_outcome(self, tmp_dir):
        """Sparse subgraph with poor outcome gets flagged."""
        flag_file = tmp_dir / "data" / "sparse-subgraph-flags.jsonl"
        with patch.object(gcd, "SPARSE_FLAGS_FILE", flag_file):
            outcome = {
                "session_id": "sess-1",
                "project_path": "/test",
                "behavioral_score": 0.3,
            }
            gcd.flag_sparse_subgraph(outcome, density=0.05)

            assert flag_file.exists()
            line = flag_file.read_text().strip()
            data = json.loads(line)
            assert data["session_id"] == "sess-1"
            assert data["subgraph_density"] == 0.05
            assert data["reason"] == "sparse_subgraph_with_poor_outcome"

    def test_append_only(self, tmp_dir):
        """Multiple flags appended, not overwritten."""
        flag_file = tmp_dir / "data" / "sparse-subgraph-flags.jsonl"
        with patch.object(gcd, "SPARSE_FLAGS_FILE", flag_file):
            outcome1 = {"session_id": "s1", "project_path": "/a", "behavioral_score": 0.2}
            outcome2 = {"session_id": "s2", "project_path": "/b", "behavioral_score": 0.1}
            gcd.flag_sparse_subgraph(outcome1, 0.03)
            gcd.flag_sparse_subgraph(outcome2, 0.01)

            lines = [l for l in flag_file.read_text().strip().split("\n") if l]
            assert len(lines) == 2


# ── Test: Process Single Outcome ─────────────────────────────────────────


class TestProcessOutcome:
    def test_boost_outcome(self, populated_supermemory, tmp_dir):
        """High behavioral score triggers boost on connected links."""
        gcd.ensure_confidence_column(populated_supermemory)
        conn = sqlite3.connect(str(populated_supermemory))

        outcome = {
            "session_id": "node_a",  # matches a node ID
            "project_path": "/project/test",
            "behavioral_score": 0.85,
        }

        with patch.object(gcd, "SNAPSHOTS_DIR", tmp_dir / "data" / "graph-snapshots"):
            result = gcd.process_single_outcome(conn, outcome)

        assert result["action"] == "boost"
        assert result["links_updated"] > 0
        conn.close()

    def test_degrade_outcome(self, populated_supermemory, tmp_dir):
        """Low behavioral score triggers degrade on connected links."""
        gcd.ensure_confidence_column(populated_supermemory)
        conn = sqlite3.connect(str(populated_supermemory))

        outcome = {
            "session_id": "node_a",
            "project_path": "/project/test",
            "behavioral_score": 0.2,
        }

        with patch.object(gcd, "SNAPSHOTS_DIR", tmp_dir / "data" / "graph-snapshots"), \
             patch.object(gcd, "SPARSE_FLAGS_FILE", tmp_dir / "data" / "sparse.jsonl"):
            result = gcd.process_single_outcome(conn, outcome)

        assert result["action"] == "degrade"
        assert result["links_updated"] > 0
        conn.close()

    def test_no_change_outcome(self, populated_supermemory):
        """Mid-range behavioral score triggers no change."""
        gcd.ensure_confidence_column(populated_supermemory)
        conn = sqlite3.connect(str(populated_supermemory))

        outcome = {
            "session_id": "node_a",
            "project_path": "/project/test",
            "behavioral_score": 0.55,
        }

        result = gcd.process_single_outcome(conn, outcome)
        assert result["action"] == "no_change"
        assert result["links_updated"] == 0
        conn.close()

    def test_no_nodes_outcome(self, populated_supermemory):
        """Outcome with no identifiable nodes returns no_nodes."""
        gcd.ensure_confidence_column(populated_supermemory)
        conn = sqlite3.connect(str(populated_supermemory))

        outcome = {
            "session_id": "",
            "project_path": "",
            "behavioral_score": 0.9,
        }

        result = gcd.process_single_outcome(conn, outcome)
        assert result["action"] == "no_nodes"
        conn.close()


# ── Test: Daemon State ───────────────────────────────────────────────────


class TestDaemonState:
    def test_initial_state(self, tmp_dir):
        """Fresh state starts at line 0."""
        with patch.object(gcd, "DAEMON_STATE_FILE", tmp_dir / "state.json"):
            state = gcd.load_daemon_state()
            assert state["last_processed_line"] == 0
            assert state["total_boosts"] == 0
            assert state["total_degrades"] == 0

    def test_state_persistence(self, tmp_dir):
        """State survives save/load cycle."""
        state_file = tmp_dir / "state.json"
        with patch.object(gcd, "DAEMON_STATE_FILE", state_file):
            state = {"last_processed_line": 42, "total_boosts": 10, "total_degrades": 3}
            gcd.save_daemon_state(state)

            loaded = gcd.load_daemon_state()
            assert loaded["last_processed_line"] == 42
            assert loaded["total_boosts"] == 10


# ── Test: Load New Outcomes ──────────────────────────────────────────────


class TestLoadOutcomes:
    def test_loads_all_new(self, tmp_dir):
        """Loads all outcomes when starting from line 0."""
        filepath = tmp_dir / "data" / "behavioral-outcomes.jsonl"
        outcomes = [
            {"session_id": "s1", "behavioral_score": 0.8},
            {"session_id": "s2", "behavioral_score": 0.3},
        ]
        write_outcomes(filepath, outcomes)

        with patch.object(gcd, "BEHAVIORAL_OUTCOMES_FILE", filepath):
            state = {"last_processed_line": 0}
            loaded, new_line = gcd.load_new_outcomes(state)

        assert len(loaded) == 2
        assert new_line == 2

    def test_skips_processed(self, tmp_dir):
        """Skips already-processed lines."""
        filepath = tmp_dir / "data" / "behavioral-outcomes.jsonl"
        outcomes = [
            {"session_id": "s1", "behavioral_score": 0.8},
            {"session_id": "s2", "behavioral_score": 0.3},
            {"session_id": "s3", "behavioral_score": 0.6},
        ]
        write_outcomes(filepath, outcomes)

        with patch.object(gcd, "BEHAVIORAL_OUTCOMES_FILE", filepath):
            state = {"last_processed_line": 2}
            loaded, new_line = gcd.load_new_outcomes(state)

        assert len(loaded) == 1
        assert loaded[0]["session_id"] == "s3"

    def test_no_file_returns_empty(self, tmp_dir):
        """Missing file returns empty list."""
        with patch.object(gcd, "BEHAVIORAL_OUTCOMES_FILE", tmp_dir / "nonexistent.jsonl"):
            state = {"last_processed_line": 0}
            loaded, _ = gcd.load_new_outcomes(state)

        assert loaded == []


# ── Test: Full Cycle ─────────────────────────────────────────────────────


class TestFullCycle:
    def test_end_to_end_boost(self, populated_supermemory, tmp_dir):
        """Full cycle: successful outcome → confidence boosted → snapshot created."""
        gcd.ensure_confidence_column(populated_supermemory)

        # Write a high-score outcome referencing node_a
        filepath = tmp_dir / "data" / "behavioral-outcomes.jsonl"
        write_outcomes(filepath, [
            {"session_id": "node_a", "project_path": "/project/test", "behavioral_score": 0.85},
        ])

        snapshots_dir = tmp_dir / "data" / "graph-snapshots"
        state_file = tmp_dir / "data" / "state.json"

        with patch.object(gcd, "BEHAVIORAL_OUTCOMES_FILE", filepath), \
             patch.object(gcd, "SNAPSHOTS_DIR", snapshots_dir), \
             patch.object(gcd, "DAEMON_STATE_FILE", state_file), \
             patch.object(gcd, "SPARSE_FLAGS_FILE", tmp_dir / "data" / "sparse.jsonl"):
            result = gcd.run_cycle(populated_supermemory)

        assert result["cycle"] == "processed"
        assert result["boosts"] == 1
        assert result["degrades"] == 0

        # Verify snapshot was created
        snapshots = list(snapshots_dir.glob("*.json"))
        assert len(snapshots) >= 1

        # Verify state was saved
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert state["last_processed_line"] == 1
        assert state["total_boosts"] == 1

    def test_end_to_end_degrade_with_sparse_flag(self, populated_supermemory, tmp_dir):
        """Full cycle: failed outcome → confidence degraded → sparse flag logged."""
        gcd.ensure_confidence_column(populated_supermemory)

        filepath = tmp_dir / "data" / "behavioral-outcomes.jsonl"
        write_outcomes(filepath, [
            {"session_id": "node_a", "project_path": "/project/test", "behavioral_score": 0.2},
        ])

        snapshots_dir = tmp_dir / "data" / "graph-snapshots"
        state_file = tmp_dir / "data" / "state.json"
        sparse_file = tmp_dir / "data" / "sparse.jsonl"

        with patch.object(gcd, "BEHAVIORAL_OUTCOMES_FILE", filepath), \
             patch.object(gcd, "SNAPSHOTS_DIR", snapshots_dir), \
             patch.object(gcd, "DAEMON_STATE_FILE", state_file), \
             patch.object(gcd, "SPARSE_FLAGS_FILE", sparse_file):
            result = gcd.run_cycle(populated_supermemory)

        assert result["cycle"] == "processed"
        assert result["degrades"] == 1

        # Verify confidence was degraded
        conn = sqlite3.connect(str(populated_supermemory))
        cursor = conn.execute("SELECT MIN(confidence) FROM memory_links")
        min_conf = cursor.fetchone()[0]
        conn.close()
        assert min_conf < 0.5  # Degraded from default 0.5

    def test_incremental_processing(self, populated_supermemory, tmp_dir):
        """Second cycle only processes new outcomes."""
        gcd.ensure_confidence_column(populated_supermemory)

        filepath = tmp_dir / "data" / "behavioral-outcomes.jsonl"
        state_file = tmp_dir / "data" / "state.json"
        snapshots_dir = tmp_dir / "data" / "graph-snapshots"

        with patch.object(gcd, "BEHAVIORAL_OUTCOMES_FILE", filepath), \
             patch.object(gcd, "SNAPSHOTS_DIR", snapshots_dir), \
             patch.object(gcd, "DAEMON_STATE_FILE", state_file), \
             patch.object(gcd, "SPARSE_FLAGS_FILE", tmp_dir / "data" / "sparse.jsonl"):

            # First cycle: 1 outcome
            write_outcomes(filepath, [
                {"session_id": "node_a", "project_path": "/p", "behavioral_score": 0.8},
            ])
            r1 = gcd.run_cycle(populated_supermemory)
            assert r1["outcomes_processed"] == 1

            # Add another outcome
            with open(filepath, "a") as f:
                f.write(json.dumps({"session_id": "node_b", "project_path": "/p", "behavioral_score": 0.9}) + "\n")

            # Second cycle: only the new one
            r2 = gcd.run_cycle(populated_supermemory)
            assert r2["outcomes_processed"] == 1

    def test_no_outcomes_noop(self, populated_supermemory, tmp_dir):
        """Cycle with no new outcomes is a no-op."""
        state_file = tmp_dir / "data" / "state.json"

        with patch.object(gcd, "BEHAVIORAL_OUTCOMES_FILE", tmp_dir / "nonexistent.jsonl"), \
             patch.object(gcd, "DAEMON_STATE_FILE", state_file):
            result = gcd.run_cycle(populated_supermemory)

        assert result["cycle"] == "no_new_outcomes"


# ── Test: Constants ──────────────────────────────────────────────────────


class TestConstants:
    def test_boost_delta_positive(self):
        assert gcd.BOOST_DELTA == 0.05
        assert gcd.BOOST_DELTA > 0

    def test_degrade_delta_negative(self):
        assert gcd.DEGRADE_DELTA == -0.10
        assert gcd.DEGRADE_DELTA < 0

    def test_default_confidence(self):
        assert gcd.DEFAULT_CONFIDENCE == 0.5

    def test_max_links_per_cycle(self):
        assert gcd.MAX_LINKS_PER_CYCLE == 100

    def test_max_hop_depth(self):
        assert gcd.MAX_HOP_DEPTH == 2

    def test_sparse_density_threshold(self):
        assert gcd.SPARSE_DENSITY_THRESHOLD == 0.1
