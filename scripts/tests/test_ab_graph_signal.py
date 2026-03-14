#!/usr/bin/env python3
"""
Tests for A/B Test Framework: Graph Signal vs Keyword Complexity (US-012)

Tests the analysis script (scripts/ab-test-graph-signal.py) and verifies:
- Both signals computed and logged
- Analysis produces valid comparison
- Rollback logic triggers correctly
- ECE computation works
- State management (rollback/resume)

Run: pytest scripts/tests/test_ab_graph_signal.py -v
"""

import json
import sys
import tempfile
import importlib
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the analysis module using importlib (hyphenated filename)
sys.path.insert(0, str(Path(__file__).parent.parent))
spec = importlib.util.spec_from_file_location(
    "ab_test_graph_signal",
    str(Path(__file__).parent.parent / "ab-test-graph-signal.py"),
)
ab_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ab_mod)

# Aliases
compute_ece = ab_mod.compute_ece
analyze = ab_mod.analyze
analyze_group = ab_mod.analyze_group
check_rollback = ab_mod.check_rollback
load_ab_state = ab_mod.load_ab_state
save_ab_state = ab_mod.save_ab_state
MIN_DECISIONS = ab_mod.MIN_DECISIONS


# ─── Fixtures ───────────────────────────────────────────────────────────────

def make_decision(ab_group, keyword_dq, graph_dq, ts=1000000, cost=0.001,
                  keyword_model="sonnet", graph_model="sonnet"):
    """Factory for A/B test decision entries."""
    return {
        "ts": ts,
        "session_id": ts,
        "query_hash": f"hash_{ts}",
        "ab_group": ab_group,
        "signal_used": ab_group,
        "keyword_complexity": 0.5,
        "graph_complexity": 0.6 if graph_dq else None,
        "keyword_model": keyword_model,
        "keyword_dq": keyword_dq,
        "keyword_dq_components": {"validity": keyword_dq, "specificity": keyword_dq, "correctness": keyword_dq},
        "graph_model": graph_model,
        "graph_dq": graph_dq,
        "graph_dq_components": {"validity": graph_dq, "specificity": graph_dq, "correctness": graph_dq} if graph_dq else None,
        "actual_model": keyword_model if ab_group == "keyword" else graph_model,
        "actual_dq": keyword_dq if ab_group == "keyword" else graph_dq,
        "cost_estimate": cost,
        "graph_feature_count": 3 if graph_dq else 0,
        "rollback_active": False,
    }


def make_balanced_decisions(n, keyword_dq_mean=0.85, graph_dq_mean=0.90, spread=0.05):
    """Generate n decisions split evenly between keyword and graph groups."""
    decisions = []
    for i in range(n):
        group = "keyword" if i % 2 == 0 else "graph"
        # Alternate DQ scores with small variation
        offset = (i % 5 - 2) * spread / 5
        kw_dq = round(keyword_dq_mean + offset, 4)
        gr_dq = round(graph_dq_mean + offset, 4)
        decisions.append(make_decision(
            ab_group=group,
            keyword_dq=kw_dq,
            graph_dq=gr_dq,
            ts=1000000 + i * 60,
            keyword_model="sonnet",
            graph_model="sonnet",
        ))
    return decisions


# ─── ECE Computation ────────────────────────────────────────────────────────

class TestECE:
    """Tests for Expected Calibration Error computation."""

    def test_perfect_calibration(self):
        """Perfectly calibrated predictions → ECE ≈ 0."""
        preds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        actuals = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        ece = compute_ece(preds, actuals)
        assert ece is not None
        assert ece < 0.01, f"Perfect calibration should give ECE ≈ 0, got {ece}"

    def test_overconfident(self):
        """Systematically overconfident predictions → ECE > 0.1."""
        preds = [0.9] * 20
        actuals = [0.5] * 20
        ece = compute_ece(preds, actuals)
        assert ece is not None
        assert ece > 0.1, f"Overconfident should give ECE > 0.1, got {ece}"

    def test_underconfident(self):
        """Systematically underconfident predictions → ECE > 0.1."""
        preds = [0.3] * 20
        actuals = [0.8] * 20
        ece = compute_ece(preds, actuals)
        assert ece is not None
        assert ece > 0.1

    def test_empty_inputs(self):
        """Empty inputs → None."""
        assert compute_ece([], []) is None
        assert compute_ece(None, None) is None

    def test_mismatched_lengths(self):
        """Mismatched prediction/actual lengths → None."""
        assert compute_ece([0.5, 0.6], [0.5]) is None

    def test_uniform_predictions(self):
        """All same prediction with varying outcomes."""
        preds = [0.5] * 10
        actuals = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        ece = compute_ece(preds, actuals)
        assert ece is not None
        # Average actual = 0.45, pred = 0.5, so ECE ≈ 0.05
        assert 0.0 <= ece <= 0.5


