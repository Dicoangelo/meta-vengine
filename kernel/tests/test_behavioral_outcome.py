#!/usr/bin/env python3
"""
Tests for US-005: Behavioral Outcome Signal — Composite Score Extractor

Uses an in-memory SQLite database with mock session data to verify each
component scoring function independently and the composite scoring pipeline.
"""

import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add kernel to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import importlib
bo = importlib.import_module("behavioral-outcome")


def create_test_db():
    """Create an in-memory SQLite db mimicking claude.db schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            project_path TEXT,
            started_at DATETIME NOT NULL,
            model TEXT NOT NULL,
            message_count INTEGER DEFAULT 0,
            tool_count INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_read_tokens INTEGER DEFAULT 0,
            cache_write_tokens INTEGER DEFAULT 0,
            outcome TEXT,
            quality_score REAL,
            dq_score REAL,
            complexity REAL,
            cost_estimate REAL,
            metadata JSON,
            ended_at DATETIME,
            transcript_path TEXT,
            scanned_at DATETIME
        );

        CREATE TABLE tool_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            tool_name TEXT NOT NULL,
            success INTEGER NOT NULL,
            duration_ms INTEGER,
            error_message TEXT,
            context TEXT
        );

        CREATE TABLE activity_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            data TEXT,
            session_id TEXT
        );

        CREATE TABLE command_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            command TEXT NOT NULL,
            args TEXT,
            success INTEGER,
            execution_time_ms INTEGER
        );
    """)
    return conn


def make_session(conn, sid, outcome="success", model="sonnet",
                 message_count=50, complexity=0.5, quality_score=None,
                 project_path="/test/project",
                 started_at=None, ended_at=None):
    """Insert a mock session into the test db."""
    if started_at is None:
        started_at = "2026-03-10T10:00:00+00:00"
    if ended_at is None:
        ended_at = "2026-03-10T11:00:00+00:00"

    conn.execute(
        "INSERT INTO sessions (id, project_path, started_at, ended_at, model, "
        "message_count, outcome, quality_score, complexity) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (sid, project_path, started_at, ended_at, model,
         message_count, outcome, quality_score, complexity),
    )
    conn.commit()
    return conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()


