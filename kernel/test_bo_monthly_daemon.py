#!/usr/bin/env python3
"""
Tests for US-110: Monthly BO Trigger + A/B Infrastructure

Tests:
- A/B assignment distributes ~70/10/10/10
- Analysis promotes winning candidate
- Analysis retains baseline when no winner
- Skip when no candidates available
"""

import json
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest

# Ensure kernel is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the module using importlib since it has a hyphen
import importlib.util

_mod_path = Path(__file__).parent / "bo-monthly-daemon.py"
_spec = importlib.util.spec_from_file_location("bo_monthly_daemon", _mod_path)
bo_daemon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bo_daemon)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dirs(tmp_path):
    """Create temp directories and patch module-level paths."""
    ab_file = tmp_path / "bo-ab-test.json"
    bandit_file = tmp_path / "bandit-history.jsonl"
    reports_dir = tmp_path / "bo-reports"
    reports_dir.mkdir()
    params_file = tmp_path / "learnable-params.json"

    # Write a minimal learnable-params.json
    params_data = {
        "version": "1.0.0",
        "description": "test",
        "banditEnabled": False,
        "parameters": [
            {
                "id": "graph_entropy_weight",
                "configFile": "config/graph-signal-weights.json",
                "jsonPath": "weights.entropy",
                "value": 0.30,
                "min": 0.05,
                "max": 0.60,
                "learnRate": 0.02,
                "group": "graph_signal",
            },
            {
                "id": "graph_gini_weight",
                "configFile": "config/graph-signal-weights.json",
                "jsonPath": "weights.gini",
                "value": 0.25,
                "min": 0.05,
                "max": 0.60,
                "learnRate": 0.02,
                "group": "graph_signal",
            },
        ],
        "groups": {
            "graph_signal": {
                "constraint": "independent",
                "description": "test",
            }
        },
        "updated": "2026-03-14",
        "updatedBy": "test",
    }
    params_file.write_text(json.dumps(params_data, indent=2))

    patches = {
        "AB_TEST_FILE": ab_file,
        "BANDIT_HISTORY": bandit_file,
        "BO_REPORTS_DIR": reports_dir,
        "LEARNABLE_PARAMS": params_file,
    }

    with patch.multiple(bo_daemon, **patches):
        yield {
            "ab_file": ab_file,
            "bandit_file": bandit_file,
            "reports_dir": reports_dir,
            "params_file": params_file,
        }


def _make_ab_config(candidates=None, status="running", start_epoch=None):
    """Helper to create an A/B test config."""
    now = datetime.now(tz=timezone.utc)
    if start_epoch is None:
        start_epoch = (now - timedelta(days=5)).timestamp()
    return {
        "baseline": {"graph_entropy_weight": 0.30, "graph_gini_weight": 0.25},
        "candidates": candidates or [
            {"graph_entropy_weight": 0.35, "graph_gini_weight": 0.20},
            {"graph_entropy_weight": 0.28, "graph_gini_weight": 0.30},
            {"graph_entropy_weight": 0.40, "graph_gini_weight": 0.22},
        ],
        "start_ts": datetime.fromtimestamp(start_epoch, tz=timezone.utc).isoformat(),
        "start_epoch": start_epoch,
        "decision_count": 0,
        "status": status,
        "month": now.strftime("%Y-%m"),
        "created_by": "test",
    }