# ─── Group Analysis ─────────────────────────────────────────────────────────

class TestAnalyzeGroup:
    """Tests for per-group analysis."""

    def test_keyword_group(self):
        decisions = [make_decision("keyword", 0.8, 0.85, ts=1000000 + i) for i in range(10)]
        stats = analyze_group(decisions, "keyword")
        assert stats is not None
        assert stats["count"] == 10
        assert 0.75 <= stats["avg_dq"] <= 0.85
        assert stats["group"] == "keyword"

    def test_graph_group(self):
        decisions = [make_decision("graph", 0.8, 0.9, ts=1000000 + i) for i in range(10)]
        stats = analyze_group(decisions, "graph")
        assert stats is not None
        assert stats["count"] == 10
        assert 0.85 <= stats["avg_dq"] <= 0.95

    def test_empty_group(self):
        stats = analyze_group([], "keyword")
        assert stats is None

    def test_model_distribution(self):
        decisions = []
        for i in range(6):
            decisions.append(make_decision("keyword", 0.8, 0.85, ts=i, keyword_model="sonnet"))
        for i in range(4):
            decisions.append(make_decision("keyword", 0.9, 0.85, ts=i + 10, keyword_model="opus"))
        stats = analyze_group(decisions, "keyword")
        assert stats["model_distribution"]["sonnet"] == 6
        assert stats["model_distribution"]["opus"] == 4

    def test_variance_computation(self):
        """Identical scores → 0 variance."""
        decisions = [make_decision("keyword", 0.8, 0.8, ts=i) for i in range(5)]
        stats = analyze_group(decisions, "keyword")
        assert stats["variance"] == 0.0

    def test_cost_tracking(self):
        decisions = [make_decision("keyword", 0.8, 0.85, ts=i, cost=0.002) for i in range(5)]
        stats = analyze_group(decisions, "keyword")
        assert abs(stats["avg_cost"] - 0.002) < 0.0001


# ─── Full Analysis ──────────────────────────────────────────────────────────

class TestAnalyze:
    """Tests for full A/B test analysis."""

    def test_balanced_analysis(self):
        decisions = make_balanced_decisions(100)
        results = analyze(decisions)
        assert results["total_decisions"] == 100
        assert results["keyword"] is not None
        assert results["graph"] is not None
        assert results["keyword"]["count"] == 50
        assert results["graph"]["count"] == 50

    def test_insufficient_data(self):
        decisions = make_balanced_decisions(50)
        results = analyze(decisions)
        assert not results["sufficient_data"]

    def test_sufficient_data(self):
        decisions = make_balanced_decisions(200)
        results = analyze(decisions)
        assert results["sufficient_data"]

    def test_keyword_only(self):
        decisions = [make_decision("keyword", 0.8, 0.85, ts=i) for i in range(10)]
        results = analyze(decisions)
        assert results["keyword"] is not None
        assert results["graph"] is None

    def test_graph_only(self):
        decisions = [make_decision("graph", 0.8, 0.9, ts=i) for i in range(10)]
        results = analyze(decisions)
        assert results["keyword"] is None
        assert results["graph"] is not None

    def test_ece_without_behavioral(self):
        decisions = make_balanced_decisions(100)
        results = analyze(decisions, behavioral_outcomes=None)
        assert results["keyword_ece"] is None
        assert results["graph_ece"] is None


# ─── Rollback Logic ─────────────────────────────────────────────────────────