def add_tool_events(conn, start_ts, end_ts, success_count, fail_count):
    """Add tool events within a timestamp range."""
    step = max(1, (end_ts - start_ts) // (success_count + fail_count + 1))
    ts = start_ts + step
    for _ in range(success_count):
        conn.execute(
            "INSERT INTO tool_events (timestamp, tool_name, success) VALUES (?, 'Bash', 1)",
            (ts,),
        )
        ts += step
    for _ in range(fail_count):
        conn.execute(
            "INSERT INTO tool_events (timestamp, tool_name, success) VALUES (?, 'Bash', 0)",
            (ts,),
        )
        ts += step
    conn.commit()


def add_command_event(conn, timestamp, command):
    """Add a command event."""
    conn.execute(
        "INSERT INTO command_events (timestamp, command, success) VALUES (?, ?, 1)",
        (timestamp, command),
    )
    conn.commit()


# --- Component Score Tests ---

class TestCompletionScore:
    def test_success(self):
        conn = create_test_db()
        s = make_session(conn, "s1", outcome="success")
        assert bo.compute_completion_score(s) == 1.0

    def test_completed(self):
        conn = create_test_db()
        s = make_session(conn, "s1", outcome="completed")
        assert bo.compute_completion_score(s) == 1.0

    def test_abandoned(self):
        conn = create_test_db()
        s = make_session(conn, "s1", outcome="abandoned")
        assert bo.compute_completion_score(s) == 0.0

    def test_partial(self):
        conn = create_test_db()
        s = make_session(conn, "s1", outcome="partial")
        assert bo.compute_completion_score(s) == 0.5

    def test_quick(self):
        conn = create_test_db()
        s = make_session(conn, "s1", outcome="quick")
        assert bo.compute_completion_score(s) == 0.5

    def test_none_outcome(self):
        conn = create_test_db()
        s = make_session(conn, "s1", outcome=None)
        assert bo.compute_completion_score(s) == 0.0


class TestToolSuccessRate:
    def test_all_success(self):
        conn = create_test_db()
        s = make_session(conn, "s1")
        # Session window: 2026-03-10 10:00-11:00 UTC → unix ~1773385200-1773388800
        start_ts = int(datetime.fromisoformat("2026-03-10T10:00:00+00:00").timestamp())
        end_ts = int(datetime.fromisoformat("2026-03-10T11:00:00+00:00").timestamp())
        add_tool_events(conn, start_ts, end_ts, 10, 0)
        assert bo.compute_tool_success_rate(conn, s) == 1.0

    def test_all_failure(self):
        conn = create_test_db()
        s = make_session(conn, "s1")
        start_ts = int(datetime.fromisoformat("2026-03-10T10:00:00+00:00").timestamp())
        end_ts = int(datetime.fromisoformat("2026-03-10T11:00:00+00:00").timestamp())
        add_tool_events(conn, start_ts, end_ts, 0, 10)
        assert bo.compute_tool_success_rate(conn, s) == 0.0

    def test_mixed(self):
        conn = create_test_db()
        s = make_session(conn, "s1")
        start_ts = int(datetime.fromisoformat("2026-03-10T10:00:00+00:00").timestamp())
        end_ts = int(datetime.fromisoformat("2026-03-10T11:00:00+00:00").timestamp())
        add_tool_events(conn, start_ts, end_ts, 7, 3)
        assert bo.compute_tool_success_rate(conn, s) == 0.7

    def test_no_events(self):
        conn = create_test_db()
        s = make_session(conn, "s1")
        assert bo.compute_tool_success_rate(conn, s) == 0.5  # neutral

    def test_no_time_range(self):
        conn = create_test_db()
        s = make_session(conn, "s1", started_at="2026-03-10T10:00:00+00:00", ended_at=None)
        # ended_at is None — need to handle
        conn.execute("UPDATE sessions SET ended_at = NULL WHERE id = 's1'")
        conn.commit()
        s = conn.execute("SELECT * FROM sessions WHERE id = 's1'").fetchone()
        assert bo.compute_tool_success_rate(conn, s) == 0.5


class TestEfficiencyRatio:
    def test_efficient_session(self):
        """Few messages + moderate complexity = efficient."""
        conn = create_test_db()
        s = make_session(conn, "s1", message_count=20, complexity=0.5)
        score = bo.compute_efficiency_ratio(s)
        assert score > 0.5, f"Expected > 0.5, got {score}"

    def test_inefficient_session(self):
        """Many messages + low complexity = inefficient."""
        conn = create_test_db()
        s = make_session(conn, "s1", message_count=200, complexity=0.1)
        score = bo.compute_efficiency_ratio(s)
        assert score < 0.5, f"Expected < 0.5, got {score}"

    def test_no_complexity(self):
        """No complexity data — use message count heuristic."""
        conn = create_test_db()
        s = make_session(conn, "s1", message_count=30, complexity=None)
        score = bo.compute_efficiency_ratio(s)
        assert 0.0 <= score <= 1.0

    def test_zero_messages(self):
        conn = create_test_db()
        s = make_session(conn, "s1", message_count=0, complexity=0.5)
        score = bo.compute_efficiency_ratio(s)
        assert score > 0.5  # Zero messages = very efficient


class TestNoOverrideScore:
    def test_no_override(self):
        conn = create_test_db()
        s = make_session(conn, "s1")
        assert bo.compute_no_override_score(conn, s) == 1.0

    def test_model_switch_command(self):
        conn = create_test_db()
        s = make_session(conn, "s1")
        start_ts = int(datetime.fromisoformat("2026-03-10T10:00:00+00:00").timestamp())
        add_command_event(conn, start_ts + 100, "switch model opus")
        assert bo.compute_no_override_score(conn, s) == 0.0

    def test_opus_command(self):
        conn = create_test_db()
        s = make_session(conn, "s1")
        start_ts = int(datetime.fromisoformat("2026-03-10T10:00:00+00:00").timestamp())
        add_command_event(conn, start_ts + 100, "opus")
        assert bo.compute_no_override_score(conn, s) == 0.0

    def test_unrelated_command(self):
        conn = create_test_db()
        s = make_session(conn, "s1")
        start_ts = int(datetime.fromisoformat("2026-03-10T10:00:00+00:00").timestamp())
        add_command_event(conn, start_ts + 100, "git status")
        assert bo.compute_no_override_score(conn, s) == 1.0


class TestNoFollowupScore:
    def test_no_followup(self):
        conn = create_test_db()
        s = make_session(conn, "s1", project_path="/test/project",
                        ended_at="2026-03-10T11:00:00+00:00")
        assert bo.compute_no_followup_score(conn, s) == 1.0

    def test_followup_within_24h(self):
        conn = create_test_db()
        s = make_session(conn, "s1", project_path="/test/project",
                        ended_at="2026-03-10T11:00:00+00:00")
        # Add a follow-up session 2 hours later on same project
        make_session(conn, "s2", project_path="/test/project",
                    started_at="2026-03-10T13:00:00+00:00",
                    ended_at="2026-03-10T14:00:00+00:00")
        assert bo.compute_no_followup_score(conn, s) == 0.0

    def test_followup_after_24h(self):
        conn = create_test_db()
        s = make_session(conn, "s1", project_path="/test/project",
                        ended_at="2026-03-10T11:00:00+00:00")
        # Add session 25 hours later — outside window
        make_session(conn, "s2", project_path="/test/project",
                    started_at="2026-03-11T12:00:00+00:00",
                    ended_at="2026-03-11T13:00:00+00:00")
        assert bo.compute_no_followup_score(conn, s) == 1.0

    def test_followup_different_project(self):
        conn = create_test_db()
        s = make_session(conn, "s1", project_path="/test/project-a",
                        ended_at="2026-03-10T11:00:00+00:00")
        # Follow-up on different project doesn't count
        make_session(conn, "s2", project_path="/test/project-b",
                    started_at="2026-03-10T13:00:00+00:00",
                    ended_at="2026-03-10T14:00:00+00:00")
        assert bo.compute_no_followup_score(conn, s) == 1.0


# --- Composite Score Tests ---

class TestCompositeScore:
    def test_perfect_session(self):
        """A perfect session: completed, all tools pass, efficient, no override, no followup."""
        conn = create_test_db()
        s = make_session(conn, "perfect", outcome="success", message_count=20, complexity=0.5)
        start_ts = int(datetime.fromisoformat("2026-03-10T10:00:00+00:00").timestamp())
        end_ts = int(datetime.fromisoformat("2026-03-10T11:00:00+00:00").timestamp())
        add_tool_events(conn, start_ts, end_ts, 20, 0)

        result = bo.compute_behavioral_score(conn, s)
        assert result["behavioral_score"] >= 0.8, f"Expected >= 0.8, got {result['behavioral_score']}"
        assert result["components"]["completion"] == 1.0
        assert result["components"]["tool_success"] == 1.0
        assert result["session_id"] == "perfect"
        assert "ace_quality_score" in result  # Preserved as weak signal

    def test_terrible_session(self):
        """Abandoned, tools failed, many messages, model override, followup needed."""
        conn = create_test_db()
        s = make_session(conn, "terrible", outcome="abandoned", message_count=500,
                        complexity=0.1, project_path="/test/bad")
        start_ts = int(datetime.fromisoformat("2026-03-10T10:00:00+00:00").timestamp())
        end_ts = int(datetime.fromisoformat("2026-03-10T11:00:00+00:00").timestamp())
        add_tool_events(conn, start_ts, end_ts, 2, 18)
        add_command_event(conn, start_ts + 100, "switch to opus")
        # Add follow-up
        make_session(conn, "terrible-followup", project_path="/test/bad",
                    started_at="2026-03-10T12:00:00+00:00",
                    ended_at="2026-03-10T13:00:00+00:00")

        result = bo.compute_behavioral_score(conn, s)
        assert result["behavioral_score"] <= 0.3, f"Expected <= 0.3, got {result['behavioral_score']}"
        assert result["components"]["completion"] == 0.0
        assert result["components"]["no_override"] == 0.0
        assert result["components"]["no_followup"] == 0.0

    def test_score_bounds(self):
        """Score is always between 0.0 and 1.0."""
        conn = create_test_db()
        for outcome in ["success", "abandoned", "partial", "quick"]:
            s = make_session(conn, f"bounds-{outcome}", outcome=outcome)
            result = bo.compute_behavioral_score(conn, s)
            assert 0.0 <= result["behavioral_score"] <= 1.0, \
                f"Score {result['behavioral_score']} out of bounds for {outcome}"

    def test_weights_sum_to_one(self):
        """Verify weights sum to 1.0."""
        total = sum(bo.WEIGHTS.values())
        assert abs(total - 1.0) < 1e-10, f"Weights sum to {total}, expected 1.0"

    def test_ace_score_preserved(self):
        """ACE quality_score is preserved as weak signal, not used as ground truth."""
        conn = create_test_db()
        s = make_session(conn, "ace-test", quality_score=0.95)
        result = bo.compute_behavioral_score(conn, s)
        assert result["ace_quality_score"] == 0.95
        # The ace_quality_score should NOT affect the behavioral score
        s2 = make_session(conn, "ace-test2", quality_score=0.1)
        result2 = bo.compute_behavioral_score(conn, s2)
        # Same session params, different ACE score → same behavioral score
        assert result["behavioral_score"] == result2["behavioral_score"]


# --- Pipeline Tests ---

class TestProcessingPipeline:
    def test_process_and_output(self):
        """Full pipeline: process sessions → write JSONL → verify output."""
        conn = create_test_db()
        make_session(conn, "pipe-1", outcome="success")
        make_session(conn, "pipe-2", outcome="abandoned")

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as db_file:
            db_path = db_file.name

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as out_file:
            out_path = Path(out_file.name)

        try:
            # Copy in-memory db to temp file
            file_conn = sqlite3.connect(db_path)
            conn.backup(file_conn)
            file_conn.close()

            stats = bo.process_sessions(db_path=db_path, output_path=out_path)
            assert stats["processed"] == 2
            assert stats["skipped"] == 0
            assert stats["errors"] == 0

            # Verify JSONL output
            with open(out_path) as f:
                lines = [json.loads(l) for l in f if l.strip()]
            assert len(lines) == 2
            assert lines[0]["session_id"] == "pipe-1"
            assert lines[1]["session_id"] == "pipe-2"
            assert lines[0]["behavioral_score"] > lines[1]["behavioral_score"]

            # Re-run should skip already processed
            stats2 = bo.process_sessions(db_path=db_path, output_path=out_path)
            assert stats2["processed"] == 0
            assert stats2["skipped"] == 2
        finally:
            os.unlink(db_path)
            os.unlink(out_path)

    def test_backfill_mode(self):
        """Backfill processes all sessions including edge cases."""
        conn = create_test_db()
        # Session with minimal data
        make_session(conn, "minimal", outcome=None, message_count=0,
                    complexity=None, project_path=None)

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as db_file:
            db_path = db_file.name
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as out_file:
            out_path = Path(out_file.name)

        try:
            file_conn = sqlite3.connect(db_path)
            conn.backup(file_conn)
            file_conn.close()

            stats = bo.process_sessions(db_path=db_path, output_path=out_path, backfill=True)
            assert stats["processed"] == 1
            assert stats["errors"] == 0
        finally:
            os.unlink(db_path)
            os.unlink(out_path)


# --- Run all tests ---

def run_tests():
    """Run all test classes and methods."""
    test_classes = [
        TestCompletionScore,
        TestToolSuccessRate,
        TestEfficiencyRatio,
        TestNoOverrideScore,
        TestNoFollowupScore,
        TestCompositeScore,
        TestProcessingPipeline,
    ]

    passed = 0
    failed = 0
    errors = []

    for cls in test_classes:
        instance = cls()
        for method_name in dir(instance):
            if not method_name.startswith("test_"):
                continue
            method = getattr(instance, method_name)
            test_name = f"{cls.__name__}.{method_name}"
            try:
                method()
                passed += 1
                print(f"  PASS: {test_name}")
            except AssertionError as e:
                failed += 1
                errors.append((test_name, str(e)))
                print(f"  FAIL: {test_name} — {e}")
            except Exception as e:
                failed += 1
                errors.append((test_name, str(e)))
                print(f"  ERROR: {test_name} — {e}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if errors:
        print("\nFailures:")
        for name, msg in errors:
            print(f"  {name}: {msg}")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