def _write_bandit_history(path, decisions):
    """Write bandit history decisions to JSONL file."""
    with open(path, "w") as f:
        for d in decisions:
            f.write(json.dumps(d) + "\n")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestABAssignment:
    """Test that A/B assignment distributes ~70/10/10/10."""

    def test_distribution_approximately_correct(self, tmp_dirs):
        """Hash-based assignment should approximate 70/10/10/10 split."""
        ab_config = _make_ab_config()
        tmp_dirs["ab_file"].write_text(json.dumps(ab_config))

        counts = {"baseline": 0, "candidate_0": 0, "candidate_1": 0, "candidate_2": 0}
        n = 10000

        for i in range(n):
            session_id = f"session-{i}-{i*7}"
            result = bo_daemon.get_ab_assignment(session_id, ab_config)
            counts[result["variant"]] += 1

        # Allow 3% tolerance on each bucket
        baseline_pct = counts["baseline"] / n
        c0_pct = counts["candidate_0"] / n
        c1_pct = counts["candidate_1"] / n
        c2_pct = counts["candidate_2"] / n

        assert 0.65 <= baseline_pct <= 0.75, f"Baseline {baseline_pct:.2%} outside [65%, 75%]"
        assert 0.07 <= c0_pct <= 0.13, f"Candidate 0 {c0_pct:.2%} outside [7%, 13%]"
        assert 0.07 <= c1_pct <= 0.13, f"Candidate 1 {c1_pct:.2%} outside [7%, 13%]"
        assert 0.07 <= c2_pct <= 0.13, f"Candidate 2 {c2_pct:.2%} outside [7%, 13%]"

    def test_deterministic_assignment(self, tmp_dirs):
        """Same session ID always gets same variant."""
        ab_config = _make_ab_config()
        result1 = bo_daemon.get_ab_assignment("fixed-session-id", ab_config)
        result2 = bo_daemon.get_ab_assignment("fixed-session-id", ab_config)
        assert result1["variant"] == result2["variant"]
        assert result1["weights"] == result2["weights"]

    def test_no_active_test_returns_baseline(self, tmp_dirs):
        """When no test is running, always return baseline."""
        ab_config = _make_ab_config(status="completed")
        result = bo_daemon.get_ab_assignment("any-session", ab_config)
        assert result["variant"] == "baseline"

    def test_none_config_returns_baseline(self, tmp_dirs):
        """When config is None, return baseline."""
        result = bo_daemon.get_ab_assignment("any-session", None)
        assert result["variant"] == "baseline"