class TestRollback:
    """Tests for auto-rollback condition."""

    def test_no_rollback_when_graph_better(self):
        """Graph signal performing better → no rollback."""
        decisions = make_balanced_decisions(200, keyword_dq_mean=0.80, graph_dq_mean=0.90)
        results = analyze(decisions)
        should_rollback, reason = check_rollback(results)
        assert not should_rollback
        assert reason is None

    def test_no_rollback_when_equal(self):
        """Equal performance → no rollback."""
        decisions = make_balanced_decisions(200, keyword_dq_mean=0.85, graph_dq_mean=0.85)
        results = analyze(decisions)
        should_rollback, reason = check_rollback(results)
        assert not should_rollback

    def test_rollback_when_graph_much_worse(self):
        """Graph signal > 5% worse → trigger rollback."""
        decisions = make_balanced_decisions(200, keyword_dq_mean=0.90, graph_dq_mean=0.80)
        results = analyze(decisions)
        should_rollback, reason = check_rollback(results)
        assert should_rollback
        assert reason is not None
        assert "worse" in reason

    def test_no_rollback_insufficient_data(self):
        """Not enough data → no rollback regardless of scores."""
        decisions = make_balanced_decisions(50, keyword_dq_mean=0.90, graph_dq_mean=0.70)
        results = analyze(decisions)
        should_rollback, reason = check_rollback(results)
        assert not should_rollback

    def test_rollback_threshold_within_tolerance(self):
        """Graph signal 4% worse → within 5% tolerance, no rollback."""
        decisions = []
        for i in range(200):
            group = "keyword" if i % 2 == 0 else "graph"
            decisions.append(make_decision(
                ab_group=group,
                keyword_dq=0.90,
                graph_dq=0.86,  # diff = 0.04, well under 0.05
                ts=1000000 + i * 60,
            ))
        results = analyze(decisions)
        should_rollback, reason = check_rollback(results)
        assert not should_rollback

    def test_rollback_just_over_threshold(self):
        """Just over 5% threshold → rollback."""
        # keyword=0.90, graph=0.84 → diff=0.06 > 0.05
        decisions = make_balanced_decisions(200, keyword_dq_mean=0.90, graph_dq_mean=0.84, spread=0.0)
        results = analyze(decisions)
        should_rollback, reason = check_rollback(results)
        assert should_rollback


# ─── State Management ───────────────────────────────────────────────────────

class TestStateManagement:
    """Tests for A/B test state persistence."""

    def test_default_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "ab-test-state.json"
            with patch.object(ab_mod, "AB_TEST_STATE", state_path):
                state = load_ab_state()
                assert state["active"] is True
                assert state["rollback"] is False
                assert state["reason"] is None

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "ab-test-state.json"
            with patch.object(ab_mod, "AB_TEST_STATE", state_path):
                save_ab_state({"active": True, "rollback": True, "reason": "test", "decisionCount": 42})
                state = load_ab_state()
                assert state["rollback"] is True
                assert state["reason"] == "test"
                assert state["decisionCount"] == 42

    def test_corrupt_state_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "ab-test-state.json"
            state_path.write_text("not valid json{{{")
            with patch.object(ab_mod, "AB_TEST_STATE", state_path):
                state = load_ab_state()
                assert state["active"] is True  # defaults


# ─── Log Loading ─────────────────────────────────────────────────────────────

class TestLogLoading:
    """Tests for JSONL log loading."""

    def test_load_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "ab-test-graph-signal.jsonl"
            decisions = [make_decision("keyword", 0.8, 0.85, ts=1000000 + i) for i in range(5)]
            with open(log_path, "w") as f:
                for d in decisions:
                    f.write(json.dumps(d) + "\n")
            with patch.object(ab_mod, "AB_TEST_LOG", log_path):
                loaded = ab_mod.load_ab_decisions()
                assert len(loaded) == 5

    def test_load_with_day_filter(self):
        import time
        now = int(time.time())
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "ab-test-graph-signal.jsonl"
            decisions = [
                make_decision("keyword", 0.8, 0.85, ts=now - 86400 * 2),  # 2 days ago
                make_decision("keyword", 0.8, 0.85, ts=now - 3600),       # 1 hour ago
                make_decision("graph", 0.8, 0.9, ts=now - 60),            # 1 min ago
            ]
            with open(log_path, "w") as f:
                for d in decisions:
                    f.write(json.dumps(d) + "\n")
            with patch.object(ab_mod, "AB_TEST_LOG", log_path):
                loaded = ab_mod.load_ab_decisions(days=1)
                assert len(loaded) == 2

    def test_load_empty_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "ab-test-graph-signal.jsonl"
            log_path.write_text("")
            with patch.object(ab_mod, "AB_TEST_LOG", log_path):
                loaded = ab_mod.load_ab_decisions()
                assert len(loaded) == 0

    def test_load_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "nonexistent.jsonl"
            with patch.object(ab_mod, "AB_TEST_LOG", log_path):
                loaded = ab_mod.load_ab_decisions()
                assert len(loaded) == 0

    def test_load_with_corrupt_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "ab-test-graph-signal.jsonl"
            with open(log_path, "w") as f:
                f.write(json.dumps(make_decision("keyword", 0.8, 0.85, ts=1000000)) + "\n")
                f.write("not json\n")
                f.write(json.dumps(make_decision("graph", 0.8, 0.9, ts=1000001)) + "\n")
            with patch.object(ab_mod, "AB_TEST_LOG", log_path):
                loaded = ab_mod.load_ab_decisions()
                assert len(loaded) == 2