class TestAnalysis:
    """Test A/B analysis logic."""

    def test_promotes_winning_candidate(self, tmp_dirs):
        """When a candidate beats baseline by >= 3%, promote it."""
        start_epoch = (datetime.now(tz=timezone.utc) - timedelta(days=5)).timestamp()
        ab_config = _make_ab_config(start_epoch=start_epoch)
        tmp_dirs["ab_file"].write_text(json.dumps(ab_config))

        # Build 200 decisions: baseline avg=0.70, candidate_1 avg=0.80 (>3% better)
        decisions = []
        for i in range(100):
            decisions.append({
                "ts": start_epoch + i * 100,
                "variant": "baseline",
                "reward": 0.70,
            })
        for i in range(20):
            decisions.append({
                "ts": start_epoch + (100 + i) * 100,
                "variant": "candidate_0",
                "reward": 0.68,
            })
        for i in range(20):
            decisions.append({
                "ts": start_epoch + (120 + i) * 100,
                "variant": "candidate_1",
                "reward": 0.80,
            })
        for i in range(20):
            decisions.append({
                "ts": start_epoch + (140 + i) * 100,
                "variant": "candidate_2",
                "reward": 0.71,
            })

        _write_bandit_history(tmp_dirs["bandit_file"], decisions)

        bo_daemon.analyze()

        # Check A/B test was updated
        updated = json.loads(tmp_dirs["ab_file"].read_text())
        assert updated["status"] == "promoted"
        assert updated["result"]["promoted"] is True
        assert updated["result"]["winner"] == "candidate_1"

        # Check report was written
        reports = list(tmp_dirs["reports_dir"].glob("*.json"))
        assert len(reports) == 1
        report = json.loads(reports[0].read_text())
        assert report["promoted"] is True
        assert report["best_candidate"] == "candidate_1"

    def test_retains_baseline_when_no_winner(self, tmp_dirs):
        """When no candidate beats baseline by >= 3%, retain baseline."""
        start_epoch = (datetime.now(tz=timezone.utc) - timedelta(days=5)).timestamp()
        ab_config = _make_ab_config(start_epoch=start_epoch)
        tmp_dirs["ab_file"].write_text(json.dumps(ab_config))

        # All variants perform similarly (within 3%)
        decisions = []
        for i in range(100):
            decisions.append({
                "ts": start_epoch + i * 100,
                "variant": "baseline",
                "reward": 0.75,
            })
        for i in range(20):
            decisions.append({
                "ts": start_epoch + (100 + i) * 100,
                "variant": "candidate_0",
                "reward": 0.76,  # Only +1.3%, below 3% threshold
            })
        for i in range(20):
            decisions.append({
                "ts": start_epoch + (120 + i) * 100,
                "variant": "candidate_1",
                "reward": 0.74,
            })
        for i in range(20):
            decisions.append({
                "ts": start_epoch + (140 + i) * 100,
                "variant": "candidate_2",
                "reward": 0.73,
            })

        _write_bandit_history(tmp_dirs["bandit_file"], decisions)

        bo_daemon.analyze()

        updated = json.loads(tmp_dirs["ab_file"].read_text())
        assert updated["status"] == "retained"
        assert updated["result"]["promoted"] is False

        reports = list(tmp_dirs["reports_dir"].glob("*.json"))
        assert len(reports) == 1
        report = json.loads(reports[0].read_text())
        assert report["promoted"] is False

    def test_insufficient_decisions_skips(self, tmp_dirs):
        """When fewer than MIN_DECISIONS, analysis should skip."""
        start_epoch = (datetime.now(tz=timezone.utc) - timedelta(days=1)).timestamp()
        ab_config = _make_ab_config(start_epoch=start_epoch)
        tmp_dirs["ab_file"].write_text(json.dumps(ab_config))

        # Only 50 decisions (below MIN_DECISIONS=150)
        decisions = [
            {"ts": start_epoch + i * 100, "variant": "baseline", "reward": 0.70}
            for i in range(50)
        ]
        _write_bandit_history(tmp_dirs["bandit_file"], decisions)

        bo_daemon.analyze()

        # Status should remain running (not analyzed)
        updated = json.loads(tmp_dirs["ab_file"].read_text())
        assert updated["status"] == "running"


class TestNoCandidates:
    """Test behavior when BO produces no candidates."""

    def test_skip_when_no_candidates(self, tmp_dirs):
        """When BO returns empty candidates, skip A/B test creation."""
        mock_bo_module = MagicMock()
        mock_optimizer = MagicMock()
        mock_optimizer.propose.return_value = []
        mock_bo_module.BayesianWeightOptimizer.return_value = mock_optimizer

        with patch.object(bo_daemon, "_load_bo_module", return_value=mock_bo_module):
            with patch.object(bo_daemon, "get_current_weights", return_value={"a": 0.5}):
                bo_daemon.run_bo()

        # No A/B test should be created
        assert not tmp_dirs["ab_file"].exists()


class TestHumanOverride:
    """Test manual approve/reject."""

    def test_approve(self, tmp_dirs):
        ab_config = _make_ab_config()
        ab_config["result"] = {"promoted": True, "winner": "candidate_0", "improvement": 0.05}
        tmp_dirs["ab_file"].write_text(json.dumps(ab_config))

        bo_daemon.approve()

        updated = json.loads(tmp_dirs["ab_file"].read_text())
        assert updated["status"] == "approved"

        # Weights should be updated in params file
        params = json.loads(tmp_dirs["params_file"].read_text())
        for p in params["parameters"]:
            if p["id"] == "graph_entropy_weight":
                assert p["value"] == 0.35  # From candidate_0

    def test_reject(self, tmp_dirs):
        ab_config = _make_ab_config()
        ab_config["result"] = {"promoted": True, "winner": "candidate_0", "improvement": 0.05}
        tmp_dirs["ab_file"].write_text(json.dumps(ab_config))

        bo_daemon.reject()

        updated = json.loads(tmp_dirs["ab_file"].read_text())
        assert updated["status"] == "rejected"
        assert updated["result"]["promoted"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