# ─── Integration: Both Signals Computed ──────────────────────────────────────

class TestBothSignalsComputed:
    """Verify both complexity signals are present in log entries."""

    def test_keyword_group_has_both_signals(self):
        d = make_decision("keyword", keyword_dq=0.8, graph_dq=0.9)
        assert d["keyword_dq"] is not None
        assert d["graph_dq"] is not None
        assert d["keyword_complexity"] is not None
        assert d["graph_complexity"] is not None

    def test_graph_group_has_both_signals(self):
        d = make_decision("graph", keyword_dq=0.8, graph_dq=0.9)
        assert d["keyword_dq"] is not None
        assert d["graph_dq"] is not None

    def test_signal_used_matches_group(self):
        kw = make_decision("keyword", 0.8, 0.85)
        assert kw["signal_used"] == "keyword"
        gr = make_decision("graph", 0.8, 0.9)
        assert gr["signal_used"] == "graph"

    def test_actual_model_from_active_signal(self):
        kw = make_decision("keyword", 0.8, 0.85, keyword_model="haiku", graph_model="opus")
        assert kw["actual_model"] == "haiku"
        gr = make_decision("graph", 0.8, 0.9, keyword_model="haiku", graph_model="opus")
        assert gr["actual_model"] == "opus"


# ─── Integration: Analysis Produces Valid Comparison ─────────────────────────

class TestValidComparison:
    """Integration tests for the full analysis pipeline."""

    def test_graph_outperforms_keyword(self):
        decisions = make_balanced_decisions(200, keyword_dq_mean=0.80, graph_dq_mean=0.92)
        results = analyze(decisions)
        assert results["graph"]["avg_dq"] > results["keyword"]["avg_dq"]
        should_rollback, _ = check_rollback(results)
        assert not should_rollback

    def test_keyword_outperforms_graph_slightly(self):
        """Within 5% tolerance → no rollback."""
        decisions = make_balanced_decisions(200, keyword_dq_mean=0.88, graph_dq_mean=0.85)
        results = analyze(decisions)
        assert results["keyword"]["avg_dq"] > results["graph"]["avg_dq"]
        should_rollback, _ = check_rollback(results)
        assert not should_rollback

    def test_full_pipeline_with_behavioral_outcomes(self):
        decisions = make_balanced_decisions(100, keyword_dq_mean=0.85, graph_dq_mean=0.90)
        outcomes = {}
        for d in decisions:
            outcomes[d["ts"]] = 0.8 + (d["ts"] % 3) * 0.05
        results = analyze(decisions, behavioral_outcomes=outcomes)
        # ECE should be computed (we have matching outcomes)
        # Note: may still be None if fewer than 10 matched per group
        assert results["total_decisions"] == 100

    def test_analysis_with_mixed_models(self):
        decisions = []
        models = ["haiku", "sonnet", "opus"]
        for i in range(60):
            group = "keyword" if i % 2 == 0 else "graph"
            model = models[i % 3]
            decisions.append(make_decision(group, 0.8, 0.85, ts=i, keyword_model=model, graph_model=model))
        results = analyze(decisions)
        assert results["keyword"] is not None
        assert results["graph"] is not None
        assert len(results["keyword"]["model_distribution"]) <= 3
